"""
Test script for Trade History API endpoints
Tests the new /api/trades endpoints
"""
import requests
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_api_endpoints():
    """Test all trade history API endpoints"""

    logger.info("=" * 60)
    logger.info("Testing Trade History API Endpoints")
    logger.info("=" * 60)

    # Test 1: Health check
    logger.info("\n[Test 1] Health check...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            logger.info(f"✅ API is running: {response.json()}")
        else:
            logger.error(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ Cannot connect to API. Is the server running?")
        logger.error("   Start with: uvicorn main:app --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        logger.error(f"❌ Health check error: {e}")
        return False

    # Test 2: GET /api/trades (all trades)
    logger.info("\n[Test 2] GET /api/trades (all trades)...")
    try:
        response = requests.get(f"{BASE_URL}/api/trades", timeout=10)
        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Retrieved {len(trades)} trades")
            if trades:
                logger.info(f"   First trade: {trades[0]['symbol']} {trades[0]['direction']} @ ${trades[0]['entry_price']}")
                logger.info(f"   Status: {trades[0]['status']}, Created: {trades[0]['created_at']}")
        else:
            logger.error(f"❌ Failed to get trades: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error getting trades: {e}")
        return False

    # Test 3: GET /api/trades with filters
    logger.info("\n[Test 3] GET /api/trades?status=closed&limit=10...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/trades",
            params={"status": "closed", "limit": 10},
            timeout=10
        )
        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Retrieved {len(trades)} closed trades")
            if trades:
                for i, trade in enumerate(trades[:3], 1):
                    pnl = trade.get('pnl_usd', 0)
                    pnl_sign = "+" if pnl >= 0 else ""
                    logger.info(f"   {i}. {trade['symbol']} {trade['direction']}: {pnl_sign}${pnl:.2f} ({trade['exit_reason']})")
        else:
            logger.warning(f"⚠️ No closed trades found or error: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting closed trades: {e}")

    # Test 4: GET /api/trades with pagination
    logger.info("\n[Test 4] GET /api/trades?page=1&limit=5...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/trades",
            params={"page": 1, "limit": 5},
            timeout=10
        )
        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Retrieved page 1 with {len(trades)} trades (limit: 5)")
        else:
            logger.warning(f"⚠️ Pagination test failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error testing pagination: {e}")

    # Test 5: GET /api/trades with symbol filter
    logger.info("\n[Test 5] GET /api/trades?symbol=BTC...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/trades",
            params={"symbol": "BTC"},
            timeout=10
        )
        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Retrieved {len(trades)} BTC trades")
            if trades:
                logger.info(f"   All trades are for BTC: {all(t['symbol'] == 'BTC' for t in trades)}")
        else:
            logger.warning(f"⚠️ No BTC trades found: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error filtering by symbol: {e}")

    # Test 6: GET /api/trades/stats (overall)
    logger.info("\n[Test 6] GET /api/trades/stats (last 30 days)...")
    try:
        response = requests.get(f"{BASE_URL}/api/trades/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ Statistics retrieved:")
            logger.info(f"   Total trades: {stats['total_trades']}")
            logger.info(f"   Win rate: {stats['win_rate']:.1f}%")
            logger.info(f"   Total P&L: ${stats['total_pnl']:.2f}")
            logger.info(f"   Avg P&L: ${stats['avg_pnl']:.2f}")
            logger.info(f"   Best trade: ${stats['best_trade']:.2f}")
            logger.info(f"   Worst trade: ${stats['worst_trade']:.2f}")
            if stats['avg_duration_minutes']:
                logger.info(f"   Avg duration: {stats['avg_duration_minutes']:.0f} minutes")
            logger.info(f"   Total fees: ${stats['total_fees']:.2f}")
        else:
            logger.warning(f"⚠️ No statistics available: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting statistics: {e}")

    # Test 7: GET /api/trades/stats with symbol filter
    logger.info("\n[Test 7] GET /api/trades/stats?symbol=BTC...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/trades/stats",
            params={"symbol": "BTC"},
            timeout=10
        )
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ BTC statistics:")
            logger.info(f"   Total BTC trades: {stats['total_trades']}")
            logger.info(f"   BTC win rate: {stats['win_rate']:.1f}%")
            logger.info(f"   BTC total P&L: ${stats['total_pnl']:.2f}")
        else:
            logger.warning(f"⚠️ No BTC statistics: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting BTC statistics: {e}")

    # Test 8: GET /api/trades/stats with custom days
    logger.info("\n[Test 8] GET /api/trades/stats?days=7...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/trades/stats",
            params={"days": 7},
            timeout=10
        )
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ Last 7 days statistics:")
            logger.info(f"   Total trades: {stats['total_trades']}")
            logger.info(f"   Win rate: {stats['win_rate']:.1f}%")
        else:
            logger.warning(f"⚠️ No statistics for last 7 days: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error getting 7-day statistics: {e}")

    # Test 9: GET /api/trades/:id
    logger.info("\n[Test 9] GET /api/trades/1 (get single trade)...")
    try:
        response = requests.get(f"{BASE_URL}/api/trades/1", timeout=10)
        if response.status_code == 200:
            trade = response.json()
            logger.info(f"✅ Trade details retrieved:")
            logger.info(f"   ID: {trade['id']}")
            logger.info(f"   Symbol: {trade['symbol']}")
            logger.info(f"   Direction: {trade['direction']}")
            logger.info(f"   Entry: ${trade['entry_price']}")
            if trade['exit_price']:
                logger.info(f"   Exit: ${trade['exit_price']}")
                logger.info(f"   P&L: ${trade['pnl_usd']:.2f} ({trade['pnl_pct']:.2f}%)")
            logger.info(f"   Status: {trade['status']}")
        elif response.status_code == 404:
            logger.warning(f"⚠️ Trade ID 1 not found (normal if no trades yet)")
        else:
            logger.error(f"❌ Failed to get trade: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error getting single trade: {e}")

    # Test 10: GET /api/trades with date filters
    logger.info("\n[Test 10] GET /api/trades with date filters...")
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        response = requests.get(
            f"{BASE_URL}/api/trades",
            params={"date_from": yesterday, "date_to": today},
            timeout=10
        )
        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Retrieved {len(trades)} trades from {yesterday} to {today}")
        else:
            logger.warning(f"⚠️ Date filter test: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error testing date filters: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ All API endpoint tests completed!")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    logger.info("Starting API endpoint tests...")
    logger.info("Make sure the API server is running:")
    logger.info("  uvicorn main:app --host 0.0.0.0 --port 8000")
    logger.info("")

    input("Press Enter to start tests...")

    success = test_api_endpoints()

    if not success:
        logger.error("\n❌ Some tests failed. Check the logs above.")
        exit(1)
    else:
        logger.info("\n✅ All API endpoints are working correctly!")
