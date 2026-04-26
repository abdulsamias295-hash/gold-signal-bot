"""
XAUUSD Gold Signal Bot — Render.com Deployment
Sends Buy/Sell signals to Telegram 24/7
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

# ─────────────────────────────────────────────
#  YOUR SETTINGS
# ─────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8617518115:AAFTNdl_-SzQodqmHRHiDE4tn2JOG6meRR0")
CHAT_ID        = os.environ.get("CHAT_ID", "6729299861")

FAST_MA        = 9
SLOW_MA        = 21
CHECK_INTERVAL = 60 * 15   # Every 15 minutes

# ─────────────────────────────────────────────
#  FLASK APP (Required to keep Render alive)
# ─────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ XAUUSD Signal Bot is Running!"

# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def send_signal(signal, fast_val, slow_val, price):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if signal == "BUY":
        emoji = "📈"
        action = "BUY (LONG)"
        advice = "Gold is trending UP 🟢"
    else:
        emoji = "📉"
        action = "SELL (SHORT)"
        advice = "Gold is trending DOWN 🔴"

    message = f"""
{emoji} <b>XAUUSD Signal Alert</b> {emoji}

🕐 Time: {now}
💰 Asset: XAUUSD (Gold)
⚡ Signal: <b>{action}</b>

📊 Fast EMA ({FAST_MA}): {fast_val:.2f}
📊 Slow EMA ({SLOW_MA}): {slow_val:.2f}
💵 Current Price: {price:.2f}

📌 {advice}

⚠️ <i>Always use Stop Loss. Trade responsibly.</i>
"""
    send_message(message)
    print(f"[{now}] Signal sent: {signal} | Price: {price:.2f}")

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
    fast_val  = float(curr_fast)
    slow_val  = float(curr_slow)

    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return "BUY", fast_val, slow_val, price
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        return "SELL", fast_val, slow_val, price

    return None, fast_val, slow_val, price

# ─────────────────────────────────────────────
#  BOT LOOP (Runs in background thread)
# ─────────────────────────────────────────────

def bot_loop():
    print("XAUUSD Bot Started ✅")
    send_message("🤖 <b>XAUUSD Signal Bot Started!</b>\n\nRunning 24/7 on Render. I will alert you every Gold signal! 🥇")

    last_signal = None

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            signal, fast_val, slow_val, price = get_signal(df)
            now = datetime.utcnow().strftime("%H:%M")

            if signal and signal != last_signal:
                send_signal(signal, fast_val, slow_val, price)
                last_signal = signal
            else:
                print(f"[{now}] No signal | Fast: {fast_val:.2f} | Slow: {slow_val:.2f} | Price: {price:.2f}")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(CHECK_INTERVAL)


# ─────────────────────────────────────────────
#  START
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Run bot in background thread
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()

    # Run Flask web server (keeps Render alive)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
