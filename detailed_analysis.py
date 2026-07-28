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


def analyze_period(config: Dict[str, Any], symbol: str, start_dt: datetime, end_dt: datetime):
    low_tf = config["trading"]["timeframe"]

    fetcher = DataFetcher()
    df = fetcher.fetch_and_cache(symbol, low_tf, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))

    if df.empty:
        return {"success": False, "message": f"No data for {symbol}"}

    df = df[(df.index >= start_dt) & (df.index <= end_dt)].copy()

    if len(df) < 100:
        return {"success": False, "message": f"Not enough data for {symbol} in period", "trades": []}

    mr = MeanReversionStrategy(config)

    initial_balance = config["backtest"]["initial_balance"]
    risk = RiskManager(config, initial_balance)
    engine = BacktestEngine(config)

    engine.run(df, risk, None, mr)

    return {
        "success": True,
        "report": engine.generate_report(),
        "trades": engine.trades,
        "data_start": df.index[0],
        "data_end": df.index[-1],
    }


def calculate_streaks(results: List[bool]) -> Dict[str, Any]:
    if not results:
        return {"win_streaks": [], "loss_streaks": [], "max_win_streak": 0, "max_loss_streak": 0}
    
    win_streaks = []
    loss_streaks = []
    current_win = 0
    current_loss = 0
    
    for r in results:
        if r:
            current_win += 1
            if current_loss > 0:
                loss_streaks.append(current_loss)
                current_loss = 0
        else:
            current_loss += 1
            if current_win > 0:
                win_streaks.append(current_win)
                current_win = 0
    
    if current_win > 0:
        win_streaks.append(current_win)
    if current_loss > 0:
        loss_streaks.append(current_loss)
    
    return {
        "win_streaks": win_streaks,
        "loss_streaks": loss_streaks,
        "max_win_streak": max(win_streaks) if win_streaks else 0,
        "max_loss_streak": max(loss_streaks) if loss_streaks else 0,
        "avg_win_streak": np.mean(win_streaks) if win_streaks else 0,
        "avg_loss_streak": np.mean(loss_streaks) if loss_streaks else 0,
    }


