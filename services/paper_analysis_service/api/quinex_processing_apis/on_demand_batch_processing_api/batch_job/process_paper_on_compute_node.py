import json
from time import time
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser
from wasabi import msg
from tqdm import tqdm
from quinex import Quinex
from quinex.config.presets import models, tasks
from text_processing_utils.boolean_checks import is_gibberish



def extract_quantitative_information_from_batch(
    batch_dir,
    skip_imprecise_quantities=False,
    use_cpu=True,
    use_fp16=False,
    parallel_worker_device_map={
        "quantity_model": {
            "n_workers": 1,
            "gpu_device_ranks": [
                0
            ],
            "batch_size": 128
        },
        "context_model": {
            "n_workers": 3,
            "gpu_device_ranks": [
                0
            ],
            "batch_size": 64
        },
        "qualifier_model": {
            "n_workers": 3,
            "gpu_device_ranks": [
                0
            ],
            "batch_size": 64
        },
        "statement_clf_model": {
            "n_workers": 1,
            "gpu_device_ranks": [
                0
            ],
            "batch_size": 64
        }
    },
    verbosity={
        "verbose": False,
        "debug": False,
    }
):
    """Extracts quantitative information from papers."""

    quinex = Quinex(
        **models.base,
        **tasks.full,
        use_cpu=use_cpu,
        use_fp16=use_fp16,
        verbose=verbosity["verbose"],
        debug=verbosity["debug"],
        parallel_worker_device_map=parallel_worker_device_map
    )    
        
    # Loop over files in paper_dir and open each paper file.
    paper_dir = batch_dir
    for paper_file_path in tqdm(paper_dir.glob("*.json")):
        paper_id = paper_file_path.stem    
        msg.info(f"Processing {paper_id}...")
        with open(paper_file_path, "r", encoding="utf-8") as f:
            paper = json.load(f)

        # Make predictions.
        print(f"Process {paper_id}")
       
        if paper.get("text", "") == "":
            msg.warn(f"Paper {paper_id} has no text. Skip it.")
            predictions = []
        elif is_gibberish(paper.get("text")):
            msg.warn(f"Paper {paper_id} text seems to be gibberish. Skip it.")
            predictions = []
        else:
            msg.info(f"Extracting quantitative information from {paper_id}...")  
            start = time()
            try:
                predictions = quinex(paper["text"], skip_imprecise_quantities=skip_imprecise_quantities, add_curation_fields=True)
            except Exception as e:
                print(e)
                predictions = []
                
            execution_time = time() - start
            print("⏱️ Execution time: ",execution_time)

        # Add predictions to paper.
        paper["annotations"] = paper.get("annotations", {})
        paper["annotations"]["quantitative_statements"] = predictions

        paper["provenance"] = {
            "execution_time": execution_time,
            "skip_imprecise_quantities": config["quantitative_information_extraction"]["skip_imprecise_quantities"],
            "models": config["quantitative_information_extraction"]["model_paths"],
            "timestamp": datetime.now().astimezone().replace(microsecond=0, second=0).isoformat()
        }
        
        # Save predictions to file.    
        with open(paper_file_path, "w") as f:
            json.dump(paper, f, indent=4, ensure_ascii=False)

    print("Done.")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--config_path",
        default="src/quinex_analysis/config.json",
        help="""Path to config file.""",
    )
    parser.add_argument(
        "--batch_dir",
        default="src/quinex_analysis/config.json",
        help="""Path to config file.""",
    )

    # Prepare and print info.
    args = parser.parse_args()
    batch_dir = Path(args.batch_dir)
    config_path = Path(args.config_path)

    with open(config_path, "r") as f:
        config = json.load(f)

    extract_quantitative_information_from_batch(batch_dir, **config["quantitative_information_extraction"])

    print("Done.")