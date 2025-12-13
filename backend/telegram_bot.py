"""
Bot Telegram interattivo per Trading Agent
Gestisce comandi utente e notifiche in tempo reale
Supporta sistema di permessi a due livelli (admin/pubblico) con rate limiting
"""
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, List, Dict, Set
from threading import Thread
from functools import wraps
from collections import defaultdict
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from notifications import TelegramNotifier
from token_tracker import get_token_tracker

load_dotenv()
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# PERMISSION SYSTEM CONFIGURATION
# ============================================================

# Admin IDs - Caricato da variabile d'ambiente (comma-separated)
ADMIN_TELEGRAM_IDS = os.getenv("ADMIN_TELEGRAM_IDS", "")
ADMIN_IDS: Set[int] = set()
if ADMIN_TELEGRAM_IDS:
    try:
        ADMIN_IDS = {int(x.strip()) for x in ADMIN_TELEGRAM_IDS.split(",") if x.strip()}
        logger.info(f"✅ Admin IDs configurati: {len(ADMIN_IDS)} amministratori")
    except ValueError as e:
        logger.error(f"❌ Errore nel parsing ADMIN_TELEGRAM_IDS: {e}")

# ============================================================
# RATE LIMITING CONFIGURATION
# ============================================================

# Rate limiting settings
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))  # Max richieste
RATE_LIMIT_WINDOW_MINUTES = int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "5"))  # Finestra temporale
RATE_LIMIT_ADMIN_EXEMPT = os.getenv("RATE_LIMIT_ADMIN_EXEMPT", "true").lower() in ("true", "1", "yes")

# Storage per tracking richieste (in produzione usare Redis)
user_request_timestamps: Dict[int, List[datetime]] = defaultdict(list)

# ============================================================
# DISCLAIMER AND WELCOME MESSAGES
# ============================================================

DISCLAIMER = """
⚠️ **IMPORTANTE - Leggere Attentamente**

Questo bot è parte del progetto open source **Trading Agent**, ispirato a Alpha Arena.

**Disclaimer:**
- Solo scopo educativo e sperimentale
- NON costituisce consulenza finanziaria
- Il trading di criptovalute comporta rischi elevati
- Possibile perdita totale del capitale investito
- DYOR (Do Your Own Research)

**Privacy:**
- I comandi pubblici sono limitati (rate limiting)
- Non vengono raccolti dati personali
- Le statistiche sono aggregate

🔗 Dashboard: https://trading-dashboard.up.railway.app/
💻 GitHub: [link al repo]

Usa /help per vedere i comandi disponibili.
"""


# ============================================================
# PERMISSION SYSTEM FUNCTIONS
# ============================================================

def admin_only(func):
    """Decorator per comandi riservati agli admin"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "⛔ **Accesso negato**\n"
                "Questo comando è riservato agli amministratori.\n\n"
                "Usa /help per vedere i comandi disponibili.",
                parse_mode='Markdown'
            )
            logger.warning(f"Tentativo accesso admin negato: user_id={user_id}, comando={update.message.text}")
            return
        return await func(update, context)
    return wrapper

def public_command(func):
    """Decorator per comandi pubblici con rate limiting"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # Check rate limit
        if not check_rate_limit(user_id):
            await update.message.reply_text(
                "⏱️ **Rate limit superato**\n"
                "Hai raggiunto il limite di richieste. Riprova tra qualche minuto.",
                parse_mode='Markdown'
            )
            logger.warning(f"Rate limit exceeded: user_id={user_id}")
            return

        return await func(update, context)
    return wrapper

def check_rate_limit(user_id: int) -> bool:
    """
    Verifica se l'utente ha superato il rate limit.
    Returns True se la richiesta è permessa, False se rate limit superato.
    """
    # Admin esenti
    if RATE_LIMIT_ADMIN_EXEMPT and user_id in ADMIN_IDS:
        return True

    now = datetime.now()
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    # Rimuovi timestamp vecchi
    user_request_timestamps[user_id] = [
        timestamp for timestamp in user_request_timestamps[user_id]
        if timestamp > window_start
    ]

    # Check limite
    if len(user_request_timestamps[user_id]) >= RATE_LIMIT_REQUESTS:
        return False

    # Aggiungi nuovo timestamp
    user_request_timestamps[user_id].append(now)
    return True

def get_rate_limit_status(user_id: int) -> dict:
    """Ottieni status rate limiting per un utente"""
    now = datetime.now()
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    recent_requests = [
        ts for ts in user_request_timestamps.get(user_id, [])
        if ts > window_start
    ]

    return {
        "requests_used": len(recent_requests),
        "requests_limit": RATE_LIMIT_REQUESTS,
        "window_minutes": RATE_LIMIT_WINDOW_MINUTES,
        "requests_remaining": max(0, RATE_LIMIT_REQUESTS - len(recent_requests))
    }


