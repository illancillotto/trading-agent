/**
 * BreakdownTables Component
 * Displays performance breakdowns by symbol and by day
 */

import React, { useState, useMemo } from 'react';
import { SymbolBreakdown, DailyBreakdown } from '../types/analytics';

interface BreakdownTablesProps {
  symbolBreakdown: SymbolBreakdown[];
  dailyBreakdown: DailyBreakdown[];
}

type SortField = keyof SymbolBreakdown | keyof DailyBreakdown;
type SortDirection = 'asc' | 'desc';

export const BreakdownTables: React.FC<BreakdownTablesProps> = ({
  symbolBreakdown,
  dailyBreakdown,
}) => {
  const [symbolSort, setSymbolSort] = useState<{
    field: SortField;
    direction: SortDirection;
  }>({ field: 'total_pnl_usd', direction: 'desc' });

  const [dailySort, setDailySort] = useState<{
    field: SortField;
    direction: SortDirection;
  }>({ field: 'date', direction: 'desc' });

  // Helper functions
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

  // Sorting functions
  const handleSymbolSort = (field: SortField) => {
    setSymbolSort((prev) => ({
      field,
      direction:
        prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const handleDailySort = (field: SortField) => {
    setDailySort((prev) => ({
      field,
      direction:
        prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  // Sorted data
  const sortedSymbolData = useMemo(() => {
    return [...symbolBreakdown].sort((a, b) => {
      const aVal = a[symbolSort.field as keyof SymbolBreakdown];
      const bVal = b[symbolSort.field as keyof SymbolBreakdown];

      if (aVal < bVal) return symbolSort.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return symbolSort.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [symbolBreakdown, symbolSort]);

  const sortedDailyData = useMemo(() => {
    return [...dailyBreakdown].sort((a, b) => {
      const aVal = a[dailySort.field as keyof DailyBreakdown];
      const bVal = b[dailySort.field as keyof DailyBreakdown];

      if (aVal < bVal) return dailySort.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return dailySort.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [dailyBreakdown, dailySort]);

  // Sort indicator component
  const SortIndicator: React.FC<{
    field: SortField;
    currentField: SortField;
    direction: SortDirection;
  }> = ({ field, currentField, direction }) => {
    if (field !== currentField) return <span className="text-gray-400 ml-1">↕</span>;
    return (
      <span className="text-blue-600 ml-1">{direction === 'asc' ? '↑' : '↓'}</span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Symbol Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800">
            Performance by Symbol
          </h3>
          <p className="text-sm text-gray-500">
            {symbolBreakdown.length} symbols traded
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('symbol')}
                >
                  Symbol
                  <SortIndicator
                    field="symbol"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('total_trades')}
                >
                  Trades
                  <SortIndicator
                    field="total_trades"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('win_rate')}
                >
                  Win Rate
                  <SortIndicator
                    field="win_rate"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('total_pnl_usd')}
                >
                  Total P&L
                  <SortIndicator
                    field="total_pnl_usd"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('avg_pnl_usd')}
                >
                  Avg P&L
                  <SortIndicator
                    field="avg_pnl_usd"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('best_trade_usd')}
                >
                  Best Trade
                  <SortIndicator
                    field="best_trade_usd"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSymbolSort('total_volume_usd')}
                >
                  Volume
                  <SortIndicator
                    field="total_volume_usd"
                    currentField={symbolSort.field}
                    direction={symbolSort.direction}
                  />
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedSymbolData.map((item, index) => (
                <tr key={item.symbol} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="font-semibold text-gray-900">{item.symbol}</span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-900">
                    {item.total_trades}
                    <span className="text-xs text-gray-500 ml-1">
                      ({item.winning_trades}W/{item.losing_trades}L)
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={`font-medium ${getWinRateColor(item.win_rate)}`}>
                      {formatPercent(item.win_rate)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={`font-semibold ${getPnlColor(item.total_pnl_usd)}`}>
                      {formatCurrency(item.total_pnl_usd)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={getPnlColor(item.avg_pnl_usd)}>
                      {formatCurrency(item.avg_pnl_usd)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-green-600">
                    {formatCurrency(item.best_trade_usd)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-600">
                    {formatCurrency(item.total_volume_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Daily Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800">Daily Performance</h3>
          <p className="text-sm text-gray-500">{dailyBreakdown.length} trading days</p>
        </div>

        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('date')}
                >
                  Date
                  <SortIndicator
                    field="date"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('total_trades')}
                >
                  Trades
                  <SortIndicator
                    field="total_trades"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('win_rate')}
                >
                  Win Rate
                  <SortIndicator
                    field="win_rate"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('pnl_usd')}
                >
                  P&L (USD)
                  <SortIndicator
                    field="pnl_usd"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('pnl_pct')}
                >
                  P&L (%)
                  <SortIndicator
                    field="pnl_pct"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
                <th
                  className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleDailySort('volume_usd')}
                >
                  Volume
                  <SortIndicator
                    field="volume_usd"
                    currentField={dailySort.field}
                    direction={dailySort.direction}
                  />
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedDailyData.map((item, index) => (
                <tr key={item.date} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                    {new Date(item.date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-900">
                    {item.total_trades}
                    <span className="text-xs text-gray-500 ml-1">
                      ({item.winning_trades}W/{item.losing_trades}L)
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={`font-medium ${getWinRateColor(item.win_rate)}`}>
                      {formatPercent(item.win_rate)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={`font-semibold ${getPnlColor(item.pnl_usd)}`}>
                      {formatCurrency(item.pnl_usd)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <span className={getPnlColor(item.pnl_pct)}>
                      {formatPercent(item.pnl_pct)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-600">
                    {formatCurrency(item.volume_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
