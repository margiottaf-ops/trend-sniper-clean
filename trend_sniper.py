# Trend Sniper Clean v3 TEST
# Railway + Telegram
# Demo/testing only. Non è consulenza finanziaria.
#
# Modifiche principali:
# - 1D aggiunto come timeframe e filtro direzionale principale
# - 4H usato come conferma per i timeframe inferiori
# - 30M aggiunto
# - 5M mantenuto ma reso molto più selettivo
# - 5M/15M/30M notificati solo 08:00-20:00 ora italiana
# - 1H/4H/1D notificati sempre
# - anti-duplicati finché il setup resta attivo
# - stop ATR leggermente più ampio, con size ricalcolata
# - scansioni allineate alle chiusure dei 5 minuti
#
# IMPORTANTE:
# - lascia GitHub Actions disabilitato
# - deve girare una sola istanza su Railway

import os
import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# =========================
# CONFIGURAZIONE
# =========================

TEST_MODE = False
HEARTBEAT_ENABLED = True

ACCOUNT_SIZE = 1000
RR_FINAL = 4.0

ITALY_TZ = ZoneInfo("Europe/Rome")
NOTIFY_START_HOUR = 8
NOTIFY_END_HOUR = 20  # escluso: notifiche 08:00-19:59

STATE_FILE = Path("state.json")
SIGNALS_FILE = Path("signals.csv")
LAST_SCAN_FILE = Path("last_scan.json")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "XAUUSD": "GC=F",
    "US100": "NQ=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
}

PROFILES = {
    "1D": {
        "enabled": True,
        "source_interval": "1d",
        "period": "2y",
        "seconds": 86400,
        "min_score": 90,
        "pull_atr": 0.75,
        "adx_min": 20,
        "risk": 0.50,
        "sl_atr": 2.2,
        "profile": "TREND PRINCIPALE",
    },
    "4H": {
        "enabled": True,
        "source_interval": "1h",
        "period": "60d",
        "seconds": 14400,
        "min_score": 90,
        "pull_atr": 0.65,
        "adx_min": 22,
        "risk": 0.50,
        "sl_atr": 2.0,
        "profile": "CONFERMA STRUTTURA",
    },
    "1H": {
        "enabled": True,
        "source_interval": "1h",
        "period": "60d",
        "seconds": 3600,
        "min_score": 92,
        "pull_atr": 0.55,
        "adx_min": 24,
        "risk": 0.35,
        "sl_atr": 1.9,
        "profile": "SETUP PRINCIPALE",
    },
    "30M": {
        "enabled": True,
        "source_interval": "15m",
        "period": "30d",
        "seconds": 1800,
        "min_score": 94,
        "pull_atr": 0.50,
        "adx_min": 24,
        "risk": 0.25,
        "sl_atr": 1.8,
        "profile": "SETUP INTERMEDIO",
    },
    "15M": {
        "enabled": True,
        "source_interval": "15m",
        "period": "30d",
        "seconds": 900,
        "min_score": 95,
        "pull_atr": 0.45,
        "adx_min": 25,
        "risk": 0.20,
        "sl_atr": 1.8,
        "profile": "SETUP RAPIDO",
    },
    "5M": {
        "enabled": True,
        "source_interval": "5m",
        "period": "7d",
        "seconds": 300,
        "min_score": 100,
        "pull_atr": 0.35,
        "adx_min": 28,
        "risk": 0.10,
        "sl_atr": 1.8,
        "profile": "SOLO SETUP PREMIUM",
    },
}

PREMIUM_CANDLES_LONG = {"Bullish Engulfing", "Hammer"}
PREMIUM_CANDLES_SHORT = {"Bearish Engulfing", "Shooting Star"}

# =========================
# UTILITÀ
# =========================

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRORE TELEGRAM: token o chat id mancanti")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    request = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(response.read().decode("utf-8"))
        return True
    except Exception as exc:
        print(f"ERRORE INVIO TELEGRAM: {exc}")
        return False


def fmt(value):
    if abs(value) >= 100:
        return f"{value:.2f}"
    if abs(value) >= 10:
        return f"{value:.3f}"
    return f"{value:.5f}"


def grade(score):
    if score >= 100:
        return "A++"
    if score >= 97:
        return "A+"
    if score >= 94:
        return "A"
    if score >= 90:
        return "B+"
    if score >= 86:
        return "B"
    return "C"


