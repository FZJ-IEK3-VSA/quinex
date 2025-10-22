import math
from transformers import (
    pipeline,
    T5Tokenizer,
    AutoTokenizer,    
    AutoModelForTokenClassification,        
    AutoModelForSequenceClassification,
    T5ForConditionalGeneration
)


def load_transformers_pipe(task, model_path, device, batch_size=8, dtype="auto", verbose=False, max_new_tokens: int=50, local_files_only: bool=False):
    """
    Load model, tokenizer and create a pipeline object.
    """
    
    # Get tokenizer and model.
    if task == "token-classification":
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, local_files_only=local_files_only, model_max_length=512)
        model = AutoModelForTokenClassification.from_pretrained(model_path, local_files_only=local_files_only)
        kwargs = {"aggregation_strategy": "simple"}
    elif task == "text-classification":
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, local_files_only=local_files_only)
        model =  AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=local_files_only)
        kwargs = {"top_k": None}
    elif task == "text2text-generation":
        tokenizer = T5Tokenizer.from_pretrained(model_path, use_fast=True, local_files_only=local_files_only, legacy=False)
        model = T5ForConditionalGeneration.from_pretrained(model_path, local_files_only=local_files_only)
        kwargs = {"max_new_tokens": max_new_tokens}        
    else:
        raise ValueError(f"Task {task} not supported.")

    new_pipe = pipeline(
        task=task,
        model=model,
        tokenizer=tokenizer,
        batch_size=batch_size,
        torch_dtype=dtype,
        device=device,
        **kwargs
    )

    if verbose:
        print(f'Loaded {task} model on device "{device}" ✅')

    return new_pipe


def get_text_chunking_helper(model_name, task, local_files_only: bool=False):
    """
    Get a helper function that counts the number of tokens in a text.
    """

    # Load tokenizer.
    if task == "text2text-generation":
        tokenizer = T5Tokenizer.from_pretrained(model_name, use_fast=True, legacy=False, local_files_only=local_files_only)
    elif task in ["token-classification", "text-classification"]:
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True, local_files_only=local_files_only)
    else:
        raise ValueError(f"Task {task} not supported.")
    
    # Check if tokenizer max length is power of two .
    if math.log2(tokenizer.model_max_length) % 1 != 0:
        raise Warning(f"Max. token length probably not correct: Model {model_name} has a maximum length of {tokenizer.model_max_length} which is not a power of two.")
    
    # Remember the maximum length of the model.
    max_chunk_size = tokenizer.model_max_length
    
    # Overwrite the maximum length for the tokenizer with a value that is almost 
    # certain to never be reached to avoid printing info on maximum length surpassed.
    tokenizer.model_max_length = 1_000_000_000

    # Get a function that counts the number of tokens in a text.
    token_counter = lambda text: len(tokenizer.tokenize(text))

    return token_counter, max_chunk_size





