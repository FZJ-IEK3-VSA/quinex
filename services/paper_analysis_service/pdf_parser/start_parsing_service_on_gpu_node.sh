#!/bin/bash

#SBATCH --job-name=quinex_background_parsing_service
#SBATCH -o ./logs/parsing_service/output-%j.out
#SBATCH -e ./logs/parsing_service/slurm-%j.err
#SBATCH --cpus-per-task=2
#SBATCH --exclude=cn[1-21,31-55]
#SBATCH --gres=gpu:8

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

# Start quinex inference API.
podman run --rm --gpus all --init --ulimit core=0 -p 8070:8070 grobid/grobid:0.8.0
