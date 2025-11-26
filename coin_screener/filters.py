"""
Hard filters for coin screening
"""
import logging
from typing import List, Tuple
from .models import CoinMetrics, HardFilterConfig

logger = logging.getLogger(__name__)


class HardFilters:
    """Apply hard filters to exclude unsuitable coins"""

    def __init__(self, config: HardFilterConfig = None):
        self.config = config or HardFilterConfig()

    def apply_filters(self, coins: List[CoinMetrics]) -> Tuple[List[CoinMetrics], List[str]]:
        """
        Apply all hard filters to a list of coins.

        Args:
            coins: List of CoinMetrics to filter

        Returns:
            Tuple of (passing_coins, excluded_coin_symbols)
        """
        passing = []
        excluded = []

        for coin in coins:
            reason = self._check_coin(coin)
            if reason is None:
                passing.append(coin)
            else:
                excluded.append(coin.symbol)
                logger.debug(f"Excluded {coin.symbol}: {reason}")

        logger.info(
            f"Hard filters: {len(passing)}/{len(coins)} coins passed, "
            f"{len(excluded)} excluded"
        )

        return passing, excluded

    def _check_coin(self, coin: CoinMetrics) -> str | None:
        """
        Check if a coin passes all hard filters.

        Args:
            coin: CoinMetrics to check

        Returns:
            None if passed, or reason string if excluded
        """
        # Stablecoin filter
        if self.config.exclude_stablecoins:
            if coin.is_stablecoin or coin.symbol in self.config.stablecoin_symbols:
                return "stablecoin"

        # Volume filter
        if coin.volume_24h_usd < self.config.min_volume_24h_usd:
            return f"volume too low (${coin.volume_24h_usd:,.0f} < ${self.config.min_volume_24h_usd:,.0f})"

        # Market cap filter
        if coin.market_cap_usd < self.config.min_market_cap_usd:
            return f"market cap too low (${coin.market_cap_usd:,.0f} < ${self.config.min_market_cap_usd:,.0f})"

        # Days listed filter
        if coin.days_listed < self.config.min_days_listed:
            return f"too new ({coin.days_listed} days < {self.config.min_days_listed} days)"

        # Open interest filter
        if coin.open_interest_usd < self.config.min_open_interest_usd:
            return f"OI too low (${coin.open_interest_usd:,.0f} < ${self.config.min_open_interest_usd:,.0f})"

        # Spread filter
        if coin.spread_pct > self.config.max_spread_pct:
            return f"spread too wide ({coin.spread_pct:.3f}% > {self.config.max_spread_pct}%)"

        return None

    def check_single_coin(self, coin: CoinMetrics) -> bool:
        """
        Check if a single coin passes all filters.

        Args:
            coin: CoinMetrics to check

        Returns:
            True if passes, False otherwise
        """
        return self._check_coin(coin) is None
