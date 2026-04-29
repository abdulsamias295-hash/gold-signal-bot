"""
XAUUSD Gold Signal Bot v3 — ULTIMATE VERSION
Strategy: EMA Cross + RSI + ADX + H1 Trend Filter
Only fires when ALL conditions align = High accuracy signals
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
TREND_EMA       = 50      # Long term trend filter

# RSI Settings
RSI_PERIOD      = 14
RSI_BUY_MAX     = 60      # Only buy if RSI below 60 (not overbought)
RSI_SELL_MIN    = 40      # Only sell if RSI above 40 (not oversold)

# ADX Settings (trend strength)
ADX_PERIOD      = 14
ADX_MIN         = 25      # Only trade if ADX > 25 (strong trend)

# SL & TP (in dollars)
STOP_LOSS_USD   = 20
TAKE_PROFIT_USD = 50      # 1:2.5 Risk/Reward ratio

# Timeframes
M15_INTERVAL    = "15m"   # Signal timeframe
H1_INTERVAL     = "1h"    # Trend filter timeframe

CHECK_INTERVAL  = 60 * 15  # Check every 15 minutes

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
        f"✅ XAUUSD Ultimate Bot v3 Running!<br><br>"
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


def send_signal(signal, price, rsi, adx, h1_trend):
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
🔥 <b>XAUUSD HIGH ACCURACY SIGNAL</b> 🔥

🕐 Time: {now}
💰 Asset: XAUUSD (Gold)
⚡ Signal: <b>{action}</b>

💵 Entry Price: <b>{price:.2f}</b>
🛑 Stop Loss:   <b>{sl:.2f}</b>  (-${STOP_LOSS_USD})
🎯 Take Profit: <b>{tp:.2f}</b>  (+${TAKE_PROFIT_USD})

📊 <b>Confirmations (ALL GREEN ✅)</b>
✅ EMA Crossover: Confirmed
✅ RSI: {rsi:.1f} (Momentum OK)
✅ ADX: {adx:.1f} (Strong Trend)
✅ H1 Trend: {h1_trend}

📌 {trend}
⚖️ Risk/Reward: 1:2.5

📈 <b>Bot Stats</b>
Total: {tracker['total']} | ✅ {tracker['wins']} Wins | ❌ {tracker['losses']} Losses
🎯 Win Rate: {win_rate:.1f}%

⚠️ <i>High confidence signal — manage risk always.</i>
"""
    send_message(message)
    print(f"[{now}] ✅ Signal: {signal} | Price: {price:.2f} | RSI: {rsi:.1f} | ADX: {adx:.1f}")

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


def get_h1_trend():
    """Check H1 chart trend direction using EMA50."""
    df = get_data(interval="1h", period="30d")
    if df is None:
        return "Unknown", None
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    price  = float(df["close"].iloc[-2])
    ema50  = float(df["ema50"].iloc[-2])
    if price > ema50:
        return "BULLISH 📈", "BUY"
    else:
        return "BEARISH 📉", "SELL"


def get_signal(df):
    """Check all conditions and return signal only if ALL pass."""

    # EMA Crossover
    df["fast"]  = df["close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["slow"]  = df["close"].ewm(span=SLOW_EMA, adjust=False).mean()
    df["trend"] = df["close"].ewm(span=TREND_EMA, adjust=False).mean()

    prev_fast = float(df["fast"].iloc[-3])
    prev_slow = float(df["slow"].iloc[-3])
    curr_fast = float(df["fast"].iloc[-2])
    curr_slow = float(df["slow"].iloc[-2])
    price     = float(df["close"].iloc[-2])
    ema_trend = float(df["trend"].iloc[-2])

    # RSI
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    rsi = float(df["rsi"].iloc[-2])

    # ADX
    df["adx"] = compute_adx(df, ADX_PERIOD)
    adx = float(df["adx"].iloc[-2]) if not pd.isna(df["adx"].iloc[-2]) else 0

    # H1 Trend
    h1_label, h1_bias = get_h1_trend()

    # ── BUY CONDITIONS ──
    ema_cross_up   = prev_fast <= prev_slow and curr_fast > curr_slow
    price_above    = price > ema_trend
    rsi_ok_buy     = rsi < RSI_BUY_MAX
    adx_strong     = adx > ADX_MIN
    h1_confirms_buy = h1_bias == "BUY"

    if ema_cross_up and price_above and rsi_ok_buy and adx_strong and h1_confirms_buy:
        return "BUY", price, rsi, adx, h1_label

    # ── SELL CONDITIONS ──
    ema_cross_down   = prev_fast >= prev_slow and curr_fast < curr_slow
    price_below      = price < ema_trend
    rsi_ok_sell      = rsi > RSI_SELL_MIN
    h1_confirms_sell = h1_bias == "SELL"

    if ema_cross_down and price_below and rsi_ok_sell and adx_strong and h1_confirms_sell:
        return "SELL", price, rsi, adx, h1_label

    return None, price, rsi, adx, h1_label


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
    print("XAUUSD Ultimate Bot v3 Started ✅")
    send_message(
        "🔥 <b>XAUUSD Ultimate Bot v3 Started!</b>\n\n"
        "🧠 Strategy: EMA + RSI + ADX + H1 Filter\n"
        "🎯 Only fires when ALL conditions align\n"
        "📊 Win/Loss tracking active\n"
        "⚖️ Risk/Reward: 1:2.5\n"
        "🥇 Running 24/7 on Render!"
    )

    last_signal = None

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            signal, price, rsi, adx, h1_trend = get_signal(df)
            now = datetime.utcnow().strftime("%H:%M")

            check_pending_result(price)

            if signal and signal != last_signal:
                send_signal(signal, price, rsi, adx, h1_trend)
                last_signal = signal
            else:
                print(f"[{now}] Scanning... Price: {price:.2f} | RSI: {rsi:.1f} | ADX: {adx:.1f} | H1: {h1_trend} | Pending: {tracker['pending'] is not None}")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
