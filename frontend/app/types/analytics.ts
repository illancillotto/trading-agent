/**
 * TypeScript type definitions for Data Export & Analytics
 */

export interface ExportPreset {
  key: string;
  days: number;
  label: string;
}

export interface PerformanceMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  breakeven_trades: number;
  win_rate: number;
  total_pnl_usd: number;
  total_pnl_pct: number;
  avg_pnl_usd: number;
  avg_pnl_pct: number;
  avg_win_usd: number;
  avg_win_pct: number;
  avg_loss_usd: number;
  avg_loss_pct: number;
  best_trade_usd: number;
  best_trade_pct: number;
  worst_trade_usd: number;
  worst_trade_pct: number;
  profit_factor: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_usd: number;
  max_drawdown_pct: number;
  max_drawdown_duration_days: number;
  calmar_ratio: number;
  recovery_factor: number;
  avg_trade_duration_hours: number;
  longest_win_streak: number;
  longest_loss_streak: number;
  current_streak: number;
  current_streak_type: 'win' | 'loss' | 'neutral';
  total_fees_usd: number;
  net_pnl_after_fees_usd: number;
  avg_fee_per_trade_usd: number;
  trades_long: number;
  trades_short: number;
  pnl_long_usd: number;
  pnl_short_usd: number;
  win_rate_long: number;
  win_rate_short: number;
  first_trade_date: string | null;
  last_trade_date: string | null;
  trading_days: number;
  avg_trades_per_day: number;
  total_volume_usd: number;
  avg_volume_per_trade_usd: number;
}

export interface EquityCurvePoint {
  date: string;
  cumulative_pnl: number;
  trade_count: number;
}

export interface SymbolBreakdown {
  symbol: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl_usd: number;
  total_pnl_pct: number;
  avg_pnl_usd: number;
  best_trade_usd: number;
  worst_trade_usd: number;
  total_volume_usd: number;
}

export interface DailyBreakdown {
  date: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  pnl_usd: number;
  pnl_pct: number;
  volume_usd: number;
}

export interface AnalyticsResponse {
  metrics: PerformanceMetrics;
  equity_curve: EquityCurvePoint[];
  breakdown_by_symbol: SymbolBreakdown[];
  breakdown_by_day: DailyBreakdown[];
}

export interface ExportTrade {
  id: number;
  symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl_usd: number;
  pnl_pct: number;
  fees_usd: number;
  created_at: string;
  closed_at: string;
  duration_hours: number;
  status: string;
}

export interface ExportDecision {
  id: number;
  timestamp: string;
  symbol: string;
  decision: string;
  confidence: number;
  reasoning: string;
  context?: any;
}

export interface ExportResponse {
  summary: {
    total_trades: number;
    total_decisions: number;
    total_account_snapshots: number;
    total_llm_usage: number;
    total_errors: number;
    period_start: string;
    period_end: string;
  };
  trades: ExportTrade[];
  decisions: ExportDecision[];
  account_snapshots?: any[];
  llm_usage?: any[];
  errors?: any[];
  analytics?: {
    performance_metrics: PerformanceMetrics;
    equity_curve: EquityCurvePoint[];
    breakdown_by_symbol: SymbolBreakdown[];
    breakdown_by_day: DailyBreakdown[];
  };
}

export interface BacktestDecision {
  id: number;
  timestamp: string;
  symbol: string;
  decision: string;
  confidence: number;
  reasoning: string;
  executed_trade_id: number | null;
  executed: boolean;
  execution_delay_seconds: number | null;
  trade_result_usd: number | null;
  trade_result_pct: number | null;
}

export interface BacktestResponse {
  period: {
    start: string;
    end: string;
    days: number;
  };
  stats: {
    total_decisions: number;
    executed_decisions: number;
    execution_rate: number;
    total_trades: number;
  };
  decisions: BacktestDecision[];
  correlation: {
    decision_id: number;
    decision_timestamp: string;
    symbol: string;
    decision: string;
    confidence: number;
    executed: boolean;
    trade_id: number | null;
    trade_pnl_usd: number | null;
    trade_pnl_pct: number | null;
  }[];
}
