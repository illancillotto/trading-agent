"""
Order Book Cache con LRU eviction

Cache TTL-based per ridurre chiamate API ripetitive.
Implementa LRU (Least Recently Used) per gestire memory usage.
"""

import time
from typing import Dict, Optional, Tuple, Any
from collections import OrderedDict
import logging
from dataclasses import dataclass

from market_data.exchanges.base_provider import OrderBookSnapshot

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entry nella cache con metadata"""
    data: OrderBookSnapshot
    timestamp: float
    access_count: int = 0


class OrderBookCache:
    """
    LRU Cache per order book snapshots

    Features:
    - TTL-based expiration
    - LRU eviction quando raggiunge max_size
    - Thread-safe (asyncio-safe)
    - Statistiche hit/miss
    """

    def __init__(self, ttl_seconds: float = 5.0, max_size: int = 100):
        """
        Args:
            ttl_seconds: Time-to-live per entry (default 5s)
            max_size: Numero massimo di entry (default 100)
        """
        self.ttl = ttl_seconds
        self.max_size = max_size

        # OrderedDict garantisce ordine inserimento (LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Statistiche
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _make_key(self, exchange: str, symbol: str) -> str:
        """Genera chiave cache"""
        return f"{exchange}:{symbol}"

    def get(self, exchange: str, symbol: str) -> Optional[OrderBookSnapshot]:
        """
        Ottiene order book dalla cache

        Args:
            exchange: Nome exchange
            symbol: Simbolo

        Returns:
            OrderBookSnapshot se presente e valido, None altrimenti
        """
        key = self._make_key(exchange, symbol)

        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Verifica TTL
        age = time.time() - entry.timestamp
        if age > self.ttl:
            # Entry scaduto
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache expired: {key} (age: {age:.1f}s)")
            return None

        # Hit! Sposta in fondo (LRU)
        self._cache.move_to_end(key)
        entry.access_count += 1
        self._hits += 1

        logger.debug(f"Cache hit: {key} (age: {age:.1f}s, accesses: {entry.access_count})")
        return entry.data

    def set(self, exchange: str, symbol: str, data: OrderBookSnapshot):
        """
        Aggiunge order book alla cache

        Args:
            exchange: Nome exchange
            symbol: Simbolo
            data: Order book snapshot
        """
        key = self._make_key(exchange, symbol)

        # Se già presente, aggiorna e sposta in fondo
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                access_count=self._cache[key].access_count
            )
            logger.debug(f"Cache updated: {key}")
            return

        # Nuovo entry - verifica limite size
        if len(self._cache) >= self.max_size:
            # Evict oldest (primo elemento OrderedDict)
            evicted_key, evicted_entry = self._cache.popitem(last=False)
            self._evictions += 1
            logger.debug(
                f"Cache eviction: {evicted_key} "
                f"(age: {time.time() - evicted_entry.timestamp:.1f}s, "
                f"accesses: {evicted_entry.access_count})"
            )

        # Aggiungi nuovo entry
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            access_count=0
        )
        logger.debug(f"Cache set: {key}")

    def invalidate(self, exchange: Optional[str] = None, symbol: Optional[str] = None):
        """
        Invalida entry cache

        Args:
            exchange: Se specificato, invalida solo questo exchange
            symbol: Se specificato (con exchange), invalida singolo pair
        """
        if exchange and symbol:
            # Invalida singolo pair
            key = self._make_key(exchange, symbol)
            if key in self._cache:
                del self._cache[key]
                logger.info(f"Cache invalidated: {key}")

        elif exchange:
            # Invalida tutti i pair di un exchange
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{exchange}:")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Cache invalidated: {len(keys_to_remove)} entries for {exchange}")

        else:
            # Invalida tutto
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")

    def cleanup_expired(self):
        """Rimuove tutte le entry scadute"""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry.timestamp > self.ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cache cleanup: {len(expired_keys)} expired entries removed")

    def get_stats(self) -> Dict[str, Any]:
        """
        Statistiche cache

        Returns:
            Dict con hit_rate, misses, size, etc.
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        # Entry più vecchio
        oldest_age = 0.0
        if self._cache:
            first_entry = next(iter(self._cache.values()))
            oldest_age = time.time() - first_entry.timestamp

        return {
            'hits': self._hits,
            'misses': self._misses,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'evictions': self._evictions,
            'current_size': len(self._cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl,
            'oldest_entry_age': oldest_age
        }

    def reset_stats(self):
        """Reset contatori statistiche (ma non la cache)"""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logger.info("Cache stats reset")


# Singleton globale
_global_cache: Optional[OrderBookCache] = None


def get_cache(ttl_seconds: float = 5.0, max_size: int = 100) -> OrderBookCache:
    """
    Ottiene istanza globale cache

    Args:
        ttl_seconds: TTL default
        max_size: Size massima

    Returns:
        OrderBookCache singleton
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = OrderBookCache(ttl_seconds, max_size)
        logger.info(f"Order book cache initialized (TTL: {ttl_seconds}s, max_size: {max_size})")
    return _global_cache
