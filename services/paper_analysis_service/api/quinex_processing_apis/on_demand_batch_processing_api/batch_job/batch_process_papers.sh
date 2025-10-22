#!/bin/bash

#SBATCH --job-name=quinex_batch_processing
#SBATCH -o ./logs/inference_api/batch_processing/output-%j.out
#SBATCH -e ./logs/inference_api/batch_processing/slurm-%j.err
#SBATCH --exclude=cn[1-21,31-55]
#SBATCH --gres=gpu:1

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

/usr/bin/env /path/to/.conda/envs/your_quinex_env/bin/python services/paper_analysis_service/api/quinex_processing_apis/on_demand_batch_processing_api/batch_job/process_paper_on_compute_node.py $*