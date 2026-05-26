from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy


class SMCSweepStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        strategy_config = config["strategy"]["smc"]
        self.swing_left = strategy_config["swing_left"]
        self.swing_right = strategy_config["swing_right"]
        self.fvg_max_age = strategy_config["fvg_max_age"]
        self.use_atr = strategy_config.get("use_atr_for_stops", False)
        self.atr_mult_sl = strategy_config.get("atr_multiplier_sl", 1.5)
        self.atr_mult_tp = strategy_config.get("atr_multiplier_tp", 2.5)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        left = self.swing_left
        right = self.swing_right

        df["atr"] = self.compute_atr(df, 14)

        df["swing_high"] = self._vectorized_swing_detection(df["high"], left, right, is_high=True)
        df["swing_low"] = self._vectorized_swing_detection(df["low"], left, right, is_high=False)

        df = self._detect_sweeps(df)
        df = self._detect_smc_signals(df)

        return df

    def _vectorized_swing_detection(
        self, series: pd.Series, left: int, right: int, is_high: bool
    ) -> pd.Series:
        window = left + right + 1
        result = pd.Series(False, index=series.index)

        if is_high:
            rolling_max = series.rolling(window=window, center=True).max()
            result.iloc[left:-right] = (
                series.iloc[left:-right] == rolling_max.iloc[left:-right]
            )
        else:
            rolling_min = series.rolling(window=window, center=True).min()
            result.iloc[left:-right] = (
                series.iloc[left:-right] == rolling_min.iloc[left:-right]
            )

        return result

    def _detect_sweeps(self, df: pd.DataFrame) -> pd.DataFrame:
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

        return df

    def _detect_smc_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df["smc_signal"] = None
        df["smc_sl"] = np.nan
        df["smc_tp"] = np.nan

        pip_size = self._pip_size_from_df(df)

        for i in range(len(df)):
            if df["sweep_low"].iloc[i]:
                signal = self._process_bullish_sweep(df, i, pip_size)
                if signal:
                    confirm_idx, sl, tp = signal
                    df.loc[df.index[confirm_idx], "smc_signal"] = "buy"
                    df.loc[df.index[confirm_idx], "smc_sl"] = sl
                    df.loc[df.index[confirm_idx], "smc_tp"] = tp

            elif df["sweep_high"].iloc[i]:
                signal = self._process_bearish_sweep(df, i, pip_size)
                if signal:
                    confirm_idx, sl, tp = signal
                    df.loc[df.index[confirm_idx], "smc_signal"] = "sell"
                    df.loc[df.index[confirm_idx], "smc_sl"] = sl
                    df.loc[df.index[confirm_idx], "smc_tp"] = tp

        return df

    def _process_bullish_sweep(
        self, df: pd.DataFrame, sweep_idx: int, pip_size: float
    ) -> Optional[Tuple[int, float, float]]:
        leg_start = max(0, sweep_idx - self.fvg_max_age)
        fvg_top, fvg_bottom = self._find_fvg(df, leg_start, sweep_idx, "bullish")

        if fvg_top is None:
            return None

        for j in range(sweep_idx + 1, min(len(df), sweep_idx + self.fvg_max_age)):
            if df["low"].iloc[j] <= fvg_top and df["close"].iloc[j] >= fvg_bottom:
                confirm_idx = j + 1
                if confirm_idx < len(df) and df["close"].iloc[confirm_idx] > df["open"].iloc[confirm_idx]:
                    sl, tp = self._calculate_stops(df, confirm_idx, fvg_bottom, "high")
                    return confirm_idx, sl, tp
                break
        return None

    def _process_bearish_sweep(
        self, df: pd.DataFrame, sweep_idx: int, pip_size: float
    ) -> Optional[Tuple[int, float, float]]:
        leg_start = max(0, sweep_idx - self.fvg_max_age)
        fvg_top, fvg_bottom = self._find_fvg(df, leg_start, sweep_idx, "bearish")

        if fvg_top is None:
            return None

        for j in range(sweep_idx + 1, min(len(df), sweep_idx + self.fvg_max_age)):
            if df["high"].iloc[j] >= fvg_bottom and df["close"].iloc[j] <= fvg_top:
                confirm_idx = j + 1
                if confirm_idx < len(df) and df["close"].iloc[confirm_idx] < df["open"].iloc[confirm_idx]:
                    sl, tp = self._calculate_stops(df, confirm_idx, fvg_top, "low")
                    return confirm_idx, sl, tp
                break
        return None

    def _calculate_stops(
        self, df: pd.DataFrame, idx: int, base_level: float, swing_direction: str
    ) -> Tuple[float, float]:
        pip_size = self._pip_size_from_df(df)

        if self.use_atr and pd.notna(df["atr"].iloc[idx]):
            atr = df["atr"].iloc[idx]
            tp = self._find_last_swing(df, idx, swing_direction)

            if swing_direction == "high":
                sl = base_level - (atr * self.atr_mult_sl)
                tp = tp if tp else df["close"].iloc[idx] + (atr * self.atr_mult_tp)
            else:
                sl = base_level + (atr * self.atr_mult_sl)
                tp = tp if tp else df["close"].iloc[idx] - (atr * self.atr_mult_tp)
        else:
            tp = self._find_last_swing(df, idx, swing_direction)

            if swing_direction == "high":
                sl = base_level - (3 * pip_size)
                tp = tp if tp else df["close"].iloc[idx] + (30 * pip_size)
            else:
                sl = base_level + (3 * pip_size)
                tp = tp if tp else df["close"].iloc[idx] - (30 * pip_size)

        return sl, tp

    def _find_fvg(
        self, df: pd.DataFrame, start: int, end: int, direction: str
    ) -> Tuple[Optional[float], Optional[float]]:
        for i in range(start + 2, end + 1):
            if direction == "bullish":
                if df["high"].iloc[i - 2] < df["low"].iloc[i]:
                    return df["low"].iloc[i], df["high"].iloc[i - 2]
            else:
                if df["low"].iloc[i - 2] > df["high"].iloc[i]:
                    return df["low"].iloc[i - 2], df["high"].iloc[i]
        return None, None

    def _find_last_swing(self, df: pd.DataFrame, idx: int, direction: str) -> Optional[float]:
        for i in range(idx - 1, max(0, idx - 300), -1):
            if direction == "high" and df["swing_high"].iloc[i]:
                return df["high"].iloc[i]
            if direction == "low" and df["swing_low"].iloc[i]:
                return df["low"].iloc[i]
        return None

    def _pip_size_from_df(self, df: pd.DataFrame) -> float:
        symbol = self._get_symbol(df)
        return self._pip_size(symbol)

    def generate_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        open_positions_for_symbol: bool,
        htf_bias: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if open_positions_for_symbol:
            return None

        if idx < 50:
            return None

        row = df.iloc[idx]
        if pd.isna(row.get("smc_signal")) or row["smc_signal"] is None:
            return None

        symbol = self._get_symbol(df)

        return {
            "direction": row["smc_signal"],
            "sl": row["smc_sl"],
            "tp": row["smc_tp"],
            "reason": f"smc_sweep_{row['smc_signal']}"
        }
