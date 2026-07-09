# strategy.py
from datetime import datetime, timezone
from indicators import ema, rsi, atr, adx
from datafeed import yahoo_download, resample_rows
from settings import ACCOUNT_SIZE, RR_FINAL

def detect_structure(rows, pivot_len=6):
    structure, last_high, last_low = 0, None, None
    for i in range(pivot_len, len(rows) - pivot_len):
        if rows[i]["high"] == max(x["high"] for x in rows[i - pivot_len:i + pivot_len + 1]):
            last_high = rows[i]["high"]
        if rows[i]["low"] == min(x["low"] for x in rows[i - pivot_len:i + pivot_len + 1]):
            last_low = rows[i]["low"]
        if last_high is not None and rows[i]["close"] > last_high:
            structure = 1
        if last_low is not None and rows[i]["close"] < last_low:
            structure = -1
    return structure

def candle_confirm(rows):
    last, prev = rows[-1], rows[-2]
    body = abs(last["close"] - last["open"])
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]

    bull_engulf = last["close"] > last["open"] and prev["close"] < prev["open"] and last["close"] >= prev["open"] and last["open"] <= prev["close"]
    bear_engulf = last["close"] < last["open"] and prev["close"] > prev["open"] and last["close"] <= prev["open"] and last["open"] >= prev["close"]

    hammer = lower > body * 2 and upper <= body * 1.25 and last["close"] > last["open"]
    shooting = upper > body * 2 and lower <= body * 1.25 and last["close"] < last["open"]

    bull = last["close"] > last["open"] and (bull_engulf or hammer or last["close"] > prev["high"])
    bear = last["close"] < last["open"] and (bear_engulf or shooting or last["close"] < prev["low"])

    ctype = "Bullish Engulfing" if bull_engulf else "Bearish Engulfing" if bear_engulf else "Hammer" if hammer else "Shooting Star" if shooting else "Breakout candela precedente" if last["close"] > prev["high"] else "Breakdown candela precedente" if last["close"] < prev["low"] else "Nessuna"
    return bull, bear, ctype

def grade(score):
    return "A+" if score >= 97 else "A" if score >= 94 else "B+" if score >= 90 else "B" if score >= 86 else "C"

def estimate_lot(symbol, entry, sl, risk_percent):
    risk_money = ACCOUNT_SIZE * risk_percent / 100
    distance = abs(entry - sl)
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
    return round(risk_money / (pips * 10), 2) if pips > 0 else 0.0

def analyze_symbol(symbol_name, yahoo_symbol, timeframe, cfg):
    raw = yahoo_download(yahoo_symbol, cfg["period"], cfg["source_interval"])
    rows = resample_rows(raw, cfg["seconds"])

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

    closes = [r["close"] for r in rows]

    ema20, ema50, ema200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    rv, av, xv = rsi(closes, 14), atr(rows, 14), adx(rows, 14)

    last, close = rows[-1], rows[-1]["close"]

    ema_long = close > ema200[-1] and ema20[-1] > ema50[-1] and ema50[-1] > ema200[-1]
    ema_short = close < ema200[-1] and ema20[-1] < ema50[-1] and ema50[-1] < ema200[-1]

    rsi_long = 50 < rv[-1] < 72
    rsi_short = 28 < rv[-1] < 50
    adx_ok = xv[-1] >= cfg["adx_min"]
    pull_ok = abs(close - ema20[-1]) <= av[-1] * cfg["pull_atr"]

    struct = detect_structure(rows, 6)
    structure_long, structure_short = struct == 1, struct == -1

    bull_confirm, bear_confirm, candle_type = candle_confirm(rows)

    long_score = (30 if ema_long else 0) + (15 if structure_long else 0) + (15 if rsi_long else 0) + (10 if adx_ok else 0) + (15 if pull_ok else 0) + (10 if bull_confirm else 0) + 5
    short_score = (30 if ema_short else 0) + (15 if structure_short else 0) + (15 if rsi_short else 0) + (10 if adx_ok else 0) + (15 if pull_ok else 0) + (10 if bear_confirm else 0) + 5

    side, score = "WAIT", max(long_score, short_score)

    if long_score >= cfg["min_score"] and ema_long and structure_long and rsi_long and adx_ok and pull_ok and bull_confirm:
        side, score = "BUY", long_score
    elif short_score >= cfg["min_score"] and ema_short and structure_short and rsi_short and adx_ok and pull_ok and bear_confirm:
        side, score = "SELL", short_score

    result = {
        "symbol": symbol_name,
        "timeframe": timeframe,
        "profile": cfg["profile"],
        "status": side,
        "score": score,
        "grade": grade(score),
        "price": close,
        "rsi": rv[-1],
        "adx": xv[-1],
        "candle_type": candle_type,
        "trend": "LONG" if ema_long else "SHORT" if ema_short else "NEUTRALE",
        "structure": "BULLISH" if structure_long else "BEARISH" if structure_short else "NEUTRALE",
        "candle_time": datetime.fromtimestamp(last["t"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "candle_id": str(last["t"]),
        "risk_percent": cfg["risk"],
        "checks": {
            "EMA": ema_long or ema_short,
            "BOS": (ema_long and structure_long) or (ema_short and structure_short),
            "RSI": (ema_long and rsi_long) or (ema_short and rsi_short),
            "ADX": adx_ok,
            "Pullback": pull_ok,
            "Candela": (ema_long and bull_confirm) or (ema_short and bear_confirm),
        },
    }

    if side == "WAIT":
        return result

    entry = close

    if side == "BUY":
        sl = min(entry - av[-1] * 1.5, min(r["low"] for r in rows[-14:]))
        risk = entry - sl
        tp = entry + risk * RR_FINAL
    else:
        sl = max(entry + av[-1] * 1.5, max(r["high"] for r in rows[-14:]))
        risk = sl - entry
        tp = entry - risk * RR_FINAL

    result.update({
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": RR_FINAL,
        "risk_money": ACCOUNT_SIZE * cfg["risk"] / 100,
        "lot": estimate_lot(symbol_name, entry, sl, cfg["risk"]),
    })

    return result
