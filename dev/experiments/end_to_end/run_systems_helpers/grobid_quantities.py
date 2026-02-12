import json
import requests
from .out_strucuture import empty_concept, empty_qualifiers_dict, empty_statement_clf_dict


delimiter = '\n'
def text_splitter(text):
    return text.split(delimiter)

delimiter_len = len(delimiter)

def extract(text, doc_offset, endpoint_url="http://localhost:8060/service/processQuantityText"):

    def normalize_text(text):
        text = text.replace("\u2009", " ")
        text = text.replace("–", "-")
        return text

    normalized_text = normalize_text(text)
    response = requests.post(endpoint_url, files={"text": (None, normalized_text)})
    if response.status_code != 200:
        raise ValueError
    
    qclaims = []
    result = json.loads(response.text)
    if "measurements" in result:            
        for res in result['measurements']:

            # Quantified object.
            if "quantified" in res:
                measured_concepts_span = res["quantified"]["rawName"]
                measured_concepts_offsets = (res["quantified"]["offsetStart"], res["quantified"]["offsetEnd"])
                if normalize_text(text[measured_concepts_offsets[0]:measured_concepts_offsets[1]]) != measured_concepts_span:
                    start_char = text.find(measured_concepts_span)
                    if start_char != -1:
                        # Grobid-quantities seems to return char offsets relative to sentence start for quantified objects.
                        print("Warning: Character offsets of quantified object wrong, however, found span in text and use offsets of this match.")
                        end_char = start_char + len(measured_concepts_span)
                        print("Quantity offsets:", (res["measurementOffsets"]["start"], res["measurementOffsets"]["end"]))
                        print("Old offsets:", measured_concepts_offsets)
                        measured_concepts_offsets = (start_char, end_char)
                        print("New offsets:", measured_concepts_offsets)                    
                    else:
                        print("Warning: Character offsets of quantified object wrong and did not found span in text.")
                        measured_concepts_offsets = (0, 0)
                else:                
                    pass
                entity = {
                    "is_implicit": False,
                    "start": measured_concepts_offsets[0] + doc_offset,
                    "end": measured_concepts_offsets[1] + doc_offset,
                    "text": measured_concepts_span,
                    "curation": []
                }
            else:
                entity = empty_concept

            # Property.
            property = empty_concept

            # Quantity.
            if "measurementRaw" in res:
                quantity_span = res["measurementRaw"]
                quantity_offsets = (res["measurementOffsets"]["start"], res["measurementOffsets"]["end"])
                is_range = True if res["measurementRaw"] == "interval" else False                
                assert normalize_text(text[quantity_offsets[0]:quantity_offsets[1]]) == quantity_span
            else:
                assert 'rawUnit' not in res['quantity'], "TODO: Add unit offset"
                quantity_span = res['quantity']["rawValue"]
                quantity_offsets = (res['quantity']['offsetStart'], res['quantity']['offsetEnd'])
                is_range = False # TODO: assumption
                assert normalize_text(text[quantity_offsets[0]:quantity_offsets[1]]) == quantity_span


            def quantity_dict_to_value_unit_span_and_offsets(quantity_dict):
                value_span = quantity_dict["rawValue"]
                value_offsets = (quantity_dict["offsetStart"], quantity_dict["offsetEnd"])
                value_numeric = quantity_dict["parsedValue"].get("numeric")
                if "rawUnit" in quantity_dict:
                    unit = quantity_dict["rawUnit"]
                    unit_span = unit["name"]
                    unit_offsets = (unit["offsetStart"], unit["offsetEnd"])
                    no_unit = False
                    is_suffixed_unit = unit_offsets[0] > value_offsets[0]
                else:                
                    unit_span = ""
                    unit_offsets = (0, 0)
                    no_unit = True
                    is_suffixed_unit = False

                quantity_type = quantity_dict.get("type")
                
                return value_span, value_offsets, value_numeric, unit_span, unit_offsets, is_suffixed_unit, no_unit, quantity_type

            # Value and unit.
            is_range = False
            is_list = False
            is_time = False
            if res['type'] == 'value':
                value_span, value_offsets, value_numeric, unit_span, unit_offsets, is_suffixed_unit, no_unit, quantity_type = quantity_dict_to_value_unit_span_and_offsets(res['quantity'])
                is_time = quantity_type == "time" and len(unit_span) == 0
            elif res['type'] == 'interval':
                if 'quantityLeast' in res and 'quantityMost' in res:
                    value_lb_span, value_lb_offsets, value_lb_numeric, unit_lb_span, unit_lb_offsets, is_suffixed_unit_lb, no_unit_lb, quantity_type_lb = quantity_dict_to_value_unit_span_and_offsets(res['quantityLeast'])
                    value_ub_span, value_ub_offsets, value_ub_numeric, unit_ub_span, unit_ub_offsets, is_suffixed_unit_ub, no_unit_ub, quantity_type_ub = quantity_dict_to_value_unit_span_and_offsets(res['quantityMost'])
                    is_range = True
                elif 'quantityLeast' in res:
                    value_span, value_offsets, value_numeric, unit_span, unit_offsets, is_suffixed_unit, no_unit, quantity_type = quantity_dict_to_value_unit_span_and_offsets(res['quantityLeast'])
                    modifier = ">="
                elif 'quantityMost' in res:
                    value_span, value_offsets, value_numeric, unit_span, unit_offsets, is_suffixed_unit, no_unit, quantity_type = quantity_dict_to_value_unit_span_and_offsets(res['quantityMost'])
                    modifier = "<="
                else:
                    raise NotImplementedError                                                
            elif res['type'] == 'listc':
                values_span = []
                values_offsets = []
                values_numeric = []
                units_span = []
                units_offsets = []
                is_suffixed_units = []
                no_units = []
                for el in res["quantities"]:
                    value_span, value_offsets, value_numeric, unit_span, unit_offsets, is_suffixed_unit, no_unit, quantity_type = quantity_dict_to_value_unit_span_and_offsets(el)
                    values_span.append(value_span)
                    values_offsets.append(value_offsets)
                    values_numeric.append(value_numeric)
                    units_span.append(unit_span)
                    units_offsets.append(unit_offsets)
                    is_suffixed_units.append(is_suffixed_unit)
                    no_units.append(no_unit)
                is_list = True
            else:
                raise NotImplementedError
            
            
            if not is_time:
                change_normalized = "="
                if is_range:
                    individual_quantities = [
                        {
                            "value": {
                                "normalized": {
                                    "numeric_value": value_lb_numeric,
                                    "is_imprecise": False,
                                    "modifiers": "=",
                                    "is_mean": None,
                                    "is_median": None
                                },
                                "text": value_lb_span
                            },
                            "unit": {
                                "text": {
                                    "prefixed": "" if is_suffixed_unit_lb else unit_lb_span,
                                    "suffixed": unit_lb_span if is_suffixed_unit_lb else "",
                                    "ellipsed": ""
                                },
                                "normalized": [] # TODO: Add normalized unit
                            }
                        },
                        {
                            "value": {
                                "normalized": {
                                    "numeric_value": value_ub_numeric,
                                    "is_imprecise": False,
                                    "modifiers": "=",
                                    "is_mean": None,
                                    "is_median": None
                                },
                                "text": value_ub_span
                            },
                            "unit": {
                                "text": {
                                    "prefixed": "" if is_suffixed_unit_ub else unit_ub_span,
                                    "suffixed": unit_ub_span if is_suffixed_unit_ub else "",
                                    "ellipsed": ""
                                },
                                "normalized": [] # TODO: Add normalized unit
                            }
                        }
                    ]
                elif is_list:
                    individual_quantities = [{
                        "value": {
                            "normalized": {
                                "numeric_value": value_numeric,
                                "is_imprecise": False,
                                "modifiers": "=", # TODO: Add change direction
                                "is_mean": None,
                                "is_median": None
                            },
                            "text": value_span
                        },
                        "unit": {
                            "text": {
                                "prefixed": "" if is_suffixed_unit else unit_span,
                                "suffixed": unit_span if is_suffixed_unit else "",
                                "ellipsed": ""
                            },
                            "normalized": [] # TODO: Add normalized unit
                        }
                    } for value_numeric, value_span, is_suffixed_unit, unit_span in zip(values_numeric, values_span, is_suffixed_units, units_span)]
                else:                    
                    individual_quantities = [{
                        "value": {
                            "normalized": {
                                "numeric_value": value_numeric,
                                "is_imprecise": False,
                                "modifiers": "=", # TODO: Add change direction
                                "is_mean": None,
                                "is_median": None
                            },
                            "text": value_span
                        },
                        "unit": {
                            "text": {
                                "prefixed": "" if is_suffixed_unit else unit_span,
                                "suffixed": unit_span if is_suffixed_unit else "",
                                "ellipsed": ""
                            },
                            "normalized": [] # TODO: Add normalized unit
                        }
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