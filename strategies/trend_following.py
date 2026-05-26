from typing import Dict, Any, Optional
import pandas as pd
from strategies.base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config["strategy"]["trend"]
        self.ema_fast = strategy_config["ema_fast"]
        self.ema_slow = strategy_config["ema_slow"]
        self.sl_pips = strategy_config["sl_pips"]
        self.tp_pips = strategy_config["tp_pips"]
        self.min_ema_sep_pct = strategy_config.get("min_ema_separation_pct", 0.02)
        self.use_atr = strategy_config.get("use_atr_for_stops", False)
        self.atr_mult_sl = strategy_config.get("atr_multiplier_sl", 1.5)
        self.atr_mult_tp = strategy_config.get("atr_multiplier_tp", 2.5)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["ema_separation_pct"] = abs(df["ema_fast"] - df["ema_slow"]) / df["close"] * 100

        df["atr"] = self.compute_atr(df, 14)
        df["atr_median"] = df["atr"].rolling(window=100).median()

        return df

    def generate_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        open_positions_for_symbol: bool,
        htf_bias: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if open_positions_for_symbol:
            return None

        if idx < self.ema_slow + 100:
            return None

        if htf_bias and isinstance(htf_bias, str):
            if "ranging" in htf_bias or "weak_range" in htf_bias:
                return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if pd.isna(row.get("ema_fast")) or pd.isna(row.get("ema_slow")):
            return None

        if pd.notna(row.get("ema_separation_pct")) and row["ema_separation_pct"] < self.min_ema_sep_pct:
            return None

        if pd.notna(row.get("atr")) and pd.notna(row.get("atr_median")):
            if row["atr"] < row["atr_median"] * 0.8:
                return None

        symbol = self._get_symbol(df)
        pip = self._pip_size(symbol)

        cross_up = prev_row["ema_fast"] <= prev_row["ema_slow"] and row["ema_fast"] > row["ema_slow"]
        cross_down = prev_row["ema_fast"] >= prev_row["ema_slow"] and row["ema_fast"] < row["ema_slow"]

        if self.use_atr and pd.notna(row.get("atr")):
            atr = row["atr"]
            if cross_up:
                sl = row["close"] - (atr * self.atr_mult_sl)
                tp = row["close"] + (atr * self.atr_mult_tp)
                return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_cross_up"}
            if cross_down:
                sl = row["close"] + (atr * self.atr_mult_sl)
                tp = row["close"] - (atr * self.atr_mult_tp)
                return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_cross_down"}
        else:
            if cross_up:
                sl = row["close"] - (self.sl_pips * pip)
                tp = row["close"] + (self.tp_pips * pip)
                return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_cross_up"}
            if cross_down:
                sl = row["close"] + (self.sl_pips * pip)
                tp = row["close"] - (self.tp_pips * pip)
                return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_cross_down"}

        return None