def italian_now(now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(ITALY_TZ)


def notification_window_open(now_utc):
    local = italian_now(now_utc)
    return NOTIFY_START_HOUR <= local.hour < NOTIFY_END_HOUR


# =========================
# SCHEDULAZIONE TIMEFRAME
# =========================

def should_scan(timeframe, now):
    if timeframe == "5M":
        return now.minute % 5 == 0
    if timeframe == "15M":
        return now.minute % 15 == 0
    if timeframe == "30M":
        return now.minute % 30 == 0
    if timeframe == "1H":
        return now.minute == 0
    if timeframe == "4H":
        return now.minute == 0 and now.hour % 4 == 0
    if timeframe == "1D":
        return now.minute == 0 and now.hour == 0
    return False


def active_timeframes(now):
    return [
        timeframe
        for timeframe, config in PROFILES.items()
        if config["enabled"] and should_scan(timeframe, now)
    ]


# =========================
# DATI
# =========================

def request_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def yahoo_download(symbol, period, interval):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?range={period}&interval={interval}"
    )
    data = request_json(url)

    if not data.get("chart") or not data["chart"].get("result"):
        return []

    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]
    rows = []

    for index, timestamp in enumerate(timestamps):
        open_ = quote["open"][index]
        high = quote["high"][index]
        low = quote["low"][index]
        close = quote["close"][index]
        volume = quote.get("volume", [0] * len(timestamps))[index] or 0

        if open_ is None or high is None or low is None or close is None:
            continue

        rows.append({
            "t": int(timestamp),
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        })

    return rows


def resample_rows(rows, seconds):
    if not rows:
        return []

    if seconds in (86400, 3600, 900, 300):
        output = rows[:]
        now_ts = int(time.time())

        if output and now_ts < output[-1]["t"] + seconds:
            output = output[:-1]

        return output

    buckets = {}

    for row in rows:
        bucket_time = row["t"] - (row["t"] % seconds)

        if bucket_time not in buckets:
            buckets[bucket_time] = {
                "t": bucket_time,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
        else:
            bucket = buckets[bucket_time]
            bucket["high"] = max(bucket["high"], row["high"])
            bucket["low"] = min(bucket["low"], row["low"])
            bucket["close"] = row["close"]
            bucket["volume"] += row["volume"]

    output = [buckets[key] for key in sorted(buckets)]
    now_ts = int(time.time())

    if output and now_ts < output[-1]["t"] + seconds:
        output = output[:-1]

    return output


# =========================
# INDICATORI
# =========================

def ema(values, length):
    alpha = 2 / (length + 1)
    output = [values[0]]

    for value in values[1:]:
        output.append(value * alpha + output[-1] * (1 - alpha))

    return output


def rsi(values, length=14):
    gains = [0]
    losses = [0]

    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = ema(gains, length)
    avg_loss = ema(losses, length)
    output = []

    for gain, loss in zip(avg_gain, avg_loss):
        if loss == 0:
            output.append(100)
        else:
            output.append(100 - (100 / (1 + gain / loss)))

    return output


def atr(rows, length=14):
    true_ranges = []

    for index, row in enumerate(rows):
        if index == 0:
            true_ranges.append(row["high"] - row["low"])
        else:
            previous_close = rows[index - 1]["close"]
            true_ranges.append(max(
                row["high"] - row["low"],
                abs(row["high"] - previous_close),
                abs(row["low"] - previous_close),
            ))

    return ema(true_ranges, length)


def adx(rows, length=14):
    plus_dm = [0]
    minus_dm = [0]
    true_ranges = [rows[0]["high"] - rows[0]["low"]]

    for index in range(1, len(rows)):
        up = rows[index]["high"] - rows[index - 1]["high"]
        down = rows[index - 1]["low"] - rows[index]["low"]

        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

        true_ranges.append(max(
            rows[index]["high"] - rows[index]["low"],
            abs(rows[index]["high"] - rows[index - 1]["close"]),
            abs(rows[index]["low"] - rows[index - 1]["close"]),
        ))

    atr_smoothed = ema(true_ranges, length)
    plus_smoothed = ema(plus_dm, length)
    minus_smoothed = ema(minus_dm, length)
    dx_values = []

    for atr_value, plus_value, minus_value in zip(
        atr_smoothed,
        plus_smoothed,
        minus_smoothed,
    ):
        if atr_value == 0 or plus_value + minus_value == 0:
            dx_values.append(0)
        else:
            plus_di = 100 * plus_value / atr_value
            minus_di = 100 * minus_value / atr_value
            dx_values.append(
                100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            )

    return ema(dx_values, length)


# =========================
# STRATEGIA
# =========================

def detect_structure(rows, pivot_len=6):
    structure = 0
    last_high = None
    last_low = None

    for index in range(pivot_len, len(rows) - pivot_len):
        window = rows[index - pivot_len:index + pivot_len + 1]

        if rows[index]["high"] == max(item["high"] for item in window):
            last_high = rows[index]["high"]

        if rows[index]["low"] == min(item["low"] for item in window):
            last_low = rows[index]["low"]

        if last_high is not None and rows[index]["close"] > last_high:
            structure = 1

        if last_low is not None and rows[index]["close"] < last_low:
            structure = -1

    return structure


def candle_confirm(rows):
    last = rows[-1]
    previous = rows[-2]

    body = abs(last["close"] - last["open"])
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]

    bull_engulf = (
        last["close"] > last["open"]
        and previous["close"] < previous["open"]
        and last["close"] >= previous["open"]
        and last["open"] <= previous["close"]
    )
    bear_engulf = (
        last["close"] < last["open"]
        and previous["close"] > previous["open"]
        and last["close"] <= previous["open"]
        and last["open"] >= previous["close"]
    )

    hammer = (
        lower > body * 2
        and upper <= body * 1.25
        and last["close"] > last["open"]
    )
    shooting = (
        upper > body * 2
        and lower <= body * 1.25
        and last["close"] < last["open"]
    )

    bull = (
        last["close"] > last["open"]
        and (bull_engulf or hammer or last["close"] > previous["high"])
    )
    bear = (
        last["close"] < last["open"]
        and (bear_engulf or shooting or last["close"] < previous["low"])
    )

    if bull_engulf:
        candle_type = "Bullish Engulfing"
    elif bear_engulf:
        candle_type = "Bearish Engulfing"
    elif hammer:
        candle_type = "Hammer"
    elif shooting:
        candle_type = "Shooting Star"
    elif last["close"] > previous["high"]:
        candle_type = "Breakout candela precedente"
    elif last["close"] < previous["low"]:
        candle_type = "Breakdown candela precedente"
    else:
        candle_type = "Nessuna"

    return bull, bear, candle_type


