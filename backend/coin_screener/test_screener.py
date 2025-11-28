"""
Simple tests for coin screener module
"""
import sys
import os
sys.path.append('..')

from coin_screener import CoinScreener, HardFilterConfig, ScoringWeights
from coin_screener.models import CoinMetrics
from coin_screener.filters import HardFilters
from coin_screener.scoring import CoinScorer


def test_hard_filters():
    """Test hard filters"""
    print("\n🧪 Testing hard filters...")

    config = HardFilterConfig()
    filters = HardFilters(config)

    # Create test metrics
    good_coin = CoinMetrics(
        symbol="BTC",
        price=50000,
        volume_24h_usd=100_000_000,
        market_cap_usd=1_000_000_000,
        open_interest_usd=50_000_000,
        funding_rate=0.0001,
        spread_pct=0.1,
        days_listed=365
    )

    bad_coin = CoinMetrics(
        symbol="SCAM",
        price=0.01,
        volume_24h_usd=1000,  # Too low
        market_cap_usd=100_000,  # Too low
        open_interest_usd=100,
        funding_rate=0.01,
        spread_pct=2.0,  # Too wide
        days_listed=5  # Too new
    )

    assert filters.check_single_coin(good_coin) == True
    assert filters.check_single_coin(bad_coin) == False

    print("✅ Hard filters test passed")


def test_scoring():
    """Test scoring system"""
    print("\n🧪 Testing scoring system...")

    scorer = CoinScorer()

    # Create test metrics
    coins = [
        CoinMetrics(
            symbol="BTC",
            price=50000,
            price_7d_ago=45000,  # +11% momentum
            price_30d_ago=40000,  # +25% momentum
            volume_24h_usd=100_000_000,
            volume_7d_avg=90_000_000,
            volume_30d_avg=80_000_000,
            market_cap_usd=1_000_000_000,
            open_interest_usd=50_000_000,
            oi_7d_ago=45_000_000,
            funding_rate=0.0001,
            spread_pct=0.1,
            days_listed=365,
            atr_14=1000,
            atr_sma_20=900
        ),
        CoinMetrics(
            symbol="ETH",
            price=3000,
            price_7d_ago=2900,  # +3.4% momentum
            price_30d_ago=2800,
            volume_24h_usd=80_000_000,
            volume_7d_avg=75_000_000,
            volume_30d_avg=70_000_000,
            market_cap_usd=400_000_000,
            open_interest_usd=30_000_000,
            oi_7d_ago=28_000_000,
            funding_rate=0.0002,
            spread_pct=0.15,
            days_listed=300,
            atr_14=50,
            atr_sma_20=48
        ),
    ]

    scored = scorer.score_coins(coins, btc_price=50000, btc_price_7d=45000)

    assert len(scored) == 2
    assert scored[0].rank == 1
    assert scored[1].rank == 2
    assert all(0 <= coin.score <= 100 for coin in scored)

    print(f"  BTC score: {scored[0].score:.2f}")
    print(f"  ETH score: {scored[1].score:.2f}")
    print("✅ Scoring test passed")


def test_screener_initialization():
    """Test screener initialization"""
    print("\n🧪 Testing screener initialization...")

    screener = CoinScreener(
        testnet=True,
        top_n=3,
        cache_enabled=True
    )

    assert screener.testnet == True
    assert screener.top_n == 3
    assert screener.hl_provider is not None
    assert screener.cg_provider is not None
    assert screener.cache is not None

    print("✅ Screener initialization test passed")


def test_full_screening():
    """Test full screening (may be slow)"""
    print("\n🧪 Testing full screening...")
    print("⚠️  This test is slow as it fetches real data from APIs")

    screener = CoinScreener(
        testnet=True,
        top_n=3,
        cache_enabled=True
    )

    try:
        result = screener.run_full_screening()

        print(f"  Total symbols checked: {len(result.selected_coins) + len(result.excluded_coins)}")
        print(f"  Selected coins: {len(result.selected_coins)}")
        print(f"  Excluded coins: {len(result.excluded_coins)}")

        if result.selected_coins:
            print(f"  Top coin: {result.selected_coins[0].symbol} (score: {result.selected_coins[0].score:.2f})")

        # Basic assertions
        assert result.selected_coins is not None
        assert result.screening_timestamp is not None
        assert result.next_rebalance is not None

        print("✅ Full screening test passed")

    except Exception as e:
        print(f"⚠️  Full screening test failed: {e}")
        print("   This is expected if APIs are unavailable or rate-limited")


def test_cache():
    """Test caching system"""
    print("\n🧪 Testing cache...")

    from coin_screener.data_providers import DataCache

    cache = DataCache(cache_dir=".cache/test")

    # Test set and get
    cache.set("test_key", {"data": "value"})
    value = cache.get("test_key", max_age_seconds=60)

    assert value is not None
    assert value["data"] == "value"

    # Test expiration
    expired = cache.get("test_key", max_age_seconds=0)
    assert expired is None

    # Cleanup
    cache.clear()

    print("✅ Cache test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Running Coin Screener Tests")
    print("=" * 60)

    try:
        test_hard_filters()
        test_scoring()
        test_screener_initialization()
        test_cache()

        # Optional: test full screening (slow)
        run_slow_tests = input("\n❓ Run full screening test? (slow, requires APIs) [y/N]: ")
        if run_slow_tests.lower() == 'y':
            test_full_screening()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
