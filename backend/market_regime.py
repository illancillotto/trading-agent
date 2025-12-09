"""
Market Regime Detection Module
Identifica il regime di mercato corrente e fornisce parametri ottimali per il trading.
"""

import logging
import numpy as np
from enum import Enum
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Regimi di mercato identificabili"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


@dataclass
class RegimeAnalysis:
    """Risultato dell'analisi del regime"""
    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    adx_value: float
    volatility_percentile: float
    trend_strength: float  # -1.0 (strong down) to +1.0 (strong up)
    recommended_params: Dict
    strategy_hint: str
    warnings: List[str]

    def __str__(self) -> str:
        return (
            f"Regime: {self.regime.value} (conf: {self.confidence:.0%}) | "
            f"ADX: {self.adx_value:.1f} | Vol%: {self.volatility_percentile:.0f} | "
            f"Strategy: {self.strategy_hint}"
        )

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "adx_value": self.adx_value,
            "volatility_percentile": self.volatility_percentile,
            "trend_strength": self.trend_strength,
            "recommended_params": self.recommended_params,
            "strategy_hint": self.strategy_hint,
            "warnings": self.warnings
        }


class RegimeDetector:
    """
    Rileva il regime di mercato corrente basandosi su:
    - ADX (trend strength)
    - ATR percentile (volatility)
    - EMA slopes (trend direction)
    - Price position relative to EMAs
    """

    # Soglie configurabili
    DEFAULT_CONFIG = {
        "adx_trending_threshold": 25,      # ADX > 25 = trending
        "adx_strong_threshold": 40,        # ADX > 40 = strong trend
        "adx_weak_threshold": 15,          # ADX < 15 = very weak/ranging
        "volatility_high_percentile": 75,  # ATR > 75th percentile = high vol
        "volatility_low_percentile": 25,   # ATR < 25th percentile = low vol
        "ema_alignment_threshold": 0.02,   # 2% difference for alignment check
        "breakout_volume_multiplier": 1.5, # Volume > 1.5x average = potential breakout
    }

    # Parametri ottimali per ogni regime
    REGIME_PARAMS = {
        MarketRegime.TRENDING_UP: {
            "preferred_direction": "long",
            "leverage_multiplier": 1.2,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.5,
            "position_size_multiplier": 1.1,
            "min_rr_ratio": 1.5,
            "strategy": "trend_following",
            "description": "Strong uptrend - favor long positions with wider TP"
        },
        MarketRegime.TRENDING_DOWN: {
            "preferred_direction": "short",
            "leverage_multiplier": 1.0,
            "sl_multiplier": 1.2,
            "tp_multiplier": 1.3,
            "position_size_multiplier": 1.0,
            "min_rr_ratio": 1.5,
            "strategy": "trend_following",
            "description": "Strong downtrend - favor short positions, slightly wider SL"
        },
        MarketRegime.RANGING: {
            "preferred_direction": None,
            "leverage_multiplier": 0.7,
            "sl_multiplier": 0.8,
            "tp_multiplier": 0.8,
            "position_size_multiplier": 0.8,
            "min_rr_ratio": 1.2,
            "strategy": "mean_reversion",
            "description": "Ranging market - reduce size, trade S/R levels"
        },
        MarketRegime.HIGH_VOLATILITY: {
            "preferred_direction": None,
            "leverage_multiplier": 0.5,
            "sl_multiplier": 1.8,
            "tp_multiplier": 2.0,
            "position_size_multiplier": 0.6,
            "min_rr_ratio": 1.3,
            "strategy": "breakout_or_wait",
            "description": "High volatility - reduce leverage, widen SL/TP significantly"
        },
        MarketRegime.LOW_VOLATILITY: {
            "preferred_direction": None,
            "leverage_multiplier": 1.0,
            "sl_multiplier": 0.7,
            "tp_multiplier": 1.0,
            "position_size_multiplier": 0.9,
            "min_rr_ratio": 1.5,
            "strategy": "wait_for_breakout",
            "description": "Low volatility - tighter SL, wait for expansion"
        },
        MarketRegime.BREAKOUT: {
            "preferred_direction": None,  # Determined by breakout direction
            "leverage_multiplier": 0.8,
            "sl_multiplier": 1.2,
            "tp_multiplier": 2.0,
            "position_size_multiplier": 0.9,
            "min_rr_ratio": 2.0,
            "strategy": "breakout_follow",
            "description": "Potential breakout - wait for confirmation, then follow"
        },
        MarketRegime.UNKNOWN: {
            "preferred_direction": None,
            "leverage_multiplier": 0.5,
            "sl_multiplier": 1.0,
            "tp_multiplier": 1.0,
            "position_size_multiplier": 0.5,
            "min_rr_ratio": 1.5,
            "strategy": "conservative",
            "description": "Unclear regime - reduce exposure, wait for clarity"
        }
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        Inizializza il detector con configurazione opzionale.

        Args:
            config: Override per DEFAULT_CONFIG
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        logger.info(f"🔬 RegimeDetector initialized with ADX threshold: {self.config['adx_trending_threshold']}")

    def detect_regime(
        self,
        indicators: Dict,
        historical_atr: Optional[List[float]] = None
    ) -> RegimeAnalysis:
        """
        Rileva il regime di mercato corrente.

        Args:
            indicators: Dict con indicatori tecnici (adx, atr, ema20, ema50, ema200,
                       rsi, volume, avg_volume, price, macd, macd_signal)
            historical_atr: Lista di ATR storici per calcolare percentile (opzionale)

        Returns:
            RegimeAnalysis con regime identificato e parametri consigliati
        """
        warnings = []

        # Estrai indicatori con fallback
        adx = indicators.get('adx', 0)
        atr = indicators.get('atr', 0)
        atr_pct = indicators.get('atr_pct', 0)  # ATR as % of price
        price = indicators.get('price', indicators.get('close', 0))
        ema20 = indicators.get('ema20', indicators.get('ema_20', price))
        ema50 = indicators.get('ema50', indicators.get('ema_50', price))
        ema200 = indicators.get('ema200', indicators.get('ema_200', price))
        rsi = indicators.get('rsi', 50)
        volume = indicators.get('volume', 0)
        avg_volume = indicators.get('avg_volume', indicators.get('volume_sma', volume))
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)

        # Calcola volatility percentile
        if historical_atr and len(historical_atr) > 10:
            volatility_percentile = self._calculate_percentile(atr, historical_atr)
        else:
            # Stima basata su ATR% tipico per crypto (2-5% normale)
            if atr_pct > 5:
                volatility_percentile = 85
            elif atr_pct > 3:
                volatility_percentile = 60
            elif atr_pct > 1.5:
                volatility_percentile = 40
            else:
                volatility_percentile = 20
            warnings.append("Using estimated volatility percentile (no historical ATR)")

        # Calcola trend strength (-1 to +1)
        trend_strength = self._calculate_trend_strength(
            price, ema20, ema50, ema200, macd, macd_signal
        )

        # Determina se siamo in trend
        is_trending = adx > self.config['adx_trending_threshold']
        is_strong_trend = adx > self.config['adx_strong_threshold']
        is_weak = adx < self.config['adx_weak_threshold']

        # Determina volatilità
        is_high_vol = volatility_percentile > self.config['volatility_high_percentile']
        is_low_vol = volatility_percentile < self.config['volatility_low_percentile']

        # Detect potential breakout
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        is_volume_spike = volume_ratio > self.config['breakout_volume_multiplier']

        # Classifica regime
        regime, confidence = self._classify_regime(
            is_trending=is_trending,
            is_strong_trend=is_strong_trend,
            is_weak=is_weak,
            is_high_vol=is_high_vol,
            is_low_vol=is_low_vol,
            is_volume_spike=is_volume_spike,
            trend_strength=trend_strength,
            adx=adx,
            rsi=rsi
        )

        # Ottieni parametri per il regime
        params = self.REGIME_PARAMS.get(regime, self.REGIME_PARAMS[MarketRegime.UNKNOWN])

        # Aggiungi warning specifici
        if is_high_vol and is_trending:
            warnings.append("High volatility in trending market - increased whipsaw risk")
        if rsi > 70 and regime == MarketRegime.TRENDING_UP:
            warnings.append("RSI overbought in uptrend - potential reversal")
        if rsi < 30 and regime == MarketRegime.TRENDING_DOWN:
            warnings.append("RSI oversold in downtrend - potential bounce")
        if is_volume_spike and not is_trending:
            warnings.append("Volume spike in ranging market - watch for breakout")

        analysis = RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            adx_value=adx,
            volatility_percentile=volatility_percentile,
            trend_strength=trend_strength,
            recommended_params=params,
            strategy_hint=params.get('strategy', 'unknown'),
            warnings=warnings
        )

        logger.info(f"📊 Regime Analysis: {analysis}")

        return analysis

    def _calculate_percentile(self, value: float, historical: List[float]) -> float:
        """Calcola il percentile di un valore rispetto alla distribuzione storica"""
        sorted_hist = sorted(historical)
        count_below = sum(1 for v in sorted_hist if v < value)
        return (count_below / len(sorted_hist)) * 100

    def _calculate_trend_strength(
        self,
        price: float,
        ema20: float,
        ema50: float,
        ema200: float,
        macd: float,
        macd_signal: float
    ) -> float:
        """
        Calcola la forza del trend da -1 (strong down) a +1 (strong up).

        Fattori considerati:
        - Posizione prezzo vs EMAs
        - Ordine EMAs (20 > 50 > 200 = bullish)
        - MACD position
        """
        if price == 0:
            return 0.0

        score = 0.0
        factors = 0

        # Price vs EMA20 (peso: 0.25)
        if ema20 > 0:
            pct_from_ema20 = (price - ema20) / ema20
            score += np.clip(pct_from_ema20 * 10, -0.25, 0.25)
            factors += 1

        # Price vs EMA50 (peso: 0.20)
        if ema50 > 0:
            pct_from_ema50 = (price - ema50) / ema50
            score += np.clip(pct_from_ema50 * 5, -0.20, 0.20)
            factors += 1

        # EMA alignment (peso: 0.25)
        if ema20 > 0 and ema50 > 0 and ema200 > 0:
            if ema20 > ema50 > ema200:
                score += 0.25  # Perfect bullish alignment
            elif ema20 < ema50 < ema200:
                score -= 0.25  # Perfect bearish alignment
            elif ema20 > ema50:
                score += 0.10  # Partial bullish
            elif ema20 < ema50:
                score -= 0.10  # Partial bearish
            factors += 1

        # MACD (peso: 0.30)
        if macd != 0 or macd_signal != 0:
            if macd > 0 and macd > macd_signal:
                score += 0.30  # Bullish MACD
            elif macd < 0 and macd < macd_signal:
                score -= 0.30  # Bearish MACD
            elif macd > macd_signal:
                score += 0.15  # Bullish crossover
            elif macd < macd_signal:
                score -= 0.15  # Bearish crossover
            factors += 1

        return np.clip(score, -1.0, 1.0)

    def _classify_regime(
        self,
        is_trending: bool,
        is_strong_trend: bool,
        is_weak: bool,
        is_high_vol: bool,
        is_low_vol: bool,
        is_volume_spike: bool,
        trend_strength: float,
        adx: float,
        rsi: float
    ) -> Tuple[MarketRegime, float]:
        """
        Classifica il regime di mercato e calcola confidence.

        Returns:
            Tuple di (MarketRegime, confidence)
        """
        # Alta volatilità ha priorità
        if is_high_vol:
            if is_volume_spike and is_weak:
                return MarketRegime.BREAKOUT, 0.7
            return MarketRegime.HIGH_VOLATILITY, 0.8

        # Trend forte
        if is_strong_trend:
            if trend_strength > 0.3:
                return MarketRegime.TRENDING_UP, 0.9
            elif trend_strength < -0.3:
                return MarketRegime.TRENDING_DOWN, 0.9

        # Trend moderato
        if is_trending:
            if trend_strength > 0.15:
                confidence = 0.6 + (adx - 25) / 100  # Più alto ADX = più confidence
                return MarketRegime.TRENDING_UP, min(confidence, 0.85)
            elif trend_strength < -0.15:
                confidence = 0.6 + (adx - 25) / 100
                return MarketRegime.TRENDING_DOWN, min(confidence, 0.85)

        # Bassa volatilità
        if is_low_vol:
            if is_volume_spike:
                return MarketRegime.BREAKOUT, 0.6
            return MarketRegime.LOW_VOLATILITY, 0.75

        # Mercato debole/ranging
        if is_weak:
            return MarketRegime.RANGING, 0.7

        # Default: ranging con confidence media
        return MarketRegime.RANGING, 0.5

    def adjust_trade_params(
        self,
        decision: Dict,
        regime_analysis: RegimeAnalysis
    ) -> Dict:
        """
        Aggiusta i parametri di un trade decision basandosi sul regime.

        Args:
            decision: Dict con decisione LLM (leverage, sl_pct, tp_pct, etc.)
            regime_analysis: Analisi del regime corrente

        Returns:
            Dict con parametri aggiustati
        """
        params = regime_analysis.recommended_params
        adjusted = decision.copy()

        # Aggiusta leverage
        original_leverage = decision.get('leverage', 3)
        adjusted_leverage = int(original_leverage * params['leverage_multiplier'])
        adjusted['leverage'] = max(1, min(10, adjusted_leverage))

        # Aggiusta stop loss
        original_sl = decision.get('stop_loss_pct', 2.0)
        adjusted_sl = original_sl * params['sl_multiplier']
        adjusted['stop_loss_pct'] = max(0.5, min(10.0, adjusted_sl))

        # Aggiusta take profit
        original_tp = decision.get('take_profit_pct', 4.0)
        adjusted_tp = original_tp * params['tp_multiplier']
        adjusted['take_profit_pct'] = max(1.0, min(50.0, adjusted_tp))

        # Verifica R:R ratio minimo
        min_rr = params['min_rr_ratio']
        current_rr = adjusted['take_profit_pct'] / adjusted['stop_loss_pct']
        if current_rr < min_rr:
            # Aumenta TP per raggiungere minimo R:R
            adjusted['take_profit_pct'] = adjusted['stop_loss_pct'] * min_rr
            logger.info(f"📐 Adjusted TP to meet min R:R {min_rr}: {adjusted['take_profit_pct']:.1f}%")

        # Aggiusta position size
        original_portion = decision.get('target_portion_of_balance', 0.1)
        adjusted_portion = original_portion * params['position_size_multiplier']
        adjusted['target_portion_of_balance'] = max(0.05, min(0.3, adjusted_portion))

        # Aggiungi metadata
        adjusted['_regime_adjusted'] = True
        adjusted['_regime'] = regime_analysis.regime.value
        adjusted['_regime_confidence'] = regime_analysis.confidence
        adjusted['_adjustments'] = {
            'leverage': f"{original_leverage} → {adjusted['leverage']}",
            'stop_loss_pct': f"{original_sl:.1f}% → {adjusted['stop_loss_pct']:.1f}%",
            'take_profit_pct': f"{original_tp:.1f}% → {adjusted['take_profit_pct']:.1f}%",
            'position': f"{original_portion:.1%} → {adjusted['target_portion_of_balance']:.1%}"
        }

        # Check direction preference
        preferred_dir = params.get('preferred_direction')
        trade_dir = decision.get('direction', 'long')

        if preferred_dir and trade_dir != preferred_dir:
            adjusted['_direction_warning'] = (
                f"Trade direction '{trade_dir}' conflicts with regime preference '{preferred_dir}'"
            )
            logger.warning(f"⚠️ {adjusted['_direction_warning']}")

        logger.info(
            f"🔧 Regime adjustment ({regime_analysis.regime.value}): "
            f"Leverage {adjusted['_adjustments']['leverage']}, "
            f"SL {adjusted['_adjustments']['stop_loss_pct']}, "
            f"TP {adjusted['_adjustments']['take_profit_pct']}"
        )

        return adjusted


