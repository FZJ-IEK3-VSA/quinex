import re
import time
import json
import requests
from copy import deepcopy
from datetime import datetime
import numpy as np               
from scipy.optimize import curve_fit
import pandas as pd
from tqdm import tqdm
import plotly.express as px
import plotly.graph_objects as go

from quinex_utils.functions.boolean_checks import contains_any_number
from quinex_utils.parsers.quantity_parser import FastSymbolicQuantityParser, FastSymbolicUnitParser
from quinex.normalize.spatial_scope.llm_geoguessing import get_geo_coordinates_from_spatial_scope

from quinex.analyze.create_plots.helpers.utils import load_application_results, condense_quantity_format
from quinex.analyze.create_plots.helpers.filter import filter_based_on_characteristic_keywords, only_absolute_quantities, only_keep_successfully_normalized_quantities, filter_rows_with_value_outside_expected_bounds
from quinex.normalize.quantity.units import transform_to_uniform_unit
from quinex.normalize.quantity.value import get_single_quantities_from_normalized_quantity
from quinex.analyze.create_plots.helpers.normalize import transform_intervals_etc_to_single_value
from quinex.normalize.temporal_scope.year import get_int_year_from_temporal_scope
from quinex.analyze.create_plots.helpers.group import extract_qclaims_within_columns, add_category_based_on_keywords



def get_single_numeric_value_for_each_quantity(
        df_filtered, 
        expected_bounds,
        if_outside_expected_bounds_ask_instead_of_remove,
        facets_for_which_bounds_are_not_valid,
        consider_intervals_by_averaging,
        consider_lists_by_taking_individual_values,
        consider_ratios_by_calculating_fraction,
        take_first_value_if_interval_with_different_units,
        redo_quantity_normalization=False,
        answer_cache_path="answer_cache.json",
    ):

    # Normalize quantity strings.
    if redo_quantity_normalization:
        print("\n>>>>>>>>>>>>>>> Normalizing quantities")
        df_filtered["normalized_quantity"] = None # reset
        quantity_parser = FastSymbolicQuantityParser()
        for index, row in tqdm(df_filtered.iterrows()):
            df_filtered.at[index, "normalized_quantity"] = quantity_parser.parse(row["quantity"])

    # Filter out rows with unsuccessfully normalized quantities.
    df_quantity_parsing_failed = df_filtered[df_filtered["normalized_quantity"].apply(lambda x: x is None or not x["success"] or len(x["normalized_quantities"]) == 0)]
    print(f"\n>>>>>>>>>>>>>>> {len(df_quantity_parsing_failed)} rows for which quantity normalization failed")
    df_filtered = df_filtered[~df_filtered.index.isin(df_quantity_parsing_failed.index)]        

    # Filter out rows with values that are outside the expected bounds.
    df_filtered, df_outside_expected_bounds, ANSWER_CACHE = filter_rows_with_value_outside_expected_bounds(df_filtered, expected_bounds, facets_for_which_bounds_are_not_valid, if_outside_expected_bounds_ask_instead_of_remove, answer_cache_path)
    print(f"\n>>>>>>>>>>>>>>> {len(df_outside_expected_bounds)} rows for which quantity values are outside expected bounds " \
        f"of which {len(ANSWER_CACHE['drop_row_indices'])} were dropped")

    # Transform intervals, lists, and multidimensional quantities into single quantities.
    split_interval_if_individual_temporal_scopes_given = True
    row_count_before_transformation = len(df_filtered)
    df_filtered = transform_intervals_etc_to_single_value(
        df_filtered,     
        consider_intervals=consider_intervals_by_averaging, 
        consider_lists=consider_lists_by_taking_individual_values, 
        consider_ratios=consider_ratios_by_calculating_fraction,
        consider_multidimensional=False,  # Not implemented yet.
        take_first_value_if_interval_with_different_units=take_first_value_if_interval_with_different_units,
        split_interval_if_individual_temporal_scopes_given=split_interval_if_individual_temporal_scopes_given
    )
    row_count_after_transformation = len(df_filtered)
    print(f"\n>>>>>>>>>>>>>>> During transformation into single quantities {row_count_after_transformation - row_count_before_transformation} rows were added")

    # Filter out rows with more than a single normalized quantity.
    df_filtered = df_filtered[df_filtered["normalized_quantity"].apply(lambda x: len(x["normalized_quantities"]) == 1)]
    print(f"\n>>>>>>>>>>>>>>> {row_count_after_transformation - len(df_filtered)} rows could not be transformed into single quantities and have been dropped")

    return df_filtered


def get_ages_and_population_size_from_columns(df_filtered, entity_search_columns=["entity", "qualifier"]):    
    df_filtered = extract_qclaims_within_columns(df_filtered, columns_to_search_in=entity_search_columns)
    
    # Get top property_str values in entity and qualifier columns.
    top_property_values_in_entity_column = df_filtered["qclaims_in_entity"].apply(lambda x: [qclaim["property_str"].lower() for qclaim in x if isinstance(x, list)] if isinstance(x, list) else []).explode().value_counts()
    top_property_values_in_qualifier_column = df_filtered["qclaims_in_qualifier"].apply(lambda x: [qclaim["property_str"].lower() for qclaim in x if isinstance(x, list)] if isinstance(x, list) else []).explode().value_counts()
    top_property_values_in_entity_and_qualifier_columns = (top_property_values_in_entity_column + top_property_values_in_qualifier_column).sort_values(ascending=False) 
            
    # Tip: Check candidates for creating the keyword lists.
    # age_keyword_candidates = [key for key in top_property_values_in_entity_and_qualifier_columns.keys() if " age" in " " + key]
    # population_size_keyword_candidates = [key for key in top_property_values_in_entity_and_qualifier_columns.keys() if " age" in " " + key]
    
    # Set keywords.
    concepts_to_detect = {
        "age": {
            "fullmatch_keywords": ['age', 'mean age', 'ages', 'mean sd age', 'age [mean sd]', 'mean age sd', 'median age', 'age range'],
            "substring_keywords": []
        },
        "population_size": {
            "fullmatch_keywords": ['n'],
            "substring_keywords": [' number of ']
        }
    }
    for concept, keywords in concepts_to_detect.items():
        df_filtered[concept] = None
        for index, row in df_filtered.iterrows():
            qclaims_in_entity_and_qualifier = []
            if row["qclaims_in_entity"] != None:    
                qclaims_in_entity_and_qualifier += row["qclaims_in_entity"]
            if row["qclaims_in_qualifier"] != None:
                qclaims_in_entity_and_qualifier += row["qclaims_in_qualifier"]
            
            if len(qclaims_in_entity_and_qualifier) > 0:
                concept_match_candidates = []
                for qclaim in qclaims_in_entity_and_qualifier:                
                    if any(keyword == qclaim["property_str"].lower() for keyword in keywords["fullmatch_keywords"]) \
                        or any(keyword in f" {qclaim['property_str'].lower()} " for keyword in keywords["substring_keywords"]):
                        concept_match_candidates.append(qclaim["value"])
                
                # Only add concept match if there are no contradicting values,
                # which we assume if there is more than one candidate.
                if len(concept_match_candidates) == 1:
                    df_filtered.at[index, concept] = concept_match_candidates[0]

    # Defined age bins.
    age_bounds = (0, 125)  # Realistic bounds for age.
    age_bins = {
        "CHILDREN": (0, 12),
        "ADOLESCENTS": (13, 19),
        "YOUNG_ADULTS": (20, 35),
        "MIDDLE_AGED": (36, 55),
        "ELDERLY": (56, 100)
    }
    
    # Assign age groups based on age.
    for index, row in df_filtered.iterrows():        
        if (row["age"] != None) and (age_bounds[0] <= row["age"] <= age_bounds[1]):
            for age_group, (age_lb, age_ub) in age_bins.items():
                if age_lb <= row["age"] <= age_ub:
                    # Check if age group is already assigned.
                    if row["age_group"] != None:
                        if row["age_group"] == age_group:
                            # Double evidence! Nothing to do.
                            pass
                        else:
                            # Conflict! We have to decide which age group to keep.
                            # In this case, we keep the first one we encounter.
                            print(f"Warning: Conflict in row {index}: age {row['age']} is assigned to {row['age_group']} based on keywords but detected year suggests {age_group}. Overwrite age group with the latter.")
                            df_filtered.at[index, "age_group"] = age_group
                    else:
                        # Assign age group.
                        print(f"Assigning age group '{age_group}' to row {index} with age {row['age']}")
                        df_filtered.at[index, "age_group"] = age_group
                    break

        # Assign population size as int.
        if row["population_size"] is not None:
            try:
                df_filtered.at[index, "population_size"] = int(row["population_size"])
            except ValueError:
                df_filtered.at[index, "population_size"] = None

    return df_filtered


