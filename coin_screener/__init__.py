"""
Coin Screener Module

Dynamic cryptocurrency selection system for the trading agent.
"""
from .screener import CoinScreener
from .models import (
    CoinScore,
    CoinScreenerResult,
    CoinMetrics,
    HardFilterConfig,
    ScoringWeights
)
from .filters import HardFilters
from .scoring import CoinScorer

__version__ = "1.0.0"

__all__ = [
    'CoinScreener',
    'CoinScore',
    'CoinScreenerResult',
    'CoinMetrics',
    'HardFilterConfig',
    'ScoringWeights',
    'HardFilters',
    'CoinScorer',
]
