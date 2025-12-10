"""
Utility functions per microstructure module

Include retry decorator, error handling, helpers.
"""

import asyncio
import functools
from typing import Callable, TypeVar, Optional, Type, Tuple
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger_func: Optional[Callable] = None
):
    """
    Decorator per retry automatico di funzioni async

    Args:
        max_attempts: Numero massimo di tentativi
        delay: Delay iniziale tra retry (secondi)
        backoff: Moltiplicatore delay (exponential backoff)
        exceptions: Tuple di eccezioni da catturare per retry
        logger_func: Logger custom (usa logger module se None)

    Example:
        @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
        async def fetch_data():
            # May fail and will be retried
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            _logger = logger_func or logger
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 1:
                        _logger.info(f"{func.__name__}: Success on attempt {attempt}/{max_attempts}")
                    return result

                except exceptions as e:
                    if attempt == max_attempts:
                        _logger.error(
                            f"{func.__name__}: Failed after {max_attempts} attempts - {type(e).__name__}: {e}"
                        )
                        raise

                    _logger.warning(
                        f"{func.__name__}: Attempt {attempt}/{max_attempts} failed - "
                        f"{type(e).__name__}: {e}. Retrying in {current_delay:.1f}s..."
                    )

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # Should never reach here
            raise RuntimeError(f"{func.__name__}: Unexpected retry logic error")

        return wrapper
    return decorator


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Divisione sicura che gestisce zero division

    Args:
        numerator: Numeratore
        denominator: Denominatore
        default: Valore default se divisione per zero

    Returns:
        Risultato divisione o default
    """
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calcola variazione percentuale

    Args:
        old_value: Valore precedente
        new_value: Valore nuovo

    Returns:
        Variazione percentuale
    """
    if old_value == 0:
        return 0.0 if new_value == 0 else 100.0
    return ((new_value - old_value) / old_value) * 100.0


def format_usd(amount: float, decimals: int = 2) -> str:
    """
    Formatta amount USD con separatori migliaia

    Args:
        amount: Amount in USD
        decimals: Decimali

    Returns:
        String formattata (es. "$1,234.56")
    """
    return f"${amount:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Formatta percentuale

    Args:
        value: Valore percentuale (0-100)
        decimals: Decimali

    Returns:
        String formattata (es. "12.34%")
    """
    return f"{value:.{decimals}f}%"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Limita valore tra min e max

    Args:
        value: Valore da limitare
        min_val: Valore minimo
        max_val: Valore massimo

    Returns:
        Valore limitato
    """
    return max(min_val, min(value, max_val))


def weighted_average(values: list, weights: list) -> float:
    """
    Calcola media ponderata

    Args:
        values: Lista valori
        weights: Lista pesi (stessa lunghezza)

    Returns:
        Media ponderata
    """
    if not values or not weights or len(values) != len(weights):
        return 0.0

    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    return sum(v * w for v, w in zip(values, weights)) / total_weight


class ExchangeError(Exception):
    """Base exception per errori exchange"""
    def __init__(self, exchange: str, message: str):
        self.exchange = exchange
        self.message = message
        super().__init__(f"[{exchange}] {message}")


class RateLimitError(ExchangeError):
    """Errore rate limit exceeded"""
    pass


class CircuitBreakerOpenError(ExchangeError):
    """Errore circuit breaker aperto"""
    pass


class OrderBookNotAvailableError(ExchangeError):
    """Order book non disponibile"""
    pass
