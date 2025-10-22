import re
import time
import json
import requests
from copy import deepcopy
from datetime import datetime
import pandas as pd
from tqdm import tqdm
from quinex_utils.parsers.quantity_parser import FastSymbolicQuantityParser, FastSymbolicUnitParser
from quinex_utils.functions import normalize_quantity_span
from quinex_utils.functions.boolean_checks import contains_any_number


def load_application_results(path):
    """
    Load application results from a JSON file.
    """
    # Load the results from the JSON file
    with open(path, "r") as f:
        results = json.load(f)
        
    flattened_results = []
    i = 0
    for abstract in results:
        for prediction in abstract["predictions"]:
            flattened_results.append({
                "index": i,
                "pub_year": abstract["Year"],
                "citations": abstract["Cited by"],
                "abstract": abstract["Abstract"],
                "doi": abstract["DOI"],
                "entity": normalize_quantity_span(prediction['claim']["entity"]["text"].lower()),
                "entity_raw": prediction['claim']["entity"]["text"],
                "property": prediction['claim']["property"]["text"].lower(),
                "quantity": prediction['claim']["quantity"]["text"],
                "is_relative": prediction['claim']["quantity"]["normalized"]["is_relative"]["bool"],
                'temporal_scope': prediction['qualifiers']['temporal_scope']["text"],
                'spatial_scope': prediction['qualifiers']['spatial_scope']["text"],
                'reference':  prediction['qualifiers']['reference']["text"],
                'method': prediction['qualifiers']['method']["text"],
                "qualifier": prediction['qualifiers']['qualifier']["text"]
            })            
            i += 1
    
    df = pd.DataFrame(flattened_results)
    df.set_index("index", inplace=True)

    return df


def condense_quantity_format(single_normalized_quantities):
    simple_normalized_quantities = []
    for quantity in single_normalized_quantities:    
        index = quantity["index"]
        normalized_quantity = quantity["normalized_quantity"]["normalized_quantities"][0]    
        
        if normalized_quantity["value"]["normalized"] == None or normalized_quantity["value"]["normalized"]["is_imprecise"]:
            continue
        else:
            value = normalized_quantity["value"]["normalized"]["numeric_value"]

        unit = []
        if normalized_quantity["prefixed_unit"] != None and normalized_quantity["prefixed_unit"]["normalized"] != None:
            unit += normalized_quantity["prefixed_unit"]["normalized"] 
        if normalized_quantity["suffixed_unit"] != None and normalized_quantity["suffixed_unit"]["normalized"] != None:    
            unit += normalized_quantity["suffixed_unit"]["normalized"] 

        simple_normalized_quantities.append({"index": index, "text": quantity["normalized_quantity"]["text"], "value": value, "unit": unit, "temporal_scope": quantity["temporal_scope"]})

    return simple_normalized_quantities
    




