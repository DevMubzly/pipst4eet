import os
from typing import Dict, Any, Optional
import requests


class Notifier:
    _instance: Optional['Notifier'] = None
    _token: Optional[str] = None
    _chat_id: Optional[str] = None

    @classmethod
    def _load_tokens(cls) -> None:
        if cls._token is None:
            cls._token = os.getenv("TELEGRAM_BOT_TOKEN")
            cls._chat_id = os.getenv("TELEGRAM_CHAT_ID")

    @classmethod
    def get_url(cls) -> Optional[str]:
        cls._load_tokens()
        if cls._token:
            return f"https://api.telegram.org/bot{cls._token}/sendMessage"
        return None


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    url = Notifier.get_url()
    Notifier._load_tokens()

    if not Notifier._token or not Notifier._chat_id or not url:
        return False

    try:
        payload = {
            "chat_id": Notifier._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def alert_trade_open(trade: Any) -> bool:
    text = (
        f"🟢 <b>TRADE OPENED</b>\n\n"
        f"📊 Pair: <code>{trade.symbol}</code>\n"
        f"📈 Direction: <b>{trade.direction.upper()}</b>\n"
        f"💰 Entry: <code>{trade.entry_price}</code>\n"
        f"🛑 SL: <code>{trade.sl}</code>\n"
        f"🎯 TP: <code>{trade.tp}</code>\n"
        f"📦 Lot Size: <code>{trade.lot_size}</code>\n"
        f"📝 Reason: <code>{trade.reason}</code>\n"
        f"🕒 Time: <code>{trade.entry_time}</code>"
    )
    return send_message(text)


def alert_trade_close(trade: Any) -> bool:
    emoji = "✅" if trade.pnl > 0 else "❌"
    text = (
        f"{emoji} <b>TRADE CLOSED</b>\n\n"
        f"📊 Pair: <code>{trade.symbol}</code>\n"
        f"📈 Direction: <b>{trade.direction.upper()}</b>\n"
        f"💰 Entry: <code>{trade.entry_price}</code>\n"
        f"💵 Exit: <code>{trade.exit_price}</code>\n"
        f"📉 Pips: <code>{trade.pips}</code>\n"
        f"💲 PnL: <b>${trade.pnl:.2f}</b>\n"
        f"🚪 Exit: <code>{trade.exit_reason}</code>\n"
        f"🕒 Duration: <code>{trade.entry_time}</code> → <code>{trade.exit_time}</code>"
    )
    return send_message(text)


def alert_backtest_report(report: Dict[str, Any], symbol: str) -> bool:
    emoji = "📈" if report.get("total_pnl", 0) > 0 else "📉"
    text = (
        f"{emoji} <b>BACKTEST: {symbol}</b>\n\n"
        f"📊 Trades: <code>{report.get('total_trades', 0)}</code>\n"
        f"✅ Win Rate: <code>{report.get('win_rate', 0)}%</code>\n"
        f"💲 PnL: <b>${report.get('total_pnl', 0):.2f}</b>\n"
        f"📈 Return: <code>{report.get('return_pct', 0)}%</code>\n"
        f"📉 Max DD: <code>{report.get('max_drawdown', 0)}%</code>\n"
        f"⚡ Profit Factor: <code>{report.get('profit_factor', 0)}</code>\n"
        f"🎯 Trend WR: <code>{report.get('trend_win_rate', 0)}%</code>\n"
        f"🔄 MR WR: <code>{report.get('mr_win_rate', 0)}%</code>"
    )
    return send_message(text)


def alert_daily_summary(
    balance: float, daily_pnl: float, daily_trades: int, symbol_pnls: Dict[str, float]
) -> bool:
    emoji = "✅" if daily_pnl >= 0 else "❌"
    pairs_text = "\n".join([f"  <code>{s}</code>: ${p:+.2f}" for s, p in symbol_pnls.items()])
    text = (
        f"{emoji} <b>DAILY SUMMARY</b>\n\n"
        f"💰 Balance: <b>${balance:.2f}</b>\n"
        f"📊 Daily PnL: <b>${daily_pnl:+.2f}</b>\n"
        f"🔢 Trades: <code>{daily_trades}</code>\n\n"
        f"<b>Per Pair:</b>\n{pairs_text}"
    )
    return send_message(text)


def alert_error(message: str) -> bool:
    text = f"🚨 <b>BOT ERROR</b>\n\n<code>{message}</code>"
    return send_message(text)
