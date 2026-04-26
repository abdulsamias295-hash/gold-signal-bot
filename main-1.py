"""
XAUUSD Gold Signal Bot v2 — Render.com
Features: MA Crossover + SL/TP Levels + Win/Loss Tracker
"""

import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from flask import Flask
import threading
import os
import json

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8617518115:AAFTNdl_-SzQodqmHRHiDE4tn2JOG6meRR0")
CHAT_ID        = os.environ.get("CHAT_ID", "6729299861")

FAST_MA        = 9
SLOW_MA        = 21
CHECK_INTERVAL = 60 * 15   # Every 15 minutes

# SL & TP settings (in dollars)
STOP_LOSS_USD   = 15   # Stop Loss $15 from entry
TAKE_PROFIT_USD = 30   # Take Profit $30 from entry

# ─────────────────────────────────────────────
#  WIN/LOSS TRACKER
# ─────────────────────────────────────────────

tracker = {
    "total":   0,
    "wins":    0,
    "losses":  0,
    "pending": None
}

# ─────────────────────────────────────────────
#  FLASK APP
# ─────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def home():
    win_rate = (tracker["wins"] / tracker["total"] * 100) if tracker["total"] > 0 else 0
    return (
        f"✅ XAUUSD Signal Bot Running!<br><br>"
        f"📊 Total Signals: {tracker['total']}<br>"
        f"✅ Wins: {tracker['wins']}<br>"
        f"❌ Losses: {tracker['losses']}<br>"
        f"🎯 Win Rate: {win_rate:.1f}%"
    )

# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def send_signal(signal, price):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if signal == "BUY":
        emoji  = "📈"
        action = "BUY (LONG)"
        sl     = round(price - STOP_LOSS_USD, 2)
        tp     = round(price + TAKE_PROFIT_USD, 2)
        trend  = "Gold trending UP 🟢"
    else:
        emoji  = "📉"
        action = "SELL (SHORT)"
        sl     = round(price + STOP_LOSS_USD, 2)
        tp     = round(price - TAKE_PROFIT_USD, 2)
        trend  = "Gold trending DOWN 🔴"

    win_rate = (tracker["wins"] / tracker["total"] * 100) if tracker["total"] > 0 else 0

    message = f"""
{emoji} <b>XAUUSD Signal Alert</b> {emoji}

🕐 Time: {now}
💰 Asset: XAUUSD (Gold)
⚡ Signal: <b>{action}</b>

💵 Entry Price: <b>{price:.2f}</b>
🛑 Stop Loss:   <b>{sl:.2f}</b>  (-${STOP_LOSS_USD})
🎯 Take Profit: <b>{tp:.2f}</b>  (+${TAKE_PROFIT_USD})

📌 {trend}

📊 <b>Bot Stats</b>
Total: {tracker['total']} | ✅ {tracker['wins']} Wins | ❌ {tracker['losses']} Losses
🎯 Win Rate: {win_rate:.1f}%

⚠️ <i>Always manage your risk. Trade responsibly.</i>
"""
    send_message(message)
    print(f"[{now}] Signal: {signal} | Entry: {price:.2f} | SL: {sl} | TP: {tp}")

    tracker["pending"] = {
        "signal": signal,
        "entry":  price,
        "sl":     sl,
        "tp":     tp
    }
    tracker["total"] += 1


def send_result(result, price):
    now = datetime.utcnow().strftime("%H:%M UTC")
    win_rate = (tracker["wins"] / tracker["total"] * 100) if tracker["total"] > 0 else 0

    emoji = "✅" if result == "WIN" else "❌"
    msg   = "Take Profit Hit! 🎯" if result == "WIN" else "Stop Loss Hit! 🛑"

    message = f"""
{emoji} <b>Trade Result — {result}</b>

⏰ {now}
📌 {msg}
💵 Close Price: {price:.2f}

📊 <b>Updated Stats</b>
Total: {tracker['total']} | ✅ {tracker['wins']} Wins | ❌ {tracker['losses']} Losses
🎯 Win Rate: {win_rate:.1f}%
"""
    send_message(message)

# ─────────────────────────────────────────────
#  MARKET DATA & SIGNAL
# ─────────────────────────────────────────────

def get_data():
    try:
        df = yf.download("GC=F", period="5d", interval="15m", progress=False)
        if df.empty:
            return None
        df = df[["Close"]].dropna()
        df.columns = ["close"]
        return df
    except Exception as e:
        print(f"Data error: {e}")
        return None


def get_signal(df):
    df["fast"] = df["close"].ewm(span=FAST_MA, adjust=False).mean()
    df["slow"] = df["close"].ewm(span=SLOW_MA, adjust=False).mean()

    prev_fast = df["fast"].iloc[-3]
    prev_slow = df["slow"].iloc[-3]
    curr_fast = df["fast"].iloc[-2]
    curr_slow = df["slow"].iloc[-2]
    price     = float(df["close"].iloc[-2])

    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return "BUY", price
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        return "SELL", price

    return None, price


def check_pending_result(current_price):
    p = tracker["pending"]
    if not p:
        return

    if p["signal"] == "BUY":
        if current_price >= p["tp"]:
            tracker["wins"] += 1
            tracker["pending"] = None
            send_result("WIN", current_price)
        elif current_price <= p["sl"]:
            tracker["losses"] += 1
            tracker["pending"] = None
            send_result("LOSS", current_price)
    else:
        if current_price <= p["tp"]:
            tracker["wins"] += 1
            tracker["pending"] = None
            send_result("WIN", current_price)
        elif current_price >= p["sl"]:
            tracker["losses"] += 1
            tracker["pending"] = None
            send_result("LOSS", current_price)

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────

def bot_loop():
    print("XAUUSD Bot v2 Started ✅")
    send_message(
        "🤖 <b>XAUUSD Signal Bot v2 Started!</b>\n\n"
        "✅ SL & TP levels included in every signal\n"
        "📊 Win/Loss tracking active\n"
        "🥇 Running 24/7 on Render!"
    )

    last_signal = None

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            signal, price = get_signal(df)
            now = datetime.utcnow().strftime("%H:%M")

            check_pending_result(price)

            if signal and signal != last_signal:
                send_signal(signal, price)
                last_signal = signal
            else:
                print(f"[{now}] No signal | Price: {price:.2f} | Pending: {tracker['pending'] is not None}")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
