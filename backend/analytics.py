"""
Advanced Analytics Module per Trading Agent
Calcola metriche finanziarie e statistiche avanzate
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Metriche di performance complete"""
    # Periodo analisi
    start_date: str
    end_date: str
    days_analyzed: int

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # P&L metrics
    total_pnl_usd: float
    total_pnl_pct: float
    avg_win_usd: float
    avg_loss_usd: float
    avg_win_pct: float
    avg_loss_pct: float
    largest_win_usd: float
    largest_loss_usd: float
    profit_factor: float  # abs(total_wins) / abs(total_losses)

    # Risk-adjusted metrics
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    max_drawdown_usd: float
    max_drawdown_pct: float

    # Trading patterns
    avg_trade_duration_minutes: Optional[float]
    median_trade_duration_minutes: Optional[float]
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Direction breakdown
    long_trades: int
    short_trades: int
    long_win_rate: float
    short_win_rate: float
    long_pnl_usd: float
    short_pnl_usd: float

    # Costs
    total_fees_usd: float
    avg_fee_per_trade: float

    # AI Decision quality
    total_decisions: int
    decisions_executed: int
    execution_rate: float  # % decisioni effettivamente tradate

    def to_dict(self) -> Dict[str, Any]:
        """Converte a dictionary per JSON"""
        return asdict(self)


