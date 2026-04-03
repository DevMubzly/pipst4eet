import argparse
import os
import pandas as pd
from datetime import datetime, timedelta

from utils.config import load_config
from utils.logger import setup_logger
from data.fetcher import DataFetcher
from data.mock_data import generate_mock_ohlcv
from engine.regime import RegimeDetector
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager
from backtest.engine import BacktestEngine
from backtest.walkforward import WalkForwardAnalyzer

logger = setup_logger("bot")

def print_report(symbol, report, df, config, data_source):
    print("")
    print("=" * 70)
    print(f"  BACKTEST REPORT: {symbol}")
    print("=" * 70)

    print("")
    print("  DATA & SETTINGS")
    print(f"  {'Source:':<30} {data_source}")
    print(f"  {'Timeframe:':<30} {config['trading']['timeframe']}")
    print(f"  {'Data Start:':<30} {df.index.min()}")
    print(f"  {'Data End:':<30} {df.index.max()}")
    print(f"  {'Total Candles:':<30} {len(df):,}")
    print(f"  {'Trading Session:':<30} {config['trading']['session_start']} - {config['trading']['session_end']} (UTC+3)")
    print(f"  {'Initial Balance:':<30} ${config['backtest']['initial_balance']:,.2f}")
    print(f"  {'Risk Per Trade:':<30} {config['risk']['risk_per_trade_pct']}%")
    print(f"  {'Daily Loss Limit:':<30} {config['risk']['daily_loss_limit_pct']}%")

    print("")
    print("  PERFORMANCE")
    print(f"  {'Total Trades:':<30} {report['total_trades']}")
    print(f"  {'Winning / Losing:':<30} {report['winning_trades']} / {report['losing_trades']}")
    print(f"  {'Win Rate:':<30} {report['win_rate']}%")
    print(f"  {'Total PnL:':<30} ${report['total_pnl']:,.2f}")
    print(f"  {'Total Pips:':<30} {report['total_pips']}")
    print(f"  {'Return:':<30} {report['return_pct']}%")
    print(f"  {'Final Balance:':<30} ${report['final_balance']:,.2f}")

    print("")
    print("  RISK METRICS")
    print(f"  {'Max Drawdown:':<30} {report['max_drawdown']}% (${report['max_drawdown_usd']:,.2f})")
    print(f"  {'Sharpe Ratio:':<30} {report['sharpe_ratio']}")
    print(f"  {'Sortino Ratio:':<30} {report['sortino_ratio']}")
    print(f"  {'Profit Factor:':<30} {report['profit_factor']}")
    print(f"  {'Recovery Factor:':<30} {report['recovery_factor']}")
    print(f"  {'Consecutive Losses:':<30} {report['consecutive_losses']}")

    print("")
    print("  TRADE DETAILS")
    print(f"  {'Gross Profit:':<30} ${report['gross_profit']:,.2f}")
    print(f"  {'Gross Loss:':<30} ${report['gross_loss']:,.2f}")
    print(f"  {'Avg Win:':<30} ${report['avg_win']:,.2f}")
    print(f"  {'Avg Loss:':<30} ${report['avg_loss']:,.2f}")
    print(f"  {'Largest Win:':<30} ${report['largest_win']:,.2f}")
    print(f"  {'Largest Loss:':<30} ${report['largest_loss']:,.2f}")
    print(f"  {'Avg Holding Time:':<30} {report['avg_holding_time']}")

    print("")
    print("  STRATEGY BREAKDOWN")
    print(f"  {'Trend-Following Trades:':<30} {report['trend_trades']} (Win Rate: {report['trend_win_rate']}%)")
    print(f"  {'Mean-Reversion Trades:':<30} {report['mr_trades']} (Win Rate: {report['mr_win_rate']}%)")

    print("")
    print("  EXIT REASONS")
    print(f"  {'Stop Loss Hits:':<30} {report['sl_hits']}")
    print(f"  {'Take Profit Hits:':<30} {report['tp_hits']}")
    print(f"  {'Session Closes:':<30} {report['session_closes']}")
    print("=" * 70)
    print("")

def run_backtest(config, symbol, start_date, end_date, use_mock=False):
    logger.info(f"Starting backtest: {symbol} | {start_date} to {end_date}")

    if use_mock:
        cache_path = f"data/{symbol}_{config['trading']['timeframe']}_mock.parquet"
        if os.path.exists(cache_path):
            df = pd.read_parquet(cache_path)
            logger.info(f"Loaded cached mock data for {symbol}: {len(df)} candles")
            data_source = "Mock Data (Cached)"
        else:
            df = generate_mock_ohlcv(symbol, config["trading"]["timeframe"], start_date, end_date, cache_path)
            logger.info(f"Generated mock data for {symbol}: {len(df)} candles")
            data_source = "Mock Data (Generated)"
    else:
        fetcher = DataFetcher()
        df = fetcher.fetch_and_cache(symbol, config["trading"]["timeframe"], start_date, end_date)
        data_source = "Twelve Data API"

    if df.empty:
        logger.error(f"No data fetched for {symbol}")
        return

    logger.info(f"Loaded {len(df)} candles for {symbol}")

    regime_detector = RegimeDetector(config)
    trend_strategy = TrendFollowingStrategy(config)
    mr_strategy = MeanReversionStrategy(config)

    initial_balance = config["backtest"]["initial_balance"]
    risk_manager = RiskManager(config, initial_balance)

    engine = BacktestEngine(config)
    report = engine.run(df, risk_manager, regime_detector, trend_strategy, mr_strategy)

    print_report(symbol, report, df, config, data_source)

    trades_data = [t.to_dict() for t in engine.trades]
    if trades_data:
        trades_df = pd.DataFrame(trades_data)
        output_path = f"logs/{symbol}_trades.csv"
        trades_df.to_csv(output_path, index=False)
        logger.info(f"Trade log saved to {output_path}")

    return report

