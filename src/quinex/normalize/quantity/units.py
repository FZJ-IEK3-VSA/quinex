import time
from datetime import datetime
from tqdm import tqdm
from quinex_utils.parsers.unit_parser import FastSymbolicUnitParser


def transform_to_uniform_unit(convert_to, simple_normalized_quantities, flattened_results):
    # Only consider quantities that can be converted to the following unit.
    unit_parser = FastSymbolicUnitParser()    
    quantities_with_correct_unit = []
    start = time.time()
    for i, quantity in enumerate(tqdm(simple_normalized_quantities)):

        # Print elapsed time.
        if i % 100 == 0:
            print(f"Processing {i} of {len(simple_normalized_quantities)}")
            print(f"Elapsed time: {time.time() - start}")

        unit = quantity["unit"]        
        last_year = datetime.now().year - 1
        from_pub_year = flattened_results[quantity["index"]]["year"]
        from_assumed_year = min(last_year, from_pub_year) # Cannot be current or future year, because annual averages can only be calculated for past years.
        try:
            conv_value, conv_unit = unit_parser.unit_conversion(value=quantity["value"], from_compound_unit=unit, to_compound_unit=convert_to, from_default_year=None, to_default_year=None, verbose=False)
        except Exception as e:
            print(f"Error: {e}")
            continue
            
        if conv_value == None:
            continue
        else:
            quantity["value"] = conv_value
            quantity["unit"] = conv_unit

            quantities_with_correct_unit.append(quantity)
    
    return quantities_with_correct_unit








