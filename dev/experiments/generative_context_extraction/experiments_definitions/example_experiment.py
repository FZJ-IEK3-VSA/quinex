DATA_DIR = '../path/to/datasets/'
MODEL_DIR = '/path/to/model/model_checkpoints/'
RUNS = [
    {        
        "seed": 493,
        "epochs": [20, 35],
        "train_sets": [
            "merged_qa/preprocessed/context_qa/noisy/{variant}/merged_qa_context_qa_all_splits.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_train.json",
        ],
        "dev_sets": [
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_dev.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_dev.json",
        ],
        "test_sets": [
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_test.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_test.json",
        ],
        "models": ["google/flan-t5-base"],
        "hyperparameter_optimization": True,
        "number_of_hp_search_trials": [10],
        "learning_rate": [["4e-05", "4e-05"]],
        "per_device_train_batch_size": ["16"],
        "gradient_accumulation_steps": ["1"],
        "fp16": False,
        "bf16": False,
        "variants": [
            "context_extraction_dataset_only_entity_and_property",
            "context_extraction_dataset_only_entity_and_property_wo_questions_marked",
            "context_extraction_dataset_w_qualifiers",
            "context_extraction_dataset_w_qualifiers_wo_entity_and_questions_marked",
            "context_extraction_dataset_w_qualifiers_wo_entity_marked",
            "context_extraction_dataset_w_qualifiers_wo_questions_marked",
        ],
        "keep_examples_based_on_id_substring": [[],[]],
        "remove_examples_based_on_id_substring": [[],[]],
    }, 
        {
        "seed": 123,
        "epochs": [20, 35],
        "train_sets": [
            "merged_qa/preprocessed/context_qa/noisy/{variant}/merged_qa_context_qa_all_splits.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_train.json",
        ],
        "dev_sets": [
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_dev.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_dev.json",
        ],
        "test_sets": [
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_test.json",
            "merged_qa/preprocessed/context_qa/curated/{variant}/merged_qa_context_qa_test.json",
        ],
        "models": ["google/flan-t5-small", "google/flan-t5-base", "google/flan-t5-large"],         
        "hyperparameter_optimization": True,
        "number_of_hp_search_trials": [100, 36, 12],
        "learning_rate": [["4e-05", "4e-05"], ["4e-05", "4e-05"], ["4e-05", "4e-05"]],
        "per_device_train_batch_size": ["16", "16", "8"],
        "gradient_accumulation_steps": ["1", "1", "2"],
        "fp16": False,
        "bf16": False,
        "variants": ["context_extraction_dataset_w_qualifiers_wo_questions_marked"],
        "keep_examples_based_on_id_substring": [[],[]],
        "remove_examples_based_on_id_substring": [[],[]],
    },  
]