def run_all_pairs(config, start_date, end_date, use_mock=False):
    pairs = config["trading"]["pairs"]
    all_reports = {}

    for symbol in pairs:
        report = run_backtest(config, symbol, start_date, end_date, use_mock)
        if report:
            all_reports[symbol] = report

    print("")
    print("=" * 70)
    print("  AGGREGATE RESULTS (All Pairs)")
    print("=" * 70)

    total_trades = sum(r["total_trades"] for r in all_reports.values())
    total_pnl = sum(r["total_pnl"] for r in all_reports.values())
    total_wins = sum(r["winning_trades"] for r in all_reports.values())
    avg_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    max_dd = max(r["max_drawdown"] for r in all_reports.values()) if all_reports else 0
    best_pair = max(all_reports, key=lambda x: all_reports[x]["total_pnl"]) if all_reports else "N/A"
    worst_pair = min(all_reports, key=lambda x: all_reports[x]["total_pnl"]) if all_reports else "N/A"

    print(f"  {'Total Trades:':<30} {total_trades}")
    print(f"  {'Total PnL:':<30} ${total_pnl:,.2f}")
    print(f"  {'Overall Win Rate:':<30} {avg_win_rate:.1f}%")
    print(f"  {'Worst Max DD:':<30} {max_dd}%")
    print(f"  {'Best Pair:':<30} {best_pair} (${all_reports[best_pair]['total_pnl']:,.2f})")
    print(f"  {'Worst Pair:':<30} {worst_pair} (${all_reports[worst_pair]['total_pnl']:,.2f})")

    print("")
    print("  Per-Pair Summary:")
    print(f"  {'Pair':<10} {'Trades':>7} {'Win%':>7} {'PnL':>12} {'DD%':>7} {'PF':>5}")
    print(f"  {'-'*10} {'-'*7} {'-'*7} {'-'*12} {'-'*7} {'-'*5}")
    for sym, r in all_reports.items():
        print(f"  {sym:<10} {r['total_trades']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10,.2f} {r['max_drawdown']:>6.1f}% {r['profit_factor']:>5.2f}")
    print("=" * 70)
    print("")

    return all_reports

def run_walkforward(config, symbol, start_date, end_date, use_mock=False):
    logger.info(f"Starting walk-forward: {symbol} | {start_date} to {end_date}")

    if use_mock:
        cache_path = f"data/{symbol}_{config['trading']['timeframe']}_mock.parquet"
        if os.path.exists(cache_path):
            df = pd.read_parquet(cache_path)
        else:
            df = generate_mock_ohlcv(symbol, config["trading"]["timeframe"], start_date, end_date, cache_path)
    else:
        fetcher = DataFetcher()
        df = fetcher.fetch_and_cache(symbol, config["trading"]["timeframe"], start_date, end_date)

    if df.empty:
        logger.error(f"No data for {symbol}")
        return

    analyzer = WalkForwardAnalyzer(config)
    results = analyzer.run(df)
    return results

def run_walkforward_all(config, start_date, end_date, use_mock=False):
    pairs = config["trading"]["pairs"]
    all_results = {}

    for symbol in pairs:
        results = run_walkforward(config, symbol, start_date, end_date, use_mock)
        if results:
            all_results[symbol] = results

    return all_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipst4eet Trading Bot")
    parser.add_argument("--mode", choices=["backtest", "live", "walkforward"], default="backtest")
    parser.add_argument("--symbol", default=None, help="Single pair to test (e.g. XAUUSD)")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--mock", action="store_true", help="Use mock data instead of Twelve Data API")
    args = parser.parse_args()

    config = load_config()

    if args.mode == "backtest":
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        if args.symbol:
            run_backtest(config, args.symbol, start_date, end_date, use_mock=args.mock)
        else:
            run_all_pairs(config, start_date, end_date, use_mock=args.mock)
    elif args.mode == "walkforward":
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start or (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        if args.symbol:
            run_walkforward(config, args.symbol, start_date, end_date, use_mock=args.mock)
        else:
            run_walkforward_all(config, start_date, end_date, use_mock=args.mock)
    elif args.mode == "live":
        logger.info("Live mode not yet implemented. Run backtest first.")
