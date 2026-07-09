# Trend Sniper Clean TEST

Versione definitiva da test per repository pulito.

## Caratteristiche
- Scan ogni 5 minuti
- 5M ogni 5 minuti
- 15M ogni 15 minuti
- 1H ogni ora
- 4H ogni 4 ore
- Nessun push automatico
- Nessun conflitto con GitHub Desktop
- Heartbeat Telegram ogni ora
- Log dettagliato dei filtri
- Un solo Stop Loss
- Un solo Take Profit 1:4

## File principali
- `trend_sniper.py` = programma principale
- `settings.py` = configurazione
- `strategy.py` = regole segnali
- `indicators.py` = indicatori tecnici
- `telegram_bot.py` = messaggi Telegram
- `journal.py` = salvataggio segnali
- `datafeed.py` = dati Yahoo Finance

## GitHub Secrets
Nel nuovo repository devi aggiungere:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Percorso:

Settings → Secrets and variables → Actions → New repository secret

## Artifact
Il bot non scrive più nel repository.
I file vengono salvati come artifact dentro ogni run:

- `last_scan.json`
- `signals.csv`
- `state.json`

## Test Telegram
Per testare Telegram, in `settings.py` metti:

```python
TEST_MODE = True
```

Poi rimetti:

```python
TEST_MODE = False
```

## Nota importante
Il bot usa Yahoo Finance come sorgente dati.  
TradingView può mostrare numeri diversi perché usa broker/datafeed diversi.
