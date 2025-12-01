import logging
import aiohttp
from typing import Dict, Any
from .base_provider import BaseProvider

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

