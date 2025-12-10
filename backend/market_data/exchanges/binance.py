import logging
import aiohttp
from typing import Dict, Any, Optional
from .base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel

logger = logging.getLogger(__name__)

class BinanceProvider(BaseProvider):
    """
    Provider per Binance Futures (USDT-M).
    Usa API pubbliche, non richiede API key per i dati di mercato.
    """

    BASE_URL = "https://fapi.binance.com"

    def check_availability(self) -> bool:
        # Le API pubbliche sono sempre "disponibili" a meno di blocchi IP
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        # Mappa simboli generici (BTC) ai simboli Binance (BTCUSDT)
        # Hyperliquid usa spesso solo il base asset name
        pair = f"{symbol}USDT"

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Ottieni Prezzo e Volume 24h
                ticker_url = f"{self.BASE_URL}/fapi/v1/ticker/24hr"
                async with session.get(ticker_url, params={"symbol": pair}, timeout=5) as resp:
                    if resp.status != 200:
                        logger.warning(f"Binance ticker failed for {pair}: {resp.status}")
                        return {}
                    ticker_data = await resp.json()

                # 2. Ottieni Funding Rate e Open Interest (opzionale, ma utile)
                # Facciamo una chiamata separata per il Premium Index che contiene il funding
                funding_url = f"{self.BASE_URL}/fapi/v1/premiumIndex"
                async with session.get(funding_url, params={"symbol": pair}, timeout=5) as resp:
                    funding_data = await resp.json() if resp.status == 200 else {}

            # Estrai dati
            return {
                "price": float(ticker_data.get("lastPrice", 0)),
                "volume_24h": float(ticker_data.get("quoteVolume", 0)), # Volume in USDT
                "funding_rate": float(funding_data.get("lastFundingRate", 0)) if funding_data else None,
                "open_interest": None, # Richiede altra chiamata, saltiamo per velocità
                "source": "binance_futures"
            }

        except Exception as e:
            logger.error(f"Error fetching Binance data for {symbol}: {e}")
            return {"error": str(e)}

    # ===== NUOVI METODI =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """
        Fetch order book da Binance Futures.

        Args:
            symbol: Simbolo base (es. 'BTC')
            depth: Numero livelli (5, 10, 20, 50, 100, 500, 1000)
        """
        pair = f"{symbol}USDT"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/fapi/v1/depth"
                params = {"symbol": pair, "limit": min(depth, 1000)}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        logger.warning(f"Binance order book failed for {pair}: {resp.status}")
                        return None
                    data = await resp.json()

            if not data.get('bids') or not data.get('asks'):
                return None

            # Parse bids e asks
            bids = []
            for bid in data['bids'][:depth]:
                price = float(bid[0])
                size = float(bid[1])
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for ask in data['asks'][:depth]:
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
                exchange_name='Binance',
                symbol=symbol
            )

        except Exception as e:
            logger.error(f"Error fetching Binance order book for {symbol}: {e}")
            return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch open interest da Binance"""
        pair = f"{symbol}USDT"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/fapi/v1/openInterest"
                params = {"symbol": pair}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            oi = float(data.get('openInterest', 0))

            # Get price for USD conversion
            market_data = await self.get_market_data(symbol)
            price = market_data.get('price', 0) if market_data else 0

            return {
                'symbol': symbol,
                'open_interest': oi,
                'open_interest_usd': oi * price,
                'source': 'binance_futures'
            }

        except Exception as e:
            logger.error(f"Error fetching Binance OI for {symbol}: {e}")
            return None

    async def get_long_short_ratio(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch long/short ratio da Binance (Top Traders)"""
        pair = f"{symbol}USDT"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/futures/data/topLongShortAccountRatio"
                params = {"symbol": pair, "period": "1h", "limit": 1}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if not data:
                return None

            latest = data[0]
            return {
                'symbol': symbol,
                'long_ratio': float(latest.get('longAccount', 0.5)),
                'short_ratio': float(latest.get('shortAccount', 0.5)),
                'long_short_ratio': float(latest.get('longShortRatio', 1.0)),
                'source': 'binance_futures'
            }

        except Exception as e:
            logger.error(f"Error fetching Binance LS ratio for {symbol}: {e}")
            return None

