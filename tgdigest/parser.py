import yaml

from .models import Config


def load_config(config_path="config.yaml"):
    with open(config_path, encoding="utf-8") as f:
        return Config(**yaml.safe_load(f))
