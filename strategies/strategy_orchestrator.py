from typing import Dict, Any, Optional
import pandas as pd
from strategies.base_strategy import BaseStrategy, NullStrategy


class StrategyOrchestrator:
    def __init__(
        self,
        config: Dict[str, Any],
        trend_strategy: Optional[BaseStrategy] = None,
        mr_strategy: Optional[BaseStrategy] = None,
        smc_strategy: Optional[BaseStrategy] = None
    ):
        self.config = config
        self.trend_strategy = trend_strategy or NullStrategy()
        self.mr_strategy = mr_strategy or NullStrategy()
        self.smc_strategy = smc_strategy or NullStrategy()
        self.regime_config = config.get("regime", {})

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.trend_strategy.compute_indicators(df)
        df = self.mr_strategy.compute_indicators(df)
        df = self.smc_strategy.compute_indicators(df)
        return df

    def select_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        has_open: bool,
        regime: str = "unknown"
    ) -> Optional[Dict[str, Any]]:
        signal = None

        if self.regime_config.get("enable_regime_filter", False):
            prefer_trend = self.regime_config.get("prefer_trend_in_trending", True)
            prefer_mr = self.regime_config.get("prefer_mr_in_ranging", True)

            if "trending" in regime and prefer_trend:
                signal = self.smc_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.trend_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.mr_strategy.generate_signal(df, idx, has_open, regime)
            elif ("ranging" in regime or "weak_range" in regime) and prefer_mr:
                signal = self.smc_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.mr_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.trend_strategy.generate_signal(df, idx, has_open, regime)
            else:
                signal = self.smc_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.trend_strategy.generate_signal(df, idx, has_open, regime)
                if signal is None:
                    signal = self.mr_strategy.generate_signal(df, idx, has_open, regime)
        else:
            signal = self.smc_strategy.generate_signal(df, idx, has_open)
            if signal is None:
                signal = self.trend_strategy.generate_signal(df, idx, has_open)
            if signal is None:
                signal = self.mr_strategy.generate_signal(df, idx, has_open)

        return signal
