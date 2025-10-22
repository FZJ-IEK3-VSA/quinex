# This script benchmarks various LLMs for geolocation tasks by comparing their predicted coordinates against ground truth locations.
import os
import re
import time
import json
import pandas as pd
from geopy import distance
from quinex.analyze.create_plots.blablador import Models, Completions, ChatCompletions, TokenCount


API_KEY = os.getenv("BLABLADOR_API_KEY")

number_of_runs_averaged = 3

prompt_template = 'Return the latitude and longitude that best matches the following place description and only answer with a JSON response of the format {{"latitude": 0, "longitude": 0}}. Place description: "{location_str}", JSON: {{"'
EXCLUDED_MODELS = ['gpt-3.5-turbo', 'text-davinci-003', 'text-embedding-ada-002', '1 - Llama3 405 the best general model and big context size']
exclude_models_starting_with = "alias-"

# Benchmark models.
# TODO: Add more locations.
groundtruth_locations = [
    {"location_str": "Paris", "latitude": 48.856667, "longitude": 2.351667},
    {"location_str": "Ning'er, Yunnan Province", "latitude": 23.048, "longitude": 101.046},
    {"location_str": "central Chilean margin", "latitude": -35.909, "longitude": -72.733},
    {"location_str": "Tokyo", "latitude": 35.689444, "longitude": 139.691667},
    {"location_str": "Mount Everest", "latitude": 27.988056, "longitude": 86.925},
    {"location_str": "Meppen in north-west Germany", "latitude": 52.69064, "longitude": 7.29097},
    {"location_str": "San Francisco", "latitude": 37.775, "longitude": -122.419444},
    {"location_str": "San Francisco, Córdoba", "latitude": -31.435556, "longitude": -62.071389}, 
]

top_k=0
geolocation_benchmark_results = {}
geolocation_benchmark_exec_times = {}
all_models = Models(api_key=API_KEY).get_model_ids()
models_to_benchmark = [m for m in all_models if not m.startswith(exclude_models_starting_with) and m not in EXCLUDED_MODELS]
for model_id in models_to_benchmark:
    print(f"Evaluating model {model_id} for geolocation benchmark...")
    model_predictions = []
    elapsed_times = []
    completion = Completions(api_key=API_KEY, model=model_id)
    for gt_loc in groundtruth_locations:            
        prompt = prompt_template.format(location_str=gt_loc["location_str"])
        model_pred_per_loc = []
        exec_times_per_loc = []
        for run in range(number_of_runs_averaged):
            start_time = time.time()
            
            trials = 0
            max_trials = 5
            while trials < max_trials:                
                response = completion.get_completion(prompt)
                if response.startswith('{"error":') or response.startswith('<!DOCTYPE HTML PUBLIC'):
                    trials += 1
                    time.sleep(1)
                else:
                    break
            
            elapsed_time = time.time() - start_time
            try:
                json_answer = '{"' + json.loads(response)["choices"][top_k]["text"]
                # In case answer contains additional information, cut answer to start with first '{' and end with first '}'.
                single_json_lines = re.findall(r'\{[^\{]*\}', json_answer, re.DOTALL)                
                json_answer = json.loads(single_json_lines[0])
                dist_deviation_km = distance.distance((gt_loc["latitude"], gt_loc["longitude"]), (json_answer["latitude"], json_answer["longitude"])).km                
            except Exception as e:
                print(f"Error processing response '{response}' for model {model_id} and location '{gt_loc['location_str']}': {e}")
                dist_deviation_km = None
            
            model_pred_per_loc.append(dist_deviation_km)
            exec_times_per_loc.append(elapsed_time)
            
        # Average over multiple runs.
        # TODO: Average results later.
        model_pred_per_loc_not_none = [d for d in model_pred_per_loc if d is not None]
        if len(model_pred_per_loc_not_none) > 0:                       
            average_dist_deviation_km = sum(model_pred_per_loc_not_none) / len(model_pred_per_loc_not_none)
        else:
            average_dist_deviation_km = None
        elapsed_time = sum(exec_times_per_loc) / len(exec_times_per_loc)
        model_predictions.append(average_dist_deviation_km)
        elapsed_times.append(elapsed_time)

    geolocation_benchmark_results[model_id] = model_predictions
    geolocation_benchmark_exec_times[model_id] = elapsed_times

loc_indices = [f"{gt_loc['location_str']} ({gt_loc['latitude']}, {gt_loc['longitude']})" for gt_loc in groundtruth_locations]
df_geo_loc_benchmark = pd.DataFrame(geolocation_benchmark_results, index=loc_indices)
df_geo_loc_benchmark_exec_times = pd.DataFrame(geolocation_benchmark_exec_times, index=loc_indices)

df_geo_loc_benchmark = df_geo_loc_benchmark.T
df_geo_loc_benchmark["Number of Failed Predictions"] = df_geo_loc_benchmark.apply(lambda x: x.isna().sum(), axis=1).astype(int)
df_geo_loc_benchmark["Mean Distance Deviation (km)"] = df_geo_loc_benchmark.apply(lambda x: x.mean() if x.count() > 0 else None, axis=1)
df_geo_loc_benchmark["Total Distance Deviation (km)"] = df_geo_loc_benchmark.apply(lambda x: x.sum() if x.count() > 0 else None, axis=1)
df_geo_loc_benchmark["Mean Execution Time (s)"] = df_geo_loc_benchmark_exec_times.mean(axis=0)
model_average_label = "Model average"
df_geo_loc_benchmark.loc[model_average_label] = df_geo_loc_benchmark.mean(numeric_only=True)
df_geo_loc_benchmark = df_geo_loc_benchmark.sort_values(by="Mean Distance Deviation (km)", ascending=True)

# Add column with model rank
df_geo_loc_benchmark["Most accurate rank"] = df_geo_loc_benchmark["Mean Distance Deviation (km)"].rank(method='min').astype(int)        
df_geo_loc_benchmark["Fastest rank"] = df_geo_loc_benchmark["Mean Execution Time (s)"].rank(method='min').astype(int)   
# TODO: do not just add up individual ranks but calculate efficiency based on distance deviation and execution time. 
df_geo_loc_benchmark["Efficiency rank"] = df_geo_loc_benchmark["Most accurate rank"] + df_geo_loc_benchmark["Fastest rank"]
df_geo_loc_benchmark["Efficiency rank"] = df_geo_loc_benchmark["Efficiency rank"].rank(method='min').astype(int)        
df_geo_loc_benchmark["Most accurate rank"] = df_geo_loc_benchmark["Most accurate rank"].replace({1: '🥇', 2: '🥈', 3: '🥉'})
df_geo_loc_benchmark["Fastest rank"] = df_geo_loc_benchmark["Fastest rank"].replace({1: '🥇', 2: '🥈', 3: '🥉'})
df_geo_loc_benchmark["Efficiency rank"] = df_geo_loc_benchmark["Efficiency rank"].replace({1: '🥇', 2: '🥈', 3: '🥉'})

# Print results per model.        
print("\nGeolocation benchmark results per model over all locations:")
with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.float_format', '{:.1f}'.format):
    print(df_geo_loc_benchmark[["Most accurate rank", "Efficiency rank", "Mean Distance Deviation (km)", "Total Distance Deviation (km)", "Number of Failed Predictions", "Mean Execution Time (s)"]])

# Print results per location.
print("\nGeolocation benchmark results per location over all models (deviation in km):")
with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000, 'display.float_format', '{:.1f}'.format):        
    print(df_geo_loc_benchmark.loc[model_average_label, loc_indices].to_frame())