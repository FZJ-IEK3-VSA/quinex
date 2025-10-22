import os
import io
import re
import json
import time
from datetime import datetime
import zipfile
import hashlib
import requests
from pathlib import Path
from wasabi import msg
from thefuzz import fuzz
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
from text_processing_utils.locate import locate_span_in_context
from quinex.documents.validate import has_valid_extension
from typing import Annotated
from pydantic import BaseModel
from pydantic.types import constr
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from quinex.documents.papers.parse.helpers.transform import post_process_parsed_json, s2orc_json_to_string
from quinex.documents.papers.download.select_papers import select_papers
from quinex.documents.papers.download.helpers.openalex import get_papers_by_dois, get_papers_by_search_query
from quinex.documents.papers.download.download_papers import download_papers, download_paper_by_doi
from quinex.documents.papers.parse.parse_papers import parse_papers
from quinex.documents.papers.download.helpers.openalex import search_paper_by_title, inverted_index_to_text
from quinex.normalize.references.grobid import normalize_references
from manage_analyses_api.utils.normalize import bulk_analysis_qualifier_normalization_wrapper
from manage_analyses_api.utils.schema import (
    NormalizedQuantity,
    AnnotationType,
    NormalizationType,
    ClassificationType,
    QualifierAnnotationTypes,
    QuantityTypeClasses,
    StatementTypeClasses,
    StatementRationalClasses,
    StatementSystemClasses,
    OpenAlexFilters,
    analysis_name_constr,
)
from manage_analyses_api.config.get_config import CONFIG, PAPER_ANALYSIS_SERVICES_DIR, ANNOTATION_SERVICE_URL, BATCH_ANNOTATION_SERVICE_URL, get_analysis_dir, get_papers_dir
if CONFIG["manage_analyses_api"]:
    PAPER_COLLECTION = None
    from manage_analyses_api.store.disk_operations import save_paper_dict_on_disk as store_paper
    from manage_analyses_api.store.disk_operations import get_all_papers_from_disk as get_all_papers
    from manage_analyses_api.store.disk_operations import get_paper_from_disk as get_paper
    from manage_analyses_api.store.disk_operations import delete_paper_from_disk as delete_paper
    from manage_analyses_api.store.disk_operations import check_paper_exists_on_disk_by_hash as check_paper_exists_by_hash    
else:
    from manage_analyses_api.store.db_operations import PAPER_COLLECTION
    from manage_analyses_api.store.db_operations import add_paper_dict_to_db as store_paper
    from manage_analyses_api.store.db_operations import get_all_papers_from_db as get_all_papers
    from manage_analyses_api.store.db_operations import get_paper_from_db as get_paper
    from manage_analyses_api.store.db_operations import delete_paper_from_db as delete_paper
    from manage_analyses_api.store.db_operations import check_paper_exists_in_db_by_hash as check_paper_exists_by_hash

# Set up logging.
# import logging
# from quinex.services.bulk_analysis.api.config.logging_config import LOGGING_CONFIG
# logging.config.dictConfig(LOGGING_CONFIG)
# logger = logging.getLogger('quinex_analysis')

