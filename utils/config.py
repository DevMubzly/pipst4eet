import os
from typing import Dict, Any, Optional
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or CONFIG_PATH
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_config_value(
    config: Dict[str, Any], key_path: str, default: Any = None
) -> Any:
    keys = key_path.split(".")
    val = config
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return default
    return val
