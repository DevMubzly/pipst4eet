# pipst4eet

A Mean Reversion algorithmic trading bot for Forex and Metals with backtesting capabilities.

## Strategy

**Mean Reversion (RSI + Bollinger Bands)**

The bot trades based on:
- **RSI (14)**: Oversold (<30) / Overbought (>70) with momentum confirmation
- **Bollinger Bands (20, 2.0)**: 15th percentile extreme thresholds
- **Stops**: 1.5× ATR (SL) / 3.0× ATR (TP)
- **Momentum Confirmation**: RSI must move >3 points to filter weak signals

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
│   └── fetcher.py         # Twelve Data API client
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
git clone https://github.com/DevMubzly/pipst4eet.git
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
  pairs: [GBPUSD, USDJPY, XAUUSD]
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
python main.py --mode backtest --symbol GBPUSD --start 2024-01-01 --end 2024-12-31
```

### Strategy Comparison

Compare performance across all pairs:
```bash
python main.py --mode compare
```

### Walk-Forward Analysis

Run walk-forward validation for robustness testing:
```bash
python main.py --mode walkforward --symbol GBPUSD
```

### Live Trading

**WARNING: Live trading involves real financial risk. Always test in demo mode first.**

```bash
python main.py --mode live
```

## Backtest Results (Real Twelve Data, 1 Year: 2025-05-26 to 2026-05-26)

| Pair | Trades | Win Rate | PnL | Return | Max DD | Profit Factor |
|------|--------|----------|-----|--------|--------|---------------|
| **USDJPY** | 35 | 57.1% | +$2,418 | +24.2% | 4.0% | **2.42** |
| **GBPUSD** | 50 | 46.0% | +$1,403 | +14.0% | 6.1% | 1.45 |
| **XAUUSD** | 36 | 38.9% | +$611 | +6.1% | 6.6% | 1.27 |
| **TOTAL** | 121 | 47.1% | **+$4,432** | **+44.3%** | 4.0-6.6% | **1.71** |

**Settings**: $10,000 initial balance, 1% risk per trade, 15min timeframe

**Tuned Parameters**:
- RSI: 30 (oversold) / 70 (overbought)
- BB Extreme Threshold: 0.15
- ATR Multipliers: 1.5× (SL) / 3.0× (TP)
- Momentum Confirmation: ON (RSI > 3 point change)
- Candle Body Confirmation: OFF

**Pairs Removed**: EURUSD (consistently lost with these parameters)

## Security Notes

- **Never commit `.env` to version control** (already in `.gitignore`)
- If you previously committed API keys, **revoke them immediately**
- Use demo mode first before live trading
- Start with small position sizes

## License

MIT License - see LICENSE file.
