The training and evaluation scripts, metrics, and helpers are based on code from The HuggingFace Inc. team distributed as part of [HuggingFace transformers library](https://github.com/huggingface/transformers) and the [HuggingFace evaluate library](https://github.com/huggingface/evaluate), which are licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0), and have been partly modified. The respective files are:

* Metrics
    * `./dev/training/context_extraction/metrics/compute_score.py`
    * `./dev/training/quantity_extraction/metrics/seqeval.py`
    * `./dev/training/statement_type_classification/metrics/accuracy.py`
    * `./dev/training/context_extraction/metrics/squad_v2.py`
* Training scripts
    * `./dev/training/context_extraction/generative_QA_with_seq2seq_encoder_decoder_models/trainer_seq2seq_qa.py`
    * `./dev/training/context_extraction/generative_QA_with_seq2seq_encoder_decoder_models/run_seq2seq_qa.py`
    * `./dev/training/context_extraction/helpers/qa_utils.py`
    * `./dev/training/quantity_extraction/sequence_labeling_with_autoencoding_encoder_models/run_ner.py`
    * `./dev/training/statement_type_classification/run_classification.py`

A copy of the Apache License, Version 2.0 is included in this directory.