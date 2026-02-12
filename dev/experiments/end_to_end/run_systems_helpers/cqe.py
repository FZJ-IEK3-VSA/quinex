import re
from CQE import CQE
from CQE.classes import Range
from .out_strucuture import empty_concept, empty_qualifiers_dict, empty_statement_clf_dict


cqe_parser = CQE.CQE(overload=True)

delimiter = '\n\n'
def text_splitter(text):
    return text.split(delimiter)

delimiter_len = len(delimiter)
                
def extract(text, doc_offset):

    def find_closest_match(text, search_substring, ref_start_char, ref_end_char):
        """
        Find the occurrence of search_substring closest to a reference substring.
        
        Args:
            text: The string to search in
            ref_start_char: Start index of the reference substring
            ref_end_char: End index of the reference substring
            search_substring: The substring or pattern to find all matches of
        
        Returns:
            Tuple of (start_index, end_index) of the closest match, or None if not found
        """
        if not search_substring or not text:
            return None
                
        # Find all matches using re.finditer
        matches = [(m.start(), m.end()) for m in re.finditer(re.escape(search_substring), text)]
        
        if not matches:
            return None
        
        # Find closest match by minimum distance between boundaries
        def distance(match):
            match_start, match_end = match
            # Distance is 0 if ranges overlap, otherwise minimum gap between them
            if match_end <= ref_start_char:
                return ref_start_char - match_end
            elif match_start >= ref_end_char:
                return match_start - ref_end_char
            else:
                return 0  # overlapping
        
        closest = min(matches, key=distance)
        
        return closest


    def token_list_to_span_and_char_offsets(tokens, text):

        start_char = tokens[0].idx
        end_char = tokens[-1].idx + len(tokens[-1])    
        span_in_preprocessed_doc = tokens[0].doc.text[start_char:end_char]
        
        if span_in_preprocessed_doc == text[start_char:end_char]:
            char_offsets = (start_char, end_char)
            span_in_orginal_text = span_in_preprocessed_doc
        else:
            if span_in_preprocessed_doc == '0.25 ffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffi k2.5 T million':
                span_in_preprocessed_doc = '¼ ffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffiffi kT=2.5M'
            char_offsets = find_closest_match(text, span_in_preprocessed_doc, start_char, end_char)
            if char_offsets == None:
                # Try again.                
                char_offsets = find_closest_match(text.replace("-", " "), span_in_preprocessed_doc, start_char, end_char)
                if char_offsets == None:
                    # Try again.
                    char_offsets = find_closest_match(text.replace(" +", " up ").replace(" -", " minus "), span_in_preprocessed_doc, start_char, end_char)
                    if char_offsets == None:
                        # Try again.
                        rectified_span = span_in_preprocessed_doc.replace("12 h", "12h").replace("deg","degrees ").lower()
                        char_offsets = find_closest_match(text.lower(), rectified_span, start_char, end_char)
                        if char_offsets == None:
                            # Try again.
                            rectified_spans = []
                            for k, thousand in [
                                                    ("B", "billion"),
                                                    ("b", "billion"),
                                                    ("M", "million"),
                                                    ("K", "thousand"),
                                                    ("k", "thousand"),
                                                    ("bn", "billion"),
                                                    ("tn", "trillion"),
                                                ]:
                                if thousand in span_in_preprocessed_doc:
                                    rectified_span = rectified_span.replace(thousand, k).replace(" " + thousand, k)
                                    rectified_spans.append(span_in_preprocessed_doc.replace(thousand, k))
                                    rectified_spans.append(span_in_preprocessed_doc.replace(" " + thousand, k))

                            for nspan in rectified_spans:
                                char_offsets = find_closest_match(text, nspan, start_char, end_char)                        
                                if char_offsets != None:
                                    break

                            if char_offsets == None:
                                # Try again.
                                char_offsets = find_closest_match(text.lower(), rectified_span.replace("0.25", "¼").lower(), start_char, end_char)
                
            if char_offsets == None:
                raise NotImplementedError
            
            span_in_orginal_text = text[char_offsets[0]:char_offsets[1]]            
            
            if span_in_orginal_text != span_in_preprocessed_doc:
                print("\n")
                print("span_in_orginal_text", span_in_orginal_text)
                print("span_in_preprocessed_doc", span_in_preprocessed_doc)

        return span_in_orginal_text, char_offsets
    

    result = cqe_parser.parse(text)
    
    qclaims = []
    for res in result:

        # ============ Change ============
        change_normalized = res.change.change
        change_spans = res.change.span

        # ============ Measured Concepts ============
        measured_concepts_normalized = res.referred_concepts.noun
        measured_concepts_spans = []
        measured_concepts_char_offsets = []
        if measured_concepts_normalized != '-':
            for tokens in measured_concepts_normalized.values():
                span, char_offsets = token_list_to_span_and_char_offsets(tokens, text)
                measured_concepts_spans.append(span)
                if span == "HPCs in suspension":
                    print("Investigate")
                measured_concepts_char_offsets.append(char_offsets)
        
        # ============ Value ============
        if type(res.value) == Range:
            is_range = True
            if str(res.value.span) == '[10, minus, 1]':
                print("Investigate!")
            value_span, value_char_offsets = token_list_to_span_and_char_offsets(res.value.span, text)
            lb = res.value.lower
            ub = res.value.upper            

        else:
            is_range = False
            value_normalized = res.value.value
            value_char_offsets = res.value.char_indices
            assert len(value_char_offsets) == 1

            # Check indices correct.
            value_span, value_char_offsets = token_list_to_span_and_char_offsets(res.value.span, text)

        # ============ Unit ============
        unit_normalized = res.unit.norm_unit
        if unit_normalized in ['-', '% -']:
            unit_char_offsets = (0, 0)
            unit_span = ""
            is_suffixed_unit = True
            unit_is_implicit = True
            quantity_offsets = value_char_offsets
        else:
            unit_char_offsets = res.unit.char_indices
            
            if len(unit_char_offsets) == 1:
                unit_is_implicit = False
            
                # Check indices correct.
                unit_span, unit_char_offsets = token_list_to_span_and_char_offsets(res.unit.span, text)

            elif len(unit_char_offsets) == 0:
                unit_span, unit_char_offsets = token_list_to_span_and_char_offsets(res.unit.span, text)
                unit_is_implicit = False
            else:
                unit_char_offsets = (0, 0)
                unit_span = res.unit.norm_unit
                unit_is_implicit = True

            is_suffixed_unit = unit_char_offsets[0] > value_char_offsets[0]


        # ============ Quantity ============
        if unit_is_implicit:
            quantity_offsets = value_char_offsets
        else:
            quantity_offsets = (
                min(value_char_offsets[0], unit_char_offsets[0]),
                max(value_char_offsets[1], unit_char_offsets[1])
            )
        quantity_span = text[quantity_offsets[0]:quantity_offsets[1]]

        non_empty_concepts = []
        for spans, offsets in zip(measured_concepts_spans, measured_concepts_char_offsets):
            non_empty_concepts.append({
                    "is_implicit": False,
                    "start": offsets[0] + doc_offset,
                    "end": offsets[1] + doc_offset,
                    "text": spans,
                    "curation": []
                })

        if len(measured_concepts_spans) > 2:
            property = empty_concept
            entity  = {
                "is_implicit": True,
                "start": 0,
                "end": 0,
                "text": " | ".join(measured_concepts_spans),
                "curation": []
            }
        elif len(measured_concepts_spans) == 2:
            property = non_empty_concepts[0]
            entity = non_empty_concepts[1]
        elif len(measured_concepts_spans) == 1:
            property = empty_concept
            entity = non_empty_concepts[0]
        else:
            property = empty_concept
            entity = empty_concept

        unit = {
            "text": {
                "prefixed": "" if is_suffixed_unit else unit_span,
                "suffixed": unit_span if is_suffixed_unit else "",
                "ellipsed": ""
            },
            "normalized": [] # TODO: Add normalized unit
        }
        if is_range:
            individual_quantities = [
                {
                    "value": {
                        "normalized": {
                            "numeric_value": lb,
                            "is_imprecise": False,
                            "modifiers": "=",
                            "is_mean": None,
                            "is_median": None
                        },
                        "text": value_span  # TODO: Replace with span of lower bound
                    },
                    "unit": unit
                },
                {
                    "value": {
                        "normalized": {
                            "numeric_value": ub,
                            "is_imprecise": False,
                            "modifiers": "=",
                            "is_mean": None,
                            "is_median": None
                        },
                        "text": value_span  # TODO: Replace with span of upper bound
                    },
                    "unit": unit
                }
            ]

        else:                    
            individual_quantities = [{
                "value": {
                    "normalized": {
                        "numeric_value": value_normalized,
                        "is_imprecise": False,
                        "modifiers": "=", # TODO: Add change direction
                        "is_mean": None,
                        "is_median": None
                    },
                    "text": value_span
                },
                "unit": unit
            }]

        qclaim = {
            "claim": {
                "entity": entity,
                "property": property,
                "quantity": {
                    "normalized": {
                    "type": {
                        "class": "range" if is_range else "single_quantity",
                        "curation": []
                    },
                    "is_relative": {
                        "bool": True if change_normalized != "=" else False,
                        "curation": []
                    },
                    "individual_quantities": {
                        "normalized": individual_quantities,
                        "curation": []
                    }
                    },
                    "is_implicit": False,
                    "start": quantity_offsets[0] + doc_offset,
                    "end": quantity_offsets[1] + doc_offset,
                    "text": quantity_span,
                    "curation": []
                },            
            },
            "qualifiers": empty_qualifiers_dict,
            "statement_classification": empty_statement_clf_dict
        }
        
        qclaims.append(qclaim)

    return qclaims