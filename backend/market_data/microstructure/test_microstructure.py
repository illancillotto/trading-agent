"""
Test per Market Microstructure Module
"""

import unittest
import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from market_data.exchanges.binance import BinanceProvider
from market_data.exchanges.bybit import BybitProvider
from market_data.exchanges.okx import OkxProvider
from market_data.exchanges.coinglass import CoinglassProvider
from market_data.microstructure.aggregator import MicrostructureAggregator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMicrostructure")


class TestOrderBook(unittest.IsolatedAsyncioTestCase):
    """Test order book fetching"""

    async def test_binance_orderbook(self):
        logger.info("Testing Binance Order Book...")
        provider = BinanceProvider()
        ob = await provider.get_order_book("BTC")

        self.assertIsNotNone(ob, "Binance order book should not be None")
        self.assertEqual(ob.exchange, "Binance")
        self.assertGreater(ob.best_bid, 0)
        self.assertGreater(ob.best_ask, 0)
        self.assertGreater(ob.best_ask, ob.best_bid)  # Ask > Bid
        self.assertGreater(len(ob.bids), 0)
        self.assertGreater(len(ob.asks), 0)

        print(f"✅ Binance BTC: Bid ${ob.best_bid:,.0f} | Ask ${ob.best_ask:,.0f} | Spread {ob.spread_pct:.4f}%")

    async def test_bybit_orderbook(self):
        logger.info("Testing Bybit Order Book...")
        provider = BybitProvider()
        ob = await provider.get_order_book("BTC")

        self.assertIsNotNone(ob)
        print(f"✅ Bybit BTC: Bid ${ob.best_bid:,.0f} | Ask ${ob.best_ask:,.0f}")

    async def test_okx_orderbook(self):
        logger.info("Testing OKX Order Book...")
        provider = OkxProvider()
        ob = await provider.get_order_book("BTC")

        self.assertIsNotNone(ob)
        print(f"✅ OKX BTC: Bid ${ob.best_bid:,.0f} | Ask ${ob.best_ask:,.0f}")


class TestCoinglass(unittest.IsolatedAsyncioTestCase):
    """Test Coinglass provider"""

    async def test_coinglass_liquidations(self):
        logger.info("Testing Coinglass Liquidations...")
        provider = CoinglassProvider()

        if not provider.check_availability():
            self.skipTest("Coinglass API key not configured")

        liq = await provider.get_liquidations("BTC")

        self.assertIsNotNone(liq)
        self.assertEqual(liq.symbol, "BTC")
        self.assertGreater(liq.total_24h_usd, 0)

        print(f"✅ BTC 24h Liquidations: ${liq.total_24h_usd/1e6:.1f}M (Long: {liq.long_ratio:.0%})")


class TestMicrostructureAggregator(unittest.IsolatedAsyncioTestCase):
    """Test aggregatore completo"""

    async def test_full_context(self):
        logger.info("Testing Full Microstructure Context...")
        aggregator = MicrostructureAggregator()

        context = await aggregator.get_full_context("BTC")

        self.assertIsNotNone(context)
        self.assertEqual(context.symbol, "BTC")
        self.assertGreater(context.current_price, 0)

        print(f"\n=== BTC Microstructure ===")
        print(f"Price: ${context.current_price:,.0f}")
        print(f"Bias: {context.overall_bias.value} ({context.bias_confidence:.0%})")
        print(f"Reasons: {context.bias_reasons}")

        if context.order_book:
            print(f"Order Book: {context.order_book.exchanges_included}")
            print(f"  Imbalance: {context.order_book.imbalance:.2f} ({context.order_book.imbalance_interpretation})")

        if context.warnings:
            print(f"⚠️ Warnings: {context.warnings}")

        # Test to_prompt_context
        prompt_context = context.to_prompt_context()
        self.assertIn("<market_microstructure", prompt_context)
        print(f"\n=== Prompt Context Preview ===\n{prompt_context[:500]}...")


if __name__ == "__main__":
    unittest.main()
