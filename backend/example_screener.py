"""
Example usage of the coin screener module

This script demonstrates how to use the coin screener independently
of the main trading bot.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from coin_screener import CoinScreener, HardFilterConfig, ScoringWeights

def main():
    print("=" * 70)
    print("📊 COIN SCREENER - Example Usage")
    print("=" * 70)

    # Configuration
    testnet = True
    top_n = 5
    coingecko_api_key = os.getenv("COINGECKO_API_KEY")

    print(f"\n⚙️  Configuration:")
    print(f"   Testnet: {testnet}")
    print(f"   Top N coins: {top_n}")
    print(f"   CoinGecko API: {'Yes' if coingecko_api_key else 'No (using free tier)'}")

    # Initialize screener
    print(f"\n🔧 Initializing screener...")
    screener = CoinScreener(
        testnet=testnet,
        coingecko_api_key=coingecko_api_key,
        top_n=top_n,
        cache_enabled=True
    )

    # Run full screening
    print(f"\n🔍 Running full screening (this may take a minute)...")
    try:
        result = screener.run_full_screening()

        print(f"\n" + "=" * 70)
        print(f"📈 SCREENING RESULTS")
        print(f"=" * 70)
        print(f"Timestamp: {result.screening_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Next rebalance: {result.next_rebalance.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Total coins analyzed: {len(result.selected_coins) + len(result.excluded_coins)}")
        print(f"Coins passed filters: {len(result.selected_coins)}")
        print(f"Coins excluded: {len(result.excluded_coins)}")

        # Display selected coins
        print(f"\n🎯 TOP {len(result.selected_coins)} SELECTED COINS:")
        print(f"{'-' * 70}")
        print(f"{'Rank':<6} {'Symbol':<8} {'Score':<8} {'7d%':<10} {'30d%':<10} {'Vol Trend':<12}")
        print(f"{'-' * 70}")

        for coin in result.selected_coins:
            # Calculate performance metrics
            metrics = coin.metrics
            perf_7d = ((metrics.get('price', 0) / metrics.get('price_7d_ago', 1)) - 1) * 100 if metrics.get('price_7d_ago') else 0
            perf_30d = ((metrics.get('price', 0) / metrics.get('price_30d_ago', 1)) - 1) * 100 if metrics.get('price_30d_ago') else 0

            print(f"{coin.rank:<6} {coin.symbol:<8} {coin.score:<8.2f} "
                  f"{perf_7d:>8.2f}%  {perf_30d:>8.2f}%  "
                  f"{coin.factors.get('volume_trend', 0)*100:>10.1f}%")

        # Display factor breakdown for #1 coin
        if result.selected_coins:
            top_coin = result.selected_coins[0]
            print(f"\n📊 FACTOR BREAKDOWN - {top_coin.symbol}:")
            print(f"{'-' * 70}")
            for factor, score in sorted(top_coin.factors.items(), key=lambda x: x[1], reverse=True):
                bar = '█' * int(score * 30)
                print(f"  {factor:<20} {score*100:>6.1f}%  {bar}")

        # Display some excluded coins
        if result.excluded_coins:
            print(f"\n❌ SAMPLE EXCLUDED COINS (showing first 10):")
            print(f"   {', '.join(result.excluded_coins[:10])}")

        # Cache info
        cache_stats = screener.cache.get_stats()
        print(f"\n💾 CACHE STATUS:")
        print(f"   Files: {cache_stats.get('total_files', 0)}")
        print(f"   Size: {cache_stats.get('total_size_mb', 0):.2f} MB")

        # Next steps
        print(f"\n" + "=" * 70)
        print(f"✅ SCREENING COMPLETE")
        print(f"=" * 70)
        print(f"\nTo use these coins in trading:")
        print(f"1. Set SCREENING_ENABLED=True in main.py CONFIG")
        print(f"2. The bot will automatically use these selected coins")
        print(f"3. Rebalancing happens every Sunday at 00:00 UTC")

    except Exception as e:
        print(f"\n❌ Error during screening: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def demo_custom_config():
    """Demonstrate custom configuration"""
    print("\n" + "=" * 70)
    print("🔧 CUSTOM CONFIGURATION EXAMPLE")
    print("=" * 70)

    # Custom hard filters (more strict)
    custom_filters = HardFilterConfig(
        min_volume_24h_usd=100_000_000,  # $100M (vs $50M default)
        min_market_cap_usd=500_000_000,  # $500M (vs $250M default)
        min_days_listed=60,               # 60 days (vs 30 default)
        max_spread_pct=0.3                # 0.3% (vs 0.5% default)
    )

    # Custom scoring weights (focus on momentum)
    custom_weights = ScoringWeights(
        momentum_7d=0.30,      # More weight on short-term momentum
        momentum_30d=0.20,
        volatility_regime=0.15,
        volume_trend=0.15,
        oi_trend=0.05,
        funding_stability=0.05,
        liquidity_score=0.05,
        relative_strength=0.05
    )

    print("\nCustom Filters:")
    print(f"  Min Volume 24h: $100M")
    print(f"  Min Market Cap: $500M")
    print(f"  Min Days Listed: 60")

    print("\nCustom Weights (momentum-focused):")
    print(f"  7d momentum: 30%")
    print(f"  30d momentum: 20%")

    screener = CoinScreener(
        testnet=True,
        filter_config=custom_filters,
        scoring_weights=custom_weights,
        top_n=3
    )

    print(f"\n✅ Custom screener initialized")
    print(f"   (Run screener.run_full_screening() to use)")


if __name__ == "__main__":
    # Run main example
    main()

    # Optional: show custom config
    show_custom = input("\n❓ Show custom configuration example? [y/N]: ")
    if show_custom.lower() == 'y':
        demo_custom_config()

    print("\n👋 Done!")
