#!/bin/bash

#SBATCH --job-name=evaluate_on_test_set
#SBATCH -o ./logs/experiments/output-%j.out
#SBATCH -e ./logs/experiments/slurm-%j.err
#SBATCH --gres=gpu:1

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1


TRANSFORMERS_OFFLINE=1 && HF_DATASETS_OFFLINE=1 && python dev/training/quantity_extraction/sequence_labeling_with_autoencoding_encoder_models/run_ner.py --model_name_or_path /path/to/model_checkpoint --train_file ../path/to/train_file.json --validation_file ../path/to/validation_file.json --test_file ../path/to/test_file.json \
--do_predict --task_name "ner" \
--output_dir /path/to/output_dir/test_set_predictions \
--metric_for_best_model "f1" --mask_input "False" --mask_probability "0" --seed 123 --log_level info --max_seq_length 512 --weight_decay 0 --optim "adamw_torch" --lr_scheduler_type "linear"