class TradingTelegramBot:
    """Bot Telegram interattivo per controllo Trading Agent"""

    def __init__(self, token: str = None, chat_id: str = None, chat_ids: Optional[List[str]] = None):
        self.token = token or TELEGRAM_BOT_TOKEN

        env_chat_ids = os.getenv("TELEGRAM_CHAT_IDS")
        parsed_env = [c.strip() for c in env_chat_ids.split(",")] if env_chat_ids else []

        if chat_ids:
            self.chat_ids = chat_ids
        elif parsed_env:
            self.chat_ids = [c for c in parsed_env if c]
        elif chat_id or TELEGRAM_CHAT_ID:
            self.chat_ids = [chat_id or TELEGRAM_CHAT_ID]
        else:
            self.chat_ids = []

        self.chat_id = self.chat_ids[0] if self.chat_ids else None  # backward compatibility
        self.enabled = bool(self.token and self.chat_ids)

        # Trading Agent reference (set later via set_trading_agent)
        self.trading_agent: Optional[Any] = None

        # Application and thread management
        self.application: Optional[Application] = None
        self.thread: Optional[Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Notifier for push notifications (compatibility with existing system)
        self.notifier = TelegramNotifier(token=self.token, chat_ids=self.chat_ids)

        # Persisted message id for live log view per chat
        self.logs_message_ids: Dict[int, int] = {}

        if not self.enabled:
            logger.warning("⚠️ Telegram bot non configurato (mancano TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID)")
        else:
            logger.info("✅ Telegram bot configurato correttamente")

    def set_trading_agent(self, agent: Any) -> None:
        """Collega il Trading Agent al bot"""
        self.trading_agent = agent
        logger.info("✅ Trading Agent collegato al bot Telegram")

    async def _send_message(self, chat_id: int, text: str, parse_mode: str = "HTML", reply_markup=None):
        """Helper per inviare messaggi sia da comando sia da callback."""
        from telegram.constants import ParseMode
        await self.application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML if parse_mode == "HTML" else parse_mode,
            reply_markup=reply_markup
        )

    def _is_authorized(self, update: Update, require_admin: bool = False) -> bool:
        """
        Verifica se l'utente è autorizzato

        Args:
            update: Update object da Telegram
            require_admin: Se True, richiede permessi admin

        Returns:
            True se autorizzato, False altrimenti
        """
        if not update.effective_chat:
            return False

        user_id = update.effective_user.id if update.effective_user else None
        user_chat_id = str(update.effective_chat.id)

        if require_admin:
            # Per comandi admin, controllare sia chat_id che user_id admin
            chat_authorized = user_chat_id in self.chat_ids
            admin_authorized = user_id in ADMIN_IDS if user_id else False
            authorized = chat_authorized and admin_authorized

            if not authorized:
                logger.warning(f"⚠️ Tentativo accesso admin negato: chat_id={user_chat_id}, user_id={user_id}")
        else:
            # Per comandi pubblici, permettere sempre (rate limiting gestito dai decoratori)
            authorized = True

        return authorized

    async def _log_command(self, update: Update, command: str, is_admin: bool = False) -> None:
        """Log di tutti i comandi ricevuti"""
        user = update.effective_user
        chat_id = update.effective_chat.id if update.effective_chat else "unknown"
        user_id = user.id if user else "unknown"
        permission_level = "admin" if is_admin else "public"
        logger.info(f"📝 Comando ricevuto: /{command} da {user.username or user.first_name} (user_id: {user_id}, chat_id: {chat_id}, level: {permission_level})")

    # ==================== COMMAND HANDLERS ====================

    @public_command
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Messaggio di benvenuto con disclaimer"""
        user = update.effective_user
        user_id = user.id if user else "unknown"
        is_admin = user_id in ADMIN_IDS

        await self._log_command(update, "start", is_admin)

        # Determina stato e network per admin
        if self.trading_agent and is_admin:
            is_running = getattr(self.trading_agent, 'is_running', False)
            status_emoji = "🟢" if is_running else "🔴"
            status_text = "Attivo" if is_running else "Fermo"

            # Detect testnet from config
            config = getattr(self.trading_agent, 'config', {})
            is_testnet = config.get('TESTNET', False)
            network = "Testnet" if is_testnet else "Mainnet"

            # Get tickers
            tickers = config.get('TICKERS', ['BTC', 'ETH', 'SOL'])
            tickers_str = ", ".join(tickers)
        else:
            status_emoji = "⚪"
            status_text = "Non connesso"
            network = "N/A"
            tickers_str = "N/A"

        # Messaggio di benvenuto personalizzato
        user_name = user.first_name if user else "Utente"
        admin_badge = " 👑" if is_admin else ""

        welcome = f"""
👋 Benvenuto **{user_name}**{admin_badge}!

