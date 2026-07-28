import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

from utils.config import load_config
from data.fetcher import DataFetcher
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager
from backtest.engine import BacktestEngine


def run_breakout_test():
    config = load_config()

    print(f"\n{'='*80}")
    print(f"  PIPST4EET - BREAKOUT STRATEGY TEST")
    print(f"{'='*80}")
    
    bo_config = config.get("strategy", {}).get("breakout", {})
    
    print(f"\n  CONFIG:")
    print(f"    Pairs: {config['trading']['pairs']}")
    print(f"    Timeframe: {config['trading']['timeframe']}")
    print(f"    Lookback: {bo_config.get('lookback_period', 20)} bars")
    print(f"    R:R: 1:{bo_config.get('atr_multiplier_tp', 1.5)/bo_config.get('atr_multiplier_sl', 1.0):.1f}")
    print(f"    Trend Confirmation: {bo_config.get('require_trend_confirmation', True)}")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    
    print(f"\n  Period: {start_date} to {end_date}")

    pairs = config["trading"]["pairs"]
    low_tf = config["trading"]["timeframe"]
    fetcher = DataFetcher()
    
    all_trades = []
    initial_balance = config["backtest"]["initial_balance"]
    
    for symbol in pairs:
        print(f"\n  Fetching {symbol}...")
        df = fetcher.fetch_and_cache(symbol, low_tf, start_date, end_date)
        if df.empty:
            print(f"    No data for {symbol}")
            continue
            
        print(f"    {len(df)} candles from {df.index[0]} to {df.index[-1]}")

        from strategies.breakout import BreakoutStrategy
        strategy = BreakoutStrategy(config)
        risk = RiskManager(config, initial_balance)
        engine = BacktestEngine(config)

        print(f"  Running backtest for {symbol}...")
        
        df = strategy.compute_indicators(df)
        
        session_start = config["trading"]["session_start"]
        session_end = config["trading"]["session_end"]
        
        for i in range(len(df)):
            row = df.iloc[i]
            current_time = row.name
            
            if not isinstance(current_time, pd.Timestamp):
                current_time = pd.Timestamp(current_time)
            
            time_str = current_time.strftime("%H:%M")
            in_session = session_start <= time_str <= session_end
            
            for trade in list(engine.open_trades):
                if trade.is_open:
                    trade.check_exit(row["high"], row["low"], row["close"], current_time)
                    if not trade.is_open:
                        risk.record_trade_result(trade.pnl)
                        risk.close_position()
                        engine.trades.append(trade)
                        engine.balance = risk.balance
            
            if not in_session:
                continue
            
            has_open = any(t.is_open for t in engine.open_trades)
            if not has_open and risk.can_open_trade():
                signal = strategy.generate_signal(df, i, False, None)
                
                if signal:
                    lot_size = risk.calculate_position_size(
                        symbol,
                        row["close"],
                        signal["sl"]
                    )
                    
                    if lot_size > 0:
                        spread = config["backtest"].get("spread_pips", 0.5)
                        slippage = config["backtest"].get("slippage_pips", 0.3)
                        
                        pair_config_dict = config.get("pair_config", {})
                        from backtest.engine import Trade
                        trade = Trade(
                            symbol=symbol,
                            direction=signal["direction"],
                            entry_price=row["close"],
                            entry_time=current_time,
                            sl=signal["sl"],
                            tp=signal["tp"],
                            lot_size=lot_size,
                            reason=signal["reason"],
                            spread_pips=spread,
                            slippage_pips=slippage,
                            pair_config=pair_config_dict.get(symbol, {}),
                            enable_trailing=False,
                        )
                        engine.open_trades.append(trade)
                        risk.open_position()

        for trade in list(engine.open_trades):
            if trade.is_open:
                trade._close(df.iloc[-1]["close"], df.index[-1], "session_close")
                risk.record_trade_result(trade.pnl)
                risk.close_position()
                engine.trades.append(trade)

        trades = [t for t in engine.trades if not t.is_open]
        all_trades.extend(trades)
        
        if trades:
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]
            pnl = sum(t.pnl for t in trades)
            wr = len(wins)/len(trades)*100 if trades else 0
            print(f"    {len(trades)} trades, {wr:.1f}% WR, P&L: ${pnl:,.2f}")

    if not all_trades:
        print("\n  No trades!")
        return

    all_trades.sort(key=lambda t: t.entry_time)
    wins = [t for t in all_trades if t.pnl > 0]
    losses = [t for t in all_trades if t.pnl <= 0]

    print(f"\n{'='*80}")
    print(f"  FINAL RESULTS - BREAKOUT STRATEGY")
    print(f"{'='*80}")

    print(f"\n  {'Metric':<30} {'Value':<30}")
    print(f"  {'-'*30} {'-'*30}")
    print(f"  Total Trades:                  {len(all_trades)}")
    print(f"  Winning Trades:                {len(wins)} ({len(wins)/len(all_trades)*100:.1f}%)")
    print(f"  Losing Trades:                 {len(losses)} ({len(losses)/len(all_trades)*100:.1f}%)")
    print(f"  Total P&L:                     ${sum(t.pnl for t in all_trades):,.2f}")
    print(f"  Final Balance:                 ${initial_balance + sum(t.pnl for t in all_trades):,.2f}")
    print(f"  Return:                        {sum(t.pnl for t in all_trades)/initial_balance*100:.1f}%")

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
    for t in all_trades:
        if t.pnl <= 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0
    print(f"  Max Consecutive Losses:        {max_consec}")

    actual_r_wins = []
    actual_r_losses = []
    
    for t in all_trades:
        initial_risk = t.risk_distance if hasattr(t, 'risk_distance') and t.risk_distance > 0 else abs(t.entry_price - t.initial_sl) if hasattr(t, 'initial_sl') else abs(t.entry_price - t.sl)
        if initial_risk > 0:
            r_multiple = (t.exit_price - t.entry_price) / initial_risk if t.direction == "buy" else (t.entry_price - t.exit_price) / initial_risk
            if t.pnl > 0:
                actual_r_wins.append(r_multiple)
            else:
                actual_r_losses.append(r_multiple)

    if actual_r_wins:
        print(f"\n  Win R-multiples:")
        print(f"    Average:                   {np.mean(actual_r_wins):.2f}R")
    
    if actual_r_losses:
        print(f"\n  Loss R-multiples:")
        print(f"    Average:                   {np.mean(actual_r_losses):.2f}")

    if actual_r_wins and actual_r_losses:
        expectancy = (len(wins)/len(all_trades) * np.mean(actual_r_wins)) + (len(losses)/len(all_trades) * np.mean(actual_r_losses))
        print(f"\n  Expectancy per trade:        {expectancy:.2f}R")

    print(f"\n  All Trades:")
    print(f"\n  {'#':<4} {'Date':<12} {'Pair':<8} {'Dir':<4} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'Reason':<15}")
    print(f"  {'-'*4} {'-'*12} {'-'*8} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*15}")

    for i, t in enumerate(all_trades, 1):
        pnl_sign = "+" if t.pnl > 0 else ""
        print(f"  {i:<4} {t.entry_time.strftime('%Y-%m-%d'):<12} {t.symbol:<8} {t.direction.upper():<4} "
              f"{t.entry_price:>10.5f} {t.exit_price:>10.5f} "
              f"${pnl_sign}{t.pnl:>8.2f} {t.exit_reason:<15}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    run_breakout_test()
