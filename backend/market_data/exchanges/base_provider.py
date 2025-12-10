from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class OrderBookLevel:
    """Singolo livello dell'order book"""
    price: float
    size: float
    size_usd: float


@dataclass
class OrderBookSnapshot:
    """Snapshot dell'order book da un exchange"""
    exchange: str
    symbol: str
    timestamp: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    best_bid: float
    best_ask: float
    spread_pct: float
    mid_price: float
    bid_depth_usd: float  # Depth entro 2% dal mid price
    ask_depth_usd: float
    imbalance: float  # bid_depth / ask_depth

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'spread_pct': self.spread_pct,
            'mid_price': self.mid_price,
            'bid_depth_usd': self.bid_depth_usd,
            'ask_depth_usd': self.ask_depth_usd,
            'imbalance': self.imbalance,
            'bids_count': len(self.bids),
            'asks_count': len(self.asks)
        }


class BaseProvider(ABC):
    """
    Interfaccia base per tutti i provider di dati di mercato.
    Ogni nuovo exchange deve ereditare da questa classe.
    """

    # Ogni provider deve definire il proprio EXCHANGE_NAME
    EXCHANGE_NAME: str = "Unknown"

    @abstractmethod
    def check_availability(self) -> bool:
        """
        Verifica se il provider è configurato correttamente e raggiungibile.
        Returns:
            bool: True se disponibile, False altrimenti.
        """
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Ottiene i dati di mercato standardizzati per un simbolo.

        Args:
            symbol: Simbolo (es. 'BTC', 'ETH')

        Returns:
            Dict con chiavi standard:
            - price (float)
            - volume_24h (float)
            - funding_rate (float, opzionale)
            - open_interest (float, opzionale)
            - source (str)
        """
        pass

    # ===== NUOVI METODI PER MICROSTRUCTURE =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """
        Ottiene l'order book per un simbolo.
        Default: restituisce None (provider non supporta order book).
        Override nei provider che lo supportano.

        Args:
            symbol: Simbolo base (es. 'BTC')
            depth: Numero di livelli da richiedere

        Returns:
            OrderBookSnapshot o None se non supportato
        """
        return None

    async def get_funding_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene funding rate dettagliato.
        Default: estrae da get_market_data() se disponibile.
        """
        data = await self.get_market_data(symbol)
        if data and 'funding_rate' in data and data['funding_rate'] is not None:
            return {
                'symbol': symbol,
                'funding_rate': data['funding_rate'],
                'source': data.get('source', 'unknown')
            }
        return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene open interest.
        Default: estrae da get_market_data() se disponibile.
        """
        data = await self.get_market_data(symbol)
        if data and 'open_interest' in data and data['open_interest'] is not None:
            return {
                'symbol': symbol,
                'open_interest': data['open_interest'],
                'source': data.get('source', 'unknown')
            }
        return None

    async def safe_get_order_book(
        self,
        symbol: str,
        depth: int = 50,
        use_cache: bool = True,
        use_circuit_breaker: bool = True,
        use_rate_limiter: bool = True
    ) -> Optional[OrderBookSnapshot]:
        """
        Ottiene order book con circuit breaker, cache e rate limiting integrati.

        Questo metodo wrappa get_order_book() con resilienza:
        - Cache: Riduce chiamate API ripetitive
        - Circuit Breaker: Previene cascade failure
        - Rate Limiter: Rispetta limiti API

        Args:
            symbol: Simbolo base
            depth: Livelli richiesti
            use_cache: Abilita cache (default True)
            use_circuit_breaker: Abilita circuit breaker (default True)
            use_rate_limiter: Abilita rate limiter (default True)

        Returns:
            OrderBookSnapshot o None
        """
        # Import lazy per evitare circular imports
        from market_data.microstructure.cache import get_cache
        from market_data.microstructure.circuit_breaker import CircuitBreakerRegistry
        from market_data.microstructure.rate_limiter import RateLimiterRegistry
        from market_data.microstructure.utils import CircuitBreakerOpenError
        import logging

        logger = logging.getLogger(__name__)
        exchange_name = self.EXCHANGE_NAME

        # 1. Check cache
        if use_cache:
            cache = get_cache()
            cached = cache.get(exchange_name, symbol)
            if cached:
                logger.debug(f"Cache hit: {exchange_name}:{symbol}")
                return cached

        # 2. Check circuit breaker
        if use_circuit_breaker:
            breaker_registry = CircuitBreakerRegistry()
            breaker = breaker_registry.get_breaker(exchange_name)

            if not breaker.can_execute():
                logger.warning(f"Circuit breaker OPEN for {exchange_name}, skipping request")
                raise CircuitBreakerOpenError(exchange_name, "Circuit breaker is open")

        # 3. Apply rate limiting
        if use_rate_limiter:
            limiter_registry = RateLimiterRegistry()
            limiter = limiter_registry.get_limiter(exchange_name.lower())
            await limiter.acquire()

        # 4. Execute actual request
        try:
            result = await self.get_order_book(symbol, depth)

            # Record success
            if use_circuit_breaker and result:
                breaker.record_success()

            # Update cache
            if use_cache and result:
                cache.set(exchange_name, symbol, result)

            return result

        except Exception as e:
            # Record failure
            if use_circuit_breaker:
                breaker.record_failure(e)

            logger.error(f"{exchange_name} safe_get_order_book error for {symbol}: {e}")
            raise

    def _calculate_order_book_metrics(
        self,
        bids: List[OrderBookLevel],
        asks: List[OrderBookLevel],
        exchange_name: str,
        symbol: str
    ) -> Optional[OrderBookSnapshot]:
        """
        Helper per calcolare metriche order book.
        Usato dai provider che implementano get_order_book().
        """
        if not bids or not asks:
            return None

        best_bid = bids[0].price
        best_ask = asks[0].price
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0

        # Calcola depth entro 2% dal mid price
        bid_depth = sum(
            b.size_usd for b in bids
            if b.price >= mid_price * 0.98
        )
        ask_depth = sum(
            a.size_usd for a in asks
            if a.price <= mid_price * 1.02
        )

        imbalance = bid_depth / ask_depth if ask_depth > 0 else 1.0

        return OrderBookSnapshot(
            exchange=exchange_name,
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread_pct=spread_pct,
            mid_price=mid_price,
            bid_depth_usd=bid_depth,
            ask_depth_usd=ask_depth,
            imbalance=imbalance
        )

