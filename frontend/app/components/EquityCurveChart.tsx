/**
 * EquityCurveChart Component
 * Interactive line chart showing cumulative P&L over time
 */

import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import { EquityCurvePoint } from '../types/analytics';

interface EquityCurveChartProps {
  data: EquityCurvePoint[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-gray-300 rounded-lg p-3 shadow-lg">
        <p className="text-sm font-semibold text-gray-700 mb-1">
          {new Date(label || '').toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          })}
        </p>
        <p
          className={`text-base font-bold ${
            data.cumulative_pnl >= 0 ? 'text-green-600' : 'text-red-600'
          }`}
        >
          P&L: $
          {data.cumulative_pnl.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </p>
        <p className="text-xs text-gray-500 mt-1">Trades: {data.trade_count}</p>
      </div>
    );
  }
  return null;
};

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <p className="text-gray-500">No equity curve data available</p>
      </div>
    );
  }

  // Determine if overall P&L is positive or negative
  const finalPnl = data[data.length - 1]?.cumulative_pnl || 0;
  const lineColor = finalPnl >= 0 ? '#10b981' : '#ef4444'; // green-500 : red-500

  // Format data for Recharts
  const chartData = data.map((point) => ({
    ...point,
    date: new Date(point.date).getTime(), // Convert to timestamp for XAxis
    displayDate: new Date(point.date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Equity Curve</h3>
        <p className="text-sm text-gray-500">Cumulative P&L over time</p>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />

          <XAxis
            dataKey="date"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(timestamp) =>
              new Date(timestamp).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })
            }
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />

          <YAxis
            tickFormatter={(value) =>
              `$${value.toLocaleString('en-US', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              })}`
            }
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
          />

          <Tooltip content={<CustomTooltip />} />

          <Legend
            wrapperStyle={{ fontSize: '14px', paddingTop: '20px' }}
            iconType="line"
          />

          <ReferenceLine
            y={0}
            stroke="#6b7280"
            strokeDasharray="3 3"
            strokeWidth={1}
          />

          <Line
            type="monotone"
            dataKey="cumulative_pnl"
            stroke={lineColor}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6 }}
            name="Cumulative P&L ($)"
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Summary Stats Below Chart */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
        <div className="text-center">
          <p className="text-sm text-gray-500">Total Trades</p>
          <p className="text-xl font-bold text-gray-900">
            {data[data.length - 1]?.trade_count || 0}
          </p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-500">Final P&L</p>
          <p
            className={`text-xl font-bold ${
              finalPnl >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            $
            {finalPnl.toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-500">Trading Days</p>
          <p className="text-xl font-bold text-gray-900">{data.length}</p>
        </div>
      </div>
    </div>
  );
};