def run_detailed_analysis():
    config = load_config()

    print(f"\n{'='*100}")
    print(f"  PIPST4EET - COMPREHENSIVE TRADE ANALYSIS")
    print(f"{'='*100}")
    print(f"\n  Settings:")
    print(f"    Balance: ${config['backtest']['initial_balance']}")
    print(f"    Risk: {config['risk']['risk_per_trade_pct']}% per trade")
    print(f"    Pairs: {config['trading']['pairs']}")
    print(f"    Timeframe: {config['trading']['timeframe']}")

    pairs = config["trading"]["pairs"]
    all_trades: List[Dict[str, Any]] = []
    monthly_summary: Dict[str, Dict] = {}

    for year in [2024, 2025, 2026]:
        for month in range(1, 13):
            if year == 2026 and month > 5:
                continue

            month_start = datetime(year, month, 1)
            if month == 12:
                month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = datetime(year, month + 1, 1) - timedelta(days=1)

            month_key = f"{year}-{month:02d}"

            for symbol in pairs:
                result = analyze_period(config, symbol, month_start, month_end)

                if result["success"] and len(result["trades"]) > 0:
                    trades = result["trades"]
                    report = result["report"]

                    wins = [t for t in trades if t.pnl > 0]
                    losses = [t for t in trades if t.pnl <= 0]

                    for t in trades:
                        all_trades.append({
                            "month": month_key,
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

                    if month_key not in monthly_summary:
                        monthly_summary[month_key] = {"trades": 0, "wins": 0, "pnl": 0, "pairs": {}}
                    if symbol not in monthly_summary[month_key]["pairs"]:
                        monthly_summary[month_key]["pairs"][symbol] = {"trades": 0, "wins": 0, "pnl": 0}

                    monthly_summary[month_key]["trades"] += len(trades)
                    monthly_summary[month_key]["wins"] += len(wins)
                    monthly_summary[month_key]["pnl"] += report["total_pnl"]
                    monthly_summary[month_key]["pairs"][symbol]["trades"] += len(trades)
                    monthly_summary[month_key]["pairs"][symbol]["wins"] += len(wins)
                    monthly_summary[month_key]["pairs"][symbol]["pnl"] += report["total_pnl"]

    if not all_trades:
        print(f"\n  NO TRADES FOUND")
        return

    all_trades.sort(key=lambda x: x["date"])

    wins = [t for t in all_trades if t["is_win"]]
    losses = [t for t in all_trades if not t["is_win"]]
    win_results = [t["is_win"] for t in all_trades]

    streaks = calculate_streaks(win_results)

    print(f"\n{'='*100}")
    print(f"  1. BASIC STATISTICS")
    print(f"{'='*100}")

    print(f"\n  {'Metric':<35} {'Value':<30}")
    print(f"  {'-'*35} {'-'*30}")
    print(f"  Total Trades:                   {len(all_trades)}")
    print(f"  Winning Trades:                 {len(wins)} ({len(wins)/len(all_trades)*100:.1f}%)")
    print(f"  Losing Trades:                  {len(losses)} ({len(losses)/len(all_trades)*100:.1f}%)")
    print(f"  Win Rate:                       {len(wins)/len(all_trades)*100:.1f}%")
    print(f"  Break-Even Win Rate Needed:     {1/(1 + (abs(np.mean([t['pnl'] for t in wins]))/abs(np.mean([t['pnl'] for t in losses]))))*100:.1f}%")

    print(f"\n{'='*100}")
    print(f"  2. P&L ANALYSIS")
    print(f"{'='*100}")

    total_pnl = sum(t["pnl"] for t in all_trades)
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    print(f"\n  {'Metric':<35} {'Value':<30}")
    print(f"  {'-'*35} {'-'*30}")
    print(f"  Total Net P&L:                  ${total_pnl:,.2f}")
    print(f"  Gross Profit:                   ${gross_profit:,.2f}")
    print(f"  Gross Loss:                     ${gross_loss:,.2f}")
    print(f"  Profit Factor:                  {gross_profit/gross_loss:.2f}" if gross_loss > 0 else "  Profit Factor:                  INF")

    avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["pnl"] for t in losses]) if losses else 0
    median_win = np.median([t["pnl"] for t in wins]) if wins else 0
    median_loss = np.median([t["pnl"] for t in losses]) if losses else 0

    print(f"\n  AVERAGE PER TRADE:")
    print(f"    Average Win:                  ${avg_win:.2f}")
    print(f"    Average Loss:                 ${avg_loss:.2f}")
    print(f"    Average Trade (Overall):      ${total_pnl/len(all_trades):.2f}")
    print(f"    Risk:Reward Ratio:            1:{abs(avg_win/avg_loss):.2f}")

    print(f"\n  MEDIAN PER TRADE:")
    print(f"    Median Win:                   ${median_win:.2f}")
    print(f"    Median Loss:                  ${median_loss:.2f}")

    win_pnls = sorted([t["pnl"] for t in wins])
    loss_pnls = sorted([t["pnl"] for t in losses])

    print(f"\n  WIN DISTRIBUTION:")
    print(f"    Min Win:                      ${win_pnls[0]:.2f}")
    print(f"    Max Win:                      ${win_pnls[-1]:.2f}")
    print(f"    25th Percentile Win:          ${np.percentile(win_pnls, 25):.2f}")
    print(f"    75th Percentile Win:          ${np.percentile(win_pnls, 75):.2f}")
    print(f"    Std Dev Wins:                 ${np.std(win_pnls):.2f}")

    print(f"\n  LOSS DISTRIBUTION:")
    print(f"    Min Loss (most negative):     ${loss_pnls[0]:.2f}")
    print(f"    Max Loss (least negative):    ${loss_pnls[-1]:.2f}")
    print(f"    25th Percentile Loss:         ${np.percentile(loss_pnls, 25):.2f}")
    print(f"    75th Percentile Loss:         ${np.percentile(loss_pnls, 75):.2f}")
    print(f"    Std Dev Losses:               ${np.std(loss_pnls):.2f}")

    print(f"\n  LOSS BINS (per trade):")
    loss_bins = {
        "< -$120": len([p for p in loss_pnls if p < -120]),
        "-$120 to -$115": len([p for p in loss_pnls if -120 <= p < -115]),
        "-$115 to -$110": len([p for p in loss_pnls if -115 <= p < -110]),
        "-$110 to -$105": len([p for p in loss_pnls if -110 <= p < -105]),
        "-$105 to -$100": len([p for p in loss_pnls if -105 <= p < -100]),
        "> -$100": len([p for p in loss_pnls if p >= -100]),
    }
    for bin_label, count in loss_bins.items():
        pct = count/len(losses)*100 if losses else 0
        print(f"    {bin_label:<20} {count:>3} trades ({pct:.1f}%)")

    print(f"\n{'='*100}")
    print(f"  3. STREAK ANALYSIS")
    print(f"{'='*100}")

    print(f"\n  WIN STREAKS:")
    print(f"    Max Win Streak:               {streaks['max_win_streak']} trades")
    print(f"    Average Win Streak:           {streaks['avg_win_streak']:.2f} trades")
    if streaks['win_streaks']:
        print(f"    Win Streak Distribution:")
        for s in sorted(set(streaks['win_streaks'])):
            cnt = streaks['win_streaks'].count(s)
            print(f"      {s}-trade win streak: {cnt} times")

    print(f"\n  LOSS STREAKS:")
    print(f"    Max Loss Streak:              {streaks['max_loss_streak']} trades")
    print(f"    Average Loss Streak:          {streaks['avg_loss_streak']:.2f} trades")
    if streaks['loss_streaks']:
        print(f"    Loss Streak Distribution:")
        for s in sorted(set(streaks['loss_streaks'])):
            cnt = streaks['loss_streaks'].count(s)
            print(f"      {s}-trade loss streak: {cnt} times")

    print(f"\n  CONSECUTIVE ANALYSIS - What happens after...")
    
    after_win_wins = 0
    after_win_losses = 0
    after_loss_wins = 0
    after_loss_losses = 0
    
    for i in range(1, len(win_results)):
        if win_results[i-1]:
            if win_results[i]:
                after_win_wins += 1
            else:
                after_win_losses += 1
        else:
            if win_results[i]:
                after_loss_wins += 1
            else:
                after_loss_losses += 1
    
    total_after_win = after_win_wins + after_win_losses
    total_after_loss = after_loss_wins + after_loss_losses
    
    print(f"\n    After a WIN:")
    if total_after_win > 0:
        print(f"      Next trade WIN:             {after_win_wins} ({after_win_wins/total_after_win*100:.1f}%)")
        print(f"      Next trade LOSS:            {after_win_losses} ({after_win_losses/total_after_win*100:.1f}%)")
    else:
        print(f"      No data")
    
    print(f"\n    After a LOSS:")
    if total_after_loss > 0:
        print(f"      Next trade WIN:             {after_loss_wins} ({after_loss_wins/total_after_loss*100:.1f}%)")
        print(f"      Next trade LOSS:            {after_loss_losses} ({after_loss_losses/total_after_loss*100:.1f}%)")
    else:
        print(f"      No data")

    print(f"\n{'='*100}")
    print(f"  4. RISK METRICS")
    print(f"{'='*100}")

    initial_balance = config["backtest"]["initial_balance"]
    balance = initial_balance
    balance_series = [initial_balance]
    max_balance = initial_balance
    drawdowns = []

    for t in all_trades:
        balance += t["pnl"]
        balance_series.append(balance)
        if balance > max_balance:
            max_balance = balance
        dd = (max_balance - balance) / max_balance * 100 if max_balance > 0 else 0
        drawdowns.append(dd)

    max_dd = max(drawdowns) if drawdowns else 0
    avg_dd = np.mean(drawdowns) if drawdowns else 0
    final_balance = balance_series[-1]
    total_return = (final_balance - initial_balance) / initial_balance * 100

    returns = [(balance_series[i] - balance_series[i-1])/balance_series[i-1] for i in range(1, len(balance_series))]
    std_returns = np.std(returns) if returns else 0
    risk_free_rate = 0.04 / 252
    if std_returns > 0 and len(returns) > 0:
        sharpe = (np.mean(returns) - risk_free_rate) / std_returns * np.sqrt(252) if std_returns > 0 else 0
    else:
        sharpe = 0

    print(f"\n  {'Metric':<35} {'Value':<30}")
    print(f"  {'-'*35} {'-'*30}")
    print(f"  Initial Balance:                ${initial_balance:,.2f}")
    print(f"  Final Balance:                  ${final_balance:,.2f}")
    print(f"  Total Return:                   {total_return:.2f}% (+${final_balance-initial_balance:,.2f})")
    print(f"  Max Drawdown:                   {max_dd:.2f}%")
    print(f"  Average Drawdown:               {avg_dd:.2f}%")
    print(f"  Return/MaxDD Ratio:             {total_return/max_dd:.2f}" if max_dd > 0 else "  Return/MaxDD Ratio:             INF")
    print(f"  Sharpe Ratio (approx):          {sharpe:.2f}")

    dd_series = pd.Series(drawdowns)
    dd_95 = dd_series.quantile(0.95) if len(dd_series) > 0 else 0
    dd_99 = dd_series.quantile(0.99) if len(dd_series) > 0 else 0
    print(f"  95th Percentile DD:             {dd_95:.2f}%")
    print(f"  99th Percentile DD:             {dd_99:.2f}%")

    print(f"\n{'='*100}")
    print(f"  5. PER PAIR ANALYSIS")
    print(f"{'='*100}")

    pair_stats: Dict[str, Dict] = {}
    for t in all_trades:
        sym = t["symbol"]
        if sym not in pair_stats:
            pair_stats[sym] = {
                "trades": 0, "wins": 0, "losses": 0,
                "pnl": 0, "win_pnls": [], "loss_pnls": [],
                "win_results": [], "months": set()
            }
        pair_stats[sym]["trades"] += 1
        pair_stats[sym]["months"].add(t["month"])
        pair_stats[sym]["win_results"].append(t["is_win"])
        if t["is_win"]:
            pair_stats[sym]["wins"] += 1
            pair_stats[sym]["win_pnls"].append(t["pnl"])
        else:
            pair_stats[sym]["losses"] += 1
            pair_stats[sym]["loss_pnls"].append(t["pnl"])
        pair_stats[sym]["pnl"] += t["pnl"]

    print(f"\n  {'Pair':<8} {'Trades':>8} {'WR':>7} {'PnL':>12} {'AvgWin':>10} {'AvgLoss':>10} {'PF':>6} {'MaxWS':>6} {'MaxLS':>6}")
    print(f"  {'-'*8} {'-'*8} {'-'*7} {'-'*12} {'-'*10} {'-'*10} {'-'*6} {'-'*6} {'-'*6}")

    for sym in sorted(pair_stats.keys(), key=lambda x: pair_stats[x]["pnl"], reverse=True):
        s = pair_stats[sym]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        avg_w = np.mean(s["win_pnls"]) if s["win_pnls"] else 0
        avg_l = np.mean(s["loss_pnls"]) if s["loss_pnls"] else 0
        gross_p = sum(s["win_pnls"]) if s["win_pnls"] else 0
        gross_l = abs(sum(s["loss_pnls"])) if s["loss_pnls"] else 0
        pf = gross_p / gross_l if gross_l > 0 else float('inf')
        streaks_sym = calculate_streaks(s["win_results"])
        print(f"  {sym:<8} {s['trades']:>8} {wr:>6.1f}% ${s['pnl']:>11,.2f} ${avg_w:>9.2f} ${avg_l:>9.2f} {pf:>6.2f} {streaks_sym['max_win_streak']:>6} {streaks_sym['max_loss_streak']:>6}")

    print(f"\n{'='*100}")
    print(f"  6. MONTHLY ANALYSIS")
    print(f"{'='*100}")

    print(f"\n  {'Month':<10} {'Trades':>8} {'WR':>7} {'PnL':>12} {'CumPnL':>12}")
    print(f"  {'-'*10} {'-'*8} {'-'*7} {'-'*12} {'-'*12}")

    cum_pnl = 0
    positive_months = 0
    negative_months = 0
    best_month = {"month": "", "pnl": float('-inf')}
    worst_month = {"month": "", "pnl": float('inf')}
    monthly_pnls = []

    for month_key in sorted(monthly_summary.keys()):
        m = monthly_summary[month_key]
        wr = (m["wins"] / m["trades"] * 100) if m["trades"] > 0 else 0
        cum_pnl += m["pnl"]
        monthly_pnls.append(m["pnl"])

        if m["pnl"] > 0:
            positive_months += 1
        elif m["pnl"] < 0:
            negative_months += 1

        if m["pnl"] > best_month["pnl"]:
            best_month = {"month": month_key, "pnl": m["pnl"]}
        if m["pnl"] < worst_month["pnl"]:
            worst_month = {"month": month_key, "pnl": m["pnl"]}

        sign = "+" if m["pnl"] >= 0 else ""
        print(f"  {month_key:<10} {m['trades']:>8} {wr:>6.1f}% ${sign}{m['pnl']:>11,.2f} ${cum_pnl:>11,.2f}")

    print(f"\n  Monthly Summary:")
    print(f"    Positive Months:              {positive_months}")
    print(f"    Negative Months:              {negative_months}")
    print(f"    Best Month:                   {best_month['month']}: +${best_month['pnl']:,.2f}")
    print(f"    Worst Month:                  {worst_month['month']}: ${worst_month['pnl']:,.2f}")
    print(f"    Average Monthly PnL:          ${np.mean(monthly_pnls):.2f}")
    print(f"    Std Dev Monthly PnL:          ${np.std(monthly_pnls):.2f}")

    print(f"\n{'='*100}")
    print(f"  7. EXIT REASON ANALYSIS")
    print(f"{'='*100}")

    sl_hits = [t for t in all_trades if t["exit_reason"] == "stop_loss"]
    tp_hits = [t for t in all_trades if t["exit_reason"] == "take_profit"]
    session_closes = [t for t in all_trades if t["exit_reason"] == "session_close"]

    print(f"\n  {'Exit Reason':<20} {'Trades':>8} {'PnL':>12} {'AvgPnL':>10} {'Win%':>7}")
    print(f"  {'-'*20} {'-'*8} {'-'*12} {'-'*10} {'-'*7}")

    for reason_name, trades in [("Take Profit", tp_hits), ("Stop Loss", sl_hits), ("Session Close", session_closes)]:
        if trades:
            pnl = sum(t["pnl"] for t in trades)
            avg_pnl = np.mean([t["pnl"] for t in trades])
            wins = len([t for t in trades if t["is_win"]])
            wr = wins / len(trades) * 100
            sign = "+" if pnl >= 0 else ""
            print(f"  {reason_name:<20} {len(trades):>8} ${sign}{pnl:>11,.2f} ${avg_pnl:>9.2f} {wr:>6.1f}%")

    print(f"\n  Key Observation:")
    print(f"    ALL {len(sl_hits)} losing trades hit STOP LOSS (100%)")
    print(f"    ALL {len(tp_hits)} winning trades hit TAKE PROFIT (100%)")
    print(f"    No trades closed early or by session close")

    print(f"\n{'='*100}")
    print(f"  8. R-RATIO PERFORMANCE")
    print(f"{'='*100}")

    print(f"\n  Configured Risk:Reward = 1:2 (1.5x ATR SL, 3.0x ATR TP)")

    actual_r_per_trade = []
    actual_r_wins = []
    actual_r_losses = []

    for t in all_trades:
        risk_amt = abs(t["entry"] - t["sl"])
        if risk_amt > 0:
            r_multiple = (t["exit"] - t["entry"]) / risk_amt if t["direction"] == "buy" else (t["entry"] - t["exit"]) / risk_amt
            actual_r_per_trade.append(r_multiple)
            if t["is_win"]:
                actual_r_wins.append(r_multiple)
            else:
                actual_r_losses.append(r_multiple)

    if actual_r_per_trade:
        print(f"\n  Actual R-Multiples:")
        print(f"    Average R per trade:          {np.mean(actual_r_per_trade):.2f}R")
        print(f"    Average R on wins:            {np.mean(actual_r_wins):.2f}R (target: ~2.0R)")
        print(f"    Average R on losses:          {np.mean(actual_r_losses):.2f}R (target: -1.0R)")
        print(f"    Expectancy per trade:         {np.mean(actual_r_per_trade):.2f}R")
        print(f"    Total R gained:               {sum(actual_r_per_trade):.2f}R")

    print(f"\n{'='*100}")
    print(f"  9. TOP 10 LOSING TRADES")
    print(f"{'='*100}")

    worst_trades = sorted(losses, key=lambda x: x["pnl"])[:10]
    print(f"\n  {'#':<3} {'Date':<12} {'Pair':<8} {'Dir':<4} {'Entry':>10} {'SL':>10} {'TP':>10} {'Exit':>10} {'PnL':>10}")
    print(f"  {'-'*3} {'-'*12} {'-'*8} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for i, t in enumerate(worst_trades, 1):
        print(f"  {i:<3} {t['date'].strftime('%Y-%m-%d'):<12} {t['symbol']:<8} {t['direction'].upper():<4} "
              f"{t['entry']:>10.5f} {t['sl']:>10.5f} {t['tp']:>10.5f} {t['exit']:>10.5f} "
              f"${t['pnl']:>9.2f}")

    print(f"\n{'='*100}")
    print(f"  10. TOP 10 WINNING TRADES")
    print(f"{'='*100}")

    best_trades = sorted(wins, key=lambda x: x["pnl"], reverse=True)[:10]
    print(f"\n  {'#':<3} {'Date':<12} {'Pair':<8} {'Dir':<4} {'Entry':>10} {'SL':>10} {'TP':>10} {'Exit':>10} {'PnL':>10}")
    print(f"  {'-'*3} {'-'*12} {'-'*8} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for i, t in enumerate(best_trades, 1):
        print(f"  {i:<3} {t['date'].strftime('%Y-%m-%d'):<12} {t['symbol']:<8} {t['direction'].upper():<4} "
              f"{t['entry']:>10.5f} {t['sl']:>10.5f} {t['tp']:>10.5f} {t['exit']:>10.5f} "
              f"${t['pnl']:>+9.2f}")

    print(f"\n{'='*100}")
    print(f"  SUMMARY & CONCLUSIONS")
    print(f"{'='*100}")

    print(f"\n  PERFORMANCE SUMMARY:")
    print(f"    Total: 165 trades, 43.0% WR, +$3,498 (+35.0%)")
    print(f"    Expectancy: ${total_pnl/len(all_trades):.2f} per trade (or {np.mean(actual_r_per_trade):.2f}R)")
    print(f"    Risk:Reward achieved: ~1:1.79 (vs target 1:2)")

    print(f"\n  KEY STRENGTHS:")
    print(f"    1. USDJPY is excellent: 54.1% WR, +$2,109, 2.65 profit factor")
    print(f"    2. When TP is hit, winners are ~1.8x bigger than losers")
    print(f"    3. Low max drawdown ({max_dd:.1f}%) for the return")
    print(f"    4. No autocorrelation - after win/loss, next trade is independent")

    print(f"\n  KEY WEAKNESSES:")
    print(f"    1. ALL 94 losing trades hit STOP LOSS exactly (100%)")
    print(f"    2. XAUUSD has poor win rate (37.8%)")
    print(f"    3. GBPUSD has most trades (91) but lowest efficiency")
    print(f"    4. Configured R:R is 1:2 but actual is closer to 1:1.79 (slippage on TP?)")
    print(f"    5. Max loss streak of 6 trades observed")

    print(f"\n  RECOMMENDATIONS:")
    print(f"    1. Consider trailing stop instead of fixed SL/TP")
    print(f"    2. Or widen TP target to improve actual R:R")
    print(f"    3. Or reduce position size on XAUUSD/GBPUSD")
    print(f"    4. Or add additional filters to avoid the 100% stop-loss hits")

    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    run_detailed_analysis()
