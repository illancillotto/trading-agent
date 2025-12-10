import logging
import aiohttp
from typing import Dict, Any, Optional
from .base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel

logger = logging.getLogger(__name__)

class CoinbaseProvider(BaseProvider):
    """
    Provider per Coinbase Exchange (Spot).
    """
    BASE_URL = "https://api.exchange.coinbase.com"

    def check_availability(self) -> bool:
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        # Coinbase usa BTC-USD
        pair = f"{symbol}-USD"
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/products/{pair}/ticker"

                async with session.get(url, timeout=5) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()

            if "price" not in data:
                return {}

            price = float(data.get("price", 0))
            volume_base = float(data.get("volume", 0))

            return {
                "price": price,
                "volume_24h": volume_base * price, # Normalizzato in USD
                "funding_rate": None, # Spot non ha funding
                "open_interest": None,
                "source": "coinbase_spot"
            }
        except Exception as e:
            logger.error(f"Coinbase fetch error for {symbol}: {e}")
            return {}

    # ===== NUOVO METODO =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """Fetch order book da Coinbase"""
        pair = f"{symbol}-USD"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/products/{pair}/book"
                params = {"level": "2"}  # Level 2 = aggregated

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if not data.get("bids") or not data.get("asks"):
                return None

            bids = []
            for bid in data["bids"][:depth]:
                price = float(bid[0])
                size = float(bid[1])
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for ask in data["asks"][:depth]:
                price = float(ask[0])
                size = float(ask[1])
                asks.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            return self._calculate_order_book_metrics(
                bids=bids,
                asks=asks,
                exchange_name='Coinbase',
                symbol=symbol
            )

        except Exception as e:
            logger.error(f"Error fetching Coinbase order book for {symbol}: {e}")
            return None

