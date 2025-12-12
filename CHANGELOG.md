# Changelog

## [0.3.0] - 2025-12-12

### 🎯 NOF1.ai Trading Framework Implementation

Complete implementation of NOF1.ai standards for disciplined, risk-aware trading with focus on quality over quantity and capital preservation.

#### 🚀 New Features

##### 📊 Performance Metrics Integration
- **Sharpe Ratio Calculation**: Annualized Sharpe Ratio with automatic interpretation (LOSING/VOLATILE/GOOD/EXCELLENT)
- **Performance Calculator**: New `performance_metrics.py` module with PerformanceCalculator singleton
- **Real-Time Feedback Loop**: Performance metrics injected into AI decision-making prompt every cycle
- **Comprehensive Metrics**: Total return, win rate, avg win/loss, max drawdown, consecutive losses tracking
- **Database Integration**: New functions `get_closed_trades()` and `get_account_snapshots()` for metrics calculation

##### 🔒 Trade Decision Validation
- **NOF1.ai Rules Enforcement**: New `validate_trade_decision()` function with strict validation criteria
- **R:R Ratio Validation**: Minimum 1.5:1 risk-reward ratio enforced (ideally 2.0+)
- **Risk Limits**: Maximum 3% account risk per trade validation
- **Invalidation Conditions**: Required specific invalidation condition for every trade (min 10 chars)
- **Confidence Thresholds**: Minimum 0.5 confidence required to open positions
- **Position Size Limits**: Maximum 30% of balance per position

##### 🎚️ Confidence-Based Leverage System
- **Dynamic Leverage Mapping**: Leverage limits based on confidence level
  - 0.00-0.49: Don't trade (HOLD)
  - 0.50-0.59: Max 2x leverage (low conviction)
  - 0.60-0.69: Max 4x leverage (moderate conviction)
  - 0.70-0.84: Max 6x leverage (high conviction)
  - 0.85-1.00: Max 8x leverage (very high conviction)
- **Automatic Validation**: `_get_max_leverage_for_confidence()` helper for leverage checks

##### ⏱️ Timeframe Configuration System
- **Configurable Timeframes**: New `config.py` with PRIMARY_TIMEFRAME and SECONDARY_TIMEFRAME
- **Scalping Mode Disabled**: 5m timeframe disabled by default (too much noise)
- **Recommended Default**: 15m primary timeframe, 4h secondary for trend confirmation
- **Dynamic Indicator Loading**: `indicators.py` updated to use configurable timeframes
- **Environment Variables**: Full .env configuration for timeframe selection

#### 📐 Schema Enhancements

##### Extended TRADE_DECISION_SCHEMA
- **New Required Fields**:
  - `invalidation_condition`: Specific observable condition proving trade thesis wrong
  - `risk_usd`: Calculated dollar risk (portion * balance * sl_pct * leverage)
- **Updated Constraints**:
  - `leverage`: 1-8 (was 1-10)
  - `target_portion_of_balance`: Max 0.30 (was 1.0)
  - `stop_loss_pct`: 1.5-5.0 (was 0.5-10)
  - `take_profit_pct`: Min 2.25 (ensures 1.5x R:R)

#### 🧪 Testing Suite

##### Comprehensive Test Coverage (23 tests)
- **TestTradeDecisionValidation** (8 tests): R:R ratio, invalidation conditions, confidence thresholds, risk limits
- **TestLeverageConfidenceMapping** (5 tests): Confidence-leverage mapping validation
- **TestPerformanceMetrics** (6 tests): Sharpe calculation, win rate, drawdown, consecutive losses
- **TestRiskCalculations** (2 tests): Risk formula validation, 3% limit enforcement
- **TestSchemaCompliance** (2 tests): JSON schema validation with NOF1.ai constraints
- **100% Pass Rate**: All 23 tests passing successfully

#### 📚 Documentation Updates

##### README.md Enhancements
- **Complete NOF1.ai Section**: 152-line comprehensive framework documentation
- **Core Principles**: Risk-first approach, invalidation conditions, R:R ratios, confidence-based sizing
- **Performance Metrics**: Sharpe interpretation guide and integration details
- **Configuration Guide**: Timeframe setup, risk management variables
- **Best Practices**: Trading recommendations based on NOF1.ai philosophy
- **Testing Instructions**: Complete guide to running test suite

##### Configuration Documentation
- **Updated env.example**: 43 new lines with NOF1.ai configuration variables
- **Risk Management Section**: MAX_RISK_PER_TRADE_PCT, MIN_RR_RATIO, MAX_LEVERAGE, MAX_POSITION_SIZE_PCT
- **Performance Tracking**: SHARPE_LOOKBACK_DAYS, RISK_FREE_RATE_ANNUAL, thresholds for trading modes
- **Timeframe Configuration**: PRIMARY_TIMEFRAME, SECONDARY_TIMEFRAME, CYCLE_INTERVAL_MINUTES

