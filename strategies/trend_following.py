import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, config):
        self.ema_fast = config["strategy"]["trend"]["ema_fast"]
        self.ema_slow = config["strategy"]["trend"]["ema_slow"]
        self.sl_pips = config["strategy"]["trend"]["sl_pips"]
        self.tp_pips = config["strategy"]["trend"]["tp_pips"]
        self.min_ema_sep_pct = config["strategy"]["trend"].get("min_ema_separation_pct", 0.02)

        self.pip_sizes = {
            "XAUUSD": 0.01,
            "EURUSD": 0.0001,
            "GBPUSD": 0.0001,
            "USDJPY": 0.01,
            "GBPJPY": 0.01,
            "AUDUSD": 0.0001,
        }

    def compute_indicators(self, df):
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["ema_separation_pct"] = abs(df["ema_fast"] - df["ema_slow"]) / df["close"] * 100

        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()
        df["atr_median"] = df["atr"].rolling(window=100).median()

        return df

    def _pip_size(self, symbol):
        return self.pip_sizes.get(symbol, 0.0001)

    def generate_signal(self, df, idx, open_positions_for_symbol, htf_bias=None):
        if open_positions_for_symbol:
            return None

        if idx < self.ema_slow + 100:
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

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"
        pip = self._pip_size(symbol)

        cross_up = prev_row["ema_fast"] <= prev_row["ema_slow"] and row["ema_fast"] > row["ema_slow"]
        cross_down = prev_row["ema_fast"] >= prev_row["ema_slow"] and row["ema_fast"] < row["ema_slow"]

        if cross_up:
            sl = row["close"] - (self.sl_pips * pip)
            tp = row["close"] + (self.tp_pips * pip)
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "trend_cross_up"}

        if cross_down:
            sl = row["close"] + (self.sl_pips * pip)
            tp = row["close"] - (self.tp_pips * pip)
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "trend_cross_down"}

        return None
