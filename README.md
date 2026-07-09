# Trend Sniper Clean v1 TEST

Versione pulita definitiva da test.

## Scopo
Bot gratuito per test demo con GitHub Actions + Telegram.

## Caratteristiche
- Un solo file Python principale: `trend_sniper.py`
- Scan ogni 5 minuti
- 5M ogni 5 minuti
- 15M ogni 15 minuti
- 1H ogni ora
- 4H ogni 4 ore
- Un solo Stop Loss
- Un solo Take Profit 1:4
- Heartbeat Telegram ogni ora
- Log dettagliato dei filtri
- Nessun auto-commit
- Nessun conflitto con GitHub Desktop

## GitHub Secrets richiesti
Repository → Settings → Secrets and variables → Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Artifact
Ogni run salva come artifact:

- `last_scan.json`
- `signals.csv`
- `state.json`

## Nota importante
Il bot usa Yahoo Finance come fonte dati.  
TradingView può mostrare numeri diversi se usa OANDA, SAXO, IC Markets, IG o altri broker.

## Modalità test Telegram
In `trend_sniper.py`:

```python
TEST_MODE = True
```

Poi rimettere:

```python
TEST_MODE = False
```
