class RiskManager:
    def __init__(self, config, balance):
        self.risk_pct = config["risk"]["risk_per_trade_pct"]
        self.daily_loss_pct = config["risk"]["daily_loss_limit_pct"]
        self.daily_loss_usd = config["risk"]["daily_loss_limit_usd"]
        self.max_open = config["risk"]["max_open_positions"]
        self.max_daily_trades = config["risk"]["max_daily_trades"]
        self.lot_sizes = config["lots"]
        self.balance = balance
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.open_positions = 0
        self.killed = False

    def calculate_position_size(self, symbol, entry_price, sl_price):
        risk_amount = self.balance * (self.risk_pct / 100)
        sl_distance = abs(entry_price - sl_price)

        if sl_distance == 0:
            return 0

        pair_config = self._get_pair_config(symbol)
        pip_value = pair_config["pip_value"]
        pip_size = pair_config["pip_size"]

        pips_at_risk = sl_distance / pip_size
        lot_size = risk_amount / (pips_at_risk * pip_value)

        lot_size = max(pair_config["min_lot"], min(pair_config["max_lot"], lot_size))
        lot_size = round(lot_size, 2)

        return lot_size

    def _get_pair_config(self, symbol):
        configs = {
            "XAUUSD": {"pip_value": 1.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 5.0},
            "EURUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
            "GBPUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
            "USDJPY": {"pip_value": 10.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 100.0},
            "GBPJPY": {"pip_value": 10.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 100.0},
            "AUDUSD": {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0},
        }
        return configs.get(symbol, {"pip_value": 10.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0})

    def can_open_trade(self):
        if self.killed:
            return False
        if self.open_positions >= self.max_open:
            return False
        if self.daily_trades >= self.max_daily_trades:
            return False
        if self.daily_loss_pct and self.daily_pnl <= -(self.balance * self.daily_loss_pct / 100):
            self.killed = True
            return False
        if self.daily_loss_usd and self.daily_pnl <= -self.daily_loss_usd:
            self.killed = True
            return False
        return True

    def record_trade_result(self, pnl):
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.balance += pnl

        if self.daily_loss_pct and self.daily_pnl <= -(self.balance * self.daily_loss_pct / 100):
            self.killed = True

    def open_position(self):
        self.open_positions += 1

    def close_position(self):
        self.open_positions = max(0, self.open_positions - 1)

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.killed = False

    def is_session_active(self, current_time, session_start, session_end):
        time_str = current_time.strftime("%H:%M")
        return session_start <= time_str <= session_end
