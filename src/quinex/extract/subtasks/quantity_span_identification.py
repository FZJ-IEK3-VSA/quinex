import re
from time import time
from spacy import Language

from text_processing_utils.iob_tags import iob_tags_to_spans, remove_overlapping_bio_tags, token_spans_to_char_annotations

from quinex_utils.lookups.number_words import NUMBER_WORDS
from quinex_utils.lookups.imprecise_quantities import IMPRECISE_QUANTITIES
from quinex_utils.lookups.physical_constants import PHYSICAL_CONSTANTS_LOWERED
from quinex_utils.parsers.quantity_parser import FastSymbolicQuantityParser
from quinex_utils.patterns.contains import CONTAINS_DIGIT_REGEX, CONTAINS_NUMBER_WORD_OR_IMPRECISE_QUANTITY_REGEX
from quinex_utils.functions.boolean_checks import contains_any_number, is_relative_quantity
from quinex_utils.functions.extract_quantity_modifiers import GazetteerBasedQuantityModifierExtractor

from quinex import msg
from quinex.extract.utils.transformers import load_transformers_pipe, get_text_chunking_helper




blacklisted_special_chars = [".", ",", ";", ":", "-", "_" "!", "?", "&", "(", "{", "[", "]", "}", ")", "'", '"', "=", "+", "*", "/", "\\", "|", "<", ">", "^", "#", "@", "~", "`"]
ONLY_SPECIAL_CHARS = re.compile(r"^[" + re.escape("".join(blacklisted_special_chars)) + r"]*$")


def add_char_offset(spans, char_offset):
    """Add char offset to all spans."""
    if char_offset == 0:
        pass
    elif char_offset > 0:
        for span in spans:
            span["start"] += char_offset
            span["end"] += char_offset
    else:
        raise ValueError("char_offset must be positive.")
    
    return spans


def merge_likely_wrongly_split_quantity_spans(quantity_spans, text):
    """
    Merge numbers that
        a) end and start on the same character (e.g., '7' and '40.8A˚' are merged to '740.8A˚'), or
        b) are split at a decimal point (e.g., '740' and '8A' are merged to '740.8A').
    """            
    # TODO: This currently assumes that not multiple quantities consecutive quantities are merged.
    remove_idx = []
    for i, (prev, curr) in enumerate(zip(quantity_spans, quantity_spans[1:])):
        is_adjecent = prev["end"] == curr["start"]
        is_split_at_decimal = curr["start"] - prev["end"] == 1 and text[prev["end"]] == "." and prev["text"][-1].isdigit() and curr["text"][0].isdigit() 
        is_split_by_dash = curr["start"] - prev["end"] == 1 and text[prev["end"]] == "-"
        if is_adjecent or is_split_at_decimal or is_split_by_dash:        
            curr["start"] = prev["start"]
            curr["text"] = text[curr["start"] : curr["end"]]
            remove_idx.append(i)
    
    # Remove merged quantity spans.
    for i in reversed(remove_idx):
        quantity_spans.pop(i)

    return quantity_spans


def filter_quantity_spans(quantity_spans):
    """
    Removes quantity spans that do not contain any of the following:
     - a digit
     - a number word
     - a known constant

    """    
    for quantity_span in quantity_spans:
        test_span = quantity_span["text"].lower()
        if CONTAINS_DIGIT_REGEX.match(test_span):
            # Span contains at least one digit.
            pass
        elif CONTAINS_NUMBER_WORD_OR_IMPRECISE_QUANTITY_REGEX.match(test_span):
            # Span contains at least one number word or imprecise quantity.
            pass
        elif test_span in PHYSICAL_CONSTANTS_LOWERED:
            # Span matches a known constant.
            pass
        else:
            # The given span seems not to be a quantity span.
            quantity_spans.remove(quantity_span)
            print(f"Warning: Removed {quantity_span} from quantity spans, because it seems not to be a quantity span.")

    return quantity_spans


def filter_garbage_quantity_spans(quantity_spans):
    """
    Remove quantity spans that only consists of certain special symbols, whitespace or are empty.
    """
    valid_quantity_spans = []
    for q in quantity_spans:
        if ONLY_SPECIAL_CHARS.fullmatch(q["text"]):
            # Span only contains special characters and is unlikely
            # to be a quantity span. Therefore, it is removed.
            continue
        else:
            valid_quantity_spans.append(q)

    return valid_quantity_spans


