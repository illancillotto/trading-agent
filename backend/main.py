from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import io
import pandas as pd

from model_manager import get_model_manager
from db_utils import get_connection
from token_tracker import get_token_tracker
from notifications import notifier
from backtrack_analysis import BacktrackAnalyzer
from confidence_calibrator import get_confidence_calibrator
from data_export import DataExporter
from trade_view_generator import TradeViewGenerator
import threading
import logging

logger = logging.getLogger(__name__)

# =====================
# Security Configuration
# =====================
PUBLIC_DASHBOARD_MODE = os.getenv("PUBLIC_DASHBOARD_MODE", "false").lower() == "true"

if PUBLIC_DASHBOARD_MODE:
    logger.info("🔒 PUBLIC DASHBOARD MODE ACTIVE: Logs disabled, Sensitive config hidden")

# =====================
# Trading Bot Control
# =====================
TRADING_BOT_ENABLED = os.getenv("TRADING_BOT_ENABLED", "false").lower() == "true"

if TRADING_BOT_ENABLED:
    logger.info("🚀 TRADING BOT IS ENABLED - Live trading attivo")
else:
    logger.warning("⚠️ TRADING BOT IS DISABLED - Modalità test/demo, nessun trade verrà eseguito")

app = FastAPI(title="Trading Agent API")

# Configure CORS middleware BEFORE routes (best practice)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Trading Agent API is running"}


# Schemi per le API dei modelli
class ModelInfo(BaseModel):
    id: str
    name: str
    model_id: str
    provider: str
    available: bool
    supports_json_schema: bool
    supports_reasoning: bool


# Endpoint per i modelli
@app.get("/api/models", response_model=List[ModelInfo])
async def get_available_models():
    """Restituisce la lista dei modelli disponibili"""
    model_manager = get_model_manager()
    return model_manager.get_available_models()


@app.get("/api/models/current")
async def get_current_model():
    """
    Restituisce il modello corrente.
    Nota: Il modello viene configurato solo tramite variabile d'ambiente DEFAULT_AI_MODEL.
    Non è possibile modificarlo tramite API.
    """
    model_manager = get_model_manager()
    current_model_key = model_manager.get_current_model()
    model_config = model_manager.get_model_config(current_model_key)
    
    if not model_config:
        raise HTTPException(status_code=500, detail="Modello corrente non trovato")
    
    return {
        "id": current_model_key,
        "name": model_config.name,
        "model_id": model_config.model_id,
        "provider": model_config.provider.value,
        "available": model_manager.is_model_available(current_model_key)
    }


# =====================
# Modelli di risposta API per dashboard
# =====================

class BalancePoint(BaseModel):
    timestamp: datetime
    balance_usd: float


class OpenPosition(BaseModel):
    id: int
    snapshot_id: int
    symbol: str
    side: str
    size: float
    entry_price: Optional[float]
    mark_price: Optional[float]
    pnl_usd: Optional[float]
    leverage: Optional[str]
    snapshot_created_at: datetime


class TradeResult(BaseModel):
    trade_id: int
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    status: str
    exit_reason: Optional[str]
    closed_at: Optional[datetime]


class BotOperation(BaseModel):
    id: int
    created_at: datetime
    operation: str
    symbol: Optional[str]
    direction: Optional[str]
    target_portion_of_balance: Optional[float]
    leverage: Optional[float]
    raw_payload: Any
    system_prompt: Optional[str]
    trade_result: Optional[TradeResult] = None


class ExecutedTrade(BaseModel):
    id: int
    created_at: datetime
    bot_operation_id: Optional[int]
    trade_type: str
    symbol: str
    direction: str
    entry_price: Optional[float]
    exit_price: Optional[float]
    size: float
    size_usd: Optional[float]
    leverage: Optional[int]
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    exit_reason: Optional[str]
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    duration_minutes: Optional[int]
    status: str
    closed_at: Optional[datetime]
    fees_usd: Optional[float]


class TradeStatistics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    best_trade: float
    worst_trade: float
    avg_duration_minutes: Optional[float]
    total_fees: float


# =====================
# Endpoint API Dashboard
# =====================

