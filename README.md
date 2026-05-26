# pipst4eet

A multi-strategy algorithmic trading bot for Forex with backtesting capabilities.

## Features

- **Multiple Strategies**:
  - Trend Following (EMA Crossover with ATR stops)
  - Mean Reversion (RSI + Bollinger Bands)
  - Smart Money Concepts (SMC) - Liquidity Sweep + Fair Value Gap

- **Market Regime Detection**:
  - ADX, Choppiness Index, and Bollinger Band width voting system
  - Regime-based strategy selection (trend strategies in trending markets, mean reversion in ranging markets)

- **Backtesting Engine**:
  - Walk-forward analysis for out-of-sample validation
  - Spread and slippage modeling
  - Comprehensive performance reporting (Sharpe, Sortino, max drawdown, profit factor, etc.)

- **Risk Management**:
  - Fixed percentage risk per trade
  - Daily loss limits with kill switch
  - Max open positions limit
  - Max daily trades limit

- **Live Trading**:
  - MetaTrader 5 integration
  - Telegram notifications
  - Session-based trading hours
  - Dynamic polling near candle closes

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
│   ├── trend_following.py # EMA crossover strategy
│   ├── mean_reversion.py  # RSI + Bollinger Bands strategy
│   ├── smc_sweep.py       # SMC sweep + FVG strategy
│   └── strategy_orchestrator.py  # Regime-based strategy selection
├── utils/
│   ├── config.py          # YAML config loading
│   ├── logger.py          # Logging setup
│   └── notifications.py   # Telegram alerts
├── tests/                  # Unit tests
├── constants.py            # Shared constants (pip sizes, pair configs)
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
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Edit `config.yaml` to customize:

- **Trading pairs, timeframe, session hours** (`trading:` section)
- **Risk parameters** (`risk:` section)
- **Pair-specific pip values, spreads** (`pair_config:` section)
- **Regime detection thresholds** (`regime:` section)
- **Strategy parameters** (`strategy:` section)
- **Backtest settings** (`backtest:` section)
- **MT5 execution** (`execution:` section)
- **Telegram notifications** (`telegram:` section)

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

Test a specific strategy:
```bash
python main.py --mode backtest --symbol EURUSD --strategy smc
python main.py --mode backtest --symbol EURUSD --strategy ema
python main.py --mode backtest --symbol EURUSD --strategy mr
```

### Strategy Comparison

Compare all strategies across all pairs:
```bash
python main.py --mode compare
```

Compare for a specific symbol:
```bash
python main.py --mode compare --symbol EURUSD
```

### Walk-Forward Analysis

Run walk-forward validation:
```bash
python main.py --mode walkforward --symbol EURUSD
```

### Live Trading

**WARNING: Live trading involves real financial risk. Always test in demo mode first.**

```bash
python main.py --mode live
```

## Running Tests

```bash
pytest tests/ -v
```

## Improvements Made (v2)

1. **Fixed critical bugs**:
   - Removed duplicate `run()` method in `live_bot.py`
   - Implemented `walkforward` mode in `main.py`

2. **Eliminated code duplication**:
   - Created `constants.py` for shared pip sizes and pair configs
   - Created `BaseStrategy` ABC with shared indicator calculations (ATR)
   - Created `NullStrategy` to replace `type()` duck typing hacks
   - Created `StrategyOrchestrator` to extract shared strategy selection logic from both `backtest/engine.py` and `execution/live_bot.py`

3. **Performance optimizations**:
   - Vectorized regime detection in `engine/regime.py` (replaced row-by-row loop with numpy operations)
   - Vectorized swing detection in `strategies/smc_sweep.py` using `rolling().max()/min()`

4. **Type hints added throughout**:
   - All source files now have proper type annotations
   - Better IDE support and static analysis

5. **Cleaned up dependencies**:
   - Removed unused packages (`ta`, `matplotlib`, `seaborn`)
   - Pinned all dependency versions for reproducible builds
   - Added missing `requests` dependency

6. **Unit tests added**:
   - Tests for constants, risk manager, and strategies
   - `tests/test_constants.py`
   - `tests/test_risk_manager.py`
   - `tests/test_strategies.py`

7. **Fixed env var loading**:
   - Lazy loading of Telegram tokens in `notifications.py` (no longer loads at import time)
   - Consistent naming in `.env.example`

## Security Notes

- **Never commit `.env` to version control** (already in `.gitignore`)
- If you previously committed API keys, **revoke them immediately**
- Use demo mode first before live trading
- Start with small position sizes

## License

MIT License - see LICENSE file.