app = FastAPI(
    title="Quinex API", 
    version="0.0.0",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

verbose = False


###############################################################
#           Check if configured services are alive            #
###############################################################

# Load grobid config.
grobid_config_path = PAPER_ANALYSIS_SERVICES_DIR / CONFIG["parsing_service"]["grobid_config_file_path"]
if not os.path.exists(grobid_config_path):
    raise ValueError(f"Grobid config file not found at {grobid_config_path}. Please create it according to the README.")
else:
    with open(grobid_config_path, "r", encoding="utf-8") as f:
        grobid_config = json.load(f)


def annotation_service_is_alive():
    """
    Check if the inference API is running.
    """
    is_alive_endpoint = ANNOTATION_SERVICE_URL + "is_alive/"
    print(f"Send request to {is_alive_endpoint}")
    try:
        response = requests.get(is_alive_endpoint)
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to parsing service: {e}")
        return False
    
    if response.status_code == 200 and response.text == '{"detail":"Alive and kicking!"}':
        return True
    else:
        return False
    

def batch_annotation_service_is_alive():
    """
    Check if the bulk annotation service is running.
    """
    is_alive_endpoint = BATCH_ANNOTATION_SERVICE_URL + "/is_alive/"
    print(f"Send request to {is_alive_endpoint}")
    try:
        response = requests.get(is_alive_endpoint)
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to parsing service: {e}")
        return False

    if response.status_code == 200 and response.text == '{"detail":"Alive and kicking!"}':
        return True
    else:
        return False


def parsing_service_is_alive():
    """
    Check if the PDF parsing service is running.
    """
    is_alive_endpoint = grobid_config["grobid_server"] + "isalive/"
    print(f"Send request to {is_alive_endpoint}")
    try:
        response = requests.get(is_alive_endpoint)
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to parsing service: {e}")
        return False

    if response.status_code == 200 and response.text == 'true':
        return True
    else:
        return False


if not CONFIG["quinex_api"]["enable"]:
    msg.warn("Annotation is disabled.")
elif annotation_service_is_alive():
    msg.good("Inference service is up and running! It can be reached through the SSH tunnel!")
else:
    raise Exception("The inference service is not alive or cannot be reached through the SSH tunnel (port forwarding). Please start the inference service manually or check the SSH tunnel is configured correctly. See the README.")    

if not CONFIG["on_demand_batch_processing_api"]["enable"]:
    msg.warn("Bulk annotation is disabled.")
elif batch_annotation_service_is_alive():
    msg.good("Bulk annotation service is up and running!")
else:
    raise Exception("The bulk annotation service is not alive. Please start the bulk annotation service manually. See the README.")

if not CONFIG["parsing_service"]["enable"]:
    msg.warn("Parsing is disabled.")
    grobid_client = None
    convert_tei_xml_file_to_s2orc_json = None
elif parsing_service_is_alive():
    msg.good("Parsing service is up and running!")

    # Create Grobid client.
    from grobid_client.grobid_client import GrobidClient
    from doc2json.grobid2json.tei_to_json import convert_tei_xml_file_to_s2orc_json, convert_tei_xml_soup_to_s2orc_json
    print(f"Using GROBID config at {grobid_config_path}")
    grobid_client = GrobidClient(config_path=grobid_config_path, check_server=True)
else:
    raise Exception("The parsing service is not alive. Please start the parsing service manually. See the README.")


###############################################################
#                          Functions                          #
###############################################################
def batch_annotate_papers(batch_job_payload, gpu_count: int=4): 
    print("Sending annotation job to compute node...")    
    
    endpoint_url = f'{BATCH_ANNOTATION_SERVICE_URL}/api/batch_process_papers/?mean_execution_time_per_paper_per_gpu=50&gpu_count={gpu_count}'
    headers = {'Content-type': 'application/json'}
    
    print(f"Send request to {endpoint_url}")    
    response = requests.post(endpoint_url, headers=headers, json=batch_job_payload)
    
    if response.status_code != 200:                
        print(f"Requesting the headnode API failed with error code", response.status_code, "and error message", response.text)        
        raise HTTPException(status_code=400, detail="Failed to annotate paper. Contact the admin.")
    else:
        msg.good("Paper was successfully annotated.")
                
        # TODO: Delete if requests 3.x
        # From https://blog.petrzemek.net/2018/04/22/on-incomplete-http-reads-and-the-requests-library-in-python/:
        # Check that we have read all the data as the requests library does not
        # currently enforce this.         
        expected_length = response.headers.get('Content-Length')
        if expected_length is not None:
            actual_length = response.raw.tell()
            expected_length = int(expected_length)
            if actual_length < expected_length:
                print(response.text)
                raise IOError(
                    'incomplete read ({} bytes read, {} more expected)'.format(
                        actual_length,
                        expected_length - actual_length
                    )
                )                
        
        try:
            result = response.json()
        except Exception as e:
            print(e)
            print(response)
            print(response.text)
            print(response.json())
            return []

    processed_papers = result.get("processed_papers")
                                               
    return processed_papers
    

def annotate_paper_text(paper_dict, skip_imprecise_quantities=False, worker_id=None):    
    # We send minimal information to the compute node.

    # Send annotation job to compute node.
    # Note: Since we don't want to copy the files on the disk of the compute node,
    # and sending the data in a curl command from the compute node SSH terminal 
    # results in a command too long for bash, we send the data by referencing 
    # the path to the file from the local machine. For this we created the port 
    # forwarding tunnel from the local machine to the compute node.
    print("Sending annotation job to compute node...")

    endpoint_url = f'{ANNOTATION_SERVICE_URL}/api/process_paper/?skip_imprecise_quantities={skip_imprecise_quantities}'
    headers = {'Content-type': 'application/json'}

    print(f"Send request to {endpoint_url}")
    response = requests.post(endpoint_url, headers=headers, json=paper_dict)
    
    if response.status_code != 200:
        return [], [], False
    else:
        msg.good("Paper was successfully annotated.")
                
        # TODO: Delete if requests 3.x
        # From https://blog.petrzemek.net/2018/04/22/on-incomplete-http-reads-and-the-requests-library-in-python/:
        # Check that we have read all the data as the requests library does not currently enforce this.
        expected_length = response.headers.get('Content-Length')
        if expected_length is not None:
            actual_length = response.raw.tell()
            expected_length = int(expected_length)
            if actual_length < expected_length:
                print(response.text)
                raise IOError(
                    'incomplete read ({} bytes read, {} more expected)'.format(
                        actual_length,
                        expected_length - actual_length
                    )
                )                
        
        try:
            result = response.json()
        except Exception as e:
            print(e)
            print(response)
            print(response.text)
            print(response.json())
            return [], [], False

    quantitative_statements = result.get("predictions")
    print(f"Received {len(quantitative_statements)} quantitative statements.")
    extraction_provenance = result.get("provenance")
                                               
    return quantitative_statements, extraction_provenance, True


def parse_and_extract(paper_dir, analysis_config, papers_to_process=[], skip_paper_parsing=False, skip_extraction=False, gpu_count=4):
    
    print("STEP 3: Parse papers in", paper_dir)
    if skip_paper_parsing:
        failed_parses = []
        pass
    else:        
        failed_parses = parse_papers(paper_dir, **analysis_config["parse"], papers_to_process=papers_to_process)

    print("Parsing done. Failed parses:", failed_parses)

    print("STEP 4: Extract quantitative information")
    if skip_extraction:
        total_extraction_time = 0
        average_extraction_time_per_paper = 0
        number_of_quantities = 0
        processed_papers = papers_to_process
    else:
        all_papers = []
        for subdir in paper_dir.iterdir():

            paper_file_path = subdir / "structured.json"
            if not subdir.is_dir():
                continue
            elif not subdir.name.startswith("W"):
                continue
            elif not os.path.exists(paper_file_path):
                continue
            elif len(papers_to_process) > 0 and subdir.name not in papers_to_process:
                continue
            else:
                with open(paper_file_path, "r", encoding="utf-8") as f:
                    paper = json.load(f)

                paper_id = subdir.name
                paper_dict = {"text": paper.get("text", ""), "paper_id": paper_id}
                all_papers.append(paper_dict)

        msg.info("Send batch annotation job to cluster.")
        start_extraction_time = time.time()
        batch_job_payload = {"papers": all_papers, "config": analysis_config}
        print(f"Send {len(all_papers)} papers for annotation to cluster...")
        processed_papers = batch_annotate_papers(batch_job_payload, gpu_count=gpu_count)        
        processed_papers = json.loads(processed_papers)
        total_extraction_time = time.time() - start_extraction_time
        average_extraction_time_per_paper = total_extraction_time / len(processed_papers) if len(processed_papers) > 0 else None
        print(f"Received {len(processed_papers)} processed papers.")
        print(f"The total extraction time was {total_extraction_time} s.")
        print(f"Average time per paper: {average_extraction_time_per_paper} s.")

        number_of_quantities = 0
        for paper_dict in processed_papers:

            # Open paper and add annotations.            
            paper_id = paper_dict["paper_id"]                    
            quantitative_statements = paper_dict["annotations"]["quantitative_statements"]
            number_of_quantities += len(quantitative_statements)
            extraction_provenance = paper_dict["provenance"]
            
            with open(paper_dir / paper_id / "structured.json", "r", encoding="utf-8") as f:
                paper = json.load(f)

            paper["metadata"]["provenance"]["quantitative_statements_annotations"] = extraction_provenance
            paper["annotations"]["quantitative_statements"] = quantitative_statements

            # Save paper.
            with open(paper_dir / paper_id / "structured.json", "w", encoding="utf-8") as f:
                json.dump(paper, f, indent=4, ensure_ascii=False)

    print("STEP 5: Normalize references")
    start_normalization_time = time.time()
    bulk_analysis_qualifier_normalization_wrapper(paper_dir, qualifier="references", papers_to_process=papers_to_process, revert_to_bibliographic_api=False, paper_filename="structured.json")
    bulk_analysis_qualifier_normalization_wrapper(paper_dir, qualifier="temporal_scope", papers_to_process=papers_to_process, paper_filename="structured.json")
    bulk_analysis_qualifier_normalization_wrapper(paper_dir, qualifier="spatial_scope", papers_to_process=papers_to_process, paper_filename="structured.json", extend_geo_normalization_cache=True, nice=1.1)
    
    total_normalization_time = time.time() - start_normalization_time
    
    # TODO: Better validation for json serialization, e.g., inf is out of range float

    return processed_papers, failed_parses, number_of_quantities, average_extraction_time_per_paper, total_normalization_time


def create_config_file(analysis_name, config_file_dest, only_open_access=True, only_english=True, limit=1_000, filters={'by_topic': {"enable": False, 'openalex_topic_ids': ""}, 'by_issn': {"enable": False, 'issns': ""}, 'by_search_query': {"enable": False, 'search_query': ""}}, download_timeout_per_paper_in_s=10):

    # Copy config file to results directory.
    config_file = Path(__file__).resolve().parents[1] / "config" / "batch_script.json"

    # Open config file template.
    with open(config_file, "r") as f:
        analysis_config = json.load(f)

    # Modify config.
    analysis_config["analysis_name"] = analysis_name
    analysis_config["selection"]["only_open_access"] = only_open_access
    analysis_config["selection"]["only_english"] = only_english
    analysis_config["selection"]["limit"] = limit
    analysis_config["selection"]["filters"] = filters    
    analysis_config["download"]["timeout_per_paper_in_s"] = download_timeout_per_paper_in_s

    # Save modified config to results directory.    
    with open(config_file_dest, "w") as f:
        json.dump(analysis_config, f, indent=4, ensure_ascii=False)

    return analysis_config

###############################################################
#                          Endpoints                          #
###############################################################
@app.get("/", include_in_schema=False)
def home():    
    # Redirect to API docs.
    return RedirectResponse("./docs")

@app.get("/api/is_alive/", tags=["Special Endpoints"])
def is_alive():
    return {"detail": "Alive and kicking!"}

@app.get("/api/is_alive/services", tags=["Special Endpoints"])
def is_alive_services():
    """Check if the external services are alive."""
    return {"detail": {"api": True, "extraction": annotation_service_is_alive(), "bulk_extraction": batch_annotation_service_is_alive(), "parsing": parsing_service_is_alive()}}

@app.get("/api/bulk_analysis/{analysis_name}", tags=["Bulk analysis"])
def get_bulk_analysis_endpoint(analysis_name: str):
    """Get information about a bulk analysis."""
    # Check if analysis exists.
    ANALYSIS_DIR = get_analysis_dir(analysis_name)
    if not ANALYSIS_DIR.exists():
        raise HTTPException(status_code=400, detail=f"Analysis with name {analysis_name} does not exist.")
    else:
        return True
    
@app.post("/api/bulk_analysis/{analysis_name}", tags=["Bulk analysis"])
def init_bulk_analysis_endpoint(analysis_name: str) -> dict:
    """Initialize a bulk analysis."""
    # Check if analysis exists.
    ANALYSIS_DIR = get_analysis_dir(analysis_name)
    if ANALYSIS_DIR.exists():
        raise HTTPException(status_code=400, detail=f"Analysis with name {analysis_name} already exists. Please choose another name.")
    else:
        try:
            # Create results directory.        
            ANALYSIS_DIR.mkdir(parents=False, exist_ok=False)
            PAPERS_DIR = get_papers_dir(analysis_name)
            PAPERS_DIR.mkdir(parents=False, exist_ok=False)            

        except Exception as e:
            # Unforeseen error.
            print(e)
            raise HTTPException(status_code=400, detail=f"Failed to initialize analysis with name \"{analysis_name}\". Please try again and contact the admin if the problem persists.")

        return {"detail": f"Analysis {analysis_name} was successfully initialized."}
    

paper_id_constr = constr(pattern=r"^W.*$")

class PaperIDs(BaseModel):
    paper_ids: list[paper_id_constr]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "paper_ids": ["W123124912", "W123124913"]
                }
            ]
        }
    }

