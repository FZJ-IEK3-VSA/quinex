#!/bin/bash 
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH -o ./logs/output-%j.out
#SBATCH -e ./logs/slurm-%j.err
#SBATCH --gres=gpu:1 
##SBATCH --exclusive 
## JOB LOGIC ##

echo "start"

python dev/training/statement_type_classification/run_classification.py\
    --model_name_or_path FacebookAI/roberta-base \
    --train_file ../path/to/train_file.json \
    --validation_file ../path/to/validation_file.json \
    --shuffle_train_dataset \
    --metric_name f1 \
    --metric_for_best_model "f1" \
    --text_column_name text \
    --label_column_name label \
    --do_train \
    --do_eval \
    --max_seq_length 512 \
    --per_device_train_batch_size 16 \
    --learning_rate 2e-5 \
    --num_train_epochs 15 \
    --output_dir /path/to/output_dir/ \
    --save_strategy "epoch" \
    --evaluation_strategy "epoch" \
    --logging_first_step "True" \
    --logging_strategy "steps" \
    --save_total_limit "1" \
    --load_best_model_at_end "True" \
    --overwrite_cache \
    --log_level info

echo "finish"