def prepare_data_for_plot(
    df,        
    preferred_property_label,
    expected_bounds,        
    require_non_empty_value_for_columns,
    keywords_quantity_must_include,
    keywords_property_must_include,
    if_outside_expected_bounds_ask_instead_of_remove=True,
    bin_entities=False,
    facets_for_which_bounds_are_not_valid=[],
    search_for_entity_keywords_in_qualifier=False,
    ENTIY_FACET_KEYWORDS={},
    ENTIY_FACET_KEYWORDS_MATCH_STRATEGY={},
    detect_ages_and_population_size_in_entity_and_qualifier_column=False,
    redo_quantity_normalization=True,
    consider_intervals_by_averaging=True,
    consider_lists_by_taking_individual_values=True,
    consider_ratios_by_calculating_fraction=True,
    take_first_value_if_interval_with_different_units=True,
    perform_unit_conversion=False,
    convert_to=[],
    normalize_spatial_scope_to_geo_coordinates=False,
    drop_rows_without_longitude_and_latitude=True,
    required_number_of_model_guesses_for_geolocation=2,
    predicted_geo_coordinates_cache_path="cached_predicted_geo_coordinates.json",
    normalize_temporal_scope_to_year=True,
    year_normalization_bounds=(1800, 2100), # 4-digit numbers outside this range are not considered years
    temporal_scope_range_considered=None, # (lb, ub) only keep data with temporal scope in this range.
    answer_cache_path="answer_cache.json"
):
    row_count = len(df)    
    print(f"\n\n>>>>>>>>>>>>>>> Starting with {row_count} rows")    
    FACETS = list(ENTIY_FACET_KEYWORDS.keys())

    # Show all rows containing the string "horse" if value is str
    # with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.max_colwidth', None):
    #     print(df[df.apply(lambda row: any("horse" in str(value) for value in row if isinstance(value, str)), axis=1)])

    # ==============================================================
    # =     Drop rows with empty string for a required column      =
    # ==============================================================        
    if len(require_non_empty_value_for_columns) > 0:
        df_filtered = df[df[require_non_empty_value_for_columns].apply(lambda x: x.str.strip() != "", axis=1).all(axis=1)]
        
        # Message.
        new_row_count = len(df_filtered)        
        print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows with an empty string in a required column")
        row_count = new_row_count

    # ==============================================================
    # =                     Filter quantities                      =
    # ==============================================================
    df_filtered = filter_based_on_characteristic_keywords(df_filtered, keywords_quantity_must_include, "quantity")
    
    # Message.
    new_row_count = len(df_filtered)
    print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows with a quantity that does not contain the required keywords")
    row_count = new_row_count

    df_filtered = only_absolute_quantities(df_filtered)

    # ==============================================================
    # =                     Filter properties                      =
    # ==============================================================
    df_filtered = filter_based_on_characteristic_keywords(df_filtered, keywords_property_must_include, "property")
    # Message.
    new_row_count = len(df_filtered)
    print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows with a property that does not contain the required keywords")
    row_count = new_row_count
    print(f">>>>>>>>>>>>>>> Found {len(df_filtered)} quantitative claims with {preferred_property_label} property")

    # ==============================================================
    # =                   Sort data into facets                    =
    # ==============================================================
    if bin_entities:
        entity_search_columns = ["entity", "qualifier"] if search_for_entity_keywords_in_qualifier else ["entity"]  
        for facet_name, keywords in ENTIY_FACET_KEYWORDS.items():
            df_filtered = add_category_based_on_keywords(df_filtered, entity_search_columns, facet_name, keywords, match_strategy=ENTIY_FACET_KEYWORDS_MATCH_STRATEGY[facet_name]["match"], mutual_exclusive=ENTIY_FACET_KEYWORDS_MATCH_STRATEGY[facet_name]["mutual_exclusive"])

            print(f">>>>>>>>>>>>>>> Added facet '{facet_name}' and assigned {df_filtered[facet_name].notnull().sum()} rows to it")

            # Debug-tip: Print rows with specific facet type.
            # with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.max_colwidth', None):
            #     print(df_filtered[df_filtered["animal"].notnull()][["entity", "qualifier", "quantity"]])
            
            # Debug-tip: Print rows with specific facet.            
            # with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.max_colwidth', None):
            #     print(df_filtered[df_filtered["health"] == "HEART"][["entity", "qualifier", "quantity"]])

        # Extract quantitative statements within entity and qualifier column.
        if detect_ages_and_population_size_in_entity_and_qualifier_column: 
            df_filtered = get_ages_and_population_size_from_columns(df_filtered, entity_search_columns)

        # Add column with all assigned subfacets as a list.
        df_filtered["assigned_subfacets"] = None
        for index, row in df_filtered.iterrows():        
            all_assigned_types = []
            for facet in FACETS:  
                if row[facet] != None:
                    all_assigned_types.append(row[facet])
            
            df_filtered.at[index, "assigned_subfacets"] = all_assigned_types

    # ==============================================================
    # =                    Normalize quantities                    =
    # ==============================================================
    df_filtered = get_single_numeric_value_for_each_quantity(
        df_filtered, 
        expected_bounds,
        if_outside_expected_bounds_ask_instead_of_remove,
        facets_for_which_bounds_are_not_valid,
        consider_intervals_by_averaging,
        consider_lists_by_taking_individual_values,
        consider_ratios_by_calculating_fraction,
        take_first_value_if_interval_with_different_units,
        redo_quantity_normalization=redo_quantity_normalization,
        answer_cache_path=answer_cache_path
    )


    # ==============================================================
    # =                      Unit conversion                       =
    # ==============================================================
    if perform_unit_conversion:                
        unit_parser = FastSymbolicUnitParser()
        start = time.time()
        rows_for_which_unit_conversion_failed = []
        for i, (index, row) in enumerate(tqdm(df_filtered.iterrows())):

            # Print elapsed time.
            if i % 100 == 0:
                print(f"Processing {i} of {len(df_filtered)}")
                print(f"Elapsed time: {time.time() - start}")
            
            # Assume only single quantities given.            
            nqs = row["normalized_quantity"]["normalized_quantities"]
            assert len(nqs) == 1, f"Expected exactly one normalized quantity, but got {len(nqs)}"
            nq = nqs[0]

            # Get input value.
            from_value = nq["value"]["normalized"]["numeric_value"]
            
            # Get input unit.
            from_unit = []
            if nq["prefixed_unit"] != None and nq["prefixed_unit"]["normalized"] != None:
                from_unit += nq["prefixed_unit"]["normalized"]
            if nq["suffixed_unit"] != None and nq["suffixed_unit"]["normalized"] != None:
                from_unit += nq["suffixed_unit"]["normalized"]                

            # Get fallback input year for inflation adjustment in case the currency was not given with a year
            # Assumption: year the value is given in is the publication year or last year if
            # the publication year is the current or a future year, because annual averages 
            # for inflation adjustion can only be calculated for past years.
            last_year = datetime.now().year - 1 # TODO: Make this a setting!
            from_year = min(last_year, row["pub_year"])

            # If currency in to_unit, it has to be given with a year for inflation adjustment.
            to_year = None
            for to_unit in convert_to:
                unit_uri = to_unit[2]
                unit_year = to_unit[3]
                if unit_uri.split("/")[4] == "currency" or unit_uri.split("/")[5].startswith("CCY_"):
                    if unit_year == None:
                        raise ValueError(f"For currencies in the compound unit the data should be converted to a year must be given for inflation adjustment.")
                    elif to_year == None:
                        to_year = unit_year
                    elif to_year != unit_year:
                        raise ValueError(f"The year must be the same for all currencies in the compound unit the data should be converted to, but got {to_year} and {unit_year}.")
                    else:
                        pass

            # Adjust for common error $/MW h is parsed as $.MW-1.h instead of $.MW-1.h-1
            if from_unit != None and len(from_unit) == 3 and "kg" not in [u[0] for u in from_unit]:
                from_uri_splits = from_unit[0][2].split("/")
                if len(from_uri_splits) == 6:
                    first_unit_is_currency = from_uri_splits[4] == "currency" or from_uri_splits[5].startswith("CCY_")                
                    if first_unit_is_currency and from_unit[-1][1] == 1 and from_unit[-1][2] == 'http://qudt.org/vocab/unit/HR' and from_unit[-2][0][-1].lower() == "w" and from_unit[-2][1] == -1:
                        new_unit_str = from_unit[-2][0] + " " + from_unit[-1][0]
                        if from_unit[-2][2] == 'http://qudt.org/vocab/unit/KiloW':
                            combined_qudt_uri = 'http://qudt.org/vocab/unit/KiloW-HR'
                        elif from_unit[-2][2] == 'http://qudt.org/vocab/unit/MegaW':
                            combined_qudt_uri = 'http://qudt.org/vocab/unit/MegaW-HR'
                        else:
                            raise ValueError(f"Could not adjust for common parsing error in row {index}.")

                        from_unit[-2] = (new_unit_str, -1, combined_qudt_uri, None)
                        from_unit = from_unit[:-1]
                        print(f"Warning: Adjusted for common parsing error in row {index}.")                    

            try:
                known_fails = ['http://qudt.org/vocab/unit/CCY_MYR'] # TODO: fix
                if any(u[2] in known_fails for u in from_unit):
                    raise ValueError(f"Known currency conversion error for unit {from_unit}.")
                conv_value, conv_unit = unit_parser.unit_conversion(
                    value=from_value,
                    from_compound_unit=from_unit,
                    to_compound_unit=convert_to,
                    from_default_year=from_year,
                    to_default_year=to_year,                    
                    verbose=False,
                )
            except Exception as e:
                print(f"Error: {e}")
                conv_value, conv_unit = None, None
                
            if conv_value == None:
                rows_for_which_unit_conversion_failed.append(index)
            else:                
                # Update the normalized quantity with the converted value and unit.
                row["normalized_quantity"]["converted"] = {"value": conv_value, "unit": conv_unit}

    # Remove rows for which unit conversion failed.
    row_count = len(df_filtered)
    df_filtered = df_filtered[~df_filtered.index.isin(rows_for_which_unit_conversion_failed)]

    # Message.
    new_row_count = len(df_filtered)
    print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows which could not be converted to the target unit")
    row_count = new_row_count

    # Analyze errors.
    for error_type, error_list in unit_parser.ERROR_LOG.items():
        print(f"\n>>>>>>>>>>>>>>> {len(error_list)} errors of type '{error_type}'")

        # Count occurence of unique errors using collections
        error_list = [str(e) for e in error_list]        
        unique_errors = set(error_list)
        error_counts = {str(error): list(error_list).count(error) for error in unique_errors}
        print(f"Unique errors: {len(unique_errors)}")
        for error, count in error_counts.items():
            print(f"- Error: {error}, Count: {count}")

    # ==============================================================
    # =                  Simplify representation                   =
    # ==============================================================
    for index, row in df_filtered.iterrows(): 
        # Add value as single numeric value.
        if perform_unit_conversion:
            df_filtered.at[index, "value"] = row["normalized_quantity"]["converted"]["value"]
        else:
            row_nqs = row["normalized_quantity"]["normalized_quantities"]
            assert len(row_nqs) == 1, f"Expected exactly one normalized quantity, but got {len(row_nqs)}"            
            df_filtered.at[index, "value"] = row_nqs[0]["value"]["normalized"]["numeric_value"]

    # ==============================================================
    # =                  Normalize temporal scope                  =
    # ==============================================================
    if normalize_temporal_scope_to_year:
        df_filtered["temporal_scope_as_int_year"] = None
        df_filtered["temporal_scope_as_int_year_assumed_from_pub_year"] = None        
        for index, row in df_filtered.iterrows():          
            # Get the temporal scope as int year.            
            temporal_scope_as_int_year, year_assumed_from_pub_year = get_int_year_from_temporal_scope(
                temporal_scope_span=row["temporal_scope"],
                publication_year=row["pub_year"],
                allowed_year_lb=year_normalization_bounds[0],
                allowed_year_ub=year_normalization_bounds[1]
            )
            df_filtered.at[index, "temporal_scope_as_int_year"] = temporal_scope_as_int_year
            df_filtered.at[index, "temporal_scope_as_int_year_assumed_from_pub_year"] = year_assumed_from_pub_year
            
        print(f"\n>>>>>>>>>>>>>>> Frequency of years in temporal scope:")
        print(df_filtered["temporal_scope_as_int_year"].value_counts().sort_index())

        if temporal_scope_range_considered != None:
            row_count = len(df_filtered)
            df_filtered = df_filtered[df_filtered["temporal_scope_as_int_year"].between(temporal_scope_range_considered[0], temporal_scope_range_considered[1])]
            new_row_count = len(df_filtered)
            print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows with a temporal scope outside the considered range of {temporal_scope_range_considered[0]} to {temporal_scope_range_considered[1]}")

    # ==============================================================
    # =                  Geolocate spatial scope                   =
    # ==============================================================
    model_ids = ['2 - Qwen3-30B-A3B-Instruct-2507 - a reasoning model from Alibaba from July 2025']
    nbr_runs_per_model = 2
    selected_models = model_ids[0:required_number_of_model_guesses_for_geolocation]
    if normalize_spatial_scope_to_geo_coordinates:
        df_filtered = get_geo_coordinates_from_spatial_scope(
            df_filtered,            
            blablador_llm_ids=selected_models,
            nbr_runs_per_model=nbr_runs_per_model,
            dist_deviation_threshold_in_km=300,
            predicted_geo_coordinates_cache_path=predicted_geo_coordinates_cache_path,
        )
    
    if drop_rows_without_longitude_and_latitude:
        # Drop rows without longitude and latitude.
        print(f">>>>>>>>>>>>>>> Dropping rows without longitude and latitude")
        row_count = len(df_filtered)
        df_filtered = df_filtered.dropna(subset=['latitude', 'longitude', 'value'])        
        print(f">>>>>>>>>>>>>>> Dropped {row_count - len(df_filtered)} rows without longitude and latitude")
        

    return df_filtered


