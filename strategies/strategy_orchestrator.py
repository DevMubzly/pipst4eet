from typing import Dict, Any, Optional
import pandas as pd
from strategies.base_strategy import BaseStrategy, NullStrategy


class StrategyOrchestrator:
    def __init__(
        self,
        config: Dict[str, Any],
        mr_strategy: Optional[BaseStrategy] = None
    ):
        self.config = config
        self.mr_strategy = mr_strategy or NullStrategy()
        self.regime_config = config.get("regime", {})

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.mr_strategy.compute_indicators(df)
        return df

    def select_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        has_open: bool,
        regime: str = "unknown"
    ) -> Optional[Dict[str, Any]]:
        signal = self.mr_strategy.generate_signal(df, idx, has_open, regime)
        return signal
