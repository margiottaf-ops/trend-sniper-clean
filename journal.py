# datafeed.py
import time
import json
import urllib.request
import urllib.parse

def request_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def yahoo_download(symbol, period, interval):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={period}&interval={interval}"
    data = request_json(url)

    if not data.get("chart") or not data["chart"].get("result"):
        return []

    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    q = result["indicators"]["quote"][0]

    rows = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = q.get("volume", [0] * len(timestamps))[i] or 0
        if o is None or h is None or l is None or c is None:
            continue
        rows.append({"t": int(ts), "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)})
    return rows

def resample_rows(rows, seconds):
    if not rows:
        return []

    if seconds in (3600, 900, 300):
        out = rows[:]
        now = int(time.time())
        if out and now < out[-1]["t"] + seconds:
            out = out[:-1]
        return out

    buckets = {}
    for r in rows:
        b = r["t"] - (r["t"] % seconds)
        if b not in buckets:
            buckets[b] = {"t": b, "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"], "volume": r["volume"]}
        else:
            x = buckets[b]
            x["high"] = max(x["high"], r["high"])
            x["low"] = min(x["low"], r["low"])
            x["close"] = r["close"]
            x["volume"] += r["volume"]

    out = [buckets[k] for k in sorted(buckets.keys())]
    now = int(time.time())
    if out and now < out[-1]["t"] + seconds:
        out = out[:-1]
    return out
