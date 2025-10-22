import os
import json
import numpy as np
import matplotlib.pyplot as plt
from transformers import (
    AutoConfig,
    AutoTokenizer,
)


DATA_DIR = '../measurement-extraction-datasets/datasets/'
dataset_paths = [    
    "merged_qa/preprocessed/context_qa/curated/best_config_no_weak_accepts_added_context_w_qualifiers_wo_questions_marked_20240723/merged_qa_context_qa_train.json",
    "merged_qa/preprocessed/context_qa/curated/best_config_no_weak_accepts_added_context_w_qualifiers_wo_questions_marked_20240723/merged_qa_context_qa_dev.json",
    "merged_qa/preprocessed/context_qa/curated/best_config_no_weak_accepts_added_context_w_qualifiers_wo_questions_marked_20240723/merged_qa_context_qa_test.json",
    "merged_qa/preprocessed/context_qa/noisy/best_config_no_weak_accepts_added_context_w_qualifiers_wo_questions_marked_20240723/merged_qa_context_qa_all_splits.json",
]

task = "context_qa"  # "quantity_ner" or "context_qa"

if task == "quantity_ner":
    max_token_length = 512
    model_name = "roberta-large"
    check_answers_not_questions = None
elif task == "context_qa":
    max_token_length = 512
    model_name = "google/flan-t5-base" 
    check_answers_not_questions = True
else:
    raise ValueError(f"Task {task} not supported.")


# Load tokenizer.
config = AutoConfig.from_pretrained(
    model_name,
    num_labels=3,
    finetuning_task="ner",
    cache_dir=None,
    revision=None,
    use_auth_token=None,
)

if config.model_type in {"bloom", "gpt2", "roberta"}:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=None,
        use_fast=True,
        revision=None,
        use_auth_token=None,
        add_prefix_space=True,
    )
else:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=None,
        use_fast=True,
        revision=None,
        use_auth_token=None,
    )

# Iterate over datasets.
count = 0
word_tokenization = []
subword_tokenization = []
for dataset_path in dataset_paths:
    # Load dataset.
    with open(os.path.join(DATA_DIR, dataset_path)) as f:
        dataset = json.load(f)

    print(f"Max. token length violations in {dataset_path}:")

    # Iterate over examples.    
    for example in dataset["data"]:

        # Check if example is not too long.
        if task == "quantity_ner":
            tokenized_inputs = tokenizer(
                example["tokens"],
                padding=False ,
                truncation=False,
                max_length=None,            
                is_split_into_words=True,
            )
        elif task == "context_qa":
            assert len(example["answers"]["text"]) < 2, "Only one answer is supported."
            input_str = "".join(example["answers"]["text"]) if check_answers_not_questions else example["question"] + example["context"] 

            tokenized_inputs = tokenizer(
                input_str,
                padding=False ,
                truncation=False,
                max_length=None,            
                is_split_into_words=False,
            )

        else:
            raise ValueError(f"Task {task} not supported.")

        subword_tokenization_len = len(tokenized_inputs["input_ids"])        
        subword_tokenization.append(subword_tokenization_len)

        if task == "quantity_ner":
            word_tokenization.append(len(example["tokens"]))

        if subword_tokenization_len > max_token_length:
            count += 1
            if task == "quantity_ner":
                print("\n- Target:", example["target"])
                print("  First tokens:", example["tokens"][0:10])     
            elif task == "context_qa":
                print("\n- Target:", example["id"])
                print("\n- Question:", example["question"])
                print("  Context:", example["context"][0:130])

print(f"Number of examples with more than {max_token_length} tokens: ", count)

print(f"Max. token length: {max(subword_tokenization)}")

# Plot gaussian distribution of token lengths.
fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
plt.hist(subword_tokenization, bins=100, alpha=0.75, color='b', density=True, histtype="step", cumulative=True, label="Cumulative histogram")
ax.set_ylim(0.95, 1.0)
ax.grid(True)
ax.legend()
ax.set_xlabel("Number of Tokens")
ax.set_ylabel("Percentage of all data")
ax.label_outer()
plt.show()

# save the figure
plt.savefig("token_len_distribution.png")

mu = 200
sigma = 25
n_bins = 25
data = np.array(subword_tokenization)

fig = plt.figure(figsize=(9, 4), layout="constrained")
axs = fig.subplots(1, 2, sharex=True, sharey=True)

# Cumulative distributions.
axs[0].ecdf(data, label="CDF")
n, bins, patches = axs[0].hist(data, n_bins, density=True, histtype="step",
                               cumulative=True, label="Cumulative histogram")
x = np.linspace(data.min(), data.max())
y = ((1 / (np.sqrt(2 * np.pi) * sigma)) *
     np.exp(-0.5 * (1 / sigma * (x - mu))**2))
y = y.cumsum()
y /= y[-1]
axs[0].plot(x, y, "k--", linewidth=1.5, label="Theory")

# Complementary cumulative distributions.
axs[1].ecdf(data, complementary=True, label="CCDF")
axs[1].hist(data, bins=bins, density=True, histtype="step", cumulative=-1,
            label="Reversed cumulative histogram")
axs[1].plot(x, 1 - y, "k--", linewidth=1.5, label="Theory")

# Label the figure.
fig.suptitle("Cumulative distributions")
for ax in axs:
    ax.grid(True)
    ax.legend()
    ax.set_xlabel("Annual rainfall (mm)")
    ax.set_ylabel("Probability of occurrence")
    ax.label_outer()

plt.show()

if task == "quantity_ner":
    print(f"The average ratio between number of subword and word tokens is {sum(subword_tokenization)/sum(word_tokenization)}")
    ratios = []
    for subword_token_len, word_token_len in zip(subword_tokenization, word_tokenization):
        ratios.append(subword_token_len/word_token_len)
    print(f"The minimum and maximum ratio between number of subword and word tokens is {min(ratios)} and {max(ratios)}, respectively.")

print("Done.")
