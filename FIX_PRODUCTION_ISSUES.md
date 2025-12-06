# Fix Production Issues - Checklist

## Problema 1: ERR_NETWORK_CHANGED nel browser
**Status**: ✅ NON È UN ERRORE DEL SISTEMA
- Questo è un errore del browser client quando la connessione di rete cambia
- Il backend risponde correttamente (200 OK)
- Il frontend fa retry automatico (normale)

## Problema 2: HTTP 429 Rate Limiting
**Status**: ⚠️ DA VERIFICARE SE RISOLTO

Il container potrebbe non essere stato ricostruito con il nuovo Dockerfile.

### Verifica sulla VPS:

```bash
# 1. Vai nella directory del progetto
cd ~/trading-agent

# 2. Verifica quanti worker uvicorn sono attivi
docker compose -f docker-compose.prod.yml exec app ps aux | grep uvicorn

# 3. Se vedi più di 1 processo uvicorn, rebuilda:
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml up -d app

# 4. Verifica di nuovo
docker compose -f docker-compose.prod.yml exec app ps aux | grep uvicorn
```

**Output atteso** (1 solo processo):
```
root  51  uvicorn main:app --host 0.0.0.0 --port 5611 --workers 1 --loop asyncio
```

## Problema 3: NaN nei forecast (BNB)
**Status**: 🐛 BUG NEL FORECAST

Il forecast per BNB su interval 1h sta generando NaN invece di un numero valido.

### Fix:

Modifica `backend/forecast.py` per gestire NaN nei forecast:

```python
# Quando crei il forecast, verifica che non sia NaN
if pd.isna(forecast_price) or pd.isna(pct_change):
    logger.warning(f"⚠️ Forecast NaN per {symbol} {interval}, skipping")
    continue
```

## Comandi rapidi VPS:

```bash
# Stop, rebuild, start
cd ~/trading-agent
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Verifica logs
docker compose -f docker-compose.prod.yml logs -f app | grep -E "(worker|429|ERROR)"
```

## Verifica finale:

1. ✅ Nessun errore 429 (rate limiting)
2. ✅ Nessun deadlock database
3. ✅ Un solo processo uvicorn
4. ✅ Nessun errore NaN nei forecast
