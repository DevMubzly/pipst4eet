# pipst4eet

A Mean Reversion algorithmic trading bot for Forex with backtesting capabilities.

## Strategy

**Mean Reversion (RSI + Bollinger Bands)**

The bot trades only ranging markets using:
- **RSI (14)**: Oversold (<25) / Overbought (>75)
- **Bollinger Bands (20, 2.0)**: Extreme percentile-based thresholds
- **Regime Filter**: Uses ADX + Choppiness + BB Width to only trade in ranging markets
- **Stops**: 1.5× ATR (SL) / 6.0× ATR (TP) for favorable risk:reward

## Features

- **Market Regime Detection**: ADX, Choppiness Index, Bollinger Band width voting system
- **Backtesting Engine**: Walk-forward analysis, spread/slippage modeling, performance reporting
- **Risk Management**: Fixed percentage risk per trade, max open positions, daily limits
- **Live Trading**: MetaTrader 5 integration, Telegram notifications, session-based hours

## Project Structure

```
pipst4eet/
├── backtest/
│   ├── engine.py          # Core backtesting engine
│   └── walkforward.py     # Walk-forward analysis
├── data/
│   ├── fetcher.py         # Twelve Data API client
│   └── mock_data.py       # Synthetic OHLCV generator
├── engine/
│   └── regime.py          # Market regime detection
├── execution/
│   ├── live_bot.py        # Live trading loop
│   └── mt5_executor.py    # MetaTrader 5 order execution
├── risk/
│   └── manager.py         # Position sizing and risk controls
├── strategies/
│   ├── base_strategy.py   # Abstract base class + NullStrategy
│   ├── mean_reversion.py  # RSI + Bollinger Bands strategy
│   └── strategy_orchestrator.py  # Strategy wrapper
├── utils/
│   ├── config.py          # YAML config loading
│   ├── logger.py          # Logging setup
│   └── notifications.py   # Telegram alerts
├── tests/                  # Unit tests
├── constants.py            # Shared constants
├── main.py                 # CLI entry point
├── config.yaml             # Main configuration
├── requirements.txt        # Dependencies
├── .env.example            # Environment variables template
└── .gitignore
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/pipst4eet.git
cd pipst4eet
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Copy .env.example to .env and edit with your API keys
copy .env.example .env
```

## Configuration (config.yaml)

```yaml
trading:
  pairs: [EURUSD, GBPUSD, USDJPY, XAUUSD]
  timeframe: "15m"
  session_start: "09:00"
  session_end: "19:00"

risk:
  risk_per_trade_pct: 1.0    # 1% risk per trade
  max_open_positions: 2

backtest:
  initial_balance: 10000      # $10,000
```

## Usage

### Backtesting

Run a backtest for a specific symbol:
```bash
python main.py --mode backtest --symbol EURUSD --start 2024-01-01 --end 2024-12-31
```

Run with mock data (no API key required):
```bash
python main.py --mode backtest --symbol EURUSD --mock
```

### Strategy Comparison

Compare performance across all pairs:
```bash
python main.py --mode compare
```

### Walk-Forward Analysis

Run walk-forward validation for robustness testing:
```bash
python main.py --mode walkforward --symbol EURUSD
```

### Live Trading

**WARNING: Live trading involves real financial risk. Always test in demo mode first.**

```bash
python main.py --mode live
```

## Backtest Results (Real Twelve Data, 1 Year)

| Pair | Trades | Win Rate | PnL | Return | Max DD | Profit Factor |
|------|--------|----------|-----|--------|--------|---------------|
| **EURUSD** | 11 | 63.6% | +$606 | +6.06% | 3.1% | 2.38 |
| **GBPUSD** | 20 | 40.0% | -$94 | -0.94% | 6.2% | 0.92 |
| **Combined** | 31 | 48.4% | +$512 | +2.56% | 3-6% | ~1.65 |

**Settings**: $10,000 initial balance, 1% risk per trade, 15min timeframe

## Running Tests

```bash
pytest tests/ -v
```

## Security Notes

- **Never commit `.env` to version control** (already in `.gitignore`)
- If you previously committed API keys, **revoke them immediately**
- Use demo mode first before live trading
- Start with small position sizes

## License

MIT License - see LICENSE file.
