
import json
from time import time
from argparse import ArgumentParser
import pandas as pd
from quinex import Quinex, CONFIG


parser = ArgumentParser()
parser.add_argument(
    "--path_to_scopus_csv",
    default="scopus.csv",
    help="Path to the CSV file containing the Scopus data. The CSV file should have columns 'Title' and 'Abstract'.",
)
parser.add_argument(
    "--results_path",
    default="extraction_results.json",
    help="Path to save the results JSON file.",
)
parser.add_argument(
    "--debug_mode",
    action="store_true",
    help="If set, only process the first 10 papers.",
)
parser.add_argument(
    "--use_cpu",
    action="store_true",
    default=CONFIG["quinex"]["settings"]["use_cpu"],
    help="If set, use CPU instead of GPU.",
)
args = parser.parse_args()


debug_mode = args.debug_mode
df = pd.read_csv(args.path_to_scopus_csv)

if debug_mode:
    df = df.head(10)

quinex = Quinex(    
    use_cpu=False,    
    parallel_worker_device_map={
        "quantity_model": {"n_workers": 1, "gpu_device_ranks": [0], "batch_size": 128},
        "context_model": {"n_workers": 3, "gpu_device_ranks": [0], "batch_size": 64}, 
        "qualifier_model": {"n_workers": 3, "gpu_device_ranks": [0], "batch_size": 64},
        "statement_clf_model": {"n_workers": 1, "gpu_device_ranks": [0], "batch_size": 64},
    }
)

# Loop over rows in the dataframe and print the title of each article
results = []
overall_start = time()
save_each_x_rows = 500
for index, row in df.iterrows():    
    print("Analyze paper with title:", row["Title"])
    row_dict = row.to_dict()
    clean_abstract = row_dict["Title"] + ": " + row_dict["Abstract"].split("©")[0].rstrip()
    start = time()
    predictions = quinex(clean_abstract, skip_imprecise_quantities=True, add_curation_fields=True)
    row_dict["predictions"] = predictions
    row_dict["execution_time"] = time()-start
    results.append(row_dict)

    if index % save_each_x_rows == 0:
        print(f"Saving intermediate results after {index} rows...")
        with open(args.results_path, "w") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

print(f"Overall execution time: {time() - overall_start:.2f} seconds")

# Save as JSON.
with open(args.results_path, "w") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

print("Done.")


