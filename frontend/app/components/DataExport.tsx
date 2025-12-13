/**
 * DataExport Component
 * Main component for Data Export & Analytics dashboard
 */

import React, { useEffect, useState } from 'react';
import { useDataExport } from '../hooks/useDataExport';
import { PerformanceMetrics } from './PerformanceMetrics';
import { EquityCurveChart } from './EquityCurveChart';
import { BreakdownTables } from './BreakdownTables';

export const DataExport: React.FC = () => {
  const {
    loading,
    error,
    presets,
    analytics,
    fetchPresets,
    exportFullDataset,
    exportBacktest,
    fetchAnalytics,
  } = useDataExport();

  // Local state
  const [selectedPeriod, setSelectedPeriod] = useState<string>('7d');
  const [selectedFormat, setSelectedFormat] = useState<'json' | 'csv'>('json');
  const [includeContext, setIncludeContext] = useState<boolean>(true);
  const [includeMetrics, setIncludeMetrics] = useState<boolean>(true);
  const [analyticsPeriod, setAnalyticsPeriod] = useState<number>(30);

  // Fetch presets and initial analytics on mount
  useEffect(() => {
    fetchPresets();
    fetchAnalytics({ days: analyticsPeriod });
  }, []);

  // Handlers
  const handleExport = async () => {
    await exportFullDataset({
      period: selectedPeriod,
      format: selectedFormat,
      includeContext,
      includeMetrics,
    });
  };

  const handleBacktestExport = async () => {
    await exportBacktest(analyticsPeriod);
  };

  const handleAnalyticsPeriodChange = (days: number) => {
    setAnalyticsPeriod(days);
    fetchAnalytics({ days });
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Data Export & Analytics
        </h2>
        <p className="text-gray-600">
          Export trading data and analyze performance with advanced metrics
        </p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg
              className="w-5 h-5 text-red-600 mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-red-800 font-medium">{error}</span>
          </div>
        </div>
      )}

      {/* Export Controls */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Export Data</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {/* Period Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Period
            </label>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              {presets.map((preset) => (
                <option key={preset.key} value={preset.key}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>

          {/* Format Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Format
            </label>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value as 'json' | 'csv')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </select>
          </div>

          {/* Include Context */}
          <div className="flex items-center">
            <div className="pt-7">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeContext}
                  onChange={(e) => setIncludeContext(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Include Context</span>
              </label>
            </div>
          </div>

          {/* Include Metrics */}
          <div className="flex items-center">
            <div className="pt-7">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeMetrics}
                  onChange={(e) => setIncludeMetrics(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Include Metrics</span>
              </label>
            </div>
          </div>
        </div>

        {/* Export Buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleExport}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Exporting...
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                Export Full Dataset
              </>
            )}
          </button>

          <button
            onClick={handleBacktestExport}
            disabled={loading}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center"
          >
            {loading ? (
              'Exporting...'
            ) : (
              <>
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                Export Backtest Format
              </>
            )}
          </button>
        </div>

        <div className="mt-3 text-sm text-gray-500">
          <p>
            Full Dataset: Complete export with trades, decisions, snapshots, and
            analytics
          </p>
          <p>Backtest Format: Decision-to-trade correlation data for backtesting</p>
        </div>
      </div>

      {/* Analytics Period Selection */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Analytics Dashboard
        </h3>

        <div className="flex flex-wrap gap-2 mb-4">
          {[7, 14, 30, 60, 90, 180, 365].map((days) => (
            <button
              key={days}
              onClick={() => handleAnalyticsPeriodChange(days)}
              className={`px-4 py-2 rounded-md transition-colors ${
                analyticsPeriod === days
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {days}d
            </button>
          ))}
        </div>
      </div>

      {/* Analytics Display */}
      {loading && !analytics && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <svg
            className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-gray-600">Loading analytics...</p>
        </div>
      )}

      {analytics && (
        <>
          {/* Performance Metrics */}
          <PerformanceMetrics metrics={analytics.metrics} />

          {/* Equity Curve */}
          <EquityCurveChart data={analytics.equity_curve} />

          {/* Breakdown Tables */}
          <BreakdownTables
            symbolBreakdown={analytics.breakdown_by_symbol}
            dailyBreakdown={analytics.breakdown_by_day}
          />
        </>
      )}

      {!loading && !analytics && !error && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <svg
            className="w-16 h-16 text-gray-400 mx-auto mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="text-gray-600 text-lg">No analytics data available</p>
          <p className="text-gray-500 text-sm mt-2">
            Select a period to view performance analytics
          </p>
        </div>
      )}
    </div>
  );
};
