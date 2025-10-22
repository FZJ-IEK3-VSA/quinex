

import json
import yaml
from pathlib import Path
from werkzeug.utils import secure_filename


PAPER_ANALYSIS_SERVICES_DIR = Path(__file__).parents[3]

config_path = PAPER_ANALYSIS_SERVICES_DIR / "config" / "config.yml"
with open(config_path, "r") as f:
    CONFIG = yaml.safe_load(f)

ANALYSES_DIR = PAPER_ANALYSIS_SERVICES_DIR / CONFIG["manage_analyses_api"]["analyses_dir"]
API_PAPER_DIR = ANALYSES_DIR / "api_uploads"

ann_service_host = CONFIG["quinex_api"]["host"]
ann_service_port = CONFIG["quinex_api"]["port"]
ANNOTATION_SERVICE_URL = f"http://{ann_service_host}:{ann_service_port}/api/"

batch_ann_service_host = CONFIG["on_demand_batch_processing_api"]["host"]
batch_ann_service_port = CONFIG["on_demand_batch_processing_api"]["port"]
BATCH_ANNOTATION_SERVICE_URL = f"http://{batch_ann_service_host}:{batch_ann_service_port}/api/"

batch_script_config_dir = PAPER_ANALYSIS_SERVICES_DIR / CONFIG["manage_analyses_api"]["batch_script_config_path"]
with open(batch_script_config_dir, "r") as f:
    SCRIPT_CONFIG = json.load(f)

get_analysis_dir = lambda name: ANALYSES_DIR / secure_filename(name)
get_papers_dir = lambda name: get_analysis_dir(name) / "papers"