from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
from constants import get_pip_size


class BaseStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        open_positions_for_symbol: bool,
        htf_bias: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        pass

    def _get_symbol(self, df: pd.DataFrame) -> str:
        return df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"

    def _pip_size(self, symbol: str) -> float:
        return get_pip_size(symbol)

    def compute_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr


class NullStrategy(BaseStrategy):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def generate_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        open_positions_for_symbol: bool,
        htf_bias: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return None
