import pytest
import pandas as pd
import numpy as np
from constants import (
    PIP_SIZES, DEFAULT_PIP_SIZE, PAIR_CONFIG_DEFAULTS, DEFAULT_PAIR_CONFIG,
    get_pip_size, get_pair_config, get_pip_value
)


class TestConstants:
    def test_pip_sizes_contains_common_pairs(self):
        assert "EURUSD" in PIP_SIZES
        assert "GBPUSD" in PIP_SIZES
        assert "XAUUSD" in PIP_SIZES
        assert "USDJPY" in PIP_SIZES

    def test_get_pip_size_returns_correct_value(self):
        assert get_pip_size("EURUSD") == 0.0001
        assert get_pip_size("XAUUSD") == 0.01
        assert get_pip_size("UNKNOWN") == DEFAULT_PIP_SIZE

    def test_get_pip_value_returns_correct_value(self):
        assert get_pip_value("XAUUSD") == 1.0
        assert get_pip_value("EURUSD") == 10.0
        assert get_pip_value("GBPUSD") == 10.0

    def test_get_pair_config_returns_correct_config(self):
        config = get_pair_config("EURUSD")
        assert config["pip_value"] == 10.0
        assert config["pip_size"] == 0.0001

    def test_get_pair_config_with_custom_dict(self):
        custom_config = {"EURUSD": {"pip_value": 1.0, "pip_size": 0.0001, "min_lot": 0.1, "max_lot": 10.0}}
        config = get_pair_config("EURUSD", custom_config)
        assert config["pip_value"] == 1.0
