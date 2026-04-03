import pandas as pd
import numpy as np

class RegimeDetector:
    def __init__(self, config):
        self.adx_period = config["regime"]["adx_period"]
        self.adx_trend = config["regime"]["adx_trend_threshold"]
        self.adx_range = config["regime"]["adx_range_threshold"]
        self.chop_period = config["regime"]["choppiness_period"]
        self.chop_range_thresh = config["regime"]["chop_range_threshold"]
        self.chop_trend_thresh = config["regime"]["chop_trend_threshold"]
        self.bb_period = config["regime"]["bb_period"]
        self.bb_std = config["regime"]["bb_std"]
        self.confirmation = config["regime"]["confirmation_candles"]

    def compute_atr(self, df, period=None):
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

    def compute_adx(self, df):
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

    def compute_choppiness(self, df):
        period = self.chop_period
        high = df["high"]
        low = df["low"]
        close = df["close"]

        atr_sum = self.compute_atr(df, 1).rolling(window=period).sum()
        price_range = high.rolling(window=period).max() - low.rolling(window=period).min()

        chop = 100 * np.log10(atr_sum / price_range) / np.log10(period)
        return chop

    def compute_bb_width(self, df):
        period = self.bb_period
        std = self.bb_std
        sma = df["close"].rolling(window=period).mean()
        upper = sma + std * df["close"].rolling(window=period).std()
        lower = sma - std * df["close"].rolling(window=period).std()
        bb_width = (upper - lower) / sma
        return bb_width, upper, lower, sma

    def detect_regime(self, df):
        adx = self.compute_adx(df)
        chop = self.compute_choppiness(df)
        bb_width, upper, lower, sma = self.compute_bb_width(df)

        df = df.copy()
        df["adx"] = adx
        df["choppiness"] = chop
        df["bb_width"] = bb_width
        df["bb_upper"] = upper
        df["bb_lower"] = lower
        df["bb_sma"] = sma

        trend_votes = 0
        range_votes = 0

        adx_trend = adx > self.adx_trend
        adx_range = adx < self.adx_range
        chop_trend = chop < self.chop_trend_thresh
        chop_range = chop > self.chop_range_thresh

        bb_expanding = bb_width > bb_width.shift(self.confirmation)
        bb_contracting = bb_width < bb_width.shift(self.confirmation)

        for i in range(len(df)):
            if i < self.adx_period * 2:
                df.loc[df.index[i], "regime"] = "unknown"
                continue

            trend_votes = 0
            range_votes = 0

            if adx.iloc[i] > self.adx_trend:
                trend_votes += 1
            elif adx.iloc[i] < self.adx_range:
                range_votes += 1

            if chop.iloc[i] < self.chop_trend_thresh:
                trend_votes += 1
            elif chop.iloc[i] > self.chop_range_thresh:
                range_votes += 1

            if bb_expanding.iloc[i]:
                trend_votes += 1
            elif bb_contracting.iloc[i]:
                range_votes += 1

            if trend_votes >= 2:
                regime = "trending"
            elif range_votes >= 2:
                regime = "ranging"
            else:
                regime = "unknown"

            df.loc[df.index[i], "regime"] = regime

        return df
