from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np


class RegimeDetector:
    def __init__(self, config: Dict[str, Any]):
        regime_config = config["regime"]
        self.adx_period = regime_config["adx_period"]
        self.adx_trend = regime_config["adx_trend_threshold"]
        self.adx_range = regime_config["adx_range_threshold"]
        self.chop_period = regime_config["choppiness_period"]
        self.chop_range_thresh = regime_config["chop_range_threshold"]
        self.chop_trend_thresh = regime_config["chop_trend_threshold"]
        self.bb_period = regime_config["bb_period"]
        self.bb_std = regime_config["bb_std"]
        self.confirmation = regime_config["confirmation_candles"]
        self.atr_lookback = regime_config["atr_lookback"]

    def compute_atr(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        period = period or self.adx_period
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def compute_adx(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        period = self.adx_period

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        atr = self.compute_atr(df, period)
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def compute_choppiness(self, df: pd.DataFrame) -> pd.Series:
        period = self.chop_period
        atr_1 = self.compute_atr(df, 1)
        atr_sum = atr_1.rolling(window=period).sum()
        price_range = df["high"].rolling(window=period).max() - df["low"].rolling(window=period).min()
        chop = 100 * np.log10(atr_sum / price_range) / np.log10(period)
        return chop

    def compute_bb_width(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        period = self.bb_period
        std = self.bb_std
        sma = df["close"].rolling(window=period).mean()
        std_dev = df["close"].rolling(window=period).std()
        upper = sma + std * std_dev
        lower = sma - std * std_dev
        bb_width = (upper - lower) / sma
        return bb_width, upper, lower, sma

    def detect_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        adx = self.compute_adx(df)
        chop = self.compute_choppiness(df)
        bb_width, upper, lower, sma = self.compute_bb_width(df)
        atr = self.compute_atr(df, self.adx_period)

        df = df.copy()
        df["adx"] = adx
        df["choppiness"] = chop
        df["bb_width"] = bb_width
        df["bb_upper"] = upper
        df["bb_lower"] = lower
        df["bb_sma"] = sma
        df["atr"] = atr
        df["regime"] = "unknown"

        min_idx = self.adx_period * 3

        trend_votes = pd.Series(0, index=df.index)
        range_votes = pd.Series(0, index=df.index)

        trend_votes = trend_votes + np.where(adx > self.adx_trend, 2, 0)
        range_votes = range_votes + np.where(adx < self.adx_range, 2, 0)
        range_votes = range_votes + np.where((adx >= self.adx_range) & (adx < 25), 1, 0)

        trend_votes = trend_votes + np.where(chop < self.chop_trend_thresh, 2, 0)
        range_votes = range_votes + np.where(chop > self.chop_range_thresh, 2, 0)
        range_votes = range_votes + np.where((chop <= self.chop_range_thresh) & (chop > 50), 1, 0)

        bb_w_avg = bb_width.rolling(window=self.confirmation * 3).mean()
        trend_votes = trend_votes + np.where(bb_width > bb_w_avg * 1.1, 1, 0)
        range_votes = range_votes + np.where(bb_width < bb_w_avg * 0.9, 1, 0)

        conditions = [
            (trend_votes >= 3),
            (range_votes >= 3),
            (trend_votes >= range_votes),
        ]
        choices = ["trending", "ranging", "weak_trend"]

        df.loc[df.index[min_idx:], "regime"] = np.select(
            conditions, choices, default="weak_range"
        )

        return df
