# Trade History & LLM Optimization - Implementation Status

## ✅ Phase 1: Trade History Tracking (COMPLETED)

### 1. Database Schema ✅

**Migration File Created:** `migrations/003_executed_trades.sql`

**Table:** `executed_trades`
- Tracks actual trades executed on Hyperliquid
- Links to AI decisions via `bot_operation_id`
- Records entry/exit prices, P&L, duration
- Tracks stop loss/take profit levels
- Stores Hyperliquid order references

**Columns:**
- `id` - Primary key
- `created_at` - Trade open timestamp
- `bot_operation_id` - Link to AI decision
- `trade_type` - 'open', 'close', 'partial_close'
- `symbol`, `direction` - Trade details
- `entry_price`, `exit_price` - Execution prices
- `size`, `size_usd`, `leverage` - Position sizing
- `stop_loss_price`, `take_profit_price` - Risk management
- `exit_reason` - Why trade closed
- `pnl_usd`, `pnl_pct` - Realized profit/loss
- `duration_minutes` - Trade duration
- `hl_order_id`, `hl_fill_price` - Hyperliquid references
- `status` - 'open', 'closed', 'cancelled'
- `fees_usd`, `slippage_pct` - Execution costs

**Views Created:**
1. `trade_statistics` - Per-symbol win rate, avg P&L, etc.
2. `daily_trade_performance` - Daily aggregates
3. `exit_reason_statistics` - Analysis by exit reason

**Indexes:**
- Fast lookups by symbol, status, date
- Optimized for filtering and statistics queries

### 2. Database Functions ✅

**Added to `db_utils.py`:**

```python
log_executed_trade()      # Log when trade opens
close_trade()              # Log when trade closes
get_open_trades()          # Get all open trades
get_trade_by_symbol()      # Get specific trade
get_trade_statistics()     # Get performance stats
```

### 3. Migration Applied ✅

Database successfully updated with:
- ✅ `executed_trades` table
- ✅ All indexes
- ✅ 3 analytical views
- ✅ Constraints for data integrity

---

## ✅ Phase 2: Integration (COMPLETED)

### ✅ Integrated in `trading_engine.py`

**Changes Made:**

1. **Added `active_trades` to BotState** (line 134):
   - Dictionary mapping symbol → trade_id
   - Tracks which trades are currently open

2. **Trade Logging on OPEN** (lines 660-678):
   - Logs trade immediately after successful execution
   - Stores trade_id in `bot_state.active_trades[symbol]`
   - Links to bot_operation_id after operation is logged

3. **Trade Logging on CLOSE** (lines 680-707):
   - Logs closure with P&L, exit price, fees
   - Removes from `bot_state.active_trades`
   - Exit reason: "signal" for AI-driven closes

4. **SL/TP Trigger Handling** (lines 386-477):
   - Three closure paths: "skipped", "ok", "error"
   - Logs appropriate exit_reason: "stop_loss" or "take_profit"
   - Calculates P&L percentage from entry/exit prices
   - Fail-safe: continues execution even if logging fails

5. **Bot Operation Linking** (lines 734-748):
   - Updates executed_trade with bot_operation_id
   - Links AI decision to actual trade execution
   - Enables analysis of decision vs execution quality

---

## ⏳ Phase 3: API Endpoints (NEXT STEPS)

### TODO: Add to `main.py`

**Endpoint 1: Get Trade History**
```python
@app.get("/api/trades")
async def get_trades(
    page: int = 1,
    limit: int = 50,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    # Implementation provided in requirements
    pass
```

**Endpoint 2: Get Statistics**
```python
@app.get("/api/trades/stats")
async def get_trade_stats(
    symbol: Optional[str] = None,
    days: int = 30
):
    return db_utils.get_trade_statistics(symbol, days)
```

---

## ⏳ Phase 4: Frontend Component (NEXT STEPS)

### TODO: Create `TradeHistory.tsx`

**Features:**
- Trade table with filtering
- Statistics cards (win rate, P&L, etc.)
- Pagination
- Date range selection
- Symbol/direction filters

**Location:** `frontend/app/components/TradeHistory.tsx`

Full implementation provided in requirements document.

---

## ⏳ Phase 5: LLM Optimizations (FUTURE)

### Strategy 1: Batch Multi-Ticker (NOT IMPLEMENTED)

**Concept:** Single LLM call for all tickers instead of 3 separate calls
**Savings:** ~40-50% token reduction
**Effort:** Medium

### Strategy 2: Skip LLM on Poor Trend (READY TO IMPLEMENT)

**Concept:** Use Trend Confirmation to filter before calling LLM
**Savings:** ~30-40% (depends on market conditions)
**Effort:** Low (Trend Confirmation already integrated)

**Implementation:**
```python
# In trading_cycle(), before calling LLM
confirmation = bot_state.trend_engine.confirm_trend(ticker)

if not confirmation.should_trade:
    # Skip LLM call, log skip decision
    db_utils.log_bot_operation({
        "operation": "skip",
        "symbol": ticker,
        "reason": f"Trend quality: {confirmation.quality}",
        "confidence": 0.0
    })
    continue

# Only call LLM if trend is good
decision = previsione_trading_agent(...)
```