@app.get("/api/balance", response_model=List[BalancePoint])
async def get_balance() -> List[BalancePoint]:
    """Restituisce TUTTA la storia del saldo (balance_usd) ordinata nel tempo.
    
    I dati sono presi dalla tabella `account_snapshots`.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT created_at, balance_usd
                    FROM account_snapshots
                    ORDER BY created_at ASC;
                    """
                )
                rows = cur.fetchall()
        
        return [
            BalancePoint(timestamp=row[0], balance_usd=float(row[1]))
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero del saldo: {str(e)}")


@app.get("/api/open-positions", response_model=List[OpenPosition])
async def get_open_positions() -> List[OpenPosition]:
    """Restituisce le posizioni aperte dell'ULTIMO snapshot disponibile.
    
    - Prende l'ultimo record da `account_snapshots`.
    - Recupera le posizioni corrispondenti da `open_positions`.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Ultimo snapshot
                cur.execute(
                    """
                    SELECT id, created_at
                    FROM account_snapshots
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """
                )
                row = cur.fetchone()
                if not row:
                    logger.warning("⚠️ Nessuno snapshot trovato in account_snapshots")
                    return []
                snapshot_id = row[0]
                snapshot_created_at = row[1]
                
                logger.info(f"🔍 Fetching positions for snapshot {snapshot_id} (created {snapshot_created_at})")

                # Posizioni aperte per quello snapshot
                cur.execute(
                    """
                    SELECT
                        id,
                        snapshot_id,
                        symbol,
                        side,
                        size,
                        entry_price,
                        mark_price,
                        pnl_usd,
                        leverage
                    FROM open_positions
                    WHERE snapshot_id = %s
                    ORDER BY symbol ASC, id ASC;
                    """,
                    (snapshot_id,),
                )
                rows = cur.fetchall()
                logger.info(f"✅ Trovate {len(rows)} posizioni per snapshot {snapshot_id}")
        
        return [
            OpenPosition(
                id=row[0],
                snapshot_id=row[1],
                symbol=row[2],
                side=row[3],
                size=float(row[4]),
                entry_price=float(row[5]) if row[5] is not None else None,
                mark_price=float(row[6]) if row[6] is not None else None,
                pnl_usd=float(row[7]) if row[7] is not None else None,
                leverage=row[8],
                snapshot_created_at=snapshot_created_at,
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero delle posizioni: {str(e)}")


@app.get("/api/bot-operations", response_model=List[BotOperation])
async def get_bot_operations(
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Numero massimo di operazioni da restituire (default 50)",
    ),
) -> List[BotOperation]:
    """Restituisce le ULTIME `limit` operazioni del bot con il full system prompt.
    
    - I dati provengono da `bot_operations` uniti a `ai_contexts`.
    - Ordinati da più recente a meno recente.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        bo.id,
                        bo.created_at,
                        bo.operation,
                        bo.symbol,
                        bo.direction,
                        bo.target_portion_of_balance,
                        bo.leverage,
                        bo.raw_payload,
                        ac.system_prompt,
                        et.id as trade_id,
                        et.pnl_usd,
                        et.pnl_pct,
                        et.status as trade_status,
                        et.exit_reason,
                        et.closed_at
                    FROM bot_operations AS bo
                    LEFT JOIN ai_contexts AS ac ON bo.context_id = ac.id
                    LEFT JOIN executed_trades AS et ON bo.id = et.bot_operation_id
                    ORDER BY bo.created_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        operations: List[BotOperation] = []
        for row in rows:
            trade_result = None
            if row[9] is not None:
                trade_result = TradeResult(
                    trade_id=row[9],
                    pnl_usd=float(row[10]) if row[10] is not None else None,
                    pnl_pct=float(row[11]) if row[11] is not None else None,
                    status=row[12],
                    exit_reason=row[13],
                    closed_at=row[14]
                )

            operations.append(
                BotOperation(
                    id=row[0],
                    created_at=row[1],
                    operation=row[2],
                    symbol=row[3],
                    direction=row[4],
                    target_portion_of_balance=float(row[5]) if row[5] is not None else None,
                    leverage=float(row[6]) if row[6] is not None else None,
                    raw_payload=row[7],
                    system_prompt=row[8],
                    trade_result=trade_result,
                )
            )

        return operations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero delle operazioni: {str(e)}")


# =====================
# Trade History API Endpoints
# =====================

@app.get("/api/trades", response_model=List[ExecutedTrade])
async def get_trades(
    page: int = Query(1, ge=1, description="Numero di pagina (1-based)"),
    limit: int = Query(50, ge=1, le=500, description="Numero di trades per pagina"),
    symbol: Optional[str] = Query(None, description="Filtra per symbol (es. BTC, ETH)"),
    direction: Optional[str] = Query(None, description="Filtra per direction (long/short)"),
    status: Optional[str] = Query(None, description="Filtra per status (open/closed/cancelled)"),
    date_from: Optional[str] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fine (YYYY-MM-DD)"),
) -> List[ExecutedTrade]:
    """
    Restituisce la lista dei trades eseguiti con filtri e paginazione.

    Filtri disponibili:
    - symbol: Filtra per simbolo specifico
    - direction: Filtra per direzione (long/short)
    - status: Filtra per stato (open/closed/cancelled)
    - date_from: Data inizio (formato YYYY-MM-DD)
    - date_to: Data fine (formato YYYY-MM-DD)

    Paginazione:
    - page: Numero di pagina (default: 1)
    - limit: Numero di risultati per pagina (default: 50, max: 500)
    """
    try:
        # Costruisci query con filtri
        offset = (page - 1) * limit

        query = """
            SELECT
                id, created_at, bot_operation_id, trade_type, symbol, direction,
                entry_price, exit_price, size, size_usd, leverage,
                stop_loss_price, take_profit_price, exit_reason,
                pnl_usd, pnl_pct, duration_minutes, status, closed_at, fees_usd
            FROM executed_trades
            WHERE 1=1
        """
        params = []

        # Aggiungi filtri
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)

        if direction:
            query += " AND direction = %s"
            params.append(direction)

        if status:
            query += " AND status = %s"
            params.append(status)

        if date_from:
            query += " AND created_at >= %s::date"
            params.append(date_from)

        if date_to:
            query += " AND created_at < (%s::date + interval '1 day')"
            params.append(date_to)

        # Ordina per data (più recenti prima) e aggiungi paginazione
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        trades = []
        for row in rows:
            trades.append(
                ExecutedTrade(
                    id=row[0],
                    created_at=row[1],
                    bot_operation_id=row[2],
                    trade_type=row[3],
                    symbol=row[4],
                    direction=row[5],
                    entry_price=float(row[6]) if row[6] is not None else None,
                    exit_price=float(row[7]) if row[7] is not None else None,
                    size=float(row[8]),
                    size_usd=float(row[9]) if row[9] is not None else None,
                    leverage=row[10],
                    stop_loss_price=float(row[11]) if row[11] is not None else None,
                    take_profit_price=float(row[12]) if row[12] is not None else None,
                    exit_reason=row[13],
                    pnl_usd=float(row[14]) if row[14] is not None else None,
                    pnl_pct=float(row[15]) if row[15] is not None else None,
                    duration_minutes=row[16],
                    status=row[17],
                    closed_at=row[18],
                    fees_usd=float(row[19]) if row[19] is not None else None,
                )
            )

        return trades

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero dei trades: {str(e)}")