class TradingAnalytics:
    """
    Calcola metriche avanzate per analisi performance trading
    """

    def __init__(self, trades_df: pd.DataFrame, decisions_df: Optional[pd.DataFrame] = None):
        """
        Args:
            trades_df: DataFrame con colonne: created_at, closed_at, pnl_usd, pnl_pct,
                      direction, symbol, fees_usd, duration_minutes, status
            decisions_df: DataFrame con decisioni AI (opzionale per correlation analysis)
        """
        self.trades = trades_df
        self.decisions = decisions_df

        # Converti date se necessario
        if not pd.api.types.is_datetime64_any_dtype(self.trades['created_at']):
            self.trades['created_at'] = pd.to_datetime(self.trades['created_at'])
        if 'closed_at' in self.trades.columns:
            if not pd.api.types.is_datetime64_any_dtype(self.trades['closed_at']):
                self.trades['closed_at'] = pd.to_datetime(self.trades['closed_at'])

    def calculate_all_metrics(self) -> PerformanceMetrics:
        """Calcola tutte le metriche"""

        # Filtra solo trade chiusi per metriche P&L
        closed_trades = self.trades[self.trades['status'] == 'closed'].copy()

        if len(closed_trades) == 0:
            return self._empty_metrics()

        # Date range
        start_date = closed_trades['created_at'].min()
        end_date = closed_trades['closed_at'].max()
        days_analyzed = (end_date - start_date).days + 1

        # Basic statistics
        total_trades = len(closed_trades)
        winning_trades = len(closed_trades[closed_trades['pnl_usd'] > 0])
        losing_trades = len(closed_trades[closed_trades['pnl_usd'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L metrics
        wins = closed_trades[closed_trades['pnl_usd'] > 0]
        losses = closed_trades[closed_trades['pnl_usd'] < 0]

        total_pnl_usd = closed_trades['pnl_usd'].sum()
        total_pnl_pct = closed_trades['pnl_pct'].sum()

        avg_win_usd = wins['pnl_usd'].mean() if len(wins) > 0 else 0
        avg_loss_usd = losses['pnl_usd'].mean() if len(losses) > 0 else 0
        avg_win_pct = wins['pnl_pct'].mean() if len(wins) > 0 else 0
        avg_loss_pct = losses['pnl_pct'].mean() if len(losses) > 0 else 0

        largest_win_usd = wins['pnl_usd'].max() if len(wins) > 0 else 0
        largest_loss_usd = losses['pnl_usd'].min() if len(losses) > 0 else 0

        # Profit factor
        total_wins = wins['pnl_usd'].sum() if len(wins) > 0 else 0
        total_losses = abs(losses['pnl_usd'].sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Risk-adjusted metrics
        sharpe = self._calculate_sharpe_ratio(closed_trades)
        sortino = self._calculate_sortino_ratio(closed_trades)
        max_dd_usd, max_dd_pct = self._calculate_max_drawdown(closed_trades)
        calmar = abs(total_pnl_usd) / abs(max_dd_usd) if max_dd_usd != 0 else 0

        # Duration statistics
        if 'duration_minutes' in closed_trades.columns:
            durations = closed_trades['duration_minutes'].dropna()
            avg_duration = durations.mean() if len(durations) > 0 else None
            median_duration = durations.median() if len(durations) > 0 else None
        else:
            avg_duration = None
            median_duration = None

        # Consecutive wins/losses
        max_cons_wins, max_cons_losses = self._calculate_consecutive_streaks(closed_trades)

        # Direction breakdown
        longs = closed_trades[closed_trades['direction'] == 'long']
        shorts = closed_trades[closed_trades['direction'] == 'short']

        long_trades = len(longs)
        short_trades = len(shorts)
        long_win_rate = len(longs[longs['pnl_usd'] > 0]) / long_trades if long_trades > 0 else 0
        short_win_rate = len(shorts[shorts['pnl_usd'] > 0]) / short_trades if short_trades > 0 else 0
        long_pnl_usd = longs['pnl_usd'].sum()
        short_pnl_usd = shorts['pnl_usd'].sum()

        # Costs
        total_fees = closed_trades['fees_usd'].sum() if 'fees_usd' in closed_trades.columns else 0
        avg_fee = total_fees / total_trades if total_trades > 0 else 0

        # AI decisions (se disponibili)
        total_decisions = len(self.decisions) if self.decisions is not None else 0
        decisions_executed = total_trades  # Assumendo 1:1 mapping
        execution_rate = decisions_executed / total_decisions if total_decisions > 0 else 0

        return PerformanceMetrics(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            days_analyzed=days_analyzed,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl_usd=total_pnl_usd,
            total_pnl_pct=total_pnl_pct,
            avg_win_usd=avg_win_usd,
            avg_loss_usd=avg_loss_usd,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            largest_win_usd=largest_win_usd,
            largest_loss_usd=largest_loss_usd,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_usd=max_dd_usd,
            max_drawdown_pct=max_dd_pct,
            avg_trade_duration_minutes=avg_duration,
            median_trade_duration_minutes=median_duration,
            max_consecutive_wins=max_cons_wins,
            max_consecutive_losses=max_cons_losses,
            long_trades=long_trades,
            short_trades=short_trades,
            long_win_rate=long_win_rate,
            short_win_rate=short_win_rate,
            long_pnl_usd=long_pnl_usd,
            short_pnl_usd=short_pnl_usd,
            total_fees_usd=total_fees,
            avg_fee_per_trade=avg_fee,
            total_decisions=total_decisions,
            decisions_executed=decisions_executed,
            execution_rate=execution_rate
        )

    def generate_equity_curve(self) -> List[Dict[str, Any]]:
        """
        Genera equity curve (cumulative P&L nel tempo)

        Returns:
            Lista di dict con timestamp e cumulative_pnl
        """
        closed = self.trades[self.trades['status'] == 'closed'].copy()
        closed = closed.sort_values('closed_at')
        closed['cumulative_pnl'] = closed['pnl_usd'].cumsum()

        equity_curve = []
        for _, row in closed.iterrows():
            equity_curve.append({
                'timestamp': row['closed_at'].isoformat(),
                'cumulative_pnl_usd': float(row['cumulative_pnl']),
                'trade_pnl': float(row['pnl_usd']),
                'symbol': row['symbol'],
                'direction': row['direction']
            })

        return equity_curve

    def breakdown_by_symbol(self) -> Dict[str, Dict[str, Any]]:
        """Breakdown performance per simbolo"""
        closed = self.trades[self.trades['status'] == 'closed']
        breakdown = {}

        for symbol in closed['symbol'].unique():
            symbol_trades = closed[closed['symbol'] == symbol]

            wins = symbol_trades[symbol_trades['pnl_usd'] > 0]
            total = len(symbol_trades)

            breakdown[symbol] = {
                'total_trades': total,
                'win_rate': len(wins) / total if total > 0 else 0,
                'total_pnl_usd': float(symbol_trades['pnl_usd'].sum()),
                'avg_pnl_usd': float(symbol_trades['pnl_usd'].mean()),
                'best_trade': float(symbol_trades['pnl_usd'].max()),
                'worst_trade': float(symbol_trades['pnl_usd'].min())
            }

        return breakdown

    def breakdown_by_timeframe(self, timeframe: str = 'daily') -> List[Dict[str, Any]]:
        """
        Breakdown performance per periodo temporale

        Args:
            timeframe: 'daily', 'weekly', 'monthly'
        """
        closed = self.trades[self.trades['status'] == 'closed'].copy()

        freq_map = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
        freq = freq_map.get(timeframe, 'D')

        closed['period'] = closed['closed_at'].dt.to_period(freq)

        breakdown = []
        for period, group in closed.groupby('period'):
            wins = group[group['pnl_usd'] > 0]

            breakdown.append({
                'period': str(period),
                'trades': len(group),
                'wins': len(wins),
                'win_rate': len(wins) / len(group) if len(group) > 0 else 0,
                'pnl_usd': float(group['pnl_usd'].sum()),
                'fees_usd': float(group['fees_usd'].sum()) if 'fees_usd' in group.columns else 0
            })

        return breakdown

    # === HELPER METHODS ===

    def _calculate_sharpe_ratio(self, trades: pd.DataFrame, risk_free_rate: float = 0.0) -> Optional[float]:
        """Calcola Sharpe Ratio (annualizzato)"""
        if len(trades) < 2:
            return None

        # Returns giornalieri
        trades = trades.sort_values('closed_at')
        trades['daily_return'] = trades['pnl_pct'] / 100  # Converti % a decimale

        mean_return = trades['daily_return'].mean()
        std_return = trades['daily_return'].std()

        if std_return == 0:
            return None

        # Annualizza (assume 365 giorni)
        sharpe = (mean_return - risk_free_rate) / std_return * np.sqrt(365)
        return float(sharpe)

    def _calculate_sortino_ratio(self, trades: pd.DataFrame, risk_free_rate: float = 0.0) -> Optional[float]:
        """Calcola Sortino Ratio (considera solo downside volatility)"""
        if len(trades) < 2:
            return None

        trades = trades.sort_values('closed_at')
        trades['daily_return'] = trades['pnl_pct'] / 100

        mean_return = trades['daily_return'].mean()

        # Downside deviation (solo ritorni negativi)
        negative_returns = trades['daily_return'][trades['daily_return'] < 0]
        if len(negative_returns) == 0:
            return None

        downside_std = negative_returns.std()
        if downside_std == 0:
            return None

        sortino = (mean_return - risk_free_rate) / downside_std * np.sqrt(365)
        return float(sortino)

    def _calculate_max_drawdown(self, trades: pd.DataFrame) -> Tuple[float, float]:
        """
        Calcola Maximum Drawdown (USD e %)

        Returns:
            (max_dd_usd, max_dd_pct)
        """
        if len(trades) == 0:
            return 0.0, 0.0

        trades = trades.sort_values('closed_at')
        trades['cumulative_pnl'] = trades['pnl_usd'].cumsum()

        # Running maximum
        trades['running_max'] = trades['cumulative_pnl'].cummax()

        # Drawdown
        trades['drawdown'] = trades['cumulative_pnl'] - trades['running_max']

        max_dd_usd = abs(trades['drawdown'].min())

        # Drawdown %
        max_dd_pct = abs(trades['drawdown'].min() / trades['running_max'].max() * 100) if trades['running_max'].max() > 0 else 0

        return float(max_dd_usd), float(max_dd_pct)

    def _calculate_consecutive_streaks(self, trades: pd.DataFrame) -> Tuple[int, int]:
        """Calcola max consecutive wins e losses"""
        trades = trades.sort_values('closed_at')
        trades['is_win'] = trades['pnl_usd'] > 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for is_win in trades['is_win']:
            if is_win:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _empty_metrics(self) -> PerformanceMetrics:
        """Restituisce metriche vuote"""
        return PerformanceMetrics(
            start_date="",
            end_date="",
            days_analyzed=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl_usd=0.0,
            total_pnl_pct=0.0,
            avg_win_usd=0.0,
            avg_loss_usd=0.0,
            avg_win_pct=0.0,
            avg_loss_pct=0.0,
            largest_win_usd=0.0,
            largest_loss_usd=0.0,
            profit_factor=0.0,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=0.0,
            max_drawdown_usd=0.0,
            max_drawdown_pct=0.0,
            avg_trade_duration_minutes=None,
            median_trade_duration_minutes=None,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            long_trades=0,
            short_trades=0,
            long_win_rate=0.0,
            short_win_rate=0.0,
            long_pnl_usd=0.0,
            short_pnl_usd=0.0,
            total_fees_usd=0.0,
            avg_fee_per_trade=0.0,
            total_decisions=0,
            decisions_executed=0,
            execution_rate=0.0
        )