{DISCLAIMER}
"""

        # Keyboard diversa per admin e utenti pubblici
        if is_admin:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Status", callback_data="cmd:status"),
                    InlineKeyboardButton("💰 Balance", callback_data="cmd:balance"),
                    InlineKeyboardButton("📂 Posizioni", callback_data="cmd:positions"),
                ],
                [
                    InlineKeyboardButton("🧾 Today", callback_data="cmd:today"),
                    InlineKeyboardButton("⚙️ Config", callback_data="cmd:config"),
                    InlineKeyboardButton("🪵 Log", callback_data="cmd:logs"),
                ],
                [
                    InlineKeyboardButton("🆘 Help", callback_data="cmd:help"),
                    InlineKeyboardButton("🛑 Stop", callback_data="cmd:stop"),
                    InlineKeyboardButton("▶️ Resume", callback_data="cmd:resume"),
                ],
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Stats", callback_data="cmd:stats"),
                    InlineKeyboardButton("📈 Performance", callback_data="cmd:performance"),
                    InlineKeyboardButton("💼 Posizioni", callback_data="cmd:positions"),
                ],
                [
                    InlineKeyboardButton("🔔 Segnali", callback_data="cmd:last_signals"),
                    InlineKeyboardButton("🤖 Status", callback_data="cmd:status"),
                ],
                [
                    InlineKeyboardButton("ℹ️ About", callback_data="cmd:about"),
                    InlineKeyboardButton("📖 Help", callback_data="cmd:help"),
                ],
            ])

        chat_id = update.effective_chat.id if update.effective_chat else self.chat_id
        if chat_id:
            await self._send_message(chat_id, welcome, parse_mode="Markdown", reply_markup=keyboard)

    async def _get_recent_logs(self, lines: int = 20) -> str:
        """Legge le ultime N righe del log di sistema."""
        log_path = os.getenv(
            "LOG_FILE",
            os.path.join(os.path.dirname(__file__), "trading_agent.log")
        )
        if not os.path.exists(log_path):
            return "⚠️ Log file non trovato"

        try:
            with open(log_path, "r") as f:
                content = f.readlines()
            tail = content[-lines:] if len(content) >= lines else content
            formatted = "".join(tail).rstrip()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"🪵 <b>System Logs</b>\n\n<code>{formatted}</code>\n\n⏱ Aggiornato: {ts}"
        except Exception as e:
            logger.error(f"Errore lettura log: {e}")
            return f"❌ Errore lettura log: {e}"

    # ==================== PUBLIC COMMANDS ====================

    @public_command
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📊 Statistiche generali del bot"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "stats", is_admin)

        try:
            # Get basic stats from database
            from db_utils import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Count total trades
                    cur.execute("SELECT COUNT(*) FROM bot_operations WHERE operation IN ('open', 'close')")
                    total_trades = cur.fetchone()[0]

                    # Count winning trades
                    cur.execute("""
                        SELECT COUNT(*) FROM bot_operations
                        WHERE operation = 'close' AND pnl_usd > 0
                    """)
                    winning_trades = cur.fetchone()[0]

                    # Get total PnL
                    cur.execute("SELECT COALESCE(SUM(pnl_usd), 0) FROM bot_operations WHERE operation = 'close'")
                    total_pnl = float(cur.fetchone()[0])

                    # Get win rate
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                    # Get uptime (approximated from first trade to now)
                    cur.execute("SELECT MIN(created_at) FROM bot_operations")
                    first_trade = cur.fetchone()[0]
                    uptime_days = (datetime.now(timezone.utc) - first_trade).days if first_trade else 0

            # Get LLM costs
            try:
                tracker = get_token_tracker()
                today_stats = tracker.get_daily_stats()
                total_cost_today = today_stats.total_cost_usd
            except:
                total_cost_today = 0.0

            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"

            msg = f"""📊 <b>STATISTICHE TRADING AGENT</b>

<b>Performance Generale:</b>
├ Trades Totali: {total_trades}
├ Win Rate: {win_rate:.1f}%
├ PnL Totale: {pnl_emoji} ${total_pnl:,.2f}
└ Uptime: {uptime_days} giorni

<b>Costi LLM (oggi):</b> ${total_cost_today:.4f}

