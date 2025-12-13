"""
Trade View Generator for Telegram Instant View
Genera pagine HTML ottimizzate per visualizzazione dettagliata trade
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Template
import db_utils

logger = logging.getLogger(__name__)


class TradeViewGenerator:
    """Genera HTML views per trade con ottimizzazione Instant View"""

    @staticmethod
    def generate_trade_view_html(trade_id: int, base_url: str) -> Optional[str]:
        """
        Genera HTML completo per Instant View di un trade

        Args:
            trade_id: ID del trade da visualizzare
            base_url: Base URL per asset statici (es. https://trading-agent.com)

        Returns:
            HTML string ottimizzato per Telegram Instant View
        """
        try:
            # Recupera dati trade completi
            trade_data = TradeViewGenerator._get_trade_data(trade_id)

            if not trade_data:
                return None

            # Recupera contesto AI (se disponibile)
            ai_context = TradeViewGenerator._get_ai_context(trade_data.get('bot_operation_id'))

            # Genera HTML usando template
            html = TradeViewGenerator._render_template(trade_data, ai_context, base_url)

            return html

        except Exception as e:
            logger.error(f"Error generating trade view: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_trade_data(trade_id: int) -> Optional[Dict[str, Any]]:
        """Recupera dati trade dal database"""
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            id,
                            created_at,
                            closed_at,
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
                            bot_operation_id
                        FROM executed_trades
                        WHERE id = %s
                    """

                    cur.execute(query, (trade_id,))
                    row = cur.fetchone()

                    if not row:
                        return None

                    columns = [desc[0] for desc in cur.description]
                    trade = dict(zip(columns, row))

                    # Converti datetime a string
                    if trade['created_at']:
                        trade['created_at'] = trade['created_at'].isoformat()
                    if trade['closed_at']:
                        trade['closed_at'] = trade['closed_at'].isoformat()

                    # Converti Decimal a float
                    for key in ['entry_price', 'exit_price', 'size', 'size_usd',
                               'pnl_usd', 'pnl_pct', 'fees_usd', 'slippage_pct',
                               'stop_loss_price', 'take_profit_price', 'duration_minutes']:
                        if trade.get(key) is not None:
                            trade[key] = float(trade[key])

                    return trade

        except Exception as e:
            logger.error(f"Error fetching trade data: {e}")
            return None

    @staticmethod
    def _get_ai_context(bot_operation_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Recupera contesto AI della decisione"""
        if not bot_operation_id:
            return None

        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            bo.raw_payload,
                            bo.operation,
                            bo.created_at as decision_time,
                            ac.system_prompt,
                            ic.ticker, ic.price, ic.ema20_15m, ic.ema50_15m,
                            ic.atr14_15m, ic.intraday_rsi14_series,
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
                        WHERE bo.id = %s
                        LIMIT 1
                    """

                    cur.execute(query, (bot_operation_id,))
                    row = cur.fetchone()

                    if not row:
                        return None

                    columns = [desc[0] for desc in cur.description]
                    context = dict(zip(columns, row))

                    # Parse raw_payload per confidence, reason, etc.
                    if context.get('raw_payload'):
                        payload = context['raw_payload']
                        context['confidence'] = payload.get('confidence')
                        context['reason'] = payload.get('reason')
                        context['invalidation_condition'] = payload.get('invalidation_condition')

                    # Convert Decimal to float for numeric fields
                    for key in ['price', 'ema20_15m', 'ema50_15m', 'atr14_15m',
                               'sentiment_value', 'prediction', 'change_pct']:
                        if context.get(key) is not None:
                            try:
                                context[key] = float(context[key])
                            except (TypeError, ValueError):
                                pass

                    return context

        except Exception as e:
            logger.error(f"Error fetching AI context: {e}")
            return None

    @staticmethod
    def _render_template(trade: Dict, ai_context: Optional[Dict], base_url: str) -> str:
        """Renderizza HTML usando Jinja2 template"""

        template_str = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta property="og:title" content="{{ trade.symbol }} {{ trade.direction|upper }} Trade #{{ trade.id }}">
    <meta property="og:description" content="P&L: {{ '${:,.2f}'.format(trade.pnl_usd or 0) }} ({{ '{:.2f}'.format(trade.pnl_pct or 0) }}%) | {{ trade.status|upper }}">
    <meta property="og:type" content="article">
    <meta property="article:published_time" content="{{ trade.created_at }}">

    <title>{{ trade.symbol }} {{ trade.direction|upper }} Trade #{{ trade.id }}</title>

    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, {{ '#10b981' if trade.direction == 'long' else '#ef4444' }}, {{ '#059669' if trade.direction == 'long' else '#dc2626' }});
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 28px;
        }
        .header .subtitle {
            opacity: 0.9;
            font-size: 14px;
        }
        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 10px;
        }
        .status-open { background: #3b82f6; color: white; }
        .status-closed { background: #6b7280; color: white; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
        }
        .metric-card.positive { border-left-color: #10b981; }
        .metric-card.negative { border-left-color: #ef4444; }
        .metric-label {
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #111827;
        }
        .metric-value.positive { color: #10b981; }
        .metric-value.negative { color: #ef4444; }
        .metric-subvalue {
            font-size: 13px;
            color: #6b7280;
            margin-top: 5px;
        }
        .section {
            background: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .section h2 {
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 20px;
            color: #111827;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f3f4f6;
        }
        .info-row:last-child {
            border-bottom: none;
        }
        .info-label {
            font-weight: 600;
            color: #6b7280;
        }
        .info-value {
            color: #111827;
            text-align: right;
        }
        .ai-context {
            background: #f9fafb;
            border-left: 4px solid #8b5cf6;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }
        .confidence-bar {
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #059669);
            transition: width 0.3s ease;
        }
        .news-item {
            background: #fef3c7;
            border-left: 3px solid #f59e0b;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
            font-size: 14px;
        }
        .timestamp {
            color: #6b7280;
            font-size: 13px;
        }
        footer {
            text-align: center;
            padding: 20px;
            color: #6b7280;
            font-size: 13px;
        }
        .chart-placeholder {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 200px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 18px;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ trade.symbol }} {{ trade.direction|upper }} Trade</h1>
        <div class="subtitle">
            Trade ID: #{{ trade.id }} |
            {{ 'Opened' if trade.status == 'open' else 'Closed' }}: {{ trade.created_at[:19].replace('T', ' ') }}
        </div>
        <span class="status-badge status-{{ trade.status }}">{{ trade.status }}</span>
    </div>

    <div class="metrics-grid">
        <div class="metric-card {{ 'positive' if (trade.pnl_usd or 0) >= 0 else 'negative' }}">
            <div class="metric-label">P&L (USD)</div>
            <div class="metric-value {{ 'positive' if (trade.pnl_usd or 0) >= 0 else 'negative' }}">
                ${{ '{:,.2f}'.format(trade.pnl_usd or 0) }}
            </div>
            <div class="metric-subvalue">{{ '{:.2f}'.format(trade.pnl_pct or 0) }}%</div>
        </div>

        <div class="metric-card">
            <div class="metric-label">Entry Price</div>
            <div class="metric-value">${{ '{:,.2f}'.format(trade.entry_price or 0) }}</div>
            {% if trade.exit_price %}
            <div class="metric-subvalue">Exit: ${{ '{:,.2f}'.format(trade.exit_price) }}</div>
            {% endif %}
        </div>

        <div class="metric-card">
            <div class="metric-label">Position Size</div>
            <div class="metric-value">{{ '{:.4f}'.format(trade.size or 0) }}</div>
            <div class="metric-subvalue">${{ '{:,.2f}'.format(trade.size_usd or 0) }} @ {{ trade.leverage }}x</div>
        </div>

        {% if trade.duration_minutes %}
        <div class="metric-card">
            <div class="metric-label">Duration</div>
            <div class="metric-value">
                {% if trade.duration_minutes >= 60 %}
                    {{ (trade.duration_minutes // 60)|int }}h {{ (trade.duration_minutes % 60)|int }}m
                {% else %}
                    {{ trade.duration_minutes|int }}m
                {% endif %}
            </div>
            {% if trade.exit_reason %}
            <div class="metric-subvalue">Exit: {{ trade.exit_reason }}</div>
            {% endif %}
        </div>
        {% endif %}
    </div>

    <div class="section">
        <h2>📊 Trade Details</h2>

        <div class="info-row">
            <span class="info-label">Symbol</span>
            <span class="info-value">{{ trade.symbol }}</span>
        </div>

        <div class="info-row">
            <span class="info-label">Direction</span>
            <span class="info-value">{{ trade.direction|upper }}</span>
        </div>

        <div class="info-row">
            <span class="info-label">Leverage</span>
            <span class="info-value">{{ trade.leverage }}x</span>
        </div>

        {% if trade.stop_loss_price %}
        <div class="info-row">
            <span class="info-label">Stop Loss</span>
            <span class="info-value">${{ '{:,.2f}'.format(trade.stop_loss_price) }}</span>
        </div>
        {% endif %}

        {% if trade.take_profit_price %}
        <div class="info-row">
            <span class="info-label">Take Profit</span>
            <span class="info-value">${{ '{:,.2f}'.format(trade.take_profit_price) }}</span>
        </div>
        {% endif %}

        {% if trade.fees_usd %}
        <div class="info-row">
            <span class="info-label">Fees Paid</span>
            <span class="info-value">${{ '{:.2f}'.format(trade.fees_usd) }}</span>
        </div>
        {% endif %}

        {% if trade.slippage_pct %}
        <div class="info-row">
            <span class="info-label">Slippage</span>
            <span class="info-value">{{ '{:.3f}'.format(trade.slippage_pct) }}%</span>
        </div>
        {% endif %}
    </div>

    {% if ai_context %}
    <div class="section">
        <h2>🤖 AI Decision Context</h2>

        {% if ai_context.confidence %}
        <div class="ai-context">
            <div class="info-label">Confidence Level</div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {{ (ai_context.confidence * 100)|int }}%"></div>
            </div>
            <div class="metric-subvalue">{{ (ai_context.confidence * 100)|int }}% confident</div>
        </div>
        {% endif %}

        {% if ai_context.reason %}
        <div class="ai-context">
            <strong>📝 Reasoning:</strong>
            <p style="margin: 10px 0 0 0;">{{ ai_context.reason }}</p>
        </div>
        {% endif %}

        {% if ai_context.invalidation_condition %}
        <div class="ai-context">
            <strong>⚠️ Invalidation Condition:</strong>
            <p style="margin: 10px 0 0 0;">{{ ai_context.invalidation_condition }}</p>
        </div>
        {% endif %}

        {% if ai_context.price %}
        <div style="margin-top: 20px;">
            <h3 style="font-size: 16px; margin-bottom: 10px;">📈 Market Indicators</h3>

            <div class="info-row">
                <span class="info-label">Price at Decision</span>
                <span class="info-value">${{ '{:,.2f}'.format(ai_context.price) }}</span>
            </div>

            {% if ai_context.ema20_15m %}
            <div class="info-row">
                <span class="info-label">EMA 20 (15m)</span>
                <span class="info-value">${{ '{:,.2f}'.format(ai_context.ema20_15m) }}</span>
            </div>
            {% endif %}

            {% if ai_context.ema50_15m %}
            <div class="info-row">
                <span class="info-label">EMA 50 (15m)</span>
                <span class="info-value">${{ '{:,.2f}'.format(ai_context.ema50_15m) }}</span>
            </div>
            {% endif %}

            {% if ai_context.atr14_15m %}
            <div class="info-row">
                <span class="info-label">ATR 14 (15m)</span>
                <span class="info-value">${{ '{:,.2f}'.format(ai_context.atr14_15m) }}</span>
            </div>
            {% endif %}
        </div>
        {% endif %}

        {% if ai_context.sentiment_value %}
        <div style="margin-top: 20px;">
            <h3 style="font-size: 16px; margin-bottom: 10px;">😊 Market Sentiment</h3>
            <div class="ai-context">
                <strong>{{ ai_context.sentiment_class or 'Neutral' }}</strong>
                <p style="margin: 5px 0 0 0;">Fear & Greed Index: {{ ai_context.sentiment_value }}</p>
            </div>
        </div>
        {% endif %}

        {% if ai_context.news_text %}
        <div style="margin-top: 20px;">
            <h3 style="font-size: 16px; margin-bottom: 10px;">📰 Relevant News</h3>
            <div class="news-item">
                {{ ai_context.news_text[:500] }}{% if ai_context.news_text|length > 500 %}...{% endif %}
            </div>
        </div>
        {% endif %}

        {% if ai_context.prediction %}
        <div style="margin-top: 20px;">
            <h3 style="font-size: 16px; margin-bottom: 10px;">🔮 Price Forecast</h3>
            <div class="ai-context">
                <div class="info-row">
                    <span class="info-label">Predicted Price</span>
                    <span class="info-value">${{ '{:,.2f}'.format(ai_context.prediction) }}</span>
                </div>
                {% if ai_context.change_pct %}
                <div class="info-row">
                    <span class="info-label">Expected Change</span>
                    <span class="info-value {{ 'positive' if ai_context.change_pct >= 0 else 'negative' }}">
                        {{ '{:+.2f}'.format(ai_context.change_pct) }}%
                    </span>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <div class="section">
        <h2>📈 Performance Visualization</h2>
        <div class="chart-placeholder">
            💹 Equity Curve Chart
            <br>
            <span style="font-size: 14px; opacity: 0.8;">(Interactive chart in dashboard)</span>
        </div>
    </div>

    <footer>
        <p>
            <strong>Trading Agent</strong> | AI-Powered Crypto Trading
            <br>
            Generated: {{ datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC') }}
        </p>
        <p style="margin-top: 10px;">
            <a href="{{ base_url }}" style="color: #3b82f6; text-decoration: none;">🏠 Back to Dashboard</a>
            |
            <a href="{{ base_url }}/api/export/backtest?days=30" style="color: #3b82f6; text-decoration: none;">📥 Export Data</a>
        </p>
    </footer>
</body>
</html>"""

        # Render template
        template = Template(template_str)
        html = template.render(
            trade=trade,
            ai_context=ai_context,
            base_url=base_url,
            datetime=datetime
        )

        return html