def create_violin_plot(
    df_filtered,    
    preferred_property_label,
    preferred_unit_label,
    x_range=[10, 175],
    min_sample_size=3,
    add_sample_size_to_subfacet_label=True,
    remove_outliers_bounds=None,  
    sort_by_max_instead_of_mean=False,  
    facets=[],
    drop_facet_values=[],
    facets_for_which_other_facets_are_not_considered=[],    
):

    # Only keep rows with value in bounds.
    if remove_outliers_bounds != None:
        df_filtered = df_filtered[df_filtered["value"].between(remove_outliers_bounds[0], remove_outliers_bounds[1])]

    # For rows with animal not None, set all other facet values to None
    for solo_facet in facets_for_which_other_facets_are_not_considered:
        for facet in facets:
            if facet == solo_facet:
                continue
            df_filtered.loc[df_filtered[solo_facet].notna(), facet] = None

    # Unpivot the DataFrame from wide to long format.
    variables = ["value", "entity", "qualifier", "pub_year", "doi"]    
    hover_data = ["entity", "qualifier", "pub_year", "doi"]

    # Add extra data to variables and hover_data if available.
    for extra_data_extracted in ["age", "population_size"]:
        if extra_data_extracted in df_filtered.columns:
            variables.append(extra_data_extracted)
            hover_data.append(extra_data_extracted)

    melted = df_filtered.melt(id_vars=variables, value_vars=facets, var_name="facet_type", value_name="facet_value", ignore_index=False)

    # Drop rows where facet_value is None
    melted = melted.dropna(subset=["facet_value"])

    # Drop facets with less than `min_sample_size`.
    melted = melted.groupby("facet_value").filter(lambda x: len(x) >= min_sample_size)

    # Drop rows of certain subfacets.
    melted = melted[~melted["facet_value"].isin(drop_facet_values)]

    # TODO: Create function to add sample size to facet labels and re-use from create_scatter_plot_with_trendlines()
    # Add the sample size n of each facet value in parantheses to the facet_value
    if add_sample_size_to_subfacet_label:    
        melted["facet_value"] = melted["facet_value"] + " (n=" + melted.groupby("facet_value")["value"].transform("count").astype(str) + ")"
    
    # Make facet value and type capitalized and replace underscores with spaces.
    melted["facet_value"] = melted["facet_value"].str.replace("_", " ").str.capitalize()
    melted["facet_type"] = melted["facet_type"].str.replace("_", " ").str.capitalize()  

    # Sort facet types by highest mean value of facet_values and then sort facet values by mean value.
    df_sort = melted.groupby(["facet_type", "facet_value"])
    if sort_by_max_instead_of_mean:
        df_sort = df_sort["value"].max().reset_index()  
    else:
        df_sort = df_sort["value"].mean().reset_index()

    df_sort["facet_type_mean"] = df_sort.groupby("facet_type")["value"].transform("mean")
    df_sort = df_sort.sort_values(by=["facet_type_mean", "value"], ascending=[False, False])
    ordered_facet_values = df_sort["facet_value"].tolist()
    ordered_facet_types = df_sort["facet_type"].unique().tolist()

    # Sort melted by facet_value to ensure that legend is ordered correctly.
    melted = melted.sort_values(by=["facet_value"], key=lambda x: pd.Categorical(x, categories=ordered_facet_values, ordered=True))
    
    # How many unique indices are in the filtered data?
    print_df_size(melted)

    # See https://plotly.com/python/discrete-color/ for discrete color palettes.
    facet_colors = px.colors.qualitative.Plotly[0:len(ordered_facet_types)] 
    facet_colors[7] = px.colors.qualitative.D3[7] # 7th color is not very visible, so we replace it

    # Create violin plot.
    fig = px.violin(
        melted,
        x="value",
        y="facet_value",
        color="facet_type",
        title=f"{preferred_property_label} by Facet",
        points="all",
        violinmode="overlay",
        labels={"value": preferred_property_label, "facet_value": "Facet", "facet_type": "Facet Type"},
        category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
        hover_data=hover_data,
        color_discrete_sequence=facet_colors, 
    )
    fig.update_xaxes(range=x_range)
    fig.update_xaxes(title_text=f"{preferred_property_label} ({preferred_unit_label})")
    fig.update_yaxes(title_text="Facet")
    fig.update_xaxes(dtick=10)
    fig.update_traces(marker_size=3)
    fig.update_layout(scattermode="group")
    height_per_facet = 1.0
    fig.update_traces(width=height_per_facet, side='positive', meanline_visible=True, box_visible=False, scalemode="width", pointpos=-0.45, jitter=0.25)
    
    # When setting side='positive', excessive space is added to the top and bottom of the plot.
    # TODO: Fix bug or remove space over top facet and below bottom facet.

    return fig

