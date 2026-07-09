# journal.py
import csv
from datetime import datetime, timezone
from pathlib import Path

SIGNALS_FILE = Path("signals.csv")

def save_signal_csv(r):
    exists = SIGNALS_FILE.exists()

    fields = [
        "created_at_utc", "symbol", "timeframe", "profile", "side", "score", "grade",
        "entry", "sl", "tp", "rr", "risk_percent", "risk_money", "lot",
        "trend", "structure", "candle_type", "rsi", "adx", "candle_time"
    ]

    with SIGNALS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)

        if not exists:
            writer.writeheader()

        writer.writerow({
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "profile": r["profile"],
            "side": r["status"],
            "score": r["score"],
            "grade": r["grade"],
            "entry": r["entry"],
            "sl": r["sl"],
            "tp": r["tp"],
            "rr": r["rr"],
            "risk_percent": r["risk_percent"],
            "risk_money": r["risk_money"],
            "lot": r["lot"],
            "trend": r["trend"],
            "structure": r["structure"],
            "candle_type": r["candle_type"],
            "rsi": r["rsi"],
            "adx": r["adx"],
            "candle_time": r["candle_time"],
        })
