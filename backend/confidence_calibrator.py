"""
Confidence Calibrator Module
Analizza la correlazione tra confidence LLM e risultati reali dei trade.
Fornisce calibrazione dinamica e soglie ottimali.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import db_utils

logger = logging.getLogger(__name__)


class CalibrationQuality(Enum):
    """Qualità della calibrazione basata su sample size"""
    EXCELLENT = "excellent"    # 50+ trades nella fascia
    GOOD = "good"              # 20-49 trades
    MODERATE = "moderate"      # 10-19 trades
    LOW = "low"                # 5-9 trades
    INSUFFICIENT = "insufficient"  # <5 trades


@dataclass
class ConfidenceBandStats:
    """Statistiche per una fascia di confidence"""
    band_start: float
    band_end: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_pnl_pct: float
    avg_pnl_usd: float
    total_pnl_usd: float
    std_pnl_pct: float
    sharpe_ratio: float  # Simplified: avg_pnl / std_pnl
    avg_duration_minutes: float
    best_trade_pnl: float
    worst_trade_pnl: float
    quality: CalibrationQuality
    recommendation: str

    def __str__(self) -> str:
        return (
            f"[{self.band_start:.0%}-{self.band_end:.0%}] "
            f"WR: {self.win_rate:.1%} | "
            f"Avg: {self.avg_pnl_pct:+.2f}% | "
            f"Sharpe: {self.sharpe_ratio:.2f} | "
            f"n={self.total_trades} ({self.quality.value})"
        )


@dataclass
class CalibrationReport:
    """Report completo di calibrazione"""
    generated_at: datetime
    period_days: int
    total_trades_analyzed: int
    bands: List[ConfidenceBandStats]
    optimal_threshold: float
    optimal_band: Optional[ConfidenceBandStats]
    model_breakdown: Dict[str, Dict]
    direction_breakdown: Dict[str, Dict]
    symbol_breakdown: Dict[str, Dict]
    recommendations: List[str]
    warnings: List[str]

    def get_band_for_confidence(self, confidence: float) -> Optional[ConfidenceBandStats]:
        """Trova la banda che contiene questa confidence"""
        for band in self.bands:
            if band.band_start <= confidence < band.band_end:
                return band
        # Edge case: confidence = 1.0
        if confidence == 1.0 and self.bands:
            return self.bands[-1]
        return None

    def to_dict(self) -> Dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "period_days": self.period_days,
            "total_trades": self.total_trades_analyzed,
            "optimal_threshold": self.optimal_threshold,
            "bands": [
                {
                    "range": f"{b.band_start:.0%}-{b.band_end:.0%}",
                    "win_rate": b.win_rate,
                    "avg_pnl_pct": b.avg_pnl_pct,
                    "sharpe": b.sharpe_ratio,
                    "trades": b.total_trades,
                    "quality": b.quality.value,
                    "recommendation": b.recommendation
                }
                for b in self.bands
            ],
            "recommendations": self.recommendations,
            "warnings": self.warnings
        }


@dataclass
class CalibrationDecision:
    """Decisione del calibrator su un trade"""
    should_execute: bool
    original_confidence: float
    calibrated_confidence: float
    confidence_adjustment: float
    historical_win_rate: float
    historical_avg_pnl: float
    band_quality: CalibrationQuality
    reason: str
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "✅ EXECUTE" if self.should_execute else "❌ BLOCK"
        return (
            f"{status} | Conf: {self.original_confidence:.0%} → {self.calibrated_confidence:.0%} | "
            f"Historical WR: {self.historical_win_rate:.1%} | "
            f"Reason: {self.reason}"
        )


class ConfidenceCalibrator:
    """
    Calibra la confidence delle decisioni LLM basandosi sui risultati storici.

    Funzionalità:
    - Analizza win rate per fasce di confidence
    - Identifica soglia ottimale di confidence
    - Calcola Sharpe ratio per fascia
    - Fornisce adjustment factors
    - Breakdown per modello, direzione, simbolo
    """

    # Configurazione default
    DEFAULT_CONFIG = {
        "confidence_bands": [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "min_trades_for_calibration": 5,
        "min_trades_for_reliable": 20,
        "min_win_rate_threshold": 0.40,      # Blocca se WR storico < 40%
        "min_avg_pnl_threshold": -1.0,       # Blocca se avg P&L < -1%
        "min_sharpe_threshold": 0.0,         # Blocca se Sharpe < 0
        "lookback_days": 30,                 # Analizza ultimi 30 giorni
        "enable_confidence_adjustment": True,
        "max_confidence_boost": 0.15,        # Max +15% confidence
        "max_confidence_penalty": 0.25,      # Max -25% confidence
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        Inizializza il calibrator.

        Args:
            config: Override per DEFAULT_CONFIG
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._calibration_cache: Optional[CalibrationReport] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_minutes = 60  # Refresh ogni ora

        logger.info(
            f"📊 ConfidenceCalibrator initialized | "
            f"Lookback: {self.config['lookback_days']}d | "
            f"Min WR: {self.config['min_win_rate_threshold']:.0%}"
        )

    def generate_calibration_report(
        self,
        days: Optional[int] = None,
        force_refresh: bool = False
    ) -> CalibrationReport:
        """
        Genera un report completo di calibrazione.

        Args:
            days: Numero di giorni da analizzare (default: config lookback)
            force_refresh: Forza rigenerazione anche se cache valida

        Returns:
            CalibrationReport con tutte le statistiche
        """
        # Check cache
        if not force_refresh and self._is_cache_valid():
            logger.debug("📦 Using cached calibration report")
            return self._calibration_cache

        days = days or self.config['lookback_days']
        logger.info(f"📊 Generating calibration report for last {days} days...")

        # Fetch trade data from database
        trades = self._fetch_trade_data(days)

        if not trades:
            logger.warning("⚠️ No trade data available for calibration")
            return self._generate_empty_report(days)

        logger.info(f"📈 Analyzing {len(trades)} trades...")

        # Calculate band statistics
        bands = self._calculate_band_stats(trades)

        # Find optimal threshold
        optimal_threshold, optimal_band = self._find_optimal_threshold(bands)

        # Breakdown analysis
        model_breakdown = self._analyze_by_model(trades)
        direction_breakdown = self._analyze_by_direction(trades)
        symbol_breakdown = self._analyze_by_symbol(trades)

        # Generate recommendations
        recommendations, warnings = self._generate_recommendations(
            bands, model_breakdown, direction_breakdown
        )

        report = CalibrationReport(
            generated_at=datetime.utcnow(),
            period_days=days,
            total_trades_analyzed=len(trades),
            bands=bands,
            optimal_threshold=optimal_threshold,
            optimal_band=optimal_band,
            model_breakdown=model_breakdown,
            direction_breakdown=direction_breakdown,
            symbol_breakdown=symbol_breakdown,
            recommendations=recommendations,
            warnings=warnings
        )

        # Update cache
        self._calibration_cache = report
        self._cache_timestamp = datetime.utcnow()

        logger.info(
            f"✅ Calibration report generated | "
            f"Optimal threshold: {optimal_threshold:.0%} | "
            f"Recommendations: {len(recommendations)}"
        )

        return report

    def evaluate_decision(
        self,
        decision: Dict,
        model: Optional[str] = None
    ) -> CalibrationDecision:
        """
        Valuta una decisione di trading basandosi sulla calibrazione storica.

        Args:
            decision: Dict con decisione LLM (deve avere 'confidence', 'direction', 'symbol')
            model: Nome del modello che ha generato la decisione

        Returns:
            CalibrationDecision con raccomandazione
        """
        original_confidence = decision.get('confidence', 0.5)
        direction = decision.get('direction', 'long')
        symbol = decision.get('symbol', 'UNKNOWN')

        # Get or generate calibration report
        report = self.generate_calibration_report()

        warnings = []

        # Find relevant band
        band = report.get_band_for_confidence(original_confidence)

        if not band:
            return CalibrationDecision(
                should_execute=True,
                original_confidence=original_confidence,
                calibrated_confidence=original_confidence,
                confidence_adjustment=0.0,
                historical_win_rate=0.5,
                historical_avg_pnl=0.0,
                band_quality=CalibrationQuality.INSUFFICIENT,
                reason="No calibration data for this confidence range",
                warnings=["Operating without historical calibration"]
            )

        # Check band quality
        if band.quality == CalibrationQuality.INSUFFICIENT:
            warnings.append(f"Low sample size ({band.total_trades} trades) - calibration unreliable")

        # Calculate confidence adjustment
        calibrated_confidence, adjustment = self._calculate_adjustment(
            original_confidence, band, report
        )

        # Determine if should execute
        should_execute, block_reason = self._should_execute(
            band, direction, symbol, report
        )

        if not should_execute:
            return CalibrationDecision(
                should_execute=False,
                original_confidence=original_confidence,
                calibrated_confidence=calibrated_confidence,
                confidence_adjustment=adjustment,
                historical_win_rate=band.win_rate,
                historical_avg_pnl=band.avg_pnl_pct,
                band_quality=band.quality,
                reason=block_reason,
                warnings=warnings
            )

        # Build approval reason
        if adjustment > 0:
            reason = f"Historical performance supports trade (WR: {band.win_rate:.0%}, boosted confidence)"
        elif adjustment < 0:
            reason = f"Historical performance below average (WR: {band.win_rate:.0%}, reduced confidence)"
        else:
            reason = f"Historical performance neutral (WR: {band.win_rate:.0%})"

        return CalibrationDecision(
            should_execute=True,
            original_confidence=original_confidence,
            calibrated_confidence=calibrated_confidence,
            confidence_adjustment=adjustment,
            historical_win_rate=band.win_rate,
            historical_avg_pnl=band.avg_pnl_pct,
            band_quality=band.quality,
            reason=reason,
            warnings=warnings
        )

    def get_optimal_threshold(self) -> float:
        """Restituisce la soglia di confidence ottimale basata su dati storici"""
        report = self.generate_calibration_report()
        return report.optimal_threshold

    def _fetch_trade_data(self, days: int) -> List[Dict]:
        """Fetch trade data dal database"""
        try:
            query = """
            SELECT
                et.id,
                et.symbol,
                et.direction,
                et.entry_price,
                et.exit_price,
                et.pnl_usd,
                et.pnl_pct,
                et.duration_minutes,
                et.exit_reason,
                et.created_at,
                (bo.raw_payload->>'confidence')::NUMERIC as confidence,
                bo.raw_payload->>'model' as model,
                bo.raw_payload->>'reason' as ai_reason
            FROM executed_trades et
            LEFT JOIN bot_operations bo ON et.bot_operation_id = bo.id
            WHERE et.status = 'closed'
              AND et.created_at >= NOW() - INTERVAL '%s days'
              AND bo.raw_payload->>'confidence' IS NOT NULL
            ORDER BY et.created_at DESC
            """

            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (days,))
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

            trades = [dict(zip(columns, row)) for row in rows]
            return trades

        except Exception as e:
            logger.error(f"❌ Error fetching trade data: {e}")
            return []

    def _calculate_band_stats(self, trades: List[Dict]) -> List[ConfidenceBandStats]:
        """Calcola statistiche per ogni fascia di confidence"""
        bands = self.config['confidence_bands']
        band_stats = []

        for i in range(len(bands) - 1):
            band_start = bands[i]
            band_end = bands[i + 1]

            # Filter trades in this band
            band_trades = [
                t for t in trades
                if band_start <= (t.get('confidence') or 0) < band_end
            ]

            # Handle edge case for confidence = 1.0
            if band_end == 1.0:
                band_trades.extend([
                    t for t in trades
                    if (t.get('confidence') or 0) == 1.0
                ])

            stats = self._compute_band_statistics(band_start, band_end, band_trades)
            band_stats.append(stats)

        return band_stats

    def _compute_band_statistics(
        self,
        band_start: float,
        band_end: float,
        trades: List[Dict]
    ) -> ConfidenceBandStats:
        """Computa statistiche dettagliate per una banda"""

        total = len(trades)

        if total == 0:
            return ConfidenceBandStats(
                band_start=band_start,
                band_end=band_end,
                total_trades=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_pnl_pct=0.0,
                avg_pnl_usd=0.0,
                total_pnl_usd=0.0,
                std_pnl_pct=0.0,
                sharpe_ratio=0.0,
                avg_duration_minutes=0.0,
                best_trade_pnl=0.0,
                worst_trade_pnl=0.0,
                quality=CalibrationQuality.INSUFFICIENT,
                recommendation="No data - cannot evaluate"
            )

        # Basic stats
        pnl_pcts = [t.get('pnl_pct', 0) or 0 for t in trades]
        pnl_usds = [t.get('pnl_usd', 0) or 0 for t in trades]
        durations = [t.get('duration_minutes', 0) or 0 for t in trades]

        wins = sum(1 for p in pnl_pcts if p > 0)
        losses = total - wins
        win_rate = wins / total if total > 0 else 0

        avg_pnl_pct = statistics.mean(pnl_pcts) if pnl_pcts else 0
        avg_pnl_usd = statistics.mean(pnl_usds) if pnl_usds else 0
        total_pnl_usd = sum(pnl_usds)

        std_pnl_pct = statistics.stdev(pnl_pcts) if len(pnl_pcts) > 1 else 0
        sharpe = avg_pnl_pct / std_pnl_pct if std_pnl_pct > 0 else 0

        avg_duration = statistics.mean(durations) if durations else 0
        best_trade = max(pnl_pcts) if pnl_pcts else 0
        worst_trade = min(pnl_pcts) if pnl_pcts else 0

        # Determine quality
        if total >= 50:
            quality = CalibrationQuality.EXCELLENT
        elif total >= 20:
            quality = CalibrationQuality.GOOD
        elif total >= 10:
            quality = CalibrationQuality.MODERATE
        elif total >= 5:
            quality = CalibrationQuality.LOW
        else:
            quality = CalibrationQuality.INSUFFICIENT

        # Generate recommendation
        recommendation = self._generate_band_recommendation(
            win_rate, avg_pnl_pct, sharpe, quality
        )

        return ConfidenceBandStats(
            band_start=band_start,
            band_end=band_end,
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl_pct,
            avg_pnl_usd=avg_pnl_usd,
            total_pnl_usd=total_pnl_usd,
            std_pnl_pct=std_pnl_pct,
            sharpe_ratio=sharpe,
            avg_duration_minutes=avg_duration,
            best_trade_pnl=best_trade,
            worst_trade_pnl=worst_trade,
            quality=quality,
            recommendation=recommendation
        )

    def _generate_band_recommendation(
        self,
        win_rate: float,
        avg_pnl: float,
        sharpe: float,
        quality: CalibrationQuality
    ) -> str:
        """Genera raccomandazione per una banda"""

        if quality == CalibrationQuality.INSUFFICIENT:
            return "⚠️ Insufficient data - use with caution"

        if win_rate >= 0.6 and avg_pnl > 0 and sharpe > 0.5:
            return "✅ STRONG - High confidence trades perform well"
        elif win_rate >= 0.5 and avg_pnl > 0:
            return "✅ GOOD - Positive expectancy"
        elif win_rate >= 0.45 and avg_pnl > -0.5:
            return "⚡ NEUTRAL - Marginal performance"
        elif win_rate < 0.4 or avg_pnl < -1.0:
            return "❌ AVOID - Historically unprofitable"
        else:
            return "⚠️ CAUTION - Below average performance"

    def _find_optimal_threshold(
        self,
        bands: List[ConfidenceBandStats]
    ) -> Tuple[float, Optional[ConfidenceBandStats]]:
        """
        Trova la soglia ottimale di confidence.
        Ottimizza per Sharpe ratio con minimo sample size.
        """
        min_trades = self.config['min_trades_for_calibration']

        # Filter bands with sufficient data
        valid_bands = [
            b for b in bands
            if b.total_trades >= min_trades and b.avg_pnl_pct > 0
        ]

        if not valid_bands:
            # Fallback: usa la banda con più trades positivi
            positive_bands = [b for b in bands if b.win_rate > 0.5]
            if positive_bands:
                best = max(positive_bands, key=lambda b: b.total_trades)
                return best.band_start, best
            return 0.5, None  # Default threshold

        # Find band with best risk-adjusted return
        best_band = max(valid_bands, key=lambda b: b.sharpe_ratio)

        return best_band.band_start, best_band

    def _analyze_by_model(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Analizza performance per modello AI"""
        models = {}

        for trade in trades:
            model = trade.get('model', 'unknown') or 'unknown'
            if model not in models:
                models[model] = {'trades': [], 'pnl_pcts': []}
            models[model]['trades'].append(trade)
            models[model]['pnl_pcts'].append(trade.get('pnl_pct', 0) or 0)

        breakdown = {}
        for model, data in models.items():
            pnl_pcts = data['pnl_pcts']
            total = len(pnl_pcts)
            wins = sum(1 for p in pnl_pcts if p > 0)

            breakdown[model] = {
                'total_trades': total,
                'win_rate': wins / total if total > 0 else 0,
                'avg_pnl_pct': statistics.mean(pnl_pcts) if pnl_pcts else 0,
                'total_pnl_pct': sum(pnl_pcts)
            }

        return breakdown

    def _analyze_by_direction(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Analizza performance per direzione (long/short)"""
        directions = {'long': [], 'short': []}

        for trade in trades:
            direction = trade.get('direction', 'long')
            if direction in directions:
                directions[direction].append(trade.get('pnl_pct', 0) or 0)

        breakdown = {}
        for direction, pnl_pcts in directions.items():
            total = len(pnl_pcts)
            wins = sum(1 for p in pnl_pcts if p > 0)

            breakdown[direction] = {
                'total_trades': total,
                'win_rate': wins / total if total > 0 else 0,
                'avg_pnl_pct': statistics.mean(pnl_pcts) if pnl_pcts else 0,
                'total_pnl_pct': sum(pnl_pcts)
            }

        return breakdown

    def _analyze_by_symbol(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Analizza performance per simbolo"""
        symbols = {}

        for trade in trades:
            symbol = trade.get('symbol', 'UNKNOWN')
            if symbol not in symbols:
                symbols[symbol] = []
            symbols[symbol].append(trade.get('pnl_pct', 0) or 0)

        breakdown = {}
        for symbol, pnl_pcts in symbols.items():
            total = len(pnl_pcts)
            wins = sum(1 for p in pnl_pcts if p > 0)

            breakdown[symbol] = {
                'total_trades': total,
                'win_rate': wins / total if total > 0 else 0,
                'avg_pnl_pct': statistics.mean(pnl_pcts) if pnl_pcts else 0,
                'total_pnl_pct': sum(pnl_pcts)
            }

        return breakdown

    def _generate_recommendations(
        self,
        bands: List[ConfidenceBandStats],
        model_breakdown: Dict,
        direction_breakdown: Dict
    ) -> Tuple[List[str], List[str]]:
        """Genera raccomandazioni e warning basati sull'analisi"""
        recommendations = []
        warnings = []

        # Band-based recommendations
        profitable_bands = [b for b in bands if b.avg_pnl_pct > 0 and b.total_trades >= 5]
        unprofitable_bands = [b for b in bands if b.avg_pnl_pct < -0.5 and b.total_trades >= 5]

        if profitable_bands:
            best = max(profitable_bands, key=lambda b: b.sharpe_ratio)
            recommendations.append(
                f"Best confidence range: {best.band_start:.0%}-{best.band_end:.0%} "
                f"(WR: {best.win_rate:.0%}, Sharpe: {best.sharpe_ratio:.2f})"
            )

        if unprofitable_bands:
            for band in unprofitable_bands:
                warnings.append(
                    f"⚠️ Avoid confidence {band.band_start:.0%}-{band.band_end:.0%}: "
                    f"Historically negative (avg P&L: {band.avg_pnl_pct:+.2f}%)"
                )

        # Model-based recommendations
        for model, stats in model_breakdown.items():
            if stats['total_trades'] >= 10:
                if stats['win_rate'] > 0.55:
                    recommendations.append(
                        f"Model {model} performing well (WR: {stats['win_rate']:.0%})"
                    )
                elif stats['win_rate'] < 0.4:
                    warnings.append(
                        f"⚠️ Model {model} underperforming (WR: {stats['win_rate']:.0%})"
                    )

        # Direction-based recommendations
        long_stats = direction_breakdown.get('long', {})
        short_stats = direction_breakdown.get('short', {})

        if long_stats.get('total_trades', 0) >= 10 and short_stats.get('total_trades', 0) >= 10:
            long_wr = long_stats.get('win_rate', 0)
            short_wr = short_stats.get('win_rate', 0)

            if abs(long_wr - short_wr) > 0.15:
                better = 'LONG' if long_wr > short_wr else 'SHORT'
                recommendations.append(
                    f"{better} trades performing significantly better "
                    f"(Long WR: {long_wr:.0%}, Short WR: {short_wr:.0%})"
                )

        return recommendations, warnings

    def _calculate_adjustment(
        self,
        original: float,
        band: ConfidenceBandStats,
        report: CalibrationReport
    ) -> Tuple[float, float]:
        """
        Calcola l'aggiustamento di confidence basato su performance storica.

        Returns:
            Tuple di (calibrated_confidence, adjustment_amount)
        """
        if not self.config['enable_confidence_adjustment']:
            return original, 0.0

        if band.quality in [CalibrationQuality.INSUFFICIENT, CalibrationQuality.LOW]:
            return original, 0.0  # Non aggiustare con dati insufficienti

        # Base adjustment on win rate deviation from 50%
        wr_deviation = band.win_rate - 0.5

        # Scale by Sharpe ratio
        sharpe_factor = min(abs(band.sharpe_ratio), 1.0)  # Cap at 1

        # Calculate adjustment
        adjustment = wr_deviation * sharpe_factor * 0.3  # Max ~15%

        # Apply limits
        max_boost = self.config['max_confidence_boost']
        max_penalty = self.config['max_confidence_penalty']

        adjustment = max(-max_penalty, min(max_boost, adjustment))

        calibrated = max(0.0, min(1.0, original + adjustment))

        return calibrated, adjustment

    def _should_execute(
        self,
        band: ConfidenceBandStats,
        direction: str,
        symbol: str,
        report: CalibrationReport
    ) -> Tuple[bool, str]:
        """
        Determina se un trade dovrebbe essere eseguito.

        Returns:
            Tuple di (should_execute, reason)
        """
        # Check minimum win rate
        if band.win_rate < self.config['min_win_rate_threshold']:
            if band.quality not in [CalibrationQuality.INSUFFICIENT, CalibrationQuality.LOW]:
                return False, (
                    f"Historical win rate ({band.win_rate:.0%}) below threshold "
                    f"({self.config['min_win_rate_threshold']:.0%})"
                )

        # Check average P&L
        if band.avg_pnl_pct < self.config['min_avg_pnl_threshold']:
            if band.quality not in [CalibrationQuality.INSUFFICIENT, CalibrationQuality.LOW]:
                return False, (
                    f"Historical avg P&L ({band.avg_pnl_pct:+.2f}%) below threshold "
                    f"({self.config['min_avg_pnl_threshold']:+.2f}%)"
                )

        # Check Sharpe ratio
        if band.sharpe_ratio < self.config['min_sharpe_threshold']:
            if band.quality in [CalibrationQuality.EXCELLENT, CalibrationQuality.GOOD]:
                return False, (
                    f"Historical Sharpe ratio ({band.sharpe_ratio:.2f}) below threshold "
                    f"({self.config['min_sharpe_threshold']:.2f})"
                )

        # Check direction-specific performance
        dir_stats = report.direction_breakdown.get(direction, {})
        if dir_stats.get('total_trades', 0) >= 10:
            if dir_stats.get('win_rate', 0.5) < 0.35:
                return False, f"Direction '{direction}' historically poor (WR: {dir_stats['win_rate']:.0%})"

        # Check symbol-specific performance
        sym_stats = report.symbol_breakdown.get(symbol, {})
        if sym_stats.get('total_trades', 0) >= 10:
            if sym_stats.get('win_rate', 0.5) < 0.35:
                return False, f"Symbol '{symbol}' historically poor (WR: {sym_stats['win_rate']:.0%})"

        return True, "Passed all calibration checks"

    def _is_cache_valid(self) -> bool:
        """Check if cached calibration is still valid"""
        if not self._calibration_cache or not self._cache_timestamp:
            return False

        age = datetime.utcnow() - self._cache_timestamp
        return age.total_seconds() < (self._cache_ttl_minutes * 60)

    def _generate_empty_report(self, days: int) -> CalibrationReport:
        """Genera report vuoto quando non ci sono dati"""
        return CalibrationReport(
            generated_at=datetime.utcnow(),
            period_days=days,
            total_trades_analyzed=0,
            bands=[],
            optimal_threshold=0.5,
            optimal_band=None,
            model_breakdown={},
            direction_breakdown={},
            symbol_breakdown={},
            recommendations=["No historical data - using default thresholds"],
            warnings=["⚠️ No trades to calibrate - all confidence levels treated equally"]
        )


# Singleton instance
_calibrator: Optional[ConfidenceCalibrator] = None


def get_confidence_calibrator(config: Optional[Dict] = None) -> ConfidenceCalibrator:
    """
    Restituisce l'istanza singleton del ConfidenceCalibrator.

    Args:
        config: Configurazione opzionale (usata solo alla prima chiamata)

    Returns:
        ConfidenceCalibrator instance
    """
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator(config)
    return _calibrator


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )

    calibrator = get_confidence_calibrator()

    # Generate report
    print("\n" + "="*60)
    print("CALIBRATION REPORT TEST")
    print("="*60)

    report = calibrator.generate_calibration_report(days=30)

    print(f"\nPeriod: {report.period_days} days")
    print(f"Total trades: {report.total_trades_analyzed}")
    print(f"Optimal threshold: {report.optimal_threshold:.0%}")

    print("\n📊 Confidence Bands:")
    for band in report.bands:
        print(f"  {band}")

    print("\n💡 Recommendations:")
    for rec in report.recommendations:
        print(f"  {rec}")

    print("\n⚠️ Warnings:")
    for warn in report.warnings:
        print(f"  {warn}")

    # Test evaluation
    print("\n" + "="*60)
    print("DECISION EVALUATION TEST")
    print("="*60)

    test_decisions = [
        {"confidence": 0.75, "direction": "long", "symbol": "BTC"},
        {"confidence": 0.45, "direction": "short", "symbol": "ETH"},
        {"confidence": 0.85, "direction": "long", "symbol": "SOL"},
    ]

    for dec in test_decisions:
        result = calibrator.evaluate_decision(dec)
        print(f"\nDecision: {dec}")
        print(f"  {result}")