def create_boxplot(
    df_filtered,    
    preferred_property_label,
    preferred_unit_label,
    x_range=[10, 175],
    min_sample_size=3,
    add_sample_size_to_subfacet_label=True,
    remove_outliers_bounds=None,  
    sort_by_max_instead_of_mean=False,  
    facets=[],
):
    
    ref_paper_material_order = ['MAPI', 'MAPB',  'FAPI', 'CsPbI3', 'CsPbBr3'] 

    # Plot and make eacht material a different color.    
    fig = px.box(df_filtered, y="value", x="material", points="all", category_orders={"material": ref_paper_material_order}, 
                 title=f"{preferred_property_label} by Material",
                 labels={"value": preferred_property_label, "material": "Material"},
                 color="material", 
                 color_discrete_sequence=px.colors.qualitative.Plotly[0:len(ref_paper_material_order)],
                 hover_data=["entity", "qualifier", "pub_year", "doi"])
    fig.update_yaxes(range=[1.3, 3])
    fig.update_yaxes(title_text=f"{preferred_property_label.capitalize()} ({preferred_unit_label})")
    fig.update_xaxes(title_text="Material")
    fig.update_yaxes(dtick=0.1)
    fig.update_traces(marker_size=10)
    fig.update_layout(scattermode="group")

    # Calculate mode value of all values for each material.
    all_values_per_material = df_filtered.groupby("material")["value"].apply(list).reset_index()
    all_values_per_material["mode"] = all_values_per_material["value"].apply(lambda x: pd.Series(x).mode().iloc[0])

    # Add mode values to figure.
    for index, row in all_values_per_material.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["material"]], 
            y=[row["mode"]], 
            mode='markers+text', 
            marker=dict(symbol='star-dot', size=12, color='lightgray', line=dict(color='black', width=1)), 
            text=[f"Mode: {row['mode']:.2f}"],
            textposition='top center',
            name=f"Mode: {row['material']}"
        ))

    # Add reference mode values to figure.
    ref_mode_values = {"MAPI": 1.55, "MAPB": 2.30, "FAPI": 1.48, "CsPbI3": 1.73, "CsPbBr3": 2.30}
    for material, ref_value in ref_mode_values.items():
        fig.add_trace(go.Scatter(
            x=[material],
            y=[ref_value],
            mode='markers+text',
            marker=dict(symbol='hexagram-dot', size=12, color='yellow', line=dict(color='black', width=1)),
            text=[f"Ref. mode: {ref_value:.2f}"],
            textposition='top center',
            name=f"Ref: {material}"
        ))

    return fig


