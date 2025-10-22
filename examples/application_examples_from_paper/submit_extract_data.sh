#!/bin/bash

#SBATCH --job-name=process_abstracts
#SBATCH -o ./logs/output-%j.out
#SBATCH -e ./logs/slurm-%j.err
#SBATCH --exclude=cn[1-21,31-55]
#SBATCH --gres=gpu:1

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1

python ./extract_data.py \
    --path_to_scopus_csv ./path/to/scopus.csv \
    --results_path ./path/to/extraction_results.csv\
    --debug_mode False \
    --use_cpu False
