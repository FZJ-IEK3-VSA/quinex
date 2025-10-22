from transformers import AutoTokenizer, T5Tokenizer

# Check how the tokenizers split the input text into tokens.
quantity_identification_model_name = "JuelichSystemsAnalysis/quinex-quantity-v0-124M"
context_extraction_model_name = "JuelichSystemsAnalysis/quinex-context-v0-783M"

quantity_identification_tokenizer = AutoTokenizer.from_pretrained(quantity_identification_model_name, use_fast=True)
context_extraction_tokenizer = T5Tokenizer.from_pretrained(context_extraction_model_name, use_fast=True, legacy=False)

def show_tokenization(tokenizer, test_str):
    token_ids = tokenizer(test_str, return_tensors="pt").input_ids
    token_ids = [int(a) for a in token_ids[0]]
    tokens_labels = [tokenizer._convert_id_to_token(t) for t in token_ids]

    print(f"String: \"{test_str}\"")
    print("Tokens:", tokens_labels)
    print("Token IDs:", token_ids)

test_str = "The apple falls with a speed of 123 or 1.213 m/s."

print("Tokenizer used in quantity span identification:")
show_tokenization(quantity_identification_tokenizer, test_str)

print("Tokenizer used in measurement context extraction:")
show_tokenization(context_extraction_tokenizer, test_str)


