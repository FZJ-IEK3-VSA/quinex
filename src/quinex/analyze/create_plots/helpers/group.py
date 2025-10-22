import re
import requests
from tqdm import tqdm
from quinex_utils.functions.boolean_checks import contains_any_number
from quinex.normalize.quantity.value import get_single_quantities_from_normalized_quantity



def add_category_based_on_keywords(df, search_in_column_names, category_column_name, keywords_dict, negative_keywords_dict={}, match_strategy="contains", mutual_exclusive=True):
    """
    Add a category to the DataFrame based on keywords.
    Keywords are matched case-insensitive.
    The keywords are matched when they are preceded by a word boundary. To force a trailing word boundary, 
    add a trailing whitespace etc. to the respective keyword in the keywords_dict.
    When there is also a match with keyword of another categories which is not a substring of the positive keyword,
    it is added to the negative keywords of the category.
    """
    # Add health category to df_vo2_max defaulting to None
    df[category_column_name] = None
    
    if match_strategy == "contains":
        # Add leading and trailing whitespace to the search columns to 
        # enable and disable matching substrings with simply added whitespace to keywords.    
        for search_column in search_in_column_names:
            df[search_column] = df[search_column].apply(lambda x: f" {x} " if isinstance(x, str) else x)

    # Assign health categories based on keywords
    for category_label, keywords in keywords_dict.items():

        if match_strategy == "fullmatch":
            # Match if string of entity or qualifier in keywords list using simple "in list"            
            match_rows = df[search_in_column_names].apply(lambda x: x.str.lower().isin([kw.lower() for kw in keywords])).any(axis=1)
            df.loc[match_rows, category_column_name] = category_label
            print(f'Assigned the "{category_label}" facet to {match_rows.sum()} rows based on full match with given keywords')

        elif match_strategy == "contains":        
            # Init negative keywords with user-defined list.
            negative_keywords = negative_keywords_dict.get(category_label, [])
            
            # Pattern should match keywords but only if they are not preced by non, not, or un.
            for keyword in keywords:
                negative_keywords.extend([f"non {keyword}", f"non-{keyword}", f"non{keyword}", f"not {keyword}", f"not-{keyword}", f"un{keyword}", f"un-{keyword}"])

            # Add keywords from other classes in same facet as negative keywords.
            if mutual_exclusive:
                for v, k in keywords_dict.items():
                    if v != category_label:
                        for nkw in k:
                            if any(nkw in kw for kw in keywords):
                                # Do not allow substrings of positive keywords to be negative keywords.
                                # E.g. not "male" as negative and "female" as positive.
                                continue
                            else:
                                negative_keywords.append(nkw)
        
            # Use negative pattern to exclude rows and positive pattern to include rows.
            negative_pattern = "|".join([re.escape(keyword) for keyword in negative_keywords])
            positive_pattern = "|".join([r"\b" + re.escape(keyword) for keyword in keywords])

            # Use contains to match substrings.            
            exclude_rows = df[search_in_column_names].apply(lambda x: x.str.contains(negative_pattern, na=False, case=False)).any(axis=1)
            match_rows = df[search_in_column_names].apply(lambda x: x.str.contains(positive_pattern, na=False, case=False)).any(axis=1)        

            df.loc[match_rows & ~exclude_rows, category_column_name] = category_label
        else:
            raise ValueError(f"Unknown match strategy '{match_strategy}'. Use 'contains' or 'fullmatch'.")

    if match_strategy == "contains":
        # Remove leading and trailing whitespace from the search columns.
        for search_column in search_in_column_names:
            df[search_column] = df[search_column].apply(lambda x: x.strip() if isinstance(x, str) else x)

    return df


def extract_qclaims_within_columns(df, columns_to_search_in=["entity", "qualifier"], quinex_api_endpoint="http://127.0.0.1:5555/api/text/annotate?skip_imprecise_quantities=true"):
    """
    Extract quantitative claims from the given columns of a dataframe using the Quinex API.
    """    
    # Initialize columns for storing qclaims.
    for search_column in columns_to_search_in:
        df[f"qclaims_in_{search_column}"] = None  

    for index, row in tqdm(df.iterrows()):        
        for search_column in columns_to_search_in:
            # Search for age in the format "30", "30 years", "30-year-old", etc.            
            text = row[search_column].strip()
            if not contains_any_number(text):
                # Save resources and skip if no number is present.
                continue
            else:
                # Extract quantitative claims using the Quinex API.
                print(f"Search for age in '{text}'")
                # TODO: Batching requests would be much more efficient.
                response = requests.post(quinex_api_endpoint, json=text)
                if response.status_code == 200:
                    qclaims = response.json()["predictions"]["quantitative_statements"]
                    
                    # Reduce quantitative claims into simple <property, value, unit> triples.
                    if len(qclaims) > 0:                                                
                        property_value_unit_pairs  = []
                        for qclaim in qclaims:

                            # Format returned by API endpoint is slightly different, align format.
                            normalized_quantity = qclaim["claim"]["quantity"]["normalized"]
                            normalized_quantity["normalized_quantities"] = normalized_quantity["individual_quantities"]["normalized"]
                            del normalized_quantity["individual_quantities"]
                            
                            if len(normalized_quantity["normalized_quantities"] ) == 0:
                                # Skip as quantity could not be normalized
                                # and we want to reduce complexity.
                                continue
                            elif len(normalized_quantity["normalized_quantities"] ) == 1:
                                quantity = normalized_quantity["normalized_quantities"][0]
                            elif len(normalized_quantity["normalized_quantities"] ) > 1:
                                quantity_list, temp_scope = get_single_quantities_from_normalized_quantity(normalized_quantity, temporal_scope="", split_interval_if_individual_temporal_scopes_given=False)
                                if len(quantity_list) == 1:
                                    quantity = quantity_list[0]["normalized_quantities"][0]
                                else:
                                    # Skip this claim as it has multiple quantities 
                                    # and we want to reduce complexity.
                                    continue

                            property_value_unit_pairs.append({
                                "property_str": qclaim["claim"]["property"]["text"],
                                "value": quantity["value"]["normalized"]["numeric_value"],
                                "unit": quantity["unit"]["normalized"],
                                "unit_str": " ".join([u for u in quantity["unit"]["text"].values() if u not in ["", None]]),
                            })

                        df.at[index, f"qclaims_in_{search_column}"] = property_value_unit_pairs

    return df