import time
import pandas as pd
from datetime import datetime, timedelta
from data.fetcher import DataFetcher
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from risk.manager import RiskManager
from execution.mt5_executor import MT5Executor
from utils.notifications import send_message, alert_error, alert_daily_summary
from utils.logger import setup_logger

logger = setup_logger("live")

class LiveBot:
    def __init__(self, config):
        self.config = config
        self.pairs = config["trading"]["pairs"]
        self.timeframe = config["trading"]["timeframe"]
        self.session_start = config["trading"]["session_start"]
        self.session_end = config["trading"]["session_end"]
        self.close_before = config["trading"]["close_positions_before"]

        self.fetcher = DataFetcher()
        self.regime_detector = None
        self.trend_strategy = TrendFollowingStrategy(config)
        self.mr_strategy = MeanReversionStrategy(config)

        initial_balance = config["backtest"]["initial_balance"]
        self.risk_manager = RiskManager(config, initial_balance)
        self.executor = MT5Executor(config)

        self.daily_pnls = {pair: 0.0 for pair in self.pairs}
        self.daily_trades_count = 0
        self.last_candle_time = None

    def connect(self):
        if not self.executor.connect():
            return False

        balance = self.executor.get_balance()
        if balance > 0:
            self.risk_manager.balance = balance
            self.risk_manager.peak_balance = balance

        send_message(
            f"🤖 <b>BOT STARTED</b>\n\n"
            f"💰 Balance: <b>${balance:.2f}</b>\n"
            f"📊 Pairs: <code>{', '.join(self.pairs)}</code>\n"
            f"⏰ Session: {self.session_start} - {self.session_end} UTC+3\n"
            f"📈 Timeframe: <code>{self.timeframe}</code>"
        )
        return True

    def run(self):
        logger.info("Live bot started")

        while True:
            try:
                self._tick()
                time.sleep(15)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.executor.disconnect()
                break
            except Exception as e:
                logger.error(f"Error in live loop: {e}")
                alert_error(str(e))
                time.sleep(60)

    def _tick(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M")

        if time_str >= self.close_before:
            for symbol in self.pairs:
                self.executor.close_all_positions(symbol)
            return

        if not self._is_session_active(time_str):
            return

        if self._is_new_candle(now):
            self.last_candle_time = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
            self._scan_pairs()

    def _is_session_active(self, time_str):
        return self.session_start <= time_str <= self.session_end

    def _is_new_candle(self, now):
        candle_time = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        if self.last_candle_time is None:
            return True
        return candle_time > self.last_candle_time

    def _scan_pairs(self):
        for symbol in self.pairs:
            try:
                self._scan_pair(symbol)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

    def _scan_pair(self, symbol):
        end = datetime.now()
        start = end - timedelta(days=90)

        df = self.fetcher.fetch_and_cache(symbol, self.timeframe, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

        if df is None or df.empty or len(df) < 50:
            return

        df = self.trend_strategy.compute_indicators(df)
        df = self.mr_strategy.compute_indicators(df)

        open_positions = self.executor.get_open_positions(symbol)
        has_open = len(open_positions) > 0

        if has_open:
            return

        if not self.risk_manager.can_open_trade():
            return

        idx = len(df) - 1
        row = df.iloc[idx]

        signal = self.trend_strategy.generate_signal(df, idx, has_open)
        if signal is None:
            signal = self.mr_strategy.generate_signal(df, idx, has_open)

        if signal:
            lot_size = self.risk_manager.calculate_position_size(symbol, row["close"], signal["sl"])

            if lot_size > 0:
                trade = self.executor.open_trade(
                    symbol=symbol,
                    direction=signal["direction"],
                    entry_price=row["close"],
                    sl=signal["sl"],
                    tp=signal["tp"],
                    lot_size=lot_size,
                    reason=signal["reason"],
                )

                if trade:
                    self.risk_manager.open_position()
                    self.daily_trades_count += 1
