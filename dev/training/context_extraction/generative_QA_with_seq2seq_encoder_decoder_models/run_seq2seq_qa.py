#!/usr/bin/env python
# coding=utf-8
# Copyright 2021 The HuggingFace Team All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# This code has been modified by Jülich Systems Analysis.
#
"""
Fine-tuning the library's seq2seq models for question answering using the 🤗 Seq2SeqTrainer.
"""
# You can also adapt this script on your own question answering task. Pointers for this are left as comments.

import logging
import os
import sys
import warnings
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import datasets
import evaluate
import numpy as np
from datasets import load_dataset
from trainer_seq2seq_qa import QuestionAnsweringSeq2SeqTrainer

import transformers
from transformers import (
    AutoConfig,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    HfArgumentParser,
    Seq2SeqTrainingArguments,
    set_seed,
)
from transformers.optimization import Adafactor, AdafactorSchedule
from transformers.trainer_utils import EvalLoopOutput, EvalPrediction, get_last_checkpoint
from transformers.utils import check_min_version, send_example_telemetry
from transformers.utils.versions import require_version



logger = logging.getLogger(__name__)


@dataclass
class ModelArguments:
    """
    Arguments pertaining to which model/config/tokenizer we are going to fine-tune from.
    """

    model_name_or_path: str = field(
        metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    config_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained config name or path if not the same as model_name"}
    )
    tokenizer_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained tokenizer name or path if not the same as model_name"}
    )
    cache_dir: Optional[str] = field(
        default=None,
        metadata={"help": "Path to directory to store the pretrained models downloaded from huggingface.co"},
    )
    use_fast_tokenizer: bool = field(
        default=True,
        metadata={"help": "Whether to use one of the fast tokenizer (backed by the tokenizers library) or not."},
    )
    model_revision: str = field(
        default="main",
        metadata={"help": "The specific model version to use (can be a branch name, tag name or commit id)."},
    )
    token: str = field(
        default=None,
        metadata={
            "help": (
                "The token to use as HTTP bearer authorization for remote files. If not specified, will use the token "
                "generated when running `huggingface-cli login` (stored in `~/.huggingface`)."
            )
        },
    )
    use_auth_token: bool = field(
        default=None,
        metadata={
            "help": "The `use_auth_token` argument is deprecated and will be removed in v4.34. Please use `token` instead."
        },
    )
    trust_remote_code: bool = field(
        default=False,
        metadata={
            "help": (
                "Whether or not to allow for custom models defined on the Hub in their own modeling files. This option "
                "should only be set to `True` for repositories you trust and in which you have read the code, as it will "
                "execute code present on the Hub on your local machine."
            )
        },
    )


