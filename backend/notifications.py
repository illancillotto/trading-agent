"""
Sistema di notifiche Telegram
"""
import os
import logging
import requests
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


class TelegramNotifier:
    """Gestisce le notifiche Telegram"""

    def __init__(self, token: str = None, chat_id: str = None, chat_ids: Optional[List[str]] = None):
        self.token = token or TELEGRAM_BOT_TOKEN

        # Supporta più chat ID (TELEGRAM_CHAT_IDS= id1,id2,...) con fallback singolo
        env_chat_ids = os.getenv("TELEGRAM_CHAT_IDS")
        parsed_env = []
        if env_chat_ids:
            parsed_env = [c.strip() for c in env_chat_ids.split(",") if c.strip()]

        if chat_ids:
            self.chat_ids = chat_ids
        elif parsed_env:
            self.chat_ids = parsed_env
        elif chat_id or TELEGRAM_CHAT_ID:
            self.chat_ids = [chat_id or TELEGRAM_CHAT_ID]
        else:
            self.chat_ids = []

        self.enabled = bool(self.token and self.chat_ids)

        if not self.enabled:
            logger.warning("⚠️ Telegram notifier non configurato (mancano TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID/TELEGRAM_CHAT_IDS)")

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Invia messaggio Telegram"""
        if not self.enabled:
            return False

        any_ok = False
        for cid in self.chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                response = requests.post(
                    url,
                    json={
                        "chat_id": cid,
                        "text": message,
                        "parse_mode": parse_mode
                    },
                    timeout=10
                )
                response.raise_for_status()
                any_ok = True
            except Exception as e:
                logger.error(f"❌ Errore invio Telegram a chat {cid}: {e}")
        return any_ok

    def notify_trade_opened(
        self,
        symbol: str,
        direction: str,
        size_usd: float,
        leverage: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        trade_id: int = None,
        details_url: str = None
    ) -> None:
        """Notifica apertura trade"""
        emoji = "🟢" if direction == "long" else "🔴"

        # Calculate potential P&L percentages
        if entry_price and entry_price > 0:
            sl_pct = abs((stop_loss - entry_price) / entry_price * 100) if stop_loss else 0
            tp_pct = abs((take_profit - entry_price) / entry_price * 100) if take_profit else 0
        else:
            sl_pct = 0
            tp_pct = 0

        msg = f"""{emoji} <b>TRADE APERTO</b>

<b>Asset:</b> {symbol}
<b>Direzione:</b> {direction.upper()}
<b>Size:</b> ${size_usd:.2f}
<b>Leva:</b> {leverage}x

