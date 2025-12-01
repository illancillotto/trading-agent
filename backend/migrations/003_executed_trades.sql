-- Migration: Add executed_trades table for trade history tracking
-- Created: 2025-12-01
-- Description: Track actual trades executed on Hyperliquid with outcomes

-- Create executed_trades table
CREATE TABLE IF NOT EXISTS executed_trades (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Link to AI decision
    bot_operation_id    BIGINT REFERENCES bot_operations(id),

    -- Trade details
    trade_type          TEXT NOT NULL,  -- 'open' | 'close' | 'partial_close'
    symbol              TEXT NOT NULL,
    direction           TEXT NOT NULL,  -- 'long' | 'short'

    -- Execution details
    entry_price         NUMERIC(20, 8),
    exit_price          NUMERIC(20, 8),
    size                NUMERIC(20, 8) NOT NULL,
    size_usd            NUMERIC(20, 4),
    leverage            INTEGER,

    -- Risk management
    stop_loss_price     NUMERIC(20, 8),
    take_profit_price   NUMERIC(20, 8),

    -- Outcome (populated on close)
    exit_reason         TEXT,  -- 'take_profit' | 'stop_loss' | 'manual' | 'signal' | 'trend_reversal'
    pnl_usd             NUMERIC(20, 4),
    pnl_pct             NUMERIC(10, 4),
    duration_minutes    INTEGER,

    -- Hyperliquid reference
    hl_order_id         TEXT,
    hl_fill_price       NUMERIC(20, 8),

    -- Status
    status              TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'closed' | 'cancelled'
    closed_at           TIMESTAMPTZ,

    -- Metadata
    fees_usd            NUMERIC(10, 4),
    slippage_pct        NUMERIC(10, 4),
    raw_response        JSONB,

    -- Constraints
    CONSTRAINT valid_trade_type CHECK (trade_type IN ('open', 'close', 'partial_close')),
    CONSTRAINT valid_direction CHECK (direction IN ('long', 'short')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'closed', 'cancelled')),
    CONSTRAINT valid_exit_reason CHECK (
        exit_reason IS NULL OR
        exit_reason IN ('take_profit', 'stop_loss', 'manual', 'signal', 'trend_reversal', 'circuit_breaker')
    )
);

-- Indexes for frequent queries
CREATE INDEX idx_executed_trades_symbol ON executed_trades(symbol);
CREATE INDEX idx_executed_trades_status ON executed_trades(status);
CREATE INDEX idx_executed_trades_created_at ON executed_trades(created_at DESC);
CREATE INDEX idx_executed_trades_direction ON executed_trades(direction);
CREATE INDEX idx_executed_trades_bot_operation_id ON executed_trades(bot_operation_id);
CREATE INDEX idx_executed_trades_closed_at ON executed_trades(closed_at DESC) WHERE closed_at IS NOT NULL;

-- Composite index for common filters
CREATE INDEX idx_executed_trades_symbol_status ON executed_trades(symbol, status);
CREATE INDEX idx_executed_trades_symbol_created ON executed_trades(symbol, created_at DESC);

-- View for quick statistics
CREATE OR REPLACE VIEW trade_statistics AS
SELECT
    symbol,
    direction,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
    COUNT(*) FILTER (WHERE pnl_usd < 0) as losing_trades,
    COUNT(*) FILTER (WHERE pnl_usd = 0) as breakeven_trades,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pnl_usd > 0) / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(SUM(pnl_usd)::numeric, 2) as total_pnl,
    ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl,
    ROUND(MAX(pnl_usd)::numeric, 2) as best_trade,
    ROUND(MIN(pnl_usd)::numeric, 2) as worst_trade,
    ROUND(AVG(duration_minutes)::numeric, 0) as avg_duration_min,
    ROUND(AVG(pnl_pct)::numeric, 2) as avg_pnl_pct,
    ROUND(AVG(leverage)::numeric, 1) as avg_leverage
FROM executed_trades
WHERE status = 'closed' AND pnl_usd IS NOT NULL
GROUP BY symbol, direction
ORDER BY total_pnl DESC;

-- View for daily performance
CREATE OR REPLACE VIEW daily_trade_performance AS
SELECT
    DATE(created_at) as trade_date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pnl_usd > 0) / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(SUM(pnl_usd)::numeric, 2) as daily_pnl,
    ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl_per_trade,
    ROUND(SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END)::numeric, 2) as total_profit,
    ROUND(SUM(CASE WHEN pnl_usd < 0 THEN ABS(pnl_usd) ELSE 0 END)::numeric, 2) as total_loss,
    ROUND((SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) /
           NULLIF(SUM(CASE WHEN pnl_usd < 0 THEN ABS(pnl_usd) ELSE 0 END), 0))::numeric, 2) as profit_factor
FROM executed_trades
WHERE status = 'closed' AND pnl_usd IS NOT NULL
GROUP BY DATE(created_at)
ORDER BY trade_date DESC;

-- View for exit reason analysis
CREATE OR REPLACE VIEW exit_reason_statistics AS
SELECT
    exit_reason,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
    ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl,
    ROUND(SUM(pnl_usd)::numeric, 2) as total_pnl,
    COUNT(*) FILTER (WHERE pnl_usd > 0) as winners,
    COUNT(*) FILTER (WHERE pnl_usd < 0) as losers
FROM executed_trades
WHERE status = 'closed' AND exit_reason IS NOT NULL
GROUP BY exit_reason
ORDER BY count DESC;

-- Comment the table
COMMENT ON TABLE executed_trades IS 'Tracks all trades actually executed on Hyperliquid with their outcomes';
COMMENT ON COLUMN executed_trades.bot_operation_id IS 'References the AI decision that led to this trade';
COMMENT ON COLUMN executed_trades.trade_type IS 'Type of trade: open (new position), close (full close), partial_close';
COMMENT ON COLUMN executed_trades.pnl_usd IS 'Realized profit/loss in USD (only for closed trades)';
COMMENT ON COLUMN executed_trades.duration_minutes IS 'Trade duration from open to close in minutes';
COMMENT ON COLUMN executed_trades.hl_order_id IS 'Hyperliquid order ID for reference';