@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """

    dataset_name: Optional[str] = field(
        default=None, metadata={"help": "The name of the dataset to use (via the datasets library)."}
    )
    dataset_config_name: Optional[str] = field(
        default=None, metadata={"help": "The configuration name of the dataset to use (via the datasets library)."}
    )
    context_column: Optional[str] = field(
        default="context",
        metadata={"help": "The name of the column in the datasets containing the contexts (for question answering)."},
    )
    question_column: Optional[str] = field(
        default="question",
        metadata={"help": "The name of the column in the datasets containing the questions (for question answering)."},
    )
    answer_column: Optional[str] = field(
        default="answers",
        metadata={"help": "The name of the column in the datasets containing the answers (for question answering)."},
    )
    train_file: Optional[str] = field(default=None, metadata={"help": "The input training data file (a text file)."})
    validation_file: Optional[str] = field(
        default=None,
        metadata={"help": "An optional input evaluation data file to evaluate the perplexity on (a text file)."},
    )
    test_file: Optional[str] = field(
        default=None,
        metadata={"help": "An optional input test data file to evaluate the perplexity on (a text file)."},
    )
    overwrite_cache: bool = field(
        default=False, metadata={"help": "Overwrite the cached training and evaluation sets"}
    )
    preprocessing_num_workers: Optional[int] = field(
        default=None,
        metadata={"help": "The number of processes to use for the preprocessing."},
    )
    max_seq_length: int = field(
        default=512,
        metadata={
            "help": (
                "The maximum total input sequence length after tokenization. Sequences longer "
                "than this will be truncated, sequences shorter will be padded."
            )
        },
    )
    max_answer_length: int = field(
        default=120,
        metadata={
            "help": (
                "The maximum length of an answer that can be generated. This is needed because the start "
                "and end predictions are not conditioned on one another."
            )
        },
    )
    val_max_answer_length: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "The maximum total sequence length for validation target text after tokenization. Sequences longer "
                "than this will be truncated, sequences shorter will be padded. Will default to `max_answer_length`. "
                "This argument is also used to override the ``max_length`` param of ``model.generate``, which is used "
                "during ``evaluate`` and ``predict``."
            )
        },
    )
    pad_to_max_length: bool = field(
        default=True,
        metadata={
            "help": (
                "Whether to pad all samples to `max_seq_length`. If False, will pad the samples dynamically when"
                " batching to the maximum length in the batch (which can be faster on GPU but will be slower on TPU)."
            )
        },
    )
    max_train_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "For debugging purposes or quicker training, truncate the number of training examples to this "
                "value if set."
            )
        },
    )
    max_eval_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "For debugging purposes or quicker training, truncate the number of evaluation examples to this "
                "value if set."
            )
        },
    )
    max_predict_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "For debugging purposes or quicker training, truncate the number of prediction examples to this "
                "value if set."
            )
        },
    )
    version_2_with_negative: bool = field(
        default=False, metadata={"help": "If true, some of the examples do not have an answer."}
    )
    null_score_diff_threshold: float = field(
        default=0.0,
        metadata={
            "help": (
                "The threshold used to select the null answer: if the best answer has a score that is less than "
                "the score of the null answer minus this threshold, the null answer is selected for this example. "
                "Only useful when `version_2_with_negative=True`."
            )
        },
    )
    doc_stride: int = field(
        default=128,
        metadata={"help": "When splitting up a long document into chunks, how much stride to take between chunks."},
    )
    n_best_size: int = field(
        default=20,
        metadata={"help": "The total number of n-best predictions to generate when looking for an answer."},
    )
    num_beams: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "Number of beams to use for evaluation. This argument will be passed to ``model.generate``, "
                "which is used during ``evaluate`` and ``predict``."
            )
        },
    )
    ignore_pad_token_for_loss: bool = field(
        default=True,
        metadata={
            "help": "Whether to ignore the tokens corresponding to padded labels in the loss computation or not."
        },
    )

    remove_examples_based_on_id_substring: Optional[List[str]] = field(
        default=None,
        metadata={
            "help": (
                "If specified, examples with IDs containing any of the substrings will be removed from the datasets."
            )
        },
    )

    keep_examples_based_on_id_substring: Optional[List[str]] = field(
        default=None,
        metadata={
            "help": (
                "If specified, only examples with IDs containing any of the substrings will be kept in the datasets."
            )
        },
    )

    def __post_init__(self):
        if (
            self.dataset_name is None
            and self.train_file is None
            and self.validation_file is None
            and self.test_file is None
        ):
            raise ValueError("Need either a dataset name or a training/validation file/test_file.")
        else:
            if self.train_file is not None:
                extension = self.train_file.split(".")[-1]
                assert extension in ["csv", "json"], "`train_file` should be a csv or a json file."
            if self.validation_file is not None:
                extension = self.validation_file.split(".")[-1]
                assert extension in ["csv", "json"], "`validation_file` should be a csv or a json file."
            if self.test_file is not None:
                extension = self.test_file.split(".")[-1]
                assert extension in ["csv", "json"], "`test_file` should be a csv or a json file."
        if self.val_max_answer_length is None:
            self.val_max_answer_length = self.max_answer_length

@dataclass
class HyperParameterSearchArguments:
    """
    Arguments for hyperparameter search/tuning.
    """

    do_hyperparameter_search: bool = field(
        default=False,
        metadata={
            "help": "Whether to optimize hyperparameters instead of using a fixed set of them."
        },
    )
    hp_tuning_n_trials: Optional[int] = field(
        default=10,
        metadata={"help": "The number of trials using different hyperparameter sets."},
    )
    hp_results_path: Optional[str] = field(
        default="experiments/generative_context_extraction/hyperpar_search_results/",
        metadata={
            "help": "An optional input evaluation data file to evaluate on (a csv or JSON file)."
        },
    )

question_answering_column_name_mapping = {
    "squad_v2": ("question", "context", "answer"),
}


def main():
    # See all possible arguments in src/transformers/training_args.py
    # or by passing the --help flag to this script.
    # We now keep distinct sets of args, for a cleaner separation of concerns.

    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, Seq2SeqTrainingArguments, HyperParameterSearchArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        # If we pass only one argument to the script and it's the path to a json file,
        # let's parse it to get our arguments.
        model_args, data_args, training_args = parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
    else:
        model_args, data_args, training_args, hyperpar_search_args = parser.parse_args_into_dataclasses()


    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if training_args.should_log:
        # The default of training_args.log_level is passive, so we set log level at info here to have that default.
        transformers.utils.logging.set_verbosity_info()

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    # Require GPU usage.
    if training_args.device.type == 'cpu':
        raise ValueError("GPU usage required but no GPU is used. Exiting.")    

    # Log on each process the small summary:    
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}, "
        + f"distributed training: {training_args.parallel_mode.value == 'distributed'}, "
        + f"16-bits training: fp16 {training_args.fp16}, bf16 {training_args.bf16}, "
        + f"evaluate with 16-bits: {training_args.fp16_full_eval}, bf16 {training_args.bf16_full_eval}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")

    # Detecting last checkpoint.
    last_checkpoint = None
    if os.path.isdir(training_args.output_dir) and training_args.do_train and not training_args.overwrite_output_dir:
        last_checkpoint = get_last_checkpoint(training_args.output_dir)
        if last_checkpoint is None and len(os.listdir(training_args.output_dir)) > 0:
            raise ValueError(
                f"Output directory ({training_args.output_dir}) already exists and is not empty. "
                "Use --overwrite_output_dir to overcome."
            )
        elif last_checkpoint is not None and training_args.resume_from_checkpoint is None:
            logger.info(
                f"Checkpoint detected, resuming training at {last_checkpoint}. To avoid this behavior, change "
                "the `--output_dir` or add `--overwrite_output_dir` to train from scratch."
            )

    # Set seed before initializing model.
    set_seed(training_args.seed)

    # Get the datasets: you can either provide your own CSV/JSON/TXT training and evaluation files (see below)
    # or just provide the name of one of the public datasets available on the hub at https://huggingface.co/datasets/
    # (the dataset will be downloaded automatically from the datasets Hub).
    #
    # For CSV/JSON files, this script will use the column called 'text' or the first column if no column called
    # 'text' is found. You can easily tweak this behavior (see below).
    #
    # In distributed training, the load_dataset function guarantee that only one local process can concurrently
    # download the dataset.
    if data_args.dataset_name is not None:
        # Downloading and loading a dataset from the hub.
        raw_datasets = load_dataset(
            data_args.dataset_name,
            data_args.dataset_config_name,
            cache_dir=model_args.cache_dir,
            # token=model_args.token,
        )
    else:
        data_files = {}
        if data_args.train_file is not None:
            data_files["train"] = data_args.train_file
            extension = data_args.train_file.split(".")[-1]
        if data_args.validation_file is not None:
            data_files["validation"] = data_args.validation_file
            extension = data_args.validation_file.split(".")[-1]
        if data_args.test_file is not None:
            data_files["test"] = data_args.test_file
            extension = data_args.test_file.split(".")[-1]
        raw_datasets = load_dataset(
            extension,
            data_files=data_files,
            field="data",
            cache_dir=model_args.cache_dir,
            # token=model_args.token,
        )
    # See more about loading any type of standard or custom dataset (from files, python dict, pandas DataFrame, etc) at
    # https://huggingface.co/docs/datasets/loading_datasets.

    # Remove examples based on ID substring.
    if data_args.remove_examples_based_on_id_substring is not None:
        # for split in raw_datasets.keys():
        for split in ["train"]:
            for substring in data_args.remove_examples_based_on_id_substring:
                if len(substring) > 0: # Do nothing if empty string is given.
                    raw_datasets[split] = raw_datasets[split].filter(
                        lambda example: substring not in example["id"]
                    )

    # Only keep examples based on ID substring.
    if data_args.keep_examples_based_on_id_substring is not None:
        # for split in raw_datasets.keys():
        for split in ["train"]:            
            substrings = [substring for substring in data_args.keep_examples_based_on_id_substring if len(substring) > 0]                
            if len(substrings) > 0: # Do nothing if empty list is given.
                raw_datasets[split] = raw_datasets[split].filter(
                        lambda example: any(substring in example["id"] for substring in substrings)
                )

    # Load pretrained model and tokenizer
    #
    # Distributed training:
    # The .from_pretrained methods guarantee that only one local process can concurrently
    # download model & vocab.
    config = AutoConfig.from_pretrained(
        model_args.config_name if model_args.config_name else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
        revision=model_args.model_revision,
        # token=model_args.token,
        # trust_remote_code=model_args.trust_remote_code,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.tokenizer_name if model_args.tokenizer_name else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
        use_fast=model_args.use_fast_tokenizer,
        revision=model_args.model_revision,
        # token=model_args.token,
        # trust_remote_code=model_args.trust_remote_code,
    )
    # tokenizer.add_tokens(list(set(["∣","λ","ε","◦","∆","α","β","Ξ","ξ","Γ","γ","Δ","δ","Π","π","ε","ζ","Σ","σς","η","τ","Θ","θ","ι","Φ","φ","κ","χ","Λ","λ","Ψ","ψ","μ","Ω","ω"])))

    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_args.model_name_or_path,
        from_tf=bool(".ckpt" in model_args.model_name_or_path),
        config=config,
        cache_dir=model_args.cache_dir,
        revision=model_args.model_revision,
        # token=model_args.token,
        # trust_remote_code=model_args.trust_remote_code,
    )

    # We resize the embeddings only when necessary to avoid index errors. If you are creating a model from scratch
    # on a small vocab and want a smaller embedding size, remove this test.
    embedding_size = model.get_input_embeddings().weight.shape[0]
    if len(tokenizer) > embedding_size:
        print("Probably new tokens were added to the tokenizer. Resizing token embeddings to fit tokenizer vocab...")
        model.resize_token_embeddings(len(tokenizer))

    if model.config.decoder_start_token_id is None:
        raise ValueError("Make sure that `config.decoder_start_token_id` is correctly defined")

    # Preprocessing the datasets.
    # We need to generate and tokenize inputs and targets.
    if training_args.do_train:
        column_names = raw_datasets["train"].column_names
    elif training_args.do_eval:
        column_names = raw_datasets["validation"].column_names
    elif training_args.do_predict:
        column_names = raw_datasets["test"].column_names
    else:
        logger.info("There is nothing to do. Please pass `do_train`, `do_eval` and/or `do_predict`.")
        return

    # Get the column names for input/target.
    dataset_columns = question_answering_column_name_mapping.get(data_args.dataset_name, None)
    if data_args.question_column is None:
        question_column = dataset_columns[0] if dataset_columns is not None else column_names[0]
    else:
        question_column = data_args.question_column
        if question_column not in column_names:
            raise ValueError(
                f"--question_column' value '{data_args.question_column}' needs to be one of: {', '.join(column_names)}"
            )
    if data_args.context_column is None:
        context_column = dataset_columns[1] if dataset_columns is not None else column_names[1]
    else:
        context_column = data_args.context_column
        if context_column not in column_names:
            raise ValueError(
                f"--context_column' value '{data_args.context_column}' needs to be one of: {', '.join(column_names)}"
            )
    if data_args.answer_column is None:
        answer_column = dataset_columns[2] if dataset_columns is not None else column_names[2]
    else:
        answer_column = data_args.answer_column
        if answer_column not in column_names:
            raise ValueError(
                f"--answer_column' value '{data_args.answer_column}' needs to be one of: {', '.join(column_names)}"
            )

    # Temporarily set max_answer_length for training.
    max_answer_length = data_args.max_answer_length
    padding = "max_length" if data_args.pad_to_max_length else False

    if training_args.label_smoothing_factor > 0 and not hasattr(model, "prepare_decoder_input_ids_from_labels"):
        logger.warning(
            "label_smoothing is enabled but the `prepare_decoder_input_ids_from_labels` method is not defined for "
            f"`{model.__class__.__name__}`. This will lead to loss being calculated twice and will take up more memory"
        )

    if data_args.max_seq_length > tokenizer.model_max_length:
        logger.warning(
            f"The max_seq_length passed ({data_args.max_seq_length}) is larger than the maximum length for the "
            f"model ({tokenizer.model_max_length}). Using max_seq_length={tokenizer.model_max_length}."
        )
    max_seq_length = min(data_args.max_seq_length, tokenizer.model_max_length)

    def preprocess_squad_batch(
        examples,
        question_column: str,
        context_column: str,
        answer_column: str,
    ) -> Tuple[List[str], List[str]]:
        questions = examples[question_column]
        contexts = examples[context_column]
        answers = examples[answer_column]

        def generate_input(_question, _context):
            return " ".join(["question:", _question.lstrip(), "context:", _context.lstrip()])

        inputs = [generate_input(question, context) for question, context in zip(questions, contexts)]
        targets = [answer["text"][0] if len(answer["text"]) > 0 else "" for answer in answers]
        return inputs, targets

    def preprocess_function(examples):
        inputs, targets = preprocess_squad_batch(examples, question_column, context_column, answer_column)

        model_inputs = tokenizer(inputs, max_length=max_seq_length, padding=padding, truncation=True)
        # Tokenize targets with text_target=...
        labels = tokenizer(text_target=targets, max_length=max_answer_length, padding=padding, truncation=True)

        # If we are padding here, replace all tokenizer.pad_token_id in the labels by -100 when we want to ignore
        # padding in the loss.
        if padding == "max_length" and data_args.ignore_pad_token_for_loss:
            labels["input_ids"] = [
                [(l if l != tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
            ]

        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    # Validation preprocessing
    def preprocess_validation_function(examples):
        inputs, targets = preprocess_squad_batch(examples, question_column, context_column, answer_column)

        model_inputs = tokenizer(
            inputs,
            max_length=max_seq_length,
            padding=padding,
            truncation=True,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
        )
        # Tokenize targets with the `text_target` keyword argument
        labels = tokenizer(text_target=targets, max_length=max_answer_length, padding=padding, truncation=True)

        # If we are padding here, replace all tokenizer.pad_token_id in the labels by -100 when we want to ignore
        # padding in the loss.
        if padding == "max_length" and data_args.ignore_pad_token_for_loss:
            labels["input_ids"] = [
                [(l if l != tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
            ]

        # Since one example might give us several features if it has a long context, we need a map from a feature to
        # its corresponding example. This key gives us just that.
        sample_mapping = model_inputs.pop("overflow_to_sample_mapping")

        # For evaluation, we will need to convert our predictions to substrings of the context, so we keep the
        # corresponding example_id and we will store the offset mappings.
        model_inputs["example_id"] = []
        # Augment the overflowing tokens to the labels
        labels_out = []

        for i in range(len(model_inputs["input_ids"])):
            # One example can give several spans, this is the index of the example containing this span of text.
            sample_index = sample_mapping[i]
            model_inputs["example_id"].append(examples["id"][sample_index])
            labels_out.append(labels["input_ids"][sample_index])

        model_inputs["labels"] = labels_out
        return model_inputs

    if training_args.do_train:
        if "train" not in raw_datasets:
            raise ValueError("--do_train requires a train dataset")
        train_dataset = raw_datasets["train"]
        if data_args.max_train_samples is not None:
            # We will select sample from whole data if argument is specified
            max_train_samples = min(len(train_dataset), data_args.max_train_samples)
            train_dataset = train_dataset.select(range(max_train_samples))
        # Create train feature from dataset
        with training_args.main_process_first(desc="train dataset map pre-processing"):
            train_dataset = train_dataset.map(
                preprocess_function,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                remove_columns=column_names,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on train dataset",
            )
        if data_args.max_train_samples is not None:
            # Number of samples might increase during Feature Creation, We select only specified max samples
            max_train_samples = min(len(train_dataset), data_args.max_train_samples)
            train_dataset = train_dataset.select(range(max_train_samples))

    if training_args.do_eval:
        if "validation" not in raw_datasets:
            raise ValueError("--do_eval requires a validation dataset")
        eval_examples = raw_datasets["validation"]
        if data_args.max_eval_samples is not None:
            # We will select sample from whole data
            max_eval_samples = min(len(eval_examples), data_args.max_eval_samples)
            eval_examples = eval_examples.select(range(max_eval_samples))
        # Validation Feature Creation
        with training_args.main_process_first(desc="validation dataset map pre-processing"):
            eval_dataset = eval_examples.map(
                preprocess_validation_function,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                remove_columns=column_names,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on validation dataset",
            )
        if data_args.max_eval_samples is not None:
            # During Feature creation dataset samples might increase, we will select required samples again
            max_eval_samples = min(len(eval_dataset), data_args.max_eval_samples)
            eval_dataset = eval_dataset.select(range(max_eval_samples))

    if training_args.do_predict:
        if "test" not in raw_datasets:
            raise ValueError("--do_predict requires a test dataset")
        predict_examples = raw_datasets["test"]
        if data_args.max_predict_samples is not None:
            # We will select sample from whole data
            predict_examples = predict_examples.select(range(data_args.max_predict_samples))
        # Predict Feature Creation
        with training_args.main_process_first(desc="prediction dataset map pre-processing"):
            predict_dataset = predict_examples.map(
                preprocess_validation_function,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                remove_columns=column_names,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on prediction dataset",
            )
        if data_args.max_predict_samples is not None:
            # During Feature creation dataset samples might increase, we will select required samples again
            max_predict_samples = min(len(predict_dataset), data_args.max_predict_samples)
            predict_dataset = predict_dataset.select(range(max_predict_samples))

    # Data collator
    label_pad_token_id = -100 if data_args.ignore_pad_token_for_loss else tokenizer.pad_token_id
    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        label_pad_token_id=label_pad_token_id,
        pad_to_multiple_of=8 if training_args.fp16 else None,
    )

    if data_args.version_2_with_negative:
        metric = evaluate.load("dev/training/context_extraction/metrics/squad_v2.py")
    else:
        # TODO: Download squad evaluation script for offline use.
        metric = evaluate.load("squad", cache_dir=model_args.cache_dir)

    def compute_metrics(p: EvalPrediction):
        return metric.compute(predictions=p.predictions, references=p.label_ids, questions=p.inputs)

    # Post-processing:
    def post_processing_function(
        examples: datasets.Dataset, features: datasets.Dataset, outputs: EvalLoopOutput, stage="eval"
    ):
        # Decode the predicted tokens.
        preds = outputs.predictions
        if isinstance(preds, tuple):
            preds = preds[0]
        # Replace -100s used for padding as we can't decode them
        preds = np.where(preds != -100, preds, tokenizer.pad_token_id)
        decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)

        # Build a map example to its corresponding features.
        example_id_to_index = {k: i for i, k in enumerate(examples["id"])}
        feature_per_example = {example_id_to_index[feature["example_id"]]: i for i, feature in enumerate(features)}
        predictions = {}
        # Let's loop over all the examples!
        for example_index, example in enumerate(examples):
            # This is the index of the feature associated to the current example.
            feature_index = feature_per_example[example_index]
            predictions[example["id"]] = decoded_preds[feature_index]
        
        # Format the result to the format the metric expects.
        if data_args.version_2_with_negative:
            formatted_predictions = [
                {"id": k, "prediction_text": v, "no_answer_probability": 0.0} for k, v in predictions.items()
            ]
        else:
            formatted_predictions = [{"id": k, "prediction_text": v} for k, v in predictions.items()]

        references = [{"id": ex["id"], "answers": ex[answer_column]} for ex in examples]
        input_questions = [{"id": ex["id"], "question": ex["question"]} for ex in examples]
        return EvalPrediction(predictions=formatted_predictions, label_ids=references, inputs=input_questions)

        
    if hyperpar_search_args.do_hyperparameter_search and training_args.do_train:

        def model_init(trial):
            return AutoModelForSeq2SeqLM.from_pretrained(
                model_args.model_name_or_path,
                from_tf=bool(".ckpt" in model_args.model_name_or_path),
                config=config,
                cache_dir=model_args.cache_dir,
                revision=model_args.model_revision,
            )
    

        def hyperparameter_space(trial):
            return {
                "learning_rate": trial.suggest_float(
                    "learning_rate", 1e-6, 1e-3, log=True
                ),
                # "per_device_train_batch_size": trial.suggest_categorical(
                #     "per_device_train_batch_size", [16, 32]
                # ),
                # "weight_decay": trial.suggest_categorical(
                #     "weight_decay", [0.0, 0.01]
                # ),
                # "warmup_steps": trial.suggest_categorical(
                #     "warmup_steps", [0, 50, 500, 1000]
                # ),
                # "lr_scheduler_type": trial.suggest_categorical(
                #     "lr_scheduler_type", ["linear", "cosine"]
                # ),
                # "optim": trial.suggest_categorical(
                #     "optim", ["adamw_torch", "adafactor"]
                # ),
                # When adding new hyperparameters, make sure that there is a corresponding field in `TrainingArguments`.
                # If there is no corresponding field, you will get a warning in the logs like:
                # "Trying to set some_param_that_does_not_exist in the hyperparameter search but there is no corresponding field in `TrainingArguments`.""
                # "num_train_epochs": trial.suggest_int("num_train_epochs", 1, 10),s
            }

        def hyperparameter_search_objective(metrics: dict):
            """Objective function for hyperparemter tuning.
            Metrics includes the following keys:
                eval_loss, eval_precision, eval_recall, eval_f1, eval_accuracy,
                eval_runtime, eval_samples_per_second, eval_steps_per_second, epoch
            """
            return metrics["eval_f1"]        

        hp_search_trainer = QuestionAnsweringSeq2SeqTrainer(
            model=None,
            model_init=model_init,
            args=training_args,
            train_dataset=train_dataset if training_args.do_train else None,
            eval_dataset=eval_dataset if training_args.do_eval else None,
            eval_examples=eval_examples if training_args.do_eval else None,
            tokenizer=tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics if training_args.predict_with_generate else None,
            post_process_function=post_processing_function,            
        )

        hp_study_name = training_args.output_dir.split("/")[-1]
        hp_results_storage_path = os.path.join(
            os.getcwd(),
            hyperpar_search_args.hp_results_path,
            f"{hp_study_name}.db",
        )
        best_trial = hp_search_trainer.hyperparameter_search(
            direction="maximize",
            backend="optuna",
            hp_space=hyperparameter_space,
            n_trials=int(hyperpar_search_args.hp_tuning_n_trials),
            compute_objective=hyperparameter_search_objective,
            study_name=hp_study_name,
        )
        print("👑 Best hyperparameter set found:")
        print(best_trial)

        # Update training args
        training_args.learning_rate = best_trial.hyperparameters["learning_rate"]
        if "per_device_train_batch_size" in best_trial.hyperparameters:
            training_args.per_device_train_batch_size = best_trial.hyperparameters["per_device_train_batch_size"]
    
    # Get optimizer and learning rate scheduler.
    # Recommended settings for T5 according to https://discuss.huggingface.co/t/t5-finetuning-tips/684/
    # Recommended setting 1
    optimizer = Adafactor(model.parameters(), scale_parameter=False, relative_step=False, warmup_init=False, lr=training_args.learning_rate)
    lr_scheduler = None
    # Recommended setting 2
    # optimizer = Adafactor(model.parameters(), scale_parameter=True, relative_step=True, warmup_init=True, lr=None)
    # lr_scheduler = AdafactorSchedule(optimizer)
    

    # Initialize our Trainer
    trainer = QuestionAnsweringSeq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset if training_args.do_train else None,
        eval_dataset=eval_dataset if training_args.do_eval else None,
        eval_examples=eval_examples if training_args.do_eval else None,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics if training_args.predict_with_generate else None,
        post_process_function=post_processing_function,
        optimizers=(optimizer, lr_scheduler),
    )


    # Training
    if training_args.do_train:
        checkpoint = None
        if training_args.resume_from_checkpoint is not None:
            checkpoint = training_args.resume_from_checkpoint
        elif last_checkpoint is not None:
            checkpoint = last_checkpoint
        train_result = trainer.train(resume_from_checkpoint=checkpoint)
        trainer.save_model()  # Saves the tokenizer too for easy upload

        metrics = train_result.metrics
        max_train_samples = (
            data_args.max_train_samples if data_args.max_train_samples is not None else len(train_dataset)
        )
        metrics["train_samples"] = min(max_train_samples, len(train_dataset))

        trainer.log_metrics("train", metrics)
        trainer.save_metrics("train", metrics)
        trainer.save_state()

    # Evaluation
    results = {}
    max_length = (
        training_args.generation_max_length
        if training_args.generation_max_length is not None
        else data_args.val_max_answer_length
    )
    num_beams = data_args.num_beams if data_args.num_beams is not None else training_args.generation_num_beams
    if training_args.do_eval:
        logger.info("*** Evaluate ***")
        metrics = trainer.evaluate(max_length=max_length, num_beams=num_beams, metric_key_prefix="eval")

        max_eval_samples = data_args.max_eval_samples if data_args.max_eval_samples is not None else len(eval_dataset)
        metrics["eval_samples"] = min(max_eval_samples, len(eval_dataset))

        trainer.log_metrics("eval", metrics)
        trainer.save_metrics("eval", metrics)

    # Prediction
    if training_args.do_predict:
        logger.info("*** Predict ***")
        print("Settings:")
        print(f"max_length: {max_length}")
        print(f"num_beams: {num_beams}")
        results = trainer.predict(predict_dataset, predict_examples, max_length=max_length, num_beams=num_beams)
        metrics = results.metrics

        max_predict_samples = (
            data_args.max_predict_samples if data_args.max_predict_samples is not None else len(predict_dataset)
        )
        metrics["predict_samples"] = min(max_predict_samples, len(predict_dataset))

        trainer.log_metrics("predict", metrics)
        trainer.save_metrics("predict", metrics)

        # Save predictions and groundtruths.                
        wrong_predictions = []        
        all_predictions = []  
        for predictions, example in zip(results.predictions, predict_examples):
            assert predictions["id"] == example["id"]
            prediction_answer_text = predictions["prediction_text"]
            prediction_no_answer_probability = predictions.get("no_answer_probability")
            ds_context = example["context"]
            ds_question = example["question"]
            ds_answer_text = ", ".join(example["answers"]["text"])

            p = {
                "context": ds_context,
                "question": ds_question,
                "groundtruth": ds_answer_text,
                "predictions": prediction_answer_text,
                "predictions_no_answer_probability": prediction_no_answer_probability,
            }

            all_predictions.append(p)
            if prediction_answer_text != ds_answer_text:
                wrong_predictions.append(p)

        all_predictions_file = os.path.join(training_args.output_dir, "predictions.json")
        wrong_predictions_file = os.path.join(training_args.output_dir, "wrong_predictions.json")

        if trainer.is_world_process_zero():
    
            import json
            with open(all_predictions_file, "w") as writer:
                json.dump(all_predictions, writer, indent=4, ensure_ascii=False)

            with open(wrong_predictions_file, "w") as writer:
                json.dump(wrong_predictions, writer, indent=4, ensure_ascii=False)

    if training_args.push_to_hub:
        kwargs = {"finetuned_from": model_args.model_name_or_path, "tasks": "question-answering"}
        if data_args.dataset_name is not None:
            kwargs["dataset_tags"] = data_args.dataset_name
            if data_args.dataset_config_name is not None:
                kwargs["dataset_args"] = data_args.dataset_config_name
                kwargs["dataset"] = f"{data_args.dataset_name} {data_args.dataset_config_name}"
            else:
                kwargs["dataset"] = data_args.dataset_name

        trainer.push_to_hub(**kwargs)


def _mp_fn(index):
    # For xla_spawn (TPUs)
    main()


if __name__ == "__main__":
    main()