#  requests.post(endpoint, json=[paper["id"] for paper in papers_to_process])
@app.post("/api/bulk_analysis/{analysis_name}/process", tags=["Bulk analysis"])
def process_bulk_analysis_endpoint(analysis_name: analysis_name_constr, gpu_count: int=1, skip_imprecise_quantities: bool=False, papers_to_process: PaperIDs=[]):
    """Process a bulk analysis.

    Args:
        analysis_name (str): Name of the analysis.
        gpu_count (int): Number of GPUs to use for processing.
        skip_imprecise_quantities (bool): Whether to skip imprecise quantities.
        papers_to_process (list): List of papers to process. If empty, all papers will be processed.

    """
    analysis_dir = get_analysis_dir(analysis_name)
    paper_dir = get_papers_dir(analysis_name)

    # Open config file template.
    with open(PAPER_ANALYSIS_SERVICES_DIR / "config" / "default_analysis.json", "r") as f:
        analysis_config = json.load(f)

    analysis_config["analysis_name"] = analysis_name
    analysis_config["quantitative_information_extraction"]["max_parallel_workers"] = gpu_count
    analysis_config["quantitative_information_extraction"]["skip_imprecise_quantities"] = skip_imprecise_quantities        

    # Save modified config to results directory.    
    with open(analysis_dir / "config.json", "w") as f:
        json.dump(analysis_config, f, indent=4, ensure_ascii=False)
    
    processed_papers, failed_parses, number_of_quantities, average_extraction_time_per_paper, total_normalization_time = parse_and_extract(paper_dir, analysis_config, papers_to_process=papers_to_process.paper_ids, skip_paper_parsing=False, skip_extraction=False, gpu_count=gpu_count)
    processed_papers_ids = [p["paper_id"] for p in processed_papers]    

    return {"detail": f"Analysis {analysis_name} was successfully processed.", "processed_papers": processed_papers_ids, "failed_parses": failed_parses, "number_of_quantities": number_of_quantities, "average_extraction_time_per_paper": average_extraction_time_per_paper, "total_normalization_time": total_normalization_time}


@app.post("/api/bulk_analysis/{analysis_name}/rerun_normalizations", tags=["Bulk analysis"])
def process_bulk_analysis_rerun_normalizations_endpoint(analysis_name: analysis_name_constr, papers_to_process: PaperIDs=[]):
    """Reruns normalization of references and the spatio-temporal scope. Quantity normalization is not affected.

    Args:
        analysis_name (str): Name of the analysis.        
        papers_to_process (list): List of papers to process. If empty, all papers will be processed.
    """

    analysis_dir = get_analysis_dir(analysis_name)
    paper_dir = get_papers_dir(analysis_name)

    # Open config file template.
    with open(analysis_dir / "config.json", "r") as f:
        analysis_config = json.load(f)
    
    _, _, _, _, total_normalization_time = parse_and_extract(paper_dir, analysis_config, papers_to_process=papers_to_process.paper_ids, skip_paper_parsing=True, skip_extraction=True)    

    return {"detail": f"Analysis {analysis_name} was successfully processed.", "total_normalization_time": total_normalization_time}


@app.post("/api/bulk_analysis/", tags=["Bulk analysis"], deprecated=True)
def bulk_analysis_endpoint(analysis_name: analysis_name_constr, filter_by: OpenAlexFilters, search_query: str="", issns: list[str] = [""], openalex_topic_ids: list[str] = [""], limit: int=1_000, only_open_access: bool=True, only_english: bool=True, force_overwrite_study: bool=False, gpu_count: int=4, download_timeout_per_paper_in_s: int=10, force_redownload_papers: bool=False, skip_imprecise_quantities: bool=False) -> dict:
    """Examples:
    - search_query: '(elmo AND "sesame street") NOT (cookie OR monster)' (see https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/search-entities)
    - issns: ['1364-0321']
    - openalex_topic_id: ['t10967']
    """
    
    # For debugging.    
    skip_paper_selection = False
    skip_download = False
    skip_paper_parsing = False
    skip_extraction = False

    new_analysis = not any(skip_paper_selection, skip_download, skip_paper_parsing, skip_extraction)

    if OpenAlexFilters.by_topic and len(openalex_topic_ids) == 0:
        raise HTTPException(status_code=400, detail="At least one OpenAlex topic ID must be provided if filtering by topic.")
    elif OpenAlexFilters.by_issn and len(issns) == 0:
        raise HTTPException(status_code=400, detail="At least one ISSN must be provided if filtering by ISSN.")
    elif OpenAlexFilters.by_search_query and len(search_query) == 0:
        raise HTTPException(status_code=400, detail="A search query must be provided if filtering by search query.")

    filters= {
        'by_topic': {"enable": filter_by == OpenAlexFilters.by_topic, 'openalex_topic_ids': openalex_topic_ids}, 
        'by_issn': {"enable": filter_by == OpenAlexFilters.by_issn, 'issns': issns}, 
        'by_search_query': {"enable": filter_by == OpenAlexFilters.by_search_query, 'search_query': search_query}
    }

    analysis_name = secure_filename(analysis_name)
    
    print("#############################################")
    print(f"Start bulk analysis for {analysis_name}")
    print("#############################################")

    ANALYSIS_DIR = get_analysis_dir(analysis_name)
    PAPER_DIR =  ANALYSIS_DIR / "papers"
    CONFIG_FILE_PATH = ANALYSIS_DIR / "config.json"

    # Init batch analysis.
    if new_analysis:
        try:
            # Create results directory.
            print(f"{ANALYSIS_DIR} does not exist. Creating it.")
            ANALYSIS_DIR.mkdir(parents=True, exist_ok=force_overwrite_study)
        except FileExistsError:
            raise HTTPException(status_code=400, detail=f"Analysis with name {analysis_name} already exists. Please choose another name or set force_overwrite_study=True.")
    
        analysis_config = create_config_file(analysis_name, CONFIG_FILE_PATH, only_open_access=only_open_access, only_english=only_english, limit=limit, filters=filters, download_timeout_per_paper_in_s=download_timeout_per_paper_in_s)
    else:
        with open(CONFIG_FILE_PATH, "r") as f:
            analysis_config = json.load(f)

    print("STEP 1: Select papers")    
    selected_papers = [] if skip_paper_selection else select_papers(ANALYSIS_DIR, analysis_config)
    if len(selected_papers) == 0 and not skip_paper_selection:
        raise HTTPException(status_code=400, detail="Found 0 papers matching your query and filters. Please adjust your query and filters. The OpenAlex API is used in the backend to search for papers. So your query must be a valid OpenAlex search query (https://openalex.org/works).")

    print("STEP 2: Download papers")    
    download_stats, papers_to_download_manually = None, None if skip_download else download_papers(ANALYSIS_DIR, analysis_config)

    print("STEP 3 and 4: Parse papers and extract information")
    processed_papers, failed_parses, number_of_quantities, average_extraction_time_per_paper, total_normalization_time = parse_and_extract(PAPER_DIR, analysis_config, skip_paper_parsing=False, skip_extraction=False, gpu_count=4)

    if verbose:
        print("STEP 5: Analyze quantitative information")
        dashboard_path = PAPER_ANALYSIS_SERVICES_DIR / "paper_analysis_service" / "ui" / "analyses_dashboard" / "index.py"
        print("You can analyze the extracted information in a dashboard by running the following command:")
        print(f"streamlit run {dashboard_path}")
        print(f"and entering the analysis name {analysis_name}\" at http://localhost:8501/.")

    return {"bulk_analysis_steps": {"paper_selection": {"success": True}, "paper_download": {"success": True, "download_stats": download_stats, "papers_to_download_manually": papers_to_download_manually}, "extraction": {"papers": len(processed_papers), "average_extraction_time_per_paper": average_extraction_time_per_paper, "total_normalization_time": total_normalization_time, "number_of_quantities": number_of_quantities}}}


