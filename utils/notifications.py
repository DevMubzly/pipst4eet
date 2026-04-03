import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_message(text, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def alert_trade_open(trade):
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

def alert_trade_close(trade):
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

def alert_backtest_report(report, symbol):
    emoji = "📈" if report["total_pnl"] > 0 else "📉"
    text = (
        f"{emoji} <b>BACKTEST: {symbol}</b>\n\n"
        f"📊 Trades: <code>{report['total_trades']}</code>\n"
        f"✅ Win Rate: <code>{report['win_rate']}%</code>\n"
        f"💲 PnL: <b>${report['total_pnl']:.2f}</b>\n"
        f"📈 Return: <code>{report['return_pct']}%</code>\n"
        f"📉 Max DD: <code>{report['max_drawdown']}%</code>\n"
        f"⚡ Profit Factor: <code>{report['profit_factor']}</code>\n"
        f"🎯 Trend WR: <code>{report['trend_win_rate']}%</code>\n"
        f"🔄 MR WR: <code>{report['mr_win_rate']}%</code>"
    )
    return send_message(text)

def alert_daily_summary(balance, daily_pnl, daily_trades, symbol_pnls):
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

def alert_error(message):
    text = f"🚨 <b>BOT ERROR</b>\n\n<code>{message}</code>"
    return send_message(text)
