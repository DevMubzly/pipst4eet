import pandas as pd
import numpy as np

class MeanReversionStrategy:
    def __init__(self, config):
        self.rsi_period = config["strategy"]["mean_reversion"]["rsi_period"]
        self.rsi_oversold = config["strategy"]["mean_reversion"]["rsi_oversold"]
        self.rsi_overbought = config["strategy"]["mean_reversion"]["rsi_overbought"]
        self.bb_period = config["strategy"]["mean_reversion"]["bb_period"]
        self.bb_std = config["strategy"]["mean_reversion"]["bb_std"]
        self.atr_period = config["strategy"]["mean_reversion"]["atr_period"]
        self.atr_sl_mult = config["strategy"]["mean_reversion"]["atr_sl_mult"]
        self.atr_tp_mult = config["strategy"]["mean_reversion"]["atr_tp_mult"]

    def compute_indicators(self, df):
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
        df["bb_sma"] = sma

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

        if idx < max(self.rsi_period, self.bb_period, self.atr_period) + 2:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        prev2_row = df.iloc[idx - 2]

        if pd.isna(row.get("atr")) or pd.isna(row.get("rsi")):
            return None

        if pd.isna(row.get("regime")) or row["regime"] != "ranging":
            return None

        touched_lower = row["low"] <= row["bb_lower"] or prev_row["low"] <= prev_row["bb_lower"]
        rsi_recovering = row["rsi"] > self.rsi_oversold and prev_row["rsi"] <= self.rsi_oversold

        if touched_lower and rsi_recovering:
            atr = row["atr"]
            sl = row["close"] - (atr * self.atr_sl_mult)
            tp = row["bb_sma"]
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "mr_oversold"}

        touched_upper = row["high"] >= row["bb_upper"] or prev_row["high"] >= prev_row["bb_upper"]
        rsi_declining = row["rsi"] < self.rsi_overbought and prev_row["rsi"] >= self.rsi_overbought

        if touched_upper and rsi_declining:
            atr = row["atr"]
            sl = row["close"] + (atr * self.atr_sl_mult)
            tp = row["bb_sma"]
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "mr_overbought"}

        return None
