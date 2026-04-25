import pandas as pd
import numpy as np

class Trade:
    def __init__(self, symbol, direction, entry_price, entry_time, sl, tp, lot_size, reason, spread_pips=0.5, slippage_pips=0.3, pair_config=None):
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.sl = sl
        self.tp = tp
        self.lot_size = lot_size
        self.reason = reason
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl = 0.0
        self.pips = 0.0
        self.is_open = True
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips
        self.pair_config = pair_config or {}

        # Apply spread and slippage to entry price
        pip_size = self._pip_size()
        if direction == "buy":
            self.entry_price += (spread_pips / 2 + slippage_pips) * pip_size
        else:
            self.entry_price -= (spread_pips / 2 + slippage_pips) * pip_size

    def check_exit(self, high, low, close, current_time):
        if not self.is_open:
            return None

        pip_size = self._pip_size()
        # Apply spread/slippage to exit prices
        sl_adjusted = self.sl
        tp_adjusted = self.tp
        if self.direction == "buy":
            tp_adjusted -= (self.spread_pips / 2 + self.slippage_pips) * pip_size
        else:
            tp_adjusted += (self.spread_pips / 2 + self.slippage_pips) * pip_size

        if self.direction == "buy":
            if low <= sl_adjusted:
                self._close(sl_adjusted, current_time, "stop_loss")
            elif high >= tp_adjusted:
                self._close(tp_adjusted, current_time, "take_profit")
        elif self.direction == "sell":
            if high >= sl_adjusted:
                self._close(sl_adjusted, current_time, "stop_loss")
            elif low <= tp_adjusted:
                self._close(tp_adjusted, current_time, "take_profit")

        return self

    def _close(self, price, time, reason):
        self.exit_price = price
        self.exit_time = time
        self.exit_reason = reason
        self.is_open = False

        pip_size = self._pip_size()
        pip_value = self._pip_value()

        if self.direction == "buy":
            pips = (price - self.entry_price) / pip_size
        else:
            pips = (self.entry_price - price) / pip_size

        self.pips = round(pips, 1)
        self.pnl = round(pips * pip_value * self.lot_size, 2)

    def _pip_size(self):
        jpy_pairs = ["USDJPY", "GBPJPY"]
        if self.symbol in jpy_pairs:
            return 0.01
        if self.symbol == "XAUUSD":
            return 0.01
        return 0.0001

    def _pip_value(self):
        if self.symbol == "XAUUSD":
            return 1.0
        return 10.0

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "sl": self.sl,
            "tp": self.tp,
            "lot_size": self.lot_size,
            "reason": self.reason,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time,
            "exit_reason": self.exit_reason,
            "pnl": self.pnl,
            "pips": self.pips,
        }


