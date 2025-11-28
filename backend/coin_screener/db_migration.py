"""
Database migration for coin screener tables
"""

SCREENING_TABLES_SQL = """
-- Coin screening results
CREATE TABLE IF NOT EXISTS coin_screenings (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    screening_type TEXT NOT NULL,  -- 'full_rebalance' or 'daily_update'
    selected_coins JSONB NOT NULL,
    excluded_coins JSONB,
    raw_scores JSONB,
    next_rebalance TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_coin_screenings_created_at
    ON coin_screenings(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coin_screenings_type
    ON coin_screenings(screening_type);

-- Historical coin scores
CREATE TABLE IF NOT EXISTS coin_scores_history (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    screening_id BIGINT REFERENCES coin_screenings(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    score NUMERIC(5, 2),
    rank INTEGER,
    factors JSONB,
    metrics JSONB
);

CREATE INDEX IF NOT EXISTS idx_coin_scores_history_symbol
    ON coin_scores_history(symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coin_scores_history_screening
    ON coin_scores_history(screening_id);

CREATE INDEX IF NOT EXISTS idx_coin_scores_history_created_at
    ON coin_scores_history(created_at DESC);

-- Coin metrics snapshots (for debugging and analysis)
CREATE TABLE IF NOT EXISTS coin_metrics_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    price NUMERIC(30, 10),
    volume_24h_usd NUMERIC(30, 10),
    market_cap_usd NUMERIC(30, 10),
    open_interest_usd NUMERIC(30, 10),
    funding_rate NUMERIC(20, 10),
    spread_pct NUMERIC(10, 6),
    days_listed INTEGER,
    raw_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_coin_metrics_snapshots_symbol
    ON coin_metrics_snapshots(symbol, created_at DESC);
"""


def run_migration(conn):
    """
    Run the database migration.

    Args:
        conn: psycopg2 connection object
    """
    with conn.cursor() as cur:
        cur.execute(SCREENING_TABLES_SQL)
    conn.commit()
    print("✅ Coin screener tables created successfully")


if __name__ == "__main__":
    # Can be run standalone
    import sys
    sys.path.append('..')

    from db_utils import get_connection

    with get_connection() as conn:
        run_migration(conn)
