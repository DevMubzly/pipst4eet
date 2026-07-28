from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy


class TrendPullbackStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config.get("strategy", {}).get("trend_pullback", {})
        
        self.fast_ema_period = strategy_config.get("fast_ema_period", 20)
        self.med_ema_period = strategy_config.get("med_ema_period", 50)
        self.slow_ema_period = strategy_config.get("slow_ema_period", 100)
        
        self.rsi_period = strategy_config.get("rsi_period", 14)
        self.rsi_oversold = strategy_config.get("rsi_oversold", 40)
        self.rsi_overbought = strategy_config.get("rsi_overbought", 60)
        
        self.atr_multiplier_sl = strategy_config.get("atr_multiplier_sl", 1.5)
        self.atr_multiplier_tp = strategy_config.get("atr_multiplier_tp", 2.25)
        
        self.min_atr_multiplier = strategy_config.get("min_atr_multiplier", 0.8)
        
        self.require_rsi_confirmation = strategy_config.get("require_rsi_confirmation", True)
        self.require_candle_confirmation = strategy_config.get("require_candle_confirmation", True)
        self.min_candle_body_ratio = strategy_config.get("min_candle_body_ratio", 0.3)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df["ema_fast"] = df["close"].ewm(span=self.fast_ema_period, adjust=False).mean()
        df["ema_med"] = df["close"].ewm(span=self.med_ema_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow_ema_period, adjust=False).mean()
        
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))
        
        df["atr"] = self.compute_atr(df, 14)
        
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
        df["prev_close"] = df["close"].shift(1)
        df["prev_open"] = df["open"].shift(1)
        
        df["uptrend"] = (
            (df["close"] > df["ema_fast"]) &
            (df["ema_fast"] > df["ema_med"]) &
            (df["ema_med"] > df["ema_slow"])
        )
        
        df["downtrend"] = (
            (df["close"] < df["ema_fast"]) &
            (df["ema_fast"] < df["ema_med"]) &
            (df["ema_med"] < df["ema_slow"])
        )
        
        df["touch_ema_fast"] = (
            (df["low"] <= df["ema_fast"] * 1.005) &
            (df["high"] >= df["ema_fast"] * 0.995)
        )
        
        df["touch_ema_med"] = (
            (df["low"] <= df["ema_med"] * 1.005) &
            (df["high"] >= df["ema_med"] * 0.995)
        )
        
        df["close_above_ema_fast"] = df["close"] > df["ema_fast"]
        df["close_below_ema_fast"] = df["close"] < df["ema_fast"]
        
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

        if idx < max(self.fast_ema_period, self.med_ema_period, self.slow_ema_period, self.rsi_period) + 1:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if (pd.isna(row.get("ema_fast")) or 
            pd.isna(row.get("ema_med")) or 
            pd.isna(row.get("ema_slow")) or
            pd.isna(row.get("rsi")) or
            pd.isna(row.get("atr"))):
            return None

        if "atr_median" in df.columns and pd.notna(row.get("atr_median")):
            if row["atr"] < row["atr_median"] * self.min_atr_multiplier:
                return None

        symbol = self._get_symbol(df)
        pip = self._pip_size(symbol)

        uptrend = row["uptrend"]
        downtrend = row["downtrend"]
        
        if not uptrend and not downtrend:
            return None

        candle_body = row["close"] - row["open"]
        candle_range = row["high"] - row["low"]
        body_ratio = abs(candle_body) / candle_range if candle_range > 0 else 0
        is_bullish_candle = candle_body > 0 and body_ratio >= self.min_candle_body_ratio
        is_bearish_candle = candle_body < 0 and body_ratio >= self.min_candle_body_ratio
        
        close_above_prev_high = row["close"] > prev_row["high"]
        close_below_prev_low = row["close"] < prev_row["low"]
        
        rsi_rising = row["rsi"] > prev_row["rsi"]
        rsi_falling = row["rsi"] < prev_row["rsi"]

        touch_ema_fast = row["touch_ema_fast"]
        touch_ema_med = row["touch_ema_med"]
        prev_touch_ema_fast = prev_row["touch_ema_fast"]
        prev_touch_ema_med = prev_row["touch_ema_med"]
        
        near_pullback = (
            touch_ema_fast or 
            touch_ema_med or 
            prev_touch_ema_fast or 
            prev_touch_ema_med
        )

        if uptrend and near_pullback:
            if self.require_candle_confirmation and not (is_bullish_candle or close_above_prev_high):
                pass
            else:
                if self.require_rsi_confirmation and not rsi_rising:
                    pass
                else:
                    atr = row["atr"]
                    sl = row["close"] - (atr * self.atr_multiplier_sl)
                    tp = row["close"] + (atr * self.atr_multiplier_tp)
                    return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_pullback_buy"}

        if downtrend and near_pullback:
            if self.require_candle_confirmation and not (is_bearish_candle or close_below_prev_low):
                pass
            else:
                if self.require_rsi_confirmation and not rsi_falling:
                    pass
                else:
                    atr = row["atr"]
                    sl = row["close"] + (atr * self.atr_multiplier_sl)
                    tp = row["close"] - (atr * self.atr_multiplier_tp)
                    return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_pullback_sell"}

        if uptrend:
            if row["close_above_ema_fast"] and not prev_row["close_above_ema_fast"]:
                if not self.require_candle_confirmation or (is_bullish_candle or close_above_prev_high):
                    if not self.require_rsi_confirmation or rsi_rising:
                        atr = row["atr"]
                        sl = row["close"] - (atr * self.atr_multiplier_sl)
                        tp = row["close"] + (atr * self.atr_multiplier_tp)
                        return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_follow_buy"}

        if downtrend:
            if row["close_below_ema_fast"] and not prev_row["close_below_ema_fast"]:
                if not self.require_candle_confirmation or (is_bearish_candle or close_below_prev_low):
                    if not self.require_rsi_confirmation or rsi_falling:
                        atr = row["atr"]
                        sl = row["close"] + (atr * self.atr_multiplier_sl)
                        tp = row["close"] - (atr * self.atr_multiplier_tp)
                        return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_follow_sell"}

        return None
