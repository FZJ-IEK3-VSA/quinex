#!/bin/bash 
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH -o ./logs/output-%j.out
#SBATCH -e ./logs/slurm-%j.err
#SBATCH --gres=gpu:1

echo "start"

python dev/training/context_extraction/generative_QA_with_seq2seq_encoder_decoder_models/run_seq2seq_qa.py --model_name_or_path experiments/generative_context_extraction/model_checkpoints/t5_small --train_file ../path/to/train_file.json --validation_file ../path/to/validation_file.json --test_file ../path/to/test_file.json --context_column context --question_column question --answer_column answers --do_train --do_eval --per_device_train_batch_size "16" --learning_rate "1e-5" --num_train_epochs "3" --version_2_with_negative --max_seq_length "384" --doc_stride "128" --output_dir temp/generative_context_extraction_test --save_strategy "epoch" --evaluation_strategy "epoch" --logging_first_step "True" --logging_strategy "steps" --save_total_limit "5" --load_best_model_at_end "True" --metric_for_best_model "f1" --overwrite_cache

echo "finish"