import argparse
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from utils.config import load_config
from data.fetcher import DataFetcher
from data.mock_data import generate_mock_ohlcv
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager
from backtest.engine import BacktestEngine
from backtest.walkforward import WalkForwardAnalyzer
from execution.live_bot import LiveBot


def run_backtest_single(
    config: Dict[str, Any],
    symbol: str,
    start_date: str,
    end_date: str,
    use_mock: bool = False
) -> Optional[Dict[str, Any]]:
    low_tf = config["trading"]["timeframe"]

    if use_mock:
        cache_path = f"data/{symbol}_{low_tf}_mock.parquet"
        if os.path.exists(cache_path):
            df = pd.read_parquet(cache_path)
        else:
            df = generate_mock_ohlcv(symbol, low_tf, start_date, end_date, cache_path)
    else:
        fetcher = DataFetcher()
        df = fetcher.fetch_and_cache(symbol, low_tf, start_date, end_date)

    if df.empty:
        return None

    mr = MeanReversionStrategy(config)

    initial_balance = config["backtest"]["initial_balance"]
    risk = RiskManager(config, initial_balance)
    engine = BacktestEngine(config)

    engine.run(df, risk, None, mr)

    return engine.generate_report()


def run_comparison(
    config: Dict[str, Any],
    symbol: str,
    start_date: str,
    end_date: str,
    use_mock: bool = False
) -> Dict[str, Dict[str, Any]]:
    print(f"\n{'='*70}")
    print(f"  BACKTEST: {symbol}")
    print(f"  Period: {start_date} to {end_date}")
    print(f"{'='*70}")

    r = run_backtest_single(config, symbol, start_date, end_date, use_mock)

    if r:
        print(f"\n  {'Strategy':<12} {'Trades':>6} {'Win%':>6} {'PnL':>10} {'DD%':>7} {'PF':>5}")
        print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*5}")
        print(f"  {'Mean Rev':<12} {r['total_trades']:>6} {r['win_rate']:>5.1f}% ${r['total_pnl']:>8,.2f} {r['max_drawdown']:>6.1f}% {r['profit_factor']:>5.2f}")
        print(f"{'='*70}")

    return {"mr": r} if r else {}


def run_all_pairs_comparison(
    config: Dict[str, Any],
    start_date: str,
    end_date: str,
    use_mock: bool = False
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    pairs = config["trading"]["pairs"]
    all_results = {}

    for symbol in pairs:
        results = run_comparison(config, symbol, start_date, end_date, use_mock)
        all_results[symbol] = results

    print("\n" + "="*70)
    print("  AGGREGATE RESULTS")
    print("="*70)
    print(f"\n  {'Pair':<12} {'Trades':>6} {'Win%':>6} {'PnL':>12} {'PF':>5}")
    print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*12} {'-'*5}")

    total_trades = 0
    total_wins = 0
    total_pnl = 0
    avg_pf_sum = 0
    count = 0

    for symbol, r in all_results.items():
        if "mr" in r:
            trades = r["mr"]["total_trades"]
            wins = r["mr"]["winning_trades"]
            pnl = r["mr"]["total_pnl"]
            pf = r["mr"]["profit_factor"]
            wr = r["mr"]["win_rate"]

            total_trades += trades
            total_wins += wins
            total_pnl += pnl
            avg_pf_sum += pf
            count += 1

            print(f"  {symbol:<12} {trades:>6} {wr:>5.1f}% ${pnl:>10,.2f} {pf:>5.2f}")

    if count > 0:
        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_pf = avg_pf_sum / count
        print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*12} {'-'*5}")
        print(f"  {'TOTAL':<12} {total_trades:>6} {overall_wr:>5.1f}% ${total_pnl:>10,.2f} {avg_pf:>5.2f}")

    print(f"{'='*70}\n")

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipst4eet Trading Bot (Mean Reversion Only)")
    parser.add_argument("--mode", choices=["backtest", "live", "walkforward", "compare"], default="backtest")
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

        pairs = [args.symbol] if args.symbol else config["trading"]["pairs"]
        for symbol in pairs:
            r = run_backtest_single(config, symbol, start_date, end_date, use_mock=args.mock)
            if r:
                print(f"\n{symbol}: WR={r['win_rate']}%, PnL=${r['total_pnl']:.2f}, PF={r['profit_factor']}")
    elif args.mode == "live":
        bot = LiveBot(config)
        if bot.connect():
            bot.run()
    elif args.mode == "walkforward":
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
        start_date = args.start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        pairs = [args.symbol] if args.symbol else config["trading"]["pairs"]

        for symbol in pairs:
            print(f"\n{'='*70}")
            print(f"  WALK-FORWARD ANALYSIS: {symbol}")
            print(f"{'='*70}")

            if args.mock:
                cache_path = f"data/{symbol}_{config['trading']['timeframe']}_mock.parquet"
                if os.path.exists(cache_path):
                    df = pd.read_parquet(cache_path)
                else:
                    df = generate_mock_ohlcv(symbol, config["trading"]["timeframe"], start_date, end_date, cache_path)
            else:
                fetcher = DataFetcher()
                df = fetcher.fetch_and_cache(symbol, config["trading"]["timeframe"], start_date, end_date)

            if df is None or df.empty:
                print(f"  No data available for {symbol}")
                continue

            wf = WalkForwardAnalyzer(config)
            wf.run(df)
