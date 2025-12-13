# Data Export & Analytics - Guida Completa

Sistema completo di **Data Export** e **Analytics Avanzate** per Trading Agent con metriche finanziarie professionali, equity curve, e supporto backtesting.

## Indice

- [Overview](#overview)
- [Architettura](#architettura)
- [API Endpoints](#api-endpoints)
- [Metriche Calcolate](#metriche-calcolate)
- [Esempi Utilizzo](#esempi-utilizzo)
- [Output Format](#output-format)
- [Best Practices](#best-practices)
- [Performance & Ottimizzazioni](#performance--ottimizzazioni)

---

## Overview

Il sistema di Data Export & Analytics fornisce:

✅ **Export Completo** - Tutti i dati trading in JSON/CSV con filtri temporali
✅ **Analytics Avanzate** - Metriche finanziarie professionali (Sharpe, Sortino, Calmar, Max DD)
✅ **Correlation Analysis** - Decisioni AI → Trade → Risultati
✅ **Equity Curve** - Cumulative P&L nel tempo
✅ **Performance Breakdown** - Per simbolo, periodo, direzione
✅ **Backtesting Ready** - Formato ottimizzato per analisi retrospettive

### Componenti Principali

```
backend/
├── analytics.py           # Modulo calcolo metriche avanzate
├── data_export.py         # Modulo export dati multi-formato
├── main.py                # API endpoints (modificato)
└── test_data_export.py    # Test suite
```

---

## Architettura

### 1. Analytics Module (`analytics.py`)

**Classe: `TradingAnalytics`**

Calcola metriche finanziarie avanzate a partire da DataFrame di trade.

**Input:**
- `trades_df`: DataFrame con colonne `created_at`, `closed_at`, `pnl_usd`, `pnl_pct`, `direction`, `symbol`, `fees_usd`, `duration_minutes`, `status`
- `decisions_df` (opzionale): DataFrame decisioni AI per correlation analysis

**Output:**
- `PerformanceMetrics`: Dataclass con 45+ metriche di performance

**Metodi Principali:**
```python
analytics = TradingAnalytics(trades_df)

# Calcola tutte le metriche
metrics = analytics.calculate_all_metrics()

# Genera equity curve
equity_curve = analytics.generate_equity_curve()

# Breakdown per simbolo
breakdown_symbol = analytics.breakdown_by_symbol()

# Breakdown temporale (daily/weekly/monthly)
breakdown_daily = analytics.breakdown_by_timeframe('daily')
```

### 2. Data Export Module (`data_export.py`)

**Classe: `DataExporter`**

Gestisce export dati in vari formati con filtri temporali.

**Metodi Statici Principali:**
```python
# Export completo
data = DataExporter.export_full_dataset(
    days=30,
    period_preset='7d',
    include_context=True,
    include_metrics=True,
    format='json'
)

# Export backtesting
backtest_data = DataExporter.export_backtest_format(days=30)

# Export CSV
csv_string = DataExporter.export_to_csv_string(data)
```

**Preset Periodi Disponibili:**
- `12h` - Last 12 hours (0.5 days)
- `24h` - Last 24 hours (1 day)
- `3d` - Last 3 days
- `7d` - Last 7 days (1 week)
- `30d` - Last 30 days (1 month)
- `90d` - Last 90 days (3 months)
- `365d` - Last 365 days (1 year)

---

## API Endpoints

### 1. Export Completo

**Endpoint:** `GET /api/export/full`

Export completo di tutti i dati trading con filtri temporali flessibili.

**Query Parameters:**
- `days` (int, optional): Numero di giorni da esportare
- `period` (string, optional): Preset periodo (`12h`, `24h`, `3d`, `7d`, `30d`, `90d`, `365d`)
- `start_date` (string, optional): Data inizio (ISO format: `2025-12-01`)
- `end_date` (string, optional): Data fine (ISO format: `2025-12-13`)
- `include_context` (bool, default: `true`): Include contesto AI (indicators, news, sentiment)
- `include_metrics` (bool, default: `true`): Include metriche analytics
- `format` (string, default: `json`): Formato export (`json` o `csv`)

**Esempi:**
```bash
# Export 7 giorni JSON con analytics
curl "http://localhost:8000/api/export/full?period=7d&include_metrics=true"

# Export 30 giorni CSV
curl "http://localhost:8000/api/export/full?period=30d&format=csv" > trading_data.csv

# Export custom date range
curl "http://localhost:8000/api/export/full?start_date=2025-12-01&end_date=2025-12-13&include_metrics=true"

# Export senza contesto AI (più leggero)
curl "http://localhost:8000/api/export/full?period=7d&include_context=false"
```

**Response Structure (JSON):**
```json
{
  "export_info": {
    "timestamp": "2025-12-13T10:30:00Z",
    "period_days": 7,
    "period_preset": "7d",
    "format": "json",
    "include_context": true,
    "include_metrics": true
  },
  "summary": {
    "total_trades": 45,
    "total_decisions": 52,
    "total_snapshots": 168,
    "llm_api_calls": 104,
    "errors_logged": 3
  },
  "data": {
    "trades": [...],
    "decisions": [...],
    "account_snapshots": [...],
    "llm_usage": [...],
    "errors": [...]
  },
  "analytics": {
    "performance_metrics": {...},
    "equity_curve": [...],
    "breakdown_by_symbol": {...},
    "breakdown_by_day": [...]
  }
}
```

---

### 2. Export Backtesting

**Endpoint:** `GET /api/export/backtest`

Export ottimizzato per backtesting con correlation decisioni AI → trade.

**Query Parameters:**
- `days` (int, default: 30): Numero di giorni da esportare

**Esempio:**
```bash
curl "http://localhost:8000/api/export/backtest?days=30"
```

**Response Structure:**
```json
{
  "export_info": {
    "timestamp": "2025-12-13T10:30:00Z",
    "days": 30,
    "format": "backtest"
  },
  "decisions": [
    {
      "decision_id": 123,
      "decision_time": "2025-12-10T14:30:00Z",
      "operation": "open",
      "symbol": "BTC",
      "direction": "long",
      "target_portion": 0.15,
      "leverage": 3.0,
      "raw_payload": {...},
      "indicators": [...],
      "news": "...",
      "sentiment": {...},
      "forecasts": [...]
    }
  ],
  "actual_trades": [
    {
      "trade_id": 456,
      "created_at": "2025-12-10T14:31:00Z",
      "symbol": "BTC",
      "direction": "long",
      "entry_price": 96500.0,
      "exit_price": 97200.0,
      "pnl_usd": 105.5,
      "pnl_pct": 0.73,
      "status": "closed"
    }
  ],
  "correlation": [
    {
      "decision_id": 123,
      "trade_id": 456,
      "decision_time": "2025-12-10T14:30:00Z",
      "trade_open_time": "2025-12-10T14:31:00Z",
      "symbol": "BTC",
      "direction": "long",
      "predicted_confidence": 0.68,
      "actual_pnl_usd": 105.5,
      "actual_pnl_pct": 0.73
    }
  ],
  "stats": {
    "total_decisions": 52,
    "total_trades": 45,
    "execution_rate": 0.865
  }
}
```

---

### 3. Performance Analytics

**Endpoint:** `GET /api/analytics/performance`

Calcola metriche di performance avanzate.

**Query Parameters:**
- `days` (int, default: 30): Numero di giorni da analizzare
- `symbol` (string, optional): Filtra per simbolo specifico (es. `BTC`, `ETH`)

**Esempi:**
```bash
# Performance ultimi 30 giorni
curl "http://localhost:8000/api/analytics/performance?days=30"

# Performance BTC only
curl "http://localhost:8000/api/analytics/performance?days=30&symbol=BTC"

# Performance ultimi 7 giorni
curl "http://localhost:8000/api/analytics/performance?days=7"
```

**Response Structure:**
```json
{
  "period_days": 30,
  "symbol_filter": null,
  "metrics": {
    "start_date": "2025-11-13T00:00:00Z",
    "end_date": "2025-12-13T23:59:59Z",
    "days_analyzed": 31,

    "total_trades": 45,
    "winning_trades": 28,
    "losing_trades": 17,
    "win_rate": 0.622,

    "total_pnl_usd": 1234.56,
    "total_pnl_pct": 12.35,
    "avg_win_usd": 89.34,
    "avg_loss_usd": -45.67,
    "avg_win_pct": 0.92,
    "avg_loss_pct": -0.47,
    "largest_win_usd": 245.78,
    "largest_loss_usd": -123.45,
    "profit_factor": 2.15,

    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.31,
    "calmar_ratio": 3.57,
    "max_drawdown_usd": 345.67,
    "max_drawdown_pct": 12.5,

    "avg_trade_duration_minutes": 180.5,
    "median_trade_duration_minutes": 165.0,
    "max_consecutive_wins": 5,
    "max_consecutive_losses": 3,

    "long_trades": 28,
    "short_trades": 17,
    "long_win_rate": 0.643,
    "short_win_rate": 0.588,
    "long_pnl_usd": 789.12,
    "short_pnl_usd": 445.44,

    "total_fees_usd": 23.45,
    "avg_fee_per_trade": 0.52,

    "total_decisions": 52,
    "decisions_executed": 45,
    "execution_rate": 0.865
  },
  "equity_curve": [
    {
      "timestamp": "2025-11-13T10:30:00Z",
      "cumulative_pnl_usd": 25.50,
      "trade_pnl": 25.50,
      "symbol": "BTC",
      "direction": "long"
    },
    {
      "timestamp": "2025-11-13T15:45:00Z",
      "cumulative_pnl_usd": 68.75,
      "trade_pnl": 43.25,
      "symbol": "ETH",
      "direction": "short"
    }
  ],
  "breakdown_by_symbol": {
    "BTC": {
      "total_trades": 25,
      "win_rate": 0.64,
      "total_pnl_usd": 789.12,
      "avg_pnl_usd": 31.56,
      "best_trade": 245.78,
      "worst_trade": -98.45
    },
    "ETH": {
      "total_trades": 20,
      "win_rate": 0.60,
      "total_pnl_usd": 445.44,
      "avg_pnl_usd": 22.27,
      "best_trade": 156.23,
      "worst_trade": -123.45
    }
  },
  "breakdown_by_day": [
    {
      "period": "2025-11-13",
      "trades": 3,
      "wins": 2,
      "win_rate": 0.667,
      "pnl_usd": 68.75,
      "fees_usd": 0.65
    },
    {
      "period": "2025-11-14",
      "trades": 2,
      "wins": 1,
      "win_rate": 0.50,
      "pnl_usd": 15.30,
      "fees_usd": 0.40
    }
  ]
}
```

---

### 4. Export Presets

**Endpoint:** `GET /api/export/presets`

Restituisce lista preset periodi disponibili.

**Esempio:**
```bash
curl "http://localhost:8000/api/export/presets"
```

**Response:**
```json
{
  "presets": [
    {"key": "12h", "days": 0.5, "label": "Last 12 hours"},
    {"key": "24h", "days": 1, "label": "Last 24 hours"},
    {"key": "3d", "days": 3, "label": "Last 3 days"},
    {"key": "7d", "days": 7, "label": "Last 7 days (1 week)"},
    {"key": "30d", "days": 30, "label": "Last 30 days (1 month)"},
    {"key": "90d", "days": 90, "label": "Last 90 days (3 months)"},
    {"key": "365d", "days": 365, "label": "Last 365 days (1 year)"}
  ]
}
```

---

## Metriche Calcolate

### Risk-Adjusted Metrics

#### 1. Sharpe Ratio (Annualizzato)
**Formula:** `(Mean Return - Risk Free Rate) / Std Deviation × √365`

**Interpretazione:**
- `< 0`: Perdita (worse than risk-free)
- `0-1`: Volatile performance
- `1-2`: Good performance
- `> 2`: Excellent performance

**Uso:** Misura return risk-adjusted. Considera tutta la volatilità (upside + downside).

---

#### 2. Sortino Ratio (Annualizzato)
**Formula:** `(Mean Return - Risk Free Rate) / Downside Deviation × √365`

**Interpretazione:**
- Simile a Sharpe, ma penalizza solo downside volatility
- Più alto di Sharpe = strategia asimmetrica (big wins, small losses)

**Uso:** Preferibile a Sharpe per strategie asimmetriche.

---

#### 3. Calmar Ratio
**Formula:** `|Total Return| / |Max Drawdown|`

**Interpretazione:**
- `< 1`: Return non compensa drawdown
- `1-3`: Acceptable
- `> 3`: Excellent (high return, low drawdown)

**Uso:** Misura efficienza rischio/rendimento.

---

#### 4. Maximum Drawdown
**Definizione:** Massima perdita da peak a trough.

**Calcolo:**
- USD: Max differenza tra cumulative P&L peak e successive trough
- %: Max DD USD / Running Max P&L

**Uso:** Identifica worst-case scenario loss.

---

### Performance Metrics

#### 5. Win Rate
**Formula:** `Winning Trades / Total Trades`

**Benchmark:**
- `< 40%`: Problema strategia (a meno che R:R alto)
- `40-60%`: Normale
- `> 60%`: Ottimo (verifica profit factor)

---

#### 6. Profit Factor
**Formula:** `Total Wins (USD) / |Total Losses (USD)|`

**Interpretazione:**
- `< 1`: Losing strategy
- `1-2`: Profitable
- `> 2`: Very good (check if sustainable)

---

#### 7. Average Win/Loss
**Metriche:**
- Average Win USD/PCT
- Average Loss USD/PCT

**Uso:** Verifica R:R ratio effettivo (should be >= 1.5).

---

### Trading Patterns

#### 8. Consecutive Streaks
- Max Consecutive Wins
- Max Consecutive Losses

**Uso:** Identifica clustering e streaks non casuali.

---

#### 9. Trade Duration
- Average Duration (minutes)
- Median Duration (minutes)

**Uso:** Verifica holding time alignment con strategia.

---

#### 10. Direction Performance
- Long Trades / Short Trades count
- Long Win Rate / Short Win Rate
- Long P&L / Short P&L

**Uso:** Identifica bias direzionale.

---

## Esempi Utilizzo

### Esempio 1: Export Completo con Python

```python
import requests
import pandas as pd
import json

# Export ultimi 30 giorni con analytics
response = requests.get(
    "http://localhost:8000/api/export/full",
    params={
        'period': '30d',
        'include_metrics': True,
        'include_context': True
    }
)

data = response.json()

# Accedi ai dati
trades = pd.DataFrame(data['data']['trades'])
metrics = data['analytics']['performance_metrics']
equity = pd.DataFrame(data['analytics']['equity_curve'])

# Stampa metriche chiave
print(f"Total Trades: {metrics['total_trades']}")
print(f"Win Rate: {metrics['win_rate']:.2%}")
print(f"Total P&L: ${metrics['total_pnl_usd']:.2f}")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: ${metrics['max_drawdown_usd']:.2f} ({metrics['max_drawdown_pct']:.2f}%)")

# Salva dati
trades.to_csv('trades_30d.csv', index=False)
equity.to_csv('equity_curve_30d.csv', index=False)
with open('metrics_30d.json', 'w') as f:
    json.dump(metrics, f, indent=2)
```

---

### Esempio 2: Analisi Performance Per Simbolo

```python
import requests
import pandas as pd

# Get performance BTC
response_btc = requests.get(
    "http://localhost:8000/api/analytics/performance",
    params={'days': 30, 'symbol': 'BTC'}
)

# Get performance ETH
response_eth = requests.get(
    "http://localhost:8000/api/analytics/performance",
    params={'days': 30, 'symbol': 'ETH'}
)

btc_metrics = response_btc.json()['metrics']
eth_metrics = response_eth.json()['metrics']

# Confronta performance
comparison = pd.DataFrame({
    'BTC': [
        btc_metrics['total_trades'],
        btc_metrics['win_rate'],
        btc_metrics['total_pnl_usd'],
        btc_metrics['sharpe_ratio']
    ],
    'ETH': [
        eth_metrics['total_trades'],
        eth_metrics['win_rate'],
        eth_metrics['total_pnl_usd'],
        eth_metrics['sharpe_ratio']
    ]
}, index=['Trades', 'Win Rate', 'P&L USD', 'Sharpe'])

print(comparison)
```

---

### Esempio 3: Backtesting Analysis

```python
import requests
import pandas as pd

# Export backtest format
response = requests.get(
    "http://localhost:8000/api/export/backtest",
    params={'days': 30}
)

data = response.json()

# Converti a DataFrame
decisions = pd.DataFrame(data['decisions'])
trades = pd.DataFrame(data['actual_trades'])
correlation = pd.DataFrame(data['correlation'])

# Analizza execution rate
print(f"Total Decisions: {data['stats']['total_decisions']}")
print(f"Executed Trades: {data['stats']['total_trades']}")
print(f"Execution Rate: {data['stats']['execution_rate']:.2%}")

# Analizza performance per confidence level
correlation['confidence_bucket'] = pd.cut(
    correlation['predicted_confidence'],
    bins=[0, 0.6, 0.7, 0.8, 1.0],
    labels=['Low', 'Medium', 'High', 'Very High']
)

performance_by_confidence = correlation.groupby('confidence_bucket').agg({
    'actual_pnl_usd': ['count', 'mean', 'sum'],
    'actual_pnl_pct': 'mean'
})

print("\nPerformance by Confidence:")
print(performance_by_confidence)
```

---

### Esempio 4: Equity Curve Visualization

```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

# Get analytics
response = requests.get(
    "http://localhost:8000/api/analytics/performance",
    params={'days': 30}
)

data = response.json()
equity_curve = pd.DataFrame(data['equity_curve'])

# Converti timestamp
equity_curve['timestamp'] = pd.to_datetime(equity_curve['timestamp'])

# Plot equity curve
plt.figure(figsize=(12, 6))
plt.plot(equity_curve['timestamp'], equity_curve['cumulative_pnl_usd'], linewidth=2)
plt.title('Equity Curve - Last 30 Days', fontsize=14, fontweight='bold')
plt.xlabel('Date')
plt.ylabel('Cumulative P&L (USD)')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('equity_curve_30d.png', dpi=300)
plt.show()

# Identifica drawdown periods
equity_curve['running_max'] = equity_curve['cumulative_pnl_usd'].cummax()
equity_curve['drawdown'] = equity_curve['cumulative_pnl_usd'] - equity_curve['running_max']

max_dd_idx = equity_curve['drawdown'].idxmin()
max_dd_value = equity_curve.loc[max_dd_idx, 'drawdown']
max_dd_date = equity_curve.loc[max_dd_idx, 'timestamp']

print(f"\nMax Drawdown: ${abs(max_dd_value):.2f} on {max_dd_date}")
```

---

## Output Format

### Trades Export (JSON)
```json
{
  "trade_id": 456,
  "created_at": "2025-12-10T14:31:00Z",
  "closed_at": "2025-12-10T18:45:00Z",
  "bot_operation_id": 123,
  "trade_type": "open",
  "symbol": "BTC",
  "direction": "long",
  "entry_price": 96500.0,
  "exit_price": 97200.0,
  "size": 0.15,
  "size_usd": 14475.0,
  "leverage": 3,
  "stop_loss_price": 95000.0,
  "take_profit_price": 98500.0,
  "exit_reason": "take_profit",
  "pnl_usd": 105.5,
  "pnl_pct": 0.73,
  "duration_minutes": 254,
  "status": "closed",
  "fees_usd": 1.45,
  "slippage_pct": 0.05,
  "hl_order_id": "0x123abc"
}
```

### Decisions Export (JSON, con context)
```json
{
  "decision_id": 123,
  "decision_time": "2025-12-10T14:30:00Z",
  "operation": "open",
  "symbol": "BTC",
  "direction": "long",
  "target_portion": 0.15,
  "leverage": 3.0,
  "raw_payload": {
    "operation": "open",
    "confidence": 0.68,
    "reason": "Strong bullish momentum with MACD crossover",
    "invalidation_condition": "BTC breaks below $95,000 4h support"
  },
  "indicators": [
    {
      "ticker": "BTC",
      "price": 96500.0,
      "ema20_15m": 96200.0,
      "ema50_15m": 95800.0
    }
  ],
  "news": "Bitcoin surges past $96k as institutional demand increases...",
  "sentiment": {
    "value": 72,
    "classification": "Greed"
  },
  "forecasts": []
}
```

### CSV Export Format
```csv
trade_id,created_at,symbol,direction,entry_price,exit_price,pnl_usd,pnl_pct,status
456,2025-12-10T14:31:00Z,BTC,long,96500.0,97200.0,105.5,0.73,closed
457,2025-12-10T16:20:00Z,ETH,short,3450.0,3420.0,43.25,1.25,closed
```

---

## Best Practices

### 1. Scelta Periodo Export

**Per Analisi Tattiche (intraday):**
- Usa `12h` o `24h`
- Analizza pattern giornalieri
- Monitora execution rate

**Per Review Settimanali:**
- Usa `7d`
- Confronta con settimane precedenti
- Verifica Sharpe Ratio trend

**Per Analisi Strategiche:**
- Usa `30d` o `90d`
- Calcola metriche stabili (Sharpe > 30 trade campione)
- Identifica bias e pattern

**Per Backtesting:**
- Usa `365d` o custom date range
- Include sempre contesto AI completo
- Usa formato backtest

---

### 2. Interpretazione Metriche

**Sharpe Ratio:**
- Campione minimo: 30 trades
- < 0.5: Rivedi strategia
- 0.5-1.0: Ok ma volatile
- 1.0-2.0: Ottimo
- > 2.0: Eccellente (verifica sostenibilità)

**Max Drawdown:**
- Deve essere < 20% per strategie conservative
- Deve essere < 30% per strategie aggressive
- Se > 30%: riduci leverage/position size

**Win Rate:**
- Non focalizzarti solo su win rate
- Verifica sempre profit factor (more important)
- Win rate alto + profit factor basso = problema R:R

---

### 3. Export Performance

**Ottimizza Query:**
- Per periodi lunghi (>90d), usa `include_context=false` se non necessario
- CSV è ~70% più leggero di JSON
- Usa filtri simbolo quando possibile

**Database Indexing:**
```sql
-- Aggiungi indici per performance
CREATE INDEX IF NOT EXISTS idx_executed_trades_closed_at ON executed_trades(closed_at);
CREATE INDEX IF NOT EXISTS idx_bot_operations_created_at ON bot_operations(created_at);
CREATE INDEX IF NOT EXISTS idx_executed_trades_symbol ON executed_trades(symbol);
```

---

### 4. Workflow Consigliato

**1. Daily Review:**
```bash
# Export 24h
curl "http://localhost:8000/api/export/full?period=24h&include_metrics=true" > daily_$(date +%Y%m%d).json

# Check metriche giornaliere
curl "http://localhost:8000/api/analytics/performance?days=1" | jq '.metrics | {win_rate, pnl_usd, sharpe_ratio}'
```

**2. Weekly Analysis:**
```bash
# Export 7d con breakdown
curl "http://localhost:8000/api/analytics/performance?days=7" | jq '{
  metrics: .metrics | {total_trades, win_rate, total_pnl_usd, sharpe_ratio, max_drawdown_usd},
  breakdown: .breakdown_by_symbol
}'
```

**3. Monthly Backtest:**
```python
# Export backtest 30d e analizza correlazioni
import requests
import pandas as pd

data = requests.get("http://localhost:8000/api/export/backtest?days=30").json()
correlation = pd.DataFrame(data['correlation'])

# Performance per confidence level
perf_by_conf = correlation.groupby(
    pd.cut(correlation['predicted_confidence'], bins=[0, 0.6, 0.7, 0.8, 1.0])
).agg({
    'actual_pnl_usd': ['count', 'mean', 'sum'],
    'actual_pnl_pct': 'mean'
})
print(perf_by_conf)
```

---

## Performance & Ottimizzazioni

### Database Performance

**Indici Raccomandati:**
```sql
-- Indici temporali (più importanti)
CREATE INDEX IF NOT EXISTS idx_executed_trades_created_at ON executed_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_executed_trades_closed_at ON executed_trades(closed_at);
CREATE INDEX IF NOT EXISTS idx_bot_operations_created_at ON bot_operations(created_at);

-- Indici filtri
CREATE INDEX IF NOT EXISTS idx_executed_trades_symbol ON executed_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_executed_trades_status ON executed_trades(status);
CREATE INDEX IF NOT EXISTS idx_executed_trades_direction ON executed_trades(direction);

-- Indici compositi (per query complesse)
CREATE INDEX IF NOT EXISTS idx_trades_status_closed ON executed_trades(status, closed_at)
WHERE status = 'closed';
```

**Query Performance:**
- Export 7d: ~200-500ms (con indici)
- Export 30d: ~500-1500ms (con indici)
- Analytics calculation: ~100-300ms (45 trades)

---

### Caching (Opzionale)

Per API ad alto traffico, considera Redis caching:

```python
# Esempio cache Redis (opzionale)
import redis
import json

cache = redis.Redis(host='localhost', port=6379, db=0)

def get_cached_analytics(days: int, symbol: str = None):
    cache_key = f"analytics:{days}:{symbol or 'all'}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Calculate
    data = DataExporter._get_trades_data(days)
    if symbol:
        data = [t for t in data if t['symbol'] == symbol]

    analytics = TradingAnalytics(pd.DataFrame(data))
    metrics = analytics.calculate_all_metrics()

    # Cache 5 min
    cache.setex(cache_key, 300, json.dumps(metrics.to_dict()))

    return metrics.to_dict()
```

---

### Rate Limiting

Per produzione, aggiungi rate limiting agli endpoint export:

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.get("/api/export/full", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def export_full_dataset(...):
    # Max 10 richieste/minuto
    ...
```

---

## Testing

### Test Suite

Esegui test completi:
```bash
cd backend
python test_data_export.py
```

**Test Coverage:**
- ✅ Export presets
- ✅ Export 7d JSON
- ✅ Export 30d CSV
- ✅ Backtest format
- ✅ Performance analytics
- ✅ Symbol-specific analytics

---

### Manual Testing

**Test 1: Export Completo**
```bash
curl -s "http://localhost:8000/api/export/full?period=7d&include_metrics=true" | jq '.summary'
```

Expected:
```json
{
  "total_trades": 45,
  "total_decisions": 52,
  "total_snapshots": 168,
  "llm_api_calls": 104,
  "errors_logged": 3
}
```

**Test 2: CSV Download**
```bash
curl "http://localhost:8000/api/export/full?period=30d&format=csv" > trades.csv
head -5 trades.csv
```

**Test 3: Performance Metrics**
```bash
curl -s "http://localhost:8000/api/analytics/performance?days=30" | jq '.metrics | {win_rate, sharpe_ratio, max_drawdown_usd}'
```

---

## FAQ

**Q: Qual è la differenza tra `/api/export/full` e `/api/export/backtest`?**

A:
- `/api/export/full`: Export completo di tutti i dati (trades, decisions, snapshots, llm_usage, errors) + analytics opzionale
- `/api/export/backtest`: Formato ottimizzato per backtesting con correlation decisioni → trade + stats execution rate

**Q: Posso esportare solo le decisioni senza i trade?**

A: Sì, usa `/api/export/full?include_context=true` e accedi a `data.decisions`.

**Q: Come calcolare Sharpe Ratio manualmente?**

A:
```python
import numpy as np

# Calcola daily returns
returns = trades['pnl_pct'] / 100  # Converti % a decimale

# Mean e std
mean_return = returns.mean()
std_return = returns.std()

# Sharpe annualizzato (assume 365 trading days)
sharpe = (mean_return - 0.0) / std_return * np.sqrt(365)
```

**Q: Posso filtrare per direzione (long/short)?**

A: L'endpoint analytics non supporta filtro direzione diretto, ma puoi filtrare lato client:
```python
trades = pd.DataFrame(data['data']['trades'])
long_trades = trades[trades['direction'] == 'long']
analytics_long = TradingAnalytics(long_trades)
metrics_long = analytics_long.calculate_all_metrics()
```

**Q: Come gestire export molto grandi (>1 anno)?**

A:
1. Usa `include_context=false` per ridurre dimensioni
2. Usa formato CSV (più leggero)
3. Scarica in batch mensili
4. Considera database export diretto:
   ```bash
   psql -U trading_user -d trading_db -c "COPY (SELECT * FROM executed_trades WHERE created_at > NOW() - INTERVAL '365 days') TO STDOUT CSV HEADER" > trades_1y.csv
   ```

---

## Troubleshooting

**Problema: "No trades found for the specified period"**

Soluzione:
- Verifica che ci siano trade nel periodo richiesto
- Controlla database: `SELECT COUNT(*) FROM executed_trades WHERE status='closed';`
- Aumenta periodo: usa `90d` invece di `7d`

**Problema: "Error calculating metrics"**

Soluzione:
- Serve almeno 2 trade chiusi per calcolare Sharpe/Sortino
- Verifica colonne trade: `pnl_usd`, `pnl_pct`, `closed_at` devono essere presenti

**Problema: Export molto lento (>10s)**

Soluzione:
- Aggiungi indici database (vedi sezione Performance)
- Riduci periodo o usa `include_context=false`
- Verifica connessione database

---

## Changelog

**v1.0.0 - 2025-12-13**
- ✅ Initial release
- ✅ Export completo JSON/CSV
- ✅ Analytics avanzate (Sharpe, Sortino, Calmar, Max DD)
- ✅ Backtest format con correlation
- ✅ Equity curve generation
- ✅ Breakdown per simbolo/periodo/direzione
- ✅ 4 API endpoints
- ✅ Test suite completa
- ✅ Documentazione completa

---

## Support

Per domande o problemi:
1. Consulta questa guida
2. Esegui test suite: `python test_data_export.py`
3. Verifica logs: `tail -f backend/trading_agent.log`
4. Controlla database: `psql -U trading_user -d trading_db`

---

**Happy Analyzing! 📊**
