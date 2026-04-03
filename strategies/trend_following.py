import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, config):
        self.ema_fast = config["strategy"]["trend"]["ema_fast"]
        self.ema_slow = config["strategy"]["trend"]["ema_slow"]
        self.ema_trend = config["strategy"]["trend"]["ema_trend"]
        self.atr_period = config["strategy"]["trend"]["atr_period"]
        self.atr_sl_mult = config["strategy"]["trend"]["atr_sl_mult"]
        self.atr_tp_mult = config["strategy"]["trend"]["atr_tp_mult"]
        self.min_adx = config["strategy"]["trend"]["min_adx_for_trend"]
        self.pullback_ema = config["strategy"]["trend"]["pullback_ema"]
        self.min_vol_ratio = config["strategy"]["trend"]["min_volatility_ratio"]

    def compute_indicators(self, df):
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["ema_trend"] = df["close"].ewm(span=self.ema_trend, adjust=False).mean()
        df["ema_pullback"] = df["close"].ewm(span=self.pullback_ema, adjust=False).mean()

        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.atr_period).mean()

        atr_pct = df["atr"] / df["close"]
        df["atr_pct_avg"] = atr_pct.rolling(window=50).mean()

        return df

    def generate_signal(self, df, idx, open_positions_for_symbol):
        if open_positions_for_symbol:
            return None

        if idx < self.ema_trend + 2:
            return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        prev2_row = df.iloc[idx - 2]

        if pd.isna(row.get("atr")) or pd.isna(row.get("ema_fast")) or pd.isna(row.get("ema_slow")):
            return None

        if pd.isna(row.get("regime")):
            return None

        if row["regime"] not in ("trending", "weak_trend"):
            return None

        if pd.notna(row.get("adx")) and row["adx"] < 15:
            return None

        ema_fast_val = row["ema_fast"]
        ema_slow_val = row["ema_slow"]
        ema_trend_val = row["ema_trend"]
        prev_fast = prev_row["ema_fast"]
        prev_slow = prev_row["ema_slow"]
        prev2_fast = prev2_row["ema_fast"]
        prev2_slow = prev2_row["ema_slow"]

        bullish_trend = ema_fast_val > ema_slow_val and ema_slow_val > ema_trend_val
        bearish_trend = ema_fast_val < ema_slow_val and ema_slow_val < ema_trend_val

        if not bullish_trend and not bearish_trend:
            return None

        close_val = row["close"]
        atr = row["atr"]

        if bullish_trend:
            pullback_buy = close_val <= row["ema_pullback"] and prev_row["close"] > prev_row["ema_pullback"]
            cross_up = (prev2_fast <= prev2_slow and prev_fast > prev_slow) or (prev_fast <= prev_slow and ema_fast_val > ema_slow_val)

            if cross_up or pullback_buy:
                sl = close_val - (atr * self.atr_sl_mult)
                tp = close_val + (atr * self.atr_tp_mult)
                reason = "trend_bullish_cross" if cross_up else "trend_bullish_pullback"
                return {"direction": "buy", "sl": sl, "tp": tp, "reason": reason}

        if bearish_trend:
            pullback_sell = close_val >= row["ema_pullback"] and prev_row["close"] < prev_row["ema_pullback"]
            cross_down = (prev2_fast >= prev2_slow and prev_fast < prev_slow) or (prev_fast >= prev_slow and ema_fast_val < ema_slow_val)

            if cross_down or pullback_sell:
                sl = close_val + (atr * self.atr_sl_mult)
                tp = close_val - (atr * self.atr_tp_mult)
                reason = "trend_bearish_cross" if cross_down else "trend_bearish_pullback"
                return {"direction": "sell", "sl": sl, "tp": tp, "reason": reason}

        return None
