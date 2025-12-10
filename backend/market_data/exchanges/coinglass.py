"""
Coinglass Provider - Dati aggregati su liquidazioni, OI, funding.
NUOVO provider - non esiste nella codebase attuale.
"""

import os
import asyncio
import logging
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from .base_provider import BaseProvider

logger = logging.getLogger(__name__)


class LiquidationRisk(Enum):
    """Livello di rischio liquidazione"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class LiquidationLevel:
    """Livello di liquidazione"""
    price: float
    pct_from_current: float
    total_usd: float
    type: str  # 'long' or 'short'
    risk: LiquidationRisk

    def to_dict(self) -> Dict:
        return {
            'price': self.price,
            'pct_from_current': self.pct_from_current,
            'total_usd': self.total_usd,
            'type': self.type,
            'risk': self.risk.value
        }


@dataclass
class LiquidationData:
    """Dati completi liquidazioni"""
    symbol: str
    timestamp: str
    total_24h_usd: float
    long_24h_usd: float
    short_24h_usd: float
    long_ratio: float  # % delle liquidazioni che sono long
    total_4h_usd: float = 0.0
    total_1h_usd: float = 0.0
    liquidation_levels: List[LiquidationLevel] = field(default_factory=list)
    nearest_long_cluster: Optional[LiquidationLevel] = None
    nearest_short_cluster: Optional[LiquidationLevel] = None
    cascade_risk: LiquidationRisk = LiquidationRisk.LOW
    cascade_risk_reason: str = ""
    exchange_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'total_24h_usd': self.total_24h_usd,
            'long_24h_usd': self.long_24h_usd,
            'short_24h_usd': self.short_24h_usd,
            'long_ratio': self.long_ratio,
            'total_4h_usd': self.total_4h_usd,
            'total_1h_usd': self.total_1h_usd,
            'liquidation_levels': [l.to_dict() for l in self.liquidation_levels],
            'nearest_long_cluster': self.nearest_long_cluster.to_dict() if self.nearest_long_cluster else None,
            'nearest_short_cluster': self.nearest_short_cluster.to_dict() if self.nearest_short_cluster else None,
            'cascade_risk': self.cascade_risk.value,
            'cascade_risk_reason': self.cascade_risk_reason,
            'exchange_breakdown': self.exchange_breakdown
        }


class CoinglassProvider(BaseProvider):
    """
    Provider per Coinglass API.
    Fornisce dati aggregati su liquidazioni, OI e funding da tutti gli exchange.

    Richiede API key (free tier: 30 req/min).
    Ottieni API key su: https://www.coinglass.com/pricing
    """

    BASE_URL = "https://open-api.coinglass.com/public/v2"

    def __init__(self):
        self.api_key = os.getenv("COINGLASS_API_KEY", "")
        self._last_request_time = 0.0
        self._min_interval = 2.0  # 30 req/min = 1 ogni 2 sec

    def check_availability(self) -> bool:
        """Verifica se API key è configurata"""
        return bool(self.api_key)

    async def _rate_limit(self):
        """Applica rate limiting"""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Helper per fare richieste a Coinglass con rate limiting"""
        if not self.api_key:
            logger.warning("Coinglass API key not configured")
            return None

        await self._rate_limit()

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/{endpoint}"
                headers = {
                    "coinglassSecret": self.api_key,
                    "Accept": "application/json"
                }

                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") or data.get("code") == "0":
                            return data.get("data", data)
                        else:
                            logger.error(f"Coinglass API error: {data.get('msg', 'Unknown')}")
                    elif resp.status == 429:
                        logger.warning("Coinglass rate limited, waiting...")
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"Coinglass HTTP error: {resp.status}")
                    return None

        except Exception as e:
            logger.error(f"Coinglass request error: {e}")
            return None

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Coinglass non fornisce ticker base.
        Restituisce OI aggregato come "market data".
        """
        oi_data = await self.get_aggregated_open_interest(symbol)

        if oi_data:
            return {
                "price": None,
                "volume_24h": None,
                "funding_rate": None,
                "open_interest": oi_data.get("total_oi_usd"),
                "source": "coinglass_aggregated"
            }
        return {}

    async def get_liquidations(self, symbol: str) -> Optional[LiquidationData]:
        """
        Fetch dati liquidazioni aggregati.
        Include: 24h liquidations, breakdown per exchange, cascade risk.
        """
        params = {"symbol": symbol.upper(), "timeType": "2"}  # 24h
        data = await self._make_request("liquidation/v2/coin", params)

        if not data:
            return None

        try:
            # Trova dati per il simbolo
            symbol_data = None
            if isinstance(data, list):
                for item in data:
                    if item.get("symbol", "").upper() == symbol.upper():
                        symbol_data = item
                        break
            else:
                symbol_data = data

            if not symbol_data:
                return None

            total_24h = float(symbol_data.get("volUsd", 0))
            long_24h = float(symbol_data.get("longVolUsd", 0))
            short_24h = float(symbol_data.get("shortVolUsd", 0))
            long_ratio = long_24h / total_24h if total_24h > 0 else 0.5

            # Stima 4h e 1h (approssimazione)
            total_4h = total_24h * 0.17  # ~4/24
            total_1h = total_24h * 0.04  # ~1/24

            # Calcola cascade risk
            cascade_risk, cascade_reason = self._assess_cascade_risk(total_24h, long_ratio)

            # Exchange breakdown (se disponibile)
            exchange_breakdown = {}
            if "list" in symbol_data and isinstance(symbol_data["list"], list):
                for ex in symbol_data["list"]:
                    ex_name = ex.get("exchangeName", "Unknown")
                    ex_vol = float(ex.get("volUsd", 0))
                    exchange_breakdown[ex_name] = ex_vol

            return LiquidationData(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_24h_usd=total_24h,
                long_24h_usd=long_24h,
                short_24h_usd=short_24h,
                long_ratio=long_ratio,
                total_4h_usd=total_4h,
                total_1h_usd=total_1h,
                cascade_risk=cascade_risk,
                cascade_risk_reason=cascade_reason,
                exchange_breakdown=exchange_breakdown
            )

        except Exception as e:
            logger.error(f"Error parsing Coinglass liquidations: {e}")
            return None

    def _assess_cascade_risk(self, total_24h: float, long_ratio: float) -> tuple:
        """Valuta rischio cascade basato sui volumi"""
        # Determina risk level basato su volume 24h
        if total_24h >= 500_000_000:  # $500M+
            risk = LiquidationRisk.EXTREME
            reason = f"Massive liquidations (${total_24h/1e6:.0f}M in 24h)"
        elif total_24h >= 200_000_000:  # $200M+
            risk = LiquidationRisk.HIGH
            reason = f"High liquidation volume (${total_24h/1e6:.0f}M in 24h)"
        elif total_24h >= 50_000_000:  # $50M+
            risk = LiquidationRisk.MEDIUM
            reason = f"Moderate liquidations (${total_24h/1e6:.0f}M in 24h)"
        else:
            risk = LiquidationRisk.LOW
            reason = "Normal liquidation levels"

        # Aggiungi info su skew
        if long_ratio > 0.75:
            reason += f" - Heavy long bias ({long_ratio:.0%})"
        elif long_ratio < 0.25:
            reason += f" - Heavy short bias ({1-long_ratio:.0%})"

        return risk, reason

    async def get_aggregated_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch OI aggregato da tutti gli exchange"""
        params = {"symbol": symbol.upper()}
        data = await self._make_request("open_interest", params)

        if not data:
            return None

        try:
            total_oi_usd = 0
            exchange_oi = {}

            if isinstance(data, list):
                for ex_data in data:
                    ex_name = ex_data.get("exchangeName", "Unknown")
                    oi_usd = float(ex_data.get("openInterest", 0))
                    total_oi_usd += oi_usd
                    exchange_oi[ex_name] = oi_usd
            else:
                total_oi_usd = float(data.get("openInterest", 0))

            return {
                "symbol": symbol,
                "total_oi_usd": total_oi_usd,
                "exchange_breakdown": exchange_oi,
                "source": "coinglass"
            }

        except Exception as e:
            logger.error(f"Error parsing Coinglass OI: {e}")
            return None

    async def get_aggregated_funding(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch funding rate aggregato da tutti gli exchange"""
        params = {"symbol": symbol.upper()}
        data = await self._make_request("funding", params)

        if not data:
            return None

        try:
            exchange_rates = {}
            total_rate = 0
            count = 0

            if isinstance(data, list):
                for ex_data in data:
                    ex_name = ex_data.get("exchangeName", "Unknown")
                    rate = float(ex_data.get("rate", 0))
                    exchange_rates[ex_name] = rate
                    total_rate += rate
                    count += 1

            avg_rate = total_rate / count if count > 0 else 0

            # Determina sentiment
            if avg_rate > 0.01:  # > 0.01%
                sentiment = 'extremely_bullish'
                extreme = True
            elif avg_rate > 0.005:
                sentiment = 'bullish'
                extreme = False
            elif avg_rate < -0.01:
                sentiment = 'extremely_bearish'
                extreme = True
            elif avg_rate < -0.005:
                sentiment = 'bearish'
                extreme = False
            else:
                sentiment = 'neutral'
                extreme = False

            return {
                "symbol": symbol,
                "average_rate": avg_rate,
                "exchange_rates": exchange_rates,
                "sentiment": sentiment,
                "extreme": extreme,
                "source": "coinglass"
            }

        except Exception as e:
            logger.error(f"Error parsing Coinglass funding: {e}")
            return None

    async def get_long_short_ratio(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch long/short ratio aggregato"""
        params = {"symbol": symbol.upper()}
        data = await self._make_request("long_short", params)

        if not data:
            return None

        try:
            exchange_ratios = {}
            total_ratio = 0
            count = 0

            if isinstance(data, list):
                for ex_data in data:
                    ex_name = ex_data.get("exchangeName", "Unknown")
                    ratio = float(ex_data.get("longRate", 0.5))
                    exchange_ratios[ex_name] = ratio
                    total_ratio += ratio
                    count += 1

            avg_ratio = total_ratio / count if count > 0 else 0.5

            # Interpret sentiment (contrarian view)
            if avg_ratio > 0.65:
                sentiment = 'crowded_long'  # Contrarian bearish
            elif avg_ratio < 0.35:
                sentiment = 'crowded_short'  # Contrarian bullish
            else:
                sentiment = 'balanced'

            return {
                "symbol": symbol,
                "average_long_ratio": avg_ratio,
                "exchange_ratios": exchange_ratios,
                "sentiment": sentiment,
                "source": "coinglass"
            }

        except Exception as e:
            logger.error(f"Error parsing Coinglass LS ratio: {e}")
            return None
