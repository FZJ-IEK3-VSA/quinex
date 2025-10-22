The majority of quinex is licensed under the MIT License. 
The text of this license is included below.

Exceptions are:

------------------------------------------------------------------------------

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

A copy of the Apache License, Version 2.0 is included in the training directory [`./dev/training/`](./dev/training/LICENSE).

------------------------------------------------------------------------------

The country codes data included in `./src/quinex/normalize/spatial_scope/static_resources/country_codes_mapping.json` was downloaded from https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/master/all/all.json and is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/). The file has been modfied to include this provenance information.

------------------------------------------------------------------------------

For more information, check the respective original author's repositories.




MIT license text valid for the majority of quinex:
------------------------------------------------------------------------------

MIT License

Copyright (c) 2025 FZJ ICE-2

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.                      