doi_str = constr(pattern=r"^(https?://doi.org/)?10\.\d{4,9}/[\-\._;\(\)/:<>a-zA-Z0-9]+$")

class DOIs(BaseModel):
    dois: list[doi_str]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "dois": ["10.1016/j.joule.2021.07.007", "10.7717/peerj.4375"]
                }
            ]
        }
    }

@app.post("/api/bibliographic_metadata/search/dois", tags=["Bibliographic Sevices"])
def search_papers_by_dois(dois: DOIs) -> dict:
    """
    Search for papers in OpenAlex by DOI.
    """
    dois_ = dois.dois
    if len(dois_) == 0:
        raise HTTPException(status_code=400, detail="No DOIs were provided. Provide them in a JSON object with the key 'doi'.")        
        
    print("Searching for papers with number of DOIs:", len(dois_))
    papers_in_db = get_papers_by_dois(dois_, only_open_access=False, only_english=False, limit=None, only_basic_info=True)
    return {"papers": papers_in_db}


@app.get("/api/bibliographic_metadata/search/query", tags=["Bibliographic Sevices"])
def search_papers_by_search_query(search_query: str, only_open_access: bool=True, only_english: bool=True, limit: int=100, pub_year: str="") -> dict:
    """
    Search for papers in OpenAlex by a search query.
    """
    if len(search_query) == 0:
        raise HTTPException(status_code=400, detail="No search query was provided. Provide it as a query parameter.")

    if pub_year != "":
        try:
            pub_year_lb, pub_year_ub = pub_year.split("-")
            pub_year_lb = int(pub_year_lb)
            pub_year_ub = int(pub_year_ub)
            assert pub_year_lb <= pub_year_ub
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid publication year range. Provide it as a query parameter in the format 'YYYY-YYYY'.")

    papers_in_db = get_papers_by_search_query(search_query, only_open_access=only_open_access, only_english=only_english, pub_year=pub_year, limit=limit, only_basic_info=True)
    return {"papers": papers_in_db}


@app.post("/api/bulk_analysis/{analysis_name}/papers/doi/", tags=["Bulk analysis"])
def bulk_analysis_add_papers_by_dois_endpoint(analysis_name: analysis_name_constr, doi: doi_str, force_redownload: bool=False, fail_if_already_downloaded: bool=False, take_abstract_as_fallback: bool=False) -> dict:
    """
    Download paper with given DOI and add it to an existing bulk analysis.
    """
    # Note: doi must be query parameter, because if its a path parameter, the URL is not escaped properly.
    print(f"Download paper with DOI {doi} and add it to the analysis \"{analysis_name}\".")    
    papers_dir = get_papers_dir(analysis_name)
    success, paper_dir, file_format, paper_already_downloaded, reverted_to_abstract = download_paper_by_doi(doi, analysis_name, papers_dir, force_redownload=force_redownload, take_abstract_as_fallback=take_abstract_as_fallback)
    
    if paper_already_downloaded and not force_redownload and not fail_if_already_downloaded:
        return {"detail": f"Nothing to do. Paper with DOI {doi} was already downloaded as part of \"{analysis_name}\"."}        
    elif success:
        return {"detail": f"Download successfull! Found {file_format} file for paper with DOI {doi}. Added the paper to the analysis \"{analysis_name}\" under ID {paper_dir}."}
    elif reverted_to_abstract:
        return {"detail": f"Could not download fulltext for paper with DOI {doi}, but added the abstract to the analysis \"{analysis_name}\" under ID {paper_dir}."}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to add paper with DOI {doi} to the analysis \"{analysis_name}\"")


