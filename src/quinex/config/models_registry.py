import yaml
from pathlib import Path



_model_registry_path = Path(__file__).parent / 'model_registry.yml'
with open(_model_registry_path, 'r') as f:
    MODELS = yaml.safe_load(f)

del MODELS['model_family_configs']