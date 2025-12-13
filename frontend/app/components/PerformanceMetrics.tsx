/**
 * PerformanceMetrics Component
 * Displays key performance metrics in color-coded cards
 */

import React from 'react';
import { PerformanceMetrics as MetricsType } from '../types/analytics';

interface PerformanceMetricsProps {
  metrics: MetricsType;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  colorClass?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtitle,
  colorClass = 'text-gray-900',
}) => (
  <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
    <div className="text-sm font-medium text-gray-500 mb-1">{label}</div>
    <div className={`text-2xl font-bold ${colorClass}`}>{value}</div>
    {subtitle && <div className="text-xs text-gray-400 mt-1">{subtitle}</div>}
  </div>
);

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ metrics }) => {
  // Helper functions for formatting
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number): string => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const formatNumber = (value: number, decimals: number = 2): string => {
    return value.toFixed(decimals);
  };

  // Color classes based on values
  const getPnlColor = (value: number): string => {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-900';
  };

  const getWinRateColor = (value: number): string => {
    if (value >= 0.6) return 'text-green-600';
    if (value >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getRatioColor = (value: number | null, threshold: number = 1): string => {
    if (value === null) return 'text-gray-400';
    if (value >= threshold) return 'text-green-600';
    if (value >= threshold * 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* Overview Metrics */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">Overview</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Trades"
            value={metrics.total_trades}
            subtitle={`${metrics.trades_long} long / ${metrics.trades_short} short`}
          />
          <MetricCard
            label="Win Rate"
            value={formatPercent(metrics.win_rate)}
            subtitle={`${metrics.winning_trades}W / ${metrics.losing_trades}L`}
            colorClass={getWinRateColor(metrics.win_rate)}
          />
          <MetricCard
            label="Total P&L"
            value={formatCurrency(metrics.total_pnl_usd)}
            subtitle={`${formatPercent(metrics.total_pnl_pct)} avg`}
            colorClass={getPnlColor(metrics.total_pnl_usd)}
          />
          <MetricCard
            label="Net P&L (After Fees)"
            value={formatCurrency(metrics.net_pnl_after_fees_usd)}
            subtitle={`Fees: ${formatCurrency(metrics.total_fees_usd)}`}
            colorClass={getPnlColor(metrics.net_pnl_after_fees_usd)}
          />
        </div>
      </div>

      {/* Risk Metrics */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">Risk Metrics</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Sharpe Ratio"
            value={metrics.sharpe_ratio !== null ? formatNumber(metrics.sharpe_ratio) : 'N/A'}
            subtitle="Risk-adjusted return"
            colorClass={getRatioColor(metrics.sharpe_ratio, 1)}
          />
          <MetricCard
            label="Sortino Ratio"
            value={metrics.sortino_ratio !== null ? formatNumber(metrics.sortino_ratio) : 'N/A'}
            subtitle="Downside risk"
            colorClass={getRatioColor(metrics.sortino_ratio, 1)}
          />
          <MetricCard
            label="Max Drawdown"
            value={formatCurrency(metrics.max_drawdown_usd)}
            subtitle={`${formatPercent(metrics.max_drawdown_pct)} / ${metrics.max_drawdown_duration_days}d`}
            colorClass="text-red-600"
          />
          <MetricCard
            label="Calmar Ratio"
            value={formatNumber(metrics.calmar_ratio)}
            subtitle="Return / Max DD"
            colorClass={getRatioColor(metrics.calmar_ratio, 1)}
          />
        </div>
      </div>

      {/* Trade Analysis */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">Trade Analysis</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Profit Factor"
            value={formatNumber(metrics.profit_factor)}
            subtitle="Gross profit / Gross loss"
            colorClass={getRatioColor(metrics.profit_factor, 1.5)}
          />
          <MetricCard
            label="Avg Win"
            value={formatCurrency(metrics.avg_win_usd)}
            subtitle={formatPercent(metrics.avg_win_pct)}
            colorClass="text-green-600"
          />
          <MetricCard
            label="Avg Loss"
            value={formatCurrency(metrics.avg_loss_usd)}
            subtitle={formatPercent(metrics.avg_loss_pct)}
            colorClass="text-red-600"
          />
          <MetricCard
            label="Best Trade"
            value={formatCurrency(metrics.best_trade_usd)}
            subtitle={formatPercent(metrics.best_trade_pct)}
            colorClass="text-green-600"
          />
        </div>
      </div>

      {/* Position Analysis */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">Position Analysis</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Long P&L"
            value={formatCurrency(metrics.pnl_long_usd)}
            subtitle={`Win rate: ${formatPercent(metrics.win_rate_long)}`}
            colorClass={getPnlColor(metrics.pnl_long_usd)}
          />
          <MetricCard
            label="Short P&L"
            value={formatCurrency(metrics.pnl_short_usd)}
            subtitle={`Win rate: ${formatPercent(metrics.win_rate_short)}`}
            colorClass={getPnlColor(metrics.pnl_short_usd)}
          />
          <MetricCard
            label="Avg Trade Duration"
            value={`${formatNumber(metrics.avg_trade_duration_hours, 1)}h`}
            subtitle={`${metrics.trading_days} trading days`}
          />
          <MetricCard
            label="Current Streak"
            value={`${metrics.current_streak} ${metrics.current_streak_type}`}
            subtitle={`Best: ${metrics.longest_win_streak}W / ${metrics.longest_loss_streak}L`}
            colorClass={
              metrics.current_streak_type === 'win'
                ? 'text-green-600'
                : metrics.current_streak_type === 'loss'
                ? 'text-red-600'
                : 'text-gray-600'
            }
          />
        </div>
      </div>

      {/* Volume & Activity */}
      <div>
        <h3 className="text-lg font-semibold mb-3 text-gray-800">Volume & Activity</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Volume"
            value={formatCurrency(metrics.total_volume_usd)}
            subtitle={`Avg: ${formatCurrency(metrics.avg_volume_per_trade_usd)}/trade`}
          />
          <MetricCard
            label="Avg Trades/Day"
            value={formatNumber(metrics.avg_trades_per_day, 1)}
            subtitle={`${metrics.trading_days} days`}
          />
          <MetricCard
            label="Recovery Factor"
            value={formatNumber(metrics.recovery_factor)}
            subtitle="Net profit / Max DD"
            colorClass={getRatioColor(metrics.recovery_factor, 2)}
          />
          <MetricCard
            label="Trading Period"
            value={
              metrics.first_trade_date && metrics.last_trade_date
                ? `${new Date(metrics.first_trade_date).toLocaleDateString()}`
                : 'N/A'
            }
            subtitle={
              metrics.last_trade_date
                ? `to ${new Date(metrics.last_trade_date).toLocaleDateString()}`
                : ''
            }
          />
        </div>
      </div>
    </div>
  );
};
