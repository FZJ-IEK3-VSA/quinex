DATA_DIR = '../path/to/datasets/'
MODEL_DIR = '/path/to/model/model_checkpoints/'
RUNS=[   
    {
        "seed": 123,
        "epochs": [16, 36],
        "train_sets": [     
            "wiki_measurements/data_publication/Wiki-Quantities/preprocessed/wiki-quantities_large_silver_train.json",
            "merged_ner/preprocessed/quantity_ner/noisy_wo_wikim_and_curated_train/post_processed_deduplicated_balanced/merged_ner_without_wiki_measurements_quantity_ner_all_splits.json"
        ],            
        "dev_sets": [            
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_dev.json",
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_dev.json",
        ],
        "test_sets": [            
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_test.json",
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_test.json",
        ],
        "models": ["climatebert/distilroberta-base-climate-f", "nasa-impact/nasa-smd-ibm-distil-v0.1"],
        "hyperparameter_optimization": True,
        "number_of_hp_search_trials": 10,
        "learning_rate": [
                ["6.482684809377914e-05"],
                ["6.482684809377914e-05"],
        ],
        "per_device_train_batch_size": ["16", "16"],
        "mask_ratio": [0, 0],
    },
    {
        "seed": 2,
        "epochs": [16],
        "train_sets": [            
            "wiki_measurements/data_publication/Wiki-Quantities/preprocessed/wiki-quantities_large_silver_train.json",            
        ],            
        "dev_sets": [            
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_dev.json",            
        ],
        "test_sets": [            
            "merged_ner/preprocessed/quantity_ner/curated/post_processed_deduplicated_balanced/merged_ner_quantity_ner_test.json",            
        ],
        "models": ["climatebert/distilroberta-base-climate-f", "nasa-impact/nasa-smd-ibm-distil-v0.1"],
        "hyperparameter_optimization": True,
        "number_of_hp_search_trials": 10,
        "learning_rate": [
                ["6.482684809377914e-05"],
                ["6.482684809377914e-05"],
        ],
        "per_device_train_batch_size": ["16", "16"],
        "mask_ratio": [0, 0],
    },
]