@app.post("/api/bulk_analysis/{analysis_name}/papers/pdf/", tags=["Bulk analysis"])
def bulk_analysis_add_additional_papers_endpoint(analysis_name: analysis_name_constr, files: list[UploadFile]) -> dict:
    """
    Add one or multiple papers as PDFs or a single zip file containing PDFs to an existing bulk analysis.

    Args:
        analysis_name (analysis_name_constr): Name of the analysis.
        files (list[UploadFile]): PDF files to be added or a zip file containing PDFs.

    Returns:
        dict: The result of the operation.

    """
    # Check if file is zip or pdfs.
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    elif len(files) == 1 and files[0].filename.endswith(".zip"):
        # Check if valid zip file.
        zip_file = files[0]        
        filename = secure_filename(zip_file.filename)
        if not has_valid_extension(filename, extensions=["zip"]):
            raise HTTPException(status_code=400, detail="Invalid file extension. Only ZIP files are allowed.")
        
        # Extract files from zip.
        pdf_files = []    
        with zipfile.ZipFile(zip_file.file, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if has_valid_extension(file, extensions=["pdf"]):
                    pdf_files.append(file)
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid file extension for {file}. Only PDF files are allowed.")
    else:        
        # Check file format.
        pdf_files = files
        for pdf in pdf_files:            
            filename = secure_filename(pdf.filename)     
            if not has_valid_extension(filename, extensions=["pdf"]):
                raise HTTPException(status_code=400, detail=f"Invalid file extension for {pdf.filename}. Only PDF files are allowed.")
                # Move each paper file in a subdirectory with its hash as name.

    ANALYSIS_DIR = get_analysis_dir(analysis_name)
    PAPERS_DIR = get_papers_dir(analysis_name)
    # Make sure the analysis exists.
    if not ANALYSIS_DIR.exists():
        raise HTTPException(status_code=400, detail=f"Analysis with name {analysis_name} does not exist.")
    else:
        # Add papers to the analysis.
        successfully_added_papers = []
        already_exists_therefore_ignored = []
        paper_ids = []
        filenames = []        
        for pdf in pdf_files:
            binary_content = pdf.file.read()
            pdf_hash = hashlib.file_digest(io.BytesIO(binary_content), 'sha256').hexdigest()            
            unique_paper_dir = "W_sha256_" + pdf_hash
            print(unique_paper_dir)
            paper_ids.append(unique_paper_dir)
            filenames.append(pdf.filename)
            new_pdf_dir = PAPERS_DIR / unique_paper_dir
            new_pdf_path = new_pdf_dir / "raw.pdf"
            try:
                # Save pdf to disk.
                new_pdf_path.parent.mkdir(parents=False, exist_ok=False)
                new_pdf_path.write_bytes(binary_content)

                # Init empty structured.json file.
                # TODO: Align provenance with that of papers downloaded from OpenAlex.
                metadata = {
                        "provenance": {
                                "fulltext_source": {
                                    "user_uploaded": True, 
                                    "method": "pdf_upload",
                                    "sha256_hash": pdf_hash, 
                                    "timestamp": datetime.now().astimezone().replace(microsecond=0, second=0).isoformat()
                                }
                            }, 
                        "bibliographic": {}
                    }
                paper_dict = {"text": "", "metadata": metadata, "annotations": {}, "bibliography": {}, "figures": {}, "tables": {}}
                with open(new_pdf_dir / "structured.json", "w") as f:
                    json.dump(paper_dict, f, indent=4, ensure_ascii=False)

                successfully_added_papers.append(pdf.filename)

            except FileExistsError:
                already_exists_therefore_ignored.append(pdf.filename)            
            
        return {"detail": f"Added {len(successfully_added_papers)} of {len(pdf_files)} papers to the analysis \"{analysis_name}\"", "paper_ids": paper_ids, "paper_filenames": filenames, "successfully_added_papers": successfully_added_papers, "already_exists_therefore_ignored": already_exists_therefore_ignored}


@app.post("/api/bulk_analysis/{analysis_name}/papers/scopus_export/", tags=["Bulk analysis"])
def bulk_analysis_add_papers_scopus_export_endpoint(analysis_name: analysis_name_constr, files: list[UploadFile], force_overwrite: bool=False) -> dict:
    """
    Add one or multiple papers to an existing bulk analysis using Scopus export CSV file(s).     
    Only the abstract will be processed using this method.    
    The CSV file(s) must be exported from Scopus using the "CSV" export option and must contain the fields
    "DOI", "Title", "Source title", "Year", and "Abstract".

    Args:
        analysis_name (analysis_name_constr): Name of the analysis.
        files (list[UploadFile]): Scopus export CSV file(s).

    Returns:
        dict: The result of the operation.

    """    
    required_columns = ["DOI", "Title", "Source title", "Year", "Abstract"]

    # Check if file is zip or pdfs.
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    else:
        for csv in files:            
            filename = secure_filename(csv.filename)     
            if not has_valid_extension(filename, extensions=["csv"]):
                raise HTTPException(status_code=400, detail=f"Invalid file extension for {csv.filename}. Only csv files are allowed.")                

    ANALYSIS_DIR = get_analysis_dir(analysis_name)
    PAPERS_DIR = get_papers_dir(analysis_name)
    
    # Make sure the analysis exists.
    if not ANALYSIS_DIR.exists():
        raise HTTPException(status_code=400, detail=f"Analysis with name {analysis_name} does not exist.")
    else:
        # Add papers to the analysis.
        successfully_added_papers = []
        already_exists_therefore_ignored = []
        paper_ids = []
        titles = []
        for csv in files:                  
            # Read CSV file.
            content = csv.file.read().decode("utf-8")            
            df = pd.read_csv(io.StringIO(content))
            if not all(col in df.columns for col in required_columns):
                raise HTTPException(status_code=400, detail=f"CSV file {csv.filename} is missing required columns. Required columns are: {', '.join(required_columns)}.")
            
            # Process each row in the CSV file.
            for index, row in df.iterrows():
                title = str(row["Title"]).strip()
                journal = str(row["Source title"]).strip()
                pub_year = str(row["Year"]).strip()                
                doi = str(row["DOI"]).strip()
                abstract = str(row["Abstract"]).strip()
                hash_str = title + ", " + journal + ", " + pub_year + ", " + doi + ", " + abstract
                if hash_str.replace("nan", "").replace(", ","").strip() == "":
                    raise HTTPException(status_code=400, detail=f"Row {index} in CSV file {csv.filename} has empty.")
                
                abstract_hash = hashlib.file_digest(io.BytesIO(hash_str.encode("utf-8")), 'sha256').hexdigest()
                unique_paper_dir = "W_sha256_" + abstract_hash
                print(unique_paper_dir)

                paper_ids.append(unique_paper_dir)
                titles.append(title)
                new_paper_dir = PAPERS_DIR / unique_paper_dir

                try:
                    pub_year = int(pub_year)
                except ValueError:
                    pub_year = None
                
                try:
                    # Init empty structured.json file.
                    # TODO: Align provenance with that of papers downloaded from OpenAlex.
                    metadata = {
                        "provenance": {
                            "abstract_source": {
                                "user_uploaded": True, 
                                "method": "scopus_export_file_upload",
                                "sha256_hash": abstract_hash, 
                                "timestamp": datetime.now().astimezone().replace(microsecond=0, second=0).isoformat()}
                            }, 
                        "bibliographic": {                            
                            "doi": doi,
                            "title": title,
                            "display_name": title,
                            "journal": journal,
                            "publication_year": pub_year,
                        }
                    }
                    text = f"{title}\n\n\nAbstract\n"
                    pos_abstr_start = len(text)
                    text += abstract
                    annotations = {
                        "title": [
                            {
                                "start": 0,
                                "end": len(title)
                            }
                        ],
                        "abstract": [
                            {
                                "start": pos_abstr_start,
                                "end": pos_abstr_start + len(abstract)
                            }
                        ],
                        "body_text": [],
                        "back_matter": [],
                        "section_header": [],
                        "citations": [],
                        "figure_refs": [],
                        "table_refs": [],
                        "equation_refs": [],
                    }
                    paper_dict = {"text": text, "metadata": metadata, "annotations": annotations, "bibliography": {}, "figures": {}, "tables": {}}
                    new_paper_path = new_paper_dir / "structured.json"
                    new_paper_path.parent.mkdir(parents=False, exist_ok=force_overwrite)
                    with open(new_paper_path, "w") as f:
                        json.dump(paper_dict, f, indent=4, ensure_ascii=False)

                    successfully_added_papers.append(doi)

                except FileExistsError:                
                    already_exists_therefore_ignored.append(doi)            
            
        return {"detail": f"Added {len(successfully_added_papers)} of {len(df)} papers to the analysis \"{analysis_name}\"", "paper_ids": paper_ids, "paper_titles": titles, "successfully_added_papers": successfully_added_papers, "already_exists_therefore_ignored": already_exists_therefore_ignored}


@app.post("/api/papers/", tags=["Papers"], deprecated=True)
async def add_paper_endpoint(files: list[UploadFile], force: bool=False, skip_imprecise_quantities: bool=False) -> dict:    
    """Upload, parse, annotate and add one or multiple papers to the database.

    Args:
        files (list[UploadFile]): PDF files to be processed.
        force (bool, optional): If True, the paper is added even if it was already added before. Defaults to False.

    Returns:
        dict: The result of the operation.
    """    

    if not CONFIG["parsing_service"]["enable"]:
        return HTTPException(status_code=400, detail="The service was started using the option of disabling parsing. Change the config file.")
    elif not CONFIG["quinex_api"]["enable"]:
        return HTTPException(status_code=400, detail="The service was started using the option of disabling information extraction. Change the config file.")
    
    upload_timestamp = datetime.now().astimezone().replace(microsecond=0, second=0).isoformat()

    responses = []
    hashes = []
    for file in files:

        # Check file format.
        filename = secure_filename(file.filename)     
        if not has_valid_extension(filename, extensions=["pdf"]):
            raise HTTPException(status_code=400, detail=f"Invalid file extension for {file.filename}. Only PDF, TXT, and TEI XML files are allowed.")
        
        # Get SHA256 hash of file.
        binary_content = await file.read()    
        paper_hash = hashlib.file_digest(io.BytesIO(binary_content), 'sha256').hexdigest()

        # Check if paper with this hash was already processed if upload is not forced.
        exist, metadata = (False, {}) if force else check_paper_exists_by_hash(paper_hash)     

        if exist:
            raise HTTPException(
                status_code=400, 
                detail=f"\"{filename}\" was already processed. Set force to True to overwrite the existing paper.")
        else:
            # Parse PDF to TEI XML using GROBID.
            # TODO: Batch process in memory.
            _, status, tei_xml = grobid_client.process_pdf(
                "processFulltextDocument", 
                binary_content,
                generateIDs = False,
                consolidate_header = True,
                consolidate_citations = True,
                include_raw_citations = False,
                include_raw_affiliations = False,
                tei_coordinates = True,
                segment_sentences = False,
                from_memory = True,
            )        
            if status != 200:
                raise HTTPException(status_code=400, detail=f"PDF could not be parsed to TEI XML. GROBID returned status code {status}.")
            
            try:
                # Convert TEI XML to S2ORC JSON.
                soup = BeautifulSoup(tei_xml, "xml")
                intermediate_json_paper = convert_tei_xml_soup_to_s2orc_json(soup, paper_hash, paper_hash).release_json()
                            
                # Post-process generated S2ORC JSON.
                intermediate_json_paper = post_process_parsed_json(intermediate_json_paper)

                # Save intermediate JSON.
                intermediate_json_path = f"./logs/{paper_hash}.json"
                with open(intermediate_json_path, "w") as f:
                    json.dump(intermediate_json_paper, f, indent=4, ensure_ascii=False)
                                
                # Convert S2ORC JSON to flattened JSON representation.
                text, annotations = s2orc_json_to_string(intermediate_json_paper)

            except Exception as e:
                msg.fail(e)
                raise HTTPException(status_code=400, detail=f"PDF could be parsed to TEI XML but not to JSON. Contact the admin.")
            
        paper_dict = {}
        paper_dict["text"] = text     
        quantitative_statements, extraction_provenance = annotate_paper_text(paper_dict, skip_imprecise_quantities=skip_imprecise_quantities)
        
        paper_dict["metadata"] = {} 
        paper_dict["metadata"]["provenance"] = {}
        paper_dict["metadata"]["bibliographic"] = {}
        paper_dict["metadata"]["provenance"] = {            
            "fulltext_source": {
                "user_uploaded": True,
                "sha256_hash": paper_hash,
                "timestamp": upload_timestamp, 
            },
            "quantitative_statements_annotations": extraction_provenance,
        }
        paper_dict["annotations"] = annotations
        paper_dict["annotations"]["quantitative_statements"] = quantitative_statements
        paper_dict["bibliography"] = intermediate_json_paper["pdf_parse"]["bib_entries"]
        paper_dict["figures"] = {}
        paper_dict["tables"] = {}        
        for ref_id, ref in intermediate_json_paper["pdf_parse"]["ref_entries"].items():
            if ref_id[:3] == "FIG":
                paper_dict["figures"][ref_id] = ref
            elif ref_id[:3] == "TAB":
                paper_dict["tables"][ref_id] = ref
            else:
                raise HTTPException(status_code=400, detail=f"Unexpected reference ID {ref_id}.")      
            

        # TODO: Get metadata from bibliographic API.
        if intermediate_json_paper.get("identifiers") != {}:
            raise HTTPException(status_code=400, detail="Not implemented yet. Parsed PDF has identifiers. Use them instead of the paper title to get metadata from bibliographic APIs. Contact the admin.")
        title = intermediate_json_paper.get("title")
        abstract_paragraphs = intermediate_json_paper.get("pdf_parse", {}).get("abstract", [])
        abstract = " ".join([p["text"] for p in abstract_paragraphs])
        matching_paper = None
        if title != None and len(title) > 0:
            matching_papers = search_paper_by_title(title)

            # Check if there is a matching paper with high enough certainty.               
            for mp in matching_papers:
                # How well does the title match?
                if mp["title"].lower() == title.lower() or mp["display_name"].lower() == title.lower():
                    title_ratio = 100
                else:
                    title_ratio = fuzz.ratio(mp["title"].lower(), title.lower())
                
                # How well does the abstract match?
                candidate_abstract = inverted_index_to_text(mp["abstract_inverted_index"])
                abstract_ratio = fuzz.ratio(abstract.lower(), candidate_abstract.lower())        
                                
                if title_ratio + abstract_ratio > 195:
                    matching_paper = mp
                    break

        if matching_paper == None:
            # Just add title from PDF parse.
            paper_dict["metadata"]["provenance"]["metadata_source"] = {"source": "PDF parse"}
            paper_dict["metadata"]["bibliographic"]["title"] = title
        else:    
            # Add metadata from bibliographic API.
            paper_dict["metadata"]["provenance"]["metadata_source"] = matching_paper.pop("provenance")
            paper_dict["metadata"]["bibliographic"] = matching_paper

        
        # Normalize references.
        for quantitative_statement in paper_dict["annotations"]["quantitative_statements"]:
            individual_matches = normalize_references(quantitative_statement, paper_dict, revert_to_bibliographic_api=False)
            quantitative_statement["qualifiers"]["reference"]["normalized"] = individual_matches

        # Store paper.
        try:
            response = store_paper(paper_dict, overwrite=force)
        except Exception as e:
            msg.fail(e)
            raise HTTPException(status_code=400, detail=f"Paper could be parsed but not ingested into the database. Contact the admin.")

        responses.append(response)
        hashes.append(paper_hash)


    return {"detail": "Papers were successfully added.", "count": len(hashes), "hashes": hashes, "paper_ids": [r["_id"] for r in responses], "db_operations": [r["operation"] for r in responses]}


@app.get("/api/bulk_analysis/{analysis_name}/papers/", tags=["Bulk analysis"])
def list_bulk_analysis_papers_endpoint(analysis_name: str) -> list[dict]:
    """Lists all papers in DB with some metadata.
    
    Returns:
        papers (list): List of papers.
    """
    return get_all_papers(consider_only_api_uploads=False, analysis_name=analysis_name)

@app.get("/api/bulk_analysis/{analysis_name}/papers/{paper_id}", tags=["Bulk analysis"])
def get_bulk_analysis_paper_by_id_endpoint(analysis_name: str, paper_id: str, raw_pdf: bool=False) -> dict:
    """Get paper by ID from MongoDB.

    Args:
        paper_id (str): The MongoDB ID of the paper.

    Returns:
        paper (dict): The paper.
    """
    return get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False, raw_pdf=raw_pdf)


