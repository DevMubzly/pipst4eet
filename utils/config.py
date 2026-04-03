import os
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config(path=None):
    path = path or CONFIG_PATH
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_config_value(config, key_path, default=None):
    keys = key_path.split(".")
    val = config
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return default
    return val