def estimate_lot(symbol, entry, stop_loss, risk_percent):
    risk_money = ACCOUNT_SIZE * risk_percent / 100
    distance = abs(entry - stop_loss)

    if distance <= 0:
        return 0.0

    if "JPY" in symbol:
        pip_size = 0.01
    elif symbol == "XAUUSD":
        pip_size = 0.10
    elif symbol in ["US100", "BTCUSD", "ETHUSD"]:
        return round(risk_money / distance, 3)
    else:
        pip_size = 0.0001

    pips = distance / pip_size

    if pips <= 0:
        return 0.0

    return round(risk_money / (pips * 10), 2)


def trend_snapshot(symbol_name, yahoo_symbol, timeframe):
    config = PROFILES[timeframe]
    raw = yahoo_download(
        yahoo_symbol,
        config["period"],
        config["source_interval"],
    )
    rows = resample_rows(raw, config["seconds"])

    if len(rows) < 220:
        return "NEUTRALE"

    closes = [row["close"] for row in rows]
    ema20_values = ema(closes, 20)
    ema50_values = ema(closes, 50)
    ema200_values = ema(closes, 200)
    close = closes[-1]

    if (
        close > ema200_values[-1]
        and ema20_values[-1] > ema50_values[-1]
        and ema50_values[-1] > ema200_values[-1]
    ):
        return "LONG"

    if (
        close < ema200_values[-1]
        and ema20_values[-1] < ema50_values[-1]
        and ema50_values[-1] < ema200_values[-1]
    ):
        return "SHORT"

    return "NEUTRALE"


