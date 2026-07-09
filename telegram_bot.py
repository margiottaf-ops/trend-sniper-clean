# settings.py
# Configurazione principale Trend Sniper AI TEST

TEST_MODE = False
HEARTBEAT_ENABLED = True

ACCOUNT_SIZE = 1000
RR_FINAL = 4.0

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
    "4H":  {"enabled": True, "source_interval": "1h",  "period": "60d", "seconds": 14400, "min_score": 86, "pull_atr": 0.60, "adx_min": 20, "risk": 1.00, "profile": "PRINCIPALE"},
    "1H":  {"enabled": True, "source_interval": "1h",  "period": "60d", "seconds": 3600,  "min_score": 90, "pull_atr": 0.55, "adx_min": 22, "risk": 0.50, "profile": "TEST SECONDARIO"},
    "15M": {"enabled": True, "source_interval": "15m", "period": "30d", "seconds": 900,   "min_score": 90, "pull_atr": 0.65, "adx_min": 20, "risk": 0.25, "profile": "SOLO TEST RAPIDO"},
    "5M":  {"enabled": True, "source_interval": "5m",  "period": "7d",  "seconds": 300,   "min_score": 92, "pull_atr": 0.70, "adx_min": 20, "risk": 0.10, "profile": "SOLO PRATICA"},
}
