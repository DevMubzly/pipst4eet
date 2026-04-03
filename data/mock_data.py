import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_ohlcv(symbol, timeframe, start_date, end_date, save_path=None):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if timeframe == "15m":
        freq = "15min"
    elif timeframe == "1h":
        freq = "1h"
    elif timeframe == "5m":
        freq = "5min"
    else:
        freq = "15min"

    all_timestamps = pd.date_range(start=start, end=end, freq=freq)

    market_hours = []
    for ts in all_timestamps:
        if ts.weekday() < 5 and 7 <= ts.hour <= 21:
            market_hours.append(ts)

    timestamps = pd.DatetimeIndex(market_hours)

    base_prices = {
        "XAUUSD": 2025.00,
        "EURUSD": 1.0850,
        "GBPUSD": 1.2650,
        "USDJPY": 149.50,
        "GBPJPY": 189.50,
        "AUDUSD": 0.6550,
    }

    base = base_prices.get(symbol, 1.0)
    np.random.seed(hash(symbol) % 2**32)

    n = len(timestamps)
    returns = np.random.normal(0.00002, 0.0003, n)

    for i in range(n):
        hour = timestamps[i].hour
        if 8 <= hour <= 10 or 13 <= hour <= 15:
            returns[i] *= 1.8
        elif 11 <= hour <= 12 or 16 <= hour <= 17:
            returns[i] *= 1.3
        elif 19 <= hour <= 21 or 7 <= hour <= 8:
            returns[i] *= 0.5

    n_trends = np.random.randint(4, 8)
    trend_starts = np.sort(np.random.choice(n, n_trends, replace=False))
    trend_dirs = np.random.choice([-1, 1], n_trends)

    trend_signal = np.zeros(n)
    for j, (t_start, t_dir) in enumerate(zip(trend_starts, trend_dirs)):
        t_end = trend_starts[j + 1] if j + 1 < n_trends else n
        length = t_end - t_start
        if length > 10:
            trend_signal[t_start:t_end] = t_dir * 0.0001 * np.linspace(0, 1, length)

    returns += trend_signal

    for i in range(n):
        hour = timestamps[i].hour
        if 10 <= hour <= 14:
            returns[i] += np.sin(i / 50) * 0.0001

    close = base * np.cumprod(1 + returns)

    vol = base * 0.0002
    noise = np.abs(np.random.normal(0, vol, n))
    high = close + noise
    low = close - noise
    open_prices = np.roll(close, 1)
    open_prices[0] = base

    high = np.maximum(high, np.maximum(open_prices, close))
    low = np.minimum(low, np.minimum(open_prices, close))

    volume = np.random.randint(100, 3000, n)
    for i in range(n):
        hour = timestamps[i].hour
        if 8 <= hour <= 10 or 13 <= hour <= 15:
            volume[i] = int(volume[i] * 1.5)

    df = pd.DataFrame({
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "symbol": symbol,
    }, index=timestamps)

    df.index.name = "datetime"

    if save_path:
        df.to_parquet(save_path)

    return df
