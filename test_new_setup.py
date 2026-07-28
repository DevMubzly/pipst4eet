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


def run_analysis():
    config = load_config()

    print(f"\n{'='*80}")
    print(f"  PIPST4EET - NEW STRATEGY TEST (1:4 R:R + Trailing Stop)")
    print(f"{'='*80}")
    
    mr_config = config.get("strategy", {}).get("mean_reversion", {})
    risk_config = config.get("risk", {})
    
    print(f"\n  CONFIG:")
    print(f"    Pairs: {config['trading']['pairs']}")
    print(f"    R:R: 1:{mr_config.get('atr_multiplier_tp', 3.0)/mr_config.get('atr_multiplier_sl', 1.5):.1f}")
    print(f"    SL: {mr_config.get('atr_multiplier_sl', 1.5)}x ATR")
    print(f"    TP: {mr_config.get('atr_multiplier_tp', 3.0)}x ATR")
    print(f"    Trailing: {'Enabled' if mr_config.get('enable_trailing_stop', True) else 'Disabled'}")
    if mr_config.get('enable_trailing_stop', True):
        print(f"      - Start at: {mr_config.get('trailing_start_r', 1.0)}R")
        print(f"      - Step: {mr_config.get('trailing_step_r', 0.5)}R")
        print(f"      - Breakeven at: {mr_config.get('breakeven_at_r', 1.5)}R")
    print(f"    Skip after {risk_config.get('max_consecutive_losses', 2)} losses: {risk_config.get('skip_after_consecutive_losses', True)}")

    pairs = config["trading"]["pairs"]
    all_trades: List[Dict[str, Any]] = []

    for year in [2024, 2025, 2026]:
        for month in range(1, 13):
            if year == 2026 and month > 5:
                continue

            month_start = datetime(year, month, 1)
            if month == 12:
                month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(year, month + 1, 1) - timedelta(days=1)

            for symbol in pairs:
                low_tf = config["trading"]["timeframe"]
                fetcher = DataFetcher()
                df = fetcher.fetch_and_cache(symbol, low_tf, month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d"))

                if df.empty or len(df) < 100:
                    continue

                df = df[(df.index >= month_start) & (df.index <= month_end)].copy()
                if len(df) < 100:
                    continue

                mr = MeanReversionStrategy(config)
                initial_balance = config["backtest"]["initial_balance"]
                risk = RiskManager(config, initial_balance)
                engine = BacktestEngine(config)

                engine.run(df, risk, None, mr)

                for t in engine.trades:
                    if not t.is_open:
                        all_trades.append({
                            "month": f"{year}-{month:02d}",
                            "symbol": symbol,
                            "date": t.entry_time,
                            "direction": t.direction,
                            "entry": t.entry_price,
                            "sl": t.sl,
                            "tp": t.tp,
                            "exit": t.exit_price,
                            "pnl": t.pnl,
                            "exit_reason": t.exit_reason,
                            "is_win": t.pnl > 0,
                        })

    if not all_trades:
        print(f"\n  NO TRADES FOUND")
        return

    all_trades.sort(key=lambda x: x["date"])
    wins = [t for t in all_trades if t["is_win"]]
    losses = [t for t in all_trades if not t["is_win"]]

    print(f"\n{'='*80}")
    print(f"  RESULTS")
    print(f"{'='*80}")

    print(f"\n  {'Metric':<30} {'Value':<30}")
    print(f"  {'-'*30} {'-'*30}")
    print(f"  Total Trades:                  {len(all_trades)}")
    print(f"  Winning Trades:                {len(wins)} ({len(wins)/len(all_trades)*100:.1f}%)")
    print(f"  Losing Trades:                 {len(losses)} ({len(losses)/len(all_trades)*100:.1f}%)")
    print(f"  Total P&L:                     ${sum(t['pnl'] for t in all_trades):,.2f}")

    if wins:
        avg_win = np.mean([t["pnl"] for t in wins])
        print(f"  Average Win:                   ${avg_win:.2f}")
    if losses:
        avg_loss = np.mean([t["pnl"] for t in losses])
        print(f"  Average Loss:                  ${avg_loss:.2f}")
        if avg_loss != 0 and wins:
            print(f"  Actual R:R achieved:           1:{abs(avg_win/avg_loss):.2f}")

    max_consec = 0
    current_consec = 0
    for t in all_trades:
        if t["pnl"] <= 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0
    print(f"  Max Consecutive Losses:        {max_consec}")

    print(f"\n{'='*80}")
    print(f"  EXIT REASONS")
    print(f"{'='*80}")

    from collections import Counter
    exit_reasons = Counter([t["exit_reason"] for t in all_trades])
    print(f"\n  {'Reason':<20} {'Count':>8} {'PnL':>12} {'Win%':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*12} {'-'*8}")

    for reason in ["take_profit", "trailing_stop", "breakeven", "stop_loss", "session_close"]:
        if reason in exit_reasons:
            trades_with_reason = [t for t in all_trades if t["exit_reason"] == reason]
            pnl = sum(t["pnl"] for t in trades_with_reason)
            wr = len([t for t in trades_with_reason if t["is_win"]]) / len(trades_with_reason) * 100
            sign = "+" if pnl >= 0 else ""
            print(f"  {reason:<20} {exit_reasons[reason]:>8} ${sign}{pnl:>11,.2f} {wr:>7.1f}%")

    print(f"\n{'='*80}")
    print(f"  R-MULTIPLE ANALYSIS")
    print(f"{'='*80}")

    actual_r_per_trade = []
    actual_r_wins = []
    actual_r_losses = []

    for t in all_trades:
        risk_amt = abs(t["entry"] - t["sl"]) if t["sl"] and t["entry"] != t["sl"] else 0
        if risk_amt > 0:
            r_multiple = (t["exit"] - t["entry"]) / risk_amt if t["direction"] == "buy" else (t["entry"] - t["exit"]) / risk_amt
            actual_r_per_trade.append(r_multiple)
            if t["is_win"]:
                actual_r_wins.append(r_multiple)
            else:
                actual_r_losses.append(r_multiple)

    if actual_r_wins:
        print(f"\n  Win R-multiples:")
        print(f"    Average:                     {np.mean(actual_r_wins):.2f}R")
        print(f"    Median:                      {np.median(actual_r_wins):.2f}R")
        print(f"    Min:                         {min(actual_r_wins):.2f}R")
        print(f"    Max:                         {max(actual_r_wins):.2f}R")
        if len(actual_r_wins) >= 4:
            print(f"    25th percentile:             {np.percentile(actual_r_wins, 25):.2f}R")
            print(f"    75th percentile:             {np.percentile(actual_r_wins, 75):.2f}R")

    if actual_r_losses:
        print(f"\n  Loss R-multiples:")
        print(f"    Average:                     {np.mean(actual_r_losses):.2f}R")
        print(f"    Median:                      {np.median(actual_r_losses):.2f}R")

    if actual_r_per_trade:
        print(f"\n  Overall:")
        print(f"    Expectancy per trade:        {np.mean(actual_r_per_trade):.2f}R")
        print(f"    Total R:                     {sum(actual_r_per_trade):.2f}R")

    print(f"\n{'='*80}")
    print(f"  ALL TRADES")
    print(f"{'='*80}")

    print(f"\n  {'#':<4} {'Date':<12} {'Dir':<4} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'R':>8} {'Reason':<15} {'Result':<6}")
    print(f"  {'-'*4} {'-'*12} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*15} {'-'*6}")

    for i, t in enumerate(all_trades, 1):
        risk_amt = abs(t["entry"] - t["sl"]) if t["sl"] and t["entry"] != t["sl"] else 0
        r_mult = (t["exit"] - t["entry"]) / risk_amt if risk_amt > 0 and t["direction"] == "buy" else (t["entry"] - t["exit"]) / risk_amt if risk_amt > 0 else 0
        result = "WIN" if t["is_win"] else "LOSS"
        pnl_sign = "+" if t["is_win"] else ""
        print(f"  {i:<4} {t['date'].strftime('%Y-%m-%d'):<12} {t['direction'].upper():<4} "
              f"{t['entry']:>10.5f} {t['exit']:>10.5f} "
              f"${pnl_sign}{t['pnl']:>8.2f} {r_mult:>7.2f}R "
              f"{t['exit_reason']:<15} {result:<6}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    run_analysis()
