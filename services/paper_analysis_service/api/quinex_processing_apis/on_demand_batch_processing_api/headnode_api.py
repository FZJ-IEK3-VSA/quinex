import os
import math
import json
import yaml
import time
import shutil
import subprocess
from pathlib import Path
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException
import uvicorn
from concurrent.futures import ProcessPoolExecutor
from pydantic import BaseModel
from quinex import __version__



app = FastAPI(
    title="Quinex Batch Processing API",
    version=__version__,
)

API_DIR = Path(__file__).resolve().parent
SLURM_SCRIPT_PATH = API_DIR / "batch_job" / "batch_process_papers.sh"
BASE_BATCH_PROCESSING_DIR = API_DIR / "temp" 

def process_batch(analysis_dir, config_path, batch, refresh_interval=30, timeout=5*60*60):
    """Process a batch of papers on the cluster."""
    
    # Store papers in batch on disk.
    batch_id = batch.get("batch_id")
    batch_dir = analysis_dir / f"batch_{batch_id}"

    actually_process = True
    if actually_process:
        # If batch directory already exists, delete it, else create it.
        if batch_dir.exists():        
            shutil.rmtree(batch_dir)    
        batch_dir.mkdir(parents=True)
            
        for i, paper in enumerate(batch.get("papers")):        
            with open(os.path.join(batch_dir, f"paper_{i}.json" ), "w") as f:
                json.dump(paper, f, indent=4, ensure_ascii=False)      

        # Submit processing script on cluster.        
        stout = subprocess.check_output(f"sbatch {SLURM_SCRIPT_PATH} --batch_dir {batch_dir.as_posix()} --config_path {config_path.as_posix()}", shell=True)
        job_id = int(stout.decode().removeprefix("Submitted batch job "))
        start = time.time()
        print(f"Batch {batch_id} submitted with job_id {job_id}.")
        while time.time() - start < timeout:
            # Check if processing is done.    
            if os.system(f"squeue --job {job_id}") != 0:
                print("Job finished.")
                break

            try:
                if subprocess.check_output(f"squeue --job {job_id}", shell=True) == b'             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n':
                    # Directly after job is finished, the job_id might still be valid.
                    break
            except subprocess.CalledProcessError:
                pass

            time.sleep(refresh_interval)

        if os.system(f"squeue --job {job_id}") == 0:
            # Job is still running.
            os.system(f"scancel {job_id}")
            print(f"Job {job_id} was canceled because it did not finish in time.")

    # Read and return processed data.
    try:        
        processed_data = []
        for i, paper in enumerate(batch.get("papers")):
            with open(os.path.join(batch_dir, f"paper_{i}.json" ), "r") as f:
                processed_data.append(json.load(f))   
    except Exception as e:
        processed_data = []
        print("Error reading processed data. Presumingly the job failed.")
        print(e)

    print(f"Batch {batch_id} done. Processed {len(processed_data)} papers.")    
        
    return processed_data


@app.get("/api/is_alive/", tags=["Special Endpoints"])
def is_alive():    
    return {"detail": "Alive and kicking!"}


class BatchProcessPapersPayload(BaseModel):
    papers: list
    config: dict

@app.post("/api/batch_process_papers/", tags=["Predict"])
def batch_process_papers(batch_job_payload: BatchProcessPapersPayload, mean_execution_time_per_paper_per_gpu: int = 50, gpu_count: int = 4, base_timeout: int = 24*60*60, wait_x_times_until_timeout: int = 10):

    print("*******Start new batch processing*******")    
    papers = batch_job_payload.papers
    config = batch_job_payload.config
    analysis_name = config["analysis_name"]

    analysis_dir = BASE_BATCH_PROCESSING_DIR / analysis_name
    print("analysis_dir", analysis_dir)
    if analysis_dir.exists():
        shutil.rmtree(analysis_dir)
        
    analysis_dir.mkdir(parents=True)
    config_path = analysis_dir / "config.json"

    if not papers or not isinstance(papers, list):
        raise HTTPException(status_code=400, detail="Invalid papers list")

    # Split papers into n_batches batches.
    print("GPU count", gpu_count)
    n_batches = gpu_count
    batch_size = math.ceil(len(papers) / n_batches)
    print(f"Split papers into {n_batches} batches with {batch_size} papers each.")
    batches = [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]
    print(f"Got {len(batches)} batches.")
    assert sum([len(batch) for batch in batches]) == len(papers)

    # Each batch has an ID.
    batches = [{"batch_id": i, "papers": batch} for i, batch in enumerate(batches)]
    
    print(f"Start processing {len(papers)} papers with {n_batches} batches.")    

    # Save config to disk.    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)  

    expected_execution_time = len(papers) * mean_execution_time_per_paper_per_gpu / gpu_count    
    timeout = base_timeout + expected_execution_time * wait_x_times_until_timeout
    print(f"Timeout for each batch is {timeout} seconds.")
    
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_batch, analysis_dir, config_path, batch, 30, timeout) for batch in batches]
        results = [future.result() for future in futures]    
    
    processed_papers = [item for sublist in results for item in sublist]

    # Not all papers are necessarily processed.
    successfully_processed_papers = []
    for paper in processed_papers:        
        if paper.get("annotations", {}).get("quantitative_statements"):
            successfully_processed_papers.append(paper)        
    
    return {"processed_papers": json.dumps(successfully_processed_papers, indent=4, ensure_ascii=False)}


if __name__ == '__main__':
        
    parser = ArgumentParser()
    parser.add_argument(
        "--config_path",
        default="./services/paper_analysis_service/config/config.yml",
        help="""Path to the configuration file with parent dir as key and host and port as values.""",
    )    
    args = parser.parse_args()
    
    with open(args.config_path, "r") as f:
        config = yaml.safe_load(f)

    this_config = config[__file__.split("/")[-2]]

    uvicorn.run(app, port=this_config["port"], host=this_config["host"])