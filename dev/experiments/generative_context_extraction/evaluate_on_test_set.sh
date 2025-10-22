#!/bin/bash

#SBATCH --job-name=evaluate_on_test_set
#SBATCH -o ./logs/inference_api/output-%j.out
#SBATCH -e ./logs/inference_api/slurm-%j.err
#SBATCH --gres=gpu:1

#export OPENBLAS_NUM_THREADS=1
#export OMP_NUM_THREADS=1
#export USE_SIMPLE_THREADED_LEVEL3=1
#export MKL_NUM_THREADS=1


TRANSFORMERS_OFFLINE=1 && HF_DATASETS_OFFLINE=1 && python dev/training/context_extraction/generative_QA_with_seq2seq_encoder_decoder_models/run_seq2seq_qa.py --model_name_or_path /path/to/model_checkpoint --train_file ../path/to/train_file.json --validation_file ../path/to/validation_file.json --test_file ../path/to/test_file.json --context_column context --question_column question --answer_column answers --do_predict --per_device_train_batch_size "8" --version_2_with_negative --max_seq_length "512" --max_answer_length "120" --doc_stride "128" --adafactor --optim "adafactor" --output_dir /path/to/output_dir --save_strategy "epoch" --evaluation_strategy "epoch" --predict_with_generate --metric_for_best_model "f1" --overwrite_cache --seed 987 --remove_examples_based_on_id_substring "" --keep_examples_based_on_id_substring ""  

