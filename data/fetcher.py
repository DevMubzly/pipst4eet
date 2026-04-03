import os
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime, timedelta
from twelvedata import TDClient
from dotenv import load_dotenv

load_dotenv()

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
        self.api_key = api_key or os.getenv("TWELVEDATA_API_KEY")
        self.client = TDClient(apikey=self.api_key)

    def _get_td_symbol(self, symbol):
        return SYMBOL_MAP.get(symbol, symbol)

    def _get_td_interval(self, timeframe):
        return TIMEFRAME_MAP.get(timeframe, timeframe)

    def fetch_ohlcv(self, symbol, timeframe, start_date, end_date):
        td_symbol = self._get_td_symbol(symbol)
        interval = self._get_td_interval(timeframe)

        ts = TDClient(apikey=self.api_key)
        params = {
            "symbol": td_symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": 5000,
        }

        try:
            series = ts.time_series(**params).as_pandas()
        except Exception as e:
            raise Exception(f"Failed to fetch {symbol}: {e}")

        if series is None or series.empty:
            return pd.DataFrame()

        series = series.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        })

        series.index = pd.to_datetime(series.index)
        series = series[["open", "high", "low", "close", "volume"]]
        series["symbol"] = symbol

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