class BacktestEngine:
    def __init__(self, config):
        self.config = config
        self.initial_balance = config["backtest"]["initial_balance"]
        self.balance = self.initial_balance
        self.trades = []
        self.open_trades = []
        self.equity_curve = []
        self.spread_pips = config["backtest"].get("spread_pips", 0.5)
        self.slippage_pips = config["backtest"].get("slippage_pips", 0.3)
        self.pair_config = config.get("pair_config", {})

    def run(self, df, risk_manager, regime_detector, trend_strategy, mr_strategy, smc_strategy=None):
        session_start = self.config["trading"]["session_start"]
        session_end = self.config["trading"]["session_end"]

        df = trend_strategy.compute_indicators(df)
        df = mr_strategy.compute_indicators(df)

        if smc_strategy is not None:
            df = smc_strategy.compute_indicators(df)

        # Run regime detection if enabled and detector provided
        regime_config = self.config.get("regime", {})
        if regime_detector and regime_config.get("enable_regime_filter", False):
            df = regime_detector.detect_regime(df)

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "EURUSD"

        for i in range(len(df)):
            row = df.iloc[i]
            current_time = row.name

            if not isinstance(current_time, pd.Timestamp):
                current_time = pd.Timestamp(current_time)

            time_str = current_time.strftime("%H:%M")
            in_session = session_start <= time_str <= session_end

            self._check_open_exits(row, current_time, risk_manager)

            if not in_session:
                continue

            if risk_manager.can_open_trade():
                has_open = any(t.is_open for t in self.open_trades if t.symbol == symbol)

                signal = None
                regime = row.get("regime", "unknown") if "regime" in df.columns else "unknown"

                # Use regime to prioritize strategies
                if regime_config.get("enable_regime_filter", False):
                    prefer_trend = regime_config.get("prefer_trend_in_trending", True)
                    prefer_mr = regime_config.get("prefer_mr_in_ranging", True)

                    if "trending" in regime and prefer_trend:
                        # Prefer trend strategy in trending markets
                        if smc_strategy is not None:
                            signal = smc_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = trend_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = mr_strategy.generate_signal(df, i, has_open, regime)
                    elif ("ranging" in regime or "weak_range" in regime) and prefer_mr:
                        # Prefer mean reversion in ranging markets
                        if smc_strategy is not None:
                            signal = smc_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = mr_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = trend_strategy.generate_signal(df, i, has_open, regime)
                    else:
                        # Default order
                        if smc_strategy is not None:
                            signal = smc_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = trend_strategy.generate_signal(df, i, has_open, regime)
                        if signal is None:
                            signal = mr_strategy.generate_signal(df, i, has_open, regime)
                else:
                    # Default order without regime filter
                    if smc_strategy is not None:
                        signal = smc_strategy.generate_signal(df, i, has_open)
                    if signal is None:
                        signal = trend_strategy.generate_signal(df, i, has_open)
                    if signal is None:
                        signal = mr_strategy.generate_signal(df, i, has_open)

                if signal:
                    lot_size = risk_manager.calculate_position_size(
                        symbol,
                        row["close"],
                        signal["sl"]
                    )

                    if lot_size > 0:
                        # Get pair-specific spread/slippage if available
                        spread = self.spread_pips
                        slippage = self.slippage_pips
                        if symbol in self.pair_config:
                            spread = self.pair_config[symbol].get("spread_pips", self.spread_pips)

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
                            pair_config=self.pair_config
                        )
                        self.open_trades.append(trade)
                        risk_manager.open_position()

            self.equity_curve.append({
                "time": current_time,
                "balance": risk_manager.balance,
                "equity": risk_manager.balance + sum(t.pnl for t in self.open_trades if t.is_open),
            })

        for trade in list(self.open_trades):
            if trade.is_open:
                trade._close(row["close"], current_time, "session_close")
                risk_manager.record_trade_result(trade.pnl)
                risk_manager.close_position()
                self.trades.append(trade)

        self.balance = risk_manager.balance
        return self.generate_report()

    def _check_open_exits(self, row, current_time, risk_manager):
        for trade in list(self.open_trades):
            if trade.is_open:
                trade.check_exit(row["high"], row["low"], row["close"], current_time)
                if not trade.is_open:
                    risk_manager.record_trade_result(trade.pnl)
                    risk_manager.close_position()
                    self.trades.append(trade)
                    self.balance = risk_manager.balance

    def generate_report(self, df=None):
        closed_trades = [t for t in self.trades if not t.is_open]

        if not closed_trades:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0, "total_pnl": 0, "total_pips": 0,
                "gross_profit": 0, "gross_loss": 0, "profit_factor": 0,
                "avg_win": 0, "avg_loss": 0, "largest_win": 0, "largest_loss": 0,
                "max_drawdown": 0, "max_drawdown_usd": 0,
                "sharpe_ratio": 0, "sortino_ratio": 0,
                "final_balance": self.balance, "return_pct": 0,
                "trend_trades": 0, "trend_wins": 0, "trend_win_rate": 0,
                "mr_trades": 0, "mr_wins": 0, "mr_win_rate": 0,
                "sl_hits": 0, "tp_hits": 0, "session_closes": 0,
                "avg_holding_time": "N/A", "consecutive_losses": 0, "recovery_factor": 0,
            }

        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        pnl_series = pd.Series([t.pnl for t in closed_trades])
        downside = pnl_series[pnl_series < 0]
        sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(252 * 96)) if pnl_series.std() > 0 else 0
        sortino = (pnl_series.mean() / downside.std() * np.sqrt(252 * 96)) if len(downside) > 0 and downside.std() > 0 else 0

        equity = [self.initial_balance]
        for t in closed_trades:
            equity.append(equity[-1] + t.pnl)

        peak = equity[0]
        max_dd = 0
        max_dd_usd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak
            dd_usd = peak - e
            if dd > max_dd:
                max_dd = dd
                max_dd_usd = dd_usd

        trend_trades = [t for t in closed_trades if "trend" in t.reason]
        mr_trades = [t for t in closed_trades if "mr" in t.reason]
        trend_wins = [t for t in trend_trades if t.pnl > 0]
        mr_wins = [t for t in mr_trades if t.pnl > 0]

        sl_hits = [t for t in closed_trades if t.exit_reason == "stop_loss"]
        tp_hits = [t for t in closed_trades if t.exit_reason == "take_profit"]
        session_closes = [t for t in closed_trades if t.exit_reason == "session_close"]

        holding_times = []
        for t in closed_trades:
            if t.entry_time and t.exit_time:
                ht = t.exit_time - t.entry_time
                holding_times.append(ht.total_seconds() / 60)

        avg_ht = np.mean(holding_times) if holding_times else 0
        avg_ht_str = f"{int(avg_ht)}m" if avg_ht < 60 else f"{int(avg_ht // 60)}h {int(avg_ht % 60)}m"

        max_consec = 0
        current_consec = 0
        for t in closed_trades:
            if t.pnl <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        total_loss = abs(gross_loss)
        recovery = gross_profit / total_loss if total_loss > 0 else float("inf")

        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(closed_trades) * 100, 1),
            "total_pnl": round(sum(t.pnl for t in closed_trades), 2),
            "total_pips": round(sum(t.pips for t in closed_trades), 1),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(np.mean([t.pnl for t in wins]), 2) if wins else 0,
            "avg_loss": round(np.mean([t.pnl for t in losses]), 2) if losses else 0,
            "largest_win": round(max([t.pnl for t in wins]), 2) if wins else 0,
            "largest_loss": round(min([t.pnl for t in losses]), 2) if losses else 0,
            "max_drawdown": round(max_dd * 100, 2),
            "max_drawdown_usd": round(max_dd_usd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "final_balance": round(self.balance, 2),
            "return_pct": round((self.balance - self.initial_balance) / self.initial_balance * 100, 2),
            "trend_trades": len(trend_trades),
            "trend_wins": len(trend_wins),
            "trend_win_rate": round(len(trend_wins) / len(trend_trades) * 100, 1) if trend_trades else 0,
            "mr_trades": len(mr_trades),
            "mr_wins": len(mr_wins),
            "mr_win_rate": round(len(mr_wins) / len(mr_trades) * 100, 1) if mr_trades else 0,
            "sl_hits": len(sl_hits),
            "tp_hits": len(tp_hits),
            "session_closes": len(session_closes),
            "avg_holding_time": avg_ht_str,
            "consecutive_losses": max_consec,
            "recovery_factor": round(recovery, 2),
        }
