import os
from wasabi import msg
from argparse import ArgumentParser
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModel,
    AutoModelForTokenClassification,
    AutoModelForQuestionAnswering,
    AutoModelForSeq2SeqLM,
    OPTForCausalLM,
)


parser = ArgumentParser()
parser.add_argument(
    "--model_name",
    default="roberta-base",
    help="""Name of model in HuggingFace hub.""",
)
parser.add_argument(
    "--save_to",
    default="./experiments/quantity_extraction/model_checkpoints/roberta_base",
    help="""Directory to save model and tokenizer to.""",
)
parser.add_argument(
    "--task",
    choices=["quantity_ner", "context_qa", "lm", "statement_type_clf"],
    default="quantity_ner",
)

# Prepare and print info.
args = parser.parse_args()
model_url = "https://huggingface.co/" + args.model_name

# Load pretrained model and tokenizer.
if args.task == "quantity_ner":
    num_labels = len(["O", "B-Quantity", "I-Quantity"])
    config = AutoConfig.from_pretrained(
        args.model_name,
        num_labels=num_labels,
        finetuning_task="ner",
        use_auth_token=None,
    )
    tokenizer_name_or_path = args.model_name
    if config.model_type in {"bloom", "gpt2", "roberta"}:
        tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name_or_path,
            use_fast=True,
            add_prefix_space=True,
        )
    else:
        tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name_or_path,
            use_fast=True,
        )

    model = AutoModelForTokenClassification.from_pretrained(
        args.model_name,
        from_tf=False,
        config=config,
        ignore_mismatched_sizes=False,
    )
elif args.task == "context_qa":
    config = AutoConfig.from_pretrained(
        args.model_name,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        use_fast=True,
    )
    if config.model_type in {"t5"}:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            args.model_name,
            from_tf=False,
            config=config,
        )
    elif config.model_type in {"opt"}:
        model = OPTForCausalLM.from_pretrained(args.model_name)
    else:
        model = AutoModelForQuestionAnswering.from_pretrained(
            args.model_name,
            from_tf=False,
            config=config,
        )
elif args.task == "lm":
    model = OPTForCausalLM.from_pretrained(args.model_name)
elif args.task == "statement_type_clf" and args.model_name.startswith(
    "sentence-transformers"
):
    # from sentence_transformers import SentenceTransformer
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModel.from_pretrained(args.model_name)
else:
    raise ValueError("Unknown task.")

# Save model and tokenizert
tokenizer.save_pretrained(args.save_to)
model.save_pretrained(args.save_to)
msg.good(f"Successfully saved model and tokenizer from {model_url} to {args.save_to}.")
