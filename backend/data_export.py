"""
Data Export Module
Esporta dati trading in vari formati con filtri temporali
"""

import json
import csv
import io
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

import db_utils
from analytics import TradingAnalytics

logger = logging.getLogger(__name__)


class DataExporter:
    """Gestisce export di dati trading in JSON/CSV"""

    PRESET_PERIODS = {
        '12h': 0.5,
        '24h': 1,
        '3d': 3,
        '7d': 7,
        '30d': 30,
        '90d': 90,
        '365d': 365
    }

    @staticmethod
    def export_full_dataset(
        days: Optional[int] = None,
        period_preset: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_context: bool = True,
        include_metrics: bool = True,
        format: str = 'json'
    ) -> Dict[str, Any]:
        """
        Esporta dataset completo con filtri temporali

        Args:
            days: Numero di giorni da esportare (es. 30)
            period_preset: Preset periodo ('12h', '24h', '3d', '7d', '30d', etc.)
            start_date: Data inizio (ISO format)
            end_date: Data fine (ISO format)
            include_context: Include contesto AI (indicatori, news, sentiment)
            include_metrics: Include metriche analytics
            format: 'json' o 'csv'

        Returns:
            Dict con tutti i dati richiesti
        """

        # Determina periodo
        if period_preset and period_preset in DataExporter.PRESET_PERIODS:
            days = DataExporter.PRESET_PERIODS[period_preset]
        elif days is None:
            days = 30  # Default

        logger.info(f"📊 Exporting data for last {days} days (format: {format})")

        # === 1. TRADES ===
        trades = DataExporter._get_trades_data(days, start_date, end_date)

        # === 2. AI DECISIONS ===
        decisions = DataExporter._get_decisions_data(days, start_date, end_date, include_context)

        # === 3. ACCOUNT SNAPSHOTS ===
        snapshots = DataExporter._get_account_snapshots(days, start_date, end_date)

        # === 4. LLM USAGE ===
        llm_usage = DataExporter._get_llm_usage(days, start_date, end_date)

        # === 5. ERRORS ===
        errors = DataExporter._get_errors(days, start_date, end_date)

        # === 6. ANALYTICS METRICS (opzionale) ===
        metrics = None
        equity_curve = None
        breakdown_symbol = None
        breakdown_daily = None

        if include_metrics and len(trades) > 0:
            try:
                trades_df = pd.DataFrame(trades)
                analytics = TradingAnalytics(trades_df)

                metrics = analytics.calculate_all_metrics().to_dict()
                equity_curve = analytics.generate_equity_curve()
                breakdown_symbol = analytics.breakdown_by_symbol()
                breakdown_daily = analytics.breakdown_by_timeframe('daily')
            except Exception as e:
                logger.error(f"Error calculating metrics: {e}")

        # Costruisci response
        result = {
            'export_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'period_days': days,
                'period_preset': period_preset,
                'start_date': start_date,
                'end_date': end_date,
                'format': format,
                'include_context': include_context,
                'include_metrics': include_metrics
            },
            'summary': {
                'total_trades': len(trades),
                'total_decisions': len(decisions),
                'total_snapshots': len(snapshots),
                'llm_api_calls': len(llm_usage),
                'errors_logged': len(errors)
            },
            'data': {
                'trades': trades,
                'decisions': decisions,
                'account_snapshots': snapshots,
                'llm_usage': llm_usage,
                'errors': errors
            }
        }

        if metrics:
            result['analytics'] = {
                'performance_metrics': metrics,
                'equity_curve': equity_curve,
                'breakdown_by_symbol': breakdown_symbol,
                'breakdown_by_day': breakdown_daily
            }

        return result

    @staticmethod
    def export_to_csv_string(data: Dict[str, Any]) -> str:
        """
        Converte export in formato CSV (solo trades + decisions)

        Returns:
            String CSV pronta per download
        """
        output = io.StringIO()

        # Export trades
        if data['data']['trades']:
            writer = csv.DictWriter(output, fieldnames=data['data']['trades'][0].keys())
            writer.writeheader()
            writer.writerows(data['data']['trades'])

        return output.getvalue()

    @staticmethod
    def export_backtest_format(days: int = 30) -> Dict[str, Any]:
        """
        Esporta in formato ottimizzato per backtesting

        Returns:
            Dict con:
            - decisions: Lista decisioni AI con contesto
            - actual_trades: Trade effettivamente eseguiti
            - correlation: Match decision_id -> trade_id
        """
        trades = DataExporter._get_trades_data(days)
        decisions = DataExporter._get_decisions_data(days, include_context=True)

        # Crea correlation map
        correlation = []
        for trade in trades:
            if trade.get('bot_operation_id'):
                # Trova decisione corrispondente
                decision = next(
                    (d for d in decisions if d['decision_id'] == trade['bot_operation_id']),
                    None
                )
                if decision:
                    correlation.append({
                        'decision_id': decision['decision_id'],
                        'trade_id': trade['trade_id'],
                        'decision_time': decision['decision_time'],
                        'trade_open_time': trade['created_at'],
                        'symbol': trade['symbol'],
                        'direction': trade['direction'],
                        'predicted_confidence': decision.get('confidence'),
                        'actual_pnl_usd': trade.get('pnl_usd'),
                        'actual_pnl_pct': trade.get('pnl_pct')
                    })

        return {
            'export_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'days': days,
                'format': 'backtest'
            },
            'decisions': decisions,
            'actual_trades': trades,
            'correlation': correlation,
            'stats': {
                'total_decisions': len(decisions),
                'total_trades': len(trades),
                'execution_rate': len(trades) / len(decisions) if decisions else 0
            }
        }

    # === HELPER METHODS ===

    @staticmethod
    def _get_trades_data(days: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Recupera dati trade"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            id as trade_id,
                            created_at,
                            closed_at,
                            bot_operation_id,
                            trade_type,
                            symbol,
                            direction,
                            entry_price,
                            exit_price,
                            size,
                            size_usd,
                            leverage,
                            stop_loss_price,
                            take_profit_price,
                            exit_reason,
                            pnl_usd,
                            pnl_pct,
                            duration_minutes,
                            status,
                            fees_usd,
                            slippage_pct,
                            hl_order_id
                        FROM executed_trades
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        ORDER BY created_at DESC
                    """

                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    trades = []
                    for row in rows:
                        trade = dict(zip(columns, row))
                        # Converti datetime a ISO string
                        for key in ['created_at', 'closed_at']:
                            if trade[key] and hasattr(trade[key], 'isoformat'):
                                trade[key] = trade[key].isoformat()
                        # Converti Decimal a float
                        for key in ['entry_price', 'exit_price', 'size', 'size_usd', 'pnl_usd', 'pnl_pct', 'fees_usd']:
                            if trade.get(key) is not None:
                                trade[key] = float(trade[key])
                        trades.append(trade)

                    return trades
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []

    @staticmethod
    def _get_decisions_data(days: int, start_date: Optional[str] = None, end_date: Optional[str] = None, include_context: bool = True) -> List[Dict]:
        """Recupera decisioni AI con contesto"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    if include_context:
                        # Query completa con JOIN per contesto
                        query = """
                            SELECT
                                bo.id as decision_id,
                                bo.created_at as decision_time,
                                bo.operation,
                                bo.symbol,
                                bo.direction,
                                bo.target_portion_of_balance,
                                bo.leverage,
                                bo.raw_payload,
                                ac.system_prompt,
                                ic.ticker as indicator_ticker,
                                ic.price as indicator_price,
                                ic.ema20_15m, ic.ema50_15m,
                                ic.atr3_15m, ic.atr14_15m,
                                nc.news_text,
                                sc.value as sentiment_value,
                                sc.classification as sentiment_class,
                                fc.ticker as forecast_ticker,
                                fc.prediction, fc.change_pct
                            FROM bot_operations bo
                            LEFT JOIN ai_contexts ac ON bo.context_id = ac.id
                            LEFT JOIN indicators_contexts ic ON ic.context_id = ac.id
                            LEFT JOIN news_contexts nc ON nc.context_id = ac.id
                            LEFT JOIN sentiment_contexts sc ON sc.context_id = ac.id
                            LEFT JOIN forecasts_contexts fc ON fc.context_id = ac.id
                            WHERE bo.created_at > NOW() - INTERVAL '%s days'
                            ORDER BY bo.created_at DESC
                        """
                    else:
                        # Query semplice senza contesto
                        query = """
                            SELECT
                                id as decision_id,
                                created_at as decision_time,
                                operation,
                                symbol,
                                direction,
                                target_portion_of_balance,
                                leverage,
                                raw_payload
                            FROM bot_operations
                            WHERE created_at > NOW() - INTERVAL '%s days'
                            ORDER BY created_at DESC
                        """

                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    # Group by decision_id se include_context
                    if include_context:
                        decisions_dict = {}
                        for row in rows:
                            data = dict(zip(columns, row))
                            dec_id = data['decision_id']

                            if dec_id not in decisions_dict:
                                decisions_dict[dec_id] = {
                                    'decision_id': dec_id,
                                    'decision_time': data['decision_time'].isoformat() if data['decision_time'] else None,
                                    'operation': data['operation'],
                                    'symbol': data['symbol'],
                                    'direction': data['direction'],
                                    'target_portion': float(data['target_portion_of_balance']) if data['target_portion_of_balance'] else None,
                                    'leverage': float(data['leverage']) if data['leverage'] else None,
                                    'raw_payload': data['raw_payload'],
                                    'indicators': [],
                                    'news': None,
                                    'sentiment': None,
                                    'forecasts': []
                                }

                            # Aggiungi contesto
                            if data.get('indicator_ticker'):
                                decisions_dict[dec_id]['indicators'].append({
                                    'ticker': data['indicator_ticker'],
                                    'price': float(data['indicator_price']) if data['indicator_price'] else None,
                                    'ema20_15m': float(data['ema20_15m']) if data['ema20_15m'] else None,
                                    'ema50_15m': float(data['ema50_15m']) if data['ema50_15m'] else None
                                })

                            if data.get('news_text') and not decisions_dict[dec_id]['news']:
                                decisions_dict[dec_id]['news'] = data['news_text']

                            if data.get('sentiment_value') and not decisions_dict[dec_id]['sentiment']:
                                decisions_dict[dec_id]['sentiment'] = {
                                    'value': data['sentiment_value'],
                                    'classification': data['sentiment_class']
                                }

                        return list(decisions_dict.values())
                    else:
                        decisions = []
                        for row in rows:
                            dec = dict(zip(columns, row))
                            if dec['decision_time']:
                                dec['decision_time'] = dec['decision_time'].isoformat()
                            if dec.get('target_portion_of_balance'):
                                dec['target_portion'] = float(dec['target_portion_of_balance'])
                            if dec.get('leverage'):
                                dec['leverage'] = float(dec['leverage'])
                            decisions.append(dec)
                        return decisions

        except Exception as e:
            logger.error(f"Error fetching decisions: {e}")
            return []

    @staticmethod
    def _get_account_snapshots(days: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Recupera snapshot account"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            id,
                            created_at as timestamp,
                            balance_usd as account_value,
                            balance_usd as equity,
                            raw_payload as margin_summary,
                            raw_payload as positions
                        FROM account_snapshots
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        ORDER BY created_at DESC
                    """

                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    snapshots = []
                    for row in rows:
                        snap = dict(zip(columns, row))
                        if snap['timestamp']:
                            snap['timestamp'] = snap['timestamp'].isoformat()
                        if snap.get('account_value'):
                            snap['account_value'] = float(snap['account_value'])
                        if snap.get('equity'):
                            snap['equity'] = float(snap['equity'])
                        snapshots.append(snap)

                    return snapshots
        except Exception as e:
            logger.error(f"Error fetching snapshots: {e}")
            return []

    @staticmethod
    def _get_llm_usage(days: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Recupera usage LLM"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'llm_usage'
                        );
                    """)
                    table_exists = cur.fetchone()[0]

                    if not table_exists:
                        logger.warning("Table llm_usage does not exist")
                        return []

                    query = """
                        SELECT
                            id,
                            created_at,
                            model_name,
                            provider,
                            input_tokens,
                            output_tokens,
                            total_cost_usd,
                            response_time_ms
                        FROM llm_usage
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        ORDER BY created_at DESC
                    """

                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    usage = []
                    for row in rows:
                        u = dict(zip(columns, row))
                        if u['created_at']:
                            u['created_at'] = u['created_at'].isoformat()
                        if u.get('total_cost_usd'):
                            u['total_cost_usd'] = float(u['total_cost_usd'])
                        usage.append(u)

                    return usage
        except Exception as e:
            logger.error(f"Error fetching LLM usage: {e}")
            return []

    @staticmethod
    def _get_errors(days: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Recupera errori"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            id,
                            created_at,
                            error_type,
                            error_message,
                            source
                        FROM errors
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        ORDER BY created_at DESC
                        LIMIT 100
                    """

                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    errors = []
                    for row in rows:
                        err = dict(zip(columns, row))
                        if err['created_at']:
                            err['created_at'] = err['created_at'].isoformat()
                        errors.append(err)

                    return errors
        except Exception as e:
            logger.error(f"Error fetching errors: {e}")
            return []