# Singleton instance
_regime_detector: Optional[RegimeDetector] = None


def get_regime_detector(config: Optional[Dict] = None) -> RegimeDetector:
    """
    Restituisce l'istanza singleton del RegimeDetector.

    Args:
        config: Configurazione opzionale (usata solo alla prima chiamata)

    Returns:
        RegimeDetector instance
    """
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector(config)
    return _regime_detector


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    detector = get_regime_detector()

    # Test cases
    test_cases = [
        {
            "name": "Strong Uptrend",
            "indicators": {
                "adx": 45, "atr": 1500, "atr_pct": 3.0,
                "price": 100000, "ema20": 98000, "ema50": 95000, "ema200": 85000,
                "rsi": 65, "volume": 1000000, "avg_volume": 800000,
                "macd": 500, "macd_signal": 300
            }
        },
        {
            "name": "Ranging Market",
            "indicators": {
                "adx": 12, "atr": 800, "atr_pct": 1.5,
                "price": 50000, "ema20": 50100, "ema50": 49900, "ema200": 48000,
                "rsi": 52, "volume": 500000, "avg_volume": 600000,
                "macd": 50, "macd_signal": 45
            }
        },
        {
            "name": "High Volatility",
            "indicators": {
                "adx": 30, "atr": 3000, "atr_pct": 6.0,
                "price": 95000, "ema20": 96000, "ema50": 94000, "ema200": 90000,
                "rsi": 45, "volume": 2000000, "avg_volume": 800000,
                "macd": -200, "macd_signal": -100
            }
        }
    ]

    for tc in test_cases:
        print(f"\n{'='*50}")
        print(f"Test: {tc['name']}")
        print('='*50)
        analysis = detector.detect_regime(tc['indicators'])
        print(f"Result: {analysis}")
        print(f"Params: {analysis.recommended_params}")
        if analysis.warnings:
            print(f"Warnings: {analysis.warnings}")
