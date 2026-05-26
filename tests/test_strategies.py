import pytest
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy, NullStrategy


class TestNullStrategy:
    def test_null_strategy_compute_indicators_returns_df_unchanged(self):
        df = pd.DataFrame({
            "open": [1.0, 1.1, 1.2],
            "high": [1.1, 1.2, 1.3],
            "low": [0.9, 1.0, 1.1],
            "close": [1.05, 1.15, 1.25],
            "volume": [100, 200, 300],
            "symbol": ["EURUSD", "EURUSD", "EURUSD"],
        }, index=pd.date_range("2024-01-01", periods=3, freq="15min"))

        ns = NullStrategy()
        result = ns.compute_indicators(df)

        assert len(result) == 3
        pd.testing.assert_frame_equal(result, df)

    def test_null_strategy_generate_signal_returns_none(self):
        df = pd.DataFrame({
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100],
            "symbol": ["EURUSD"],
        })

        ns = NullStrategy()
        signal = ns.generate_signal(df, 0, False)

        assert signal is None

    def test_null_strategy_generate_signal_with_open_position(self):
        df = pd.DataFrame({
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
        })

        ns = NullStrategy()
        signal = ns.generate_signal(df, 0, True)

        assert signal is None


class TestBaseStrategyHelpers:
    def test_get_symbol_from_df_with_symbol_column(self):
        class TestStrategy(BaseStrategy):
            def compute_indicators(self, df):
                return df
            def generate_signal(self, df, idx, open_pos, htf_bias=None):
                return None

        df = pd.DataFrame({
            "close": [1.0, 1.1],
            "symbol": ["EURUSD", "EURUSD"],
        })

        ts = TestStrategy({})
        symbol = ts._get_symbol(df)

        assert symbol == "EURUSD"

    def test_get_symbol_default(self):
        class TestStrategy(BaseStrategy):
            def compute_indicators(self, df):
                return df
            def generate_signal(self, df, idx, open_pos, htf_bias=None):
                return None

        df = pd.DataFrame({
            "close": [1.0, 1.1],
        })

        ts = TestStrategy({})
        symbol = ts._get_symbol(df)

        assert symbol == "EURUSD"

    def test_pip_size_lookup(self):
        class TestStrategy(BaseStrategy):
            def compute_indicators(self, df):
                return df
            def generate_signal(self, df, idx, open_pos, htf_bias=None):
                return None

        ts = TestStrategy({})

        assert ts._pip_size("XAUUSD") == 0.01
        assert ts._pip_size("EURUSD") == 0.0001
        assert ts._pip_size("UNKNOWN") == 0.0001

    def test_compute_atr(self):
        class TestStrategy(BaseStrategy):
            def compute_indicators(self, df):
                return df
            def generate_signal(self, df, idx, open_pos, htf_bias=None):
                return None

        ts = TestStrategy({})

        np.random.seed(42)
        n = 20
        close = 1.0 + np.cumsum(np.random.normal(0, 0.001, n))
        high = close + np.abs(np.random.normal(0, 0.0005, n))
        low = close - np.abs(np.random.normal(0, 0.0005, n))

        df = pd.DataFrame({
            "high": high,
            "low": low,
            "close": close,
        })

        atr = ts.compute_atr(df, 14)

        assert len(atr) == n
        assert atr.isna().sum() == 13
