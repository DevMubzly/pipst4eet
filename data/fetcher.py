import os
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime, timedelta
from twelvedata import TDClient
from dotenv import load_dotenv

load_dotenv()

def get_api_key():
    key = os.getenv("TWELVEDATA_API_KEY")
    if key:
        return key
    key = os.getenv("twelvedata-api-key")
    if key:
        return key
    key = os.getenv("TWELVEDATA-API-KEY")
    return key

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TIMEFRAME_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}

SYMBOL_MAP = {
    "XAUUSD": "XAU/USD",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDUSD": "AUD/USD",
}

class DataFetcher:
    def __init__(self, api_key=None):
        self.api_key = api_key or get_api_key()
        self.client = TDClient(apikey=self.api_key)

    def _get_td_symbol(self, symbol):
        return SYMBOL_MAP.get(symbol, symbol)

    def _get_td_interval(self, timeframe):
        return TIMEFRAME_MAP.get(timeframe, timeframe)

    def fetch_ohlcv(self, symbol, timeframe, start_date, end_date):
        td_symbol = self._get_td_symbol(symbol)
        interval = self._get_td_interval(timeframe)

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        all_frames = []
        chunk_end = end

        while chunk_end > start:
            chunk_start = max(start, chunk_end - pd.Timedelta(days=180))

            ts = TDClient(apikey=self.api_key)
            params = {
                "symbol": td_symbol,
                "interval": interval,
                "start_date": chunk_start.strftime("%Y-%m-%d"),
                "end_date": chunk_end.strftime("%Y-%m-%d"),
                "outputsize": 5000,
            }

            try:
                series = ts.time_series(**params).as_pandas()
            except Exception as e:
                raise Exception(f"Failed to fetch {symbol} ({chunk_start} to {chunk_end}): {e}")

            if series is not None and not series.empty:
                all_frames.append(series)

            chunk_end = chunk_start - pd.Timedelta(seconds=1)

            if chunk_end > start:
                time.sleep(15)

        if not all_frames:
            return pd.DataFrame()

        series = pd.concat(all_frames)

        if series is None or series.empty:
            return pd.DataFrame()

        series.index = pd.to_datetime(series.index)

        required_cols = ["open", "high", "low", "close"]
        for col in required_cols:
            if col not in series.columns:
                raise Exception(f"Missing required column: {col}. Got: {list(series.columns)}")

        if "volume" in series.columns:
            series = series[["open", "high", "low", "close", "volume"]]
        else:
            series = series[["open", "high", "low", "close"]]
            series["volume"] = 0

        series["symbol"] = symbol
        series = series.sort_index()

        return series

    def save_to_parquet(self, df, symbol, timeframe):
        path = DATA_DIR / f"{symbol}_{timeframe}.parquet"
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path)
        return path

    def load_from_parquet(self, symbol, timeframe):
        path = DATA_DIR / f"{symbol}_{timeframe}.parquet"
        if not path.exists():
            return None
        table = pq.read_table(path)
        return table.to_pandas()

    def fetch_and_cache(self, symbol, timeframe, start_date, end_date):
        cached = self.load_from_parquet(symbol, timeframe)

        if cached is not None and not cached.empty:
            last_date = cached.index.max().strftime("%Y-%m-%d")
            if last_date >= end_date:
                return cached

        df = self.fetch_ohlcv(symbol, timeframe, start_date, end_date)

        if df.empty:
            return cached if cached is not None else df

        if cached is not None and not cached.empty:
            df = pd.concat([cached, df])
            df = df[~df.index.duplicated(keep="last")]
            df = df.sort_index()

        self.save_to_parquet(df, symbol, timeframe)
        return df

    def fetch_multi_timeframe(self, symbol, low_tf, high_tf, start_date, end_date):
        low_df = self.fetch_and_cache(symbol, low_tf, start_date, end_date)
        high_df = self.fetch_and_cache(symbol, high_tf, start_date, end_date)
        return low_df, high_df