def cut_data_per_facet_value_at_year_with_less_than_n_data_points_remaining(melted, year_column="temporal_scope_as_int_year", n=10):
    """
    Cut the data per facet value at the last year where there are at least n data points remaining for the given facet value.    
    """
    melted_end_cut = melted.copy()
    # Sort by temporal_scope_as_int_year.
    melted_end_cut = melted_end_cut.sort_values(by=year_column)
    
    # Get the last year for each technology where there are at least 10 data points in total for the given technology over the remaining years.
    cut_at_year = {}
    for facet_value in melted_end_cut["facet_value"].unique():
        
        # Get the data for the current facet value.
        df_facet = melted_end_cut[melted_end_cut["facet_value"] == facet_value]
        
        # Get the last year where there are at least 10 data points in total for the given technology over the remaining years.
        last_year = df_facet[year_column].max()
        for year in reversed(df_facet[year_column].unique()):
            if len(df_facet[df_facet[year_column] >= year]) >= n:
                last_year = year
                break
        
        cut_at_year[facet_value] = last_year

    # Cut the data for each facet to only include data up to the facet's last year.
    melted_end_cut = melted_end_cut[melted_end_cut.apply(lambda row: row[year_column] <= cut_at_year.get(row["facet_value"], row[year_column]), axis=1)]
        
    return melted_end_cut


def trendline_exp_decay(melted, facet_col, year_col, value_col, color_mapping, force_positive=False, plot_scatter=False):
    """
    Fit an exponential decay trendline to the data and plot it.
    """
    # Define the exponential decay function
    def exp_decay(x, a, b, c):
        return a * np.exp(-b * x) + c
            
    fig = go.Figure()
    for tech_class in melted[facet_col].unique():
        # Fit the curve for each technology class
    
        # tech_class = 'Off-grid (n=145)'  # Change this to the technology class you want to fit the curve for
        df_tech = melted[melted[facet_col] == tech_class]
        
        # Since years might be large, normalize to start at 0 for stability
        x_data = df_tech[year_col] - df_tech[year_col].min()                
        y_data = df_tech[value_col]

        # Make yeas float.
        x_data = x_data.astype(float)

        # Fit the curve to all data points
        if force_positive:
            popt, pcov = curve_fit(exp_decay, x_data, y_data, bounds=([0, 0, 0], [np.inf, np.inf, np.inf]), maxfev=10000)
        else:
            popt, pcov = curve_fit(exp_decay, x_data, y_data, maxfev=10000)                

        # Generate x values for the fitted curve line
        x_fit = np.linspace(x_data.min(), x_data.max(), 100)
        y_fit = exp_decay(x_fit, *popt)
        
        if plot_scatter:
            # Scatter plot of original data (all points)
            fig.add_trace(go.Scatter(
                x=df_tech[year_col],
                y=df_tech[value_col],
                mode='markers',
                name='Data points',
                marker=dict(color=color_mapping[tech_class], size=6, opacity=0.6)
            ))

        # Line plot of fitted exponential curve
        fig.add_trace(go.Scatter(
            x=x_fit + df_tech[year_col].min(),
            y=y_fit,
            mode='lines',
            name=tech_class,
            hovertext= f"Fitted exp decay for {tech_class}",
            line=dict(color=color_mapping[tech_class], width=2)
        ))

    return fig


def print_df_size(df):        
    print(f">>>>>>>>>>>>>>> {df.index.nunique()} unique indices and {len(df)} rows in the filtered data")        
    print(f">>>>>>>>>>>>>>> {len(df[df.index.duplicated(keep='first')])} quantitative statements are duplicates. Probably because of non-mutually exclusive facet assignments or weighting.")


