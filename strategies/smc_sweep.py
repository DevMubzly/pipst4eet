import pandas as pd
import numpy as np

class SMCSweepStrategy:
    def __init__(self, config):
        self.swing_left = config["strategy"]["smc"]["swing_left"]
        self.swing_right = config["strategy"]["smc"]["swing_right"]
        self.fvg_max_age = config["strategy"]["smc"]["fvg_max_age"]
        self.use_atr = config["strategy"]["smc"].get("use_atr_for_stops", False)
        self.atr_mult_sl = config["strategy"]["smc"].get("atr_multiplier_sl", 1.5)
        self.atr_mult_tp = config["strategy"]["smc"].get("atr_multiplier_tp", 2.5)

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
        left = self.swing_left
        right = self.swing_right

        # Add ATR calculation for adaptive stops
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()

        df["swing_high"] = False
        df["swing_low"] = False

        for i in range(left, len(df) - right):
            is_high = True
            is_low = True
            for j in range(-left, right + 1):
                if j == 0:
                    continue
                if df["high"].iloc[i + j] >= df["high"].iloc[i]:
                    is_high = False
                if df["low"].iloc[i + j] <= df["low"].iloc[i]:
                    is_low = False
            if is_high:
                df.loc[df.index[i], "swing_high"] = True
            if is_low:
                df.loc[df.index[i], "swing_low"] = True

        df["sweep_high"] = False
        df["sweep_low"] = False

        last_swing_high_price = None
        last_swing_low_price = None

        for i in range(len(df)):
            if df["swing_high"].iloc[i]:
                last_swing_high_price = df["high"].iloc[i]
            if df["swing_low"].iloc[i]:
                last_swing_low_price = df["low"].iloc[i]

            if last_swing_high_price is not None and df["close"].iloc[i] > last_swing_high_price:
                df.loc[df.index[i], "sweep_high"] = True
                last_swing_high_price = None

            if last_swing_low_price is not None and df["close"].iloc[i] < last_swing_low_price:
                df.loc[df.index[i], "sweep_low"] = True
                last_swing_low_price = None

        df["smc_signal"] = None
        df["smc_sl"] = np.nan
        df["smc_tp"] = np.nan

        for i in range(len(df)):
            if df["sweep_low"].iloc[i]:
                sweep_idx = i
                leg_start = max(0, sweep_idx - self.fvg_max_age)
                fvg_top, fvg_bottom = self._find_fvg(df, leg_start, sweep_idx, "bullish")

                if fvg_top is not None:
                    for j in range(sweep_idx + 1, min(len(df), sweep_idx + self.fvg_max_age)):
                        if df["low"].iloc[j] <= fvg_top and df["close"].iloc[j] >= fvg_bottom:
                            confirm_idx = j + 1
                            if confirm_idx < len(df) and df["close"].iloc[confirm_idx] > df["open"].iloc[confirm_idx]:
                                df.loc[df.index[confirm_idx], "smc_signal"] = "buy"
                                # Use ATR for adaptive stops if enabled
                                if self.use_atr and pd.notna(df["atr"].iloc[confirm_idx]):
                                    atr = df["atr"].iloc[confirm_idx]
                                    df.loc[df.index[confirm_idx], "smc_sl"] = fvg_bottom - (atr * self.atr_mult_sl)
                                    tp = self._find_last_swing(df, sweep_idx, "high")
                                    df.loc[df.index[confirm_idx], "smc_tp"] = tp if tp else df["close"].iloc[confirm_idx] + (atr * self.atr_mult_tp)
                                else:
                                    df.loc[df.index[confirm_idx], "smc_sl"] = fvg_bottom - (3 * self._pip_size_from_df(df))
                                    tp = self._find_last_swing(df, sweep_idx, "high")
                                    df.loc[df.index[confirm_idx], "smc_tp"] = tp if tp else df["close"].iloc[confirm_idx] + (30 * self._pip_size_from_df(df))
                            break

            if df["sweep_high"].iloc[i]:
                sweep_idx = i
                leg_start = max(0, sweep_idx - self.fvg_max_age)
                fvg_top, fvg_bottom = self._find_fvg(df, leg_start, sweep_idx, "bearish")

                if fvg_top is not None:
                    for j in range(sweep_idx + 1, min(len(df), sweep_idx + self.fvg_max_age)):
                        if df["high"].iloc[j] >= fvg_bottom and df["close"].iloc[j] <= fvg_top:
                            confirm_idx = j + 1
                            if confirm_idx < len(df) and df["close"].iloc[confirm_idx] < df["open"].iloc[confirm_idx]:
                                df.loc[df.index[confirm_idx], "smc_signal"] = "sell"
                                # Use ATR for adaptive stops if enabled
                                if self.use_atr and pd.notna(df["atr"].iloc[confirm_idx]):
                                    atr = df["atr"].iloc[confirm_idx]
                                    df.loc[df.index[confirm_idx], "smc_sl"] = fvg_top + (atr * self.atr_mult_sl)
                                    tp = self._find_last_swing(df, sweep_idx, "low")
                                    df.loc[df.index[confirm_idx], "smc_tp"] = tp if tp else df["close"].iloc[confirm_idx] - (atr * self.atr_mult_tp)
                                else:
                                    df.loc[df.index[confirm_idx], "smc_sl"] = fvg_top + (3 * self._pip_size_from_df(df))
                                    tp = self._find_last_swing(df, sweep_idx, "low")
                                    df.loc[df.index[confirm_idx], "smc_tp"] = tp if tp else df["close"].iloc[confirm_idx] - (30 * self._pip_size_from_df(df))
                            break

        return df

    def _find_fvg(self, df, start, end, direction):
        for i in range(start + 2, end + 1):
            if direction == "bullish":
                if df["high"].iloc[i - 2] < df["low"].iloc[i]:
                    return df["low"].iloc[i], df["high"].iloc[i - 2]
            else:
                if df["low"].iloc[i - 2] > df["high"].iloc[i]:
                    return df["low"].iloc[i - 2], df["high"].iloc[i]
        return None, None

    def _find_last_swing(self, df, idx, direction):
        for i in range(idx - 1, max(0, idx - 300), -1):
            if direction == "high" and df["swing_high"].iloc[i]:
                return df["high"].iloc[i]
            if direction == "low" and df["swing_low"].iloc[i]:
                return df["low"].iloc[i]
        return None

    def _pip_size_from_df(self, df):
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"
        return self.pip_sizes.get(symbol, 0.0001)

    def _pip_size(self, symbol):
        return self.pip_sizes.get(symbol, 0.0001)

    def generate_signal(self, df, idx, open_positions_for_symbol, htf_bias=None):
        if open_positions_for_symbol:
            return None

        if idx < 50:
            return None

        row = df.iloc[idx]
        if pd.isna(row.get("smc_signal")) or row["smc_signal"] is None:
            return None

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"

        return {
            "direction": row["smc_signal"],
            "sl": row["smc_sl"],
            "tp": row["smc_tp"],
            "reason": f"smc_sweep_{row['smc_signal']}"
        }
