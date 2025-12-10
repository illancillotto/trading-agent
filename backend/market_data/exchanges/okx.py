import logging
import aiohttp
from typing import Dict, Any, Optional
from .base_provider import BaseProvider, OrderBookSnapshot, OrderBookLevel

logger = logging.getLogger(__name__)

class OkxProvider(BaseProvider):
    """
    Provider per OKX API V5 (Swap/Perpetuals).
    """
    BASE_URL = "https://www.okx.com"

    def check_availability(self) -> bool:
        return True

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        inst_id = f"{symbol}-USDT-SWAP"
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/api/v5/market/ticker"
                params = {"instId": inst_id}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()

            if data["code"] != "0" or not data["data"]:
                return {}

            ticker = data["data"][0]

            # OKX non fornisce il funding rate nel ticker, serve altra chiamata
            # Per semplicità qui prendiamo prezzo e volume, funding richiederebbe /public/funding-rate

            # OKX volume handling:
            # volCcy24h: 24h volume in quote currency (es. USDT)
            # Se il valore sembra troppo basso rispetto al prezzo, potrebbe essere in contratti o altra unità
            # Per SWAP USDT-margined, volCcy24h dovrebbe essere corretto in USDT.
            # Tuttavia, se vediamo ~100k su BTC, è sospetto.
            # Proviamo a usare vol24h (contratti) * contract_val (se noto) o fidiamoci di volCcy24h
            # Nella risposta del test avevamo 104708. Se sono BTC -> 9B USD. Se sono USDT -> 100k USD.
            # OKX è top tier, 100k è impossibile. Quindi sono BTC (base currency).
            # La doc dice: "volCcy24h: 24h volume in quote currency".
            # MA per USDT-margined swap, la quote è USDT.
            # Controlliamo instId: BTC-USDT-SWAP.

            # Workaround empirico: se il volume è < 1M per BTC su un major exchange,
            # probabilmente è espresso in Base Currency (BTC).
            raw_vol = float(ticker.get("volCcy24h", 0))
            last_price = float(ticker.get("last", 0))

            # Se il volume in "USDT" è irrisorio (< 10M) ma il prezzo è alto, assumiamo sia in Base Asset
            # e convertiamo in USD. (100k BTC * 80k = 8B USD -> coerente)
            volume_usd = raw_vol
            if raw_vol > 0 and (raw_vol * last_price > 10_000_000) and raw_vol < 1_000_000:
                 # Esempio: 100.000 "units" * 80.000$ = 8 Miliardi (OK).
                 # Se fosse già USD: 100.000$ (No).
                 volume_usd = raw_vol * last_price

            return {
                "price": last_price,
                "volume_24h": volume_usd,
                "funding_rate": None,
                "open_interest": None,
                "source": "okx_swap"
            }
        except Exception as e:
            logger.error(f"OKX fetch error for {symbol}: {e}")
            return {}

    # ===== NUOVI METODI =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """Fetch order book da OKX"""
        inst_id = f"{symbol}-USDT-SWAP"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/api/v5/market/books"
                params = {"instId": inst_id, "sz": str(min(depth, 400))}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            book_data = data["data"][0]

            bids = []
            for bid in book_data.get("bids", [])[:depth]:
                price = float(bid[0])
                size = float(bid[1])
                bids.append(OrderBookLevel(
                    price=price,
                    size=size,
                    size_usd=price * size
                ))

            asks = []
            for ask in book_data.get("asks", [])[:depth]:
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
                exchange_name='OKX',
                symbol=symbol
            )

        except Exception as e:
            logger.error(f"Error fetching OKX order book for {symbol}: {e}")
            return None

    async def get_funding_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch funding rate da OKX (richiede chiamata separata)"""
        inst_id = f"{symbol}-USDT-SWAP"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/api/v5/public/funding-rate"
                params = {"instId": inst_id}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            fr_data = data["data"][0]
            return {
                'symbol': symbol,
                'funding_rate': float(fr_data.get('fundingRate', 0)),
                'next_funding_rate': float(fr_data.get('nextFundingRate', 0)) if fr_data.get('nextFundingRate') else None,
                'source': 'okx_swap'
            }

        except Exception as e:
            logger.error(f"Error fetching OKX funding rate for {symbol}: {e}")
            return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch open interest da OKX"""
        inst_id = f"{symbol}-USDT-SWAP"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/api/v5/public/open-interest"
                params = {"instId": inst_id}

                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            oi_data = data["data"][0]
            oi = float(oi_data.get('oi', 0))

            # Get price for USD conversion
            market_data = await self.get_market_data(symbol)
            price = market_data.get('price', 0) if market_data else 0

            return {
                'symbol': symbol,
                'open_interest': oi,
                'open_interest_usd': oi * price,
                'source': 'okx_swap'
            }

        except Exception as e:
            logger.error(f"Error fetching OKX OI for {symbol}: {e}")
            return None