<i>Statistiche aggiornate in tempo reale</i>"""

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel comando /stats: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero statistiche: {str(e)}")

    @public_command
    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📈 Performance dell'agente (ultimi 7/30 giorni)"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "performance", is_admin)

        try:
            from db_utils import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get performance for different periods
                    periods = [
                        (7, "7 giorni"),
                        (30, "30 giorni")
                    ]

                    msg = "📈 <b>PERFORMANCE TRADING AGENT</b>\n\n"

                    for days, label in periods:
                        start_date = datetime.now(timezone.utc) - timedelta(days=days)

                        # Get trades in period
                        cur.execute("""
                            SELECT COUNT(*) FROM bot_operations
                            WHERE operation = 'close' AND created_at >= %s
                        """, (start_date,))
                        trades_count = cur.fetchone()[0]

                        # Get PnL in period
                        cur.execute("""
                            SELECT COALESCE(SUM(pnl_usd), 0) FROM bot_operations
                            WHERE operation = 'close' AND created_at >= %s
                        """, (start_date,))
                        period_pnl = float(cur.fetchone()[0])

                        # Get win rate for period
                        cur.execute("""
                            SELECT COUNT(*) FROM bot_operations
                            WHERE operation = 'close' AND pnl_usd > 0 AND created_at >= %s
                        """, (start_date,))
                        winning_trades = cur.fetchone()[0]

                        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0
                        pnl_emoji = "🟢" if period_pnl >= 0 else "🔴"

                        msg += f"<b>{label}:</b>\n"
                        msg += f"├ Trades: {trades_count}\n"
                        msg += f"├ Win Rate: {win_rate:.1f}%\n"
                        msg += f"└ PnL: {pnl_emoji} ${period_pnl:,.2f}\n\n"

                    # Get Sharpe ratio approximation (simplified)
                    # This is a basic approximation - real Sharpe would need daily returns
                    try:
                        cur.execute("""
                            SELECT AVG(pnl_usd), STDDEV(pnl_usd)
                            FROM bot_operations
                            WHERE operation = 'close' AND created_at >= %s
                        """, (datetime.now(timezone.utc) - timedelta(days=30),))
                        avg_pnl, std_pnl = cur.fetchone()

                        if std_pnl and std_pnl > 0:
                            sharpe_ratio = (float(avg_pnl) / float(std_pnl)) * (365**0.5)  # Annualized
                            msg += f"<b>Risk Metrics (30g):</b>\n"
                            msg += f"├ Sharpe Ratio: {sharpe_ratio:.2f}\n"
                            msg += f"└ Volatilità giornaliera: ${std_pnl:.2f}\n\n"
                    except:
                        pass

                    msg += "<i>Performance calcolata su trades chiusi</i>"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel comando /performance: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero performance: {str(e)}")

    @public_command
    async def cmd_last_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔔 Ultimi segnali generati dall'AI (ultimi 5)"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "last_signals", is_admin)

        try:
            from db_utils import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get last 5 signals/decisions
                    cur.execute("""
                        SELECT symbol, direction, decision_reason, confidence, created_at
                        FROM ai_signals
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    signals = cur.fetchall()

            if not signals:
                await update.message.reply_text("📭 Nessun segnale AI trovato al momento.")
                return

            msg = "🔔 <b>ULTIMI SEGNALI AI</b>\n\n"

            for i, signal in enumerate(signals, 1):
                symbol, direction, reason, confidence, created_at = signal
                time_str = created_at.strftime('%d/%m %H:%M')

                direction_emoji = "🟢" if direction == 'long' else "🔴" if direction == 'short' else "⚪"
                confidence_pct = confidence * 100 if confidence else 0

                # Truncate reason if too long
                short_reason = reason[:100] + "..." if reason and len(reason) > 100 else reason or "N/A"

                msg += f"<b>{i}. {symbol} {direction_emoji}</b>\n"
                msg += f"├ Ora: {time_str}\n"
                msg += f"├ Confidenza: {confidence_pct:.1f}%\n"
                msg += f"└ Motivo: {short_reason}\n\n"

            msg += "<i>Segnali generati dall'AI decision engine</i>"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel comando /last_signals: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero segnali: {str(e)}")

    @public_command
    async def cmd_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ℹ️ Info sul progetto"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "about", is_admin)

        about = """
🤖 **Trading Agent**

Un progetto open source di trading AI-driven ispirato a Alpha Arena.

**Features:**
• Analisi multi-sorgente (market data, news, sentiment)
• LLM-powered decision making
• Multi-exchange support (Hyperliquid, Binance, etc.)
• Advanced risk management

**Stack:**
• Backend: FastAPI + Python
• AI: Multiple LLM providers
• Database: PostgreSQL
• Frontend: React

🔗 Dashboard: https://trading-dashboard.up.railway.app/
📚 Docs: [link]
💻 GitHub: [link]
"""
        await update.message.reply_text(about, parse_mode="Markdown")

    # ==================== ADMIN COMMANDS ====================

    @admin_only
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Messaggio persistente con log e bottone refresh (ADMIN ONLY)."""
        await self._log_command(update, "logs", True)

        if not self._is_authorized(update, require_admin=True):
            return

        text = await self._get_recent_logs()
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔄 Aggiorna", callback_data="refresh_logs")]]
        )

        chat_id = update.effective_chat.id if update.effective_chat else None

        if chat_id and chat_id in self.logs_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=self.logs_message_ids[chat_id],
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.warning(f"⚠️ Impossibile aggiornare messaggio log esistente (chat {chat_id}): {e}")

        if chat_id:
            sent = await self.application.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)
            self.logs_message_ids[chat_id] = sent.message_id

    @public_command
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🤖 Status del sistema (trading attivo/paused, exchanges connessi)"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "status", is_admin)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        # Get status info
        is_running = getattr(self.trading_agent, 'is_running', False)
        last_cycle = getattr(self.trading_agent, 'last_cycle_time', None)
        next_cycle = getattr(self.trading_agent, 'next_cycle_time', None)
        cycle_interval = getattr(self.trading_agent, 'cycle_interval_minutes', 60)

        status_emoji = "🟢" if is_running else "🔴"
        status_text = "ATTIVO" if is_running else "IN PAUSA"

        # Format times
        if last_cycle:
            last_cycle_str = last_cycle.strftime("%H:%M:%S UTC")
        else:
            last_cycle_str = "Mai eseguito"

        if next_cycle:
            next_cycle_str = next_cycle.strftime("%H:%M:%S UTC")
            time_until = (next_cycle - datetime.now(timezone.utc)).total_seconds()
            minutes_until = int(time_until / 60)
            next_cycle_str += f" (tra {minutes_until}m)"
        else:
            next_cycle_str = "N/A"

        # Show different info for admin vs public
        if is_admin:
            # Admin gets full info including costs
            try:
                tracker = get_token_tracker()
                today_stats = tracker.get_daily_stats()
                cost_today = today_stats.total_cost_usd
                cost_str = f"${cost_today:.4f}"
            except Exception as e:
                logger.error(f"Errore lettura costi token: {e}")
                cost_str = "N/A"

            msg = f"""📊 <b>STATO TRADING ENGINE</b>

<b>Stato:</b> {status_emoji} {status_text}
<b>Ultimo ciclo:</b> {last_cycle_str}
<b>Prossimo ciclo:</b> {next_cycle_str}
<b>Intervallo cicli:</b> {cycle_interval} minuti