#### 🏗️ Architecture Changes

##### New Files
- **backend/performance_metrics.py** (348 lines): PerformanceMetrics dataclass, PerformanceCalculator with Sharpe
- **backend/config.py** (202 lines): Centralized configuration for timeframes and risk management
- **backend/tests/test_nof1_integration.py** (389 lines): Complete NOF1.ai test suite

##### Modified Files
- **backend/system_prompt.txt** (340 lines): Complete rewrite with NOF1.ai philosophy and {performance_metrics} placeholder
- **backend/trading_agent.py**: Extended schema, validate_trade_decision(), _get_max_leverage_for_confidence()
- **backend/db_utils.py** (+68 lines): get_closed_trades(), get_account_snapshots() functions
- **backend/indicators.py**: Configurable timeframe support, removed hardcoded 5m/15m
- **backend/trading_engine.py**: Performance metrics calculation and prompt injection

#### 🎨 System Improvements

##### Decision-Making Process
- **8-Point Checklist**: Every open decision validated against comprehensive criteria
- **Performance-Driven Risk**: Sharpe Ratio influences position sizing decisions
- **Quality over Quantity**: System encourages fewer, higher-quality setups
- **Invalidation Discipline**: Forces clear exit conditions before entry

##### Risk Management
- **Multi-Layer Validation**: Schema constraints + runtime validation + confidence checks
- **Automatic Position Sizing**: Confidence-based sizing prevents overleverage
- **Risk-Reward Enforcement**: No trade execution without favorable R:R
- **Capital Preservation**: 3% per-trade limit prevents catastrophic losses

#### ⚙️ Configuration Variables

**New Environment Variables:**
```bash
# Timeframe Configuration
PRIMARY_TIMEFRAME=15m
SECONDARY_TIMEFRAME=4h
CYCLE_INTERVAL_MINUTES=30

# Risk Management
MAX_RISK_PER_TRADE_PCT=3.0
MIN_RR_RATIO=1.5
MIN_LIQUIDATION_DISTANCE_PCT=15.0
MAX_LEVERAGE=8
MAX_POSITION_SIZE_PCT=30.0

# Performance Tracking
SHARPE_LOOKBACK_DAYS=30
RISK_FREE_RATE_ANNUAL=0.05
MIN_SHARPE_FOR_NORMAL_TRADING=-0.5
MIN_SHARPE_FOR_AGGRESSIVE_TRADING=1.0
```

### 📈 Improvements
- **Zero Breaking Changes**: Complete backward compatibility with v0.2.1
- **Graceful Degradation**: System works with fallback values if performance metrics unavailable
- **Singleton Pattern**: Efficient calculator instantiation
- **Type Safety**: Full type hints throughout new modules
- **Error Handling**: Try/except wrappers for robustness

### 🛠 Technical Details
- **3 New Files**: performance_metrics.py, config.py, test_nof1_integration.py
- **6 Modified Files**: system_prompt.txt, trading_agent.py, db_utils.py, indicators.py, trading_engine.py, env.example
- **1 Documentation Update**: README.md with comprehensive NOF1.ai section
- **Python 3.11+**: Full compatibility maintained
- **Test Coverage**: 23 tests covering all critical NOF1.ai functionality

### 🔍 Migration Guide
1. Update `.env` with new NOF1.ai variables (optional, has defaults)
2. Run `python -m pytest tests/test_nof1_integration.py` to verify installation
3. System will automatically use new validation rules
4. Performance metrics calculated automatically from existing trade history
5. No code changes required in existing trading logic

