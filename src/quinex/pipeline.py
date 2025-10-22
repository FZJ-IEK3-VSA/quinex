
from time import time
import concurrent.futures
from queue import Queue
import pandas as pd
import torch
import spacy
import semchunk
from text_processing_utils.batches import get_batches_of_roughly_equal_size
from quinex import __version__, msg
from quinex.extract.subtasks.quantity_span_identification import QuantitySpanIdentification
from quinex.extract.subtasks.measurement_context_extraction import MeasurementContextExtraction
from quinex.extract.subtasks.statement_type_classification import StatementTypeClassification


class Quinex:
    def __init__(
        self,        
        # Models        
        quantity_model_name: str="JuelichSystemsAnalysis/quinex-quantity-v0-124M",
        context_model_name: str="JuelichSystemsAnalysis/quinex-context-v0-783M",
        statement_clf_model_name: str="JuelichSystemsAnalysis/quinex-statement-clf-v0-125M",
        spacy_model_name: str="en_core_web_md",
        # Tasks
        enable_quantity_extraction: bool=True,
        enable_context_extraction: bool=True,
        enable_qualifier_extraction: bool=True,
        enable_statement_classification: bool=False, # TODO: Default to True when statement classification is more accurate.
        # Output        
        empty_dict_for_empty_prediction: bool=False,        
        # Settings        
        max_new_tokens: int=50, # Maximum number of new tokens to generate for context extraction.
        sentence_by_sentence: bool=False, # Whether to process texts sentence by sentence instead of using larger chunks.
        # Devices
        use_cpu: bool=True, # If True, use CPU for all models and ignore parallel_worker_device_map.
        parallel_worker_device_map: dict={
            'quantity_model': {'n_workers': 1, 'gpu_device_ranks': [0], 'batch_size': 256}, 
            'context_model': {'n_workers': 3, 'gpu_device_ranks': [0], 'batch_size': 64}, 
            'qualifier_model': {'n_workers': 3, 'gpu_device_ranks': [0], 'batch_size': 64}, 
            'statement_clf_model': {'n_workers': 1, 'gpu_device_ranks': [0], 'batch_size': 64}
        },
        # Verbosity
        verbose: bool=False,
        debug: bool=False,
    ):        
        
        start = time()
        
        print("")
        msg.text("Initializing quinex...", color="blue")
        
        self.predictions = []
        self.verbose = verbose
        self.debug = debug
        self.use_cpu = use_cpu
        use_fp16 = False        
        dtype = torch.bfloat16 if use_fp16 else "auto"        
        self.sentence_by_sentence = sentence_by_sentence
        self.empty_dict_for_empty_prediction = empty_dict_for_empty_prediction
        
        # Tasks to perform.
        self.enable_quantity_extraction = enable_quantity_extraction
        self.enable_context_extraction = enable_context_extraction
        self.enable_qualifier_extraction = enable_qualifier_extraction
        self.enable_statement_classification = enable_statement_classification

        # Get device info for parallel processing.
        self.parallel_devices, self.nbr_parallel_workers, self.batch_sizes = self._get_device_info(parallel_worker_device_map, use_cpu)
        
        # Load spaCy NLP pipeline. Only "tok2vec" and "parser" are required for sentence boundary detection.
        spacy_exclude_comps = ["entity_linker", "entity_ruler", "textcat", "textcat_multilabel", "lemmatizer", 
            "trainable_lemmatizer", "morphologizer", "attribute_ruler", "senter", "sentencizer", "ner", 
            "transformers", "tagger"]
        self.nlp = spacy.load(spacy_model_name, exclude=spacy_exclude_comps)
        
        # Load quantity extraction pipeline.
        if self.enable_quantity_extraction:
            self.quantity_identifier = QuantitySpanIdentification(
                quantity_model_name,
                spacy_pipeline=self.nlp, 
                devices=self.parallel_devices["quantity_model"], 
                batch_size=self.batch_sizes["quantity_model"], 
                dtype=dtype, 
                verbose=verbose, 
                debug=debug
            )
            if self.verbose:
                msg.good(f"Quantity span identification model loaded!")
        else:
            self.quantity_identifier = None
        
        # Load context extraction pipeline.
        if self.enable_context_extraction:            
            self.measurement_context_extractor = MeasurementContextExtraction(
                context_model_name, 
                devices=self.parallel_devices["context_model"], 
                batch_size=self.batch_sizes["context_model"], 
                max_new_tokens=max_new_tokens, 
                enable_qualifier_extraction=self.enable_qualifier_extraction, 
                empty_dict_for_empty_prediction=self.empty_dict_for_empty_prediction,
                dtype=dtype, 
                verbose=verbose, 
                debug=debug
            )
            if self.verbose:
                msg.good(f"Measurement context extraction model loaded!")
        else:
            self.measurement_context_extractor = None

        # Load statement classifcation model
        if self.enable_statement_classification:            
            self.statement_type_classifier = StatementTypeClassification(statement_clf_model_name, devices=self.parallel_devices["statement_clf_model"], batch_size=self.batch_sizes["statement_clf_model"], dtype=dtype, verbose=verbose, debug=debug)
            if self.verbose:
                msg.good(f"Statement classification model loaded!")
        else:
            self.statement_type_classifier = None        
        
        print(f"""
             .-----------------------.
            |   ___________________   |
            |  |   ,,,       ,,,   |  |
            |  |  ( ● )     ( ● )  |  |
            |  |   ```       ```   |  |
            |  |     `--___--´     |  |
            |  |___________________|  |
            |                         |
            | .---. .---. .---. .---. |
            | | 7 | | 8 | | 9 | | ÷ | |
            | '---' '---' '---' '---' |
            | .---. .---. .---. .---. |
            | | 4 | | 5 | | 6 | | x | |
            | '---' '---' '---' '---' |
            | .---. .---. .---. .---. |
            | | 1 | | 2 | | 3 | | - | |
            | '---' '---' '---' '---' |
            | .---. .---. .---. .---. |
            | | = | | 0 | | . | | + | |
            | '---' '---' '---' '---' |
             '-----------------------'                
                Q U I N E X v{__version__}
        """)
        msg.good(f"Pipeline initialized in {round(time()-start, 3)} s.")
        if self.use_cpu:
            msg.text("Note that using CPUs instead of GPUs (use_cpu=False) is significantly slower.", color="grey")
            

    def print_gpu_memory_usage(self):
        if self.use_cpu:
            msg.warn("GPU memory usage not available if models are run on CPU.")
        else:        
            msg.info("Memory usage per GPU:")
            for model_key in self.parallel_devices.keys():
                print(f"Model: {model_key}")
                for device in self.parallel_devices[model_key]:
                    print("Device:", device)
                    # TODO: Set device                    
                    print(torch.cuda.memory_summary(device=None, abbreviated=True))


    def preprocess(self, text):
        # TODO: Enable using lists of texts?

        print("")
        msg.text("📄 Applying pipeline to given text...", color="blue")

        # Create spaCy Doc used to determine sentence boundaries.
        doc = self.nlp(text)
        if self.verbose:                 
            print("Number of chars:", len(text))
            print("Number of words:", len(doc))

        # For quantity extraction, we split the text into 
        # meaningful chunks that fit into the quantity model.        
        chunk_at = ["paragraphs", "sentences", "subparts", "tokens"]
        if self.sentence_by_sentence:            
            chunk_at.remove("paragraphs")

        semantic_boundaries = semchunk.get_semantic_bounderies(doc, ordered_semantic_chunk_types=chunk_at)

        return doc, semantic_boundaries


    def get_quantities(self, text: str, skip_imprecise_quantities: bool=False, add_curation_fields: bool=False):
        if type(text) != str:
            raise ValueError("text must be of type str.")
        elif len(text) == 0:
            return []
        else:
            
            start = time()
            
            # Prepare text.
            doc, semantic_boundaries = self.preprocess(text)

            # Get chunks.        
            q_chunks = semchunk.chunk(text, chunk_size=self.quantity_identifier.chunk_size, token_counter=self.quantity_identifier.token_counter, semantic_boundaries=semantic_boundaries, non_destructive=True, offsets=True)

            # Get batches of chunks.        
            q_batches = get_batches_of_roughly_equal_size(q_chunks, self.batch_sizes["quantity_model"])
            quantities = []
            for q_batch in q_batches:
                quantities.extend(self.quantity_identifier(q_batch, 0, doc, skip_imprecise_quantities=skip_imprecise_quantities, filter=False, post_process=True, add_curation_fields=add_curation_fields))
            
            msg.good(f"Identified {len(quantities)} quantities in {round(time()-start, 3)} s.")
            return quantities
        

    def simple_call(self, text: str, skip_imprecise_quantities: bool=False, return_llm_inputs: bool=False, add_curation_fields: bool=False):
        """
        Apply the pipeline to the given text without using parallel processing or concurrency
        and without performing statement classification.
        """
        if type(text) != str:
            raise ValueError("text must be of type str.")
        elif len(text) == 0:
            return []
        else:
            # Prepare text.
            doc, semantic_boundaries = self.preprocess(text)
            
            # Get quantities.            
            q_chunks = semchunk.chunk(text, chunk_size=self.quantity_identifier.chunk_size, token_counter=self.quantity_identifier.token_counter, semantic_boundaries=semantic_boundaries, non_destructive=True, offsets=True)
            q_batches = get_batches_of_roughly_equal_size(q_chunks, self.batch_sizes["quantity_model"])
            quantities = []
            for i, q_batch in enumerate(q_batches):
                quantities.extend(self.quantity_identifier(q_batch, i % self.nbr_parallel_workers["quantity_model"], doc, skip_imprecise_quantities=skip_imprecise_quantities, filter=False, post_process=True, add_curation_fields=add_curation_fields))

            # Get measurement context.
            c_batches = get_batches_of_roughly_equal_size(quantities, self.batch_sizes["context_model"])            
            qclaims = []
            for i, c_batch in enumerate(c_batches):
                qclaims.extend(self.measurement_context_extractor(c_batch, i % self.nbr_parallel_workers["context_model"], text, semantic_boundaries, return_llm_inputs=return_llm_inputs, add_curation_fields=add_curation_fields))

            return qclaims


    def get_claim_for_given_quantity(self, text, quantity, return_llm_inputs: bool=False, add_curation_fields: bool=False):
        """
        Extract the measurement context and classify the quantitative statement for a given quantity.        
        This is useful if the quantity span is already known and we want to extract the measurement context for it.
        """

        if self.measurement_context_extractor is None:
            raise ValueError("Context extraction must be enabled to use this function.")
        
        # Prepare text.
        doc, semantic_boundaries = self.preprocess(text)                
        
        if 'normalized' in quantity:
            # Quantity is already normalized.
            quantity_spans = [quantity]
        else:
            # Quantity is not yet normalized. Do so.
            # TODO: Use already created doc and not create doc from text again.
            # To do so, add tokenizer changes of qmod_extractor spaCy pipeline to quinex main spaCy pipeline.
            _, quantity_spans = self.quantity_identifier.qmod_extractor(doc.text, [quantity])
            quantity_spans = self.quantity_identifier._parse_and_normalize_quantity_spans(quantity_spans, text, add_curation_fields=False, summarized_output=False)                

        # Perform context extraction and statement classification.
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.nbr_parallel_workers["context_model"]) as executor_b, \
            concurrent.futures.ThreadPoolExecutor(max_workers=self.nbr_parallel_workers["statement_clf_model"]) as executor_c:            
            context_future = executor_b.submit(self.measurement_context_extractor, quantity_spans, 0, text, semantic_boundaries, return_llm_inputs=return_llm_inputs, add_curation_fields=add_curation_fields)
            if self.enable_statement_classification:
                classification_future = executor_c.submit(self.statement_type_classifier, quantity_spans, 0, text, semantic_boundaries, add_curation_fields=add_curation_fields)
        
        # Ensure all tasks are completed.
        concurrent.futures.wait([context_future])
        if self.enable_statement_classification:
            concurrent.futures.wait([classification_future])

        # Get measurement context result.
        quantitative_statements = context_future.result()
        
        # Output is a single quantitative statement.
        assert len(quantitative_statements) == 1
        quantitative_statement = quantitative_statements[0]

        # Add statement classification results.
        if self.enable_statement_classification:
            classification = classification_future.result()
            classification = list(classification.values())
            assert len(classification) == 1        
            quantitative_statement["statement_classification"] = classification[0]

        return quantitative_statement
    

    def __call__(self, text, skip_imprecise_quantities: bool=False, add_curation_fields: bool=False, return_llm_inputs: bool=False):
        """
        Apply pipeline to the given text.

        Args:
            text (str): Input text.
            skip_imprecise_quantities (bool): Whether to skip imprecise quantities (e.g., "several trees")
            add_curation_fields (bool): Whether to add curation fields to the output (for annotation purposes).
            return_llm_inputs (bool): Whether to return the model inputs used for context extraction (for debugging purposes).
            
        Returns:
            list: List of extracted quantitative statements.

                    
        The pipeline consists of the following steps which can be enabled/disabled individually.
        Context extraction and statement classification start as soon as enough quantities 
        are identified to fill a batch and run in parallel.

                  ----------------------------
                              Text                      
                  ----------------------------
                               |
                               V 
               1. Quantity span identification
                    |                      | 
                    V                      |
             2.1. Property                 |
                  extraction               |
                    |                      |
                    V                      V                 
             2.2. Entity            3. Statement 
                  extraction           classification
                    |                      |
                    V                      |
             2.3. Qualifier                |
                  extraction               |
                    |                      |               
                    |                      |
                  --V----------------------V--
                            Results          
                  ----------------------------

        """

        start_time = time()
        
        if self.batch_sizes["context_model"] != self.batch_sizes["statement_clf_model"]:
            msg.warn("The batch sizes for context extraction and statement classification are not equal. However, they are assumed to be equal. This may lead to suboptimal performance.")
        elif type(text) != str:
            raise ValueError("text must be a string.")
        elif len(text) == 0:
            return []
        elif not self.enable_quantity_extraction:
            raise ValueError("Quantity spand identfication must be enabled to perform measurement context extraction and/or statement classification.")
        
        # Prepare text.
        doc, semantic_boundaries = self.preprocess(text)

        # Get chunks.        
        q_chunks = semchunk.chunk(text, chunk_size=self.quantity_identifier.chunk_size, token_counter=self.quantity_identifier.token_counter, semantic_boundaries=semantic_boundaries, non_destructive=True, offsets=True)

        # Get batches of chunks.        
        q_batches = get_batches_of_roughly_equal_size(q_chunks, self.batch_sizes["quantity_model"])
        
        if self.verbose:
            print(f"Split text into {len(q_batches)} batches for quantity span identification.")

        preproc_time = time() - start_time
        msg.text(f"Pre-processing done in {round(preproc_time, 3)} s.", color="grey")
        
        context_extraction_results = []
        classification_results = []
        quantities_queue = Queue()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.nbr_parallel_workers["quantity_model"]) as executor_a, \
            concurrent.futures.ThreadPoolExecutor(max_workers=self.nbr_parallel_workers["context_model"]) as executor_b, \
            concurrent.futures.ThreadPoolExecutor(max_workers=self.nbr_parallel_workers["statement_clf_model"]) as executor_c:

            if self.verbose:
                print(f"Set up parallel workers for quantity span identification, context extraction, and statement classification in {round(time()-start_time-preproc_time, 3)} s.")
            
            # Perform quantity span identification on batches on one or multiple devices in parallel.
            quantity_futures = {executor_a.submit(self.quantity_identifier, q_batch, i % self.nbr_parallel_workers["quantity_model"], doc, skip_imprecise_quantities=skip_imprecise_quantities, filter=False, post_process=True, add_curation_fields=add_curation_fields) for i, q_batch in enumerate(q_batches)}

            quantity_span_identification_completed = False
            while quantity_futures:
                
                # Collect completed tasks.
                done, _ = concurrent.futures.wait(quantity_futures, return_when=concurrent.futures.FIRST_COMPLETED)
                
                i = 0
                for future in done:
                    
                    # Remove batch of found quantitites from set.
                    quantity_futures -= {future}
                    
                    # Put quantities in queue.
                    for q in future.result():
                        quantities_queue.put(q)

                    if len(quantity_futures) == 0:
                        quantity_span_identification_completed = True
                        got_quantities_time = time() - start_time - preproc_time
                        msg.text(f"Identified {quantities_queue.qsize()} quantities in {round(got_quantities_time, 3)} s.", color="grey")

                        if not self.enable_context_extraction and not self.enable_statement_classification:                            
                            quantities = [quantities_queue.get() for _ in range(quantities_queue.qsize())]
                            msg.good(f"Done! Found {len(quantities)} quantities in {round(got_quantities_time, 3)} s.")
                            return quantities

                    # Concurrently extract measurement context and classify statements as soon as a batch is ready 
                    # or quantity extraction is done and the last results did not fill a full batch.
                    if quantities_queue.qsize() >= self.batch_sizes["context_model"] or quantity_span_identification_completed:                        
                        while not quantities_queue.empty():
                            
                            # Increment batch counter.
                            i += 1

                            # Get batch of quantities.
                            batch_quantities = [quantities_queue.get() for _ in range(min(self.batch_sizes["context_model"], quantities_queue.qsize()))]
                            
                            if self.enable_context_extraction:
                                # Perform context extraction. 
                                context_future = executor_b.submit(self.measurement_context_extractor, batch_quantities, i % self.nbr_parallel_workers["context_model"], text, semantic_boundaries, return_llm_inputs=return_llm_inputs, add_curation_fields=add_curation_fields)
                                context_extraction_results.append(context_future)
                            
                            if self.enable_statement_classification:
                                # Perform statement classification in parallel.
                                classification_future = executor_c.submit(self.statement_type_classifier, batch_quantities, i % self.nbr_parallel_workers["statement_clf_model"], text, semantic_boundaries, add_curation_fields=add_curation_fields)
                                classification_results.append(classification_future)

        # Ensure all tasks are completed.
        if self.enable_context_extraction:
            concurrent.futures.wait(context_extraction_results)
            processed_context_extraction_results = [future.result() for future in context_extraction_results]
        
        if self.enable_statement_classification:
            concurrent.futures.wait(classification_results)
            processed_classification_results = [future.result() for future in classification_results]

        got_measurement_context_time = time() - start_time - got_quantities_time
        msg.text(f"Context analyzed in {round(got_measurement_context_time, 3)} s.", color="grey")
        
        if self.enable_context_extraction:
            if self.enable_statement_classification:            
                # Since we processed the batches in parallel and the order of results is not guranteed, we need to recombine the results.
                processed_classification_results = [{(qc["quantity"]["start"], qc["quantity"]["end"]): qc["statement_classification"] for qc in batch_c} for batch_c in processed_classification_results]
                for batch_b, batch_c in zip(processed_context_extraction_results, processed_classification_results):
                    for quantitative_statement in batch_b:
                        # Add statement classification results to quantities.            
                        quantitative_statement["statement_classification"] = batch_c.pop((quantitative_statement["claim"]["quantity"]["start"], quantitative_statement["claim"]["quantity"]["end"]))
                    
                    assert len(batch_c) == 0            

            predictions_per_batch = processed_context_extraction_results
            message = "Done! Found {} quantitative statements in {} s."
        else:
            predictions_per_batch = processed_classification_results
            message = "Done! Found and classified {} quantities in {} s."
            
        # Flatten batches of predictions.
        predictions = [item for sublist in predictions_per_batch for item in sublist]

        msg.good(message.format(len(predictions), round(time()-start_time, 1)))
            
        return predictions


    def _get_device_info(self, parallel_worker_device_map, use_cpu):
        if use_cpu:
            # Use CPU without parallelization, assuming CPUs are only used for debugging.
            parallel_devices = {}
            for model_name in parallel_worker_device_map.keys():
                parallel_devices[model_name] = ["cpu"]
        elif not use_cpu and not torch.cuda.is_available():
            raise ValueError("No GPU available. Please set use_cpu=True.")
        else:                        
            print("Using GPUs for processing.")            
            parallel_devices = {}
            for model_name, device_info in parallel_worker_device_map.items():

                # All ranks must be integers.
                if not all(isinstance(rank, int) for rank in device_info["gpu_device_ranks"]):
                    raise ValueError(f'GPU device ranks ({device_info["gpu_device_ranks"]}) for {model_name} must be integers.')
                # Max. rank must be smaller or equal to the number of available GPUs.
                if max(device_info["gpu_device_ranks"]) >= torch.cuda.device_count():
                    raise ValueError(f'GPU device ranks for {model_name} must be smaller than the number of available GPUs.')
                
                # Use GPU.
                devices = [f"cuda:{rank}" for rank in device_info["gpu_device_ranks"]]
                if device_info["n_workers"] == len(devices):
                    pass
                elif device_info["n_workers"] > len(devices):
                    # Copy devices to fill up n_workers.
                    devices = devices * (device_info["n_workers"] // len(devices)) + devices[:device_info["n_workers"] % len(devices)]
                else:
                    raise ValueError(f'Number of workers for {model_name} must be greater or equal to the number of devices.')
                    
                # Distribute num_workers over devices.
                parallel_devices[model_name] = [devices[i] for i in range(device_info["n_workers"])]                

        # Get number of parallel workers for each model.
        nbr_parallel_workers = {}
        for model_name, devices in parallel_devices.items():
            nbr_parallel_workers[model_name] = len(devices)

        if nbr_parallel_workers["qualifier_model"] != nbr_parallel_workers["context_model"]:
            raise ValueError(
                "As the same model is used for qualifier and context extraction, the number of workers" \
                "should be the same. Context and qualifier extraction are performed sequentially," \
                "so there is no reason to not use the availabel parallel workers for both tasks."
            )
        
        # Get batch sizes for each model.
        batch_sizes = {}
        for model_name, device_info in parallel_worker_device_map.items():
            if device_info["batch_size"] < 1:
                raise ValueError(f'Batch size for {model_name} must be greater than 0.')
            else:
                batch_sizes[model_name] = device_info["batch_size"]
        
        return parallel_devices, nbr_parallel_workers, batch_sizes
    
    
    def qclaims_to_df(self, qclaims: list[dict]) -> pd.DataFrame:
        """
        Convert list of quantitative claims to a pandas DataFrame.
        Note that for simplicity not all information is included in the DataFrame.
        """    
        flattened_qclaims = []
        for qclaim in qclaims:

            # Flatten the quantitative claim structure.
            flattened_claim = {                
                'entity': qclaim['claim']['entity']['text'] if qclaim['claim']['entity'] else None,
                'property': qclaim['claim']['property']['text'] if qclaim['claim']['property'] else None,
                'quantity': qclaim['claim']['quantity']['text'],
                'normalized_quantity': qclaim['claim']['quantity']['normalized'],
                'temporal_scope': qclaim['qualifiers']['temporal_scope']['text'] if qclaim['qualifiers']['temporal_scope'] else None,
                'spatial_scope': qclaim['qualifiers']['spatial_scope']['text'] if qclaim['qualifiers']['spatial_scope'] else None,
                'reference':  qclaim['qualifiers']['reference']['text'] if qclaim['qualifiers']['reference'] else None,
                'method': qclaim['qualifiers']['method']['text'] if qclaim['qualifiers']['method'] else None,
                'other_qualifiers': qclaim['qualifiers']['qualifier']['text'] if qclaim['qualifiers']['qualifier'] else None,
            }

            # Add statement classification info if available.
            if 'statement_type' in qclaim:
                flattened_claim.update({
                    'qclaim_type': qclaim['statement_type']['type_class'],
                    'qclaim_rational': qclaim['statement_type']['rational_class'],
                    'qclaim_system': qclaim['statement_type']['system_class'],
                })

            flattened_qclaims.append(flattened_claim)                

        return pd.DataFrame(flattened_qclaims)