### Strategy 3: Two-Stage Decision (NOT IMPLEMENTED)

**Concept:** DeepSeek for pre-screening, GPT-4o for final decision
**Savings:** ~45-55%
**Effort:** Medium

### Strategy 4: Cache News/Sentiment (NOT IMPLEMENTED)

**Concept:** Cache news/sentiment for 30 minutes
**Savings:** ~10-15%
**Effort:** Low

---

## Current System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Cycle                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Coin Selection (Screener + Trend Filters)         │
│  2. Fetch Market Data                                  │
│  3. AI Decision (LLM)                                  │
│  4. Trend Confirmation ← Phase 2 of Trend System       │
│  5. Risk Management                                     │
│  6. Execute Trade                                       │
│                                                         │
│  7. ⭐ NEW: Log to executed_trades                     │
│     - If OPEN: log_executed_trade()                    │
│     - If CLOSE: close_trade()                          │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Database Schema                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  bot_operations          (AI decisions)                │
│       ↓                                                 │
│  executed_trades    ← ⭐ NEW (actual trades)          │
│                                                         │
│  Views:                                                 │
│  - trade_statistics                                     │
│  - daily_trade_performance                             │
│  - exit_reason_statistics                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Benefits

### Current (Phase 1 Complete)

✅ **Full Trade History**
- Track every trade from open to close
- Record actual execution prices vs AI decisions
- Measure P&L, duration, slippage

✅ **Performance Analytics**
- Win rate by symbol
- Average P&L per trade
- Best/worst trades
- Exit reason analysis

✅ **Debugging & Backtesting**
- Compare AI decisions vs actual execution
- Analyze which exit reasons work best
- Identify profitable patterns

### Future (When All Phases Complete)

📊 **Dashboard Integration**
- Visual trade history
- Performance charts
- Filter by date/symbol/direction

💰 **Cost Reduction**
- Skip LLM on poor trends: 30-40% savings
- Batch processing: 40-50% savings
- Combined: 60-75% savings

---

## Testing

### Test Trade Logging

```python
# Test opening a trade
trade_id = db_utils.log_executed_trade(
    bot_operation_id=123,
    trade_type="open",
    symbol="BTC",
    direction="long",
    size=0.5,
    entry_price=50000,
    leverage=5,
    stop_loss_price=49000,
    take_profit_price=52000
)

print(f"Trade logged with ID: {trade_id}")

# Test closing a trade
db_utils.close_trade(
    trade_id=trade_id,
    exit_price=51000,
    exit_reason="take_profit",
    pnl_usd=500,
    pnl_pct=2.0
)

# Get statistics
stats = db_utils.get_trade_statistics(days=30)
print(f"Win rate: {stats['win_rate']}%")
print(f"Total P&L: ${stats['total_pnl']}")
```

### Query Trade History

```sql
-- Recent trades
SELECT symbol, direction, entry_price, exit_price, pnl_usd, exit_reason
FROM executed_trades
WHERE status = 'closed'
ORDER BY created_at DESC
LIMIT 10;

-- Performance by symbol
SELECT * FROM trade_statistics ORDER BY total_pnl DESC;

-- Daily performance
SELECT * FROM daily_trade_performance ORDER BY trade_date DESC LIMIT 7;
```

---

## Files Modified/Created

### Created:
1. ✅ `migrations/003_executed_trades.sql` - Database schema
2. ⏳ `frontend/app/components/TradeHistory.tsx` - Frontend component (TODO)

### Modified:
1. ✅ `backend/db_utils.py` - Added 5 new functions (~200 lines)
2. ⏳ `backend/trading_engine.py` - Integration needed (TODO)
3. ⏳ `backend/main.py` - API endpoints needed (TODO)

---

## Next Immediate Steps

1. **Integrate trade logging in `trading_engine.py`**
   - Add `active_trades` dict to BotState
   - Call `log_executed_trade()` on opens
   - Call `close_trade()` on closes
   - Handle SL/TP triggers

2. **Test with paper trading**
   - Verify trades are logged correctly
   - Check P&L calculations
   - Validate duration tracking

3. **Add API endpoints**
   - GET /api/trades (with filters)
   - GET /api/trades/stats
   - Test with curl/Postman

4. **Create frontend component**
   - TradeHistory.tsx
   - Integrate in dashboard
   - Add charts for visualization

---

## Documentation

- Full specification: See original requirements document
- Database schema: `migrations/003_executed_trades.sql`
- API functions: `db_utils.py` lines 865-1087
- Implementation status: This document

**Status:** Phase 1 & 2 COMPLETE ✅
- ✅ Phase 1: Database schema and functions
- ✅ Phase 2: Integration in trading_engine.py
**Next:** Phase 3 (API Endpoints) - Ready to implement
**Timeline:** ~1-2 hours for API + testing