def create_scatter_plot_with_trendlines(
    df_filtered,
    preferred_property_label,
    preferred_unit_label,    
    min_sample_size=3,
    add_sample_size_to_subfacet_label=True,
    remove_outliers_bounds=None,  
    sort_by_max_instead_of_mean=False,  
    facets=[],
    drop_facet_values=[],
    facets_for_which_other_facets_are_not_considered=[],
    drop_where_year_assumed_from_pub_year=False,
    log_y=False,
    reference_data=None,
    keyword_color_mapping={}
):
    """
    Scatter plot with trendlines

     *
       *   
         *   
            *  
                *   *
    """    

    # -----------------------------------------------
    #                  Filter data                                
    # -----------------------------------------------
    # Only keep rows with value in bounds.
    if remove_outliers_bounds != None:
        row_count = len(df_filtered)
        df_filtered = df_filtered[df_filtered["value"].between(remove_outliers_bounds[0], remove_outliers_bounds[1])]
        new_row_count = len(df_filtered)
        print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows where value was outside the expected bounds {remove_outliers_bounds[0]} - {remove_outliers_bounds[1]}")
    
    # Only keep rows with known temporal scope.
    if drop_where_year_assumed_from_pub_year:
        row_count = len(df_filtered)
        df_filtered = df_filtered[df_filtered["temporal_scope_as_int_year_assumed_from_pub_year"] == False]        
        new_row_count = len(df_filtered)
        print(f">>>>>>>>>>>>>>> Dropped {row_count - new_row_count} rows where year was assumed from publication year")
      

    # -----------------------------------------------
    #              Add weighting factor              
    # -----------------------------------------------
    if add_weight_based_on_citation_count:=True:
        # Normalize citations to increase symbol size by citation count
        min_size = 1
        max_size = 1000
        df_filtered["citations_normalized_for_size"] = (df_filtered["citations"] - df_filtered["citations"].min()) / (df_filtered["citations"].max() - df_filtered["citations"].min()) * (max_size - min_size) + min_size
        print(df_filtered[["citations", "citations_normalized_for_size"]].sort_values(by="citations", ascending=False))

    if add_weight_based_on_known_year:=True:
        # Increase the weight for values where year_assumed_from_pub_year is False
        weight_factor_year_known = 5
        min_citation_weight_factor = 1
        max_citation_weight_factor = 5
        increase_weight_by_year_known = True
        increase_weight_by_citation_count = True
        df_filtered = add_weight(df_filtered, "citations", "temporal_scope_as_int_year_assumed_from_pub_year", weight_factor_year_known, min_citation_weight_factor, max_citation_weight_factor, increase_weight_by_year_known, increase_weight_by_citation_count)


    # -----------------------------------------------
    #             Unpivot the DataFrame             
    # -----------------------------------------------
    # For rows with animal not None, set all other facet values to None
    for solo_facet in facets_for_which_other_facets_are_not_considered:
        for facet in facets:
            if facet == solo_facet:
                continue
            df_filtered.loc[df_filtered[solo_facet].notna(), facet] = None

    variables = ["value", "entity", "qualifier",  "latitude", "longitude", "spatial_scope", "temporal_scope", "pub_year", "doi", "temporal_scope_as_int_year", "temporal_scope_as_int_year_assumed_from_pub_year"]
    hover_data = ["entity", "qualifier", "pub_year", "doi"]
    if add_weight_based_on_citation_count:
        variables.append("citations_normalized_for_size")

    # Add extra data to variables and hover_data if available.
    for extra_data_extracted in ["age", "population_size"]:
        if extra_data_extracted in df_filtered.columns:
            variables.append(extra_data_extracted)
            hover_data.append(extra_data_extracted)

    # Transform DataFrame to long format.
    melted = df_filtered.melt(id_vars=variables, value_vars=facets, var_name="facet_type", value_name="facet_value", ignore_index=False)

    # -----------------------------------------------
    #              Filter data further              
    # -----------------------------------------------
    melted = melted.dropna(subset=["facet_value"])  # Drop rows where facet_value is None
    melted = melted.groupby("facet_value").filter(lambda x: len(x) >= min_sample_size)  # Drop facets with less than `min_sample_size`.
    melted = melted[~melted["facet_value"].isin(drop_facet_values)]  # Drop rows of certain subfacets.

    # -----------------------------------------------
    #               Count data points               
    # -----------------------------------------------
    # How many unique indices are in the filtered data? (make sure ignore_index=False in melt above)
    print_df_size(melted)

    def add_sample_size_to_label(facet_value):            
        # Count unique indices for the given facet value.
        n = melted[melted["facet_value"] == facet_value].index.nunique()
        return f"{facet_value} (n={n})"

    facet_values = melted["facet_value"].unique().tolist()                        
    sample_size_per_facet_value = {k: add_sample_size_to_label(k) for k in facet_values}
    print(">>>>>>>>>>>>>>> Sample size per facet value:")
    print('- ' + '\n- '.join(sample_size_per_facet_value.values()))

    # -----------------------------------------------
    #                 Update labels                 
    # -----------------------------------------------
    # Add the sample size n of each facet value in parantheses to the facet_value
    if add_sample_size_to_subfacet_label:
        # Add sample size to facet_value of reference data.
        if reference_data is not None:
            reference_data["facet_value"] = reference_data["facet_value"].apply(add_sample_size_to_label)

        # Add sample size to facet_value.
        melted["facet_value"] = melted["facet_value"].apply(add_sample_size_to_label)
        facet_value_to_label_mapping = sample_size_per_facet_value
    else:
        facet_value_to_label_mapping = {k: k for k in facet_values}

    # Make facet value and type capitalized and replace underscores with spaces.
    melted["facet_value"] = melted["facet_value"].str.replace("_", " ").str.capitalize()
    melted["facet_type"] = melted["facet_type"].str.replace("_", " ").str.capitalize()

    # -----------------------------------------------
    #               Sort data for plot               
    # -----------------------------------------------
    # Sort facet types by highest mean value of facet_values and then sort facet values by mean value.
    df_sort = melted.groupby(["facet_type", "facet_value"])
    if sort_by_max_instead_of_mean:
        df_sort = df_sort["value"].max().reset_index()  
    else:
        df_sort = df_sort["value"].mean().reset_index()

    df_sort["facet_type_mean"] = df_sort.groupby("facet_type")["value"].transform("mean")
    df_sort = df_sort.sort_values(by=["facet_type_mean", "value"], ascending=[False, False])
    ordered_facet_values = df_sort["facet_value"].tolist()
    ordered_facet_types = df_sort["facet_type"].unique().tolist()

    # Sort melted by facet_value to ensure that legend is ordered correctly.
    melted = melted.sort_values(by=["facet_value"], key=lambda x: pd.Categorical(x, categories=ordered_facet_values, ordered=True))    

    # -----------------------------------------------
    #                 Color mapping                 
    # -----------------------------------------------
    # Create color mapping for facet values.
    color_mapping = {}
    ordered_facet_values.reverse()
    for i, facet_value in enumerate(ordered_facet_values):
        if len(keyword_color_mapping) != 0:
            for keyword, color in keyword_color_mapping.items():
                if facet_value.startswith(keyword):
                    color_mapping[facet_value] = color
                    break            
        else:
            color_mapping[facet_value] = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]    
 
    # -----------------------------------------------
    #               Plot scatter plot               
    # -----------------------------------------------    
    fig2 = px.scatter(
        melted,
        x="temporal_scope_as_int_year",
        y="value",
        color="facet_value",
        title=f"{preferred_property_label} in {preferred_unit_label} over Time",
        labels={"value": f"{preferred_property_label} ({preferred_unit_label})", "temporal_scope_as_int_year": "Year"},
        category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
        hover_data=hover_data,
        symbol_sequence=["circle-open", "circle"],
        symbol="temporal_scope_as_int_year_assumed_from_pub_year",
        symbol_map={True: "circle-open", False: "circle"},        
        size="citations_normalized_for_size" if add_weight_based_on_citation_count else None,
        size_max=10,        
        color_discrete_map=color_mapping
    )    

    # Change color of bubbles for "Off-grid" and "Grid-connected"
    for trace in fig2.data:
        if "Off-grid" in facet_value_to_label_mapping and trace.name in [facet_value_to_label_mapping.get("Off-grid") + ", True", facet_value_to_label_mapping.get("Off-grid") + ", False"]:
            trace.marker.color = "gray"
            trace.marker.line.width = 2
        elif "Grid-connected" in facet_value_to_label_mapping and trace.name in [facet_value_to_label_mapping.get("Grid-connected") + ", True", facet_value_to_label_mapping.get("Grid-connected") + ", False"]:
            trace.marker.color = "black"
            trace.marker.line.width = 2

    # Plot trendline
    exp_decay = True
    lowess = False
    rolling = False
    if exp_decay:        
        fig_trendlines = trendline_exp_decay(
            melted,
            facet_col="facet_value",
            year_col="temporal_scope_as_int_year",
            value_col="value",
            color_mapping=color_mapping,
            force_positive=True,
            plot_scatter=False
        )
    elif lowess:        
        fig_trendlines = px.scatter(melted,
            x="temporal_scope_as_int_year",
            y="value",
            color="facet_value",
            trendline="lowess",
            trendline_options=dict(frac=0.75),
            title="LCOE in USD/MWh over Time",
            labels={"value": "LCOE in USD/MWh", "temporal_scope_as_int_year": "Year"},
            category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
            hover_data=hover_data,
            color_discrete_map=color_mapping
        )
    elif rolling:
        fig_trendlines = px.scatter(
            melted,
            x="temporal_scope_as_int_year",
            y="value",
            color="facet_value",
            trendline="rolling",
            trendline_options=dict(window=5, win_type="gaussian", function_args=dict(std=2)),            
            title="LCOE in USD/MWh over Time",
            labels={"value": "LCOE in USD/MWh", "temporal_scope_as_int_year": "Year"},
            category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
            hover_data=hover_data,
            color_discrete_map=color_mapping
        )
    else:            
        fig_trendlines = px.scatter(
            melted,
            x="temporal_scope_as_int_year",
            y="value",
            color="facet_value",
            trendline="ols",
            trendline_options=dict(log_y=True),
            title="LCOE in USD/MWh over Time",
            labels={"value": "LCOE in USD/MWh", "temporal_scope_as_int_year": "Year"},
            category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
            hover_data=hover_data,
            color_discrete_map=color_mapping
        )

    fig_trendlines.data = [t for t in fig_trendlines.data if t.mode == "lines"]

    # Make lines for "Renewable", "Off-grid", "Grid-connected" black and dashed, dotted, etc. 
    different_trend_lines = ["Renewable", "Off-grid", "Grid-connected"]
    different_trend_lines = [facet_value_to_label_mapping.get(t) for t in different_trend_lines]
    for trace in fig_trendlines.data:
        if trace.name in different_trend_lines:                        
            if trace.name == facet_value_to_label_mapping.get("Off-grid"):
                trace.line.dash = "dash"
                trace.line.color = "gray"
            elif trace.name == facet_value_to_label_mapping.get("Grid-connected"):
                trace.line.dash = "dot"
                trace.line.color = "black"
            elif trace.name == facet_value_to_label_mapping.get("Renewable"):
                trace.line.dash = "dashdot"

    if reference_data is not None:
        fig_ref_data = px.scatter(
            reference_data, 
            x="year", 
            y="value", 
            color="facet_value", 
            title=f"LCOE in USD_2023/MWh over Time", 
            labels={"value": f"LCOE in USD_2023/MWh", "year": "Year"},
            category_orders={"facet_value": ordered_facet_values, "facet_type": ordered_facet_types},
            color_discrete_map=color_mapping
        )
        fig_ref_data.update_traces(marker=dict(size=20, symbol="hash-open-dot", line_width=2))

    # Merge the two figures.
    if reference_data is None:
        fig = go.Figure(data = fig_trendlines.data + fig2.data + fig_ref_data.data)
    else:
        fig = go.Figure(data = fig_trendlines.data + fig2.data)

    # Simplify the legend only showing the color per entity class but not the symbol or line
    fig.update_layout(title=f"LCOE in USD_2023/MWh over Time", xaxis_title="Year", yaxis_title=f"LCOE in USD_2023/MWh")
    fig.update_yaxes(range=[0, 500])
    fig.update_xaxes(range=[2008, 2050])
    if log_y:
        fig.update_yaxes(type='log')
        fig.update_yaxes(range=[1, 3])
    
    return fig, melted, color_mapping