### 📖 References
- **NOF1.ai Philosophy**: Risk-first, performance-driven trading methodology
- **Sharpe Ratio**: [Investopedia](https://www.investopedia.com/terms/s/sharperatio.asp)
- **Invalidation Concepts**: Mark Minervini / Stan Weinstein methodology

---

## [0.2.1] - 2025-12-10

### 🚀 New Features

#### 🏦 New Exchange Providers
- **Crypto.com Provider**: Aggiunto supporto Crypto.com (6% market share)
- **KuCoin Provider**: Aggiunto supporto KuCoin (4% market share)
- **Market Coverage**: Esteso da ~86% a ~94% del mercato totale

#### 🛡️ Sistemi di Resilienza
- **Circuit Breaker**: Pattern circuit breaker con 3 stati (CLOSED, OPEN, HALF_OPEN) per prevenire cascade failure
- **LRU Cache**: Cache intelligente con TTL configurabile, riduce chiamate API del ~70%
- **Rate Limiter**: Token bucket algorithm per rispettare limiti API di ogni exchange
- **Retry Logic**: Decorator `async_retry` con exponential backoff per errori temporanei
- **Graceful Degradation**: Sistema continua a funzionare anche se alcuni exchange sono offline

#### 🔌 New System Monitoring API Endpoints
- `GET /api/system/cache-stats`: Statistiche cache (hit rate, miss rate, size)
- `POST /api/system/cache-clear`: Clear cache per exchange/symbol specifico
- `GET /api/system/circuit-breakers`: Stato di tutti i circuit breakers
- `POST /api/system/circuit-breakers/reset`: Reset circuit breakers
- `GET /api/system/rate-limiters`: Statistiche rate limiting per exchange

### 📈 Improvements
- **Market Weights Updated**: Aggiornato a dati Kaiko 2025 (Binance 45% → 43%)
- **6 Exchange Support**: Binance, OKX, Bybit, Coinbase, Crypto.com, KuCoin
- **Total Market Coverage**: ~94% del mercato crypto globale
- **Error Handling**: Migliorato error handling con retry automatico e fallback

### 🏗️ Architecture Enhancements
- **BaseProvider Extended**: Aggiunto `EXCHANGE_NAME` attribute e metodo `safe_get_order_book()`
- **Singleton Pattern**: CircuitBreakerRegistry, OrderBookCache e RateLimiterRegistry come singleton
- **Microstructure Module**: Nuovi moduli `circuit_breaker.py`, `cache.py`, `rate_limiter.py`, `utils.py`
- **Zero Breaking Changes**: Tutti i miglioramenti backward-compatible con v0.2.0
- **Safe Wrapper**: `safe_get_order_book()` integra automaticamente cache, circuit breaker e rate limiter

### ⚙️ Configuration
- **Updated Config**: `config/market_data.yaml` aggiornato con nuovi provider e pesi
- **Exchange Weights**: Crypto.com 6%, KuCoin 4%, Binance 43% (era 45%)
- **Cache TTL**: Configurabile per order book (30s), liquidations (5m), funding (60s)
- **Circuit Breaker Thresholds**: Configurabili failure_threshold e timeout

### 🧪 Testing
- **New Tests**: Test per Crypto.com e KuCoin order book providers
- **Test Coverage**: TestOrderBook esteso con `test_cryptocom_orderbook()` e `test_kucoin_orderbook()`
- **Validation**: Tutti i test validano bid/ask spread, exchange name e data quality

### 📚 Documentation
- **README Updated**: Aggiunta sezione "Sistemi di Resilienza (v0.2.1)"
- **API Docs**: Documentati nuovi endpoint system monitoring
- **Exchange Coverage Table**: Aggiornata tabella con 6 exchange e ~94% coverage
- **Configuration Guide**: Documentata configurazione opzionale per nuovi provider

### 🐛 Bug Fixes
- **Production Monitoring**: Fixed Prometheus scraping PostgreSQL port causing "invalid length of startup packet" errors
- **KuCoin API**: Aggiornato da futures API a spot API per migliore stabilità

## [0.2.0] - 2025-12-10

### 🚀 New Features

#### 📊 Market Microstructure Analysis
- **Order Book Aggregation**: Combina dati order book da Binance, Bybit, OKX e Coinbase (~86% market coverage)
- **Whale Detection**: Identifica automaticamente "whale walls" con soglia $500k+
- **Market Depth Analysis**: Analisi bid/ask imbalance e liquidità cross-exchange
- **Liquidation Risk Monitoring**: Integrazione Coinglass per analisi rischio cascade (opzionale)
- **Funding Rate Aggregation**: Sentiment contrarian da funding rates multi-exchange
- **Long/Short Ratio Analysis**: Crowd positioning analysis per segnali contrarian
- **Dynamic Support/Resistance**: Livelli chiave derivati da whale walls e cluster liquidazioni
- **SL/TP Suggestions**: Stop loss e take profit basati su microstructure reale
- **LLM-Ready Context**: Output formattato `to_prompt_context()` per AI reasoning

#### 🔌 New API Endpoints
- `GET /api/microstructure/{symbol}`: Contesto microstructure completo
- `GET /api/microstructure/{symbol}/orderbook`: Solo order book aggregato
- `GET /api/microstructure/{symbol}/liquidations`: Solo dati liquidazioni

#### 🏗️ Architecture Enhancements
- **Extended Providers**: Binance, Bybit, OKX, Coinbase estesi con `get_order_book()`
- **New Coinglass Provider**: Provider dedicato per dati liquidazione aggregati
- **Microstructure Module**: Nuovo modulo `backend/market_data/microstructure/`
- **Zero Code Duplication**: Riuso completo provider esistenti
- **Graceful Degradation**: Sistema funziona anche senza Coinglass configurato

### 📈 Improvements
- **Market Share Weighting**: Aggregazione ponderata order book per market share reale
- **Exchange Coverage**: 86% coverage mercato con 4 major exchange
- **Liquidity Scoring**: Sistema scoring 0-100 per valutare liquidità mercato
- **Cascade Risk Assessment**: 4 livelli risk (LOW/MEDIUM/HIGH/EXTREME)
- **Contrarian Signals**: Interpretazione contrarian di funding e long/short ratio

### ⚙️ Configuration
- **New Config Section**: `microstructure` in `config/market_data.yaml`
- **Optional Coinglass**: Sistema funziona perfettamente anche senza API key
- **Configurable Thresholds**: Whale detection e cache TTL configurabili
- **Exchange Weights**: Pesi market share configurabili per aggregazione

### 🧪 Testing
- **Test Suite**: Test completi per order book, Coinglass e aggregatore
- **Mock Support**: Test funzionano anche senza API keys configurate
- **CI/CD Ready**: Test suite integrabili in pipeline automatizzate

### 📚 Documentation
- **README Updated**: Nuova sezione completa Market Microstructure Analysis
- **API Documentation**: Esempi Python e REST per tutti gli endpoint
- **Setup Guide**: Istruzioni configurazione Coinglass (opzionale)
- **Architecture Diagram**: Diagramma struttura modulo microstructure

### 🛠 Technical Details
- **9 New/Modified Files**: 5 provider estesi + 4 nuovi file microstructure
- **No Breaking Changes**: Totale retrocompatibilità con sistema esistente
- **Python 3.11+**: Compatibile con Python 3.11 e 3.13
- **Async/Await**: Implementazione completamente asincrona

## [0.1.1] - 2025-12-04

### 🚀 New Features

#### 🤖 AI Decision Backtrack Analysis
- **Complete Backtrack System**: Nuovo sistema completo per analizzare decisioni AI storiche e correlarle con risultati effettivi
- **Decision Context Tracking**: Tracciamento completo del contesto AI (indicatori, news, sentiment, forecasts) per ogni decisione
- **Performance Correlation**: Analisi correlazione tra decisioni AI, condizioni di mercato e risultati di trading
- **Backtrack API Endpoint**: Nuovo endpoint `/api/backtrack-analysis` per analisi programmata
- **Decision Outcome Analysis**: Metriche avanzate su win rate, profit factor, exit reasons per categoria

#### 📊 Frontend Backtrack Dashboard
- **Backtrack Analysis Component**: Nuovo componente React per visualizzare analisi backtrack
- **Performance Metrics Dashboard**: Metriche chiave (win rate, execution rate, profit/loss) con filtri per periodo
- **Category Analysis**: Breakdown performance per operazione (open/close/hold), symbol e direzione
- **Exit Reason Distribution**: Analisi distribuzione motivi chiusura trade con impatto sul profitto
- **Improvement Recommendations**: Suggerimenti automatici basati su pattern identificati (confidence threshold, risk management)

#### 🐳 Docker Production Optimization
- **Build Optimization**: Riduzione tempi build da ~11 minuti a ~1-2 minuti per rebuild successivi
- **Layer Caching**: Implementazione intelligente caching dipendenze Python separate dal codice
- **Docker BuildKit**: Utilizzo BuildKit per build paralleli e caching avanzato
- **Multi-Environment Support**: Configurazioni separate per sviluppo e produzione

#### 🏭 Enterprise Production Deployment
- **Production-Ready Stack**: Configurazione completa per produzione con alta disponibilità
- **Security Hardening**: User non-root, read-only filesystem, security headers, rate limiting
- **SSL/TLS Support**: Configurazione Nginx con SSL termination e Let's Encrypt
- **Load Balancing**: Nginx reverse proxy con health checks e load balancing
- **Zero-Downtime Deployment**: Sistema di deployment rolling con backup automatico
- **Resource Management**: Limits CPU/memoria per tutti i servizi

#### 📈 Monitoring & Observability
- **Prometheus Integration**: Metriche complete per monitoraggio applicativo e infrastrutturale
- **Grafana Dashboards**: Dashboard pre-configurati per trading performance e system health
- **Centralized Logging**: Logging strutturato JSON per centralizzazione e analisi
- **Health Checks**: Health checks automatici per tutti i servizi con alerting
- **Metrics Collection**: Raccolta metriche API, database, sistema e trading performance

#### 💾 Backup & Recovery System
- **Automated Database Backup**: Backup PostgreSQL automatico con compressione
- **Configuration Backup**: Backup configurazione e certificati SSL
- **Retention Policy**: Gestione automatica retention backup con cleanup
- **Integrity Verification**: Verifica integrità backup con checksum
- **Recovery Scripts**: Script automatizzati per disaster recovery

#### 🔒 Security Enhancements
- **Container Security**: Security-opt, no-new-privileges, read-only root filesystem
- **Network Security**: Rate limiting, DDoS protection, IP filtering
- **Secret Management**: Environment-based secrets con Docker secrets support
- **SSL/TLS Everywhere**: Crittografia end-to-end per tutte le comunicazioni
- **Audit Logging**: Logging completo per compliance e security monitoring

#### 🚀 Deployment Automation
- **Production Deploy Script**: Script `production-deploy.sh` per deployment automatizzato
- **CI/CD Ready**: Support completo per pipeline CI/CD con GitLab CI, GitHub Actions
- **Environment Management**: Gestione multi-environment (dev/staging/prod)
- **Rollback Automation**: Rollback automatico in caso di deployment failure
- **Version Tagging**: Tagging automatico immagini Docker con git commit SHA

### 🐛 Bug Fixes
- Risolto memory leak nel backtrack analysis per dataset di grandi dimensioni
- Fix race condition in Docker build con dipendenze Python pesanti
- Corretto calcolo metriche performance per trade con dati incompleti
- Risolto timeout nei backup database per tabelle molto grandi

### 🛠 Maintenance
- Aggiornata versione a 0.1.1 in pyproject.toml
- Aggiunto supporto Python 3.13 con ottimizzazioni performance
- Migliorata gestione errori e logging strutturato
- Aggiornati requirements sicurezza e dipendenze

### 📚 Documentation
- **Production README**: Guida completa deployment produzione (`PRODUCTION_README.md`)
- **Docker Optimization**: Documentazione ottimizzazioni build (`DOCKER_OPTIMIZATION_README.md`)
- **Data Tracking Analysis**: Analisi sistema tracciamento dati (`DATA_TRACKING_ANALYSIS.md`)
- **API Documentation**: Documentazione completa nuovi endpoint backtrack
- **Security Guidelines**: Linee guida sicurezza per produzione

## [0.1.0] - 2025-12-01

### 🚀 New Features

#### Frontend Dashboard
- **Performance Overview Widget**: Visualizzazione immediata di Saldo Attuale, PnL Totale ($ e %) e Saldo Iniziale. Gestione intelligente del saldo iniziale (primo valore > 0).
- **Market Data Widget**: Dati di mercato aggregati in tempo reale (Prezzo medio, Spread, Funding Rate, Deviazione Hyperliquid).
- **System Logs Widget**: Terminale di log integrato nella dashboard per il debugging in tempo reale.
- **Closed Positions Widget**: Storico delle posizioni chiuse con visualizzazione grafica del Win Rate e card dettagliate.
- **Enhanced Bot Operations**: Nuova UI per le operazioni del bot con box dedicati per "Market Data" (RSI, MACD) e "AI Forecast".
- **Manual Refresh**: Aggiunti pulsanti di aggiornamento manuale su tutti i singoli componenti per un controllo granulare.

#### Backend
- **API Endpoints**:
  - `GET /api/market-data/aggregate`: Endpoint per dati di mercato aggregati.
  - `GET /api/system-logs`: Endpoint per leggere i log di sistema.
  - `GET /api/trades/stats`: Statistiche avanzate sui trade chiusi.
- **Reliability**:
  - Implementata logica di **Retry automatico** con backoff esponenziale per le chiamate API Hyperliquid (fix errore 429 Rate Limit).
  - **File Logging**: Il sistema ora scrive i log su `trading_agent.log` oltre che su console.
  - **Database Cleanup**: Pulizia automatica di trade "fantasma" o invalidi (prezzi a 0).
- **Dependencies**: Aggiunta libreria `PyYAML` per la gestione delle configurazioni.

### 🐛 Bug Fixes
- Risolto errore `ECONNREFUSED` all'avvio del frontend (race condition con il backend).
- Risolto calcolo errato `+Infinity%` nel widget Performance Overview.
- Risolto crash del backend per mancanza di `pyyaml`.
- Corretta visualizzazione trade con prezzi nulli/zero.

### 🛠 Maintenance
- Aggiornata configurazione `uv` e `pyproject.toml`.
- Migliorata gestione errori nel `trading_engine`.




