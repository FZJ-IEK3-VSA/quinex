#!/bin/bash

#SBATCH --job-name=test_quinex
#SBATCH -o ./logs_temp/output-%j.out
#SBATCH -e ./logs_temp/slurm-%j.err
#SBATCH --exclude=cn[1-21,31-55]

#SBATCH --gres=gpu:8

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

python src/quinex/scripts/test_pipeline.py

