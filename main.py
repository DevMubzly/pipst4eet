import argparse
import os
import pandas as pd
from datetime import datetime, timedelta

from utils.config import load_config
from utils.logger import setup_logger
from utils.notifications import alert_backtest_report
from data.fetcher import DataFetcher
from data.mock_data import generate_mock_ohlcv
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.smc_sweep import SMCSweepStrategy
from risk.manager import RiskManager
from backtest.engine import BacktestEngine
from backtest.walkforward import WalkForwardAnalyzer
from execution.live_bot import LiveBot

logger = setup_logger("bot")

def run_backtest_single(config, symbol, start_date, end_date, use_mock=False, strategy_mode="all"):
    low_tf = config["trading"]["timeframe"]

    if use_mock:
        cache_path = f"data/{symbol}_{low_tf}_mock.parquet"
        if os.path.exists(cache_path):
            df = pd.read_parquet(cache_path)
            data_source = "Mock Data (Cached)"
        else:
            df = generate_mock_ohlcv(symbol, low_tf, start_date, end_date, cache_path)
            data_source = "Mock Data (Generated)"
    else:
        fetcher = DataFetcher()
        df = fetcher.fetch_and_cache(symbol, low_tf, start_date, end_date)
        data_source = "Twelve Data API"

    if df.empty:
        return None

    trend = TrendFollowingStrategy(config)
    mr = MeanReversionStrategy(config)
    smc = SMCSweepStrategy(config)

    initial_balance = config["backtest"]["initial_balance"]
    risk = RiskManager(config, initial_balance)
    engine = BacktestEngine(config)

    if strategy_mode == "smc":
        engine.run(df, risk, None, trend, mr, smc)
        engine.trades = [t for t in engine.trades if t.reason.startswith("smc")]
    elif strategy_mode == "ema":
        dummy_smc = type("X", (), {"compute_indicators": lambda s, df: df, "generate_signal": lambda s, df, i, o, h=None: None})()
        dummy_mr = type("X", (), {"compute_indicators": lambda s, df: df, "generate_signal": lambda s, df, i, o, h=None: None})()
        engine.run(df, risk, None, trend, dummy_mr, dummy_smc)
    elif strategy_mode == "mr":
        dummy_smc = type("X", (), {"compute_indicators": lambda s, df: df, "generate_signal": lambda s, df, i, o, h=None: None})()
        dummy_trend = type("X", (), {"compute_indicators": lambda s, df: df, "generate_signal": lambda s, df, i, o, h=None: None})()
        engine.run(df, risk, None, dummy_trend, mr, dummy_smc)
    else:
        engine.run(df, risk, None, trend, mr, smc)

    return engine.generate_report()

def run_comparison(config, symbol, start_date, end_date, use_mock=False):
    print(f"\n{'='*70}")
    print(f"  STRATEGY COMPARISON: {symbol}")
    print(f"  Period: {start_date} to {end_date}")
    print(f"{'='*70}")

    results = {}
    for mode in ["smc", "ema", "mr", "all"]:
        r = run_backtest_single(config, symbol, start_date, end_date, use_mock, mode)
        if r:
            results[mode] = r

    print(f"\n  {'Strategy':<12} {'Trades':>6} {'Win%':>6} {'PnL':>10} {'DD%':>7} {'PF':>5}")
    print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*5}")
    for mode in ["smc", "ema", "mr", "all"]:
        if mode in results:
            r = results[mode]
            print(f"  {mode.upper():<12} {r['total_trades']:>6} {r['win_rate']:>5.1f}% ${r['total_pnl']:>8,.2f} {r['max_drawdown']:>6.1f}% {r['profit_factor']:>5.2f}")
    print(f"{'='*70}")

    return results

def run_all_pairs_comparison(config, start_date, end_date, use_mock=False):
    pairs = config["trading"]["pairs"]
    all_results = {}

    for symbol in pairs:
        results = run_comparison(config, symbol, start_date, end_date, use_mock)
        all_results[symbol] = results

    print(f"\n{'='*70}")
    print(f"  AGGREGATE COMPARISON")
    print(f"{'='*70}")
    print(f"\n  {'Strategy':<12} {'Trades':>6} {'Win%':>6} {'PnL':>12} {'PF':>5}")
    print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*12} {'-'*5}")

    for mode in ["smc", "ema", "mr", "all"]:
        total_trades = sum(r[mode]["total_trades"] for s, r in all_results.items() if mode in r)
        total_wins = sum(r[mode]["winning_trades"] for s, r in all_results.items() if mode in r)
        total_pnl = sum(r[mode]["total_pnl"] for s, r in all_results.items() if mode in r)
        wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_pf = sum(r[mode]["profit_factor"] for s, r in all_results.items() if mode in r)
        avg_pf = avg_pf / len([s for s in all_results if mode in all_results[s]]) if all_results else 0

        print(f"  {mode.upper():<12} {total_trades:>6} {wr:>5.1f}% ${total_pnl:>10,.2f} {avg_pf:>5.2f}")
    print(f"{'='*70}\n")

    return all_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipst4eet Trading Bot")
    parser.add_argument("--mode", choices=["backtest", "live", "walkforward", "compare"], default="backtest")
    parser.add_argument("--strategy", choices=["smc", "ema", "mr", "all"], default=None, help="Strategy to test")
    parser.add_argument("--symbol", default=None, help="Single pair to test")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    config = load_config()

    if args.mode == "compare":
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if args.symbol:
            run_comparison(config, args.symbol, start_date, end_date, use_mock=args.mock)
        else:
            run_all_pairs_comparison(config, start_date, end_date, use_mock=args.mock)
    elif args.mode == "backtest":
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        strat = args.strategy or config["backtest"].get("mode", "all")

        pairs = [args.symbol] if args.symbol else config["trading"]["pairs"]
        for symbol in pairs:
            r = run_backtest_single(config, symbol, start_date, end_date, use_mock=args.mock, strategy_mode=strat)
            if r:
                print(f"\n{symbol}: WR={r['win_rate']}%, PnL=${r['total_pnl']:.2f}, PF={r['profit_factor']}")
    elif args.mode == "live":
        bot = LiveBot(config)
        if bot.connect():
            bot.run()
