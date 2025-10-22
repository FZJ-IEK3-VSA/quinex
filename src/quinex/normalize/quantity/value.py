import re
from copy import deepcopy



def set_to_single_quantity(normalized_quantity_with_meta, single_normalized_quantity):
    normalized_quantity_with_meta["type"] = "single_quantity"
    normalized_quantity_with_meta["nbr_quantities"] = 1
    normalized_quantity_with_meta["normalized_quantities"] = [single_normalized_quantity]
    return normalized_quantity_with_meta


def transform_list_into_single_value(normalized_list, temporal_scope, split_temporal_scope_accordingly=True):
    """
    Transform lists into single values by creating a single quantity for each value in the list.
    """
    # Lists must have at least two values.
    if len(normalized_list["normalized_quantities"]) < 2:
        return [], []
        
    # Check if temporal scope is given individually for each value in the list,
    # e.g., 'in 2018 2020, 2025', '2021, 2023 and 2026'.            
    years = re.findall(r"\b\d{4}\b", temporal_scope)
    if len(years) != len(normalized_list["normalized_quantities"]) or not split_temporal_scope_accordingly:
        years = [temporal_scope] * len(normalized_list["normalized_quantities"])        
    
    # Make a single quantity out of each element in the list.
    nq_as_single_q = []
    nq_as_single_q_temp_scope = []  
    for list_element, year in zip(normalized_list["normalized_quantities"], years):
        nq_single = deepcopy(normalized_list)
        nq_single = set_to_single_quantity(nq_single, list_element)
        nq_as_single_q.append(nq_single)
        nq_as_single_q_temp_scope.append(year)
            
    return nq_as_single_q, nq_as_single_q_temp_scope


def transform_interval_into_single_value(normalized_interval, temporal_scope, split_if_individual_temporal_scopes_given=True, take_first_value_if_interval_with_different_units=True):
    """
    Transform intervals into single values by averaging the two bounds.
    """
    # Intervals must have exactly two bounds.
    if len(normalized_interval["normalized_quantities"]) != 2:
        return [], []

    # First, try to split range into individual quantities 
    # if the temporal scope is given individually for each value
    # (e.g., 'from 2015 to 2025' for '20 to 30 million dollars'). 
    if split_if_individual_temporal_scopes_given:
        years = re.findall(r"\b\d{4}\b", temporal_scope)            
        if len(years) == 2 and split_if_individual_temporal_scopes_given:
            # Don't average the values, but create two separate quantities with the respective temporal scope.
            nq_as_single_q = []
            nq_as_single_q_temp_scope = []               
            for range_bound, year in zip(normalized_interval["normalized_quantities"], years):
                nq_single = deepcopy(normalized_interval)
                nq_single = set_to_single_quantity(nq_single, range_bound)
                nq_as_single_q.append(nq_single)
                nq_as_single_q_temp_scope.append(year)

            return nq_as_single_q, nq_as_single_q_temp_scope
        
    # If we are here, we have an interval with two bounds and no individual temporal scopes.                
    # In this case, we calculate the mean of the two bounds.
    try:
        # Make sure units are the same before averaging the values.
        assert (normalized_interval["normalized_quantities"][0]["prefixed_unit"] == None and normalized_interval["normalized_quantities"][1]["prefixed_unit"] == None \
                or normalized_interval["normalized_quantities"][0]["prefixed_unit"]["normalized"] == normalized_interval["normalized_quantities"][1]["prefixed_unit"]["normalized"]) \
                    and (normalized_interval["normalized_quantities"][0]["suffixed_unit"] == None and normalized_interval["normalized_quantities"][1]["suffixed_unit"] == None \
                        or normalized_interval["normalized_quantities"][0]["suffixed_unit"]["normalized"] == normalized_interval["normalized_quantities"][1]["suffixed_unit"]["normalized"])
    except:
        # Units do not match, so we cannot average the values.
        if take_first_value_if_interval_with_different_units:
            # Assume quantity was mistakenly identified as an interval, but actually is a single value.
            # TODO: Also adjust unit by re-running the unit parser            
            nq_single = deepcopy(normalized_interval)
            nq_i = nq_single["normalized_quantities"][0]  # take first value
            nq_single = set_to_single_quantity(nq_single, nq_i)            
            return [nq_single], [temporal_scope] 
        else: 
            # Units do not match. 
            # TODO: Unit conversion?
            print(f"Warning: Cannot calculate mean from interval because units of bounds do not match. Skipping '{normalized_interval['text']}'.")
            return [], []
    
    # TODO: Test "USD 0.17-0.30/kWh", "139.07~141.19 KRW/kWh", "$91/ MWh", "3% on average and 46%", "24 €/MWh in Malaga to 42 €/MWh", "70 €/MWh in 2015 to 52 €/MWh"
    bound_a = normalized_interval["normalized_quantities"][0]["value"]["normalized"]["numeric_value"]
    bound_b = normalized_interval["normalized_quantities"][1]["value"]["normalized"]["numeric_value"]
    mean_value = (bound_a + bound_b) / 2                    
    nq_single = deepcopy(normalized_interval)
    nq_single["type"] = "single_quantity"
    nq_single["nbr_quantities"] = 1
    nq_i = nq_single["normalized_quantities"][-1]  # take any value because units match
    nq_single = set_to_single_quantity(nq_single, nq_i)    
    nq_single["normalized_quantities"][0]["value"]["normalized"]["numeric_value"] = mean_value
    
    return [nq_single], [temporal_scope]


