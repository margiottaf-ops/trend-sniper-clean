# indicators.py
def ema(values, length):
    a = 2 / (length + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * a + out[-1] * (1 - a))
    return out

def rsi(values, length=14):
    gains, losses = [0], [0]
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag, al = ema(gains, length), ema(losses, length)
    return [100 if l == 0 else 100 - (100 / (1 + g / l)) for g, l in zip(ag, al)]

def atr(rows, length=14):
    tr = []
    for i, r in enumerate(rows):
        if i == 0:
            tr.append(r["high"] - r["low"])
        else:
            pc = rows[i - 1]["close"]
            tr.append(max(r["high"] - r["low"], abs(r["high"] - pc), abs(r["low"] - pc)))
    return ema(tr, length)

def adx(rows, length=14):
    plus_dm, minus_dm, tr = [0], [0], [rows[0]["high"] - rows[0]["low"]]
    for i in range(1, len(rows)):
        up = rows[i]["high"] - rows[i - 1]["high"]
        down = rows[i - 1]["low"] - rows[i]["low"]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr.append(max(rows[i]["high"] - rows[i]["low"], abs(rows[i]["high"] - rows[i - 1]["close"]), abs(rows[i]["low"] - rows[i - 1]["close"])))
    atr_s, plus_s, minus_s = ema(tr, length), ema(plus_dm, length), ema(minus_dm, length)

    dx = []
    for a, p, m in zip(atr_s, plus_s, minus_s):
        if a == 0 or p + m == 0:
            dx.append(0)
        else:
            plus_di, minus_di = 100 * p / a, 100 * m / a
            dx.append(100 * abs(plus_di - minus_di) / (plus_di + minus_di))
    return ema(dx, length)
