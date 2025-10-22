import yaml
from pathlib import Path


config_path = Path(__file__).parents[4] / "config" / "config.yml"

with open(config_path, "r") as f:
    CONFIG = yaml.safe_load(f)

api_host = CONFIG["manage_analyses_api"]["host"]
api_port = CONFIG["manage_analyses_api"]["port"]
API_BASE_URL = f"http://{api_host}:{api_port}/api/"

gui_host = CONFIG["reading_and_curation_ui"]["host"]
gui_port = CONFIG["reading_and_curation_ui"]["port"]
GUI_URL = f"https://{gui_host}:{gui_port}"