def add_weight(df, citations_count_col, year_assumed_col, weight_factor_year_known, min_citation_weight_factor, max_citation_weight_factor, increase_weight_by_year_known=True, increase_weight_by_citation_count=True):
    """
    Calculate the weight for each row and duplicate it weight times.

    The weight increases for highly cited papers and if the year is known.
    The total weight is the sum of the citation weight and the year known weight.
    """
    df_weighted = df.copy()    
    if increase_weight_by_citation_count:
        # Normalize citations to min and max citation weight 
        df_weighted["weight_citations"] = (df_weighted[citations_count_col] - df_weighted[citations_count_col].min()) / (df_weighted[citations_count_col].max() - df_weighted[citations_count_col].min()) * (max_citation_weight_factor - min_citation_weight_factor) + min_citation_weight_factor
        df_weighted["weight_citations"] = df_weighted["weight_citations"].astype(int)
    else:
        df_weighted["weight_citations"] = 1

    if increase_weight_by_year_known:
        df_weighted["weight_year_known"] = df_weighted[year_assumed_col].apply(lambda x: weight_factor_year_known if x == False else 1)
    else:
        df_weighted["weight_year_known"] = 1

    # Calculate the total weight per row.
    df_weighted["weight"] = df_weighted["weight_citations"] + df_weighted["weight_year_known"] - 1 
    expected_number_of_rows = df_weighted["weight"].sum()

    # Duplicate rows weight times.
    df_weighted = df_weighted.loc[df_weighted.index.repeat(df_weighted["weight"])]
    df_weighted.reset_index(drop=True)

    assert len(df_weighted) == expected_number_of_rows

    print(f"\nNumber of rows before adding weight: {len(df)}")
    print(f"Number of rows after adding weight: {len(df_weighted)}")
    print(f"Row with maximum weight:")
    print(df_weighted[df_weighted['weight'] == df_weighted['weight'].max()][['citations', 'weight', 'weight_citations', 'weight_year_known']])
    
    return df_weighted


