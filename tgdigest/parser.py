import yaml
from .models import Config

def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    config = Config(**data)
    return config