from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import time

import MetaTrader5 as mt5

from utils.notifications import alert_trade_open, alert_trade_close, alert_error


@dataclass
class TradeData:
    symbol: str
    direction: str
    entry_price: float
    sl: float
    tp: float
    lot_size: float
    reason: str
    ticket: Optional[int] = None
    entry_time: Any = None
    exit_price: Optional[float] = None
    exit_time: Any = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    pips: float = 0.0


class MT5Executor:
    def __init__(self, config: Dict[str, Any]):
        self.magic_number = config["execution"]["magic_number"]
        self.slippage = config["execution"]["slippage_tolerance"]
        self.connected = False

    def connect(self) -> bool:
        if not mt5.initialize():
            alert_error(f"MT5 init failed: {mt5.last_error()}")
            return False
        self.connected = True
        return True

    def disconnect(self) -> None:
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_balance(self) -> float:
        account = mt5.account_info()
        if account:
            return account.balance
        return 0.0

    def get_open_positions(self, symbol: str) -> List[Any]:
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return list(positions)

    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        sl: float,
        tp: float,
        lot_size: float,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        if not self.connected:
            alert_error("MT5 not connected")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            alert_error(f"Symbol info not found: {symbol}")
            return None

        point = symbol_info.point
        digits = symbol_info.digits

        sl = round(sl, digits)
        tp = round(tp, digits)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            alert_error(f"Could not get tick for: {symbol}")
            return None

        if direction == "buy":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.slippage,
            "magic": self.magic_number,
            "comment": f"pipst4eet:{reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result}" if result else "No result"
            alert_error(error_msg)
            return None

        trade_data = TradeData(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            sl=sl,
            tp=tp,
            lot_size=lot_size,
            reason=reason,
            ticket=result.order,
            entry_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        alert_trade_open(trade_data)

        return {
            "symbol": symbol,
            "direction": direction,
            "entry_price": price,
            "sl": sl,
            "tp": tp,
            "lot_size": lot_size,
            "reason": reason,
            "ticket": result.order,
        }

    def close_all_positions(self, symbol: str) -> None:
        positions = self.get_open_positions(symbol)
        for pos in positions:
            if pos.magic != self.magic_number:
                continue

            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                continue

            point = symbol_info.point
            digits = symbol_info.digits

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                continue

            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": pos.ticket,
                "price": price,
                "deviation": self.slippage,
                "magic": self.magic_number,
                "comment": "session_close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                pnl = pos.profit
                direction = "buy" if pos.type == mt5.POSITION_TYPE_BUY else "sell"

                if pos.type == mt5.POSITION_TYPE_BUY:
                    pips_val = (price - pos.price_open) / point
                else:
                    pips_val = (pos.price_open - price) / point

                trade_data = TradeData(
                    symbol=symbol,
                    direction=direction,
                    entry_price=pos.price_open,
                    sl=pos.sl,
                    tp=pos.tp,
                    lot_size=pos.volume,
                    reason="session_close",
                    ticket=pos.ticket,
                    entry_time=pos.time,
                    exit_price=price,
                    exit_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    exit_reason="session_close",
                    pnl=pnl,
                    pips=round(pips_val, 1),
                )

                alert_trade_close(trade_data)
