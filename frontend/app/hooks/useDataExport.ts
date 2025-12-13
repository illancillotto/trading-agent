/**
 * Custom hook for Data Export & Analytics API calls
 */

import { useState, useCallback } from 'react';
import {
  ExportPreset,
  AnalyticsResponse,
  ExportResponse,
  BacktestResponse,
} from '../types/analytics';

const API_BASE_URL = 'http://localhost:8000';

interface UseDataExportReturn {
  // State
  loading: boolean;
  error: string | null;
  presets: ExportPreset[];
  analytics: AnalyticsResponse | null;

  // Methods
  fetchPresets: () => Promise<void>;
  exportFullDataset: (params: ExportParams) => Promise<void>;
  exportBacktest: (days: number) => Promise<void>;
  fetchAnalytics: (params: AnalyticsParams) => Promise<void>;
}

interface ExportParams {
  period?: string;
  days?: number;
  format?: 'json' | 'csv';
  includeContext?: boolean;
  includeMetrics?: boolean;
}

interface AnalyticsParams {
  days?: number;
  symbol?: string;
}

export const useDataExport = (): UseDataExportReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [presets, setPresets] = useState<ExportPreset[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);

  /**
   * Fetch available export presets
   */
  const fetchPresets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/export/presets`);
      if (!response.ok) {
        throw new Error(`Failed to fetch presets: ${response.statusText}`);
      }
      const data = await response.json();
      setPresets(data.presets || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Error fetching presets:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Export full dataset (JSON or CSV)
   */
  const exportFullDataset = useCallback(async (params: ExportParams) => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();

      if (params.period) queryParams.append('period', params.period);
      if (params.days) queryParams.append('days', params.days.toString());
      if (params.format) queryParams.append('format', params.format);
      if (params.includeContext !== undefined) {
        queryParams.append('include_context', params.includeContext.toString());
      }
      if (params.includeMetrics !== undefined) {
        queryParams.append('include_metrics', params.includeMetrics.toString());
      }

      const response = await fetch(
        `${API_BASE_URL}/api/export/full?${queryParams.toString()}`
      );

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      // Handle CSV download
      if (params.format === 'csv') {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading_data_${params.period || params.days}d_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        // Handle JSON download
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: 'application/json',
        });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading_data_${params.period || params.days}d_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Error exporting dataset:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Export backtest format data
   */
  const exportBacktest = useCallback(async (days: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/export/backtest?days=${days}`
      );

      if (!response.ok) {
        throw new Error(`Backtest export failed: ${response.statusText}`);
      }

      const data: BacktestResponse = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backtest_${days}d_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Error exporting backtest data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Fetch performance analytics
   */
  const fetchAnalytics = useCallback(async (params: AnalyticsParams) => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();

      if (params.days) queryParams.append('days', params.days.toString());
      if (params.symbol) queryParams.append('symbol', params.symbol);

      const response = await fetch(
        `${API_BASE_URL}/api/analytics/performance?${queryParams.toString()}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch analytics: ${response.statusText}`);
      }

      const data: AnalyticsResponse = await response.json();
      setAnalytics(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Error fetching analytics:', err);
      setAnalytics(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    presets,
    analytics,
    fetchPresets,
    exportFullDataset,
    exportBacktest,
    fetchAnalytics,
  };
};