def create_map_plot(
    df_filtered,
    title,
    preferred_property_label,
    remove_outliers_bounds=None,    
    lat_col="latitude",
    lon_col="longitude",
    color_col="value",
    colormap="Sunsetdark",
    colorbar_pixel_height=500,
    word_wrap_colorbar_label=True,
    colorize_earth=True,
    colorbar_ticks=1,
    categorical_colormap=None,
):
    """
    Create a map plot with scatter points based on the filtered DataFrame.

        ,-----------.
       /   *  *    * \
      |  *      * *   |
       \  *    *   * /
        '-----------'
    """

    # Remove all rows with None latitude or longitude.
    row_count = len(df_filtered)
    df_filtered = df_filtered.dropna(subset=["latitude", "longitude"])
    print(f">>>>>>>>>>>>>>> Dropped {row_count - len(df_filtered)} rows with None latitude or longitude")

    # Only keep rows with value in bounds.
    if remove_outliers_bounds != None:
        df_filtered = df_filtered[df_filtered["value"].between(remove_outliers_bounds[0], remove_outliers_bounds[1])]

    print_df_size(df_filtered)

    # Ensure that size_col is numeric.
    df_filtered["value"] = pd.to_numeric(df_filtered["value"], errors='coerce')    
    
    # Colorbar label    
    colorbar_label = preferred_property_label.capitalize()

    # Set colorbar range.
    if remove_outliers_bounds != None and color_col == "value":
        # Use the remove_outliers_bounds as colorbar range.
        color_col_is_categorical = False
        colorbar_range = remove_outliers_bounds    
    elif pd.api.types.is_numeric_dtype(df_filtered[color_col]):
        # Take min and max if color_col is of numeric type.
        color_col_is_categorical = False
        colorbar_range = (df_filtered[color_col].min(), df_filtered[color_col].max())
    else:
        color_col_is_categorical = True
        if categorical_colormap == None:
            categorical_colormap = px.colors.qualitative.Plotly


    # Show data on map.
    if color_col_is_categorical:
        # If color_col is categorical, use discrete colors.
        fig = px.scatter_geo(
            df_filtered, 
            lat=lat_col, 
            lon=lon_col,
            size="value",
            size_max=8,
            color=color_col,
            # color_discrete_sequence=colormap,       
            color_discrete_map=categorical_colormap,
            hover_name="spatial_scope", 
            hover_data=["value", "entity", "temporal_scope", "qualifier"],
            title=title,
            labels={
                "value": colorbar_label, 
                "spatial_scope": "Spatial Scope"
            },
            projection="natural earth",        
        )
    elif not color_col_is_categorical:
        fig = px.scatter_geo(
            df_filtered, 
            lat=lat_col, 
            lon=lon_col,
            size="value",
            size_max=8,
            color=color_col,
            color_continuous_scale=colormap,         
            hover_name="spatial_scope", 
            hover_data=["value", "entity", "temporal_scope", "qualifier"],
            title=title,
            range_color=colorbar_range,
            labels={
                "value": colorbar_label, 
                "spatial_scope": "Spatial Scope"
            },
            projection="natural earth",        
        )

    if word_wrap_colorbar_label:
        # Replace whitespace with line break alsways when `colorbar_label_max_char_width` characters is reached.        
        colorbar_label_max_char_width = 6
        colorbar_label = re.sub(r'(.{' +str(colorbar_label_max_char_width) + r',}?)\s', r'\1<br>', colorbar_label) 

    # Set tick of scale.
    fig.update_layout(coloraxis_colorbar=dict(
        title=dict(text=colorbar_label),
        thicknessmode="pixels", thickness=50,
        lenmode="pixels", len=colorbar_pixel_height,
        dtick=colorbar_ticks,
    ))
    
    # Color the map.
    if colorize_earth:
        fig.update_geos(
            resolution=50,
            showcoastlines=True, coastlinecolor="RebeccaPurple",
            showland=True, landcolor="#e3ffe3",
            showocean=True, oceancolor="#d6e8ff",
            showlakes=True, lakecolor="Blue",
            showrivers=True, rivercolor="Blue"
        )

    return fig


def save_fig(fig, path, file_format="png", width=1000, aspect_ratio=(3, 2), dpi=300, full_a4_size=False):
    """
    Save the figure to a file with the specified aspect ratio and DPI.

    Args:
        fig: The figure to save.
        path: The path to save the figure to.
        format: The format (svg, png, etc.) to save the figure in (default is "png").
        width: The width of the figure in pixels (default is 500).
        aspec_ratio: The aspect ratio of the figure (default is (3, 2)).
        dpi: The DPI (dots per inch) of the figure (default is 300).
        full_a4_size: If True, the figure will be saved in full A4 size ignoring 
                      width and aspect_ratio (default is False).
    """    
    
    if full_a4_size:
        # Ignore everything, and make it nice on full vertical A4.        
        width, height = (2480, 3508) # A4 size in pixels at 300 DPI
        scale = 0.5
        width = int(width * scale)
        height = int(height * scale)
        margin = dict(l=20, r=20, t=20, b=20)
    else:
        # Calculate height based on aspect ratio        
        height = width * aspect_ratio[1] / aspect_ratio[0]
        m = width*0.05  
        margin = dict(l=m, r=m, t=m, b=m)
        scale = 1

    width = int(width*scale)
    height = int(height*scale)
    
    # Update figure layout.
    fig = fig.update_layout(width=width, height=height, margin=margin)

    # Save figure to file.
    fig.write_image(path, format=file_format, width=width, height=height, scale=dpi/300)

    print(f"\n>>>>>>>>>>>>>>> Saved figure to '{path}'")


