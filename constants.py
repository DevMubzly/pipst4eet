from typing import Dict, Any, Optional

PIP_SIZES: Dict[str, float] = {
    "XAUUSD": 0.01,
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "GBPJPY": 0.01,
    "AUDUSD": 0.0001,
}

DEFAULT_PIP_SIZE: float = 0.0001

PAIR_CONFIG_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {"pip_value": 1.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 5.0},
    "EURUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
    "GBPUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
    "USDJPY": {"pip_value": 10.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 100.0},
    "GBPJPY": {"pip_value": 10.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 100.0},
    "AUDUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
}

DEFAULT_PAIR_CONFIG: Dict[str, Any] = {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0}


def get_pip_size(symbol: str) -> float:
    return PIP_SIZES.get(symbol, DEFAULT_PIP_SIZE)


def get_pair_config(symbol: str, config_dict: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    if config_dict and symbol in config_dict:
        return config_dict[symbol]
    return PAIR_CONFIG_DEFAULTS.get(symbol, DEFAULT_PAIR_CONFIG)


def get_pip_value(symbol: str) -> float:
    if symbol == "XAUUSD":
        return 1.0
    return 10.0