def transform_ratio_into_single_value(normalized_ratio):
    """
    Transform lists into single values by creating a single quantity for each value in the list.
    """

    # Ratios must have at least two values.    
    if len(normalized_ratio["normalized_quantities"]) < 2:
        return [], []
    
    # TODO: better handle preservation of units and modifiers
    ratio_result = normalized_ratio["normalized_quantities"][0]["value"]["normalized"]["numeric_value"] 
    ratio_surface = normalized_ratio["normalized_quantities"][0]["value"]["text"]
    for v, div_sign in zip(normalized_ratio["normalized_quantities"][1:], normalized_ratio['separators']):
        if v["value"]["normalized"]["numeric_value"] == 0:
            print(f"Warning: Cannot create a single value from ratio {normalized_ratio['text']} because it contains a zero denominator.")
            return [], []
        else:
            ratio_result /= v["value"]["normalized"]["numeric_value"]
            ratio_surface += f"{div_sign[0]}{v['value']['text']}"
    
    nq_single = deepcopy(normalized_ratio)
    nq_i = v # copy info from last value
    nq_single = set_to_single_quantity(nq_single, nq_i)
    nq_single["normalized_quantities"][0]["value"]["normalized"]["numeric_value"] = ratio_result
    nq_single["normalized_quantities"][0]["value"]["text"] = ratio_surface
    
    return [nq_single], []


def get_single_quantities_from_normalized_quantity(normalized_quantity, temporal_scope, consider_intervals=True, consider_lists=True, consider_ratios=True, consider_multidimensional=True, take_first_value_if_interval_with_different_units=True, split_interval_if_individual_temporal_scopes_given=True):

    # Init
    single_quantities = []
    temporal_scopes = []

    if normalized_quantity["type"] in ["single_quantity", "unknown"]:
        # Nothing to do.
        pass
    elif normalized_quantity["type"] == "range":
        if consider_intervals:
            # Transform interval.                
            single_quantities, temporal_scopes = transform_interval_into_single_value(normalized_quantity, temporal_scope, split_if_individual_temporal_scopes_given=split_interval_if_individual_temporal_scopes_given, take_first_value_if_interval_with_different_units=take_first_value_if_interval_with_different_units)
    elif normalized_quantity["type"] == "list":
        if consider_lists:
            # Transform list into single quantities.
            single_quantities, temporal_scopes = transform_list_into_single_value(normalized_quantity, temporal_scope)
    elif normalized_quantity["type"] == "ratio":
        if consider_ratios:
            single_quantities, temporal_scopes = transform_ratio_into_single_value(normalized_quantity)    
    elif normalized_quantity["type"] == "multidim":
        if consider_multidimensional:
            # Not implemented yet.
            raise NotImplementedError("How to reduce a multi-dimensional quantity to a single quantity?")
    else:
        raise NotImplementedError(f"Unexpected quantity type: {normalized_quantity['type']}")

    return single_quantities, temporal_scopes


