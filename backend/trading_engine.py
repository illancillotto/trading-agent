"""
Trading Agent - Main Entry Point
Versione con Risk Management e Scheduler integrati
"""
import logging
import sys
import os
import json
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple

from dotenv import load_dotenv

# Setup logging PRIMA di tutto
# Log file path - works both locally and in Docker
# Use /app/logs only if writable (Docker), otherwise use current directory
log_dir = "."
if os.path.exists("/app/logs"):
    try:
        # Test if we can write to /app/logs
        test_file = "/app/logs/.write_test"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        log_dir = "/app/logs"
    except (PermissionError, OSError):
        log_dir = "."
log_filename = os.path.join(log_dir, "trading_agent.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Imports dei moduli
from indicators import analyze_multiple_tickers
from news_feed import fetch_latest_news
from trading_agent import previsione_trading_agent
from sentiment import get_sentiment
from forecaster import get_crypto_forecasts
from hyperliquid_trader import HyperLiquidTrader

# NOF1.ai Prompt Manager
from prompts.trading_system_prompt import TradingSystemPrompt

# NOF1.ai Configuration
try:
    from config import SCALPING_MODE_ENABLED, PRIMARY_TIMEFRAME, SECONDARY_TIMEFRAME
except ImportError:
    # Fallback if config.py not available
    SCALPING_MODE_ENABLED = False
    PRIMARY_TIMEFRAME = "15m"
    SECONDARY_TIMEFRAME = "4h"
from risk_manager import RiskManager, RiskConfig
from scheduler import TradingScheduler
from whalealert import fetch_whale_alerts_from_api
import db_utils

# Coin screener
from coin_screener import CoinScreener

# Trend confirmation (Phase 2)
from trend_confirmation import TrendConfirmationEngine

# Market Regime Detection
from market_regime import get_regime_detector, RegimeDetector, RegimeAnalysis, MarketRegime

# Confidence Calibrator
from confidence_calibrator import (
    get_confidence_calibrator,
    ConfidenceCalibrator,
    CalibrationDecision
)

# Notifiche Telegram
from notifications import notifier
from performance_metrics import get_performance_calculator

# ============================================================
#                      CONFIGURAZIONE
# ============================================================

# Leggi TESTNET da variabile d'ambiente (default: True)
TESTNET_ENV = os.getenv("TESTNET", "true").lower()
SCREENING_ENV = os.getenv("SCREENING_ENABLED", "false").lower()

# Load monitored tickers from top_coins.json
def load_tickers_from_config():
    """Load monitored assets from config/top_coins.json"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "top_coins.json")
        with open(config_path, 'r') as f:
            tickers = json.load(f)
            # The file contains a simple list of ticker symbols
            if isinstance(tickers, list) and tickers:
                logger.info(f"✅ Loaded {len(tickers)} monitored assets from top_coins.json")
                return tickers
            else:
                logger.warning(f"⚠️ Invalid format in top_coins.json, using defaults")
                return ["BTC", "ETH", "SOL"]
    except Exception as e:
        logger.warning(f"⚠️ Could not load tickers from top_coins.json: {e}, using defaults")
        return ["BTC", "ETH", "SOL"]

CONFIG = {
    # Trading
    "TESTNET": TESTNET_ENV in ("true", "1", "yes"),
    "TICKERS": load_tickers_from_config(),
    "CYCLE_INTERVAL_MINUTES": 5,

    # Coin Screening
    "SCREENING_ENABLED": SCREENING_ENV in ("true", "1", "yes"),
    "TOP_N_COINS": 20,          # Aumentato per avere più pool di scelta
    "ANALYSIS_BATCH_SIZE": 5,   # Quante coin analizzare per ciclo (rotazione)
    "REBALANCE_DAY": "sunday",
    "FALLBACK_TICKERS": ["BTC", "ETH", "SOL"],  # Used if screening fails or disabled

    # Trend Confirmation (Phase 2)
    "TREND_CONFIRMATION_ENABLED": True,  # Enable multi-timeframe trend confirmation
    "MIN_TREND_CONFIDENCE": 0.6,  # Minimum trend confidence to trade (0-1)
    "SKIP_POOR_ENTRY": True,  # Skip trades when entry_quality is "wait"
    "ADX_THRESHOLD": 25,  # ADX threshold for strong trends
    "RSI_OVERBOUGHT": 70,  # RSI overbought level
    "RSI_OVERSOLD": 30,  # RSI oversold level
    "ALLOW_SCALPING": SCALPING_MODE_ENABLED,  # NOF1.ai: Scalping mode (from config.py, default: False)
    "ALLOW_SHORTS": os.getenv("ALLOW_SHORTS", "true").lower() in ("true", "1", "yes"),  # Allow SHORT positions (for debugging)

    # Regime Detection settings
    "REGIME_DETECTION_ENABLED": True,
    "VOLATILITY_HIGH_PCT": 75,        # ATR > 75th percentile = high vol
    "VOLATILITY_LOW_PCT": 25,         # ATR < 25th percentile = low vol
    "REGIME_ADJUST_PARAMS": True,     # Auto-adjust leverage/SL/TP based on regime
    "REGIME_DIRECTION_PENALTY": 0.8,  # Confidence multiplier when direction mismatches

    # Confidence Calibration settings
    "CALIBRATION_ENABLED": True,
    "CALIBRATION_LOOKBACK_DAYS": 30,
    "CALIBRATION_MIN_WIN_RATE": 0.40,      # Block if historical WR < 40%
    "CALIBRATION_MIN_AVG_PNL": -1.0,       # Block if historical avg P&L < -1%
    "CALIBRATION_ADJUST_CONFIDENCE": True,  # Auto-adjust confidence based on history
    "CALIBRATION_BLOCK_ON_FAIL": True,     # Actually block trades that fail calibration

    # Risk Management
    "MAX_DAILY_LOSS_USD": 500.0,
    "MAX_DAILY_LOSS_PCT": 5.0,
    "MAX_POSITION_PCT": 30.0,
    "DEFAULT_STOP_LOSS_PCT": 2.0,
    "DEFAULT_TAKE_PROFIT_PCT": 5.0,
    "MAX_CONSECUTIVE_LOSSES": 3,

    # Execution
    "MIN_CONFIDENCE": 0.4,  # Non eseguire trade con confidence < 40%
}

# Credenziali - seleziona in base a TESTNET
IS_TESTNET = CONFIG["TESTNET"]

# Master Account Address (stesso per mainnet e testnet)
MASTER_ACCOUNT_ADDRESS = os.getenv("MASTER_ACCOUNT_ADDRESS")
if not MASTER_ACCOUNT_ADDRESS:
    logger.error("❌ MASTER_ACCOUNT_ADDRESS mancante nel .env")
    logger.error("   Questo è l'indirizzo del Master Account che contiene i fondi")
    logger.error("   Usato per le chiamate di lettura (Info API)")
    sys.exit(1)

if IS_TESTNET:
    PRIVATE_KEY = os.getenv("TESTNET_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
    WALLET_ADDRESS = os.getenv("TESTNET_WALLET_ADDRESS") or os.getenv("WALLET_ADDRESS")
    network_name = "TESTNET"
else:
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
    network_name = "MAINNET"

if not PRIVATE_KEY or not WALLET_ADDRESS:
    logger.error(f"❌ Credenziali mancanti per {network_name}")
    if IS_TESTNET:
        logger.error("   Richieste: TESTNET_PRIVATE_KEY e TESTNET_WALLET_ADDRESS")
        logger.error("   (o PRIVATE_KEY e WALLET_ADDRESS come fallback)")
        logger.error("   Testnet URL: https://app.hyperliquid-testnet.xyz/trade")
        logger.error("   Testnet Faucet: https://app.hyperliquid-testnet.xyz/drip")
    else:
        logger.error("   Richieste: PRIVATE_KEY e WALLET_ADDRESS")
    sys.exit(1)

logger.info(f"🌐 Modalità: {network_name}")
logger.info(f"   Master Account: {MASTER_ACCOUNT_ADDRESS}")
logger.info(f"   API Wallet: {WALLET_ADDRESS}")
if IS_TESTNET:
    logger.info(f"   Testnet URL: https://app.hyperliquid-testnet.xyz/trade")


# ============================================================
#                    STATO GLOBALE
# ============================================================

class BotState:
    """Stato globale del bot"""

    def __init__(self):
        self.trader: Optional[HyperLiquidTrader] = None
        self.risk_manager: Optional[RiskManager] = None
        self.screener: Optional[CoinScreener] = None
        self.trend_engine: Optional[TrendConfirmationEngine] = None
        self.regime_detector: Optional[RegimeDetector] = None
        self.confidence_calibrator: Optional[ConfidenceCalibrator] = None
        self.prompt_manager: Optional[TradingSystemPrompt] = None  # NOF1.ai Prompt Manager
        self.active_trades: dict[str, int] = {}  # symbol -> trade_id mapping
        self.rotation_index: int = 0             # Indice per rotazione coin
        self.initialized: bool = False
        self.last_error: Optional[str] = None

    def initialize(self) -> bool:
        """Inizializza tutti i componenti"""
        if self.initialized:
            return True

        try:
            logger.info("🔧 Inizializzazione componenti...")

            # Database
            db_utils.init_db()
            logger.info("✅ Database inizializzato")

            # Trader
            self.trader = HyperLiquidTrader(
                secret_key=PRIVATE_KEY,
                account_address=WALLET_ADDRESS,  # API wallet per Exchange (trading)
                master_account_address=MASTER_ACCOUNT_ADDRESS,  # Master Account per Info (lettura)
                testnet=CONFIG["TESTNET"]
            )
            logger.info(f"✅ HyperLiquid Trader inizializzato ({'testnet' if CONFIG['TESTNET'] else 'mainnet'})")
            logger.info(f"   Master Account: {MASTER_ACCOUNT_ADDRESS}")
            logger.info(f"   API Wallet: {WALLET_ADDRESS}")

            # Risk Manager
            risk_config = RiskConfig(
                max_daily_loss_pct=CONFIG["MAX_DAILY_LOSS_PCT"],
                max_daily_loss_usd=CONFIG["MAX_DAILY_LOSS_USD"],
                max_position_pct=CONFIG["MAX_POSITION_PCT"],
                default_stop_loss_pct=CONFIG["DEFAULT_STOP_LOSS_PCT"],
                default_take_profit_pct=CONFIG["DEFAULT_TAKE_PROFIT_PCT"],
                max_consecutive_losses=CONFIG["MAX_CONSECUTIVE_LOSSES"]
            )
            self.risk_manager = RiskManager(config=risk_config)
            logger.info("✅ Risk Manager inizializzato")

            # Coin Screener (se abilitato)
            if CONFIG["SCREENING_ENABLED"]:
                self.screener = CoinScreener(
                    testnet=CONFIG["TESTNET"],
                    coingecko_api_key=os.getenv("COINGECKO_API_KEY"),
                    top_n=CONFIG["TOP_N_COINS"]
                )
                logger.info("✅ Coin Screener inizializzato")

                # Run migration for screener tables
                from coin_screener.db_migration import run_migration
                with db_utils.get_connection() as conn:
                    run_migration(conn)

                # Log available coins
                try:
                    available_coins = self.screener.hl_provider.get_available_symbols()
                    logger.info(f"🎯 Trading coins for {'TESTNET' if CONFIG['TESTNET'] else 'MAINNET'}: {available_coins}")
                except Exception as e:
                    logger.warning(f"⚠️ Impossibile recuperare coin disponibili: {e}")
            else:
                logger.info(f"🎯 Trading coins (screening disabled): {CONFIG['TICKERS']}")

            # Trend Confirmation Engine (se abilitato - Phase 2)
            if CONFIG["TREND_CONFIRMATION_ENABLED"]:
                self.trend_engine = TrendConfirmationEngine(testnet=CONFIG["TESTNET"])
                # Configure thresholds from CONFIG
                self.trend_engine.config['adx_threshold'] = CONFIG["ADX_THRESHOLD"]
                self.trend_engine.config['rsi_overbought'] = CONFIG["RSI_OVERBOUGHT"]
                self.trend_engine.config['rsi_oversold'] = CONFIG["RSI_OVERSOLD"]
                self.trend_engine.config['min_confidence'] = CONFIG["MIN_TREND_CONFIDENCE"]
                self.trend_engine.config['allow_scalping'] = CONFIG["ALLOW_SCALPING"]
                logger.info("✅ Trend Confirmation Engine inizializzato")
                logger.info(f"   ADX threshold: {CONFIG['ADX_THRESHOLD']}")
                logger.info(f"   Min confidence: {CONFIG['MIN_TREND_CONFIDENCE']}")
                logger.info(f"   🎯 NOF1.ai Timeframe: {PRIMARY_TIMEFRAME}/{SECONDARY_TIMEFRAME} | Scalping: {'✅ ENABLED' if CONFIG['ALLOW_SCALPING'] else '❌ DISABLED'}")

            # Initialize Regime Detector (se abilitato)
            if CONFIG["REGIME_DETECTION_ENABLED"]:
                try:
                    regime_config = {
                        "adx_trending_threshold": CONFIG.get("ADX_THRESHOLD", 25),
                        "volatility_high_percentile": CONFIG.get("VOLATILITY_HIGH_PCT", 75),
                        "volatility_low_percentile": CONFIG.get("VOLATILITY_LOW_PCT", 25),
                    }
                    self.regime_detector = get_regime_detector(regime_config)
                    logger.info("✅ Regime Detector inizializzato")
                except Exception as e:
                    logger.warning(f"⚠️ Regime Detector init failed (non-critical): {e}")
                    self.regime_detector = None

            # Initialize Confidence Calibrator (se abilitato)
            if CONFIG.get("CALIBRATION_ENABLED", True):
                try:
                    calibrator_config = {
                        "lookback_days": CONFIG.get("CALIBRATION_LOOKBACK_DAYS", 30),
                        "min_win_rate_threshold": CONFIG.get("CALIBRATION_MIN_WIN_RATE", 0.40),
                        "min_avg_pnl_threshold": CONFIG.get("CALIBRATION_MIN_AVG_PNL", -1.0),
                        "enable_confidence_adjustment": CONFIG.get("CALIBRATION_ADJUST_CONFIDENCE", True),
                    }
                    self.confidence_calibrator = get_confidence_calibrator(calibrator_config)

                    # Generate initial report (async in background ideally)
                    report = self.confidence_calibrator.generate_calibration_report()
                    logger.info(
                        f"✅ Confidence Calibrator inizializzato | "
                        f"Optimal threshold: {report.optimal_threshold:.0%} | "
                        f"Trades analyzed: {report.total_trades_analyzed}"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Confidence Calibrator init failed (non-critical): {e}")
                    self.confidence_calibrator = None

            # Initialize NOF1.ai Prompt Manager
            try:
                self.prompt_manager = TradingSystemPrompt()
                logger.info("✅ NOF1.ai Prompt Manager inizializzato")
            except Exception as e:
                logger.warning(f"⚠️ Prompt Manager init failed (falling back to legacy prompt): {e}")
                self.prompt_manager = None

            self.initialized = True
            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"❌ Errore inizializzazione: {e}", exc_info=True)
            return False


# Istanza globale
bot_state = BotState()


# ============================================================
#                    PROMPT BUILDING FUNCTIONS
# ============================================================

def build_prompt_with_new_system(
    prompt_manager: 'TradingSystemPrompt',
    performance_metrics: Dict[str, float],
    account_status: Dict,
    indicators_map: Dict,
    tickers: List[str],
    news_txt: str,
    sentiment_txt: str,
    sentiment_json: Dict,
    forecasts_map: Dict,
    whale_alerts_txt: str,
    risk_manager: 'RiskManager',
    regime_analyses: Optional[Dict] = None,
    qualified_candidates: Optional[List[Dict]] = None,
    phase: str = "management"
) -> str:
    """
    Build prompt using the new NOF1.ai prompt system.

    Args:
        prompt_manager: TradingSystemPrompt instance
        performance_metrics: Dict with sharpe_ratio, win_rate, etc.
        account_status: Account status dict
        indicators_map: Map of ticker -> indicators
        tickers: List of tickers to analyze
        news_txt: News text
        sentiment_txt: Sentiment text
        sentiment_json: Sentiment JSON data
        forecasts_map: Map of ticker -> forecast
        whale_alerts_txt: Whale alerts text
        risk_manager: RiskManager instance
        regime_analyses: Optional regime analysis dict
        qualified_candidates: Optional pre-qualified candidates
        phase: "management" or "scouting"

    Returns:
        Complete prompt string
    """

    # Format portfolio data
    portfolio_data = f"""
**Account Balance**: ${account_status.get('balance_usd', 0):.2f}
**Available Cash**: ${account_status.get('available_cash', account_status.get('balance_usd', 0)):.2f}
**Total Positions Value**: ${account_status.get('positions_value', 0):.2f}

**Open Positions**:
"""

    open_positions = account_status.get('open_positions', [])
    if not open_positions:
        portfolio_data += "\nNo open positions.\n"
    else:
        for pos in open_positions:
            portfolio_data += f"""
- {pos['symbol']} {pos['side']}:
  Entry: ${pos.get('entry_price', 0):.2f}
  Current: ${pos.get('current_price', 0):.2f}
  Size: {pos.get('size', 0)} ({pos.get('size_usd', 0):.2f} USD)
  P&L: ${pos.get('unrealized_pnl', 0):.2f} ({pos.get('pnl_pct', 0):+.2f}%)
  Leverage: {pos.get('leverage', 1)}x
"""

    # Format market data for each ticker
    # TODO: In future, fetch real multi-timeframe data (15m, 4h, daily)
    # For now, we replicate the same data across timeframes for compatibility

    market_data_parts = []
    for ticker in tickers:
        if ticker not in indicators_map:
            continue

        ind = indicators_map[ticker]
        current = ind.get('current', {})

        ticker_data = f"""
**{ticker}**:
- Price: ${current.get('price', 0):.2f}
- EMA20: ${current.get('ema_20', 0):.2f}, EMA50: ${current.get('ema_50', 0):.2f}
- MACD: {current.get('MACD', 0):.4f}, Signal: {current.get('MACD_signal', 0):.4f}
- RSI(14): {current.get('RSI', 50):.2f}
- Volume: {current.get('volume', 0):,.0f}
- ATR: {current.get('ATR', 0):.2f}
"""
        market_data_parts.append(ticker_data)

    # Combine market data (same for all timeframes for now)
    market_data_combined = "\n".join(market_data_parts)

    # NOTE: For now, we use the same data for all timeframes
    # TODO: Implement real multi-timeframe data fetching
    market_data_15m = f"**Current Market State (15-minute perspective)**:\n{market_data_combined}"
    market_data_4h = f"**Current Market State (4-hour perspective)**:\n{market_data_combined}"
    market_data_daily = f"**Current Market State (daily perspective)**:\n{market_data_combined}"

    # Format regime analysis if available
    regime_context = None
    if regime_analyses:
        regime_lines = []
        for ticker, analysis in regime_analyses.items():
            params = analysis.recommended_params
            regime_lines.append(
                f"**{ticker}**: {analysis.regime.value} (confidence: {analysis.confidence:.0%})\n"
                f"  - ADX: {analysis.adx_value:.1f}, Volatility %: {analysis.volatility_percentile:.0f}\n"
                f"  - Strategy: {params.get('strategy', 'N/A')}\n"
                f"  - Preferred direction: {params.get('preferred_direction', 'any')}\n"
                f"  - Leverage multiplier: {params.get('leverage_multiplier', 1.0):.2f}x\n"
                f"  - {params.get('description', '')}"
            )
            if analysis.warnings:
                regime_lines.append(f"  ⚠️ **Warnings**: {', '.join(analysis.warnings)}")

        regime_context = "\n".join(regime_lines)

    # Format trend pre-analysis if available
    trend_context = None
    if qualified_candidates:
        trend_lines = []
        for qc in qualified_candidates:
            trend_lines.append(
                f"**{qc['symbol']}**: {qc['direction']} trend, "
                f"confidence {qc['confidence']:.0%}, "
                f"quality {qc['quality']}, "
                f"entry timing {qc['entry_quality']}"
            )
        trend_context = "\n".join(trend_lines)

    # Format sentiment
    sentiment_context = f"{sentiment_txt}\n\n**Sentiment Data**: {json.dumps(sentiment_json, indent=2)}"

    # Build system prompt
    system_prompt = prompt_manager.get_system_prompt()

    # Build user prompt
    user_prompt = prompt_manager.build_user_prompt(
        performance_metrics=performance_metrics,
        portfolio_data=portfolio_data,
        market_data_15m=market_data_15m,
        market_data_4h=market_data_4h,
        market_data_daily=market_data_daily,
        sentiment_data=sentiment_context,
        regime_analysis=regime_context,
        trend_preanalysis=trend_context
    )

    # Combine system + user prompt (legacy format expects them combined)
    # The trading_agent function will use this as the full prompt
    final_prompt = system_prompt + "\n\n" + user_prompt

    return final_prompt


# ============================================================
#                    PRE-FILTER FUNCTIONS
# ============================================================

def pre_filter_candidates(
    tickers: List[str],
    trend_engine: 'TrendConfirmationEngine',
    min_confidence: float = 0.6
) -> Tuple[List[dict], List[dict]]:
    """
    Pre-filtra i candidati PRIMA della chiamata LLM per risparmiare token.

    Args:
        tickers: Lista di ticker candidati
        trend_engine: Istanza del TrendConfirmationEngine
        min_confidence: Soglia minima di confidence (default 0.6)

    Returns:
        Tuple di (qualified_candidates, filtered_out)
        - qualified_candidates: Lista di dict con info trend per candidati qualificati
        - filtered_out: Lista di dict con motivo del filtro per candidati esclusi
    """
    qualified = []
    filtered_out = []

    logger.info(f"🔍 PRE-FILTER: Analisi trend per {len(tickers)} candidati...")

    for ticker in tickers:
        try:
            # Esegui trend confirmation
            confirmation = trend_engine.confirm_trend(ticker)

            # Prepara info per logging
            trend_info = {
                "symbol": ticker,
                "direction": confirmation.direction.value if confirmation.direction else "unknown",
                "confidence": confirmation.confidence,
                "quality": confirmation.quality.value if confirmation.quality else "unknown",
                "entry_quality": confirmation.entry_quality,
                "should_trade": confirmation.should_trade,
                "daily_trend": confirmation.daily_trend.value if confirmation.daily_trend else None,
                "hourly_trend": confirmation.hourly_trend.value if confirmation.hourly_trend else None,
                "m15_trend": confirmation.m15_trend.value if confirmation.m15_trend else None
            }

            # Criteri di qualificazione
            passes_confidence = confirmation.confidence >= min_confidence
            passes_should_trade = confirmation.should_trade
            passes_entry = confirmation.entry_quality != "wait" if CONFIG.get("SKIP_POOR_ENTRY", True) else True

            if passes_confidence and passes_should_trade and passes_entry:
                qualified.append(trend_info)
                logger.info(
                    f"  ✅ {ticker} QUALIFIED - "
                    f"Dir: {trend_info['direction']}, "
                    f"Conf: {confirmation.confidence:.0%}, "
                    f"Quality: {trend_info['quality']}"
                )
            else:
                # Determina motivo del filtro
                reasons = []
                if not passes_confidence:
                    reasons.append(f"low_confidence ({confirmation.confidence:.0%} < {min_confidence:.0%})")
                if not passes_should_trade:
                    reasons.append("should_trade=False")
                if not passes_entry:
                    reasons.append(f"entry_quality={confirmation.entry_quality}")

                trend_info["filter_reason"] = ", ".join(reasons)
                filtered_out.append(trend_info)
                logger.info(
                    f"  ❌ {ticker} FILTERED - {trend_info['filter_reason']}"
                )

        except Exception as e:
            logger.warning(f"  ⚠️ {ticker} ERROR in trend check: {e}")
            # In caso di errore, includiamo comunque il candidato (fail-safe)
            qualified.append({
                "symbol": ticker,
                "direction": "unknown",
                "confidence": 0.5,
                "quality": "unknown",
                "entry_quality": "unknown",
                "should_trade": True,
                "error": str(e)
            })

    logger.info(
        f"📊 PRE-FILTER RESULT: {len(qualified)}/{len(tickers)} qualified "
        f"({len(filtered_out)} filtered out)"
    )

    return qualified, filtered_out


def analyze_market_regime(symbol: str, indicators: Dict) -> Optional[RegimeAnalysis]:
    """
    Analizza il regime di mercato per un simbolo specifico.

    Args:
        symbol: Ticker del simbolo
        indicators: Dict con indicatori tecnici

    Returns:
        RegimeAnalysis o None se non disponibile
    """
    if not bot_state.regime_detector:
        return None

    try:
        # Estrai indicatori rilevanti
        regime_indicators = {
            'adx': indicators.get('adx', indicators.get('ADX', 0)),
            'atr': indicators.get('atr', indicators.get('ATR', 0)),
            'atr_pct': indicators.get('atr_pct', 0),
            'price': indicators.get('price', indicators.get('close', 0)),
            'ema20': indicators.get('ema_20', indicators.get('ema20', 0)),
            'ema50': indicators.get('ema_50', indicators.get('ema50', 0)),
            'ema200': indicators.get('ema_200', indicators.get('ema200', 0)),
            'rsi': indicators.get('rsi', indicators.get('RSI', 50)),
            'volume': indicators.get('volume', 0),
            'avg_volume': indicators.get('volume_sma', indicators.get('avg_volume', 0)),
            'macd': indicators.get('macd', indicators.get('MACD', 0)),
            'macd_signal': indicators.get('macd_signal', indicators.get('MACD_signal', 0)),
        }

        # Calcola ATR % se non presente
        if regime_indicators['atr_pct'] == 0 and regime_indicators['price'] > 0:
            regime_indicators['atr_pct'] = (regime_indicators['atr'] / regime_indicators['price']) * 100

        analysis = bot_state.regime_detector.detect_regime(regime_indicators)
        logger.info(f"🔬 {symbol} Regime: {analysis}")

        return analysis

    except Exception as e:
        logger.warning(f"⚠️ Regime analysis failed for {symbol}: {e}")
        return None


def calibrate_decision(
    decision: Dict,
    model: Optional[str] = None
) -> Tuple[Dict, Optional[CalibrationDecision]]:
    """
    Applica calibrazione storica a una decisione di trading.

    Args:
        decision: Dict con decisione LLM
        model: Nome del modello usato

    Returns:
        Tuple di (decision_calibrata, calibration_result)
    """
    if not bot_state.confidence_calibrator:
        # Nessuna calibrazione disponibile
        return decision, None

    try:
        calibration = bot_state.confidence_calibrator.evaluate_decision(decision, model)

        logger.info(f"📊 Calibration: {calibration}")

        # Aggiorna decision con confidence calibrata
        calibrated_decision = decision.copy()
        calibrated_decision['_original_confidence'] = decision.get('confidence', 0.5)
        calibrated_decision['confidence'] = calibration.calibrated_confidence
        calibrated_decision['_calibration'] = {
            'adjustment': calibration.confidence_adjustment,
            'historical_wr': calibration.historical_win_rate,
            'historical_pnl': calibration.historical_avg_pnl,
            'band_quality': calibration.band_quality.value,
            'should_execute': calibration.should_execute,
            'reason': calibration.reason
        }

        if calibration.warnings:
            calibrated_decision['_calibration_warnings'] = calibration.warnings

        return calibrated_decision, calibration

    except Exception as e:
        logger.warning(f"⚠️ Calibration failed: {e}")
        return decision, None


# ============================================================
#                    CICLO DI TRADING
# ============================================================

def trading_cycle() -> None:
    """
    Ciclo principale di trading:
    1. Fetch dati di mercato
    2. Costruisci prompt
    3. Ottieni decisione AI
    4. Verifica con risk manager
    5. Esegui trade
    6. Logga tutto
    """

    # Inizializza se necessario
    if not bot_state.initialized:
        if not bot_state.initialize():
            logger.error("❌ Impossibile inizializzare il bot")
            return

    trader = bot_state.trader
    risk_manager = bot_state.risk_manager
    screener = bot_state.screener

    # Variabili per error logging
    indicators_json = []
    news_txt = ""
    sentiment_json = {}
    forecasts_json = []
    whale_alerts_list = []
    account_status = {}
    system_prompt = ""

    try:
        # ========================================
        # 0. SELEZIONE COIN (se screening abilitato)
        # ========================================
        tickers_manage = []
        tickers_scout = []
        
        # Identifica coin in portafoglio (da analizzare SEMPRE per gestire chiusure)
        if bot_state.active_trades:
            tickers_manage = list(bot_state.active_trades.keys())

        if CONFIG["SCREENING_ENABLED"] and screener:
            try:
                # Check se serve rebalance completo
                if screener.should_rebalance():
                    logger.info("🔄 Rebalance settimanale: eseguo screening completo...")
                    try:
                        result = screener.run_full_screening()

                        # Log su database
                        from coin_screener.db_utils import log_screening_result
                        with db_utils.get_connection() as conn:
                            log_screening_result(conn, result)
                    except Exception as e:
                        # Se lo screening completo fallisce (es. rate limit), prova a usare dati cached
                        logger.warning(f"⚠️ Screening completo fallito: {e}")
                        logger.info("📋 Provo a usare dati cached o fallback...")
                        selected_coins = screener.get_selected_coins(top_n=CONFIG["TOP_N_COINS"])
                        if selected_coins:
                            tickers_scout_all = [coin.symbol for coin in selected_coins]
                            logger.info(f"🎯 Trading su coin cached: {', '.join(tickers_scout_all)}")
                        else:
                            raise  # Se non ci sono dati cached, usa fallback
                else:
                    # Update giornaliero
                    logger.info("📊 Update giornaliero scores...")
                    try:
                        result = screener.update_scores()
                    except Exception as e:
                        # Se l'update fallisce, usa dati cached
                        logger.warning(f"⚠️ Update scores fallito: {e}, uso dati cached")
                        pass  # Continua con get_selected_coins che userà cache

                # Ottieni top coins (da cache se disponibile)
                all_selected_coins = screener.get_selected_coins(top_n=CONFIG["TOP_N_COINS"])
                
                if all_selected_coins:
                    # LOGICA DI ROTAZIONE SCOUTING
                    # Identifica candidati disponibili (escludendo quelli già in portafoglio)
                    # NOTA: I tickers_manage sono già gestiti separatamente
                    held_symbols_set = set(tickers_manage)
                    candidates = [c.symbol for c in all_selected_coins if c.symbol not in held_symbols_set]
                    
                    # Seleziona batch corrente per scouting
                    batch_size = CONFIG.get("ANALYSIS_BATCH_SIZE", 5)
                    
                    if candidates:
                        start_idx = bot_state.rotation_index % len(candidates)
                        end_idx = start_idx + batch_size
                        
                        # Gestione overflow lista (wrap-around)
                        if end_idx <= len(candidates):
                            tickers_scout = candidates[start_idx:end_idx]
                        else:
                            # Prendi fino alla fine e ricomincia dall'inizio
                            tickers_scout = candidates[start_idx:] + candidates[:end_idx - len(candidates)]
                            
                        # Aggiorna indice per il prossimo ciclo
                        # Avanziamo solo se abbiamo effettivamente preso dei candidati
                        bot_state.rotation_index = (start_idx + batch_size) % len(candidates)
                    
                    logger.info(f"🎯 Target: {len(tickers_manage)} in gestione, {len(tickers_scout)} in scouting")
                    if tickers_manage:
                        logger.info(f"   Gestione: {', '.join(tickers_manage)}")
                    if tickers_scout:
                        logger.info(f"   Scouting: {', '.join(tickers_scout)}")
                else:
                    # Nessun dato disponibile, usa fallback
                    raise ValueError("Nessun dato disponibile dal screener")

            except Exception as e:
                logger.error(f"❌ Errore screening: {e}", exc_info=True)
                logger.info(f"📋 Uso fallback tickers: {CONFIG['FALLBACK_TICKERS']}")
                tickers_scout = CONFIG["FALLBACK_TICKERS"]
        else:
            # Screening disabilitato, usa CONFIG["TICKERS"]
            # Se screening disabilitato, mettiamo tutto in scouting per semplicità, 
            # ma rimuoviamo quelli già in gestione per evitare doppi
            fallback_tickers = CONFIG["TICKERS"]
            tickers_scout = [t for t in fallback_tickers if t not in tickers_manage]

        # Combine for efficient fetching
        all_tickers = list(set(tickers_manage + tickers_scout))
        if not all_tickers:
            logger.warning("⚠️ Nessun ticker da analizzare")
            return

        # ========================================
        # 1. FETCH DATI DI MERCATO (UNICA CHIAMATA)
        # ========================================
        logger.info(f"📡 Recupero dati di mercato per {len(all_tickers)} ticker...")

        # Initialize data containers
        market_data_map = {} # ticker -> {indicators, news, sentiment, forecast, whale}
        
        # Indicatori tecnici
        try:
            # analyze_multiple_tickers returns (full_text, json_list)
            # We need to parse json_list to map by ticker
            _, indicators_list = analyze_multiple_tickers(
                all_tickers, 
                testnet=CONFIG["TESTNET"]
            )
            # Map indicators by ticker
            indicators_map = {item['ticker']: item for item in indicators_list if 'ticker' in item}
            logger.info(f"✅ Indicatori tecnici recuperati")
        except Exception as e:
            logger.warning(f"⚠️ Errore indicatori: {e}")
            indicators_map = {}

        # News
        try:
            # fetch_latest_news returns text. We might need structured news or just pass active text.
            # For now, news is global or per ticker? The function takes symbols list.
            # Assuming global news context for now, or we optimize later.
            news_txt = fetch_latest_news(symbols=all_tickers)
            logger.info(f"✅ News ({len(news_txt)} caratteri)")
        except Exception as e:
            logger.warning(f"⚠️ Errore news: {e}")
            news_txt = "News non disponibili"

        # Sentiment (Global)
        try:
            sentiment_txt, sentiment_json = get_sentiment()
            logger.info(f"✅ Sentiment: {sentiment_json.get('classificazione', 'N/A')}")
        except Exception as e:
            logger.warning(f"⚠️ Errore sentiment: {e}")
            sentiment_txt = "Sentiment non disponibile"
            sentiment_json = {}

        # Forecast
        try:
            forecasts_txt, forecasts_json = get_crypto_forecasts(
                tickers=all_tickers,
                testnet=CONFIG["TESTNET"]
            )
            # Map forecasts by ticker if possible, or just use the list
            forecasts_map = {f.get('Ticker'): f for f in forecasts_json if f.get('Ticker')}
            logger.info("✅ Forecast recuperati")
        except Exception as e:
            logger.warning(f"⚠️ Errore forecast: {e}")
            forecasts_txt = "Forecast non disponibili"
            forecasts_json = []
            forecasts_map = {}

        # Whale Alerts (Global)
        try:
            whale_alerts_txt, whale_alerts_list = fetch_whale_alerts_from_api(max_alerts=10)
            logger.info(f"✅ Whale alerts recuperati: {len(whale_alerts_list)} alert")
        except Exception as e:
            logger.warning(f"⚠️ Errore whale alerts: {e}")
            whale_alerts_txt = "Whale alert non disponibili"
            whale_alerts_list = []

        # ========================================
        # 2. STATO ACCOUNT
        # ========================================
        account_status = trader.get_account_status()
        balance_usd = account_status.get("balance_usd", 0)
        open_positions = account_status.get("open_positions", [])

        logger.info(f"💰 Balance: ${balance_usd:.2f}, Posizioni aperte: {len(open_positions)}")

        # ========================================
        # CALCOLO PERFORMANCE METRICS (SHARED)
        # ========================================
        # Calculate ONCE and reuse in both MANAGE and SCOUT phases
        try:
            perf_calculator = get_performance_calculator(db_utils)
            perf_metrics = perf_calculator.get_metrics_from_db(lookback_days=30)
            performance_section = perf_metrics.to_prompt_string() if perf_metrics.total_trades > 0 else """**Your Performance Metrics:**
- No completed trades yet. Focus on quality over quantity.
- Start with conservative position sizes until you build a track record."""
            logger.info(f"✅ Performance metrics calculated (trades: {perf_metrics.total_trades if perf_metrics else 0})")
        except Exception as e:
            logger.warning(f"⚠️ Error calculating performance metrics: {e}")
            performance_section = "**Your Performance Metrics:** (unavailable - system starting)"

        # --- FIX: SYNC STATO REALE ---
        # Filtra tickers_manage per includere SOLO le posizioni realmente aperte.
        # Questo evita chiamate inutili all'AI se il trade è stato chiuso altrove o per stop-loss.
        real_open_symbols = [p['symbol'] for p in open_positions]
        
        # Identifica e rimuovi i "trade fantasma" (presenti in memoria ma non sull'exchange)
        ghost_trades = [t for t in tickers_manage if t not in real_open_symbols]
        for ghost in ghost_trades:
            logger.info(f"👻 Rilevato trade fantasma su {ghost}: rimuovo da gestione interna")
            if ghost in bot_state.active_trades:
                del bot_state.active_trades[ghost]
            tickers_manage.remove(ghost)
            
        if not tickers_manage and ghost_trades:
             logger.info("⏩ Nessuna posizione reale da gestire dopo il sync. Salto Fase Gestione.")
        # -----------------------------

        # Log snapshot
        try:
            snapshot_id = db_utils.log_account_status(account_status)
            logger.debug(f"📝 Account snapshot salvato (ID: {snapshot_id})")
        except Exception as e:
            logger.warning(f"⚠️ Errore salvataggio snapshot: {e}")

        # ========================================
        # 3. CHECK SL/TP LOCALE (Risk Manager)
        # ========================================
        if open_positions:
            # Need prices for risk manager check
            current_prices = {}
            # Extract prices from indicators if available, else fetch
            for t in all_tickers:
                if t in indicators_map and 'current' in indicators_map[t]:
                     current_prices[t] = indicators_map[t]['current'].get('price')
            
            # Fallback fetch if missing
            missing_prices = [t for t in tickers_manage if t not in current_prices or not current_prices[t]]
            if missing_prices:
                fetched = trader.get_current_prices(missing_prices)
                current_prices.update(fetched)

            positions_to_close = risk_manager.check_positions(current_prices)

            for close_info in positions_to_close:
                # ... (Logic for SL/TP closing remains same, abbreviated for brevity) ...
                symbol = close_info["symbol"]
                reason = close_info["reason"]
                pnl = close_info["pnl"]
                logger.warning(f"⚠️ {reason.upper()} trigger per {symbol}, PnL: ${pnl:.2f}")
                
                try:
                    close_order = {
                        "operation": "close",
                        "symbol": symbol,
                        "direction": "long"
                    }
                    close_result = trader.execute_signal_with_risk(
                        close_order,
                        risk_manager,
                        balance_usd
                    )
                    # Log logic identical to previous...
                    if close_result and close_result.get("status") == "ok":
                         # Remove from active trades so we don't analyze it in management phase
                         if symbol in tickers_manage:
                             tickers_manage.remove(symbol)
                except Exception as e:
                    logger.error(f"❌ Eccezione chiusura SL/TP {symbol}: {e}")

        # Helper to build prompt
        def build_prompt_data(target_tickers):
            # Filter indicators text specifically for these tickers would be complex with just text
            # So we regenerate the text for the specific subset
            subset_indicators_txt = ""
            for t in target_tickers:
                if t in indicators_map:
                    # Reconstruct string representation (simplified) or use raw JSON in prompt
                    # Using JSON in prompt might be better for structure
                    pass
            
            # For simplicity, we pass the JSON list of indicators for the target tickers
            subset_indicators = [indicators_map[t] for t in target_tickers if t in indicators_map]
            subset_forecasts = [forecasts_map[t] for t in target_tickers if t in forecasts_map]
            
            return json.dumps(subset_indicators, indent=2), json.dumps(subset_forecasts, indent=2)

        # ========================================
        # 4. FASE GESTIONE (Attiva se ci sono posizioni)
        # ========================================
        if tickers_manage:
            logger.info(f"🤖 FASE GESTIONE: Analisi {len(tickers_manage)} posizioni aperte...")
            
            # Genera cycle_id univoco per gestione
            cycle_id_manage = f"manage_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            # Build specific prompt
            # Filter indicators
            subset_ind, subset_forc = build_prompt_data(tickers_manage)
            
            # Costruisci prompt specifico
            # Nota: System prompt template viene caricato e formattato
            # Usiamo un msg_info custom che focalizza l'attenzione
            
            msg_info_manage = f"""<context>
ANALYSIS TYPE: OPEN POSITIONS MANAGEMENT
FOCUS: Decide whether to CLOSE or HOLD existing positions.
DO NOT OPEN NEW POSITIONS IN THIS PHASE.
</context>

<active_positions>
{json.dumps(open_positions, indent=2)}
</active_positions>

<indicators>
{subset_ind}
</indicators>

<news>
{news_txt}
</news>

<sentiment>
{sentiment_txt}
</sentiment>

<forecast>
{subset_forc}
</forecast>

<whale_alerts>
{whale_alerts_txt}
</whale_alerts>

<risk_status>
Daily P&L: ${risk_manager.daily_pnl:.2f}
Consecutive Losses: {risk_manager.consecutive_losses}
</risk_status>
"""
            # Build prompt using new NOF1.ai system or fallback to legacy
            if bot_state.prompt_manager:
                # Use new NOF1.ai prompt system
                try:
                    final_prompt_manage = build_prompt_with_new_system(
                        prompt_manager=bot_state.prompt_manager,
                        performance_metrics={
                            'sharpe_ratio': perf_metrics.sharpe_ratio if perf_metrics else 0.0,
                            'win_rate': perf_metrics.win_rate if perf_metrics else 0.0,
                            'avg_rr': perf_metrics.avg_rr if perf_metrics else 0.0,
                            'consecutive_losses': risk_manager.consecutive_losses,
                            'total_return_pct': perf_metrics.total_return_pct if perf_metrics else 0.0
                        },
                        account_status=account_status,
                        indicators_map=indicators_map,
                        tickers=tickers_manage,
                        news_txt=news_txt,
                        sentiment_txt=sentiment_txt,
                        sentiment_json=sentiment_json,
                        forecasts_map=forecasts_map,
                        whale_alerts_txt=whale_alerts_txt,
                        risk_manager=risk_manager,
                        phase="management"
                    )
                    logger.info("✅ Using new NOF1.ai prompt system (GESTIONE)")
                except Exception as e:
                    logger.warning(f"⚠️ Error with new prompt system, falling back to legacy: {e}")
                    # Fallback to legacy prompt
                    with open('system_prompt.txt', 'r') as f:
                        system_prompt_template = f.read()
                    system_prompt_with_perf = system_prompt_template.replace(
                        "{performance_metrics}",
                        performance_section
                    )
                    final_prompt_manage = system_prompt_with_perf.format(
                        json.dumps(account_status, indent=2),
                        msg_info_manage
                    )
            else:
                # Fallback to legacy prompt system
                logger.info("📜 Using legacy prompt system (prompt_manager not available)")
                with open('system_prompt.txt', 'r') as f:
                    system_prompt_template = f.read()
                system_prompt_with_perf = system_prompt_template.replace(
                    "{performance_metrics}",
                    performance_section
                )
                final_prompt_manage = system_prompt_with_perf.format(
                    json.dumps(account_status, indent=2),
                    msg_info_manage
                )
            
            # Call AI
            try:
                decision_manage = previsione_trading_agent(
                    final_prompt_manage, 
                    cycle_id=cycle_id_manage
                )
                
                # Process Decision
                op_manage = decision_manage.get("operation", "hold")
                sym_manage = decision_manage.get("symbol")
                
                if op_manage == "close" and sym_manage in tickers_manage:
                    logger.info(f"📉 DECISIONE GESTIONE: CLOSE {sym_manage}")
                    # Execute Close
                    res = trader.execute_signal_with_risk(decision_manage, risk_manager, balance_usd)
                    # Log ... (reuse existing logic structure or function)
                    # For brevity, assume logging handles it via DB utils inside execute or after
                    # Log to DB
                    if 'execution_result' not in decision_manage:
                        decision_manage['execution_result'] = res
                    decision_manage['cycle_id'] = cycle_id_manage
                    
                    db_utils.log_bot_operation(
                        operation_payload=decision_manage,
                        system_prompt=final_prompt_manage,
                        indicators=json.loads(subset_ind),
                        news_text=news_txt,
                        sentiment=sentiment_json,
                        forecasts=json.loads(subset_forc)
                    )
                    
                    # If closed successfully, remove from active trades map locally if needed
                    if res.get("status") == "ok":
                        # Remove active trade ID
                        if sym_manage in bot_state.active_trades:
                            try:
                                # Get position info for P&L calculation
                                position = next((p for p in open_positions if p["symbol"] == sym_manage), None)
                                entry_price = position.get("entry_price", 0) if position else 0
                                # Use fill price or fallback to current market price
                                exit_price = res.get("fill_price")
                                if not exit_price and sym_manage in current_prices:
                                    exit_price = current_prices[sym_manage]
                                
                                pnl_usd = res.get("pnl_usd")
                                
                                # Calculate Pnl if missing
                                if pnl_usd is None and position:
                                    size = position.get("size", 0)
                                    if exit_price and exit_price > 0:
                                        side = position.get("side", "long")
                                        if side.lower() == "long":
                                            pnl_usd = (exit_price - entry_price) * size
                                        else:
                                            pnl_usd = (entry_price - exit_price) * size
                                    else:
                                        pnl_usd = 0

                                pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price and entry_price > 0 else 0

                                db_utils.close_trade(
                                    trade_id=bot_state.active_trades[sym_manage],
                                    exit_price=exit_price or 0,
                                    exit_reason="signal",
                                    pnl_usd=pnl_usd,
                                    pnl_pct=pnl_pct,
                                    fees_usd=res.get("fees", 0)
                                )
                                trade_id = bot_state.active_trades[sym_manage]
                                del bot_state.active_trades[sym_manage]
                                logger.info(f"✅ Trade {sym_manage} chiuso e loggato")

                                # Notify with full details
                                try:
                                    # Get public URL for details
                                    import os
                                    api_url = os.getenv("PUBLIC_API_URL", "https://static.9.126.98.91.clients.your-server.de")
                                    details_url = f"{api_url}/api/trades/{trade_id}/details"

                                    # Calculate duration if available
                                    duration_minutes = None
                                    if position and 'entry_time' in position:
                                        entry_time = position['entry_time']
                                        if isinstance(entry_time, str):
                                            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                                        duration = datetime.now(timezone.utc) - entry_time
                                        duration_minutes = duration.total_seconds() / 60

                                    # Send Instant View notification
                                    from notifications import send_trade_notification
                                    # Get trade data for size and leverage
                                    try:
                                        with db_utils.get_connection() as conn:
                                            with conn.cursor() as cur:
                                                cur.execute("""
                                                    SELECT size, leverage FROM executed_trades WHERE id = %s
                                                """, (trade_id,))
                                                trade_row = cur.fetchone()
                                                size = float(trade_row[0]) if trade_row and trade_row[0] else 0
                                                leverage = int(trade_row[1]) if trade_row and trade_row[1] else 1
                                    except Exception:
                                        size = 0
                                        leverage = 1

                                    send_trade_notification(
                                        trade_id=trade_id,
                                        symbol=sym_manage,
                                        direction=position.get("side", "unknown") if position else "unknown",
                                        action='closed',
                                        entry_price=entry_price,
                                        size=size,
                                        leverage=leverage,
                                        pnl_usd=pnl_usd,
                                        pnl_pct=pnl_pct,
                                        exit_reason="Signal AI"
                                    )
                                except Exception as e:
                                    logger.warning(f"⚠️ Notify error: {e}")
                                    
                            except Exception as log_err:
                                logger.error(f"❌ Errore logging chiusura: {log_err}")
                            
                elif op_manage == "open":
                    logger.warning(f"⚠️ AI ha suggerito OPEN in fase GESTIONE. Ignorato.")
                else:
                    logger.info(f"⏸️ GESTIONE: {op_manage} su {sym_manage}")
                    # Log HOLD decision for tracking
                    decision_manage['cycle_id'] = cycle_id_manage
                    db_utils.log_bot_operation(
                        operation_payload=decision_manage,
                        system_prompt=final_prompt_manage,
                        indicators=json.loads(subset_ind)
                    )

            except Exception as e:
                logger.error(f"❌ Errore fase gestione: {e}")

        # ========================================
        # 5. FASE SCOUTING (Attiva se ci sono candidati)
        # ========================================
        if tickers_scout:
            try:
                logger.info(f"🔭 FASE SCOUTING: Analisi {len(tickers_scout)} opportunità...")

                cycle_id_scout = f"scout_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

                # ========== PRE-FILTER: Trend Check PRIMA dell'LLM ==========
                qualified_candidates = []
                filtered_candidates = []

                if CONFIG["TREND_CONFIRMATION_ENABLED"] and bot_state.trend_engine:
                    min_conf = CONFIG.get("MIN_TREND_CONFIDENCE", 0.6)
                    qualified_candidates, filtered_candidates = pre_filter_candidates(
                        tickers_scout,
                        bot_state.trend_engine,
                        min_confidence=min_conf
                    )

                    # Log candidati filtrati nel DB (opzionale ma utile per analytics)
                    for filtered in filtered_candidates:
                        try:
                            db_utils.log_bot_operation(
                                operation="skip",
                                symbol=filtered["symbol"],
                                direction=filtered.get("direction", "unknown"),
                                confidence=filtered.get("confidence", 0),
                                raw_payload={
                                    "reason": f"Pre-filter: {filtered.get('filter_reason', 'unknown')}",
                                    "trend_info": filtered,
                                    "phase": "scouting_prefilter"
                                },
                                cycle_id=cycle_id_scout
                            )
                        except Exception as log_err:
                            logger.debug(f"Could not log filtered candidate: {log_err}")

                    # Aggiorna lista candidati
                    if not qualified_candidates:
                        logger.info("🚫 Nessun candidato qualificato dopo pre-filter - Skip LLM call")
                        # Log skip totale
                        try:
                            db_utils.log_bot_operation(
                                operation="hold",
                                symbol="NONE",
                                direction="long",
                                confidence=0.0,
                                raw_payload={
                                    "reason": "All candidates filtered by trend pre-check",
                                    "filtered_count": len(filtered_candidates),
                                    "phase": "scouting_prefilter_complete"
                                },
                                cycle_id=cycle_id_scout
                            )
                        except:
                            pass
                        # Skip alla prossima iterazione - NON chiamare LLM
                        tickers_scout = []  # Svuota per saltare il blocco LLM sotto
                    else:
                        # Usa solo i ticker qualificati
                        tickers_scout = [c["symbol"] for c in qualified_candidates]
                        logger.info(f"✅ Procedendo con {len(tickers_scout)} candidati qualificati: {tickers_scout}")

                # ========== REGIME ANALYSIS ==========
                regime_context = ""
                regime_analyses = {}

                if bot_state.regime_detector and indicators_json and tickers_scout:
                    logger.info("🔬 Analyzing market regime for candidates...")

                    for ticker in tickers_scout:
                        ticker_indicators = indicators_json.get(ticker, {})
                        if ticker_indicators:
                            regime_analysis = analyze_market_regime(ticker, ticker_indicators)
                            if regime_analysis:
                                regime_analyses[ticker] = regime_analysis

                    # Costruisci contesto regime per il prompt
                    if regime_analyses:
                        regime_lines = []
                        for ticker, analysis in regime_analyses.items():
                            params = analysis.recommended_params
                            regime_lines.append(
                                f"- {ticker}: {analysis.regime.value} (conf: {analysis.confidence:.0%})\n"
                                f"  ADX: {analysis.adx_value:.1f}, Vol%: {analysis.volatility_percentile:.0f}, "
                                f"Trend: {analysis.trend_strength:+.2f}\n"
                                f"  Strategy: {params.get('strategy', 'N/A')} | "
                                f"Preferred: {params.get('preferred_direction', 'any')} | "
                                f"Lev mult: {params.get('leverage_multiplier', 1.0):.1f}x\n"
                                f"  {params.get('description', '')}"
                            )
                            if analysis.warnings:
                                regime_lines.append(f"  ⚠️ Warnings: {', '.join(analysis.warnings)}")

                        regime_context = "\n<market_regime_analysis>\n" + "\n".join(regime_lines) + "\n</market_regime_analysis>\n"
                        logger.info(f"📊 Regime analysis added to prompt for {len(regime_analyses)} tickers")

                # ========== CHIAMATA LLM (solo se ci sono candidati) ==========
                if tickers_scout:
                    subset_ind, subset_forc = build_prompt_data(tickers_scout)
    
                    # Aggiungi trend info al contesto per l'LLM
                    trend_context = ""
                    if qualified_candidates:
                        trend_lines = []
                        for qc in qualified_candidates:
                            trend_lines.append(
                                f"- {qc['symbol']}: {qc['direction']} trend, "
                                f"confidence {qc['confidence']:.0%}, "
                                f"quality {qc['quality']}, "
                                f"entry {qc['entry_quality']}"
                            )
                        trend_context = "\n<trend_preanalysis>\n" + "\n".join(trend_lines) + "\n</trend_preanalysis>\n"
    
                    msg_info_scout = f"""<context>
    ANALYSIS TYPE: MARKET SCOUTING
    FOCUS: Look for new OPEN opportunities among the PRE-QUALIFIED candidates.
    These candidates have already passed trend confirmation checks.
    IGNORE existing positions (handled separately).
    </context>
    
    <candidates>
    {', '.join(tickers_scout)}
    </candidates>
    {trend_context}{regime_context}
    <indicators>
    {subset_ind}
    </indicators>
    
    <news>
    {news_txt}
    </news>
    
    <sentiment>
    {sentiment_txt}
    </sentiment>
    
    <forecast>
    {subset_forc}
    </forecast>
    
    <whale_alerts>
    {whale_alerts_txt}
    </whale_alerts>
    
    <risk_status>
    Daily P&L: ${risk_manager.daily_pnl:.2f}
    </risk_status>
    """
                    # Calculate performance metrics (NOF1.ai) - reuse from earlier
                    # (performance_section already calculated above)

                    # Build prompt using new NOF1.ai system or fallback to legacy
                    if bot_state.prompt_manager:
                        # Use new NOF1.ai prompt system
                        try:
                            final_prompt_scout = build_prompt_with_new_system(
                                prompt_manager=bot_state.prompt_manager,
                                performance_metrics={
                                    'sharpe_ratio': perf_metrics.sharpe_ratio if perf_metrics else 0.0,
                                    'win_rate': perf_metrics.win_rate if perf_metrics else 0.0,
                                    'avg_rr': perf_metrics.avg_rr if perf_metrics else 0.0,
                                    'consecutive_losses': risk_manager.consecutive_losses,
                                    'total_return_pct': perf_metrics.total_return_pct if perf_metrics else 0.0
                                },
                                account_status=account_status,
                                indicators_map=indicators_map,
                                tickers=tickers_scout,
                                news_txt=news_txt,
                                sentiment_txt=sentiment_txt,
                                sentiment_json=sentiment_json,
                                forecasts_map=forecasts_map,
                                whale_alerts_txt=whale_alerts_txt,
                                risk_manager=risk_manager,
                                regime_analyses=regime_analyses if 'regime_analyses' in locals() else None,
                                qualified_candidates=qualified_candidates if 'qualified_candidates' in locals() else None,
                                phase="scouting"
                            )
                            logger.info("✅ Using new NOF1.ai prompt system (SCOUTING)")
                        except Exception as e:
                            logger.warning(f"⚠️ Error with new prompt system, falling back to legacy: {e}")
                            # Fallback to legacy prompt
                            with open('system_prompt.txt', 'r') as f:
                                system_prompt_template = f.read()
                            system_prompt_with_perf_scout = system_prompt_template.replace(
                                "{performance_metrics}",
                                performance_section
                            )
                            final_prompt_scout = system_prompt_with_perf_scout.format(
                                json.dumps(account_status, indent=2),
                                msg_info_scout
                            )
                    else:
                        # Fallback to legacy prompt system
                        logger.info("📜 Using legacy prompt system (prompt_manager not available)")
                        with open('system_prompt.txt', 'r') as f:
                            system_prompt_template = f.read()
                        system_prompt_with_perf_scout = system_prompt_template.replace(
                            "{performance_metrics}",
                            performance_section
                        )
                        final_prompt_scout = system_prompt_with_perf_scout.format(
                            json.dumps(account_status, indent=2),
                            msg_info_scout
                        )
    
                    # Call AI
                    try:
                        decision_scout = previsione_trading_agent(
                            final_prompt_scout,
                            cycle_id=cycle_id_scout
                        )
                    except Exception as e:
                        logger.error(f"❌ Errore chiamata AI scouting: {e}")
                        decision_scout = {"operation": "hold", "symbol": None, "confidence": 0}

                    op_scout = decision_scout.get("operation", "hold")
                    sym_scout = decision_scout.get("symbol")
                    conf_scout = decision_scout.get("confidence", 0)
                    direction_scout = decision_scout.get("direction", "long")
    
                    trend_info = ""  # Initialize default
    
                    if op_scout == "open":
                        if sym_scout not in tickers_scout:
                            logger.warning(f"⚠️ AI ha suggerito {sym_scout} che non è nei candidati ({tickers_scout})")
                        else:
                            # Trend check già effettuato in pre-filter
                            # Recupera le info pre-calcolate
                            trend_check_passed = True
                            trend_info = ""
                            if qualified_candidates:
                                qc = next((c for c in qualified_candidates if c["symbol"] == sym_scout), None)
                                if qc:
                                    trend_info = f"Pre-qualified: {qc['direction']} trend, conf {qc['confidence']:.0%}, quality {qc['quality']}, entry {qc['entry_quality']}"
                                    logger.info(f"✅ Using pre-filter result for {sym_scout}: {trend_info}")
                                else:
                                    logger.warning(f"⚠️ {sym_scout} not in pre-qualified list but passed to LLM - allowing trade")

                            # ========== REGIME-BASED PARAMETER ADJUSTMENT ==========
                            if sym_scout in regime_analyses and CONFIG.get("REGIME_ADJUST_PARAMS", True):
                                regime = regime_analyses[sym_scout]
                                logger.info(f"🔧 Applying regime adjustments for {sym_scout} ({regime.regime.value})")

                                # Adjust parameters based on regime
                                adjusted = bot_state.regime_detector.adjust_trade_params(
                                    decision_scout,
                                    regime
                                )

                                # Log adjustments
                                if adjusted != decision_scout:
                                    logger.info(f"📊 Regime adjustments applied:")
                                    logger.info(f"  Leverage: {decision_scout.get('leverage', 'N/A')} → {adjusted.get('leverage', 'N/A')}")
                                    logger.info(f"  SL: {decision_scout.get('stop_loss_pct', 'N/A')} → {adjusted.get('stop_loss_pct', 'N/A')}")
                                    logger.info(f"  TP: {decision_scout.get('take_profit_pct', 'N/A')} → {adjusted.get('take_profit_pct', 'N/A')}")
                                    logger.info(f"  Position size mult: {adjusted.get('position_size_multiplier', 1.0)}")

                                decision_scout = adjusted

                                # Check direction mismatch warning
                                preferred_dir = regime.recommended_params.get('preferred_direction', 'any')
                                if preferred_dir != 'any' and direction_scout != preferred_dir:
                                    logger.warning(f"⚠️ Trade direction {direction_scout} conflicts with regime preference {preferred_dir}")
                                    # Apply confidence penalty
                                    if CONFIG.get("REGIME_DIRECTION_PENALTY"):
                                        original_conf = conf_scout
                                        conf_scout *= CONFIG["REGIME_DIRECTION_PENALTY"]
                                        decision_scout['confidence'] = conf_scout
                                        logger.info(f"  Confidence penalized: {original_conf:.0%} → {conf_scout:.0%}")

                                # Add regime info to decision
                                decision_scout['regime_info'] = {
                                    'regime': regime.regime.value,
                                    'confidence': regime.confidence,
                                    'trend_strength': regime.trend_strength,
                                    'adjustments_applied': True
                                }

                            # ========== CONFIDENCE CALIBRATION ==========
                            calibration_result = None
                            calibration_passed = True  # Flag to track if calibration allows trade

                            if CONFIG.get("CALIBRATION_ENABLED", True) and bot_state.confidence_calibrator:
                                logger.info(f"📊 Applying confidence calibration for {sym_scout}...")

                                # Ottieni il modello usato (se disponibile)
                                model_used = decision_scout.get('_model', None)

                                decision_scout, calibration_result = calibrate_decision(decision_scout, model_used)

                                if calibration_result:
                                    # Log calibration details
                                    logger.info(
                                        f"📈 Calibration result: "
                                        f"Conf {calibration_result.original_confidence:.0%} → {calibration_result.calibrated_confidence:.0%} | "
                                        f"Historical WR: {calibration_result.historical_win_rate:.0%} | "
                                        f"Execute: {calibration_result.should_execute}"
                                    )

                                    # Check if should block trade
                                    if not calibration_result.should_execute and CONFIG.get("CALIBRATION_BLOCK_ON_FAIL", True):
                                        logger.warning(
                                            f"🚫 Trade BLOCKED by calibration: {calibration_result.reason}"
                                        )

                                        # Log blocked trade
                                        try:
                                            db_utils.log_bot_operation(
                                                operation="skip",
                                                symbol=sym_scout,
                                                direction=direction_scout,
                                                confidence=calibration_result.original_confidence,
                                                raw_payload={
                                                    "reason": f"Calibration block: {calibration_result.reason}",
                                                    "calibration": decision_scout.get('_calibration', {}),
                                                    "phase": "scouting_calibration_block"
                                                },
                                                cycle_id=cycle_id_scout
                                            )
                                        except Exception as log_err:
                                            logger.debug(f"Could not log blocked trade: {log_err}")

                                        # Set flag to skip execution
                                        calibration_passed = False

                                    # Log warnings
                                    if calibration_result.warnings:
                                        for warn in calibration_result.warnings:
                                            logger.warning(f"⚠️ Calibration warning: {warn}")

                                    # Update conf_scout with calibrated value
                                    conf_scout = decision_scout.get('confidence', conf_scout)

                            if calibration_passed and trend_check_passed and conf_scout >= CONFIG["MIN_CONFIDENCE"]:
                                # Log Operation FIRST
                                decision_scout['cycle_id'] = cycle_id_scout
                                if trend_info:
                                    decision_scout['trend_info'] = trend_info
    
                                op_id = db_utils.log_bot_operation(
                                    operation_payload=decision_scout,
                                    system_prompt=final_prompt_scout,
                                    indicators=json.loads(subset_ind),
                                    news_text=news_txt,
                                    sentiment=sentiment_json,
                                    forecasts=json.loads(subset_forc)
                                )
                                logger.info(f"📝 Operation logged (ID: {op_id})")
    
                                # Execute Open
                                # Check if SHORTS are allowed (for debugging)
                                if direction_scout == "short" and not CONFIG["ALLOW_SHORTS"]:
                                    logger.warning(f"⛔ SHORT disabilitati per configurazione (ALLOW_SHORTS=false)")
                                    decision_scout['execution_result'] = {"status": "blocked", "reason": "SHORTS disabled by config"}
                                else:
                                    can_trade = risk_manager.can_open_position(balance_usd)
                                    if can_trade["allowed"]:
                                        res = trader.execute_signal_with_risk(decision_scout, risk_manager, balance_usd)
                                        # Log execution...
                                        if 'execution_result' not in decision_scout:
                                            decision_scout['execution_result'] = res
    
                                        if res.get("status") == "ok":
                                            try:
                                                entry_price = res.get("fill_price")
                                                if not entry_price:
                                                    # Fallback to current market price from indicators
                                                    if sym_scout in indicators_map and 'current' in indicators_map[sym_scout]:
                                                        entry_price = indicators_map[sym_scout]['current'].get('price', 0)
    
                                                trade_id = db_utils.log_executed_trade(
                                                    bot_operation_id=op_id,  # Link to the logged operation
                                                    trade_type="open",
                                                    symbol=sym_scout,
                                                    direction=decision_scout.get("direction", "long"),
                                                    size=res.get("size", 0),
                                                    entry_price=entry_price or 0,
                                                    leverage=decision_scout.get("leverage", 1),
                                                    stop_loss_price=decision_scout.get("stop_loss", 0),
                                                    take_profit_price=decision_scout.get("take_profit", 0),
                                                    hl_order_id=res.get("order_id"),
                                                    hl_fill_price=res.get("fill_price"),
                                                    size_usd=res.get("size_usd"),
                                                    raw_response=res
                                                )
                                                bot_state.active_trades[sym_scout] = trade_id
                                                logger.info(f"✅ Trade {sym_scout} aperto e loggato (ID: {trade_id})")
    
                                                # Notify - Calculate actual SL/TP prices from percentages
                                                try:
                                                    risk_info = res.get("risk_management", {})
                                                    sl_pct = risk_info.get("stop_loss_pct", 2.0)
                                                    tp_pct = risk_info.get("take_profit_pct", 5.0)
                                                    direction = decision_scout.get("direction", "long")
    
                                                    # Calculate actual prices based on entry and direction
                                                    if entry_price and entry_price > 0:
                                                        if direction == "long":
                                                            stop_loss_price = entry_price * (1 - sl_pct / 100)
                                                            take_profit_price = entry_price * (1 + tp_pct / 100)
                                                        else:  # short
                                                            stop_loss_price = entry_price * (1 + sl_pct / 100)
                                                            take_profit_price = entry_price * (1 - tp_pct / 100)
                                                    else:
                                                        stop_loss_price = 0.0
                                                        take_profit_price = 0.0
    
                                                    # Calculate size_usd if not in response
                                                    size_usd = res.get("size_usd")
                                                    if not size_usd or size_usd == 0:
                                                        size = res.get("size", 0)
                                                        if size and entry_price:
                                                            size_usd = size * entry_price
                                                        else:
                                                            size_usd = 0.0
    
                                                    # Get public URL for details
                                                    import os
                                                    api_url = os.getenv("PUBLIC_API_URL", "https://static.9.126.98.91.clients.your-server.de")
                                                    details_url = f"{api_url}/api/trades/{trade_id}/details"
    
                                                    # Send Instant View notification
                                                    from notifications import send_trade_notification
                                                    send_trade_notification(
                                                        trade_id=trade_id,
                                                        symbol=sym_scout,
                                                        direction=direction,
                                                        action='opened',
                                                        entry_price=entry_price or 0,
                                                        size=res.get("size", 0),
                                                        leverage=decision_scout.get("leverage", 1)
                                                    )
                                                except Exception as e:
                                                    logger.warning(f"⚠️ Notify error: {e}")
    
                                            except Exception as log_err:
                                                logger.error(f"❌ Errore logging apertura: {log_err}")
                                    else:
                                        logger.warning(f"⛔ Risk Manager blocca apertura: {can_trade['reason']}")
                                        decision_scout['execution_result'] = {"status": "blocked", "reason": can_trade['reason']}
                            else:
                                 logger.info(f"⏩ Skip OPEN {sym_scout}: Conf {conf_scout:.2f} o Trend Check {trend_check_passed}")
                    
                    elif op_scout == "close":
                        logger.warning(f"⚠️ AI ha suggerito CLOSE in fase SCOUTING. Ignorato.")
    
                        # Log close operation (not executed)
                        decision_scout['cycle_id'] = cycle_id_scout
                        if trend_info:
                            decision_scout['trend_info'] = trend_info
    
                        db_utils.log_bot_operation(
                            operation_payload=decision_scout,
                            system_prompt=final_prompt_scout,
                            indicators=json.loads(subset_ind),
                            news_text=news_txt,
                            sentiment=sentiment_json,
                            forecasts=json.loads(subset_forc)
                        )
    
                    elif op_scout == "hold":
                        logger.info(f"⏸️ HOLD {sym_scout} - Conf: {conf_scout:.2f}")
    
                        # Log hold operation
                        decision_scout['cycle_id'] = cycle_id_scout
                        if trend_info:
                            decision_scout['trend_info'] = trend_info
    
                        db_utils.log_bot_operation(
                            operation_payload=decision_scout,
                            system_prompt=final_prompt_scout,
                            indicators=json.loads(subset_ind),
                            news_text=news_txt,
                            sentiment=sentiment_json,
                            forecasts=json.loads(subset_forc)
                        )
    
                    else:
                        logger.info(f"⏩ Skip {sym_scout}: Conf {conf_scout:.2f} o Trend Check {trend_check_passed}")
    
                        # Log skip operation
                        decision_scout['cycle_id'] = cycle_id_scout
                        if trend_info:
                            decision_scout['trend_info'] = trend_info
    
                        db_utils.log_bot_operation(
                            operation_payload=decision_scout,
                            system_prompt=final_prompt_scout,
                            indicators=json.loads(subset_ind),
                            news_text=news_txt,
                            sentiment=sentiment_json,
                            forecasts=json.loads(subset_forc)
                        )

            except Exception as e:
                logger.error(f"❌ Errore fase scouting: {e}")

    except Exception as e:
        logger.error(f"❌ ERRORE CRITICO nel ciclo: {e}", exc_info=True)

        # Log errore su database
        try:
            db_utils.log_error(
                e,
                context={
                    "indicators": indicators_json,
                    "news": news_txt[:500] if news_txt else None,
                    "sentiment": sentiment_json,
                    "forecasts": forecasts_json,
                    "whale_alerts": whale_alerts_list,
                    "account": account_status
                },
                source="trading_cycle"
            )
        except:
            pass


def health_check() -> None:
    """Health check per verificare connettività"""
    try:
        if bot_state.trader:
            mids = bot_state.trader.info.all_mids()
            logger.debug(f"✅ Health check: {len(mids)} simboli disponibili")
    except Exception as e:
        logger.warning(f"⚠️ Health check fallito: {e}")


# ============================================================
#                      ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 TRADING AGENT - Avvio")
    logger.info("=" * 60)
    logger.info(f"📋 Configurazione: {json.dumps(CONFIG, indent=2)}")

    try:
        # Inizializza
        if not bot_state.initialize():
            logger.error("❌ Inizializzazione fallita")
            sys.exit(1)

        # Invia notifica di avvio via Telegram PRIMA di avviare lo scheduler
        try:
            if notifier.enabled:
                logger.info("📤 Invio notifica di avvio via Telegram...")
                notifier.notify_startup(
                    testnet=CONFIG["TESTNET"],
                    tickers=CONFIG["TICKERS"],
                    cycle_interval_minutes=CONFIG["CYCLE_INTERVAL_MINUTES"],
                    wallet_address=WALLET_ADDRESS,
                    screening_enabled=CONFIG.get("SCREENING_ENABLED", False),
                    top_n_coins=CONFIG.get("TOP_N_COINS", 5),
                    rebalance_day=CONFIG.get("REBALANCE_DAY", "sunday"),
                    sentiment_interval_minutes=5,  # Da sentiment.py INTERVALLO_SECONDI / 60
                    health_check_interval_minutes=5  # Da scheduler.py
                )
                logger.info("✅ Notifica di avvio inviata via Telegram")
            else:
                logger.warning("⚠️ Telegram notifier non configurato (mancano TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID)")
        except Exception as e:
            logger.error(f"❌ Errore nell'invio notifica Telegram: {e}", exc_info=True)

        # Avvia scheduler (bloccante)
        scheduler = TradingScheduler(
            trading_func=trading_cycle,
            interval_minutes=CONFIG["CYCLE_INTERVAL_MINUTES"],
            health_check_func=health_check
        )

        scheduler.start()

    except KeyboardInterrupt:
        logger.info("🛑 Interruzione manuale")
    except Exception as e:
        logger.error(f"❌ Errore fatale: {e}", exc_info=True)
        sys.exit(1)
