import os
import re
import time
import json
from tqdm import tqdm

try:
    from geopy import distance
except ImportError:
    print(f"Geopy not installed. Please install geopy to use geolocation features in {__file__}.")

try:    
    from quinex.analyze.create_plots.blablador import Models, Completions, ChatCompletions, TokenCount
except ImportError:    
    print(f"LLM geocoding not available. Please install an LLM API completion package, adapt the source of {__file__} and provide an API key.")


from quinex.analyze.create_plots.helpers.utils import load_application_results, condense_quantity_format
from quinex.analyze.create_plots.helpers.filter import filter_based_on_characteristic_keywords, only_absolute_quantities, only_keep_successfully_normalized_quantities, filter_rows_with_value_outside_expected_bounds
from quinex.normalize.quantity.units import transform_to_uniform_unit
from quinex.normalize.quantity.value import get_single_quantities_from_normalized_quantity
from quinex.analyze.create_plots.helpers.normalize import transform_intervals_etc_to_single_value
from quinex.normalize.temporal_scope.year import get_int_year_from_temporal_scope
from quinex.analyze.create_plots.helpers.group import extract_qclaims_within_columns, add_category_based_on_keywords


API_KEY = os.getenv("BLABLADOR_API_KEY")
if API_KEY is None:
    raise ValueError("Please set the BLABLADOR_API_KEY environment variable to use the Blablador API for normalizing location descriptions to geo coordinates.")


