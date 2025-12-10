"""
Crypto.com Exchange Provider

API Documentation: https://exchange-docs.crypto.com/
Public API rate limit: 100 req/s
"""

import httpx
from typing import Dict, Any, Optional
from market_data.exchanges.base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class CryptoComProvider(BaseProvider):
    """Provider per Crypto.com Exchange"""

    EXCHANGE_NAME = "Crypto.com"
    BASE_URL = "https://api.crypto.com/exchange/v1"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    def check_availability(self) -> bool:
        """Crypto.com public API non richiede API key"""
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Ottiene dati mercato da Crypto.com

        Args:
            symbol: Simbolo base (es. 'BTC')

        Returns:
            Dict con price, volume_24h, source
        """
        try:
            pair = f"{symbol}_USDT"
            url = f"{self.BASE_URL}/public/get-ticker"
            params = {"instrument_name": pair}

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"Crypto.com API error: {data}")
                return {}

            result = data.get("result", {})
            if not result or "data" not in result:
                return {}

            ticker = result["data"][0] if isinstance(result["data"], list) else result["data"]

            return {
                "price": float(ticker.get("a", 0)),  # last price
                "volume_24h": float(ticker.get("v", 0)),
                "source": "Crypto.com"
            }

        except Exception as e:
            logger.error(f"Crypto.com market data error for {symbol}: {e}")
            return {}

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """
        Ottiene order book da Crypto.com

        Args:
            symbol: Simbolo base (es. 'BTC')
            depth: Livelli richiesti (max 150)

        Returns:
            OrderBookSnapshot o None
        """
        try:
            pair = f"{symbol}_USDT"
            url = f"{self.BASE_URL}/public/get-book"

            # Crypto.com depth: 10, 150
            api_depth = 150 if depth > 10 else 10
            params = {
                "instrument_name": pair,
                "depth": api_depth
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"Crypto.com order book error: {data}")
                return None

            result = data.get("result", {})
            if not result or "data" not in result:
                return None

            book_data = result["data"][0] if isinstance(result["data"], list) else result["data"]

            # Parse bids e asks
            raw_bids = book_data.get("bids", [])[:depth]
            raw_asks = book_data.get("asks", [])[:depth]

            if not raw_bids or not raw_asks:
                logger.warning(f"Crypto.com: Empty order book for {symbol}")
                return None

            # Converti in OrderBookLevel
            bids = []
            for price_str, qty_str, _ in raw_bids:  # [price, qty, num_orders]
                price = float(price_str)
                size = float(qty_str)
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for price_str, qty_str, _ in raw_asks:
                price = float(price_str)
                size = float(qty_str)
                asks.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            # Calcola metriche
            return self._calculate_order_book_metrics(bids, asks, self.EXCHANGE_NAME, symbol)

        except Exception as e:
            logger.error(f"Crypto.com order book error for {symbol}: {e}")
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