@app.get("/api/papers/", tags=["Papers"], deprecated=True)
def list_papers_endpoint() -> list[dict]:
    """Lists all papers in DB with some metadata.
    
    Returns:
        papers (list): List of papers.
    """
    return get_all_papers(consider_only_api_uploads=True)


@app.get("/api/papers/{paper_id}", tags=["Papers"], deprecated=True)
def get_paper_by_id_endpoint(paper_id: str) -> dict:
    """Get paper by ID from MongoDB.

    Args:
        paper_id (str): The MongoDB ID of the paper.

    Returns:
        paper (dict): The paper.
    """
    return get_paper(paper_id, consider_only_api_uploads=True)


@app.delete("/api/papers/{paper_id}", tags=["Papers"], deprecated=True)
def delete_paper_by_id_endpoint(paper_id: str) -> dict:
    return delete_paper(paper_id)


example_text = "If you stack a gazillion giraffes, they would have a total height greater than 100 meters. The bottom giraffe would be exposed to a pressure of more than 10^5 Pa (see Figure 3)."
@app.post("/api/text/annotate", tags=["Special Endpoints"])
def annotate_text(text: Annotated[str, Body(examples=[example_text])], skip_imprecise_quantities: bool = True) -> dict:
    """Annotate a text with the annotation service running on the compute node."""

    if not CONFIG["quinex_api"]["enable"]:
        return HTTPException(status_code=400, detail="The service was started using the option of disabling information extraction. Change the config file.")
    
    print("Sending annotation job to compute node...")    
    start_time = time.time()

    endpoint_url = f'{ANNOTATION_SERVICE_URL}/api/process_text/?skip_imprecise_quantities={skip_imprecise_quantities}'    
    headers = {'Content-type': 'application/json'}

    print(f"Send request to {endpoint_url}")
    response = requests.post(endpoint_url, headers=headers, json=text)

    elapsed_time = time.time() - start_time
    if response.status_code == 200:        
        msg.good("Text was successfully annotated.")                    
        predictions_str = response.json().get("predictions")
        predictions = json.loads(predictions_str)        
        return {'predictions': predictions, "elapsed_time": elapsed_time}
    
    else:
        return HTTPException(status_code=400, detail="Failed to annotate paper. Contact the admin.")

    