💰 <b>Costo LLM oggi:</b> {cost_str}

<i>Il bot sta {('eseguendo' if is_running else 'aspettando')} il trading automatico.</i>"""
        else:
            # Public users get limited info
            msg = f"""🤖 <b>STATO SISTEMA</b>

<b>Stato Trading:</b> {status_emoji} {status_text}
<b>Ultimo ciclo:</b> {last_cycle_str}
<b>Prossimo ciclo:</b> {next_cycle_str}

<i>Il sistema sta {('eseguendo' if is_running else 'aspettando')} l'analisi di mercato.</i>"""

        await update.message.reply_text(msg, parse_mode="HTML")

    @admin_only
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """💰 Saldo wallet corrente (ADMIN ONLY)"""
        await self._log_command(update, "balance", True)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        try:
            # Get balance from trading agent
            trader = getattr(self.trading_agent, 'trader', None)
            if not trader:
                await update.message.reply_text("⚠️ Trader non disponibile.")
                return

            # Fetch current account state
            account_state = trader.get_account_state()
            balance_usd = account_state.get('balance_usd', 0.0)
            margin_used = account_state.get('margin_used', 0.0)
            available = balance_usd - margin_used

            # Get initial balance if tracked
            initial_balance = getattr(self.trading_agent, 'initial_balance', balance_usd)
            pnl = balance_usd - initial_balance
            pnl_pct = (pnl / initial_balance * 100) if initial_balance > 0 else 0.0

            pnl_emoji = "🟢" if pnl >= 0 else "🔴"

            msg = f"""💰 <b>SALDO WALLET</b>

<b>Balance:</b> ${balance_usd:,.2f}
<b>Margine usato:</b> ${margin_used:,.2f}
<b>Disponibile:</b> ${available:,.2f}

<b>PnL totale:</b> {pnl_emoji} ${pnl:,.2f} ({pnl_pct:+.2f}%)
<b>Balance iniziale:</b> ${initial_balance:,.2f}

<i>Aggiornato al: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</i>"""

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel recupero balance: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero del saldo: {str(e)}")

    @public_command
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """💼 Posizioni aperte (senza dettagli sensibili come quantità esatte)"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "positions", is_admin)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        try:
            # Get positions from trading agent
            trader = getattr(self.trading_agent, 'trader', None)
            if not trader:
                await update.message.reply_text("⚠️ Trader non disponibile.")
                return

            account_state = trader.get_account_state()
            positions = account_state.get('open_positions', [])

            if not positions:
                await update.message.reply_text("📭 Nessuna posizione aperta al momento.")
                return

            msg = "<b>💼 POSIZIONI APERTE</b>\n\n"

            total_pnl_pct = 0.0
            position_count = len(positions)

            for pos in positions:
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('side', 'N/A')
                entry_price = pos.get('entry_price', 0.0)
                mark_price = pos.get('mark_price', 0.0)
                pnl_usd = pos.get('pnl_usd', 0.0)

                # Calculate PnL percentage
                pnl_pct = (pnl_usd / (entry_price * pos.get('size', 1))) * 100 if entry_price > 0 else 0
                total_pnl_pct += pnl_pct

                # Duration (approximate)
                created_at = pos.get('created_at')
                if created_at:
                    if isinstance(created_at, str):
                        duration_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(created_at.replace('Z', '+00:00'))).total_seconds() / 3600
                    else:
                        duration_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                    duration_str = f"{duration_hours:.1f}h"
                else:
                    duration_str = "N/A"

                side_emoji = "🟢" if side.lower() == 'long' else "🔴"
                pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

                if is_admin:
                    # Admin gets full details
                    size = pos.get('size', 0.0)
                    leverage = pos.get('leverage', 'N/A')
                    msg += f"""{side_emoji} <b>{symbol}</b> - {side.upper()}
├ Size: {size:.6f}
├ Entry: ${entry_price:,.4f} | Mark: ${mark_price:,.4f}
├ PnL: {pnl_emoji} ${pnl_usd:,.4f} ({pnl_pct:+.2f}%)
├ Leverage: {leverage}
└ Durata: {duration_str}

"""
                else:
                    # Public users get limited info
                    msg += f"""{side_emoji} <b>{symbol}</b> - {side.upper()}
├ Prezzo entrata: ${entry_price:,.2f}
├ PnL: {pnl_emoji} {pnl_pct:+.2f}%
└ Durata: {duration_str}

