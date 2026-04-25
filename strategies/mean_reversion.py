import pandas as pd
import numpy as np

class MeanReversionStrategy:
    def __init__(self, config):
        self.rsi_period = config["strategy"]["mean_reversion"]["rsi_period"]
        self.rsi_oversold = config["strategy"]["mean_reversion"]["rsi_oversold"]
        self.rsi_overbought = config["strategy"]["mean_reversion"]["rsi_overbought"]
        self.bb_period = config["strategy"]["mean_reversion"]["bb_period"]
        self.bb_std = config["strategy"]["mean_reversion"]["bb_std"]
        self.sl_pips = config["strategy"]["mean_reversion"]["sl_pips"]
        self.tp_pips = config["strategy"]["mean_reversion"]["tp_pips"]
        self.use_atr = config["strategy"]["mean_reversion"].get("use_atr_for_stops", False)
        self.atr_mult_sl = config["strategy"]["mean_reversion"].get("atr_multiplier_sl", 1.5)
        self.atr_mult_tp = config["strategy"]["mean_reversion"].get("atr_multiplier_tp", 2.5)

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

    def _pip_size(self, symbol):
        return self.pip_sizes.get(symbol, 0.0001)

    def generate_signal(self, df, idx, open_positions_for_symbol, htf_bias=None):
        if open_positions_for_symbol:
            return None

        if idx < max(self.rsi_period, self.bb_period) + 1:
            return None

        # Filter based on regime if provided
        if htf_bias and isinstance(htf_bias, str):
            # Mean reversion works best in ranging markets
            if "trending" in htf_bias:
                return None

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        if pd.isna(row.get("rsi")) or pd.isna(row.get("bb_pct")):
            return None

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"
        pip = self._pip_size(symbol)

        rsi_cross_up = prev_row["rsi"] <= self.rsi_oversold and row["rsi"] > self.rsi_oversold
        bb_low = row["bb_pct"] < 0.1

        if rsi_cross_up and bb_low:
            if self.use_atr and pd.notna(row.get("atr")):
                atr = row["atr"]
                sl = row["close"] - (atr * self.atr_mult_sl)
                tp = row["close"] + (atr * self.atr_mult_tp)
            else:
                sl = row["close"] - (self.sl_pips * pip)
                tp = row["close"] + (self.tp_pips * pip)
            return {"direction": "buy", "sl": sl, "tp": tp, "reason": "mr_oversold"}

        rsi_cross_down = prev_row["rsi"] >= self.rsi_overbought and row["rsi"] < self.rsi_overbought
        bb_high = row["bb_pct"] > 0.9

        if rsi_cross_down and bb_high:
            if self.use_atr and pd.notna(row.get("atr")):
                atr = row["atr"]
                sl = row["close"] + (atr * self.atr_mult_sl)
                tp = row["close"] - (atr * self.atr_mult_tp)
            else:
                sl = row["close"] + (self.sl_pips * pip)
                tp = row["close"] - (self.tp_pips * pip)
            return {"direction": "sell", "sl": sl, "tp": tp, "reason": "mr_overbought"}

        return None
