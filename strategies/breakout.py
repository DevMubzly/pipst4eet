from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config.get("strategy", {}).get("breakout", {})
        
        self.lookback_period = strategy_config.get("lookback_period", 20)
        self.atr_multiplier_sl = strategy_config.get("atr_multiplier_sl", 1.0)
        self.atr_multiplier_tp = strategy_config.get("atr_multiplier_tp", 1.5)
        
        self.rsi_period = strategy_config.get("rsi_period", 14)
        self.rsi_oversold = strategy_config.get("rsi_oversold", 35)
        self.rsi_overbought = strategy_config.get("rsi_overbought", 65)
        
        self.ema_period = strategy_config.get("ema_period", 50)
        self.min_breakout_threshold = strategy_config.get("min_breakout_threshold", 0.0)
        
        self.require_trend_confirmation = strategy_config.get("require_trend_confirmation", True)
        self.require_rsi_confirmation = strategy_config.get("require_rsi_confirmation", False)
        self.min_candle_body_ratio = strategy_config.get("min_candle_body_ratio", 0.3)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df["ema_trend"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()
        
        df["resistance"] = df["high"].rolling(window=self.lookback_period).max()
        df["support"] = df["low"].rolling(window=self.lookback_period).min()
        
        df["prev_resistance"] = df["resistance"].shift(1)
        df["prev_support"] = df["support"].shift(1)
        
        df["atr"] = self.compute_atr(df, 14)
        
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))
        
        df["uptrend"] = df["close"] > df["ema_trend"]
        df["downtrend"] = df["close"] < df["ema_trend"]
        
        df["breakout_high"] = (
            (df["close"] > df["prev_resistance"]) & 
            (df["high"] > df["prev_resistance"])
        )
        
        df["breakdown_low"] = (
            (df["close"] < df["prev_support"]) & 
            (df["low"] < df["prev_support"])
        )
        
        df["close_above_open"] = df["close"] > df["open"]
        df["close_below_open"] = df["close"] < df["open"]
        
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

        if idx < self.lookback_period + 2:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if (pd.isna(row.get("prev_resistance")) or 
            pd.isna(row.get("prev_support")) or
            pd.isna(row.get("atr")) or
            pd.isna(row.get("ema_trend"))):
            return None

        symbol = self._get_symbol(df)
        pip = self._pip_size(symbol)

        uptrend = row["uptrend"]
        downtrend = row["downtrend"]
        
        if self.require_trend_confirmation:
            if not uptrend and not downtrend:
                return None

        breakout_high = row["breakout_high"]
        breakdown_low = row["breakdown_low"]
        
        if not breakout_high and not breakdown_low:
            return None

        candle_body = row["close"] - row["open"]
        candle_range = row["high"] - row["low"]
        body_ratio = abs(candle_body) / candle_range if candle_range > 0 else 0
        
        strong_bullish = candle_body > 0 and body_ratio >= self.min_candle_body_ratio
        strong_bearish = candle_body < 0 and body_ratio >= self.min_candle_body_ratio

        atr = row["atr"]
        
        if breakout_high:
            if self.require_trend_confirmation and not uptrend:
                return None
            
            if self.require_rsi_confirmation:
                if row["rsi"] < self.rsi_oversold or row["rsi"] > self.rsi_overbought:
                    return None
            
            if not strong_bullish and not row["close_above_open"]:
                return None
            
            sl = row["prev_resistance"] - (atr * self.atr_multiplier_sl)
            tp = row["close"] + (atr * self.atr_multiplier_tp)
            
            if sl >= row["close"]:
                sl = row["close"] - (atr * self.atr_multiplier_sl)
            
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "breakout_high"}

        if breakdown_low:
            if self.require_trend_confirmation and not downtrend:
                return None
            
            if self.require_rsi_confirmation:
                if row["rsi"] < self.rsi_oversold or row["rsi"] > self.rsi_overbought:
                    return None
            
            if not strong_bearish and not row["close_below_open"]:
                return None
            
            sl = row["prev_support"] + (atr * self.atr_multiplier_sl)
            tp = row["close"] - (atr * self.atr_multiplier_tp)
            
            if sl <= row["close"]:
                sl = row["close"] + (atr * self.atr_multiplier_sl)
            
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "breakdown_low"}

        return None