def get_geo_coordinates_from_spatial_scope(
    df_filtered,
    blablador_llm_ids=['7 - Qwen3-Coder-30B-A3B-Instruct - A code model from August 2025'],
    nbr_runs_per_model=2,
    predicted_geo_coordinates_cache_path="cached_predicted_geo_coordinates.json",
    dist_deviation_threshold_in_km=300,    
    rerun_those_that_failed_earlier=True,
    update_spatial_scopes=True
):    
    """
    Get geo coordinates for natural language location descriptions using the Blablador API.
    
    You can check the results, e.g., at https://www.google.com/maps/@{latitude},{longitude},15z.
    """
    try:
        # Load cached predicted coordinates.
        with open(predicted_geo_coordinates_cache_path, "r") as f:
            predicted_geo_coordinates = json.load(f)
    except FileNotFoundError:
        print("No cached predicted coordinates found. Starting geolocation from scratch.")
        predicted_geo_coordinates = {}

    for blablador_llm_id in blablador_llm_ids:
        completion = Completions(api_key=API_KEY, model=blablador_llm_id, max_tokens=36, choices=nbr_runs_per_model, stop=["}"])

        if blablador_llm_id not in predicted_geo_coordinates:
            predicted_geo_coordinates[blablador_llm_id] = {}
    
        # Check which spatial scopes are not yet geolocated.
        all_spatial_scopes = df_filtered["spatial_scope"].unique().tolist()
        all_spatial_scopes.remove("")  # Remove empty spatial scopes.

        not_yet_geolocated_spatial_scopes = []
        for scope in all_spatial_scopes:
            if scope not in predicted_geo_coordinates[blablador_llm_id] \
                or len(predicted_geo_coordinates[blablador_llm_id][scope]) < nbr_runs_per_model \
                    or (rerun_those_that_failed_earlier and any(None in pred.values() for pred in predicted_geo_coordinates[blablador_llm_id][scope])):
                not_yet_geolocated_spatial_scopes.append(scope)

        if update_spatial_scopes and len(not_yet_geolocated_spatial_scopes) > 0:
            # Geolocate missing spatial scopes.
            print(f"\n>>>>>>>>>>>>>>> Geolocating missing {len(not_yet_geolocated_spatial_scopes)} of {len(all_spatial_scopes)} unique spatial scopes")
            prompt_template = 'Return the latitude and longitude that best matches the following place description and only answer with a JSON response in the format {{"latitude": 0, "longitude": 0}}.\nPlace description: "{location_str}"\nJSON: {{"'
            for location_str in tqdm(not_yet_geolocated_spatial_scopes, desc="Geolocating spatial scopes"):

                # Generate completion.
                prompt = prompt_template.format(location_str=location_str)
                trials = 0
                max_trials = 5
                while trials < max_trials:
                    response = completion.get_completion(prompt)
                    if response.startswith('{"error":') or response.startswith('<!DOCTYPE HTML PUBLIC'):
                        trials += 1
                        time.sleep(1)
                    else:
                        break

                pred_geo_coords = []
                try:
                    answers = json.loads(response)
                    for answer in answers["choices"]:
                        # In case answer contains additional information, cut answer to start with first '{' and end with first '}'.
                        json_str ='{"' + answer["text"] + '}'
                        single_json_lines = re.findall(r'\{[^\{]*\}', json_str, re.DOTALL)
                        try:
                            json_answer = json.loads(single_json_lines[0])
                            pred_geo_coord = {
                                "latitude": json_answer["latitude"],
                                "longitude": json_answer["longitude"],
                            }
                            pred_geo_coords.append(pred_geo_coord)
                        except Exception as e:
                            # If LLM answer cannot be decoded as valid JSON, print error and continue.
                            print(f"Error decoding answer '{json_answer}' for location '{location_str}': {e}")
                            continue
                except Exception as e:
                    # If API response is not a valid JSON, print error and continue.
                    print(f"Error processing response '{response}' for location '{location_str}': {e}")
                    continue

                predicted_geo_coordinates[blablador_llm_id][location_str] = pred_geo_coords
                
            # Save predicted coordinates to file.    
            with open(predicted_geo_coordinates_cache_path, "w") as f:
                json.dump(predicted_geo_coordinates, f, indent=4, ensure_ascii=False)

    # Compare predicted coordinates of all models and sort locations by highest deviation.
    dist_sum_per_location = {}
    for model_id in predicted_geo_coordinates.keys():
        for location_str, coord_preds in predicted_geo_coordinates[model_id].items():
            for coords in coord_preds:
                # Check if coordinates are valid.
                if coords["latitude"] is not None and coords["longitude"] is not None:
                    if -90 <= coords["latitude"] <= 90 and -180 <= coords["longitude"] <= 180:
                        if location_str not in dist_sum_per_location:
                            dist_sum_per_location[location_str] = []
                        dist_sum_per_location[location_str].append((coords["latitude"], coords["longitude"]))
        
    # Calculate average distance deviation for each location.
    average_dist_deviation_per_location = {}
    averaged_coords = {}
    for location_str, coords_list in dist_sum_per_location.items():
        if len(coords_list) > 1:
            # Calculate average coordinates.
            avg_lat = sum(coord[0] for coord in coords_list) / len(coords_list)
            avg_lon = sum(coord[1] for coord in coords_list) / len(coords_list)
            average_coords = (avg_lat, avg_lon)
            averaged_coords[location_str] = {"latitude": avg_lat, "longitude": avg_lon}
            
            distances_in_km = []
            for coord in coords_list:
                # Calculate distance to average coordinates.
                distances_in_km.append(distance.distance(coord, average_coords).km)

            distances_in_km_mean = sum(distances_in_km) / len(distances_in_km)
            average_dist_deviation_per_location[location_str] = distances_in_km_mean

    # Debug-tip: Sort locations by average distance deviation.
    # sorted(average_dist_deviation_per_location.items(), key=lambda x: x[1], reverse=True)
    
    # Add coordinates to DataFrame, if no coordinates are available, None.
    df_filtered["latitude"] = df_filtered["spatial_scope"].apply(lambda x: averaged_coords[x]["latitude"] if x in averaged_coords else None)
    df_filtered["longitude"] = df_filtered["spatial_scope"].apply(lambda x: averaged_coords.get(x, {}).get("longitude", None))    

    # Set both latitude and longitude to None if distance deviation is too high > 300 km.  
    for location_str, dist in average_dist_deviation_per_location.items():
        if dist > dist_deviation_threshold_in_km:            
            df_filtered.loc[df_filtered["spatial_scope"] == location_str, ["latitude", "longitude"]] = None
            print(f"Warning: Distance deviation for location '{location_str}' is {dist:.2f} km (> {dist_deviation_threshold_in_km} km threshold). Setting coordinates to None.")    

    # Set both latitude and longitude to None if they are outside expected bounds.
    df_out_of_bounds = df_filtered[(~df_filtered["latitude"].between(-90, 90)) | (~df_filtered["longitude"].between(-180, 180))]
    df_filtered.loc[df_out_of_bounds.index, ["latitude", "longitude"]] = None

    # Set both latitude or longitutde to None if they are 0 as this is the default coordinate in the prompt 
    # and is additionally likely chosen for describtion such as "worldwide" etc., but allow NaN.
    likely_false_coords = [(0, 0)]
    for likely_false_lat, likely_false_lon in likely_false_coords:
        df_filtered.loc[(df_filtered["latitude"] == likely_false_lat) & (df_filtered["longitude"] == likely_false_lon), ["latitude", "longitude"]] = None

    return df_filtered