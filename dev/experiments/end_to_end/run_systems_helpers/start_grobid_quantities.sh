#!/bin/bash

#SBATCH --job-name=grobid_quantities
#SBATCH -o ./logs/output-%j.out
#SBATCH -e ./logs/slurm-%j.err
#SBATCH --cpus-per-task=1
#SBATCH --exclude=cn[1-21,31-55]
#SBATCH --gres=gpu:2

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

podman run --rm --init -p 8060:8060 -p 8061:8061 \
  -v /path/to/grobid_quantities_config.yml:/opt/grobid/grobid-quantities/resources/config/config.yml:ro \
  lfoppiano/grobid-quantities:0.8.2