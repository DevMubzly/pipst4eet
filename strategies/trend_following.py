import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, config):
        self.ema_fast = config["strategy"]["trend"]["ema_fast"]
        self.ema_slow = config["strategy"]["trend"]["ema_slow"]
        self.atr_period = config["strategy"]["trend"]["atr_period"]
        self.atr_sl_mult = config["strategy"]["trend"]["atr_sl_mult"]
        self.atr_tp_mult = config["strategy"]["trend"]["atr_tp_mult"]

    def compute_indicators(self, df):
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["ema_diff"] = df["ema_fast"] - df["ema_slow"]

        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.atr_period).mean()

        return df

    def generate_signal(self, df, idx, open_positions_for_symbol):
        if open_positions_for_symbol:
            return None

        if idx < self.ema_slow + 2:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        prev2_row = df.iloc[idx - 2]

        if pd.isna(row.get("atr")) or pd.isna(row.get("ema_fast")) or pd.isna(row.get("ema_slow")):
            return None

        if pd.isna(row.get("regime")) or row["regime"] != "trending":
            return None

        prev_crossed_up = prev2_row["ema_fast"] <= prev2_row["ema_slow"] and prev_row["ema_fast"] > prev_row["ema_slow"]
        curr_crossed_up = prev_row["ema_fast"] <= prev_row["ema_slow"] and row["ema_fast"] > row["ema_slow"]

        if prev_crossed_up or curr_crossed_up:
            atr = row["atr"]
            sl = row["close"] - (atr * self.atr_sl_mult)
            tp = row["close"] + (atr * self.atr_tp_mult)
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_bullish_cross"}

        prev_crossed_down = prev2_row["ema_fast"] >= prev2_row["ema_slow"] and prev_row["ema_fast"] < prev_row["ema_slow"]
        curr_crossed_down = prev_row["ema_fast"] >= prev_row["ema_slow"] and row["ema_fast"] < row["ema_slow"]

        if prev_crossed_down or curr_crossed_down:
            atr = row["atr"]
            sl = row["close"] + (atr * self.atr_sl_mult)
            tp = row["close"] - (atr * self.atr_tp_mult)
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_bearish_cross"}

        return None
