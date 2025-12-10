"""
Rate Limiter per rispettare limiti API degli exchange

Implementa token bucket algorithm per rate limiting
configurabile per exchange.
"""

import time
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterConfig:
    """Configurazione rate limiter"""
    requests_per_second: float = 10.0  # Rate limit (req/s)
    burst_size: int = 20  # Dimensione burst (token bucket)


class TokenBucketRateLimiter:
    """
    Rate limiter con Token Bucket algorithm

    Il token bucket permette burst di richieste fino a burst_size,
    ma mantiene rate medio = requests_per_second.
    """

    def __init__(self, name: str, config: RateLimiterConfig):
        """
        Args:
            name: Nome exchange
            config: Configurazione rate limiting
        """
        self.name = name
        self.config = config

        # Token bucket
        self.tokens = float(config.burst_size)
        self.max_tokens = float(config.burst_size)
        self.refill_rate = config.requests_per_second  # tokens/sec
        self.last_refill_time = time.time()

        # Statistiche
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.throttled_count = 0

        # Lock per thread-safety
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquisisce token (attende se necessario)

        Args:
            tokens: Numero di token da acquisire

        Returns:
            Tempo atteso in secondi
        """
        async with self._lock:
            # Refill tokens based on elapsed time
            now = time.time()
            elapsed = now - self.last_refill_time
            self.tokens = min(
                self.max_tokens,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill_time = now

            # Se non abbiamo abbastanza token, attendiamo
            wait_time = 0.0
            if self.tokens < tokens:
                # Calcola tempo necessario per avere abbastanza token
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.refill_rate

                logger.debug(
                    f"Rate limiter {self.name}: Throttling "
                    f"(tokens: {self.tokens:.2f}/{self.max_tokens}, "
                    f"waiting: {wait_time:.2f}s)"
                )

                self.throttled_count += 1
                await asyncio.sleep(wait_time)

                # Refill dopo wait
                self.tokens += wait_time * self.refill_rate
                self.last_refill_time = time.time()

            # Consume tokens
            self.tokens -= tokens
            self.total_requests += 1
            self.total_wait_time += wait_time

            return wait_time

    def can_proceed(self, tokens: float = 1.0) -> bool:
        """
        Check se possiamo procedere SENZA attendere

        Args:
            tokens: Numero token richiesti

        Returns:
            True se abbiamo abbastanza token
        """
        # Refill (non async, solo check)
        now = time.time()
        elapsed = now - self.last_refill_time
        current_tokens = min(
            self.max_tokens,
            self.tokens + elapsed * self.refill_rate
        )

        return current_tokens >= tokens

    def get_stats(self) -> Dict:
        """Statistiche rate limiter"""
        avg_wait = self.total_wait_time / self.total_requests if self.total_requests > 0 else 0.0
        throttle_rate = self.throttled_count / self.total_requests if self.total_requests > 0 else 0.0

        return {
            'name': self.name,
            'total_requests': self.total_requests,
            'throttled_count': self.throttled_count,
            'throttle_rate': throttle_rate,
            'avg_wait_time': avg_wait,
            'total_wait_time': self.total_wait_time,
            'current_tokens': self.tokens,
            'max_tokens': self.max_tokens,
            'refill_rate': self.refill_rate,
            'config': {
                'requests_per_second': self.config.requests_per_second,
                'burst_size': self.config.burst_size
            }
        }

    def reset_stats(self):
        """Reset statistiche (ma non token bucket)"""
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.throttled_count = 0
        logger.info(f"Rate limiter {self.name}: Stats reset")


class RateLimiterRegistry:
    """
    Registry globale per rate limiters
    Singleton per condividere stato tra provider
    """

    _instance: Optional['RateLimiterRegistry'] = None
    _limiters: Dict[str, TokenBucketRateLimiter] = {}

    # Rate limits default per exchange (req/s)
    DEFAULT_LIMITS = {
        'binance': RateLimiterConfig(requests_per_second=50.0, burst_size=100),
        'bybit': RateLimiterConfig(requests_per_second=50.0, burst_size=100),
        'okx': RateLimiterConfig(requests_per_second=20.0, burst_size=40),
        'coinbase': RateLimiterConfig(requests_per_second=10.0, burst_size=20),
        'cryptocom': RateLimiterConfig(requests_per_second=100.0, burst_size=200),  # 100 req/s public
        'kucoin': RateLimiterConfig(requests_per_second=10.0, burst_size=20),  # Conservative
        'coinglass': RateLimiterConfig(requests_per_second=0.5, burst_size=2),  # 30 req/min = 0.5 req/s
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._limiters = {}
        return cls._instance

    def get_limiter(
        self,
        exchange_name: str,
        config: Optional[RateLimiterConfig] = None
    ) -> TokenBucketRateLimiter:
        """
        Ottiene o crea rate limiter per exchange

        Args:
            exchange_name: Nome exchange
            config: Config custom (usa default se None)

        Returns:
            TokenBucketRateLimiter
        """
        if exchange_name not in self._limiters:
            # Usa config default se non specificato
            if config is None:
                config = self.DEFAULT_LIMITS.get(
                    exchange_name.lower(),
                    RateLimiterConfig()  # Fallback generico
                )

            self._limiters[exchange_name] = TokenBucketRateLimiter(exchange_name, config)
            logger.info(
                f"Rate limiter created: {exchange_name} "
                f"({config.requests_per_second} req/s, burst: {config.burst_size})"
            )

        return self._limiters[exchange_name]

    def get_all_stats(self) -> Dict[str, Dict]:
        """Statistiche tutti rate limiters"""
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}

    def reset_all_stats(self):
        """Reset statistiche tutti rate limiters"""
        for limiter in self._limiters.values():
            limiter.reset_stats()