def postprocess_quantity_span(quantity_span, text):
    """
    Postprocess a single quantity span iteratively until
    no changes are made by
    * removing leading and trailing whitespace, commas, 
      semicolons, parantheses, etc.,
    * closing parantheses if necessary, and
    * adding a % sign if it directly follows the quantity.
    
    Args:
        quantity_span (dict): Quantity span with "start", "end, and "text" fields.
        text (str): Text from which the quantity span was extracted.
    """
    
    SINGLE_CHAR_GARBAGE_AT_END = [",",";", ":", "!", "?", "&", "(", "{", "["] 
    DOUBLE_CHAR_GARBAGE_AT_END = [")."]
    SINGLE_CHAR_GARBAGE_AT_START = ["!", "?", "&", ")", "}", "]"]
    
    prev_iteration = ""                
    while len(quantity_span["text"]) > 0 and prev_iteration != quantity_span["text"]:

        prev_iteration = quantity_span["text"]

        # Remove trailing commas, semicolons, opening parantheses, etc.
        if quantity_span["text"][-1] in SINGLE_CHAR_GARBAGE_AT_END or quantity_span["text"].endswith("%."):
            quantity_span["text"] = quantity_span["text"][:-1]
            quantity_span["end"] -= 1
        elif quantity_span["text"][-2:] in DOUBLE_CHAR_GARBAGE_AT_END:
            quantity_span["text"] = quantity_span["text"][:-2]
            quantity_span["end"] -= 2

        # Remove leading commas, semicolons, opening parantheses, etc.
        if quantity_span["text"][0] in SINGLE_CHAR_GARBAGE_AT_START:
            quantity_span["text"] = quantity_span["text"][1:]
            quantity_span["start"] += 1            
        
        # Remove leading and trailing parantheses.
        if quantity_span["text"].startswith("(") or quantity_span["text"].endswith(")"):
            if quantity_span["text"].startswith("(") and quantity_span["text"].endswith(")"):
                quantity_span["text"] = quantity_span["text"][1:-1]
                quantity_span["start"] += 1
                quantity_span["end"] -= 1        
            elif quantity_span["text"].endswith(")") and quantity_span["text"].count("(") - quantity_span["text"].count(")") > 0:
                # Remove single trailing parantheses.
                quantity_span["text"] = quantity_span["text"][:-1]
                quantity_span["end"] -= 1
            elif quantity_span["text"].startswith("(") and quantity_span["text"].count("(") - quantity_span["text"].count(")") > 0:
                # Remove leading trailing parantheses.
                quantity_span["text"] = quantity_span["text"][1:]
                quantity_span["start"] += 1
            
        # Remove leading and trailing whitespace.        
        quantity_span_a = quantity_span["text"].lstrip()
        leading_whitespace = len(quantity_span["text"]) - len(quantity_span_a)
        quantity_span_b = quantity_span_a.rstrip()
        trailing_whitespace =  len(quantity_span_a) - len(quantity_span_b)
        if leading_whitespace > 0 or trailing_whitespace > 0:
            quantity_span["start"] += leading_whitespace
            quantity_span["end"] -= trailing_whitespace
            quantity_span["text"] = quantity_span_b

        # Add % sign if it directly follows the quantity.
        if len(text) >= quantity_span["end"] + 1 and text[quantity_span["end"]] == "%":
            quantity_span["text"] = quantity_span["text"] + "%"
            quantity_span["end"] += 1
        elif len(text) >= quantity_span["end"] + 2 and text[quantity_span["end"]:quantity_span["end"] + 1] == " %":
            quantity_span["text"] = quantity_span["text"] + " %"
            quantity_span["end"] += 2            
            
        # Close parantheses.
        if len(text) >= quantity_span["end"] + 1 and text[quantity_span["end"]] in [")", "}", "]"]:
            if text[quantity_span["end"]] == ")":
                pars = ["(", ")"]
            elif text[quantity_span["end"]] == "}":
                pars = ["{", "}"]
            elif text[quantity_span["end"]] == "]":
                pars = ["[", "]"]

            if quantity_span["text"].count(pars[0]) - quantity_span["text"].count(pars[1]) > 0:
                quantity_span["text"] = quantity_span["text"] + pars[1]
                quantity_span["end"] += 1

    return quantity_span


