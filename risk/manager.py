from typing import Dict, Any, Optional
from constants import get_pair_config


class RiskManager:
    def __init__(self, config: Dict[str, Any], balance: float):
        self.risk_pct: float = config["risk"]["risk_per_trade_pct"]
        self.daily_loss_pct: Optional[float] = config["risk"]["daily_loss_limit_pct"]
        self.daily_loss_usd: Optional[float] = config["risk"]["daily_loss_limit_usd"]
        self.max_open: int = config["risk"]["max_open_positions"]
        self.max_daily_trades: int = config["risk"]["max_daily_trades"]
        self.balance: float = balance
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.open_positions: int = 0
        self.killed: bool = False
        self.pair_config: Dict[str, Dict[str, Any]] = config.get("pair_config", {})
        self.enable_compounding: bool = config["risk"].get("enable_compounding", False)
        self.peak_balance: float = balance

    def calculate_position_size(
        self, symbol: str, entry_price: float, sl_price: float
    ) -> float:
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

    def _get_pair_config(self, symbol: str) -> Dict[str, Any]:
        return get_pair_config(symbol, self.pair_config)

    def can_open_trade(self) -> bool:
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

    def record_trade_result(self, pnl: float) -> None:
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.balance += pnl

        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        if self.daily_loss_pct and self.daily_pnl <= -(self.balance * self.daily_loss_pct / 100):
            self.killed = True

    def open_position(self) -> None:
        self.open_positions += 1

    def close_position(self) -> None:
        self.open_positions = max(0, self.open_positions - 1)

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.killed = False