@app.get("/api/trades/stats", response_model=TradeStatistics)
async def get_trade_stats(
    symbol: Optional[str] = Query(None, description="Filtra per symbol (es. BTC, ETH)"),
    days: int = Query(30, ge=1, le=365, description="Numero di giorni da includere"),
) -> TradeStatistics:
    """
    Restituisce statistiche aggregate sui trades.

    Parametri:
    - symbol: Calcola statistiche per un simbolo specifico (opzionale)
    - days: Numero di giorni da includere nell'analisi (default: 30)

    Ritorna:
    - total_trades: Numero totale di trades
    - winning_trades: Numero di trades profittevoli
    - losing_trades: Numero di trades in perdita
    - win_rate: Percentuale di trades vincenti
    - total_pnl: P&L totale in USD
    - avg_pnl: P&L medio per trade
    - best_trade: Miglior trade (P&L più alto)
    - worst_trade: Peggior trade (P&L più basso)
    - avg_duration_minutes: Durata media dei trades
    - total_fees: Fees totali pagate
    """
    try:
        query = """
            SELECT
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                COUNT(*) FILTER (WHERE pnl_usd < 0) as losing_trades,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pnl_usd > 0) / NULLIF(COUNT(*), 0), 2) as win_rate,
                COALESCE(SUM(pnl_usd), 0) as total_pnl,
                COALESCE(AVG(pnl_usd), 0) as avg_pnl,
                COALESCE(MAX(pnl_usd), 0) as best_trade,
                COALESCE(MIN(pnl_usd), 0) as worst_trade,
                AVG(duration_minutes) as avg_duration_minutes,
                COALESCE(SUM(fees_usd), 0) as total_fees
            FROM executed_trades
            WHERE status = 'closed'
                AND pnl_usd IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
        """
        params = [days]

        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()

        if not row or row[0] == 0:
            # Nessun trade trovato, ritorna statistiche vuote
            return TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                avg_pnl=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                avg_duration_minutes=None,
                total_fees=0.0,
            )

        return TradeStatistics(
            total_trades=row[0],
            winning_trades=row[1],
            losing_trades=row[2],
            win_rate=float(row[3]) if row[3] is not None else 0.0,
            total_pnl=float(row[4]),
            avg_pnl=float(row[5]),
            best_trade=float(row[6]),
            worst_trade=float(row[7]),
            avg_duration_minutes=float(row[8]) if row[8] is not None else None,
            total_fees=float(row[9]),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero delle statistiche: {str(e)}")


@app.get("/api/trades/{trade_id}", response_model=ExecutedTrade)
async def get_trade_by_id(trade_id: int) -> ExecutedTrade:
    """
    Restituisce i dettagli di un singolo trade.

    Parametri:
    - trade_id: ID del trade da recuperare

    Ritorna:
    - Dettagli completi del trade
    """
    try:
        query = """
            SELECT
                id, created_at, bot_operation_id, trade_type, symbol, direction,
                entry_price, exit_price, size, size_usd, leverage,
                stop_loss_price, take_profit_price, exit_reason,
                pnl_usd, pnl_pct, duration_minutes, status, closed_at, fees_usd
            FROM executed_trades
            WHERE id = %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (trade_id,))
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Trade con ID {trade_id} non trovato")

        return ExecutedTrade(
            id=row[0],
            created_at=row[1],
            bot_operation_id=row[2],
            trade_type=row[3],
            symbol=row[4],
            direction=row[5],
            entry_price=float(row[6]) if row[6] is not None else None,
            exit_price=float(row[7]) if row[7] is not None else None,
            size=float(row[8]),
            size_usd=float(row[9]) if row[9] is not None else None,
            leverage=row[10],
            stop_loss_price=float(row[11]) if row[11] is not None else None,
            take_profit_price=float(row[12]) if row[12] is not None else None,
            exit_reason=row[13],
            pnl_usd=float(row[14]) if row[14] is not None else None,
            pnl_pct=float(row[15]) if row[15] is not None else None,
            duration_minutes=row[16],
            status=row[17],
            closed_at=row[18],
            fees_usd=float(row[19]) if row[19] is not None else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero del trade: {str(e)}")


@app.get("/api/trades/{trade_id}/details")
async def get_trade_details_html(trade_id: int):
    """
    Genera pagina HTML con dettagli completi del trade per Telegram Instant View

    Parametri:
    - trade_id: ID del trade da visualizzare

    Ritorna:
    - HTML page con tutti i dettagli del trade, decision AI, market data, grafici
    """
    from fastapi.responses import HTMLResponse
    import json

    try:
        # Recupera trade details
        query_trade = """
            SELECT
                t.id, t.created_at, t.bot_operation_id, t.trade_type, t.symbol, t.direction,
                t.entry_price, t.exit_price, t.size, t.size_usd, t.leverage,
                t.stop_loss_price, t.take_profit_price, t.exit_reason,
                t.pnl_usd, t.pnl_pct, t.duration_minutes, t.status, t.closed_at, t.fees_usd
            FROM executed_trades t
            WHERE t.id = %s
        """

        # Recupera bot operation details se disponibili
        query_operation = """
            SELECT
                bo.operation, bo.direction, bo.symbol, bo.target_portion_of_balance,
                bo.leverage, bo.raw_payload, bo.created_at,
                ac.system_prompt, ac.raw_response
            FROM bot_operations bo
            LEFT JOIN ai_contexts ac ON bo.context_id = ac.id
            WHERE bo.id = %s
        """

        # Recupera indicators context se disponibili
        query_indicators = """
            SELECT ic.ticker, ic.price, ic.ema20, ic.macd, ic.rsi_7,
                   ic.volume_bid, ic.volume_ask, ic.funding_rate,
                   ic.open_interest_latest, ic.pp, ic.s1, ic.s2, ic.r1, ic.r2
            FROM indicators_contexts ic
            JOIN ai_contexts ac ON ic.context_id = ac.id
            JOIN bot_operations bo ON bo.context_id = ac.id
            WHERE bo.id = %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get trade
                cur.execute(query_trade, (trade_id,))
                trade_row = cur.fetchone()

                if not trade_row:
                    raise HTTPException(status_code=404, detail=f"Trade {trade_id} non trovato")

                # Parse trade data
                trade = {
                    'id': trade_row[0],
                    'created_at': trade_row[1],
                    'bot_operation_id': trade_row[2],
                    'trade_type': trade_row[3],
                    'symbol': trade_row[4],
                    'direction': trade_row[5],
                    'entry_price': float(trade_row[6]) if trade_row[6] else None,
                    'exit_price': float(trade_row[7]) if trade_row[7] else None,
                    'size': float(trade_row[8]),
                    'size_usd': float(trade_row[9]) if trade_row[9] else None,
                    'leverage': trade_row[10],
                    'stop_loss_price': float(trade_row[11]) if trade_row[11] else None,
                    'take_profit_price': float(trade_row[12]) if trade_row[12] else None,
                    'exit_reason': trade_row[13],
                    'pnl_usd': float(trade_row[14]) if trade_row[14] else None,
                    'pnl_pct': float(trade_row[15]) if trade_row[15] else None,
                    'duration_minutes': trade_row[16],
                    'status': trade_row[17],
                    'closed_at': trade_row[18],
                    'fees_usd': float(trade_row[19]) if trade_row[19] else None,
                }

                # Get bot operation if available
                operation = None
                if trade['bot_operation_id']:
                    cur.execute(query_operation, (trade['bot_operation_id'],))
                    op_row = cur.fetchone()
                    if op_row:
                        operation = {
                            'operation': op_row[0],
                            'direction': op_row[1],
                            'symbol': op_row[2],
                            'target_portion': float(op_row[3]) if op_row[3] else None,
                            'leverage': op_row[4],
                            'raw_payload': op_row[5],
                            'created_at': op_row[6],
                            'system_prompt': op_row[7],
                            'model_name': None,  # Non presente nello schema attuale
                            'raw_response': op_row[8]
                        }

                    # Get indicators
                    cur.execute(query_indicators, (trade['bot_operation_id'],))
                    ind_row = cur.fetchone()
                    indicators = None
                    if ind_row:
                        indicators = {
                            'ticker': ind_row[0],
                            'price': float(ind_row[1]) if ind_row[1] else None,
                            'ema20': float(ind_row[2]) if ind_row[2] else None,
                            'macd': float(ind_row[3]) if ind_row[3] else None,
                            'rsi_7': float(ind_row[4]) if ind_row[4] else None,
                            'volume_bid': float(ind_row[5]) if ind_row[5] else None,
                            'volume_ask': float(ind_row[6]) if ind_row[6] else None,
                            'funding_rate': float(ind_row[7]) if ind_row[7] else None,
                            'open_interest': float(ind_row[8]) if ind_row[8] else None,
                            'pivot_point': float(ind_row[9]) if ind_row[9] else None,
                            's1': float(ind_row[10]) if ind_row[10] else None,
                            's2': float(ind_row[11]) if ind_row[11] else None,
                            'r1': float(ind_row[12]) if ind_row[12] else None,
                            'r2': float(ind_row[13]) if ind_row[13] else None,
                        }
                else:
                    indicators = None

        # Generate HTML
        pnl_color = "#10b981" if trade['pnl_usd'] and trade['pnl_usd'] > 0 else "#ef4444"
        pnl_emoji = "🟢" if trade['pnl_usd'] and trade['pnl_usd'] > 0 else "🔴"

        # TradingView chart URL
        chart_url = f"https://www.tradingview.com/chart/?symbol=HYPERLIQUID:{trade['symbol']}USDT&interval=15"

        # Format duration
        duration_str = "N/A"
        if trade['duration_minutes']:
            hours = int(trade['duration_minutes'] // 60)
            mins = int(trade['duration_minutes'] % 60)
            duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        # Parse AI decision if available
        ai_decision_html = ""
        if operation and operation['raw_payload']:
            try:
                payload = operation['raw_payload'] if isinstance(operation['raw_payload'], dict) else json.loads(operation['raw_payload'])
                confidence = payload.get('confidence', 'N/A')
                reasoning = payload.get('reasoning', 'N/A')

                ai_decision_html = f"""
                <div class="section">
                    <h2>🤖 Decisione AI</h2>
                    <div class="data-grid">
                        <div class="data-item">
                            <span class="label">Modello:</span>
                            <span class="value">{operation.get('model_name', 'N/A')}</span>
                        </div>
                        <div class="data-item">
                            <span class="label">Confidence:</span>
                            <span class="value">{confidence}%</span>
                        </div>
                        <div class="data-item full-width">
                            <span class="label">Reasoning:</span>
                            <span class="value">{reasoning}</span>
                        </div>
                    </div>
                </div>
                """
            except:
                pass

        # Market data HTML
        market_data_html = ""
        if indicators:
            market_data_html = f"""
            <div class="section">
                <h2>📊 Condizioni di Mercato</h2>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="label">Prezzo:</span>
                        <span class="value">${indicators.get('price', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">EMA 20:</span>
                        <span class="value">${indicators.get('ema20', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">RSI 7:</span>
                        <span class="value">{indicators.get('rsi_7', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">MACD:</span>
                        <span class="value">{indicators.get('macd', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">Funding Rate:</span>
                        <span class="value">{indicators.get('funding_rate', 'N/A')}%</span>
                    </div>
                    <div class="data-item">
                        <span class="label">Open Interest:</span>
                        <span class="value">{indicators.get('open_interest', 'N/A')}</span>
                    </div>
                </div>

                <h3>📍 Pivot Points</h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="label">R2:</span>
                        <span class="value">${indicators.get('r2', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">R1:</span>
                        <span class="value">${indicators.get('r1', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">PP:</span>
                        <span class="value">${indicators.get('pivot_point', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">S1:</span>
                        <span class="value">${indicators.get('s1', 'N/A')}</span>
                    </div>
                    <div class="data-item">
                        <span class="label">S2:</span>
                        <span class="value">${indicators.get('s2', 'N/A')}</span>
                    </div>
                </div>
            </div>
            """

        html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade #{trade['id']} - {trade['symbol']} {trade['direction'].upper()}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .pnl {{
            font-size: 36px;
            font-weight: bold;
            margin: 15px 0;
            color: {pnl_color};
        }}
        .section {{
            padding: 25px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section h2 {{
            font-size: 20px;
            margin-bottom: 15px;
            color: #1f2937;
        }}
        .section h3 {{
            font-size: 16px;
            margin: 20px 0 10px 0;
            color: #4b5563;
        }}
        .data-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .data-item {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .data-item.full-width {{
            grid-column: 1 / -1;
        }}
        .label {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .value {{
            font-size: 16px;
            color: #1f2937;
            font-weight: 500;
        }}
        .chart-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: background 0.3s;
        }}
        .chart-link:hover {{
            background: #2563eb;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-long {{
            background: #d1fae5;
            color: #065f46;
        }}
        .badge-short {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .footer {{
            padding: 20px;
            text-align: center;
            background: #f9fafb;
            font-size: 14px;
            color: #6b7280;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{pnl_emoji} Trade #{trade['id']}</h1>
            <div><span class="badge badge-{trade['direction']}">{trade['symbol']} {trade['direction'].upper()}</span></div>
            <div class="pnl">${trade['pnl_usd']:+.2f}</div>
            <div>{trade['pnl_pct']:+.2f}%</div>
        </div>

        <div class="section">
            <h2>📈 Dettagli Trade</h2>
            <div class="data-grid">
                <div class="data-item">
                    <span class="label">Entry Price:</span>
                    <span class="value">${trade['entry_price']:.4f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Exit Price:</span>
                    <span class="value">${trade['exit_price']:.4f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Size:</span>
                    <span class="value">${trade['size_usd']:.2f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Leverage:</span>
                    <span class="value">{trade['leverage']}x</span>
                </div>
                <div class="data-item">
                    <span class="label">Stop Loss:</span>
                    <span class="value">${trade['stop_loss_price']:.4f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Take Profit:</span>
                    <span class="value">${trade['take_profit_price']:.4f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Durata:</span>
                    <span class="value">{duration_str}</span>
                </div>
                <div class="data-item">
                    <span class="label">Exit Reason:</span>
                    <span class="value">{trade['exit_reason'] or 'N/A'}</span>
                </div>
                <div class="data-item">
                    <span class="label">Fees:</span>
                    <span class="value">${trade['fees_usd'] or 0:.4f}</span>
                </div>
                <div class="data-item">
                    <span class="label">Opened:</span>
                    <span class="value">{trade['created_at'].strftime('%Y-%m-%d %H:%M:%S') if trade['created_at'] else 'N/A'}</span>
                </div>
                <div class="data-item">
                    <span class="label">Closed:</span>
                    <span class="value">{trade['closed_at'].strftime('%Y-%m-%d %H:%M:%S') if trade['closed_at'] else 'N/A'}</span>
                </div>
            </div>

            <a href="{chart_url}" target="_blank" class="chart-link">📊 Visualizza Grafico su TradingView</a>
        </div>

        {ai_decision_html}

        {market_data_html}

        <div class="footer">
            <p>🤖 Trading Agent - Powered by AI</p>
            <p>Trade ID: {trade['id']} | Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
        """

        return HTMLResponse(content=html)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating trade details HTML: {e}")
        raise HTTPException(status_code=500, detail=f"Errore generazione dettagli: {str(e)}")


# =====================
# Token Usage API Endpoints
# =====================

@app.get("/api/token-usage")
async def get_token_usage(period: str = Query("today", description="Period: today, session, week, month, all")):
    """
    Restituisce statistiche utilizzo token LLM per periodo specificato

    Args:
        period: "today", "session", "week", "month", "all"

    Returns:
        Statistiche dettagliate con breakdown per modello e purpose
    """
    try:
        tracker = get_token_tracker()

        # Determina periodo
        if period == "session":
            stats = tracker.get_session_stats()
            start_time = tracker.session_start
            end_time = None
        elif period == "today":
            stats = tracker.get_daily_stats()
            now = datetime.now()
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = None
        elif period == "week":
            from datetime import timedelta, timezone
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=7)
            stats = tracker._get_stats_from_db(start_time=start_time, end_time=end_time) if tracker.db_available else tracker._get_stats_from_memory([])
        elif period == "month":
            stats = tracker.get_monthly_stats()
            now = datetime.now()
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_time = None
        elif period == "all":
            stats = tracker._get_stats_from_db() if tracker.db_available else tracker._get_stats_from_memory(tracker.in_memory_usage)
            start_time = None
            end_time = None
        else:
            raise HTTPException(status_code=400, detail="Invalid period. Use: today, session, week, month, all")

        # Ottieni breakdown
        breakdown_by_model = tracker.get_cost_breakdown_by_model(start_time=start_time, end_time=end_time)
        breakdown_by_purpose = tracker.get_cost_breakdown_by_purpose(start_time=start_time, end_time=end_time)

        return {
            "period": period,
            "total_tokens": stats.total_tokens,
            "input_tokens": stats.input_tokens,
            "output_tokens": stats.output_tokens,
            "total_cost_usd": float(stats.total_cost_usd),
            "input_cost_usd": float(stats.input_cost_usd),
            "output_cost_usd": float(stats.output_cost_usd),
            "api_calls_count": stats.api_calls_count,
            "avg_tokens_per_call": float(stats.avg_tokens_per_call),
            "avg_response_time_ms": float(stats.avg_response_time_ms),
            "breakdown_by_model": breakdown_by_model,
            "breakdown_by_purpose": breakdown_by_purpose,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero token usage: {str(e)}")


@app.get("/api/token-usage/history")
async def get_token_history(days: int = Query(30, ge=1, le=365, description="Numero di giorni da includere")):
    """
    Restituisce storico giornaliero utilizzo token per grafici

    Args:
        days: Numero di giorni (1-365)

    Returns:
        Array di {date, tokens, cost, calls} per ogni giorno
    """
    try:
        tracker = get_token_tracker()
        history = tracker.get_daily_history(days=days)

        return {
            "days": days,
            "data": history
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero storico: {str(e)}")


from collections import deque
from market_data.aggregator import MarketDataAggregator

# =====================
# Market Data API Endpoints
# =====================

# Singleton aggregator instance
_market_data_aggregator = None

def get_market_aggregator():
    global _market_data_aggregator
    if _market_data_aggregator is None:
        _market_data_aggregator = MarketDataAggregator()
    return _market_data_aggregator

@app.get("/api/market-data/aggregate")
async def get_market_data_aggregate(symbol: str = "BTC"):
    """
    Restituisce dati di mercato aggregati per un symbol specifico.
    """
    try:
        aggregator = get_market_aggregator()
        snapshot = await aggregator.fetch_market_snapshot(symbol)
        return snapshot
    except Exception as e:
        logger.error(f"Errore nel recupero market data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# =====================
# MARKET MICROSTRUCTURE ENDPOINTS
# =====================

@app.get("/api/microstructure/{symbol}")
async def get_microstructure(symbol: str):
    """
    Ottiene contesto completo di market microstructure per un simbolo.

    Args:
        symbol: Simbolo crypto (es. 'BTC', 'ETH')

    Returns:
        MarketMicrostructureContext completo con order book, liquidazioni, etc.
    """
    try:
        from market_data.microstructure import get_microstructure_aggregator
        aggregator = get_microstructure_aggregator()
        context = await aggregator.get_full_context(symbol.upper())
        return context.to_dict()
    except Exception as e:
        logger.error(f"Error fetching microstructure for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/microstructure/{symbol}/orderbook")
async def get_orderbook(symbol: str):
    """Ottiene solo order book aggregato"""
    try:
        from market_data.microstructure import get_microstructure_aggregator
        aggregator = get_microstructure_aggregator()
        context = await aggregator.get_full_context(
            symbol.upper(),
            include_liquidations=False,
            include_funding=False,
            include_oi=False,
            include_ls_ratio=False
        )
        if context.order_book:
            return context.order_book.to_dict()
        raise HTTPException(status_code=404, detail="Order book not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/microstructure/{symbol}/liquidations")
async def get_liquidations(symbol: str):
    """Ottiene dati liquidazioni aggregati"""
    try:
        from market_data.microstructure import get_microstructure_aggregator
        aggregator = get_microstructure_aggregator()
        context = await aggregator.get_full_context(
            symbol.upper(),
            include_orderbook=False,
            include_funding=False,
            include_oi=False,
            include_ls_ratio=False
        )
        if context.liquidations:
            return context.liquidations.to_dict()
        raise HTTPException(status_code=404, detail="Liquidations not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# System Monitoring Endpoints (Cache, Circuit Breaker, Rate Limiter)
# =====================

@app.get("/api/system/cache-stats")
async def get_cache_stats():
    """Ottiene statistiche cache order book"""
    try:
        from market_data.microstructure.cache import get_cache
        cache = get_cache()
        return cache.get_stats()
    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/cache-clear")
async def clear_cache(exchange: Optional[str] = None, symbol: Optional[str] = None):
    """
    Invalida cache order book.

    Args:
        exchange: Nome exchange (opzionale, clear tutto se omesso)
        symbol: Simbolo (opzionale, richiede exchange se specificato)
    """
    try:
        from market_data.microstructure.cache import get_cache
        cache = get_cache()
        cache.invalidate(exchange, symbol)

        message = "All cache cleared"
        if exchange and symbol:
            message = f"Cache cleared for {exchange}:{symbol}"
        elif exchange:
            message = f"Cache cleared for all {exchange} pairs"

        return {"status": "success", "message": message}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/circuit-breakers")
async def get_circuit_breakers():
    """Ottiene stato di tutti i circuit breakers"""
    try:
        from market_data.microstructure.circuit_breaker import CircuitBreakerRegistry
        registry = CircuitBreakerRegistry()
        return registry.get_all_stats()
    except Exception as e:
        logger.error(f"Error fetching circuit breaker stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/circuit-breakers/reset")
async def reset_circuit_breakers(exchange: Optional[str] = None):
    """
    Reset circuit breakers.

    Args:
        exchange: Nome exchange (opzionale, reset tutti se omesso)
    """
    try:
        from market_data.microstructure.circuit_breaker import CircuitBreakerRegistry
        registry = CircuitBreakerRegistry()

        if exchange:
            registry.reset_exchange(exchange)
            message = f"Circuit breaker reset for {exchange}"
        else:
            registry.reset_all()
            message = "All circuit breakers reset"

        return {"status": "success", "message": message}
    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/rate-limiters")
async def get_rate_limiters():
    """Ottiene statistiche rate limiters"""
    try:
        from market_data.microstructure.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        return registry.get_all_stats()
    except Exception as e:
        logger.error(f"Error fetching rate limiter stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Coin Screener API Endpoints
# =====================

@app.get("/api/screener/latest")
async def get_latest_screener_result():
    """
    Restituisce l'ultimo risultato dello screening delle coin.
    """
    try:
        from coin_screener.db_utils import get_latest_screening
        with get_connection() as conn:
            result = get_latest_screening(conn)
        if not result:
            return {"selected_coins": [], "message": "Nessun dato di screening disponibile"}
        return result
    except Exception as e:
        logger.error(f"Errore nel recupero screening results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# =====================
# System Configuration API Endpoints
# =====================

@app.get("/api/config")
async def get_system_config():
    """
    Restituisce la configurazione del sistema (cicli, Coin Screener, ecc.)
    """
    try:
        # Import qui per evitare import circolari
        from trading_engine import CONFIG
        from sentiment import INTERVALLO_SECONDI
        
        config_response = {
            "trading": {
                "testnet": CONFIG.get("TESTNET", True),
                "tickers": CONFIG.get("TICKERS", []),
                "cycle_interval_minutes": CONFIG.get("CYCLE_INTERVAL_MINUTES", 5),
                "bot_enabled": TRADING_BOT_ENABLED
            },
            "cycles": {
                "trading_cycle_minutes": CONFIG.get("CYCLE_INTERVAL_MINUTES", 5),
                "sentiment_api_minutes": INTERVALLO_SECONDI // 60,
                "health_check_minutes": 5
            },
            "coin_screener": {
                "enabled": CONFIG.get("SCREENING_ENABLED", False),
                "top_n_coins": CONFIG.get("TOP_N_COINS", 5),
                "rebalance_day": CONFIG.get("REBALANCE_DAY", "sunday"),
                "fallback_tickers": CONFIG.get("FALLBACK_TICKERS", [])
            },
            "trend_confirmation": {
                "enabled": CONFIG.get("TREND_CONFIRMATION_ENABLED", False),
                "min_confidence": CONFIG.get("MIN_TREND_CONFIDENCE", 0.6),
                "allow_scalping": CONFIG.get("ALLOW_SCALPING", False)
            },
            "risk_management": {
                "max_daily_loss_usd": CONFIG.get("MAX_DAILY_LOSS_USD", 500.0),
                "max_daily_loss_pct": CONFIG.get("MAX_DAILY_LOSS_PCT", 5.0),
                "max_position_pct": CONFIG.get("MAX_POSITION_PCT", 30.0),
                "default_stop_loss_pct": CONFIG.get("DEFAULT_STOP_LOSS_PCT", 2.0),
                "default_take_profit_pct": CONFIG.get("DEFAULT_TAKE_PROFIT_PCT", 5.0)
            }
        }

        if PUBLIC_DASHBOARD_MODE:
            # In modalità pubblica, manteniamo visibile la configurazione per trasparenza,
            # ma proteggiamo i log (vedi endpoint system-logs)
            pass
            
        return config_response

    except Exception as e:
        logger.error(f"Errore nel recupero configurazione: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# =====================
# Backtrack Analysis API Endpoints
# =====================

@app.get("/api/backtrack-analysis")
async def get_backtrack_analysis(days: int = Query(30, ge=1, le=365, description="Number of days to analyze")):
    """
    Restituisce l'analisi backtrack delle decisioni AI e performance di trading.

    Args:
        days: Numero di giorni da analizzare (default 30, max 365)

    Returns:
        Dict con analisi completa delle decisioni, performance e raccomandazioni
    """
    try:
        analyzer = BacktrackAnalyzer()
        report = analyzer.run_full_analysis(days_back=days, save_to_file=False)

        if not report:
            raise HTTPException(status_code=500, detail="Failed to generate backtrack analysis")

        return report
    except Exception as e:
        logger.error(f"Error in backtrack analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Backtrack analysis failed: {str(e)}")


@app.post("/api/backtrack-analysis/link-trades")
async def link_existing_trades():
    """
    Collega retroattivamente i trade esistenti alle operazioni AI basandosi su timestamp e simboli.

    Returns:
        Dict con numero di collegamenti effettuati
    """
    try:
        analyzer = BacktrackAnalyzer()
        linked_count = analyzer.link_existing_trades_to_operations()

        return {
            "message": f"Successfully linked {linked_count} trades to operations",
            "linked_trades": linked_count
        }
    except Exception as e:
        logger.error(f"Error linking trades: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to link trades: {str(e)}")


# =====================
# System Logs API Endpoints
# =====================

@app.get("/api/system-logs")
async def get_system_logs(lines: int = Query(100, ge=1, le=1000)):
    """
    Restituisce le ultime N righe del file di log di sistema.
    """
    if PUBLIC_DASHBOARD_MODE:
         return {"logs": ["🔒 Logs are disabled in Public Dashboard Mode"], "message": "🔒 Logs are disabled in Public Dashboard "}

    log_file = "trading_agent.log"
    try:
        if not os.path.exists(log_file):
             return {"logs": [], "message": "Log file not found"}

        # Check if it's a directory (common deployment issue)
        if os.path.isdir(log_file):
            logger.warning(f"⚠️ {log_file} is a directory, not a file. Logs unavailable.")
            return {"logs": ["⚠️ Log file misconfigured (is a directory)"], "message": "Log file is a directory"}

        with open(log_file, "r", encoding="utf-8") as f:
            # Leggi le ultime N righe usando deque
            last_lines = deque(f, maxlen=lines)
            return {"logs": list(last_lines)}
    except IsADirectoryError:
        logger.warning(f"⚠️ {log_file} is a directory, cannot read logs")
        return {"logs": ["⚠️ Log file misconfigured"], "message": "Log file is a directory"}
    except PermissionError:
        logger.warning(f"⚠️ Permission denied reading {log_file}")
        return {"logs": ["⚠️ Permission denied"], "message": "Cannot read log file (permissions)"}
    except Exception as e:
        logger.error(f"Errore nella lettura dei log: {str(e)}")
        # Return 200 with error message instead of 500
        return {"logs": [f"⚠️ Error reading logs: {str(e)}"], "message": "Error reading log file"}


# =====================
# Confidence Calibration API Endpoints
# =====================

@app.get("/api/calibration/report")
async def get_calibration_report(days: int = Query(default=30, ge=7, le=90)):
    """
    Restituisce il report di calibrazione della confidence.

    Args:
        days: Numero di giorni da analizzare (7-90)
    """
    try:
        calibrator = get_confidence_calibrator()
        report = calibrator.generate_calibration_report(days=days)
        return report.to_dict()
    except Exception as e:
        logger.error(f"Error generating calibration report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calibration/optimal-threshold")
async def get_optimal_threshold():
    """Restituisce la soglia di confidence ottimale"""
    try:
        calibrator = get_confidence_calibrator()
        threshold = calibrator.get_optimal_threshold()
        return {"optimal_threshold": threshold}
    except Exception as e:
        logger.error(f"Error getting optimal threshold: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calibration/evaluate")
async def evaluate_decision(decision: Dict):
    """
    Valuta una decisione di trading con la calibrazione storica.

    Body:
        {
            "confidence": 0.75,
            "direction": "long",
            "symbol": "BTC"
        }
    """
    try:
        calibrator = get_confidence_calibrator()
        result = calibrator.evaluate_decision(decision)
        return {
            "should_execute": result.should_execute,
            "original_confidence": result.original_confidence,
            "calibrated_confidence": result.calibrated_confidence,
            "adjustment": result.confidence_adjustment,
            "historical_win_rate": result.historical_win_rate,
            "historical_avg_pnl": result.historical_avg_pnl,
            "band_quality": result.band_quality.value,
            "reason": result.reason,
            "warnings": result.warnings
        }
    except Exception as e:
        logger.error(f"Error evaluating decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Data Export & Analytics API Endpoints
# =====================

@app.get("/api/export/full")
async def export_full_dataset(
    days: Optional[int] = Query(None, description="Number of days to export"),
    period: Optional[str] = Query(None, description="Preset period: 12h, 24h, 3d, 7d, 30d, 90d, 365d"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    include_context: bool = Query(True, description="Include AI context (indicators, news, etc.)"),
    include_metrics: bool = Query(True, description="Include analytics metrics"),
    format: str = Query('json', description="Export format: json or csv")
):
    """
    Export complete dataset con filtri temporali

    Preset periods:
    - 12h: Last 12 hours
    - 24h: Last 24 hours
    - 3d: Last 3 days
    - 7d: Last 7 days (1 week)
    - 30d: Last 30 days (1 month)
    - 90d: Last 90 days (3 months)
    - 365d: Last 365 days (1 year)

    Example: /api/export/full?period=7d&include_metrics=true
    """
    try:
        data = DataExporter.export_full_dataset(
            days=days,
            period_preset=period,
            start_date=start_date,
            end_date=end_date,
            include_context=include_context,
            include_metrics=include_metrics,
            format=format
        )

        if format == 'csv':
            csv_string = DataExporter.export_to_csv_string(data)
            return StreamingResponse(
                io.StringIO(csv_string),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=trading_data_{period or days}d.csv"}
            )
        else:
            return data

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/export/backtest")
async def export_backtest_format(
    days: int = Query(30, description="Number of days to export")
):
    """
    Export in formato ottimizzato per backtesting

    Returns:
    - decisions: AI decisions con contesto completo
    - actual_trades: Trade effettivamente eseguiti
    - correlation: Match tra decisioni e trade

    Example: /api/export/backtest?days=30
    """
    try:
        data = DataExporter.export_backtest_format(days=days)
        return data
    except Exception as e:
        logger.error(f"Backtest export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest export failed: {str(e)}")


@app.get("/api/analytics/performance")
async def get_performance_analytics(
    days: int = Query(30, description="Number of days to analyze"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g., BTC)")
):
    """
    Calcola metriche di performance avanzate

    Returns:
    - Performance metrics (Sharpe, Sortino, Max DD, etc.)
    - Equity curve
    - Breakdown per simbolo
    - Breakdown per periodo

    Example: /api/analytics/performance?days=30&symbol=BTC
    """
    try:
        # Recupera trade
        trades = DataExporter._get_trades_data(days)

        if not trades:
            raise HTTPException(status_code=404, detail="No trades found for the specified period")

        # Filtra per simbolo se richiesto
        if symbol:
            trades = [t for t in trades if t['symbol'] == symbol]
            if not trades:
                raise HTTPException(status_code=404, detail=f"No trades found for {symbol}")

        # Calcola analytics
        trades_df = pd.DataFrame(trades)
        from analytics import TradingAnalytics
        analytics = TradingAnalytics(trades_df)

        metrics = analytics.calculate_all_metrics()
        equity_curve = analytics.generate_equity_curve()
        breakdown_symbol = analytics.breakdown_by_symbol()
        breakdown_daily = analytics.breakdown_by_timeframe('daily')

        return {
            'period_days': days,
            'symbol_filter': symbol,
            'metrics': metrics.to_dict(),
            'equity_curve': equity_curve,
            'breakdown_by_symbol': breakdown_symbol,
            'breakdown_by_day': breakdown_daily
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analytics calculation failed: {str(e)}")


@app.get("/api/export/presets")
async def get_export_presets():
    """
    Restituisce lista preset periodi disponibili
    """
    return {
        'presets': [
            {'key': '12h', 'days': 0.5, 'label': 'Last 12 hours'},
            {'key': '24h', 'days': 1, 'label': 'Last 24 hours'},
            {'key': '3d', 'days': 3, 'label': 'Last 3 days'},
            {'key': '7d', 'days': 7, 'label': 'Last 7 days (1 week)'},
            {'key': '30d', 'days': 30, 'label': 'Last 30 days (1 month)'},
            {'key': '90d', 'days': 90, 'label': 'Last 90 days (3 months)'},
            {'key': '365d', 'days': 365, 'label': 'Last 365 days (1 year)'}
        ]
    }


# =====================
# Trade View Endpoints for Telegram Instant View
# =====================

@app.get("/trade-view/{trade_id}", response_class=HTMLResponse)
async def get_trade_view(trade_id: int):
    """
    Genera pagina HTML ottimizzata per Telegram Instant View

    Args:
        trade_id: ID del trade da visualizzare

    Returns:
        HTML page ottimizzato per Instant View
    """
    try:
        # Determina base URL (usa variabile ambiente o default)
        base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

        # Genera HTML
        html = TradeViewGenerator.generate_trade_view_html(trade_id, base_url)

        if not html:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        return html

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating trade view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate trade view: {str(e)}")


@app.get("/trade-view-test/{trade_id}")
async def test_trade_view(trade_id: int):
    """
    Test endpoint per verificare struttura dati (ritorna JSON anziché HTML)
    Utile per debugging
    """
    try:
        trade = TradeViewGenerator._get_trade_data(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        ai_context = TradeViewGenerator._get_ai_context(trade.get('bot_operation_id'))

        return {
            "trade": trade,
            "ai_context": ai_context,
            "instant_view_url": f"/trade-view/{trade_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.on_event("startup")
def on_startup():
    """Initialize services on startup"""
    print("Trading Agent API started")
    
    # Avvia trading engine in background thread SOLO se abilitato
    if not TRADING_BOT_ENABLED:
        logger.warning("⚠️ Trading Bot disabilitato - Non avvio trading engine")
        logger.info("💡 Per abilitare il trading, imposta TRADING_BOT_ENABLED=true nel file .env")
        return

    try:
        # Import qui per evitare import circolari
        from trading_engine import bot_state, CONFIG, WALLET_ADDRESS, TradingScheduler, trading_cycle, health_check
        
        def start_trading_engine():
            """Avvia il trading engine in un thread separato"""
            try:
                logger.info("🚀 Avvio Trading Engine in background...")
                
                # Inizializza
                if not bot_state.initialize():
                    logger.error("❌ Inizializzazione trading engine fallita")
                    return
                
                # Invia notifica di avvio via Telegram
                try:
                    if notifier.enabled:
                        logger.info("📤 Invio notifica di avvio via Telegram...")
                        # Link dashboard: prefer dedicated var, fallback to public API URL
                        dashboard_url = os.getenv("PUBLIC_DASHBOARD_URL") or os.getenv("PUBLIC_API_URL")

                        notifier.notify_startup(
                            testnet=CONFIG["TESTNET"],
                            tickers=CONFIG["TICKERS"],
                            cycle_interval_minutes=CONFIG["CYCLE_INTERVAL_MINUTES"],
                            wallet_address=WALLET_ADDRESS,
                            screening_enabled=CONFIG.get("SCREENING_ENABLED", False),
                            top_n_coins=CONFIG.get("TOP_N_COINS", 5),
                            rebalance_day=CONFIG.get("REBALANCE_DAY", "sunday"),
                            sentiment_interval_minutes=5,  # Da sentiment.py INTERVALLO_SECONDI / 60
                            health_check_interval_minutes=5,  # Da scheduler.py
                            dashboard_url=dashboard_url
                        )
                        logger.info("✅ Notifica di avvio inviata via Telegram")
                    else:
                        logger.warning("⚠️ Telegram notifier non configurato (mancano TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID)")
                except Exception as e:
                    logger.error(f"❌ Errore nell'invio notifica Telegram: {e}", exc_info=True)
                
                # Avvia thread per aggiornamento frequente account status (ogni 30s)
                def start_account_updater():
                    """Aggiorna lo stato dell'account ogni 30 secondi"""
                    import time
                    import db_utils
                    from services.history_sync import sync_trades_from_hyperliquid
                    
                    # Attendi inizializzazione
                    while not bot_state.initialized:
                        time.sleep(1)
                    
                    logger.info("🔄 Avvio loop aggiornamento account status (30s)...")
                    while True:
                        try:
                            if bot_state.trader:
                                account_status = bot_state.trader.get_account_status()
                                db_utils.log_account_status(account_status)
                                
                                # Sync trades history from Hyperliquid
                                sync_trades_from_hyperliquid(bot_state.trader)
                                
                                # logger.debug("✅ Account status e history aggiornati (background)")
                        except Exception as e:
                            logger.warning(f"⚠️ Errore aggiornamento account status: {e}")
                        
                        time.sleep(30) # Aggiorna ogni 30 secondi
                
                updater_thread = threading.Thread(target=start_account_updater, daemon=True)
                updater_thread.start()
                logger.info("✅ Account Updater thread avviato")
                
                # Avvia scheduler (bloccante)
                scheduler = TradingScheduler(
                    trading_func=trading_cycle,
                    interval_minutes=CONFIG["CYCLE_INTERVAL_MINUTES"],
                    health_check_func=health_check
                )
                
                scheduler.start()
                
            except Exception as e:
                logger.error(f"❌ Errore nell'avvio trading engine: {e}", exc_info=True)
        
        # Avvia in thread separato (daemon=True per terminare con il processo principale)
        trading_thread = threading.Thread(target=start_trading_engine, daemon=True)
        trading_thread.start()
        logger.info("✅ Trading Engine thread avviato")
        
    except ImportError as e:
        logger.warning(f"⚠️ Impossibile importare trading_engine: {e}")
        logger.warning("⚠️ Trading engine non avviato. Avvia manualmente con: python trading_engine.py")
    except Exception as e:
        logger.error(f"❌ Errore nell'avvio trading engine: {e}", exc_info=True)


@app.on_event("shutdown")
def on_shutdown():
    """Cleanup on shutdown"""
    print("Trading Agent API shutting down")
    # TODO: Cleanup services


# =====================
# Prometheus Metrics Endpoint
# =====================

@app.get("/api/metrics")
async def get_metrics(format: str = Query("json", description="Output format: json or prometheus")):
    """
    Restituisce metriche di sistema per monitoring (Prometheus/Grafana).

    Args:
        format: 'json' (default) o 'prometheus' (text format)

    Returns:
        Metriche in formato JSON o Prometheus text-based
    """
    try:
        # Recupera dati da database
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Latest account snapshot
                cur.execute("""
                    SELECT balance_usd, created_at
                    FROM account_snapshots
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                account_row = cur.fetchone()

                # Open positions count from latest snapshot
                cur.execute("""
                    SELECT COUNT(*)
                    FROM open_positions op
                    WHERE op.snapshot_id = (
                        SELECT id FROM account_snapshots
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                """)
                positions_count = cur.fetchone()[0] if cur.rowcount > 0 else 0

                # Trade statistics (last 24 hours)
                cur.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                        COUNT(*) FILTER (WHERE pnl_usd < 0) as losing_trades,
                        COALESCE(SUM(pnl_usd), 0) as total_pnl_24h,
                        COALESCE(AVG(pnl_usd), 0) as avg_pnl
                    FROM executed_trades
                    WHERE status = 'closed'
                        AND created_at >= NOW() - INTERVAL '24 hours'
                """)
                trade_stats = cur.fetchone()

                # Recent bot operations (last hour)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM bot_operations
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)
                recent_operations = cur.fetchone()[0]

        # Parse data
        current_balance = float(account_row[0]) if account_row and account_row[0] else 0.0
        balance_timestamp = account_row[1] if account_row else None

        total_trades = trade_stats[0] if trade_stats else 0
        winning_trades = trade_stats[1] if trade_stats else 0
        losing_trades = trade_stats[2] if trade_stats else 0
        total_pnl_24h = float(trade_stats[3]) if trade_stats else 0.0
        avg_pnl = float(trade_stats[4]) if trade_stats else 0.0
        win_rate_24h = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # System info
        from trading_engine import CONFIG
        testnet_mode = CONFIG.get("TESTNET", True)
        bot_enabled = TRADING_BOT_ENABLED

        # Build metrics dict
        metrics = {
            "trading_bot_enabled": 1 if bot_enabled else 0,
            "trading_testnet_mode": 1 if testnet_mode else 0,
            "account_balance_usd": current_balance,
            "open_positions_count": positions_count,
            "trades_total_24h": total_trades,
            "trades_winning_24h": winning_trades,
            "trades_losing_24h": losing_trades,
            "trades_win_rate_24h": win_rate_24h,
            "pnl_total_24h_usd": total_pnl_24h,
            "pnl_avg_24h_usd": avg_pnl,
            "bot_operations_1h": recent_operations,
            "system_health": 1  # 1 = healthy, 0 = unhealthy
        }

        # Return based on format
        if format.lower() == "prometheus":
            # Prometheus text-based format
            lines = []
            lines.append("# HELP trading_bot_enabled Whether the trading bot is enabled (1) or disabled (0)")
            lines.append("# TYPE trading_bot_enabled gauge")
            lines.append(f"trading_bot_enabled {metrics['trading_bot_enabled']}")
            lines.append("")

            lines.append("# HELP trading_testnet_mode Whether running in testnet (1) or mainnet (0)")
            lines.append("# TYPE trading_testnet_mode gauge")
            lines.append(f"trading_testnet_mode {metrics['trading_testnet_mode']}")
            lines.append("")

            lines.append("# HELP account_balance_usd Current account balance in USD")
            lines.append("# TYPE account_balance_usd gauge")
            lines.append(f"account_balance_usd {metrics['account_balance_usd']}")
            lines.append("")

            lines.append("# HELP open_positions_count Number of currently open positions")
            lines.append("# TYPE open_positions_count gauge")
            lines.append(f"open_positions_count {metrics['open_positions_count']}")
            lines.append("")

            lines.append("# HELP trades_total_24h Total number of trades in last 24 hours")
            lines.append("# TYPE trades_total_24h counter")
            lines.append(f"trades_total_24h {metrics['trades_total_24h']}")
            lines.append("")

            lines.append("# HELP trades_winning_24h Number of winning trades in last 24 hours")
            lines.append("# TYPE trades_winning_24h counter")
            lines.append(f"trades_winning_24h {metrics['trades_winning_24h']}")
            lines.append("")

            lines.append("# HELP trades_losing_24h Number of losing trades in last 24 hours")
            lines.append("# TYPE trades_losing_24h counter")
            lines.append(f"trades_losing_24h {metrics['trades_losing_24h']}")
            lines.append("")

            lines.append("# HELP trades_win_rate_24h Win rate percentage in last 24 hours")
            lines.append("# TYPE trades_win_rate_24h gauge")
            lines.append(f"trades_win_rate_24h {metrics['trades_win_rate_24h']}")
            lines.append("")

            lines.append("# HELP pnl_total_24h_usd Total PnL in USD in last 24 hours")
            lines.append("# TYPE pnl_total_24h_usd gauge")
            lines.append(f"pnl_total_24h_usd {metrics['pnl_total_24h_usd']}")
            lines.append("")

            lines.append("# HELP pnl_avg_24h_usd Average PnL per trade in USD in last 24 hours")
            lines.append("# TYPE pnl_avg_24h_usd gauge")
            lines.append(f"pnl_avg_24h_usd {metrics['pnl_avg_24h_usd']}")
            lines.append("")

            lines.append("# HELP bot_operations_1h Number of bot operations in last hour")
            lines.append("# TYPE bot_operations_1h counter")
            lines.append(f"bot_operations_1h {metrics['bot_operations_1h']}")
            lines.append("")

            lines.append("# HELP system_health System health status (1=healthy, 0=unhealthy)")
            lines.append("# TYPE system_health gauge")
            lines.append(f"system_health {metrics['system_health']}")

            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content="\n".join(lines), media_type="text/plain; version=0.0.4")
        else:
            # JSON format
            return {
                "status": "healthy" if metrics["system_health"] == 1 else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics
            }

    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        if format.lower() == "prometheus":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(
                content="# Error generating metrics\nsystem_health 0\n",
                media_type="text/plain; version=0.0.4",
                status_code=500
            )
        else:
            raise HTTPException(status_code=500, detail=f"Metrics generation failed: {str(e)}")


# Serve frontend index.html for root and SPA routes
@app.get("/")
async def serve_root():
    """Serve the frontend index.html for root route"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Frontend not built yet"}

# Catch-all route for SPA routing (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve the frontend index.html for SPA routes that don't match API/static"""
    # Skip API and static routes
    if (full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("docs") or
        full_path.startswith("openapi.json") or full_path.startswith("trade-view")):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Frontend not built yet"}
