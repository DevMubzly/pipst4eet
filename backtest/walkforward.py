import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtest.engine import BacktestEngine
from engine.regime import RegimeDetector
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager

class WalkForwardAnalyzer:
    def __init__(self, config):
        self.config = config
        self.train_months = config["backtest"]["walk_forward_train_months"]
        self.test_months = config["backtest"]["walk_forward_test_months"]

    def generate_windows(self, df):
        windows = []
        start = df.index.min()
        end = df.index.max()

        train_delta = pd.DateOffset(months=self.train_months)
        test_delta = pd.DateOffset(months=self.test_months)

        current_start = start
        window_num = 0

        while True:
            train_end = current_start + train_delta
            test_end = train_end + test_delta

            if test_end > end:
                break

            train_mask = (df.index >= current_start) & (df.index < train_end)
            test_mask = (df.index >= train_end) & (df.index < test_end)

            train_df = df[train_mask].copy()
            test_df = df[test_mask].copy()

            if len(train_df) < 500 or len(test_df) < 100:
                current_start += test_delta
                continue

            windows.append({
                "num": window_num,
                "train_start": current_start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
                "train_df": train_df,
                "test_df": test_df,
            })

            window_num += 1
            current_start += test_delta

        return windows

    def run(self, df):
        windows = self.generate_windows(df)

        if not windows:
            print("Not enough data for walk-forward analysis.")
            return None

        print(f"\n{'='*70}")
        print(f"  WALK-FORWARD ANALYSIS")
        print(f"  Train: {self.train_months} months | Test: {self.test_months} months")
        print(f"  Total windows: {len(windows)}")
        print(f"{'='*70}\n")

        all_results = []
        all_trades = []

        for w in windows:
            print(f"  Window {w['num']}: Train {w['train_start'].strftime('%Y-%m-%d')} -> {w['train_end'].strftime('%Y-%m-%d')} | Test {w['test_start'].strftime('%Y-%m-%d')} -> {w['test_end'].strftime('%Y-%m-%d')}")

            train_df = w["train_df"]
            test_df = w["test_df"]

            regime_detector = RegimeDetector(self.config)
            trend_strategy = TrendFollowingStrategy(self.config)
            mr_strategy = MeanReversionStrategy(self.config)

            initial_balance = self.config["backtest"]["initial_balance"]
            risk_manager = RiskManager(self.config, initial_balance)

            engine = BacktestEngine(self.config)
            report = engine.run(test_df, risk_manager, regime_detector, trend_strategy, mr_strategy)

            report["window"] = w["num"]
            report["train_start"] = w["train_start"].strftime("%Y-%m-%d")
            report["test_start"] = w["test_start"].strftime("%Y-%m-%d")
            report["test_end"] = w["test_end"].strftime("%Y-%m-%d")
            all_results.append(report)

            for t in engine.trades:
                all_trades.append(t.to_dict())

        if not all_results:
            print("  No valid windows found.")
            return None

        self._print_summary(all_results)

        if all_trades:
            trades_df = pd.DataFrame(all_trades)
            output_path = "logs/walkforward_trades.csv"
            trades_df.to_csv(output_path, index=False)
            print(f"\n  All trades saved to {output_path}")

        return all_results

    def _print_summary(self, results):
        print(f"\n{'='*70}")
        print(f"  WALK-FORWARD SUMMARY")
        print(f"{'='*70}")

        print(f"\n  {'Window':>6} {'Period':<22} {'Trades':>6} {'Win%':>6} {'PnL':>10} {'DD%':>6} {'PF':>5}")
        print(f"  {'-'*6} {'-'*22} {'-'*6} {'-'*6} {'-'*10} {'-'*6} {'-'*5}")

        for r in results:
            period = f"{r['test_start']} -> {r['test_end']}"
            print(f"  {r['window']:>6} {period:<22} {r['total_trades']:>6} {r['win_rate']:>5.1f}% ${r['total_pnl']:>8,.2f} {r['max_drawdown']:>5.1f}% {r['profit_factor']:>5.2f}")

        total_trades = sum(r["total_trades"] for r in results)
        total_pnl = sum(r["total_pnl"] for r in results)
        total_wins = sum(r["winning_trades"] for r in results)
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_dd = np.mean([r["max_drawdown"] for r in results])
        max_dd = max(r["max_drawdown"] for r in results)
        profitable_windows = sum(1 for r in results if r["total_pnl"] > 0)

        all_pnls = [r["total_pnl"] for r in results]
        consistency = (sum(1 for p in all_pnls if p > 0) / len(all_pnls) * 100) if all_pnls else 0

        print(f"  {'-'*6} {'-'*22} {'-'*6} {'-'*6} {'-'*10} {'-'*6} {'-'*5}")
        print(f"  {'TOTAL':>6} {'':<22} {total_trades:>6} {win_rate:>5.1f}% ${total_pnl:>8,.2f} {avg_dd:>5.1f}% {'':>5}")
        print(f"\n  Max Drawdown (any window): {max_dd}%")
        print(f"  Profitable Windows: {profitable_windows}/{len(results)} ({consistency:.0f}%)")
        print(f"{'='*70}\n")
