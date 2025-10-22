import itertools
import concurrent.futures
import semchunk
from time import time

from text_processing_utils.boolean_checks import is_plural
from text_processing_utils.locate import locate_span_in_context
from text_processing_utils.sentences import lower_first_letter_if_sent_start
from text_processing_utils.batches import get_n_batches, get_batches_of_roughly_equal_size
from text_processing_utils.highlight_context import enclose_with_special_symbol, adapt_offsets_to_special_symbol_enclosings

from quinex import msg
from quinex.extract.utils.transformers import load_transformers_pipe, get_text_chunking_helper
from quinex.config.models_registry import MODELS



class MeasurementContextExtraction:
    """
    Extract measurement context for quantities, i.e., the measured properties, entities, and qualifiers.

    Args:
        model_path (str): Path to the model.
        enclosing_markers (dict, optional): Special symbols to enclose previous predictions in the context (see src/quinex/config/model_registry.yml).
        questions_templates (dict, optional): Question templates for property, entity, and qualifier extraction (see src/quinex/config/model_registry.yml).
        devices (list, optional): List of devices to use.
        batch_size (int, optional): Batch size used for extracting measured property and entity.
        qualifier_extraction_batch_size (int, optional): Batch size used for extracting qualifiers.
        max_new_tokens (int, optional): Maximum number of new tokens to generate per answer.
        enable_qualifier_extraction (bool, optional): Whether to enable qualifier extraction.
        create_new_pipes_for_qlf_extraction (bool, optional): Whether to use a seperate pipeline for qualifier extraction instead of using the same pipeline as for property and entity extraction.
        empty_dict_for_empty_prediction (bool, optional): Whether to return an empty dict for empty predictions instead of None.        

    """
    
    def __init__(
            self, 
            model_path,
            enclosing_markers: dict=None,
            questions_templates: dict= None,
            devices=["cpu"],
            batch_size=8,
            qualifier_extraction_batch_size=8,
            max_new_tokens=50,
            enable_qualifier_extraction=True,            
            create_new_pipes_for_qlf_extraction=False,
            empty_dict_for_empty_prediction=False,
            dtype="auto",
            verbose=False,
            debug=False
        ): 
        
        self.verbose = verbose
        self.debug = debug
        self.empty_dict_for_empty_prediction = empty_dict_for_empty_prediction

        # Qualifier extraction settings.
        self.enable_qualifier_extraction = enable_qualifier_extraction
        self.qualifier_extraction_batch_size = qualifier_extraction_batch_size

        # Symbols to enclose previous predictions in the context.
        if enclosing_markers == None:        
            enclosing_markers = MODELS["measurement_context_extraction"][model_path]["config"]["enclosing_markers"]
        self.quantity_enclosing = enclosing_markers["quantity"]
        self.property_enclosing = enclosing_markers["property"]
        self.entity_enclosing = enclosing_markers["entity"]

        # Questions for property, entity and qualifier extraction.
        if questions_templates == None:
            questions_templates = MODELS["measurement_context_extraction"][model_path]["config"]["question_templates"]
        self.questions = questions_templates
        self.qualifier_question_keys = [k for k in self.questions.keys() if not k.endswith("_fallback") and not k in ["property_question", "entity_question"]]

        # Get token counter.
        self.token_counter, self.chunk_size = get_text_chunking_helper(model_path, task="text2text-generation")

        # Get longest question for chunking (assumes all qualifier question templates have the same slots).        
        qualifier_question_token_len = [self.token_counter(self.questions[q_key]) for q_key in self.qualifier_question_keys]
        self.longest_qualifier_question_key = self.qualifier_question_keys[qualifier_question_token_len.index(max(qualifier_question_token_len))]
        
        # Get longest fallback question for chunking (assumes all fallback qualifier question templates have the same slots).
        qualifier_fallback_question_token_len = [self.token_counter(self.questions[q_key + "_fallback"]) for q_key in self.qualifier_question_keys]
        self.longest_qualifier_fallback_question_key = self.qualifier_question_keys[qualifier_fallback_question_token_len.index(max(qualifier_fallback_question_token_len))]

        # Add "the" if article or pronoun is missing.    
        article_pronoun_prefixes = ["a", "an", "the", "one", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their", "both", "all", "every"]
        self.perfix_the = lambda x: "the " + x if x.strip().split(" ")[0] not in article_pronoun_prefixes else x
            
        # Load parallel measurement context extraction pipelines.
        self.measurement_context_pipelines = [load_transformers_pipe("text2text-generation", model_path, device, batch_size=batch_size, dtype=dtype, verbose=verbose, max_new_tokens=max_new_tokens) for device in devices]
        
        # Load parallel qualifier extraction pipelines.
        if self.enable_qualifier_extraction:
            if create_new_pipes_for_qlf_extraction:
                self.qualifier_pipelines = [load_transformers_pipe("text2text-generation", model_path, device, batch_size=batch_size, dtype=dtype, verbose=verbose, max_new_tokens=max_new_tokens) for device in devices]
            else:
                self.qualifier_pipelines = self.measurement_context_pipelines
            self.qualifier_pipelines = get_n_batches(self.qualifier_pipelines, len(self.measurement_context_pipelines))


    def __call__(self, quantities, device_rank, text, semantic_boundaries, return_llm_inputs=False, add_curation_fields=False):
        
        if self.verbose:
            msg.info("Extracting measurement context for batch of quantities...")
            start = time()

        # -------------------------------
        #   Extract measured properties  
        # -------------------------------
        properties, property_contexts, property_inputs = self.extract_properties(quantities, text, semantic_boundaries, device_rank)
        if self.verbose:
            msg.good(f"Property extraction done in {round(time()-start, 3)} s.")
            start = time()
        
        # -------------------------------
        #   Extract measured entities
        # -------------------------------
        entities, entity_contexts, entity_inputs, question_template_filling_information = self.extract_entities(quantities, properties, property_contexts, text, semantic_boundaries, device_rank)    
        if self.verbose:
            msg.good(f"Entity extraction done in {round(time()-start, 3)} s.")
            start = time()
        
        # -------------------------------
        #   Extract qualifiers
        # -------------------------------
        qualifiers, qualifier_inputs = self.extract_qualifiers(quantities, properties, entities, entity_contexts, question_template_filling_information, text, semantic_boundaries, device_rank)
        if self.verbose:
            msg.good(f"Qualifier extraction done in {round(time()-start, 3)} s.")

        # -------------------------------
        #   Create output format
        # -------------------------------
        quantitative_statements = self._pack_predictions_into_output_format(quantities, properties, entities, qualifiers, property_inputs, entity_inputs, qualifier_inputs, add_curation_fields=add_curation_fields, return_llm_inputs=return_llm_inputs)
        
        return quantitative_statements
        
    
    def _postprocess_prediction(self, prediction, quantity_span, context, context_char_offset, text, semantic_boundaries):
        """Transforms generated text into annotations and checks if the prediction is implicit or not.
        If the prediction is not implicit, the character offsets of the annotation in the context are determined.
        If the prediction is implicit, the character offsets are set to (0, 0).
        """
                
        surface = prediction["generated_text"].strip()

        if len(surface) == 0:
            # Model abstained from prediction.
            return None
        else:
            # Model made a valid prediction.
            is_implicit, char_offsets = locate_span_in_context(surface, context, text_span=quantity_span, context_char_offset=context_char_offset, semantic_boundaries=semantic_boundaries, text=text)
            annotation = {
                "start": char_offsets[0], 
                "end": char_offsets[1],
                "text": surface,
                "is_implicit": is_implicit
            }

            return annotation


    def extract_properties(self, quantities, text, semantic_boundaries, device_rank):

        # Create prompts for property extraction.
        property_inputs = []
        property_contexts = []
        for quantity in quantities:
            property_question = self.questions["property_question"].format(quantity_span=quantity["text"])
            property_input, context_w_quantity_enclosing, context_wo_enclosing, context_char_offset = self._get_property_input(property_question, quantity, text, semantic_boundaries)
            property_inputs.append(property_input)
            property_contexts.append((context_w_quantity_enclosing, context_wo_enclosing, context_char_offset))

        if self.debug:
            # Make sure that the chunks are not too long.
            for chunk in property_inputs:
                if self.token_counter(chunk) > self.chunk_size:
                    print(f"Warning: Chunk in property extraction is too long ({len(chunk)} > {self.chunk_size}): {chunk}")
                    print(property_inputs)
                
        property_predictions = self.measurement_context_pipelines[device_rank](property_inputs)

        # Post-process property predictions.
        properties = []
        for p_prediction, quantity, (_, context_wo_enclosing, context_char_offset) in zip(property_predictions, quantities, property_contexts):
            properties.append(self._postprocess_prediction(
                p_prediction, quantity, context_wo_enclosing, context_char_offset, text, semantic_boundaries
            ))
        
        return properties, property_contexts, property_inputs
   
    
    def extract_entities(self, quantities, properties, property_contexts, text, semantic_boundaries, device_rank):
        # Create prompts for entity extraction.
        entity_inputs = []
        entity_contexts = []        
        question_template_filling_information = []
        for quantity, property, (context_w_quantity_enclosing, context_wo_enclosing, context_char_offset) in zip(quantities, properties, property_contexts):
                    
            # Fill in question template.
            if property is None or len(property["text"]) == 0:
                # Adapt questions to quantity.
                property_in_question, is_or_are = None, None
                entity_question = self.questions["entity_question_fallback"].format(quantity_span=quantity["text"])
            else:
                # Adapt questions to property and quantity.
                property_in_question = lower_first_letter_if_sent_start(property, text)
                is_or_are = "are" if is_plural(property_in_question) else "is"
                entity_question = self.questions["entity_question"].format(quantity_span=quantity["text"], property_span=property_in_question, is_or_are=is_or_are)            
            
            question_template_filling_information.append((property_in_question, is_or_are))

            entity_input, context_w_quantity_and_property_enclosing, context_wo_enclosing, context_char_offset = self._get_entity_input(entity_question, quantity, property, context_wo_enclosing, context_w_quantity_enclosing, context_char_offset, semantic_boundaries)
            entity_inputs.append(entity_input)
            entity_contexts.append((context_w_quantity_and_property_enclosing, context_wo_enclosing, context_char_offset))

        if self.debug:
            # Make sure that the chunks are not too long.
            for chunk in entity_inputs:
                if self.token_counter(chunk) > self.chunk_size:
                    msg.warn(f"Chunk in entity extraction is too long ({len(chunk)} > {self.chunk_size}): {chunk}")
                    print(entity_inputs)

        # Do entity extraction.
        entity_predictions = self.measurement_context_pipelines[device_rank](entity_inputs)
                
        # Post-process entity predictions.
        entities = []
        for e_prediction, quantity, (_, context_wo_enclosing, context_char_offset) in zip(entity_predictions, quantities, entity_contexts):
            entities.append(self._postprocess_prediction(
                e_prediction, quantity, context_wo_enclosing, context_char_offset, text, semantic_boundaries
            ))

        return entities, entity_contexts, entity_inputs, question_template_filling_information
    

    def extract_qualifiers(self, quantities, properties, entities, entity_contexts, question_template_filling_information, text, semantic_boundaries, device_rank):
        qualifier_inputs = []
        qualifier_contexts = []
        skip_qualifier_extraction_indices = []
        for i, (quantity, property, entity, (property_in_question, is_or_are), (context_w_quantity_and_property_enclosing, context_wo_enclosing, context_char_offset)) in enumerate(zip(quantities, properties, entities, question_template_filling_information, entity_contexts)):
            
            if entity is not None and len(entity["text"]) > 0:
                # Adapt questions to entity.             
                entity_in_question = self.perfix_the(lower_first_letter_if_sent_start(entity, text))
                if property is None or len(property["text"]) == 0:
                    # Use entity span in fallback question.
                    is_or_are = "are" if is_plural(entity_in_question) else "is"
                    entity_or_property_in_question = entity_in_question
                else:
                    # Do not use fallback question.
                    entity_or_property_in_question = None
                    property_in_question = self.perfix_the(property_in_question)

            elif property is not None and len(property["text"]) > 0:
                # Use property span in fallback question.
                entity_or_property_in_question = self.perfix_the(property_in_question)
            else:
                # We do not extract qualifiers if neither a property nor an entity was found.
                skip_qualifier_extraction_indices.append(i)                
                continue
            
            # Fill in question template.
            qualifier_questions = {}
            if entity_or_property_in_question is not None:
                # Use fallback question.
                for q_key in self.qualifier_question_keys:
                    qualifier_questions[q_key] = self.questions[q_key + "_fallback"].format(quantity_span=quantity["text"], entity_or_property_span=entity_or_property_in_question, is_or_are=is_or_are)
                longest_qualifier_question_key = self.longest_qualifier_fallback_question_key
            else:                
                for q_key in self.qualifier_question_keys:
                    qualifier_questions[q_key] = self.questions[q_key].format(quantity_span=quantity["text"], property_span=property_in_question, entity_span=entity_in_question, is_or_are=is_or_are)
                longest_qualifier_question_key = self.longest_qualifier_question_key

            qualifier_input, context_w_quantity_and_property_and_entity_enclosing, context_wo_enclosing, context_char_offset = self._get_qualifier_input(qualifier_questions, longest_qualifier_question_key, quantity, property, entity, context_wo_enclosing, context_w_quantity_and_property_enclosing, context_char_offset, semantic_boundaries)
            qualifier_inputs.append(qualifier_input)
            qualifier_contexts.append((context_w_quantity_and_property_and_entity_enclosing, context_wo_enclosing, context_char_offset))

        # Do qualifier extraction.        
        qualifier_inputs_per_key = {q_key: [q_inputs[q_key] for q_inputs in qualifier_inputs] for q_key in self.qualifier_question_keys}

        if self.debug:
            # Make sure that the chunks are not too long.
            for chunks in qualifier_inputs_per_key.values():
                for chunk in chunks:
                    if self.token_counter(chunk) > self.chunk_size:
                        raise print(f"Chunk in qualifier extraction is too long: {len(chunk)} > {self.chunk_size}. Assuming tokenizer for qualifier extraction is the same as for property and entity extraction.")
        
        # Perform qualifier extraction in parallel.
        approach = 2
        max_parallel_qualifier_workers = len(self.qualifier_pipelines[device_rank])
        if approach == 1:
            # Approach 1: One process per question type.
            if self.verbose:
                msg.info(f"Extracting qualifiers in parallel with {min(max_parallel_qualifier_workers, len(qualifier_inputs_per_key))} workers...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_qualifier_workers) as executor_qlf:
                qualifier_predictions = {}
                for i, (q_key, qualifier_input_batch_per_key) in enumerate(qualifier_inputs_per_key.items()):
                    qualifier_predictions[q_key] = executor_qlf.submit(self.qualifier_pipelines[device_rank][i % max_parallel_qualifier_workers], qualifier_input_batch_per_key)
                
                # Ensure all tasks are completed
                concurrent.futures.wait(qualifier_predictions.values())
        
            # Get results.
            qualifier_predictions = {q_key: q_pred.result() for q_key, q_pred in qualifier_predictions.items()}
            
            # Transform back to per quantity and not per question.            
            qualifier_predictions_per_quantity = [[q_preds[i] for q_preds in qualifier_predictions.values()] for i in range(len(quantities))]

        elif approach == 2:
            # Approach 2: One process per batch.
            flattened_qualifier_inputs = []
            [flattened_qualifier_inputs.extend(q_inputs.values()) for q_inputs in qualifier_inputs]
            
            if self.verbose:
                msg.info("Total number of qualifier inputs:", len(flattened_qualifier_inputs))

            batched_flattened_qualifier_inputs = get_batches_of_roughly_equal_size(flattened_qualifier_inputs, self.qualifier_extraction_batch_size)
            
            if self.verbose:
                msg.info(f"Extracting qualifiers in {len(batched_flattened_qualifier_inputs)} batches in parallel with {max_parallel_qualifier_workers} workers with batch size of {self.qualifier_extraction_batch_size}...")

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_qualifier_workers) as executor_qlf:
                qualifier_predictions = []
                for i, qlf_input_batch in enumerate(batched_flattened_qualifier_inputs):
                    if self.verbose:
                        msg.info("Submitting qualifier batch", i)
                    qualifier_predictions.append(executor_qlf.submit(self.qualifier_pipelines[device_rank][i % max_parallel_qualifier_workers], qlf_input_batch))
                
                # Ensure all tasks are completed
                concurrent.futures.wait(qualifier_predictions)
        
            # Get results and chain lists of qualifier predictions together.
            qualifier_predictions = [q_pred.result() for q_pred in qualifier_predictions]
            qualifier_predictions = list(itertools.chain(*qualifier_predictions))

            # Batch qualifier predictions per quantity.
            nbr_qualifier_questions = len(self.qualifier_question_keys)
            qualifier_predictions_per_quantity = [qualifier_predictions[i:i+nbr_qualifier_questions] for i in range(0, len(qualifier_predictions), nbr_qualifier_questions)]
                        
        # Add empty predictions for skipped quantities.
        for i in skip_qualifier_extraction_indices:
            qualifier_predictions_per_quantity.insert(i, [{'generated_text': ''}]*len(self.qualifier_question_keys))
            qualifier_contexts.insert(i, (None, None, None))
        
        assert len(qualifier_predictions_per_quantity) == len(quantities) == len(qualifier_contexts)

        # Post-process qualifier predictions.
        qualifiers = []                
        for q_predictions, quantity, (_, context_wo_enclosing, context_char_offset) in zip(qualifier_predictions_per_quantity, quantities, qualifier_contexts):
            qualifiers_per_quantity = {}
            # for q_key, q_prediction in q_predictions.items():
            for q_key, q_prediction in zip(self.qualifier_question_keys, q_predictions):            
                # Post-process qualifier predictions.
                qualifiers_per_quantity[q_key] = self._postprocess_prediction(
                    q_prediction, quantity, context_wo_enclosing, context_char_offset, text, semantic_boundaries
                )

            qualifiers.append(qualifiers_per_quantity)

        return qualifiers, qualifier_inputs
    

    def _get_property_input(self, question, quantity, text, semantic_boundaries, add_distant_context=False):
        """Get input for property extraction. Attempts to get largest and most meaningful 
        chunk of context that still fits into the model.
        """
        
        prefix = f"question: {question} context: "
        prefix_token_count = self.token_counter(prefix)

        if add_distant_context:
            # Used for an experiment to see if distant context helps. Change to True to use it and adapt the text.
            distant_context = "This study investigates the role of liquid hydrogen (LH2) in a national, greenhouse gas-neutral energy supply system for Germany in 2045 using the integrated energy system model suite ETHOS [...] "
            distant_context_token_count = self.token_counter(distant_context)
        else:
            distant_context = ""
            distant_context_token_count = 0

        # Enclose quantity in special symbols.    
        context, _ = enclose_with_special_symbol(
            text,
            (quantity["start"], quantity["end"]),
            start_symbol=self.quantity_enclosing[0],
            end_symbol=self.quantity_enclosing[1],        
        )    
        remaining_token_count = self.chunk_size-prefix_token_count - distant_context_token_count

        # TODO: Cache get_single_centered_chunk for speedup.
        centering_span = (quantity["start"], quantity["end"]+len(self.quantity_enclosing[0])+len(self.quantity_enclosing[1]))
        (context_char_offset, _), context = semchunk.get_single_centered_chunk(context, centering_char_offsets=centering_span, chunk_size=remaining_token_count, token_counter=self.token_counter, semantic_boundaries=semantic_boundaries, offsets=True)

        llm_input = prefix + distant_context + context 

        context_wo_enclosing = text[context_char_offset:context_char_offset+len(context)-len(self.quantity_enclosing[0])-len(self.quantity_enclosing[1])]
        
        return llm_input, context, context_wo_enclosing, context_char_offset


    def _get_entity_input(self, entity_question, quantity, property, context_wo_enclosing, context_w_quantity_enclosing, context_char_offset, semantic_boundaries, add_distant_context=False):
        """Get input for entity extraction. Attempts to get largest and most meaningful 
        chunk of context that still fits into the model.
        """                    
            
        if property is None or property["is_implicit"]:
            # We do not have an (explicit) property annotation. Use the old context.
            context = context_w_quantity_enclosing
            
            # Get centering offsets for the context.
            total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1])
            centering_char_offsets = (quantity["start"], quantity["end"]+total_symbol_len)
        else:
            # Adapt annotation according to previously inserted special symbols.
            symbol_offset = adapt_offsets_to_special_symbol_enclosings((property["start"], property["end"]), [(quantity["start"], quantity["end"])], [self.quantity_enclosing])
             
            property_offsets_in_highlighted_context = (
                property["start"]+symbol_offset[0]-context_char_offset, 
                property["end"]+symbol_offset[1]-context_char_offset
            )

            # Get centering offsets for the context.
            total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1]) + len(self.property_enclosing[0]) + len(self.property_enclosing[1])
            centering_char_offsets = (
                min(property["start"], quantity["start"]), 
                max(property["end"], quantity["end"]) + total_symbol_len
            )
            
            # Enclose property in special symbols.
            context, _ = enclose_with_special_symbol(
                context_w_quantity_enclosing,
                property_offsets_in_highlighted_context,
                start_symbol=self.property_enclosing[0],
                end_symbol=self.property_enclosing[1],
            )

        prefix = f"question: {entity_question} context: "
        prefix_token_count = self.token_counter(prefix)

        if add_distant_context:
            # Used for an experiment to see if distant context helps. Change to True to use it and adapt the text.
            distant_context = "This study investigates the role of liquid hydrogen (LH2) in a national, greenhouse gas-neutral energy supply system for Germany in 2045 using the integrated energy system model suite ETHOS [...] "
            distant_context_token_count = self.token_counter(distant_context)
        else:
            distant_context = ""
            distant_context_token_count = 0

        if prefix_token_count + distant_context_token_count + self.token_counter(context) <= self.chunk_size:
            # Skip. New input fits into the model. Do not chunk the context again.
            pass
        else:
            # Chunk context to fit into the model.
            remaining_token_count = self.chunk_size-prefix_token_count-distant_context_token_count

            # Adapt semantic boundaries to the text character offset and the length of the context.            
            semantic_boundaries_ = semchunk.adapt_semantic_boundaries(semantic_boundaries, context_char_offset, len(context), added_chars_len=total_symbol_len, added_chars_end_pos=centering_char_offsets[1])
            
            (new_context_char_offset, _), context = semchunk.get_single_centered_chunk(context, centering_char_offsets=centering_char_offsets, chunk_size=remaining_token_count, semantic_boundaries=semantic_boundaries_,token_counter=self.token_counter, offsets=True)
            context_char_offset += new_context_char_offset
            context_wo_enclosing = context_wo_enclosing[new_context_char_offset:new_context_char_offset+len(context)-total_symbol_len]

        llm_input = prefix + distant_context + context

        if self.debug and self.token_counter(llm_input) > self.chunk_size:
            raise ValueError("Warning: The input for the entity extraction is too long.")

        return llm_input, context, context_wo_enclosing, context_char_offset


    def _get_qualifier_input(self, qualifier_questions, longest_qualifier_question_key, quantity, property, entity, context_wo_enclosing, context_w_quantity_and_property_enclosing, context_char_offset, semantic_boundaries, add_distant_context=False, distant_context="This study investigates..."):
        """Get input for qualifier extraction. Attempts to get largest and most meaningful 
        chunk of context that still fits into the model.
        """
        
        if entity is None or entity["is_implicit"]:
            # We do not have an (explicit) entity annotation. Use the old context.
            context = context_w_quantity_and_property_enclosing
            
            # Get centering offsets for the context.
            if property is None or property["is_implicit"]:
                # Only the quantity is highlighted.
                total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1])
                centering_char_offsets = (quantity["start"], quantity["end"]+total_symbol_len)
            else:
                # Only the property and quantity are highlighted.
                total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1]) + len(self.property_enclosing[0]) + len(self.property_enclosing[1])
                centering_char_offsets = (
                    min(property["start"], quantity["start"]), 
                    max(property["end"], quantity["end"]) + total_symbol_len
                )
        else:
            # Get centering offsets for the context.
            if property is None or property["is_implicit"]:
                # Only the entity and quantity are highlighted.
                total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1]) + len(self.entity_enclosing[0]) + len(self.entity_enclosing[1])
                centering_char_offsets = (
                    min(entity["start"], quantity["start"]), 
                    max(entity["end"], quantity["end"]) + total_symbol_len
                )
                previous_annotations = [(quantity["start"], quantity["end"])]
            else:
                # Entity, property, and quantity are highlighted.
                total_symbol_len = len(self.quantity_enclosing[0]) + len(self.quantity_enclosing[1]) + len(self.property_enclosing[0]) + len(self.property_enclosing[1]) + len(self.entity_enclosing[0]) + len(self.entity_enclosing[1])
                centering_char_offsets = (
                    min(entity["start"], property["start"], quantity["start"]), 
                    max(entity["end"], property["end"], quantity["end"]) + total_symbol_len
                )
                previous_annotations = [(quantity["start"], quantity["end"]), (property["start"], property["end"])]

            symbol_offset = adapt_offsets_to_special_symbol_enclosings((entity["start"], entity["end"]), previous_annotations, [self.quantity_enclosing, self.property_enclosing])

            entity_offsets_in_highlighted_context = (
                entity["start"]+symbol_offset[0]-context_char_offset, 
                entity["end"]+symbol_offset[1]-context_char_offset
            )

            # Enclose entity in special symbols.
            context, _ = enclose_with_special_symbol(
                context_w_quantity_and_property_enclosing,
                entity_offsets_in_highlighted_context,
                start_symbol=self.entity_enclosing[0],
                end_symbol=self.entity_enclosing[1],
            )
    
        prefix = "question: {question} context: "
        longest_prefix = prefix.format(question=qualifier_questions[longest_qualifier_question_key])
        max_prefix_token_count = self.token_counter(longest_prefix)

        if add_distant_context:
            # Used for an experiment to see if distant context helps. Change to True to use it and adapt the text.
            distant_context_token_count = self.token_counter(distant_context)
        else:
            distant_context = ""
            distant_context_token_count = 0

        if max_prefix_token_count + distant_context_token_count + self.token_counter(context) <= self.chunk_size:
            # Skip. New input fits into the model. Do not chunk the context again.
            pass
        else:
            # Chunk context to fit into the model based on the longest qualifier question.
            remaining_token_count = self.chunk_size-max_prefix_token_count-distant_context_token_count

            # Adapt semantic boundaries to the text character offset and the length of the context.
            semantic_boundaries = semchunk.adapt_semantic_boundaries(semantic_boundaries, context_char_offset, len(context), added_chars_len=total_symbol_len, added_chars_end_pos=centering_char_offsets[1])
            
            (new_context_char_offset, _), context = semchunk.get_single_centered_chunk(context, centering_char_offsets=centering_char_offsets, chunk_size=remaining_token_count, semantic_boundaries=semantic_boundaries,token_counter=self.token_counter, offsets=True)
            context_char_offset += new_context_char_offset
            context_wo_enclosing = context_wo_enclosing[new_context_char_offset:new_context_char_offset+len(context)-total_symbol_len]
        
        llm_inputs = {}
        for q_key, question in qualifier_questions.items():
            llm_input = prefix.format(question=question) + distant_context + context            
            llm_inputs[q_key] = llm_input
            if self.token_counter(llm_input) > self.chunk_size:
                print("Warning: The input for the entity extraction is too long.")
        
        return llm_inputs, context, context_wo_enclosing, context_char_offset


    def _pack_predictions_into_output_format(self, quantities, properties, entities, qualifiers, property_inputs, entity_inputs, qualifier_inputs, add_curation_fields=False, return_llm_inputs=False):
        """
        Pack model predictions into the output format of quantitative statements.
        """

        def _format_pred(pred, empty_annotation: dict={"start": 0, "end": 0, "text": "", "is_implicit": None}):
            if pred == None and self.empty_dict_for_empty_prediction:
                # Add empty annotation.
                pred = empty_annotation

            if add_curation_fields and pred != None:
                # Add empty curation list.
                pred["curation"] = []
            
            return pred
        
        quantitative_statements = []
        for i, (q, p, e, qlf) in enumerate(zip(quantities, properties, entities, qualifiers)):
            
            # Create quantitative statement representation.
            quantitative_statement = {
                "claim": {
                    "entity": _format_pred(e),
                    "property": _format_pred(p),
                    "quantity": q,
                },
                "qualifiers": {qlf_key.removesuffix("_question"): _format_pred(qlf)for qlf_key, qlf in qlf.items()},
            }

            # Optionally, add model inputs for debugging.
            if return_llm_inputs:                
                llm_inputs = {"property_inputs": property_inputs[i], "entity_inputs": entity_inputs[i], "qualifier_inputs": qualifier_inputs[i]}
                quantitative_statement.update({"llm_inputs": llm_inputs})

            quantitative_statements.append(quantitative_statement)
        
        return quantitative_statements