import MetaTrader5 as mt5
import time
from utils.notifications import alert_trade_open, alert_trade_close, alert_error

class MT5Executor:
    def __init__(self, config):
        self.magic_number = config["execution"]["magic_number"]
        self.slippage = config["execution"]["slippage_tolerance"]
        self.connected = False

    def connect(self):
        if not mt5.initialize():
            alert_error(f"MT5 init failed: {mt5.last_error()}")
            return False
        self.connected = True
        return True

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_balance(self):
        account = mt5.account_info()
        if account:
            return account.balance
        return 0

    def get_open_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return positions

    def open_trade(self, symbol, direction, entry_price, sl, tp, lot_size, reason):
        if not self.connected:
            alert_error("MT5 not connected")
            return None

        point = mt5.symbol_info(symbol).point
        digits = mt5.symbol_info(symbol).digits

        sl = round(sl, digits)
        tp = round(tp, digits)

        if direction == "buy":
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid

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

        trade = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": price,
            "sl": sl,
            "tp": tp,
            "lot_size": lot_size,
            "reason": reason,
            "ticket": result.order,
        }

        alert_trade_open(type("Trade", (), trade)())
        return trade

    def close_all_positions(self, symbol):
        positions = self.get_open_positions(symbol)
        for pos in positions:
            if pos.magic != self.magic_number:
                continue

            point = mt5.symbol_info(symbol).point
            digits = mt5.symbol_info(symbol).digits

            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask

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
                trade_data = {
                    "symbol": symbol,
                    "direction": "buy" if pos.type == mt5.POSITION_TYPE_BUY else "sell",
                    "entry_price": pos.price_open,
                    "exit_price": price,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "lot_size": pos.volume,
                    "reason": "session_close",
                    "pnl": pnl,
                    "pips": round((price - pos.price_open) / point if pos.type == mt5.POSITION_TYPE_BUY else (pos.price_open - price) / point, 1),
                    "entry_time": pos.time,
                    "exit_time": time.time(),
                    "exit_reason": "session_close",
                }
                alert_trade_close(type("Trade", (), trade_data)())
