from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy


class ScalpingStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config.get("strategy", {}).get("scalping", {})
        
        self.fast_ema_period = strategy_config.get("fast_ema_period", 9)
        self.slow_ema_period = strategy_config.get("slow_ema_period", 20)
        self.trend_ema_period = strategy_config.get("trend_ema_period", 50)
        
        self.rsi_period = strategy_config.get("rsi_period", 14)
        self.rsi_oversold = strategy_config.get("rsi_oversold", 45)
        self.rsi_overbought = strategy_config.get("rsi_overbought", 55)
        
        self.atr_period = strategy_config.get("atr_period", 14)
        self.atr_multiplier_sl = strategy_config.get("atr_multiplier_sl", 0.6)
        self.atr_multiplier_tp = strategy_config.get("atr_multiplier_tp", 0.9)
        self.min_atr_multiplier = strategy_config.get("min_atr_multiplier", 0.4)
        
        self.require_pullback = strategy_config.get("require_pullback", True)
        self.pullback_candles = strategy_config.get("pullback_candles", 2)
        
        self.require_candle_confirmation = strategy_config.get("require_candle_confirmation", True)
        self.min_candle_body_ratio = strategy_config.get("min_candle_body_ratio", 0.4)
        
        self.enable_break_even = strategy_config.get("enable_break_even", True)
        self.break_even_at_r = strategy_config.get("break_even_at_r", 0.5)
        self.break_even_move_r = strategy_config.get("break_even_move_r", 0.2)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df["ema_fast"] = df["close"].ewm(span=self.fast_ema_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow_ema_period, adjust=False).mean()
        df["ema_trend"] = df["close"].ewm(span=self.trend_ema_period, adjust=False).mean()
        
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))
        
        df["atr"] = self.compute_atr(df, self.atr_period)
        
        for i in range(1, 6):
            df[f"prev_close_{i}"] = df["close"].shift(i)
            df[f"prev_high_{i}"] = df["high"].shift(i)
            df[f"prev_low_{i}"] = df["low"].shift(i)
            df[f"prev_open_{i}"] = df["open"].shift(i)
        
        df["candle_body"] = df["close"] - df["open"]
        df["candle_range"] = df["high"] - df["low"]
        df["body_ratio"] = abs(df["candle_body"]) / df["candle_range"].replace(0, 0.0001)
        
        df["is_bullish"] = (df["candle_body"] > 0) & (df["body_ratio"] >= self.min_candle_body_ratio)
        df["is_bearish"] = (df["candle_body"] < 0) & (df["body_ratio"] >= self.min_candle_body_ratio)
        
        df["price_above_trend"] = df["close"] > df["ema_trend"]
        df["price_below_trend"] = df["close"] < df["ema_trend"]
        
        df["fast_above_slow"] = df["ema_fast"] > df["ema_slow"]
        df["fast_below_slow"] = df["ema_fast"] < df["ema_slow"]
        
        df["uptrend"] = df["price_above_trend"] & df["fast_above_slow"]
        df["downtrend"] = df["price_below_trend"] & df["fast_below_slow"]
        
        df["pullback_to_ema_slow"] = False
        df["pullback_to_ema_fast"] = False
        
        for i in range(len(df)):
            if i < self.pullback_candles:
                continue
                
            curr_close = df["close"].iloc[i]
            curr_ema_slow = df["ema_slow"].iloc[i]
            curr_ema_fast = df["ema_fast"].iloc[i]
            
            if df["uptrend"].iloc[i]:
                touch_slow = False
                touch_fast = False
                for j in range(1, self.pullback_candles + 1):
                    if i - j >= 0:
                        prev_low = df["low"].iloc[i - j]
                        prev_ema_slow = df["ema_slow"].iloc[i - j]
                        prev_ema_fast = df["ema_fast"].iloc[i - j]
                        if prev_low <= prev_ema_slow * 1.001:
                            touch_slow = True
                        if prev_low <= prev_ema_fast * 1.001:
                            touch_fast = True
                df.iloc[i, df.columns.get_loc("pullback_to_ema_slow")] = touch_slow
                df.iloc[i, df.columns.get_loc("pullback_to_ema_fast")] = touch_fast
                
            elif df["downtrend"].iloc[i]:
                touch_slow = False
                touch_fast = False
                for j in range(1, self.pullback_candles + 1):
                    if i - j >= 0:
                        prev_high = df["high"].iloc[i - j]
                        prev_ema_slow = df["ema_slow"].iloc[i - j]
                        prev_ema_fast = df["ema_fast"].iloc[i - j]
                        if prev_high >= prev_ema_slow * 0.999:
                            touch_slow = True
                        if prev_high >= prev_ema_fast * 0.999:
                            touch_fast = True
                df.iloc[i, df.columns.get_loc("pullback_to_ema_slow")] = touch_slow
                df.iloc[i, df.columns.get_loc("pullback_to_ema_fast")] = touch_fast
        
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

        min_period = max(self.fast_ema_period, self.slow_ema_period, self.trend_ema_period, self.rsi_period, self.atr_period)
        if idx < min_period + 5:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if pd.isna(row.get("ema_trend")) or pd.isna(row.get("rsi")) or pd.isna(row.get("atr")):
            return None

        if row["atr"] < 0.0005:
            return None

        symbol = self._get_symbol(df)
        pip = self._pip_size(symbol)

        buy_signal = False
        sell_signal = False
        reason = ""

        if row["uptrend"]:
            rsi_ok = row["rsi"] >= self.rsi_oversold and row["rsi"] <= 65
            
            if self.require_pullback:
                pullback_ok = row["pullback_to_ema_slow"] or row["pullback_to_ema_fast"]
            else:
                pullback_ok = row["close"] >= row["ema_slow"] * 0.998
            
            candle_ok = True
            if self.require_candle_confirmation:
                candle_ok = row["is_bullish"]
            
            if rsi_ok and pullback_ok and candle_ok:
                buy_signal = True
                reason = "scalp_uptrend_pullback"

        elif row["downtrend"]:
            rsi_ok = row["rsi"] <= self.rsi_overbought and row["rsi"] >= 35
            
            if self.require_pullback:
                pullback_ok = row["pullback_to_ema_slow"] or row["pullback_to_ema_fast"]
            else:
                pullback_ok = row["close"] <= row["ema_slow"] * 1.002
            
            candle_ok = True
            if self.require_candle_confirmation:
                candle_ok = row["is_bearish"]
            
            if rsi_ok and pullback_ok and candle_ok:
                sell_signal = True
                reason = "scalp_downtrend_pullback"

        if buy_signal:
            atr = row["atr"]
            entry = row["close"]
            sl = entry - (atr * self.atr_multiplier_sl)
            tp = entry + (atr * self.atr_multiplier_tp)
            return {
                "direction": "buy",
                "sl": sl,
                "tp": tp,
                "reason": reason,
                "enable_break_even": self.enable_break_even,
                "break_even_at_r": self.break_even_at_r,
                "break_even_move_r": self.break_even_move_r
            }

        if sell_signal:
            atr = row["atr"]
            entry = row["close"]
            sl = entry + (atr * self.atr_multiplier_sl)
            tp = entry - (atr * self.atr_multiplier_tp)
            return {
                "direction": "sell",
                "sl": sl,
                "tp": tp,
                "reason": reason,
                "enable_break_even": self.enable_break_even,
                "break_even_at_r": self.break_even_at_r,
                "break_even_move_r": self.break_even_move_r
            }

        return None
