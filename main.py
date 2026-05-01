"""
XAUUSD Gold Signal Bot v4 — BALANCED VERSION
Strategy: EMA Cross + RSI + ADX (Relaxed filters)
Target: 1-2 quality signals per day
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
#  SETTINGS
# ─────────────────────────────────────────────

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "8617518115:AAFTNdl_-SzQodqmHRHiDE4tn2JOG6meRR0")
CHAT_ID         = os.environ.get("CHAT_ID", "6729299861")

# EMA Settings
FAST_EMA        = 9
SLOW_EMA        = 21

# RSI Settings (relaxed)
RSI_PERIOD      = 14
RSI_BUY_MAX     = 65      # Buy if RSI below 65
RSI_SELL_MIN    = 35      # Sell if RSI above 35

# ADX Settings (relaxed)
ADX_PERIOD      = 14
ADX_MIN         = 20      # Lowered from 25 to 20

# SL & TP
STOP_LOSS_USD   = 20
TAKE_PROFIT_USD = 40      # 1:2 Risk/Reward

CHECK_INTERVAL  = 60 * 15  # Every 15 minutes

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
#  FLASK
# ─────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def home():
    win_rate = (tracker["wins"] / tracker["total"] * 100) if tracker["total"] > 0 else 0
    return (
        f"✅ XAUUSD Balanced Bot v4 Running!<br><br>"
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


def send_signal(signal, price, rsi, adx, strength):
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
💪 Signal Strength: <b>{strength}</b>

💵 Entry Price: <b>{price:.2f}</b>
🛑 Stop Loss:   <b>{sl:.2f}</b>  (-${STOP_LOSS_USD})
🎯 Take Profit: <b>{tp:.2f}</b>  (+${TAKE_PROFIT_USD})

📊 Indicators
• RSI: {rsi:.1f}
• ADX: {adx:.1f} (Trend Strength)

📌 {trend}
⚖️ Risk/Reward: 1:2

📈 <b>Bot Stats</b>
Total: {tracker['total']} | ✅ {tracker['wins']} Wins | ❌ {tracker['losses']} Losses
🎯 Win Rate: {win_rate:.1f}%

⚠️ <i>Always manage your risk. Trade responsibly.</i>
"""
    send_message(message)
    print(f"[{now}] Signal: {signal} | Price: {price:.2f} | RSI: {rsi:.1f} | ADX: {adx:.1f} | Strength: {strength}")

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
#  INDICATORS
# ─────────────────────────────────────────────

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def compute_adx(df, period=14):
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    plus_dm  = high.diff()
    minus_dm = low.diff()
    plus_dm  = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.abs().where((minus_dm.abs() > plus_dm) & (minus_dm < 0), 0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr      = tr.rolling(period).mean()
    plus_di  = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di))
    adx      = dx.rolling(period).mean()
    return adx


def get_signal_strength(rsi, adx, signal):
    """Rate signal as STRONG / MEDIUM based on indicators."""
    score = 0
    if adx > 30:
        score += 2
    elif adx > 20:
        score += 1

    if signal == "BUY" and rsi < 55:
        score += 2
    elif signal == "BUY" and rsi < 65:
        score += 1
    elif signal == "SELL" and rsi > 45:
        score += 2
    elif signal == "SELL" and rsi > 35:
        score += 1

    if score >= 3:
        return "⭐⭐⭐ STRONG"
    elif score >= 2:
        return "⭐⭐ MEDIUM"
    else:
        return "⭐ WEAK"


def get_data(interval="15m", period="5d"):
    try:
        df = yf.download("GC=F", period=period, interval=interval, progress=False)
        if df.empty:
            return None
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close"]].dropna()
        return df
    except Exception as e:
        print(f"Data error: {e}")
        return None


def get_signal(df):
    # EMA
    df["fast"] = df["close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["slow"] = df["close"].ewm(span=SLOW_EMA, adjust=False).mean()

    prev_fast = float(df["fast"].iloc[-3])
    prev_slow = float(df["slow"].iloc[-3])
    curr_fast = float(df["fast"].iloc[-2])
    curr_slow = float(df["slow"].iloc[-2])
    price     = float(df["close"].iloc[-2])

    # RSI
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    rsi = float(df["rsi"].iloc[-2])

    # ADX
    df["adx"] = compute_adx(df, ADX_PERIOD)
    adx = float(df["adx"].iloc[-2]) if not pd.isna(df["adx"].iloc[-2]) else 0

    # BUY: EMA cross up + RSI not overbought + some trend strength
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        if rsi < RSI_BUY_MAX and adx > ADX_MIN:
            strength = get_signal_strength(rsi, adx, "BUY")
            return "BUY", price, rsi, adx, strength

    # SELL: EMA cross down + RSI not oversold + some trend strength
    if prev_fast >= prev_slow and curr_fast < curr_slow:
        if rsi > RSI_SELL_MIN and adx > ADX_MIN:
            strength = get_signal_strength(rsi, adx, "SELL")
            return "SELL", price, rsi, adx, strength

    return None, price, rsi, adx, ""


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
    print("XAUUSD Balanced Bot v4 Started ✅")
    send_message(
        "🔥 <b>XAUUSD Balanced Bot v4 Started!</b>\n\n"
        "📊 Strategy: EMA + RSI + ADX\n"
        "🎯 Target: 1-2 quality signals per day\n"
        "⭐ Signal strength rating included\n"
        "⚖️ Risk/Reward: 1:2\n"
        "🥇 Running 24/7 on Render!"
    )

    last_signal = None

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            signal, price, rsi, adx, strength = get_signal(df)
            now = datetime.utcnow().strftime("%H:%M")

            check_pending_result(price)

            if signal and signal != last_signal:
                send_signal(signal, price, rsi, adx, strength)
                last_signal = signal
            else:
                print(f"[{now}] Scanning | Price: {price:.2f} | RSI: {rsi:.1f} | ADX: {adx:.1f}")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
