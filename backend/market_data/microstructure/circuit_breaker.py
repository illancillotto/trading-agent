"""
Circuit Breaker Pattern per prevenire cascade failure

Il circuit breaker impedisce che un exchange malfunzionante
degradi l'intero sistema microstructure.
"""

import time
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Stati del circuit breaker"""
    CLOSED = "closed"      # Normale operatività
    OPEN = "open"          # Circuito aperto, blocca richieste
    HALF_OPEN = "half_open"  # Test recovery


@dataclass
class CircuitBreakerConfig:
    """Configurazione circuit breaker"""
    failure_threshold: int = 5  # Fallimenti prima di aprire
    success_threshold: int = 2  # Successi per chiudere da half-open
    timeout: float = 60.0       # Secondi prima di tentare recovery
    half_open_max_calls: int = 3  # Max chiamate in half-open state


class CircuitBreaker:
    """
    Circuit Breaker per singolo exchange

    Pattern:
    - CLOSED: Operazione normale, conta fallimenti
    - OPEN: Blocca richieste, attende timeout
    - HALF_OPEN: Testa recovery con chiamate limitate
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """
        Verifica se la richiesta può essere eseguita

        Returns:
            True se può procedere, False se bloccato
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Controlla se è il momento di tentare recovery
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name}: Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Limita chiamate in half-open
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False

        return False

    def record_success(self):
        """Registra successo"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(f"Circuit breaker {self.name}: Success {self.success_count}/{self.config.success_threshold}")

            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker {self.name}: Closing circuit")
                self._close()

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self, error: Exception):
        """Registra fallimento"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        logger.warning(
            f"Circuit breaker {self.name}: Failure {self.failure_count}/{self.config.failure_threshold} - {error}"
        )

        if self.state == CircuitState.HALF_OPEN:
            # Fallimento in half-open riapre immediatamente
            logger.error(f"Circuit breaker {self.name}: Opening circuit (failed during recovery)")
            self._open()

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                logger.error(f"Circuit breaker {self.name}: Opening circuit (threshold reached)")
                self._open()

    def _should_attempt_reset(self) -> bool:
        """Verifica se tentare reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout

    def _open(self):
        """Apre circuito"""
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0

    def _close(self):
        """Chiude circuito"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

    def get_stats(self) -> Dict:
        """Statistiche circuit breaker"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'success_threshold': self.config.success_threshold,
                'timeout': self.config.timeout
            }
        }

    def reset(self):
        """Reset manuale"""
        logger.info(f"Circuit breaker {self.name}: Manual reset")
        self._close()
        self.last_failure_time = None


class CircuitBreakerRegistry:
    """
    Registry globale per circuit breakers
    Singleton per condividere stato tra provider
    """

    _instance: Optional['CircuitBreakerRegistry'] = None
    _breakers: Dict[str, CircuitBreaker] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._breakers = {}
        return cls._instance

    def get_breaker(self, exchange_name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Ottiene o crea circuit breaker per exchange"""
        if exchange_name not in self._breakers:
            self._breakers[exchange_name] = CircuitBreaker(exchange_name, config)
        return self._breakers[exchange_name]

    def get_all_stats(self) -> Dict[str, Dict]:
        """Statistiche tutti circuit breakers"""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

    def reset_all(self):
        """Reset tutti circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()

    def reset_exchange(self, exchange_name: str):
        """Reset circuit breaker specifico"""
        if exchange_name in self._breakers:
            self._breakers[exchange_name].reset()
