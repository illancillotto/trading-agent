"""
Test script for trade logging functionality
Tests the integration of executed_trades table with trading_engine.py
"""
import logging
import db_utils

logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def test_trade_logging():
    """Test basic trade logging workflow"""

    logger.info("=" * 60)
    logger.info("Testing Trade Logging Functionality")
    logger.info("=" * 60)

    # Test 1: Log an open trade
    logger.info("\n[Test 1] Logging OPEN trade...")
    try:
        trade_id = db_utils.log_executed_trade(
            bot_operation_id=None,  # Will be updated later
            trade_type="open",
            symbol="BTC",
            direction="long",
            size=0.1,
            entry_price=50000.0,
            leverage=5,
            stop_loss_price=49000.0,
            take_profit_price=52000.0,
            hl_order_id="test_order_123",
            hl_fill_price=50000.0,
            size_usd=5000.0
        )
        logger.info(f"✅ Trade logged successfully (ID: {trade_id})")
    except Exception as e:
        logger.error(f"❌ Failed to log trade: {e}")
        return False

    # Test 2: Get open trades
    logger.info("\n[Test 2] Getting open trades...")
    try:
        open_trades = db_utils.get_open_trades()
        logger.info(f"✅ Found {len(open_trades)} open trades")
        for trade in open_trades:
            logger.info(f"   - {trade['symbol']} {trade['direction']} @ ${trade['entry_price']}")
    except Exception as e:
        logger.error(f"❌ Failed to get open trades: {e}")
        return False

    # Test 3: Get trade by symbol
    logger.info("\n[Test 3] Getting trade by symbol...")
    try:
        btc_trade = db_utils.get_trade_by_symbol("BTC", status="open")
        if btc_trade:
            logger.info(f"✅ Found BTC trade: ID {btc_trade['id']}, Entry ${btc_trade['entry_price']}")
        else:
            logger.warning("⚠️ No BTC trade found")
    except Exception as e:
        logger.error(f"❌ Failed to get trade by symbol: {e}")
        return False

    # Test 4: Close the trade
    logger.info("\n[Test 4] Closing trade...")
    try:
        exit_price = 51000.0
        entry_price = 50000.0
        size = 0.1
        pnl_usd = (exit_price - entry_price) * size
        pnl_pct = (exit_price - entry_price) / entry_price * 100

        db_utils.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_reason="take_profit",
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            fees_usd=5.0
        )
        logger.info(f"✅ Trade closed successfully")
        logger.info(f"   P&L: ${pnl_usd:.2f} ({pnl_pct:.2f}%)")
    except Exception as e:
        logger.error(f"❌ Failed to close trade: {e}")
        return False

    # Test 5: Get trade statistics
    logger.info("\n[Test 5] Getting trade statistics...")
    try:
        stats = db_utils.get_trade_statistics(days=30)
        logger.info(f"✅ Trade statistics retrieved:")
        logger.info(f"   Total trades: {stats.get('total_trades', 0)}")
        logger.info(f"   Win rate: {stats.get('win_rate', 0):.1f}%")
        logger.info(f"   Total P&L: ${stats.get('total_pnl', 0):.2f}")
        logger.info(f"   Average P&L: ${stats.get('avg_pnl', 0):.2f}")
        logger.info(f"   Best trade: ${stats.get('best_trade', 0):.2f}")
        logger.info(f"   Worst trade: ${stats.get('worst_trade', 0):.2f}")
    except Exception as e:
        logger.error(f"❌ Failed to get statistics: {e}")
        return False

    # Test 6: Query database views
    logger.info("\n[Test 6] Querying analytical views...")
    try:
        with db_utils.get_connection() as conn:
            with conn.cursor() as cur:
                # Trade statistics view
                cur.execute("SELECT * FROM trade_statistics LIMIT 5")
                stats_view = cur.fetchall()
                logger.info(f"✅ Trade statistics view: {len(stats_view)} rows")

                # Daily performance view
                cur.execute("SELECT * FROM daily_trade_performance LIMIT 5")
                daily_view = cur.fetchall()
                logger.info(f"✅ Daily performance view: {len(daily_view)} rows")

                # Exit reason statistics view
                cur.execute("SELECT * FROM exit_reason_statistics")
                exit_stats = cur.fetchall()
                logger.info(f"✅ Exit reason statistics: {len(exit_stats)} rows")

                if exit_stats:
                    logger.info("   Exit reasons:")
                    for row in exit_stats:
                        logger.info(f"   - {row[0]}: {row[1]} trades ({row[2]:.1f}%)")
    except Exception as e:
        logger.error(f"❌ Failed to query views: {e}")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("✅ All tests passed!")
    logger.info("=" * 60)
    return True

if __name__ == "__main__":
    success = test_trade_logging()
    if not success:
        logger.error("\n❌ Some tests failed. Check the logs above.")
        exit(1)
    else:
        logger.info("\n✅ Trade logging integration is working correctly!")