def analyze_symbol(
    symbol_name,
    yahoo_symbol,
    timeframe,
    config,
    daily_trend,
    h4_trend,
    h1_trend,
    m15_trend,
):
    raw = yahoo_download(
        yahoo_symbol,
        config["period"],
        config["source_interval"],
    )
    rows = resample_rows(raw, config["seconds"])

    if len(rows) < 220:
        return {
            "symbol": symbol_name,
            "timeframe": timeframe,
            "status": "NO DATA",
            "score": 0,
            "grade": "N/A",
            "checks": {},
            "note": f"Dati insufficienti: {len(rows)} barre",
        }

    closes = [row["close"] for row in rows]
    ema20_values = ema(closes, 20)
    ema50_values = ema(closes, 50)
    ema200_values = ema(closes, 200)
    rsi_values = rsi(closes, 14)
    atr_values = atr(rows, 14)
    adx_values = adx(rows, 14)

    last = rows[-1]
    close = last["close"]

    ema_long = (
        close > ema200_values[-1]
        and ema20_values[-1] > ema50_values[-1]
        and ema50_values[-1] > ema200_values[-1]
    )
    ema_short = (
        close < ema200_values[-1]
        and ema20_values[-1] < ema50_values[-1]
        and ema50_values[-1] < ema200_values[-1]
    )

    if timeframe == "5M":
        rsi_long = 55 <= rsi_values[-1] <= 65
        rsi_short = 35 <= rsi_values[-1] <= 45
    else:
        rsi_long = 52 < rsi_values[-1] < 70
        rsi_short = 30 < rsi_values[-1] < 48

    adx_ok = adx_values[-1] >= config["adx_min"]
    pullback_ok = (
        abs(close - ema20_values[-1])
        <= atr_values[-1] * config["pull_atr"]
    )

    structure = detect_structure(rows, 6)
    structure_long = structure == 1
    structure_short = structure == -1

    bull_confirm, bear_confirm, candle_type = candle_confirm(rows)

    daily_long = daily_trend == "LONG"
    daily_short = daily_trend == "SHORT"
    h4_long = h4_trend == "LONG"
    h4_short = h4_trend == "SHORT"

    # 1D genera segnali autonomi.
    # Per i timeframe inferiori, il Daily deve essere nella stessa direzione.
    if timeframe == "1D":
        higher_long_ok = True
        higher_short_ok = True
    elif timeframe == "4H":
        higher_long_ok = daily_long
        higher_short_ok = daily_short
    else:
        higher_long_ok = daily_long and h4_long
        higher_short_ok = daily_short and h4_short

    # Il 5M richiede anche allineamento 1H e 15M.
    if timeframe == "5M":
        higher_long_ok = (
            higher_long_ok
            and h1_trend == "LONG"
            and m15_trend == "LONG"
        )
        higher_short_ok = (
            higher_short_ok
            and h1_trend == "SHORT"
            and m15_trend == "SHORT"
        )

    premium_long_candle = candle_type in PREMIUM_CANDLES_LONG
    premium_short_candle = candle_type in PREMIUM_CANDLES_SHORT

    candle_long_ok = bull_confirm
    candle_short_ok = bear_confirm

    if timeframe == "5M":
        candle_long_ok = bull_confirm and premium_long_candle
        candle_short_ok = bear_confirm and premium_short_candle

    long_score = (
        (30 if ema_long else 0)
        + (15 if structure_long else 0)
        + (15 if rsi_long else 0)
        + (10 if adx_ok else 0)
        + (15 if pullback_ok else 0)
        + (10 if candle_long_ok else 0)
        + (5 if higher_long_ok else 0)
        + (10 if timeframe == "5M" and h1_trend == "LONG" and m15_trend == "LONG" else 0)
    )

    short_score = (
        (30 if ema_short else 0)
        + (15 if structure_short else 0)
        + (15 if rsi_short else 0)
        + (10 if adx_ok else 0)
        + (15 if pullback_ok else 0)
        + (10 if candle_short_ok else 0)
        + (5 if higher_short_ok else 0)
        + (10 if timeframe == "5M" and h1_trend == "SHORT" and m15_trend == "SHORT" else 0)
    )

    side = "WAIT"
    score = max(long_score, short_score)

    if (
        long_score >= config["min_score"]
        and ema_long
        and structure_long
        and rsi_long
        and adx_ok
        and pullback_ok
        and candle_long_ok
        and higher_long_ok
    ):
        side = "BUY"
        score = long_score

    elif (
        short_score >= config["min_score"]
        and ema_short
        and structure_short
        and rsi_short
        and adx_ok
        and pullback_ok
        and candle_short_ok
        and higher_short_ok
    ):
        side = "SELL"
        score = short_score

    result = {
        "symbol": symbol_name,
        "timeframe": timeframe,
        "profile": config["profile"],
        "status": side,
        "score": score,
        "grade": grade(score),
        "price": close,
        "rsi": rsi_values[-1],
        "adx": adx_values[-1],
        "candle_type": candle_type,
        "trend": (
            "LONG"
            if ema_long
            else "SHORT"
            if ema_short
            else "NEUTRALE"
        ),
        "structure": (
            "BULLISH"
            if structure_long
            else "BEARISH"
            if structure_short
            else "NEUTRALE"
        ),
        "daily_trend": daily_trend,
        "h4_trend": h4_trend,
        "h1_trend": h1_trend,
        "m15_trend": m15_trend,
        "candle_time": datetime.fromtimestamp(
            last["t"],
            tz=timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC"),
        "candle_id": str(last["t"]),
        "risk_percent": config["risk"],
        "checks": {
            "EMA": ema_long or ema_short,
            "BOS": (
                (ema_long and structure_long)
                or (ema_short and structure_short)
            ),
            "RSI": (
                (ema_long and rsi_long)
                or (ema_short and rsi_short)
            ),
            "ADX": adx_ok,
            "Pullback": pullback_ok,
            "Candela": (
                (ema_long and candle_long_ok)
                or (ema_short and candle_short_ok)
            ),
            "Daily": (
                (ema_long and daily_long)
                or (ema_short and daily_short)
                or timeframe == "1D"
            ),
            "4H": (
                (ema_long and h4_long)
                or (ema_short and h4_short)
                or timeframe in ("1D", "4H")
            ),
        },
    }

    if timeframe == "5M":
        result["checks"]["1H"] = (
            (ema_long and h1_trend == "LONG")
            or (ema_short and h1_trend == "SHORT")
        )
        result["checks"]["15M"] = (
            (ema_long and m15_trend == "LONG")
            or (ema_short and m15_trend == "SHORT")
        )

    if side == "WAIT":
        return result

    entry = close
    stop_multiplier = config["sl_atr"]

    if side == "BUY":
        stop_loss = min(
            entry - atr_values[-1] * stop_multiplier,
            min(row["low"] for row in rows[-14:]),
        )
        risk = entry - stop_loss
        take_profit = entry + risk * RR_FINAL
    else:
        stop_loss = max(
            entry + atr_values[-1] * stop_multiplier,
            max(row["high"] for row in rows[-14:]),
        )
        risk = stop_loss - entry
        take_profit = entry - risk * RR_FINAL

    result.update({
        "entry": entry,
        "sl": stop_loss,
        "tp": take_profit,
        "rr": RR_FINAL,
        "risk_money": ACCOUNT_SIZE * config["risk"] / 100,
        "lot": estimate_lot(
            symbol_name,
            entry,
            stop_loss,
            config["risk"],
        ),
    })

    return result


# =========================
# TELEGRAM / JOURNAL
# =========================

def alert_message(result):
    emoji = "🟢" if result["status"] == "BUY" else "🔴"

    checks = "\n".join(
        f"{'✅' if ok else '❌'} {name}"
        for name, ok in result["checks"].items()
    )

    lot_label = (
        "Unità indicative"
        if result["symbol"] in ["XAUUSD", "US100", "BTCUSD", "ETHUSD"]
        else "Lotto indicativo"
    )

    return (
        "🚨 <b>TREND SNIPER CLEAN v3 TEST</b>\n\n"
        f"{emoji} <b>{result['status']} {result['symbol']}</b>\n"
        f"Timeframe: <b>{result['timeframe']}</b> - {result['profile']}\n"
        f"Qualità: <b>{result['grade']} - {result['score']}/110</b>\n"
        f"Candela chiusa: {result['candle_time']}\n\n"
        "<b>Filtri superiori</b>\n"
        f"Daily: {result['daily_trend']}\n"
        f"4H: {result['h4_trend']}\n"
        f"1H: {result['h1_trend']}\n"
        f"15M: {result['m15_trend']}\n\n"
        "<b>Livelli operativi</b>\n"
        f"Entry: <b>{fmt(result['entry'])}</b>\n"
        f"Stop Loss: <b>{fmt(result['sl'])}</b>\n"
        f"Take Profit 1:{RR_FINAL}: <b>{fmt(result['tp'])}</b>\n\n"
        "<b>Gestione rischio demo</b>\n"
        f"Capitale demo: {ACCOUNT_SIZE} €\n"
        f"Rischio test: {result['risk_percent']}%\n"
        f"Perdita max indicativa: {result['risk_money']:.2f} €\n"
        f"{lot_label}: <b>{result['lot']}</b>\n\n"
        "<b>Motivo</b>\n"
        f"Trend: {result['trend']}\n"
        f"Struttura: {result['structure']}\n"
        f"Candela: {result['candle_type']}\n"
        f"RSI: {result['rsi']:.2f}\n"
        f"ADX: {result['adx']:.2f}\n\n"
        f"{checks}\n\n"
        "⚠️ Demo only. Conferma su TradingView prima di entrare."
    )


def heartbeat_message(last_scan):
    active = ", ".join(last_scan.get("active_timeframes", [])) or "nessuno"

    return (
        "🟢 <b>Trend Sniper Clean v3 online</b>\n\n"
        f"Ultimo scan UTC: {last_scan.get('scan_time_utc')}\n"
        f"Timeframe analizzati: {active}\n"
        f"Alert inviati: {last_scan.get('alerts_sent', 0)}\n"
        f"Segnali silenziati: {last_scan.get('alerts_silenced', 0)}\n"
        f"Mercati controllati: {last_scan.get('markets_checked', 0)}"
    )


def test_message():
    return (
        "✅ <b>Trend Sniper Clean v3 TEST</b>\n\n"
        "Telegram collegato.\n"
        "1D attivo.\n"
        "30M attivo.\n"
        "5M Premium attivo.\n"
        "5M/15M/30M: notifiche 08:00-20:00.\n"
        "1H/4H/1D: notifiche sempre.\n"
        "Anti-duplicati attivo."
    )


def save_signal_csv(result, notification_status):
    exists = SIGNALS_FILE.exists()

    fields = [
        "created_at_utc",
        "symbol",
        "timeframe",
        "profile",
        "side",
        "score",
        "grade",
        "entry",
        "sl",
        "tp",
        "rr",
        "risk_percent",
        "risk_money",
        "lot",
        "trend",
        "structure",
        "daily_trend",
        "h4_trend",
        "h1_trend",
        "m15_trend",
        "candle_type",
        "rsi",
        "adx",
        "candle_time",
        "notification_status",
    ]

    with SIGNALS_FILE.open("a", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fields)

        if not exists:
            writer.writeheader()

        writer.writerow({
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "symbol": result["symbol"],
            "timeframe": result["timeframe"],
            "profile": result["profile"],
            "side": result["status"],
            "score": result["score"],
            "grade": result["grade"],
            "entry": result["entry"],
            "sl": result["sl"],
            "tp": result["tp"],
            "rr": result["rr"],
            "risk_percent": result["risk_percent"],
            "risk_money": result["risk_money"],
            "lot": result["lot"],
            "trend": result["trend"],
            "structure": result["structure"],
            "daily_trend": result["daily_trend"],
            "h4_trend": result["h4_trend"],
            "h1_trend": result["h1_trend"],
            "m15_trend": result["m15_trend"],
            "candle_type": result["candle_type"],
            "rsi": result["rsi"],
            "adx": result["adx"],
            "candle_time": result["candle_time"],
            "notification_status": notification_status,
        })


# =========================
# MAIN
# =========================

def main():
    now = datetime.now(timezone.utc)
    local_now = italian_now(now)

    if TEST_MODE:
        send_telegram(test_message())
        return

    raw_state = load_json(STATE_FILE, {})
    state = {
        "active_setups": raw_state.get("active_setups", {}),
        "last_candles": raw_state.get("last_candles", {}),
    }

    active_setups = state["active_setups"]
    last_candles = state["last_candles"]
    active = active_timeframes(now)
    notify_open = notification_window_open(now)

    alerts = 0
    silenced = 0
    markets_checked = 0

    logs = [
        f"SCAN UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"ORA ITALIA: {local_now.strftime('%Y-%m-%d %H:%M:%S')}",
        "FINESTRA NOTIFICHE: " + ("APERTA" if notify_open else "CHIUSA"),
        "TIMEFRAME ATTIVI ORA: " + (", ".join(active) if active else "nessuno"),
    ]

    trend_cache = {}

    def cached_trend(symbol_name, yahoo_symbol, timeframe):
        key = f"{symbol_name}_{timeframe}"
        if key not in trend_cache:
            trend_cache[key] = trend_snapshot(
                symbol_name,
                yahoo_symbol,
                timeframe,
            )
        return trend_cache[key]

    for timeframe in active:
        config = PROFILES[timeframe]
        logs.append(
            f"===== TIMEFRAME {timeframe} | {config['profile']} ====="
        )

        for name, yahoo_symbol in WATCHLIST.items():
            markets_checked += 1
            setup_key = f"{timeframe}_{name}"

            try:
                daily_trend = cached_trend(name, yahoo_symbol, "1D")
                h4_trend = cached_trend(name, yahoo_symbol, "4H")
                h1_trend = cached_trend(name, yahoo_symbol, "1H")
                m15_trend = cached_trend(name, yahoo_symbol, "15M")

                result = analyze_symbol(
                    name,
                    yahoo_symbol,
                    timeframe,
                    config,
                    daily_trend,
                    h4_trend,
                    h1_trend,
                    m15_trend,
                )

                check_text = " | " + " ".join(
                    f"{key}:{'OK' if value else 'NO'}"
                    for key, value in result.get("checks", {}).items()
                )

                logs.append(
                    f"{timeframe} | {name}: {result['status']} | "
                    f"Score {result['score']} | Grade {result['grade']} | "
                    f"Trend {result.get('trend', '-')}{check_text}"
                )

                if result["status"] not in ["BUY", "SELL"]:
                    active_setups.pop(setup_key, None)
                    continue

                candle_key = f"{setup_key}_{result['candle_id']}"

                if last_candles.get(candle_key):
                    logs.append(
                        f"{timeframe} | {name}: candela già elaborata"
                    )
                    continue

                last_candles[candle_key] = datetime.now(
                    timezone.utc
                ).isoformat()

                if active_setups.get(setup_key) == result["status"]:
                    logs.append(
                        f"{timeframe} | {name}: "
                        "setup ancora attivo, alert non ripetuto"
                    )
                    continue

                active_setups[setup_key] = result["status"]

                high_timeframe = timeframe in ("1H", "4H", "1D")
                should_notify = notify_open or high_timeframe

                if should_notify:
                    sent = send_telegram(alert_message(result))
                    notification_status = (
                        "SENT" if sent else "SEND_ERROR"
                    )
                    if sent:
                        alerts += 1
                else:
                    notification_status = "SILENCED_OUTSIDE_WINDOW"
                    silenced += 1
                    logs.append(
                        f"{timeframe} | {name}: "
                        "segnale registrato ma silenziato"
                    )

                save_signal_csv(result, notification_status)

            except Exception as exc:
                logs.append(
                    f"{timeframe} | {name}: ERRORE {exc}"
                )

    if len(last_candles) > 1000:
        recent_keys = list(last_candles.keys())[-500:]
        state["last_candles"] = {
            key: last_candles[key] for key in recent_keys
        }

    save_json(STATE_FILE, state)

    last_scan = {
        "scan_time_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_time_italy": local_now.strftime("%Y-%m-%d %H:%M:%S"),
        "active_timeframes": active,
        "alerts_sent": alerts,
        "alerts_silenced": silenced,
        "markets_checked": markets_checked,
        "notification_window_open": notify_open,
        "heartbeat_enabled": HEARTBEAT_ENABLED,
    }

    save_json(LAST_SCAN_FILE, last_scan)

    if HEARTBEAT_ENABLED and now.minute == 0 and notify_open:
        send_telegram(heartbeat_message(last_scan))

    print("\n".join(logs))
    print(f"Alert inviati: {alerts}")
    print(f"Alert silenziati: {silenced}")
    print("Ultimo scan salvato in: last_scan.json")


def seconds_until_next_five_minutes():
    now = datetime.now(timezone.utc)
    elapsed = (now.minute % 5) * 60 + now.second
    wait_seconds = 300 - elapsed

    if wait_seconds <= 2:
        wait_seconds += 300

    return wait_seconds


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as exc:
            print(f"ERRORE CICLO PRINCIPALE: {exc}")

        wait = seconds_until_next_five_minutes()
        print(
            f"Attendo {wait} secondi fino alla prossima chiusura 5M..."
        )
        time.sleep(wait)
