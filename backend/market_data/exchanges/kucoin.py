"""
KuCoin Exchange Provider

API Documentation: https://www.kucoin.com/docs/rest/spot-trading/market-data
Public API rate limit: 100 times/10s per IP (10 req/s)
"""

import httpx
from typing import Dict, Any, Optional
from market_data.exchanges.base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class KucoinProvider(BaseProvider):
    """Provider per KuCoin Exchange"""

    EXCHANGE_NAME = "KuCoin"
    BASE_URL = "https://api.kucoin.com"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    def check_availability(self) -> bool:
        """KuCoin public API non richiede API key"""
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Ottiene dati mercato da KuCoin

        Args:
            symbol: Simbolo base (es. 'BTC')

        Returns:
            Dict con price, volume_24h, source
        """
        try:
            pair = f"{symbol}-USDT"
            url = f"{self.BASE_URL}/api/v1/market/stats"
            params = {"symbol": pair}

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "200000":
                logger.error(f"KuCoin API error: {data}")
                return {}

            ticker = data.get("data", {})
            if not ticker:
                return {}

            return {
                "price": float(ticker.get("last", 0)),
                "volume_24h": float(ticker.get("volValue", 0)),  # Volume in USD
                "source": "KuCoin"
            }

        except Exception as e:
            logger.error(f"KuCoin market data error for {symbol}: {e}")
            return {}

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """
        Ottiene order book da KuCoin

        Args:
            symbol: Simbolo base (es. 'BTC')
            depth: Livelli richiesti (20 o 100)

        Returns:
            OrderBookSnapshot o None
        """
        try:
            pair = f"{symbol}-USDT"

            # KuCoin supporta depth=20 o depth=100
            # Usa Level 2 order book (aggregated)
            api_depth = 100 if depth > 20 else 20
            url = f"{self.BASE_URL}/api/v1/market/orderbook/level2_{api_depth}"
            params = {"symbol": pair}

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "200000":
                logger.error(f"KuCoin order book error: {data}")
                return None

            book_data = data.get("data", {})
            if not book_data:
                return None

            # Parse bids e asks
            raw_bids = book_data.get("bids", [])[:depth]
            raw_asks = book_data.get("asks", [])[:depth]

            if not raw_bids or not raw_asks:
                logger.warning(f"KuCoin: Empty order book for {symbol}")
                return None

            # Converti in OrderBookLevel
            bids = []
            for price_str, size_str in raw_bids:  # [price, size]
                price = float(price_str)
                size = float(size_str)
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for price_str, size_str in raw_asks:
                price = float(price_str)
                size = float(size_str)
                asks.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            # Calcola metriche
            return self._calculate_order_book_metrics(bids, asks, self.EXCHANGE_NAME, symbol)

        except Exception as e:
            logger.error(f"KuCoin order book error for {symbol}: {e}")
            return None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Ottiene funding rate da KuCoin Futures

        Args:
            symbol: Simbolo base (es. 'BTC')

        Returns:
            Funding rate o None
        """
        try:
            # KuCoin Futures API
            pair = f"{symbol}USDTM"  # Perpetual futures symbol format
            url = f"{self.BASE_URL}/api/v1/funding-rate/{pair}/current"

            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "200000":
                return None

            result = data.get("data", {})
            if not result:
                return None

            funding_rate = float(result.get("value", 0))
            return funding_rate * 100  # Convert to percentage

        except Exception as e:
            logger.debug(f"KuCoin funding rate not available for {symbol}: {e}")
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
