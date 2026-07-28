import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

from utils.config import load_config
from data.fetcher import DataFetcher
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager
from backtest.engine import BacktestEngine, Trade


def run_full_test():
    config = load_config()

    print(f"\n{'='*80}")
    print(f"  PIPST4EET - FULL BACKTEST (Continuous)")
    print(f"{'='*80}")
    
    mr_config = config.get("strategy", {}).get("mean_reversion", {})
    risk_config = config.get("risk", {})
    
    print(f"\n  CONFIG:")
    print(f"    Pairs: {config['trading']['pairs']}")
    print(f"    R:R: 1:{mr_config.get('atr_multiplier_tp', 3.0)/mr_config.get('atr_multiplier_sl', 1.5):.1f}")
    print(f"    SL: {mr_config.get('atr_multiplier_sl', 1.5)}x ATR")
    print(f"    TP: {mr_config.get('atr_multiplier_tp', 3.0)}x ATR (or trailing)")
    print(f"    Trailing: {'Enabled' if mr_config.get('enable_trailing_stop', True) else 'Disabled'}")
    if mr_config.get('enable_trailing_stop', True):
        print(f"      - Breakeven at: {mr_config.get('breakeven_at_r', 1.5)}R")
        print(f"      - Trailing starts at: {mr_config.get('trailing_start_r', 2.0)}R")
        print(f"      - Trailing step: {mr_config.get('trailing_step_r', 1.0)}R")
    print(f"    Skip after {risk_config.get('max_consecutive_losses', 2)} losses: {risk_config.get('skip_after_consecutive_losses', True)}")
    if risk_config.get('skip_after_consecutive_losses', True):
        print(f"      - Skip {risk_config.get('skip_trades_count', 3)} trades")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    
    print(f"\n  Period: {start_date} to {end_date}")

    pairs = config["trading"]["pairs"]
    low_tf = config["trading"]["timeframe"]
    fetcher = DataFetcher()
    
    all_dfs = []
    for symbol in pairs:
        print(f"\n  Fetching {symbol}...")
        df = fetcher.fetch_and_cache(symbol, low_tf, start_date, end_date)
        if not df.empty:
            all_dfs.append(df)
            print(f"    {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    if not all_dfs:
        print("  No data!")
        return

    combined_df = pd.concat(all_dfs).sort_index()
    print(f"\n  Total: {len(combined_df)} candles")

    mr = MeanReversionStrategy(config)
    initial_balance = config["backtest"]["initial_balance"]
    risk = RiskManager(config, initial_balance)
    engine = BacktestEngine(config)

    print(f"\n  Running backtest...")
    engine.run(combined_df, risk, None, mr)

    trades = [t for t in engine.trades if not t.is_open]
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    print(f"\n{'='*80}")
    print(f"  RESULTS")
    print(f"{'='*80}")

    print(f"\n  {'Metric':<30} {'Value':<30}")
    print(f"  {'-'*30} {'-'*30}")
    print(f"  Total Trades:                  {len(trades)}")
    print(f"  Winning Trades:                {len(wins)} ({len(wins)/len(trades)*100:.1f}%)")
    print(f"  Losing Trades:                 {len(losses)} ({len(losses)/len(trades)*100:.1f}%)")
    print(f"  Total P&L:                     ${sum(t.pnl for t in trades):,.2f}")

    if wins:
        avg_win = np.mean([t.pnl for t in wins])
        print(f"  Average Win:                   ${avg_win:.2f}")
    if losses:
        avg_loss = np.mean([t.pnl for t in losses])
        print(f"  Average Loss:                  ${avg_loss:.2f}")
        if avg_loss != 0 and wins:
            print(f"  Actual R:R achieved:           1:{abs(avg_win/avg_loss):.2f}")

    max_consec = 0
    current_consec = 0
    for t in trades:
        if t.pnl <= 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0
    print(f"  Max Consecutive Losses:        {max_consec}")

    from collections import Counter
    exit_reasons = Counter([t.exit_reason for t in trades])
    print(f"\n  Exit Reasons:")
    for reason, count in exit_reasons.most_common():
        trades_with_reason = [t for t in trades if t.exit_reason == reason]
        pnl = sum(t.pnl for t in trades_with_reason)
        wr = len([t for t in trades_with_reason if t.pnl > 0]) / len(trades_with_reason) * 100
        sign = "+" if pnl >= 0 else ""
        print(f"    {reason:<20} {count:>4} trades, ${sign}{pnl:>10,.2f}, WR={wr:.1f}%")

    print(f"\n  R-Multiple Analysis:")
    
    actual_r_wins = []
    actual_r_losses = []
    
    for t in trades:
        initial_risk = t.risk_distance if hasattr(t, 'risk_distance') and t.risk_distance > 0 else abs(t.entry_price - t.initial_sl) if hasattr(t, 'initial_sl') else abs(t.entry_price - t.sl)
        if initial_risk > 0:
            r_multiple = (t.exit_price - t.entry_price) / initial_risk if t.direction == "buy" else (t.entry_price - t.exit_price) / initial_risk
            if t.pnl > 0:
                actual_r_wins.append(r_multiple)
            else:
                actual_r_losses.append(r_multiple)

    if actual_r_wins:
        print(f"\n    Win R-multiples:")
        print(f"      Average:                   {np.mean(actual_r_wins):.2f}R")
        print(f"      Median:                    {np.median(actual_r_wins):.2f}R")
        print(f"      Min:                       {min(actual_r_wins):.2f}R")
        print(f"      Max:                       {max(actual_r_wins):.2f}R")
        if len(actual_r_wins) >= 4:
            print(f"      25th percentile:           {np.percentile(actual_r_wins, 25):.2f}R")
            print(f"      75th percentile:           {np.percentile(actual_r_wins, 75):.2f}R")
        
        big_winners = [r for r in actual_r_wins if r >= 3.0]
        print(f"\n    Winners >= 3R:               {len(big_winners)}/{len(actual_r_wins)} ({len(big_winners)/len(actual_r_wins)*100:.1f}%)")
        winners_4r_plus = [r for r in actual_r_wins if r >= 4.0]
        print(f"    Winners >= 4R:               {len(winners_4r_plus)}/{len(actual_r_wins)} ({len(winners_4r_plus)/len(actual_r_wins)*100:.1f}%)")
        winners_5r_plus = [r for r in actual_r_wins if r >= 5.0]
        print(f"    Winners >= 5R:               {len(winners_5r_plus)}/{len(actual_r_wins)} ({len(winners_5r_plus)/len(actual_r_wins)*100:.1f}%)")

    if actual_r_losses:
        print(f"\n    Loss R-multiples:")
        print(f"      Average:                   {np.mean(actual_r_losses):.2f}R")
        print(f"      Median:                    {np.median(actual_r_losses):.2f}R")

    if actual_r_wins and actual_r_losses:
        expectancy = (len(wins)/len(trades) * np.mean(actual_r_wins)) + (len(losses)/len(trades) * np.mean(actual_r_losses))
        print(f"\n    Expectancy per trade:        {expectancy:.2f}R")

    print(f"\n  All Trades:")
    print(f"\n  {'#':<4} {'Date':<12} {'Dir':<4} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'R':>8} {'Reason':<15}")
    print(f"  {'-'*4} {'-'*12} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*15}")

    for i, t in enumerate(trades, 1):
        initial_risk = t.risk_distance if hasattr(t, 'risk_distance') and t.risk_distance > 0 else abs(t.entry_price - t.initial_sl) if hasattr(t, 'initial_sl') else abs(t.entry_price - t.sl)
        r_mult = (t.exit_price - t.entry_price) / initial_risk if initial_risk > 0 and t.direction == "buy" else (t.entry_price - t.exit_price) / initial_risk if initial_risk > 0 else 0
        pnl_sign = "+" if t.pnl > 0 else ""
        print(f"  {i:<4} {t.entry_time.strftime('%Y-%m-%d'):<12} {t.direction.upper():<4} "
              f"{t.entry_price:>10.5f} {t.exit_price:>10.5f} "
              f"${pnl_sign}{t.pnl:>8.2f} {r_mult:>7.2f}R "
              f"{t.exit_reason:<15}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    run_full_test()