<b>📊 Livelli:</b>
<b>   • Entry:</b> ${entry_price:.4f}
<b>   • Stop Loss:</b> ${stop_loss:.4f} (-{sl_pct:.1f}%)
<b>   • Take Profit:</b> ${take_profit:.4f} (+{tp_pct:.1f}%)

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        # Aggiungi link ai dettagli se disponibile
        if details_url:
            msg += f"""

📊 <a href="{details_url}">Visualizza Dettagli Completi</a>"""

        self.send(msg)

    def notify_trade_closed(
        self,
        symbol: str,
        direction: str,
        pnl: float,
        pnl_pct: float,
        reason: str,
        entry_price: float = None,
        exit_price: float = None,
        size_usd: float = None,
        duration_minutes: float = None,
        trade_id: int = None,
        details_url: str = None
    ) -> None:
        """Notifica chiusura trade con dettagli completi"""
        # Emoji e status basato su P&L
        if pnl > 0:
            emoji = "🟢"
            status = "PROFITTO"
        elif pnl < 0:
            emoji = "🔴"
            status = "PERDITA"
        else:
            emoji = "⚪"
            status = "BREAKEVEN"

        # Costruisci messaggio base
        msg = f"""{emoji} <b>TRADE CHIUSO - {status}</b>

<b>Asset:</b> {symbol}
<b>Direzione:</b> {direction.upper()}
<b>P&L:</b> ${pnl:+.2f} ({pnl_pct:+.2f}%)
<b>Motivo:</b> {reason}"""

        # Aggiungi dettagli prezzo se disponibili
        if entry_price and exit_price:
            price_change = ((exit_price - entry_price) / entry_price) * 100 if direction == "long" else ((entry_price - exit_price) / entry_price) * 100
            msg += f"""

<b>📊 Prezzi:</b>
<b>   • Entry:</b> ${entry_price:.4f}
<b>   • Exit:</b> ${exit_price:.4f}
<b>   • Variazione:</b> {price_change:+.2f}%"""

        # Aggiungi size se disponibile
        if size_usd:
            msg += f"""
<b>   • Size:</b> ${size_usd:.2f}"""

        # Aggiungi durata se disponibile
        if duration_minutes:
            hours = int(duration_minutes // 60)
            mins = int(duration_minutes % 60)
            duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            msg += f"""
<b>   • Durata:</b> {duration_str}"""

        msg += f"""

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        # Aggiungi link ai dettagli se disponibile
        if details_url:
            msg += f"""

📊 <a href="{details_url}">Visualizza Dettagli Completi</a>"""

        self.send(msg)

    def notify_circuit_breaker(self, daily_loss: float, reason: str) -> None:
        """Notifica attivazione circuit breaker"""
        msg = f"""🚨 <b>CIRCUIT BREAKER ATTIVATO</b>

<b>Perdita giornaliera:</b> ${abs(daily_loss):.2f}
<b>Motivo:</b> {reason}

Il bot non aprirà nuove posizioni fino a domani.

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        self.send(msg)

    def notify_daily_summary(
        self,
        balance: float,
        daily_pnl: float,
        trades_count: int,
        win_rate: float
    ) -> None:
        """Notifica riepilogo giornaliero"""
        emoji = "📈" if daily_pnl >= 0 else "📉"
        msg = f"""{emoji} <b>RIEPILOGO GIORNALIERO</b>

<b>Balance:</b> ${balance:.2f}
<b>P&L Oggi:</b> ${daily_pnl:+.2f}
<b>Trade:</b> {trades_count}
<b>Win Rate:</b> {win_rate:.1%}

⏰ {datetime.now().strftime('%Y-%m-%d')}"""
        self.send(msg)

    def notify_error(self, error_type: str, error_msg: str) -> None:
        """Notifica errore critico"""
        msg = f"""⚠️ <b>ERRORE</b>

<b>Tipo:</b> {error_type}
<b>Messaggio:</b> {error_msg[:200]}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        self.send(msg)

    def notify_startup(
        self,
        testnet: bool = True,
        tickers: list = None,
        cycle_interval_minutes: int = 60,
        wallet_address: str = None,
        screening_enabled: bool = False,
        top_n_coins: int = 5,
        rebalance_day: str = "sunday",
        sentiment_interval_minutes: int = 5,
        health_check_interval_minutes: int = 5,
        dashboard_url: str = None
    ) -> None:
        """Notifica avvio Trading Agent"""
        if not self.enabled:
            logger.warning("⚠️ Telegram notifier non abilitato, impossibile inviare notifica di avvio")
            return

        tickers_str = ", ".join(tickers) if tickers else "N/A"
        network = "🧪 TESTNET" if testnet else "🌐 MAINNET"
        wallet_display = wallet_address[:10] + "..." + wallet_address[-6:] if wallet_address and len(wallet_address) > 16 else (wallet_address or "N/A")

        # Informazioni Coin Screener
        screener_info = ""
        if screening_enabled:
            screener_info = f"""
<b>🔍 Coin Screener:</b> ✅ Abilitato
<b>   • Top N Coins:</b> {top_n_coins}
<b>   • Rebalance:</b> Ogni {rebalance_day.capitalize()} 00:00 UTC
<b>   • Update Scores:</b> Giornaliero"""
        else:
            screener_info = """
<b>🔍 Coin Screener:</b> ❌ Disabilitato"""

        # Dashboard link
        dashboard_link = ""
        if dashboard_url:
            dashboard_link = f'\n\n📊 <a href="{dashboard_url}">Apri Dashboard</a>'

        msg = f"""🚀 <b>TRADING AGENT AVVIATO</b>

{network}
<b>Wallet:</b> <code>{wallet_display}</code>
<b>Asset monitorati:</b> {tickers_str}

<b>⏱️ Cicli di Esecuzione:</b>
<b>   • Trading Cycle:</b> Ogni {cycle_interval_minutes} minuti
<b>   • Sentiment API:</b> Ogni {sentiment_interval_minutes} minuti
<b>   • Health Check:</b> Ogni {health_check_interval_minutes} minuti
{screener_info}

✅ Sistema operativo e pronto al trading{dashboard_link}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        result = self.send(msg)
        if result:
            logger.info("✅ Notifica di avvio inviata con successo")
        else:
            logger.error("❌ Fallito invio notifica di avvio")


def send_trade_notification(
    trade_id: int,
    symbol: str,
    direction: str,
    action: str,  # 'opened' o 'closed'
    entry_price: float,
    size: float,
    leverage: int,
    pnl_usd: Optional[float] = None,
    pnl_pct: Optional[float] = None,
    exit_reason: Optional[str] = None
):
    """
    Invia notifica Telegram con link a Instant View
    """
    try:
        # Base URL (da environment variable)
        base_url = os.getenv("PUBLIC_BASE_URL", "https://trading-dashboard.up.railway.app")

        # URL Instant View
        trade_url = f"{base_url}/trade-view/{trade_id}"

        # Costruisci messaggio
        if action == 'opened':
            emoji = "🟢" if direction == "long" else "🔴"
            message = f"""
{emoji} <b>{symbol} {direction.upper()} OPENED</b>

💰 Entry: ${entry_price:,.2f}
📊 Size: {size:.4f} {symbol}
⚡ Leverage: {leverage}x
💵 Notional: ${entry_price * size:,.2f}

<a href="{trade_url}">📊 View Full Details</a>
            """.strip()

        else:  # closed
            emoji = "✅" if (pnl_usd or 0) >= 0 else "❌"
            pnl_emoji = "📈" if (pnl_usd or 0) >= 0 else "📉"

            message = f"""
{emoji} <b>{symbol} {direction.upper()} CLOSED</b>

{pnl_emoji} P&L: ${pnl_usd:,.2f} ({pnl_pct:+.2f}%)
📊 Exit Reason: {exit_reason or 'Manual'}
💰 Entry: ${entry_price:,.2f}

<a href="{trade_url}">📊 View Full Analysis</a>
            """.strip()

        # Invia notifica (usa la tua funzione esistente)
        notifier.send(message, parse_mode='HTML')

        logger.info(f"Telegram notification sent for trade {trade_id} with IV link")

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


# Istanza globale
notifier = TelegramNotifier()