"""

            if is_admin:
                total_emoji = "🟢" if total_pnl_pct >= 0 else "🔴"
                msg += f"<b>PnL Totale:</b> {total_emoji} {total_pnl_pct:+.2f}%"
            else:
                msg += f"<b>Totale posizioni:</b> {position_count}"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel recupero posizioni: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero delle posizioni: {str(e)}")

    @admin_only
    async def cmd_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📊 Riepilogo giornaliero (ADMIN ONLY)"""
        await self._log_command(update, "today", True)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        try:
            # Get daily stats from database
            from db_utils import get_connection

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get today's operations
                    cur.execute("""
                        SELECT operation, symbol, direction, created_at
                        FROM bot_operations
                        WHERE created_at >= %s
                        ORDER BY created_at DESC
                    """, (today_start,))
                    operations = cur.fetchall()

                    # Get balance history for today
                    cur.execute("""
                        SELECT balance_usd, created_at
                        FROM account_snapshots
                        WHERE created_at >= %s
                        ORDER BY created_at ASC
                    """, (today_start,))
                    balances = cur.fetchall()

            # Calculate stats
            num_trades = len([op for op in operations if op[0] in ('open', 'close')])
            num_open = len([op for op in operations if op[0] == 'open'])
            num_close = len([op for op in operations if op[0] == 'close'])

            # Calculate PnL
            if balances and len(balances) >= 2:
                start_balance = float(balances[0][0])
                current_balance = float(balances[-1][0])
                daily_pnl = current_balance - start_balance
                daily_pnl_pct = (daily_pnl / start_balance * 100) if start_balance > 0 else 0.0
            else:
                daily_pnl = 0.0
                daily_pnl_pct = 0.0

            pnl_emoji = "🟢" if daily_pnl >= 0 else "🔴"

            msg = f"""📊 <b>RIEPILOGO GIORNALIERO</b>
<i>{datetime.now(timezone.utc).strftime('%d/%m/%Y')}</i>

<b>Operazioni totali:</b> {num_trades}
  • Aperture: {num_open}
  • Chiusure: {num_close}

<b>PnL giornaliero:</b> {pnl_emoji} ${daily_pnl:,.2f} ({daily_pnl_pct:+.2f}%)

<b>Ultime operazioni:</b>
"""

            # Show last 5 operations
            for i, op in enumerate(operations[:5]):
                operation, symbol, direction, created_at = op
                time_str = created_at.strftime('%H:%M')
                direction_emoji = "🟢" if direction == 'long' else "🔴" if direction == 'short' else "⚪"
                msg += f"{time_str} - {operation.upper()} {direction_emoji} {symbol or ''}\n"

            if not operations:
                msg += "<i>Nessuna operazione oggi</i>\n"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel recupero riepilogo giornaliero: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero del riepilogo: {str(e)}")

    @admin_only
    async def cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """⚙️ Configurazione completa (ADMIN ONLY)"""
        await self._log_command(update, "config", True)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        config = getattr(self.trading_agent, 'config', {})

        # Extract config values
        tickers = config.get('TICKERS', ['BTC', 'ETH', 'SOL'])
        max_leverage = config.get('MAX_LEVERAGE', 3)
        max_position_size = config.get('MAX_POSITION_SIZE_PCT', 0.3)
        is_testnet = config.get('TESTNET', False)
        cycle_interval = config.get('CYCLE_INTERVAL_MINUTES', 60)
        use_screener = config.get('USE_COIN_SCREENER', False)

        network_emoji = "🧪" if is_testnet else "🌐"

        msg = f"""⚙️ <b>CONFIGURAZIONE</b>

<b>Network:</b> {network_emoji} {'Testnet' if is_testnet else 'Mainnet'}
<b>Tickers:</b> {', '.join(tickers)}
<b>Coin Screener:</b> {'✅ Attivo' if use_screener else '❌ Disattivo'}

<b>Risk Management:</b>
  • Max Leverage: {max_leverage}x
  • Max Position Size: {max_position_size * 100:.0f}% del balance

<b>Ciclo Trading:</b>
  • Intervallo: {cycle_interval} minuti

<i>Configurazione caricata da .env e config.py</i>"""

        await update.message.reply_text(msg, parse_mode="HTML")

    @admin_only
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """⏯️ Ferma trading automatico (ADMIN ONLY)"""
        await self._log_command(update, "stop", True)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Sì, ferma", callback_data="confirm_stop"),
                InlineKeyboardButton("❌ Annulla", callback_data="cancel_stop"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ <b>CONFERMA STOP TRADING</b>\n\nSei sicuro di voler fermare il trading automatico?\n\n"
            "<i>Le posizioni aperte rimarranno aperte.</i>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    @admin_only
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """▶️ Riprendi trading automatico (ADMIN ONLY)"""
        await self._log_command(update, "resume", True)

        if not self.trading_agent:
            await update.message.reply_text("⚪ Trading Agent non connesso.")
            return

        try:
            # Resume trading
            if hasattr(self.trading_agent, 'resume'):
                self.trading_agent.resume()
                await update.message.reply_text("✅ Trading ripreso! Il bot riprenderà l'esecuzione automatica.")
            else:
                # Fallback: set is_running flag
                self.trading_agent.is_running = True
                await update.message.reply_text("✅ Trading ripreso!")

        except Exception as e:
            logger.error(f"❌ Errore nel resume trading: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")

    @public_command
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📖 Guida comandi disponibili"""
        user = update.effective_user
        is_admin = user.id in ADMIN_IDS if user else False
        await self._log_command(update, "help", is_admin)

        if is_admin:
            help_msg = """📖 <b>COMANDI DISPONIBILI</b>

<b>📊 Informazioni:</b>
/stats - Statistiche generali
/performance - Performance storica
/positions - Posizioni aperte (dettagliate)
/last_signals - Ultimi segnali AI
/status - Stato sistema
/tokens - Consumo token LLM
/config - Configurazione completa

<b>⚙️ Controllo Trading:</b>
/balance - Saldo wallet
/today - Riepilogo giornaliero
/stop - Ferma trading
/resume - Riprendi trading

<b>🔧 Admin:</b>
/logs - System logs
/admin_help - Comandi admin

<b>ℹ️ Altro:</b>
/about - Info progetto
/help - Questa guida

<i>👑 Accesso amministratore abilitato</i>"""
        else:
            help_msg = """📖 <b>COMANDI DISPONIBILI</b>

<b>📊 Informazioni:</b>
/stats - Statistiche generali
/performance - Performance storica
/positions - Posizioni aperte
/last_signals - Ultimi segnali AI
/status - Stato sistema

<b>ℹ️ Altro:</b>
/about - Info progetto
/help - Questa guida

<b>⚠️ Disclaimer:</b>
Questo bot fornisce solo informazioni generali sul sistema di trading.
Non costituisce consulenza finanziaria. DYOR.

<i>Usa /start per il disclaimer completo</i>"""

        await update.message.reply_text(help_msg, parse_mode="HTML")

    @admin_only
    async def cmd_tokens(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """🔢 Consumo token LLM e costi (ADMIN ONLY)"""
        await self._log_command(update, "tokens", True)

        try:
            tracker = get_token_tracker()

            # Get statistics
            today_stats = tracker.get_daily_stats()
            month_stats = tracker.get_monthly_stats()
            breakdown_today = tracker.get_cost_breakdown_by_model()

            # Calculate averages
            now = datetime.now(timezone.utc)
            days_in_month = now.day
            avg_daily_cost = month_stats.total_cost_usd / days_in_month if days_in_month > 0 else 0.0

            # Format breakdown (top 3 models)
            sorted_models = sorted(
                breakdown_today.items(),
                key=lambda x: x[1]['cost'],
                reverse=True
            )[:3]

            models_text = ""
            if sorted_models:
                for model, data in sorted_models:
                    percentage = (data['cost'] / today_stats.total_cost_usd * 100) if today_stats.total_cost_usd > 0 else 0
                    models_text += f"├ {model}: ${data['cost']:.4f} ({percentage:.0f}%)\n"
                models_text = models_text.rstrip('\n')
            else:
                models_text = "├ Nessun dato"

            msg = f"""📊 <b>Consumo Token LLM</b>

📅 <b>Oggi:</b>
├ Token: {today_stats.total_tokens:,}
├ Costo: ${today_stats.total_cost_usd:.4f}
└ Chiamate: {today_stats.api_calls_count}

📈 <b>Questo mese:</b>
├ Token: {month_stats.total_tokens:,}
├ Costo: ${month_stats.total_cost_usd:.2f}
└ Media/giorno: ${avg_daily_cost:.2f}

💰 <b>Per modello (oggi):</b>
{models_text}

⏱ <b>Tempo risposta medio:</b> {today_stats.avg_response_time_ms:.0f}ms

<i>Aggiornato: {now.strftime('%H:%M UTC')}</i>"""

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Errore nel comando /tokens: {e}")
            await update.message.reply_text(f"❌ Errore nel recupero statistiche token: {str(e)}")

    @admin_only
    async def cmd_admin_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """📋 Comandi amministratore"""
        await self._log_command(update, "admin_help", True)

        admin_help = """
🔧 **Comandi Admin**

<b>💰 Trading & Finanza:</b>
/balance - Saldo wallet dettagliato
/today - Riepilogo giornaliero completo
/tokens - Consumo token LLM e costi

<b>⚙️ Sistema & Config:</b>
/config - Configurazione completa
/logs - System logs in tempo reale
/status - Stato sistema dettagliato

<b>⏯️ Controllo Trading:</b>
/stop - Ferma trading automatico
/resume - Riprendi trading automatico

<b>ℹ️ Info:</b>
/admin_help - Questa guida
/help - Comandi pubblici + admin

<i>👑 Accesso amministratore richiesto per tutti questi comandi</i>
"""
        await update.message.reply_text(admin_help, parse_mode="HTML")

    # ==================== CALLBACK HANDLERS ====================

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler per callback da InlineKeyboard"""
        query = update.callback_query
        await query.answer()

        if not self._is_authorized(update):
            await query.edit_message_text("❌ Non sei autorizzato a usare questo bot.")
            return

        if query.data == "confirm_stop":
            if self.trading_agent:
                try:
                    # Stop trading
                    if hasattr(self.trading_agent, 'stop'):
                        self.trading_agent.stop()
                    else:
                        # Fallback: set is_running flag
                        self.trading_agent.is_running = False

                    await query.edit_message_text("🛑 <b>Trading fermato!</b>\n\nIl bot non aprirà nuove posizioni.", parse_mode="HTML")
                except Exception as e:
                    logger.error(f"❌ Errore nello stop trading: {e}")
                    await query.edit_message_text(f"❌ Errore: {str(e)}", parse_mode="HTML")
            else:
                await query.edit_message_text("⚪ Trading Agent non connesso.")

        elif query.data == "cancel_stop":
            await query.edit_message_text("✅ Operazione annullata. Il trading continua normalmente.")
        elif query.data == "refresh_logs":
            text = await self._get_recent_logs()
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔄 Aggiorna", callback_data="refresh_logs")]]
            )
            try:
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
                # Aggiorna l'id per questa chat
                if query.message and query.message.chat_id:
                    self.logs_message_ids[query.message.chat_id] = query.message.message_id
            except Exception as e:
                logger.error(f"❌ Errore aggiornamento log: {e}")

    # ==================== NOTIFICATION METHODS (Compatibility) ====================

    def notify_trade_opened(
        self,
        symbol: str,
        direction: str,
        size_usd: float,
        leverage: int,
        entry_price: float,
        stop_loss: float = None,
        take_profit: float = None
    ) -> None:
        """Notifica apertura trade (usa TelegramNotifier)"""
        self.notifier.notify_trade_opened(
            symbol=symbol,
            direction=direction,
            size_usd=size_usd,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss or 0.0,
            take_profit=take_profit or 0.0
        )

    def notify_trade_closed(
        self,
        symbol: str,
        direction: str,
        exit_price: float,
        pnl_usd: float,
        pnl_pct: float,
        reason: str = "Trade chiuso"
    ) -> None:
        """Notifica chiusura trade (usa TelegramNotifier)"""
        self.notifier.notify_trade_closed(
            symbol=symbol,
            direction=direction,
            pnl=pnl_usd,
            pnl_pct=pnl_pct,
            reason=reason
        )

    def notify_circuit_breaker(self, reason: str, current_drawdown: float) -> None:
        """Notifica circuit breaker attivato"""
        msg = f"""🚨 <b>CIRCUIT BREAKER ATTIVATO</b>

<b>Motivo:</b> {reason}
<b>Drawdown:</b> {current_drawdown:.2f}%

Trading fermato automaticamente per protezione del capitale."""
        self.notifier.send(msg)

    def notify_daily_summary(self, trades: int, pnl: float, win_rate: float) -> None:
        """Notifica riepilogo giornaliero"""
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        msg = f"""📊 <b>RIEPILOGO GIORNALIERO</b>

<b>Trades:</b> {trades}
<b>Win Rate:</b> {win_rate:.1f}%
<b>PnL:</b> {pnl_emoji} ${pnl:,.2f}

<i>{datetime.now(timezone.utc).strftime('%d/%m/%Y')}</i>"""
        self.notifier.send(msg)

    def notify_error(self, error_msg: str, context: str = None) -> None:
        """Notifica errore critico"""
        msg = f"""❌ <b>ERRORE</b>

<b>Messaggio:</b> {error_msg}"""
        if context:
            msg += f"\n<b>Contesto:</b> {context}"

        self.notifier.send(msg)

    # ==================== BOT LIFECYCLE ====================

    def start_polling(self) -> None:
        """Avvia il bot in background thread"""
        if not self.enabled:
            logger.warning("⚠️ Bot Telegram disabilitato, impossibile avviare polling")
            return

        if self.thread and self.thread.is_alive():
            logger.warning("⚠️ Bot Telegram già in esecuzione")
            return

        logger.info("🚀 Avvio bot Telegram in background...")

        # Create and start thread
        self.thread = Thread(target=self._run_bot, daemon=True)
        self.thread.start()

        logger.info("✅ Bot Telegram avviato in background thread")

    def _run_bot(self) -> None:
        """Esegue il bot in un thread separato (con proprio event loop)"""
        # Create new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            # Build application
            self.application = Application.builder().token(self.token).build()

            # Add command handlers
            # Public commands
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("about", self.cmd_about))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("performance", self.cmd_performance))
            self.application.add_handler(CommandHandler("positions", self.cmd_positions))
            self.application.add_handler(CommandHandler("last_signals", self.cmd_last_signals))
            self.application.add_handler(CommandHandler("status", self.cmd_status))

            # Admin commands
            self.application.add_handler(CommandHandler("balance", self.cmd_balance))
            self.application.add_handler(CommandHandler("today", self.cmd_today))
            self.application.add_handler(CommandHandler("config", self.cmd_config))
            self.application.add_handler(CommandHandler("tokens", self.cmd_tokens))
            self.application.add_handler(CommandHandler("logs", self.cmd_logs))
            self.application.add_handler(CommandHandler("stop", self.cmd_stop))
            self.application.add_handler(CommandHandler("resume", self.cmd_resume))
            self.application.add_handler(CommandHandler("admin_help", self.cmd_admin_help))

            # Add callback handler
            self.application.add_handler(CallbackQueryHandler(self.callback_handler))

            # Run polling
            # stop_signals=None per evitare errore "set_wakeup_fd only works in main thread"
            logger.info("🤖 Bot Telegram in ascolto...")
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                stop_signals=None
            )

        except Exception as e:
            logger.error(f"❌ Errore nel bot Telegram: {e}")
        finally:
            if self.loop:
                self.loop.close()

    def stop(self) -> None:
        """Ferma il bot in modo pulito"""
        if self.application:
            logger.info("🛑 Fermando bot Telegram...")

            # Stop application
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.application.stop(), self.loop)

            # Wait for thread
            if self.thread:
                self.thread.join(timeout=5)

            logger.info("✅ Bot Telegram fermato")


# ==================== STANDALONE TEST ====================

if __name__ == "__main__":
    # Test bot standalone
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    bot = TradingTelegramBot()

    if bot.enabled:
        print("✅ Bot configurato, avvio polling...")
        bot.start_polling()

        try:
            # Keep main thread alive
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Chiusura bot...")
            bot.stop()
    else:
        print("❌ Bot non configurato. Imposta TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID in .env")
