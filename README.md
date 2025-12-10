# Trading Agent

**Versione: 0.2.0** 🎉

Trading Agent è un progetto open source ispirato a [Alpha Arena](https://nof1.ai/), una piattaforma di trading AI-driven che promuove la competizione tra agenti LLMs. L'obiettivo di questo progetto è sviluppare un agente di trading automatizzato, capace di analizzare dati di mercato, notizie, sentiment e segnali provenienti da grandi movimenti ("whale alert") per prendere decisioni di trading informate.

## Caratteristiche principali

- **Analisi multi-sorgente**: integra dati di mercato, news, sentiment analysis e whale alert.
- **Previsioni**: utilizza modelli di forecasting per anticipare i movimenti di prezzo.
- **Modularità**: ogni componente (news, sentiment, indicatori, whale alert, forecasting) è gestito da moduli separati, facilmente estendibili.
- **Ispirazione Alpha Arena**: il progetto prende spunto dall'approccio competitivo e AI-driven di Alpha Arena, con l'obiettivo di creare agenti sempre più performanti.
- **Gestione multi-modello AI**: supporta GPT-5.1, GPT-4o-mini e DeepSeek con selezione dinamica.
- **Coin Screener Dinamico**: seleziona automaticamente le migliori coin in base a filtri quantitativi.
- **Rotazione Intelligente & Fasi Separate**:
  - **Fase Gestione**: Monitora costantemente le posizioni aperte per decisioni di chiusura ottimali.
  - **Fase Scouting**: Analizza a rotazione batch di nuove coin (5 per ciclo) per trovare nuove opportunità senza sovraccaricare l'AI.
- **Analisi Manuale**: possibilità di eseguire analisi on-demand su specifiche coin senza interrompere il bot.
- **🆕 Market Microstructure Analysis**: Analisi avanzata order book multi-exchange, whale detection, liquidazioni e sentiment aggregato (v0.2.0).

## 📊 Dashboard Web

Il progetto include una moderna dashboard web (React/Vite) per il monitoraggio in tempo reale.

### Caratteristiche Dashboard (v0.1.1)
- **Performance Overview**: Saldo, PnL e metriche chiave.
- **Market Data**: Dati di mercato aggregati e spread.
- **Operazioni AI**: Log delle decisioni dell'agente con ragionamento, forecast e ID Ciclo.
- **System Logs**: Log di sistema in tempo reale.
- **Gestione Posizioni**: Visualizzazione posizioni aperte e storico chiuse.

Per avviare la dashboard:
```bash
cd frontend
pnpm install
pnpm dev
```
La dashboard sarà accessibile a `http://localhost:5621`.

## 🚀 Docker Deployment

Il progetto supporta sia deployment di sviluppo che produzione completamente containerizzati.

### 🛠️ Sviluppo (Ottimizzato)

Build ottimizzato per velocità e sviluppo iterativo:

#### Caratteristiche
- **Build ottimizzato**: ~8-9 min primo build, ~1-2 min rebuild successivi
- **Layer caching intelligente**: dipendenze separate dal codice
- **Hot reload**: modifiche codice applicate automaticamente
- **Debug tools**: logging e monitoring integrati

#### Comandi Rapidi Sviluppo
```bash
# Build ottimizzato (raccomandato)
make build

# Sviluppo completo: build + avvia + logs
make dev

# Solo avvia servizi esistenti
make up

# Analisi backtrack nel container
make backtrack-analysis

# Test delle ottimizzazioni
./benchmark-build.sh
```

#### Deployment Sviluppo
```bash
# Build con Docker Compose
docker compose build

# Avvia tutto
docker compose up -d

# App: http://localhost:5611
# DB: localhost:5432
```

### 🏭 Produzione (Enterprise-Ready)

Deployment completo per produzione con alta disponibilità, sicurezza e monitoraggio.

#### Caratteristiche Produzione
- **Sicurezza hardened**: user non-root, read-only filesystem
- **SSL/TLS**: crittografia end-to-end con Let's Encrypt
- **Load balancing**: Nginx reverse proxy con rate limiting
- **Monitoring**: Prometheus + Grafana integrati
- **Backup automatico**: database e configurazione
- **Health checks**: monitoraggio continuo dello stato
- **Zero-downtime updates**: rolling deployment
- **Logging centralizzato**: JSON logs per analisi

#### Setup Produzione
```bash
# 1. Configura ambiente produzione
cp backend/env.example backend/.env
nano backend/.env  # Inserisci le tue credenziali

# 2. Configura SSL (Let's Encrypt)
mkdir -p ssl/production
# Ottieni certificati SSL e copiali in ssl/production/

# 3. Deploy completo
./production-deploy.sh
```

#### Servizi Produzione
- **Trading Agent**: App principale con 4 workers uvicorn
- **PostgreSQL**: Database con backup automatico
- **Nginx**: Reverse proxy con SSL e sicurezza
- **Prometheus**: Metriche e monitoraggio
- **Grafana**: Dashboard e visualizzazioni
- **Backup**: Servizio backup automatico

#### Accessi Produzione
- **App**: https://yourdomain.com
- **Grafana**: https://yourdomain.com:3000
- **Prometheus**: https://yourdomain.com:9090
- **API Health**: https://yourdomain.com/api/health

#### Comandi Produzione
```bash
# Deploy completo con backup
./production-deploy.sh

# Backup manuale
./backup/backup.sh

# Monitora logs
docker compose -f docker-compose.prod.yml logs -f

# Update rolling
docker compose -f docker-compose.prod.yml up -d --scale app=3
```

### 📊 Ottimizzazioni Implementate

#### Sviluppo
- **Caching dipendenze**: `pyproject.toml` e `uv.lock` cachati separatamente
- **Frontend caching**: `package.json` e `pnpm-lock.yaml` cachati
- **BuildKit**: build paralleli e cache intelligente
- **.dockerignore**: contesto build ridotto

#### Produzione
- **Multi-stage builds**: ottimizzati per runtime
- **Security hardening**: no-new-privileges, read-only
- **Resource limits**: CPU e memoria controllati
- **Health checks**: monitoraggio automatico
- **Logging strutturato**: JSON logs per centralizzazione

Vedi [`DOCKER_OPTIMIZATION_README.md`](DOCKER_OPTIMIZATION_README.md) per dettagli tecnici sviluppo e [`PRODUCTION_README.md`](PRODUCTION_README.md) per deployment produzione.

## Configurazione

### Setup iniziale

1. **Copia il file di esempio delle variabili d'ambiente:**
   ```bash
   cp .env.example .env
   ```

2. **Configura le variabili d'ambiente necessarie nel file `.env`:**

   **Variabili REQUIRED:**
   - `OPENAI_API_KEY` - Chiave API OpenAI (per GPT-5.1 e GPT-4o-mini)
   - `DATABASE_URL` - Connection string PostgreSQL

   **Variabili per Trading Live:**
   - `TESTNET` - Modalità testnet/mainnet ("true" per testnet, "false" per mainnet, default: "true")
   - **Per Testnet:**
     - `TESTNET_PRIVATE_KEY` - Chiave privata wallet Hyperliquid Testnet
     - `TESTNET_WALLET_ADDRESS` - Indirizzo wallet Hyperliquid Testnet
     - Testnet URL: https://app.hyperliquid-testnet.xyz/trade
     - Testnet Faucet: https://app.hyperliquid-testnet.xyz/drip
   - **Per Mainnet:**
     - `PRIVATE_KEY` - Chiave privata wallet Hyperliquid Mainnet
     - `WALLET_ADDRESS` - Indirizzo wallet Hyperliquid Mainnet

   **Variabili OPZIONALI (migliorano le funzionalità):**
   - `DEEPSEEK_API_KEY` - Per usare il modello DeepSeek
   - `COINGECKO_API_KEY` - Per aumentare rate limit del coin screener
   - `CMC_PRO_API_KEY` - Per Fear & Greed Index
   - `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` - Per notifiche Telegram
   - `VITE_API_URL` - URL backend per il frontend (default: http://localhost:8000)

3. **Consulta il file `.env.example` per dettagli completi su tutte le variabili disponibili.**

### Modelli AI supportati

Il sistema supporta automaticamente:
- **GPT-5.1** (`gpt-5.1-2025-11-13`) - Modello di default, richiede `OPENAI_API_KEY`
- **GPT-4o-mini** - Modello veloce ed economico, richiede `OPENAI_API_KEY`
- **DeepSeek** - Modello alternativo, richiede `DEEPSEEK_API_KEY`

Il sistema rileva automaticamente quali modelli sono disponibili in base alle API keys configurate. Puoi selezionare il modello dal frontend o tramite API.

## Utilizzo Avanzato

### Analisi Manuale

È possibile eseguire un'analisi on-demand su una specifica criptovaluta per verificare le condizioni di mercato o testare l'AI senza dover attendere il ciclo automatico del bot.

```bash
cd backend
python manual_analysis.py <SYMBOL>
```

Esempio:
```bash
python manual_analysis.py ETH
```

Questo script eseguirà l'intero processo decisionale (fetch dati, analisi tecnica, news, sentiment, decisione AI, trend check) e mostrerà il risultato nei log.

## 📊 Market Microstructure Analysis

Il Trading Agent include un modulo avanzato di **Market Microstructure** per analizzare la struttura profonda del mercato attraverso order book multi-exchange, liquidazioni, funding rate e sentiment aggregato.

### 🎯 Caratteristiche

- **Order Book Aggregato**: Combina dati da 6 exchange (Binance, Bybit, OKX, Coinbase, Crypto.com, KuCoin) con pesi di market share
- **Market Coverage**: ~94% del mercato totale (aggiornato Kaiko 2025)
- **Whale Detection**: Identifica automaticamente "whale walls" (ordini > $500k)
- **Market Depth Analysis**: Analizza bid/ask imbalance e liquidità
- **Liquidation Risk**: Monitora rischio cascade tramite Coinglass (opzionale)
- **Funding Rate Aggregato**: Sentiment contrarian da funding rates multi-exchange
- **Long/Short Ratio**: Analisi crowd positioning (contrarian signal)
- **Support/Resistance Dinamici**: Livelli chiave derivati da whale walls e liquidazioni
- **SL/TP Suggestions**: Stop loss e take profit basati su microstructure
- **LLM-Ready Context**: Output formattato per prompt AI

### 🛡️ Sistemi di Resilienza (v0.2.1)

- **Circuit Breaker**: Previene cascade failure se un exchange va offline
- **LRU Cache**: Riduce chiamate API ripetitive del ~70% (TTL configurabile)
- **Rate Limiting**: Rispetta limiti API di ogni exchange (token bucket algorithm)
- **Retry Logic**: Retry automatico con exponential backoff per errori temporanei
- **Graceful Degradation**: Sistema continua a funzionare anche se alcuni exchange sono offline

### 📡 API Endpoints

**Market Microstructure:**
```bash
# Contesto completo microstructure
GET /api/microstructure/{symbol}

# Solo order book aggregato
GET /api/microstructure/{symbol}/orderbook

# Solo dati liquidazioni (richiede Coinglass)
GET /api/microstructure/{symbol}/liquidations
```

**System Monitoring (v0.2.1):**
```bash
# Cache statistics
GET /api/system/cache-stats

# Clear cache
POST /api/system/cache-clear?exchange={exchange}&symbol={symbol}

# Circuit breaker status
GET /api/system/circuit-breakers

# Reset circuit breakers
POST /api/system/circuit-breakers/reset?exchange={exchange}

# Rate limiter statistics
GET /api/system/rate-limiters
```

### 🔧 Utilizzo

**Da Python:**
```python
from market_data.microstructure import get_microstructure_aggregator

# Ottieni aggregatore
aggregator = get_microstructure_aggregator()

# Analisi completa
context = await aggregator.get_full_context("BTC")

# Risultati
print(f"Bias: {context.overall_bias.value}")
print(f"Confidence: {context.bias_confidence:.0%}")
print(f"Warnings: {context.warnings}")
print(f"Recommendations: {context.recommendations}")

# Formato per LLM
prompt_context = context.to_prompt_context()
```

**Da API REST:**
```bash
# Analisi BTC completa
curl http://localhost:8000/api/microstructure/BTC

# Response include:
# - order_book: Aggregato da 4 exchange
# - liquidations: Dati Coinglass (se configurato)
# - funding: Funding rate aggregato
# - overall_bias: BULLISH/BEARISH/NEUTRAL
# - warnings: Alert critici
# - recommendations: Livelli chiave
```

### ⚙️ Configurazione

**Configurazione Base (Già Funzionante):**

Il sistema funziona **subito** con i provider gratuiti:
- ✅ 6 Exchange: Binance, Bybit, OKX, Coinbase, Crypto.com, KuCoin (API pubbliche)
- ✅ Order book aggregato con ~94% market coverage
- ✅ Funding rate
- ✅ Open interest
- ✅ Whale detection
- ✅ Circuit breaker, cache e rate limiting integrati

**Configurazione Opzionale - Coinglass (Liquidazioni):**

Per aggiungere dati di liquidazione aggregati:

1. **Registrati su Coinglass** (free tier: 30 req/min):
   - https://www.coinglass.com/pricing

2. **Aggiungi API key in `.env`:**
   ```bash
   # In backend/.env
   COINGLASS_API_KEY=your_coinglass_api_key_here
   ```

3. **Riavvia il backend**

**Senza Coinglass**: Il sistema funziona perfettamente, semplicemente il campo `liquidations` sarà `null` nelle response.

### 📈 Exchange Coverage

| Exchange | Order Book | Funding | Open Interest | Market Share |
|----------|-----------|---------|---------------|--------------|
| Binance | ✅ | ✅ | ✅ | 43% |
| OKX | ✅ | ✅ | ✅ | 18% |
| Bybit | ✅ | ✅ | ✅ | 15% |
| Coinbase | ✅ | ❌ (spot) | ❌ (spot) | 8% |
| Crypto.com | ✅ | ❌ (spot) | ❌ (spot) | 6% |
| KuCoin | ✅ | ✅ | ✅ | 4% |
| **Totale** | **~94% copertura mercato** | | | |

### 🧪 Test

```bash
cd backend

# Test order book providers
python3 -m unittest market_data.microstructure.test_microstructure.TestOrderBook -v

# Test aggregatore completo
python3 -m unittest market_data.microstructure.test_microstructure.TestMicrostructureAggregator -v

# Test Coinglass (se configurato)
python3 -m unittest market_data.microstructure.test_microstructure.TestCoinglass -v
```

### 📐 Architettura

```
backend/market_data/
├── exchanges/              # Provider esistenti ESTESI
│   ├── base_provider.py   # Base class con metodi microstructure
│   ├── binance.py         # + get_order_book(), get_open_interest()
│   ├── bybit.py           # + get_order_book()
│   ├── okx.py             # + get_order_book(), get_funding_rate()
│   ├── coinbase.py        # + get_order_book()
│   └── coinglass.py       # NUOVO - Liquidation data provider
│
└── microstructure/        # NUOVO - Aggregation layer
    ├── models.py          # Dataclasses (AggregatedOrderBook, etc.)
    ├── aggregator.py      # MicrostructureAggregator (riusa provider)
    └── __init__.py
```

### 💡 Design Principles

- **Zero Duplicazione**: Riusa completamente i provider esistenti
- **Graceful Degradation**: Funziona anche se alcuni provider sono offline
- **Modular**: Ogni componente è opzionale e indipendente
- **Extensible**: Facile aggiungere nuovi provider o metriche
- **LLM-Optimized**: Output formattato per AI reasoning

## Video di presentazione

Guarda la presentazione del progetto su YouTube:  
[https://www.youtube.com/watch?v=Vrl2Ar_SvSo&t=45s](https://www.youtube.com/watch?v=Vrl2Ar_SvSo&t=45s)

## Licenza

Questo progetto è distribuito sotto licenza MIT.

---

> Progetto avviato da Rizzo AI Academy
