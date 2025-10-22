import json
import yaml
from typing import Annotated
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import RedirectResponse
import uvicorn
from pydantic import BaseModel
from quinex import Quinex, __version__
from quinex.config.presets import models, tasks


app = FastAPI(
    title="Quinex Background Inference Service API",
    version=__version__
)

# ==========================================
# =                Settings                =
# ==========================================

use_cpu = True
models = models.base
tasks = tasks.full

batch_size_quantity_model = 256
batch_size_context_model = 64
batch_size_statement_clf_model = 64

workers_for_quantity_model = 1
workers_for_context_model = 3
workers_for_statement_clf_model = 1

device_ranks_for_quantity_model = [0]
device_ranks_for_context_model = [0]
device_ranks_for_statement_clf_model = [0]


# ==========================================
# =          Initialize pipelines          =
# ==========================================
   
parallel_worker_device_map = {
    'quantity_model': {
        'n_workers': workers_for_quantity_model,
        'gpu_device_ranks': device_ranks_for_quantity_model,
        'batch_size': batch_size_quantity_model
    },   
    'context_model': {
        'n_workers': workers_for_context_model,
        'gpu_device_ranks': device_ranks_for_context_model,
        'batch_size': batch_size_context_model
        },    
    'qualifier_model': {
        'n_workers': workers_for_context_model,
        'gpu_device_ranks': device_ranks_for_context_model,
        'batch_size': batch_size_context_model
        },         
    'statement_clf_model': {
        'n_workers': workers_for_statement_clf_model,
        'gpu_device_ranks': device_ranks_for_statement_clf_model,
        'batch_size': batch_size_statement_clf_model
    }
}   

quinex = Quinex(**models, **tasks, use_cpu=use_cpu, parallel_worker_device_map=parallel_worker_device_map)


# ==========================================
# =             API Endpoints              =
# ==========================================
@app.get("/", include_in_schema=False)
def home():    
    # Redirect to API docs.
    return RedirectResponse("./docs")

@app.get("/api/is_alive/", tags=["Special Endpoints"])
def is_alive():    
    return {"detail": "Alive and kicking!"}



example_text = "If you stack a gazillion giraffes, they would have a total height greater than 100 meters. The bottom giraffe would be exposed to a pressure of more than 10^5 Pa (see Figure 3)."
@app.post("/api/process_text/", tags=["Predict"])
def process_text(text: Annotated[str, Body(examples=[example_text])], skip_imprecise_quantities: bool=True, add_curation_fields: bool=False):

    if text == None:
        raise HTTPException(status_code=400, detail='Missing text in request body in form of json={"text": "Some text."}')
    elif type(text) != str:
        raise HTTPException(status_code=400, detail='Text must be of type string.')
    
    print("Applying pipeline to text:", text)

    # Send text through the models.
    print("Applying pipeline to text...")
    predictions = quinex(text, skip_imprecise_quantities=skip_imprecise_quantities, add_curation_fields=add_curation_fields)

    return {"predictions": json.dumps({"quantitative_statements": predictions}, ensure_ascii=False)}


class TextAndQuantity(BaseModel):
    text: str
    quantity_start_char: int
    quantity_end_char: int
    quantity_surface: str

    class Config:
        schema_extra = {
            "example": {
                "text": "If you stack a gazillion giraffes, they would have a total height greater than 100 meters. The bottom giraffe would be exposed to a pressure of more than 10^5 Pa (see Figure 3).",
                "quantity_start_char": 79,
                "quantity_end_char": 89,
                "quantity_surface": "100 meters"
            }
        }

@app.post("/api/get_claim_for_given_quantity/", tags=["Predict"])
def get_claim_for_given_quantity_endpoint(text_and_quantity: TextAndQuantity):
    
    text = text_and_quantity.text
    if text == None:
        raise HTTPException(status_code=400, detail='Missing text in request body in form of json={"text": "Some text."}')
    elif type(text) != str:
        raise HTTPException(status_code=400, detail='Text must be of type string.')
    
    quantity_start_char = text_and_quantity.quantity_start_char
    quantity_end_char = text_and_quantity.quantity_end_char
    quantity_surface = text_and_quantity.quantity_surface

    if type(quantity_start_char) != int or type(quantity_end_char) != int:
        raise HTTPException(status_code=400, detail='Quantity start and end char must be of type int.')
    elif type(quantity_surface) != str:
        raise HTTPException(status_code=400, detail='Quantity surface must be of type string.')
    elif quantity_start_char >= quantity_end_char:
        raise HTTPException(status_code=400, detail='Quantity start char must be smaller than quantity end char.')
    elif text[quantity_start_char:quantity_end_char] != quantity_surface:
        raise HTTPException(status_code=400, detail='Quantity surface does not match the text between quantity start and end char.')

    quantity = {
        "start": quantity_start_char,
        "end": quantity_end_char,        
        "text": quantity_surface
    }    

    # Send text through the models.
    print("Applying pipeline to text...")
    prediction = quinex.get_claim_for_given_quantity(text, quantity)

    return {"quantitative_statement": prediction}


if __name__ == '__main__':
        
    parser = ArgumentParser()
    parser.add_argument(
        "--config_path",
        default="./services/paper_analysis_service/config/config.yml",
        help="""Path to the configuration file with parent dir as key and host and port as values.""",
    )    
    args = parser.parse_args()
    
    with open(args.config_path, "r") as f:
        config = yaml.safe_load(f)

    this_config = config[__file__.split("/")[-2]]

    uvicorn.run(app, port=this_config["port"], host=this_config["host"])