@app.post("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations", tags=["Annotations"])
def create_annotation(analysis_name: str, paper_id: str, quantity_start_char: int, quantity_end_char: int, quantity_surface: str):
    """Create a new quantity annotation for a paper. Given a quantity span and its position in the text, 
    it is normalized automatically and the corresponding quantitative claim is inferred from the context. 
    The predictions can be changed manually using the endpoint to update annotations."""

    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)

    if quantity_surface == "":
        raise HTTPException(status_code=400, detail="Quantity surface must not be empty.")
    elif quantity_start_char >= quantity_end_char:
        raise HTTPException(status_code=400, detail="The quantity's start character offset must be smaller than its end offset.")

    # Check if quantity annotation already exists.
    for qclaim in paper["annotations"]["quantitative_statements"]:
        if qclaim["claim"]["quantity"]["start"] == quantity_start_char \
            and qclaim["claim"]["quantity"]["end"] == quantity_end_char:                            
            raise HTTPException(status_code=400, detail="Quantity annotation already exists.")
        
    # Check if quantity span char offsets match its surface form.
    if paper["text"][quantity_start_char:quantity_end_char] != quantity_surface:
        raise HTTPException(status_code=400, detail=f"Quantity span character offsets do not match the quantity surface form. Given character offsets correspond to \"{paper['text'][quantity_start_char:quantity_end_char]}\" instead of \"{quantity_surface}\".")
    
    # Get quantitative claim for new quantity annotation.
    endpoint_url = f'{ANNOTATION_SERVICE_URL}/api/get_claim_for_quantity/'    
    headers = {'Content-type': 'application/json'}

    print(f"Send request to {endpoint_url}")    
    response = requests.post(endpoint_url, headers=headers, json={"text": paper["text"], "quantity_start_char": quantity_start_char, "quantity_end_char": quantity_end_char, "quantity_surface": quantity_surface})

    if response.status_code == 200:
        new_qclaim = response.json().get("quantitative_statement")
    else:
        raise HTTPException(status_code=400, detail="Failed to get quantitative claim for new quantity annotation. Contact the admin.")
    
    # Insert new quantity annotation at correct position.
    for i, qclaim in enumerate(paper["annotations"]["quantitative_statements"]):
        if qclaim["claim"]["quantity"]["start"] == quantity_start_char and qclaim["claim"]["quantity"]["end"] > quantity_end_char:
            break
        elif qclaim["claim"]["quantity"]["start"] > quantity_start_char:
            break
    
    paper["annotations"]["quantitative_statements"].insert(i, new_qclaim)

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Quantity annotation was successfully added.", "extracted_context": new_qclaim}


@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/span/", tags=["Annotations"])
def update_annotation(analysis_name: str, paper_id: str, idx: int, annotation_type: AnnotationType, annotation_surface: str = "", new_annotation_surface: str = ""):
    """Update an annotation of a paper. The annotation can be updated by changing the surface form. 
    The surrounding context is used to automatically infer whether the annotation is implicit or explicit.
    If the annotation is explicit, character offsets are also automatically inferred. The curation list is emptied."""

    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    quantity = qclaim["claim"]["quantity"]
    if annotation_type in QualifierAnnotationTypes:
        annotation = qclaim["qualifiers"][annotation_type]
    else:
        annotation = qclaim["claim"][annotation_type]

    # Check integrity of user input.
    if annotation["text"] != annotation_surface:
        raise HTTPException(status_code=400, detail=f"Annotation surfaces of given '{annotation_surface}' and selected claim '{annotation['text']}' do not match.")
    
    
    if annotation_type == AnnotationType.quantity:
        # Special rules for quantity annotations as they act as anchors for the other annotations.
        if new_annotation_surface == "":
            raise HTTPException(status_code=400, detail="New quantity surface must not be empty. If you want to delete the annotation, use the delete endpoint. Note that the whole claim will be deleted. For other annotations, leave the new annotation surface empty if the context does not provide sufficient information.")
        
        # The updated quantity span must be explicit and overlap with the orignal quantity span.        
        window_for_overlap_chars = 100
        window_for_overlap = paper["text"][quantity["start"]-window_for_overlap_chars:quantity["end"]+window_for_overlap_chars]
        
        a_in_b = lambda a, b: a[0] >= b[0] and a[0] <= b[1] or a[1] >= b[0] and a[1] <= b[1] # Answers if a is inside b
        is_overlapping = lambda a, b: a_in_b(a, b) or a_in_b(b, a) # Answers if a and b are overlapping
        overlapping_matches = []        
        for match in re.finditer(new_annotation_surface, window_for_overlap):            
            old_quantity_span_relative_to_window = (window_for_overlap_chars, quantity["end"]-quantity["start"]+window_for_overlap_chars)            
            print("Old quantity span:", quantity["start"], quantity["end"])
            print("Old quantity span (relative to window):", old_quantity_span_relative_to_window)
            print("New quantity span (relative to window):", match.span())
            if is_overlapping(match.span(), old_quantity_span_relative_to_window):
                overlapping_matches.append(match)

        if len(overlapping_matches) > 1:
            raise HTTPException(status_code=400, detail="Ambiguity: Found multiple new quantity surface that overlap with the original quantity span in the text.")
        elif len(overlapping_matches) == 0:
            raise HTTPException(status_code=400, detail="The new quantity surface must overlap with the original quantity span in the text.")
        else:
            # New quantity annotations is okay.
            is_implicit = False        
            new_start_char = quantity["start"] + overlapping_matches[0].start() - window_for_overlap_chars
            new_end_char = new_start_char + len(new_annotation_surface)
            char_offsets = (new_start_char, new_end_char)

    else:
        # Check if new annotation is implicit.
        is_implicit, char_offsets = locate_span_in_context(new_annotation_surface, paper["text"], quantity)
    
    annotation["start"] = char_offsets[0]
    annotation["end"] = char_offsets[1]
    annotation["text"] = new_annotation_surface
    annotation["is_implicit"] = is_implicit
    
    # Empty curation list.
    annotation["curation"] = []

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of annotation was successfull."}


