#!/bin/bash

#SBATCH --job-name=quinex_background_inference_service
#SBATCH -o ./logs/inference_api/background_service_on_compute_node/output-%j.out
#SBATCH -e ./logs/inference_api/background_service_on_compute_node/slurm-%j.err
#SBATCH --cpus-per-task=1
#SBATCH --exclude=cn[1-21,31-55]
#SBATCH --gres=gpu:1

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

# Start quinex inference API.
python ./services/quinex_api/api.py --config_path "./services/paper_analysis_service/config/config.yml"