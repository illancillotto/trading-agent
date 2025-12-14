"""
Performance Metrics Calculator for Trading Agent
Calculates Sharpe Ratio and other risk-adjusted metrics (NOF1.ai)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    sharpe_ratio: float
    total_return_pct: float
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    avg_rr: float  # Average Risk-Reward ratio (avg_win / abs(avg_loss))
    max_drawdown_pct: float
    consecutive_losses: int
    total_trades: int
    profitable_trades: int

    def to_prompt_string(self) -> str:
        """Format metrics for inclusion in system prompt"""
        sharpe_interpretation = self._interpret_sharpe()

        return f"""**Your Performance Metrics:**
- Sharpe Ratio: {self.sharpe_ratio:.2f} ({sharpe_interpretation})
- Total Return: {self.total_return_pct:+.2f}%
- Win Rate: {self.win_rate:.1f}% ({self.profitable_trades}/{self.total_trades} trades)
- Avg Win: +{self.avg_win_pct:.2f}% | Avg Loss: {self.avg_loss_pct:.2f}%
- Avg R:R: {self.avg_rr:.2f}:1
- Max Drawdown: {self.max_drawdown_pct:.2f}%
- Consecutive Losses: {self.consecutive_losses}"""

    def _interpret_sharpe(self) -> str:
        """Interpret Sharpe ratio with actionable advice"""
        if self.sharpe_ratio < 0:
            return "⚠️ LOSING - reduce size, tighten stops"
        elif self.sharpe_ratio < 1:
            return "⚡ VOLATILE - maintain discipline"
        elif self.sharpe_ratio < 2:
            return "✅ GOOD - strategy working"
        else:
            return "🌟 EXCELLENT - don't get overconfident"


class PerformanceCalculator:
    """Calculates trading performance metrics including Sharpe Ratio"""

    RISK_FREE_RATE_ANNUAL = 0.05  # 5% annual risk-free rate
    TRADING_DAYS_PER_YEAR = 365  # Crypto trades 24/7

    def __init__(self, db_utils=None):
        """
        Initialize calculator.

        Args:
            db_utils: Database utilities module with get_closed_trades() and get_account_snapshots()
        """
        self.db_utils = db_utils

    def calculate_metrics(
        self,
        closed_trades: List[Dict],
        account_snapshots: List[Dict],
        lookback_days: int = 30
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            closed_trades: List of closed trade records with pnl_usd, pnl_pct, closed_at
            account_snapshots: List of account value snapshots over time
            lookback_days: Number of days to analyze

        Returns:
            PerformanceMetrics object
        """
        if not closed_trades:
            return PerformanceMetrics(
                sharpe_ratio=0.0,
                total_return_pct=0.0,
                win_rate=0.0,
                avg_win_pct=0.0,
                avg_loss_pct=0.0,
                avg_rr=0.0,
                max_drawdown_pct=0.0,
                consecutive_losses=0,
                total_trades=0,
                profitable_trades=0
            )

        # Filter trades within lookback period
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        recent_trades = [
            t for t in closed_trades
            if self._get_closed_at(t) >= cutoff_date
        ]

        if not recent_trades:
            # Fallback to last 20 trades if no recent trades
            recent_trades = closed_trades[-20:] if len(closed_trades) >= 20 else closed_trades

        # Calculate returns
        returns = [t.get('pnl_pct', 0) / 100 for t in recent_trades]

        # Sharpe Ratio
        sharpe = self._calculate_sharpe_ratio(returns)

        # Win/Loss stats
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        win_rate = (len(wins) / len(returns) * 100) if returns else 0
        avg_win = (sum(wins) / len(wins) * 100) if wins else 0
        avg_loss = (sum(losses) / len(losses) * 100) if losses else 0

        # Calculate average risk-reward ratio
        # avg_rr = avg_win / abs(avg_loss)
        if avg_loss != 0:
            avg_rr = avg_win / abs(avg_loss)
        elif avg_win > 0:
            avg_rr = 999.0  # Very high R:R if only wins
        else:
            avg_rr = 0.0

        # Total return
        total_return = sum(returns) * 100

        # Max drawdown from snapshots
        max_dd = self._calculate_max_drawdown(account_snapshots)

        # Consecutive losses
        consec_losses = self._count_consecutive_losses(returns)

        return PerformanceMetrics(
            sharpe_ratio=sharpe,
            total_return_pct=total_return,
            win_rate=win_rate,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            avg_rr=avg_rr,
            max_drawdown_pct=max_dd,
            consecutive_losses=consec_losses,
            total_trades=len(recent_trades),
            profitable_trades=len(wins)
        )

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """
        Calculate annualized Sharpe Ratio.

        Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns

        Args:
            returns: List of returns as decimals (e.g., 0.02 for 2%)

        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)

        # Variance and std dev
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0.001  # Avoid division by zero

        # Daily risk-free rate
        daily_rf = self.RISK_FREE_RATE_ANNUAL / self.TRADING_DAYS_PER_YEAR

        # Sharpe ratio (annualized)
        # Assuming each trade represents roughly 1 day of exposure
        excess_return = mean_return - daily_rf
        sharpe = (excess_return / std_dev) * math.sqrt(self.TRADING_DAYS_PER_YEAR)

        return round(sharpe, 2)

    def _calculate_max_drawdown(self, snapshots: List[Dict]) -> float:
        """
        Calculate maximum drawdown from account snapshots.

        Args:
            snapshots: List of dicts with 'balance_usd' and 'timestamp'

        Returns:
            Max drawdown as percentage
        """
        if not snapshots:
            return 0.0

        values = [s.get('balance_usd', 0) for s in snapshots]
        if not values or max(values) == 0:
            return 0.0

        peak = values[0]
        max_dd = 0.0

        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            max_dd = max(max_dd, drawdown)

        return round(max_dd, 2)

    def _count_consecutive_losses(self, returns: List[float]) -> int:
        """
        Count current streak of consecutive losses.

        Args:
            returns: List of returns as decimals

        Returns:
            Number of consecutive losses from most recent
        """
        if not returns:
            return 0

        # Count from most recent backwards
        count = 0
        for r in reversed(returns):
            if r < 0:
                count += 1
            else:
                break

        return count

    def _get_closed_at(self, trade: Dict) -> datetime:
        """
        Extract closed_at timestamp from trade dict, with fallback.

        Args:
            trade: Trade dict

        Returns:
            datetime object
        """
        closed_at = trade.get('closed_at')
        if isinstance(closed_at, datetime):
            return closed_at
        elif isinstance(closed_at, str):
            try:
                return datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
            except:
                pass

        # Fallback to current time if can't parse
        return datetime.now(timezone.utc)

    def get_metrics_from_db(self, lookback_days: int = 30) -> PerformanceMetrics:
        """
        Fetch data from database and calculate metrics.

        Requires db_utils to be set with methods:
        - get_closed_trades(lookback_days)
        - get_account_snapshots(lookback_days)

        Args:
            lookback_days: Number of days to look back

        Returns:
            PerformanceMetrics object
        """
        if not self.db_utils:
            logger.warning("No db_utils configured, returning empty metrics")
            return PerformanceMetrics(
                sharpe_ratio=0.0, total_return_pct=0.0, win_rate=0.0,
                avg_win_pct=0.0, avg_loss_pct=0.0, avg_rr=0.0, max_drawdown_pct=0.0,
                consecutive_losses=0, total_trades=0, profitable_trades=0
            )

        try:
            closed_trades = self.db_utils.get_closed_trades(lookback_days)
            snapshots = self.db_utils.get_account_snapshots(lookback_days)
            return self.calculate_metrics(closed_trades, snapshots, lookback_days)
        except Exception as e:
            logger.error(f"Error fetching metrics from DB: {e}", exc_info=True)
            return PerformanceMetrics(
                sharpe_ratio=0.0, total_return_pct=0.0, win_rate=0.0,
                avg_win_pct=0.0, avg_loss_pct=0.0, avg_rr=0.0, max_drawdown_pct=0.0,
                consecutive_losses=0, total_trades=0, profitable_trades=0
            )


# Singleton instance
_calculator: Optional[PerformanceCalculator] = None


def get_performance_calculator(db_utils=None) -> PerformanceCalculator:
    """
    Get or create the performance calculator singleton.

    Args:
        db_utils: Database utilities module (optional)

    Returns:
        PerformanceCalculator instance
    """
    global _calculator
    if _calculator is None:
        _calculator = PerformanceCalculator(db_utils)
    elif db_utils is not None:
        _calculator.db_utils = db_utils
    return _calculator


# Example usage for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example trades
    example_trades = [
        {'pnl_pct': 2.5, 'closed_at': datetime.now(timezone.utc)},
        {'pnl_pct': -1.0, 'closed_at': datetime.now(timezone.utc)},
        {'pnl_pct': 3.0, 'closed_at': datetime.now(timezone.utc)},
        {'pnl_pct': 1.5, 'closed_at': datetime.now(timezone.utc)},
        {'pnl_pct': -2.0, 'closed_at': datetime.now(timezone.utc)},
    ]

    # Example snapshots
    example_snapshots = [
        {'balance_usd': 1000, 'timestamp': datetime.now(timezone.utc)},
        {'balance_usd': 1025, 'timestamp': datetime.now(timezone.utc)},
        {'balance_usd': 1015, 'timestamp': datetime.now(timezone.utc)},
        {'balance_usd': 1045, 'timestamp': datetime.now(timezone.utc)},
        {'balance_usd': 1025, 'timestamp': datetime.now(timezone.utc)},
    ]

    calc = PerformanceCalculator()
    metrics = calc.calculate_metrics(example_trades, example_snapshots, lookback_days=30)

    print("📊 Performance Metrics:")
    print(metrics.to_prompt_string())
    print(f"\nSharpe Ratio: {metrics.sharpe_ratio}")
    print(f"Win Rate: {metrics.win_rate:.1f}%")
    print(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