@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/span/curate", tags=["Annotations"])
def curate_annotation(analysis_name: str, paper_id: str, idx: int, approve: bool, annotation_type: AnnotationType, annotation_surface: str = "", comment: str = ""):
    """Curate an annotation of a paper. The annotation can be approved or rejected and a comment can be added. 
    Assumes that no two quantity annotations have the same character offsets. 
    If annotation is empty, leave annotation_surface empty as well."""
    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if annotation_type in QualifierAnnotationTypes:
        annotation = qclaim["qualifiers"][annotation_type]
    else:
        annotation = qclaim["claim"][annotation_type]

    # Check integrity of user input.
    if annotation["text"] != annotation_surface:
        raise HTTPException(status_code=400, detail=f"Annotation surfaces of given '{annotation_surface}' and selected claim '{annotation['text']}' do not match.")
    
    # Update curation information.
    annotation["curation"].append({"approve": approve, "comment": comment, "timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat()})

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of annotation was successfull."}



@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/normalization/", tags=["Annotations"])
def update_normalization(analysis_name: str, paper_id: str, idx: int, annotation_type: NormalizationType, annotation_surface: str, new_normalization: list[NormalizedQuantity]):
    """Update a normalization o an annotation of a paper. The normalization can be updated by providing a JSON object."""

    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if annotation_type in QualifierAnnotationTypes:
        annotation = qclaim["qualifiers"][annotation_type]
    else:
        annotation = qclaim["claim"][annotation_type]

    if annotation_type == NormalizationType.quantity:     
        normalization = annotation["normalized"]["individual_quantities"]
    else:
        raise HTTPException(status_code=400, detail="For now only quantity normalization curation is implemented.")

    # Check integrity of user input.
    if annotation["text"] != annotation_surface:
        raise HTTPException(status_code=400, detail=f"Annotation surfaces of given '{annotation_surface}' and selected claim '{annotation['text']}' do not match.")
    
    new_normalization_dict = [n.model_dump() for n in new_normalization]
    if normalization["normalized"] != new_normalization_dict:
        normalization["normalized"] = new_normalization_dict
    else:
        raise HTTPException(status_code=400, detail="New normalization is the same as the old normalization.")        
    
    # Empty curation list.
    normalization["curation"] = []

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of quantity normalization was successfull."}


@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/normalization/curate", tags=["Annotations"])
def curate_normalization(analysis_name: str, paper_id: str, idx: int, approve: bool, annotation_type: NormalizationType, annotation_surface: str = "", comment: str = ""):
    """Curate a normalization of an annotation of a paper. The normalization can be approved or rejected and a comment can be added. 
    Assumes that no two quantity annotations have the same character offsets. 
    If annotation is empty, leave annotation_surface empty as well."""
    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if annotation_type != NormalizationType.quantity:        
        raise HTTPException(status_code=400, detail="For now only quantity normalization curation is implemented.")

    if annotation_type in QualifierAnnotationTypes:
        annotation = qclaim["qualifiers"][annotation_type]
    else:
        annotation = qclaim["claim"][annotation_type]

    # Check integrity of user input.
    if annotation["text"] != annotation_surface:
        raise HTTPException(status_code=400, detail=f"Annotation surfaces of given '{annotation_surface}' and selected claim '{annotation['text']}' do not match.")
    
    if annotation_type == NormalizationType.quantity:
        normalization = annotation["normalized"]["individual_quantities"]
    
    # Update curation information.
    normalization["curation"].append({"approve": approve, "comment": comment, "timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat()})

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of normalization was successfull."}


@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/classification/", tags=["Annotations"])
def update_classification(analysis_name: str, paper_id: str, idx: int, quantity_surface: str, statement_type: StatementTypeClasses=None, statement_rational: StatementRationalClasses=None, statement_system: StatementSystemClasses=None, is_relative_quantity: bool=None, quantity_type: QuantityTypeClasses=None):
    """Update classifcation. Choose a value for either statement_type, statement_rational, statement_system, is_relative_quantity, or quantity_type. Only one classification type can be updated at a time. Updating a classification will empty the curation list."""
    
    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if qclaim["claim"]["quantity"]["text"] != quantity_surface:
        raise HTTPException(status_code=400, detail=f"Quantity surface of given '{quantity_surface}' and selected claim '{qclaim['claim']['quantity']['text']}' do not match.")    
    elif sum([statement_type != None, statement_rational != None, statement_system != None, is_relative_quantity != None, quantity_type != None]) > 1:
        raise HTTPException(status_code=400, detail="Only one classification type can be updated at a time.")
    
    if is_relative_quantity != None:
        # Special rules for is_relative classification.
        classification = qclaim["claim"]["quantity"]["normalized"]["is_relative"]
        classification["bool"] = is_relative_quantity
    elif quantity_type != None:
        # Special rules for quantity type classification.
        classification = qclaim["claim"]["quantity"]["normalized"]["type"]
        classification["class"] = quantity_type
    elif statement_type != None:
        classification = qclaim["statement_classification"]["type"]
        classification["class"] = statement_type
    elif statement_rational != None:
        classification = qclaim["statement_classification"]["rational"]
        classification["class"] = statement_rational
    elif statement_system != None:
        classification = qclaim["statement_classification"]["system"]
        classification["class"] = statement_system
    else:
        raise HTTPException(status_code=400, detail="No classification was selected to be updated.")
    
    # Empty curation list.
    classification["curation"] = []

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of classification was successfull."}


@app.put("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}/classification/curate", tags=["Annotations"])
def curate_classification(analysis_name: str, paper_id: str, idx: int, quantity_surface: str, classification_type: ClassificationType, approve: bool, comment: str = ""):
    """Curate a classification. The classification can be approved or rejected and a comment can be added. 
    Assumes that no two quantity annotations have the same character offsets."""
    # Get paper by ID.        
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if qclaim["claim"]["quantity"]["text"] != quantity_surface:
        raise HTTPException(status_code=400, detail=f"Quantity surface of given '{quantity_surface}' and selected claim '{qclaim['claim']['quantity']['text']}' do not match.")
        
    if classification_type == ClassificationType.quantity_type:
        classification = qclaim["claim"]["quantity"]["normalized"]["type"]
    elif classification_type == ClassificationType.is_relative:
        classification = qclaim["claim"]["quantity"]["normalized"]["is_relative"]
    else:
        classification = qclaim["statement_classification"][classification_type.removeprefix("statement_")]
    
    # Update curation information.
    classification["curation"].append({"approve": approve, "comment": comment, "timestamp": datetime.now().astimezone().replace(microsecond=0).isoformat()})

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Curation of classification was successfull."}


@app.delete("/api/bulk_analysis/{analysis_name}/papers/{paper_id}/annotations/quantitative_statements/{idx}", tags=["Annotations"])
def delete_annotation(analysis_name: str, paper_id: str, idx: int, quantity_surface: str):
    
    # Get paper by ID.
    paper = get_paper(paper_id, analysis_name=analysis_name, consider_only_api_uploads=False)
    qclaim = paper["annotations"]["quantitative_statements"][idx]
    if qclaim["claim"]["quantity"]["text"] != quantity_surface:
        raise HTTPException(status_code=400, detail=f"Quantity surface of given '{quantity_surface}' and selected claim '{qclaim['claim']['quantity']['text']}' do not match.")
    
    # Delete annotation.
    del paper["annotations"]["quantitative_statements"][idx]

    # Save changes.
    _ = store_paper(paper_id, paper, analysis_name=analysis_name, overwrite=True)

    return {"detail": "Annotation was successfully deleted."}
   

if __name__ == '__main__':

    uvicorn.run(app, port=CONFIG["manage_analyses_api"]["port"], host=CONFIG["manage_analyses_api"]["host"])