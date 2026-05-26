from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config["strategy"]["mean_reversion"]
        self.rsi_period = strategy_config["rsi_period"]
        self.rsi_oversold = strategy_config["rsi_oversold"]
        self.rsi_overbought = strategy_config["rsi_overbought"]
        self.bb_period = strategy_config["bb_period"]
        self.bb_std = strategy_config["bb_std"]
        self.bb_extreme_threshold = strategy_config.get("bb_extreme_threshold", 0.05)
        self.sl_pips = strategy_config["sl_pips"]
        self.tp_pips = strategy_config["tp_pips"]
        self.use_atr = strategy_config.get("use_atr_for_stops", False)
        self.atr_mult_sl = strategy_config.get("atr_multiplier_sl", 1.5)
        self.atr_mult_tp = strategy_config.get("atr_multiplier_tp", 2.5)
        self.min_atr_mult = strategy_config.get("min_atr_multiplier", 0.8)
        self.require_momentum = strategy_config.get("require_momentum_confirmation", False)
        self.rsi_strength = strategy_config.get("rsi_strength_threshold", 5)
        self.require_bullish_candle = strategy_config.get("require_bullish_candle_for_buy", False)
        self.require_bearish_candle = strategy_config.get("require_bearish_candle_for_sell", False)
        self.min_candle_body_ratio = strategy_config.get("min_candle_body_ratio", 0.3)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))

        sma = df["close"].rolling(window=self.bb_period).mean()
        std = df["close"].rolling(window=self.bb_period).std()
        df["bb_upper"] = sma + self.bb_std * std
        df["bb_lower"] = sma - self.bb_std * std
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

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

        if idx < max(self.rsi_period, self.bb_period) + 1:
            return None

        if htf_bias and isinstance(htf_bias, str):
            if "trending" in htf_bias:
                return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if pd.isna(row.get("rsi")) or pd.isna(row.get("bb_pct")):
            return None

        if self.use_atr and pd.notna(row.get("atr")) and pd.notna(row.get("atr_median")):
            if row["atr"] < row["atr_median"] * self.min_atr_mult:
                return None

        symbol = self._get_symbol(df)
        pip = self._pip_size(symbol)

        bb_extreme_low = row["bb_pct"] < self.bb_extreme_threshold
        bb_extreme_high = row["bb_pct"] > (1 - self.bb_extreme_threshold)

        rsi_cross_up = prev_row["rsi"] <= self.rsi_oversold and row["rsi"] > self.rsi_oversold
        rsi_cross_down = prev_row["rsi"] >= self.rsi_overbought and row["rsi"] < self.rsi_overbought

        rsi_strength_up = row["rsi"] - prev_row["rsi"] > self.rsi_strength
        rsi_strength_down = prev_row["rsi"] - row["rsi"] > self.rsi_strength

        candle_body = row["close"] - row["open"]
        candle_range = row["high"] - row["low"]
        body_ratio = abs(candle_body) / candle_range if candle_range > 0 else 0
        is_bullish_candle = candle_body > 0 and body_ratio >= self.min_candle_body_ratio
        is_bearish_candle = candle_body < 0 and body_ratio >= self.min_candle_body_ratio

        if rsi_cross_up and bb_extreme_low:
            if self.require_momentum and not rsi_strength_up:
                return None
            if self.require_bullish_candle and not is_bullish_candle:
                return None

            if self.use_atr and pd.notna(row.get("atr")):
                atr = row["atr"]
                sl = row["close"] - (atr * self.atr_mult_sl)
                tp = row["close"] + (atr * self.atr_mult_tp)
            else:
                sl = row["close"] - (self.sl_pips * pip)
                tp = row["close"] + (self.tp_pips * pip)
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "mr_oversold"}

        if rsi_cross_down and bb_extreme_high:
            if self.require_momentum and not rsi_strength_down:
                return None
            if self.require_bearish_candle and not is_bearish_candle:
                return None

            if self.use_atr and pd.notna(row.get("atr")):
                atr = row["atr"]
                sl = row["close"] + (atr * self.atr_mult_sl)
                tp = row["close"] - (atr * self.atr_mult_tp)
            else:
                sl = row["close"] + (self.sl_pips * pip)
                tp = row["close"] - (self.tp_pips * pip)
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "mr_overbought"}

        return None
