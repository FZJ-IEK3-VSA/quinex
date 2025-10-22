import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import List



@dataclass(frozen=True)
class ModelPreset:
    """Configuration of models to use by Quinex pipeline."""
    quantity_model_name: str
    context_model_name: str
    statement_clf_model_name: str


@dataclass(frozen=True)
class TaskPreset:
    """Configuration of tasks to perform by Quinex pipeline."""
    tasks: List[str]


class _ModelPresetRegistry:
    """
    Registry for model presets loaded from YAML configuration.
    """
    def __init__(self, config_path: Path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self._presets = {}
        for name, params in config.get('models', {}).items():
            self._presets[name] = ModelPreset(**params)
    
    def __getattr__(self, name: str) -> dict:
        """
        Return preset as a dictionary for unpacking into Quinex() constructor.
        """
        if name in self._presets:
            preset = self._presets[name]
            return {
                'quantity_model_name': preset.quantity_model_name,
                'context_model_name': preset.context_model_name,
                'statement_clf_model_name': preset.statement_clf_model_name,
            }
        else:
            raise AttributeError(f"No preset named '{name}' found. Available: {list(self._presets.keys())}")


class _TaskPresetRegistry:
    """
    Registry for task presets loaded from YAML configuration.
    """
    
    # Mapping from task names in YAML to enable flags
    _TASK_FLAG_MAP = {
        'quantity_extraction': 'enable_quantity_extraction',
        'context_extraction': 'enable_context_extraction',
        'qualifier_extraction': 'enable_qualifier_extraction',
        'statement_classification': 'enable_statement_classification',
    }
    
    def __init__(self, config_path: Path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self._presets = {}
        for name, task_list in config.get('tasks', {}).items():
            self._presets[name] = TaskPreset(tasks=task_list)
    
    def __getattr__(self, name: str) -> dict:
        """
        Return preset as a dictionary for unpacking into Quinex() constructor.
        """
        if name in self._presets:
            task_list = self._presets[name].tasks
            
            # Initialize all flags to False
            flags = {flag: False for flag in self._TASK_FLAG_MAP.values()}
            
            # Enable flags for tasks in the preset            
            for task in task_list:
                if task in self._TASK_FLAG_MAP:
                    flags[self._TASK_FLAG_MAP[task]] = True
            
            return flags
        else:
            raise AttributeError(f"No preset named '{name}' found. Available: {list(self._presets.keys())}")


# Load model presets.
_model_presets_path = Path(__file__).parent / 'model_presets.yml'
models = _ModelPresetRegistry(_model_presets_path)

# Load task presets.
_task_presets_path = Path(__file__).parent / 'task_presets.yml'
tasks = _TaskPresetRegistry(_task_presets_path)