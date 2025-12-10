import logging
import aiohttp
from typing import Dict, Any, Optional
from .base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel

logger = logging.getLogger(__name__)

class BybitProvider(BaseProvider):
    """
    Provider per Bybit V5 API (Linear Perpetuals).
    """
    BASE_URL = "https://api.bybit.com"

    def check_availability(self) -> bool:
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        pair = f"{symbol}USDT"
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/tickers"
                params = {"category": "linear", "symbol": pair}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()

            if data["retCode"] != 0 or not data["result"]["list"]:
                return {}

            ticker = data["result"]["list"][0]

            return {
                "price": float(ticker.get("lastPrice", 0)),
                "volume_24h": float(ticker.get("turnover24h", 0)), # Turnover è volume in USD
                "funding_rate": float(ticker.get("fundingRate", 0)),
                "open_interest": float(ticker.get("openInterestValue", 0)),
                "source": "bybit_linear"
            }
        except Exception as e:
            logger.error(f"Bybit fetch error for {symbol}: {e}")
            return {}

    # ===== NUOVO METODO =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """Fetch order book da Bybit"""
        pair = f"{symbol}USDT"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v5/market/orderbook"
                params = {
                    "category": "linear",
                    "symbol": pair,
                    "limit": str(min(depth, 200))
                }

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if data.get("retCode") != 0 or "result" not in data:
                return None

            result = data["result"]

            bids = []
            for bid in result.get("b", [])[:depth]:
                price = float(bid[0])
                size = float(bid[1])
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for ask in result.get("a", [])[:depth]:
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
                exchange_name='Bybit',
                symbol=symbol
            )

        except Exception as e:
            logger.error(f"Error fetching Bybit order book for {symbol}: {e}")
            return None