def postprocess_quantity_spans(quantity_spans, text):
    pp_quantity_spans = []
    for quantity_span in quantity_spans:
        pp_quantity_spans.append(postprocess_quantity_span(quantity_span, text))

    return quantity_spans


class QuantitySpanIdentification:
    """
    Identify and normalize all quantity spans in a given text.

    Args:
        model_name_or_path (str): Path to the quantity span identification model or its name on HuggingFace.
        spacy_pipeline (spacy.Language): Preloaded spaCy pipeline. If None, a new spaCy pipeline is created.
        devices (list): List of devices to use for processing (e.g., ["cpu"], ["cuda:0", "cuda:1"]).
        batch_size (int): Batch size for processing.
        dtype (str): Data type for model weights. E.g., "auto", "float16", "float32".
        verbose (bool): If True, print verbose messages.
        debug (bool): If True, perform additional checks for debugging.
    """

    def __init__(
            self,
            model_name_or_path: str,
            spacy_pipeline: Language=None,
            devices: list=["cpu"],
            batch_size: int=8,
            dtype: str="auto",
            verbose: bool=False,
            debug: bool=False
        ):

        self.verbose = verbose
        self.debug = debug
        self.token_counter, self.chunk_size = get_text_chunking_helper(model_name_or_path, task="token-classification")

        # Load quantity parser.
        self.quantity_parser = FastSymbolicQuantityParser(verbose=verbose)

        # Load parallel quantity span identification pipelines.
        self.quantity_pipelines = [load_transformers_pipe("token-classification", model_name_or_path, device, batch_size=batch_size, dtype=dtype, verbose=verbose) for device in devices]
        
        # Load spaCy NLP pipeline.
        if spacy_pipeline is None:
            # Init new spaCy pipeline.            
            import spacy
            spacy_exclude_comps = ["entity_linker", "entity_ruler", "textcat", "textcat_multilabel", "lemmatizer", 
            "trainable_lemmatizer", "morphologizer", "attribute_ruler", "senter", "sentencizer", "ner", 
            "transformers", "tagger"]
            self.nlp = spacy.load("en_core_web_md", exclude=spacy_exclude_comps)
        else:
            # Use given spaCy pipeline.
            self.nlp = spacy_pipeline

        # Load quantity modifier extractor.
        self.qmod_extractor = GazetteerBasedQuantityModifierExtractor()


    def __call__(self, batch, device_rank, doc, skip_imprecise_quantities=False, filter=False, soft_filter=True, post_process=True, add_curation_fields=False):
        """
        Identify all quantities in a given chunk of text and normalize them.

        Args:
            batch (list): List of tuples (char_offset, text_chunk), where char_offset is a tuple of
                          start and end char as int (begin, end) indicating the position of the chunk
                          in the original text and text_chunk is the text of the chunk as str.
            device_rank (int): The rank of the device to use for processing.
            doc (spacy.Doc): The spaCy document object of the original text.
            skip_imprecise_quantities (bool): If True, imprecise quantities are skipped.
            filter (bool): If True, only quantities with numbers are returned.
            soft_filter (bool): If True, quantity spans that only consist of special characters or whitespace are removed.            
            post_process (bool): If True, trailing commas and whitespaces are removed and adjecent and overlapping quantity spans are merged.
            add_curation_fields (bool): If True, additional fields for later manual curation are added to the output.

        Returns:
            list: List of identified and normalized quantity spans with their char offsets in the original text.
        """
        tic = time()

        # Remove whitespaces. Only trailing ones to not affect char offsets.
        chunks = [chunk.rstrip() for _, chunk in batch]

        # Print GPU quantity span identification model is running on.
        if self.verbose:
            msg.info(f"Quantity span identification running on device {device_rank}.")

        quantity_spans_per_chunk = self._identify_quantity_spans(chunks, device_rank)

        pp_quantity_spans_per_chunk = []
        for quantity_spans, ((char_offset, _), chunk) in zip(quantity_spans_per_chunk, batch):

            if pre_filter_imprecise_quantities:=False:                     
                # Pre-filter imprecise quantities before using the quantity parser result for actual filtering.
                quantity_spans = [q for q in quantity_spans if contains_any_number(q["text"], consider_imprecise_quantites=not skip_imprecise_quantities)]
                        
            if filter:
                # Filter out all spans that do not contain any numbers.
                quantity_spans = filter_quantity_spans(quantity_spans)

            if soft_filter:
                # Filter out all spans that are only special characters or whitespace.
                quantity_spans = filter_garbage_quantity_spans(quantity_spans)
                            
            if post_process:
                # Remove trailing commas, whitespace and merge adjecent and overlapping quantity spans.
                quantity_spans = merge_likely_wrongly_split_quantity_spans(quantity_spans, chunk)
                quantity_spans = postprocess_quantity_spans(quantity_spans, chunk)
                
            # Check if the quantity span is valid.
            if self.debug:
                for q in quantity_spans:
                    assert q["start"] <= q["end"], f'Quantity span {q} has invalid char offsets. Span: {chunk[q["start"]:q["end"]]}'
                    assert q["text"] == chunk[q["start"]:q["end"]], f'Quantity span {q} has invalid surface or char offsets. Span: {chunk[q["start"]:q["end"]]}'              
        
            if len(quantity_spans) > 0:  
                quantity_spans = add_char_offset(quantity_spans, char_offset)                                 

                # -------------------------
                #  Add quantity modifiers
                # -------------------------
                # TODO: Use already created doc and not create doc from text again. Therefore, add 
                #       tokenizer changes of qmod_extractor spaCy pipeline to quinex main spaCy pipeline.
                qmods, quantity_spans = self.qmod_extractor(doc.text, quantity_spans)

                # -------------------------
                #    Normalize quantity
                # -------------------------
                quantity_spans = self._parse_and_normalize_quantity_spans(quantity_spans, chunk, add_curation_fields=add_curation_fields)

            pp_quantity_spans_per_chunk.extend(quantity_spans)

        if self.verbose:
            msg.good("Quantity span identification done in", round(time()-tic, 3), "s.")

        # Optinally, skip imprecise quantities such as 'several trees'.
        if skip_imprecise_quantities:
            quantities = []
            imprecise_quantities_surfaces = []
            for q in pp_quantity_spans_per_chunk:
                if all(ind_q["value"]["normalized"]["is_imprecise"] for ind_q in q["normalized"]["individual_quantities"]["normalized"]):
                    imprecise_quantities_surfaces.append(q["text"])                    
                    continue
                else:
                    quantities.append(q)

            if len(imprecise_quantities_surfaces) > 0:
                msg.text("Ignoring the following imprecise quantitities (set skip_imprecise_quantities=False to disable): " + str(imprecise_quantities_surfaces), color="grey")
                
        else:
            quantities = pp_quantity_spans_per_chunk

        return quantities
    

    def _parse_and_normalize_quantity_spans(self, quantity_spans, chunk, add_curation_fields=False, summarized_output=True):
        """
        Parse and normalize quantity spans.
        1. Parse quantity span in normalized modifiers, values, and units.
        2. Check if quantity is relative.
        3. Add curation fields 
        4. Simplify format if desired.        
        """
        for quantity in quantity_spans: 
            
            # Parse quantity span in normalized modifiers, values, and units.
            quantity["normalized"] = self.quantity_parser.parse(
                quantity["quantity_with_modifiers"]["text"]
                )
            
            # Check if quantity is relative.
            is_relative = is_relative_quantity(quantity["quantity_with_modifiers"], chunk)
            
            # Add curation fields if desired and set is_relative field.
            if add_curation_fields:
                quantity["normalized"]["type"] = {"class": quantity["normalized"]["type"], "curation": []}
                quantity["normalized"]["is_relative"] = {"bool": is_relative, "curation": []}
            else:
                quantity["normalized"]["is_relative"] = is_relative
            
            # Quantities are always explicit, because 
            # they are extracted using sequence labeling.
            quantity["is_implicit"] = False 

            # Remove redundant information.
            del quantity["modifiers"]
            del quantity["quantity_with_modifiers"]

            # Simplify normalized quantities.
            if summarized_output:
                quantity = self._summarize_normalized_quantity(quantity, add_curation_fields)

        return quantity_spans


    def _summarize_normalized_quantity(self, quantity, add_curation_fields=False):
        """
        Simplify normalized quantity structure.
        """

        def _combine_normalized_quantity_modifiers(normalized_quantity: dict, default="=") -> str:
            """
            Combine prefixed and suffixed normalized quantity modifiers.
            """
            normalized_modifiers = ""
            for key in ["prefixed_modifier", "suffixed_modifier"]:                   
                if normalized_quantity[key] != None and normalized_quantity[key]["normalized"] != None:
                    normalized_modifiers += normalized_quantity[key]["normalized"]
            
            return normalized_modifiers if normalized_modifiers != "" else default

        def _summarize_normalized_units(normalized_quantity: dict) -> dict:
            """
            Summerize normalized units (e.g., by combining prefixed and suffixed units).
            """
            
            # Combine prefixed and suffixed units.
            unit = {
                "text": {"ellipsed": "", "prefixed": "", "suffixed": ""},
                "normalized": []
            }
            for key in ["prefixed_unit", "suffixed_unit"]:  
                if normalized_quantity[key]!= None:
                    unit["text"][key.removesuffix("_unit")] = normalized_quantity[key]["text"]
                    if normalized_quantity[key]["ellipsed_text"] != None:
                        unit["text"]["ellipsed"] = normalized_quantity[key]["ellipsed_text"]
                    if normalized_quantity[key]["normalized"] != None:
                        unit["normalized"].extend(normalized_quantity[key]["normalized"])
            
            del normalized_quantity["prefixed_unit"]
            del normalized_quantity["suffixed_unit"]                         
            
            # Make unit tuples more explicit.
            normalized_units = []
            for (text, exp, uri, year) in unit["normalized"]:
                normalized_units.append({"text": text, "exponent": exp, "uri": uri, "year": year})            
            
            unit["normalized"] = normalized_units

            return unit

        del quantity["normalized"]["nbr_quantities"]
        del quantity["normalized"]["success"]
        del quantity["normalized"]["separators"]
        del quantity["normalized"]["text"]
        
        normalized_quantities = []
        for q in quantity["normalized"]["normalized_quantities"]:
            
            # Summarize normalized modifiers in single string.
            combined_qmods = _combine_normalized_quantity_modifiers(q)
            del q["prefixed_modifier"]
            del q["suffixed_modifier"]

            # Summerize value.
            if q["value"]["normalized"] == None:
                q["value"]["normalized"]["numeric_value"] = None
                q["value"]["normalized"]["is_imprecise"] = None

            q["value"]["normalized"]["modifiers"] = combined_qmods
            q["value"]["normalized"]["is_mean"] = None  # TODO: is_mean and is_median are not used
            q["value"]["normalized"]["is_median"] = None  

            # Summarize uncertainty.
            if q["uncertainty_expression_pre_unit"] != None and q["uncertainty_expression_post_unit"] != None:
                raise NotImplementedError("Both pre- and post-unit uncertainty expressions are not supported yet.")
            elif q["uncertainty_expression_pre_unit"] != None:
                q["uncertainty"] = q["uncertainty_expression_pre_unit"]
            elif q["uncertainty_expression_post_unit"] != None:
                q["uncertainty"] = q["uncertainty_expression_post_unit"]
            
            del q["uncertainty_expression_pre_unit"]
            del q["uncertainty_expression_post_unit"]
            
            # Summarize units.
            q["unit"] = _summarize_normalized_units(q)

            normalized_quantities.append(q)

        if add_curation_fields:
            quantity["normalized"]["individual_quantities"] = {"normalized": normalized_quantities, "curation": []}
        else:
            quantity["normalized"]["individual_quantities"] = {"normalized": normalized_quantities}

        del quantity["normalized"]["normalized_quantities"]

        return quantity


    def _identify_quantity_spans(self, chunks: list[str], device_rank: int):
        """
        Identify all quantity spans in a list of texts using the quantity span identification model.
        
        Assumes aggregation strategy of token-classification pipeline is set to "simple".
        Make sure to set the aggregation strategy to "simple" when initializing the pipeline in load_transformers_pipe().
        """
        
        # Use the default aggregation strategy.                    
        raw_quantities_per_chunk = self.quantity_pipelines[device_rank](chunks)

        # Transform BIO tags to char-level annotation spans.
        quantity_spans_per_chunk = []
        for raw_quantities, chunk in zip(raw_quantities_per_chunk, chunks):                
            quantity_spans_in_chunk = []
            for raw_quantity in raw_quantities:                    
                start_char = raw_quantity["start"]
                end_char = raw_quantity["end"]
                quantity = {
                    "start": start_char,
                    "end": end_char,
                    "text": chunk[start_char:end_char],
                }
                quantity_spans_in_chunk.append(quantity)
            
            quantity_spans_per_chunk.append(quantity_spans_in_chunk)

        return quantity_spans_per_chunk








