
import re
import json
import pandas as pd
from tqdm import tqdm



def filter_based_on_characteristic_keywords(df, keywords: list[list[str]], column_name: str):
    """
    All given keywords must be present in the quantity, otherwise the row is dropped.
    """        
    for keyword_w_synonyms in keywords:
        escaped_kw_w_synonyms  = [re.escape(kw) for kw in keyword_w_synonyms]
        mask = df[column_name].str.contains("|".join(escaped_kw_w_synonyms), case=False)
        df = df[mask]

    return df


def only_absolute_quantities(df, remove_percentages_and_factors=True, remove_absolute_differences=False, remove_based_on_change_keywords=False, CHANGE_KEYWORDS=["improvement", "increment", "incline", "degradation", "reduction", "benefit", "deviation", "difference", "decrease", "increase", "loss", "advantage", "delta", "change"], verbose=True):
    """    
    Identify relative, absolute, and absolute difference quantities. Keep only absolute quantities.
    """
    dfs_to_remove = []
    if remove_percentages_and_factors:
        df_relative_percentage_or_factor = df[df["quantity"].str.contains("%|percent|times|fold", case=False)]
        dfs_to_remove.append(df_relative_percentage_or_factor)
    if remove_absolute_differences:
        df_absolute_difference = df[~df["quantity"].str.contains("%|percent|times|fold", case=False) & df["quantity"].str.startswith(("Δ","-","−","+"), na=False)]
        dfs_to_remove.append(df_absolute_difference)
    if remove_based_on_change_keywords:
        change_kws = "|".join(CHANGE_KEYWORDS)
        df_change_keywords = df[df["quantity"].str.contains(change_kws, case=False) | df["property"].str.contains(change_kws, case=False) | df["qualifier"].str.contains(change_kws, case=False)]
        dfs_to_remove.append(df_change_keywords)

    # Combine all relative quantities.
    df_relative = pd.concat(dfs_to_remove).drop_duplicates()

    # Absolute is what is not relative.
    df_absolute = df[~df.index.isin(df_relative.index)]
    
    if verbose:
        print(f">>>>>>>>>>>>>>> Deivided absolute from relative quantities <<<<<<<<<<<<<<<")
        print("Stats:")
        print(f" - {len(df_absolute)} absolute quantities")
        print(f" - {len(df_relative)} relative quantities, of which")
        if remove_percentages_and_factors:
            print(f"     - {len(df_relative_percentage_or_factor)} are percentages or factors")
        if remove_absolute_differences:
            print(f"     - {len(df_absolute_difference)} are absolute differences")
        if remove_based_on_change_keywords:
            print(f"     - {len(df_change_keywords)} are relative based on a change keyword")            
    
    return df_absolute


def filter_rows_with_value_outside_expected_bounds(df_filtered, expected_bounds, expected_bounds_except_for_facets=[], if_outside_expected_bounds_ask_instead_of_remove=True, answer_cache_path="answer_cache.json"):
    """
    Check if values are within expected bounds.
    """
    is_outside_bounds = lambda nq: any(nq_i["value"]["normalized"]["numeric_value"] < expected_bounds[0] or nq_i["value"]["normalized"]["numeric_value"] > expected_bounds[1] for nq_i in nq)
    df_outside_expected_bounds = df_filtered[df_filtered["normalized_quantity"].apply(lambda x: is_outside_bounds(x["normalized_quantities"]))]

    # Check each row in df_outside_expected_bounds and drop it if necessary based on human feedback.
    always_answer_true = not if_outside_expected_bounds_ask_instead_of_remove
        
    try: 
        with open(answer_cache_path, "r") as f:
            ANSWER_CACHE = json.load(f)
    except FileNotFoundError:
        ANSWER_CACHE = {"drop_row_indices": [], "do_not_drop_row_indices": []}

    for index, row in tqdm(df_outside_expected_bounds.iterrows()):
        
        nq = row["normalized_quantity"]
        quantity_str = row["quantity"]    
        nq_values = [nq_i["value"]["normalized"]["numeric_value"] for nq_i in nq["normalized_quantities"]]

        bounds_do_not_apply = any(row[facet] != None for facet in expected_bounds_except_for_facets)
        common_parsing_error = lambda nqv: len(nqv) == 2 and nqv[0] > 1 and nqv[-1] in [-1, 1]
        if bounds_do_not_apply: # Bounds may be only valid for certain facets but not for others (e.g., for humans but not mice).
            # Bounds do not apply for this row, so we skip the check.
            continue        
        elif common_parsing_error(nq_values): # Check for wrong interpretation of single quantity as interval which would lead to wrong average value later.                
            # Probably mistake of unit parser, e.g., '57 ml·kg-1·min-1' to 57 and 1.
            print(f"\nWarning: {quantity_str} was parsed into the multiple quantities ({nq_values}). Assuming that this is a parsing error and the first value is the correct one and the second value is part of the unit.")
            
            # Adapt the normalized quantity to only contain the first value.        
            # Note: Will be corrected at a later stage in transform_intervals_etc_to_single_value() anyway
            # if take_first_value_if_interval_with_different_units is set to True.    
            nq["type"] = "single_quantity"
            nq["nbr_quantities"] = 1
            nq["normalized_quantities"] = [nq["normalized_quantities"][0]]
            df_filtered.at[index, "normalized_quantity"] = nq            
            first_num_value = nq["normalized_quantities"][0]["value"]["normalized"]["numeric_value"] 

            if first_num_value >= expected_bounds[0] and first_num_value <= expected_bounds[1]:
                # If the first value is within the expected bounds, we keep the row.
                continue
            else:
                nq_values = [first_num_value]

        # Drop row based on human feedback.
        if index in ANSWER_CACHE["do_not_drop_row_indices"]:
            print("Kept row with quantity outside expected bounds based on cached user feedback.")
            pass
        elif index in ANSWER_CACHE["drop_row_indices"]:
            print("Dropped row with quantity outside expected bounds based on cached user feedback.")
            df_filtered.drop(index, inplace=True)
        else:
            q_pos = row["abstract"].find(quantity_str) # TODO: Use actual position and not first match
            snippet = row["abstract"][min(0,q_pos-300):q_pos+len(quantity_str) + 25].strip() if q_pos != -1 else "No snippet available"    
            print(f"\nWarning: {quantity_str} was parsed into the following values ({nq_values}) of which at least one is out of expected bounds ({expected_bounds[0]} < x < {expected_bounds[1]}).")
            print(f"Source snippet: '{snippet}'")
            answer = "y" if always_answer_true else input(f"Probably the unit is wrong or it is a relative/change value. Do you want to remove this value? (y/n) ").lower()
            if answer == "y":
                # Remove row from dataframe.
                df_filtered.drop(index, inplace=True)
                ANSWER_CACHE["drop_row_indices"].append(index)    
            else:
                ANSWER_CACHE["do_not_drop_row_indices"].append(index)

    # Save answer cache to file.
    with open(answer_cache_path, "w") as f:
        json.dump(ANSWER_CACHE, f, indent=4)   

    return df_filtered, df_outside_expected_bounds, ANSWER_CACHE


def only_keep_successfully_normalized_quantities(normalized_quantities, print_failed_list=True):
    """
    Only keep successful normalized quantities.
    """
    if print_failed_list:
        print("The following quantities could not be normalized and are discarded:")
        [print("- " + q["normalized_quantity"]["text"]) for q in normalized_quantities if q["normalized_quantity"]["success"] != True]

    return [q for q in normalized_quantities if q["normalized_quantity"]["success"] == True]


