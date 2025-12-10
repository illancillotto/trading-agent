"""
Microstructure Aggregator.
USA i provider esistenti - NON duplica codice.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

from .models import (
    MarketMicrostructureContext,
    AggregatedOrderBook,
    WhaleWall,
    MarketBias
)

# IMPORTA PROVIDER ESISTENTI - NON CREARE NUOVI
from ..exchanges.binance import BinanceProvider
from ..exchanges.bybit import BybitProvider
from ..exchanges.okx import OkxProvider
from ..exchanges.coinbase import CoinbaseProvider
from ..exchanges.coinglass import CoinglassProvider, LiquidationRisk
from ..exchanges.base_provider import OrderBookSnapshot, OrderBookLevel

logger = logging.getLogger(__name__)


# Market share weights per aggregazione ponderata
EXCHANGE_WEIGHTS = {
    'Binance': 0.45,
    'OKX': 0.18,
    'Bybit': 0.15,
    'Coinbase': 0.08
}

# Soglia per whale detection (USD)
WHALE_THRESHOLD_USD = 500_000


class MicrostructureAggregator:
    """
    Aggregatore di Market Microstructure.
    RIUSA i provider esistenti da exchanges/.
    """

    def __init__(self):
        # RIUSA provider esistenti
        self.providers = {
            'binance': BinanceProvider(),
            'bybit': BybitProvider(),
            'okx': OkxProvider(),
            'coinbase': CoinbaseProvider()
        }

        # Coinglass per dati aggregati liquidazioni
        self.coinglass = CoinglassProvider()

        available = [name for name, p in self.providers.items() if p.check_availability()]
        coinglass_status = "enabled" if self.coinglass.check_availability() else "disabled (no API key)"

        logger.info(
            f"🔬 MicrostructureAggregator initialized | "
            f"Order Book: {available} | Coinglass: {coinglass_status}"
        )

    async def get_full_context(
        self,
        symbol: str,
        include_orderbook: bool = True,
        include_liquidations: bool = True,
        include_funding: bool = True,
        include_oi: bool = True,
        include_ls_ratio: bool = True
    ) -> MarketMicrostructureContext:
        """
        Ottiene contesto completo di microstructure per un simbolo.

        Args:
            symbol: Simbolo base (es. 'BTC')
            include_*: Flags per includere/escludere componenti

        Returns:
            MarketMicrostructureContext completo
        """
        logger.info(f"📊 Fetching microstructure context for {symbol}...")

        # Prepara tasks
        tasks = {}

        if include_orderbook:
            tasks['orderbook'] = self._fetch_aggregated_orderbook(symbol)

        if include_liquidations and self.coinglass.check_availability():
            tasks['liquidations'] = self.coinglass.get_liquidations(symbol)

        if include_funding and self.coinglass.check_availability():
            tasks['funding'] = self.coinglass.get_aggregated_funding(symbol)

        if include_oi and self.coinglass.check_availability():
            tasks['oi'] = self.coinglass.get_aggregated_open_interest(symbol)

        if include_ls_ratio and self.coinglass.check_availability():
            tasks['ls_ratio'] = self.coinglass.get_long_short_ratio(symbol)

        # Esegui in parallelo
        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.warning(f"Failed to fetch {name}: {e}")
                results[name] = None

        # Ottieni prezzo corrente
        current_price = 0
        if results.get('orderbook'):
            current_price = results['orderbook'].mid_price
        else:
            # Fallback: usa Binance
            try:
                market_data = await self.providers['binance'].get_market_data(symbol)
                current_price = market_data.get('price', 0) if market_data else 0
            except:
                pass

        # Calcola bias complessivo
        bias, confidence, reasons = self._calculate_overall_bias(results)

        # Genera warnings e recommendations
        warnings = self._generate_warnings(results)
        recommendations = self._generate_recommendations(results, current_price)

        # Identifica livelli chiave
        supports, resistances = self._identify_key_levels(results, current_price)

        # Calcola SL/TP suggeriti
        sl_long, tp_long, sl_short, tp_short = self._calculate_suggested_levels(
            supports, resistances
        )

        context = MarketMicrostructureContext(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            current_price=current_price,
            order_book=results.get('orderbook'),
            liquidations=results.get('liquidations'),
            funding=results.get('funding'),
            open_interest=results.get('oi'),
            long_short_ratio=results.get('ls_ratio'),
            overall_bias=bias,
            bias_confidence=confidence,
            bias_reasons=reasons,
            warnings=warnings,
            recommendations=recommendations,
            key_support_levels=supports,
            key_resistance_levels=resistances,
            suggested_sl_long=sl_long,
            suggested_tp_long=tp_long,
            suggested_sl_short=sl_short,
            suggested_tp_short=tp_short
        )

        logger.info(
            f"✅ Microstructure context ready for {symbol} | "
            f"Bias: {bias.value} ({confidence:.0%}) | Warnings: {len(warnings)}"
        )

        return context

    async def _fetch_aggregated_orderbook(self, symbol: str) -> Optional[AggregatedOrderBook]:
        """Fetch e aggrega order book da tutti i provider"""
        tasks = {
            name: provider.get_order_book(symbol)
            for name, provider in self.providers.items()
        }

        snapshots = {}
        for name, task in tasks.items():
            try:
                result = await task
                if result:
                    snapshots[name] = result
            except Exception as e:
                logger.warning(f"Order book fetch failed for {name}: {e}")

        if not snapshots:
            logger.warning(f"No order book data available for {symbol}")
            return None

        return self._aggregate_orderbooks(symbol, snapshots)

    def _aggregate_orderbooks(
        self,
        symbol: str,
        snapshots: Dict[str, OrderBookSnapshot]
    ) -> AggregatedOrderBook:
        """Aggrega order book pesando per market share"""
        total_weight = sum(
            EXCHANGE_WEIGHTS.get(snap.exchange, 0.05)
            for snap in snapshots.values()
        )

        weighted_bid = 0
        weighted_ask = 0
        total_bid_depth = 0
        total_ask_depth = 0
        all_whale_bids = []
        all_whale_asks = []

        for name, snapshot in snapshots.items():
            weight = EXCHANGE_WEIGHTS.get(snapshot.exchange, 0.05)
            rel_weight = weight / total_weight if total_weight > 0 else 1

            weighted_bid += snapshot.best_bid * rel_weight
            weighted_ask += snapshot.best_ask * rel_weight

            # Stima depth totale mercato (inversamente proporzionale al weight)
            if weight > 0:
                total_bid_depth += snapshot.bid_depth_usd / weight
                total_ask_depth += snapshot.ask_depth_usd / weight

            # Detect whale walls
            current_price = snapshot.mid_price
            for level in snapshot.bids[:20]:
                if level.size_usd >= WHALE_THRESHOLD_USD:
                    pct = ((level.price - current_price) / current_price) * 100
                    strength = 'strong' if level.size_usd >= WHALE_THRESHOLD_USD * 3 else 'moderate'
                    all_whale_bids.append(WhaleWall(
                        price=level.price,
                        size_usd=level.size_usd,
                        pct_from_price=pct,
                        exchange=snapshot.exchange,
                        side='bid',
                        strength=strength
                    ))

            for level in snapshot.asks[:20]:
                if level.size_usd >= WHALE_THRESHOLD_USD:
                    pct = ((level.price - current_price) / current_price) * 100
                    strength = 'strong' if level.size_usd >= WHALE_THRESHOLD_USD * 3 else 'moderate'
                    all_whale_asks.append(WhaleWall(
                        price=level.price,
                        size_usd=level.size_usd,
                        pct_from_price=pct,
                        exchange=snapshot.exchange,
                        side='ask',
                        strength=strength
                    ))

        # Sort whale walls by size (descending)
        all_whale_bids.sort(key=lambda x: x.size_usd, reverse=True)
        all_whale_asks.sort(key=lambda x: x.size_usd, reverse=True)

        # Calcola metriche aggregate
        spread_pct = ((weighted_ask - weighted_bid) / weighted_bid * 100) if weighted_bid > 0 else 0
        mid_price = (weighted_bid + weighted_ask) / 2
        imbalance = total_bid_depth / total_ask_depth if total_ask_depth > 0 else 1

        # Interpret imbalance
        if imbalance > 1.5:
            imbalance_interp = 'strong_bullish'
        elif imbalance > 1.2:
            imbalance_interp = 'bullish'
        elif imbalance < 0.67:
            imbalance_interp = 'strong_bearish'
        elif imbalance < 0.83:
            imbalance_interp = 'bearish'
        else:
            imbalance_interp = 'neutral'

        # Coverage % del mercato
        coverage = sum(
            EXCHANGE_WEIGHTS.get(snap.exchange, 0.05) * 100
            for snap in snapshots.values()
        )

        # Liquidity score (0-100)
        avg_depth = (total_bid_depth + total_ask_depth) / 2
        if avg_depth > 100_000_000:
            liquidity_score = 100
        elif avg_depth > 50_000_000:
            liquidity_score = 80
        elif avg_depth > 20_000_000:
            liquidity_score = 60
        elif avg_depth > 5_000_000:
            liquidity_score = 40
        else:
            liquidity_score = 20

        return AggregatedOrderBook(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            exchanges_included=[s.exchange for s in snapshots.values()],
            coverage_pct=coverage,
            best_bid=weighted_bid,
            best_ask=weighted_ask,
            spread_pct=spread_pct,
            mid_price=mid_price,
            total_bid_depth_usd=total_bid_depth,
            total_ask_depth_usd=total_ask_depth,
            imbalance=imbalance,
            imbalance_interpretation=imbalance_interp,
            whale_bids=all_whale_bids[:5],
            whale_asks=all_whale_asks[:5],
            exchange_snapshots={name: snap for name, snap in snapshots.items()},
            liquidity_score=liquidity_score
        )

    def _calculate_overall_bias(
        self,
        data: Dict
    ) -> Tuple[MarketBias, float, List[str]]:
        """Calcola bias complessivo del mercato"""
        signals = []
        reasons = []

        # Order book signal
        if data.get('orderbook'):
            ob = data['orderbook']
            if ob.imbalance > 1.3:
                signals.append(1)
                reasons.append(f"Order book bullish (imbalance: {ob.imbalance:.2f})")
            elif ob.imbalance < 0.77:
                signals.append(-1)
                reasons.append(f"Order book bearish (imbalance: {ob.imbalance:.2f})")
            else:
                signals.append(0)

        # Funding signal (contrarian)
        if data.get('funding'):
            rate = data['funding'].get('average_rate', 0)
            if rate > 0.01:  # > 0.01%
                signals.append(-0.5)  # Extreme bullish funding = contrarian bearish
                reasons.append(f"Extreme positive funding ({rate:.4%}) - crowded long")
            elif rate < -0.01:
                signals.append(0.5)
                reasons.append(f"Extreme negative funding ({rate:.4%}) - crowded short")
            elif rate > 0.005:
                signals.append(-0.3)
            elif rate < -0.005:
                signals.append(0.3)

        # Liquidations signal
        if data.get('liquidations'):
            liq = data['liquidations']
            if liq.long_ratio > 0.7:
                signals.append(-0.5)  # Heavy long liquidations = potential bottom (contrarian)
                reasons.append(f"Heavy long liquidations ({liq.long_ratio:.0%}) - potential bottom")
            elif liq.long_ratio < 0.3:
                signals.append(0.5)
                reasons.append(f"Heavy short liquidations ({1-liq.long_ratio:.0%}) - potential top")

        # Long/Short ratio (contrarian)
        if data.get('ls_ratio'):
            ls = data['ls_ratio']
            ratio = ls.get('average_long_ratio', 0.5)
            if ratio > 0.65:
                signals.append(-0.3)
                reasons.append("Crowded long (retail) - contrarian bearish")
            elif ratio < 0.35:
                signals.append(0.3)
                reasons.append("Crowded short (retail) - contrarian bullish")

        # Calculate overall
        if not signals:
            return MarketBias.NEUTRAL, 0.3, ["Insufficient data"]

        avg_signal = sum(signals) / len(signals)
        confidence = min(abs(avg_signal) + 0.3, 0.9)

        if avg_signal > 0.5:
            bias = MarketBias.STRONG_BULLISH
        elif avg_signal > 0.2:
            bias = MarketBias.BULLISH
        elif avg_signal < -0.5:
            bias = MarketBias.STRONG_BEARISH
        elif avg_signal < -0.2:
            bias = MarketBias.BEARISH
        else:
            bias = MarketBias.NEUTRAL

        return bias, confidence, reasons

    def _generate_warnings(self, data: Dict) -> List[str]:
        """Genera warnings basati sui dati"""
        warnings = []

        if data.get('liquidations'):
            liq = data['liquidations']
            if liq.cascade_risk in [LiquidationRisk.HIGH, LiquidationRisk.EXTREME]:
                warnings.append(f"HIGH CASCADE RISK: {liq.cascade_risk_reason}")

        if data.get('funding'):
            if data['funding'].get('extreme'):
                warnings.append("Extreme funding rate - potential reversal signal")

        if data.get('orderbook'):
            if data['orderbook'].spread_pct > 0.1:
                warnings.append(f"Wide spread ({data['orderbook'].spread_pct:.2f}%) - low liquidity")
            if data['orderbook'].liquidity_score < 40:
                warnings.append("Low liquidity - execution risk")

        return warnings

    def _generate_recommendations(self, data: Dict, current_price: float) -> List[str]:
        """Genera raccomandazioni di trading"""
        recommendations = []

        if data.get('orderbook'):
            ob = data['orderbook']
            if ob.whale_bids:
                top_bid = ob.whale_bids[0]
                recommendations.append(
                    f"Strong support at ${top_bid.price:,.0f} ({top_bid.pct_from_price:+.1f}%) - "
                    f"${top_bid.size_usd/1e6:.1f}M whale wall [{top_bid.exchange}]"
                )
            if ob.whale_asks:
                top_ask = ob.whale_asks[0]
                recommendations.append(
                    f"Resistance at ${top_ask.price:,.0f} ({top_ask.pct_from_price:+.1f}%) - "
                    f"${top_ask.size_usd/1e6:.1f}M whale wall [{top_ask.exchange}]"
                )

        if data.get('liquidations'):
            liq = data['liquidations']
            if liq.nearest_short_cluster:
                ns = liq.nearest_short_cluster
                recommendations.append(
                    f"Short squeeze target: ${ns.price:,.0f} ({ns.pct_from_current:+.1f}%) - "
                    f"${ns.total_usd/1e6:.0f}M shorts at risk"
                )
            if liq.nearest_long_cluster:
                nl = liq.nearest_long_cluster
                recommendations.append(
                    f"Long liquidation zone: ${nl.price:,.0f} ({nl.pct_from_current:+.1f}%) - "
                    f"${nl.total_usd/1e6:.0f}M longs at risk"
                )

        return recommendations

    def _identify_key_levels(
        self,
        data: Dict,
        current_price: float
    ) -> Tuple[List[float], List[float]]:
        """Identifica supporti e resistenze chiave"""
        supports = []
        resistances = []

        # Da whale walls
        if data.get('orderbook'):
            for wall in data['orderbook'].whale_bids:
                supports.append(wall.price)
            for wall in data['orderbook'].whale_asks:
                resistances.append(wall.price)

        # Da liquidation levels (se disponibili)
        if data.get('liquidations'):
            liq = data['liquidations']
            for level in liq.liquidation_levels[:10]:
                if level.type == 'long' and level.risk in [LiquidationRisk.HIGH, LiquidationRisk.EXTREME]:
                    supports.append(level.price)
                elif level.type == 'short' and level.risk in [LiquidationRisk.HIGH, LiquidationRisk.EXTREME]:
                    resistances.append(level.price)

        # Sort e deduplica
        supports = sorted(set(s for s in supports if s < current_price), reverse=True)[:5]
        resistances = sorted(set(r for r in resistances if r > current_price))[:5]

        return supports, resistances

    def _calculate_suggested_levels(
        self,
        supports: List[float],
        resistances: List[float]
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Calcola SL/TP suggeriti basati sulla microstructure"""
        sl_long = None
        tp_long = None
        sl_short = None
        tp_short = None

        if supports and resistances:
            # Long: SL sotto primo supporto, TP al primo resistance
            sl_long = supports[0] * 0.995  # Leggermente sotto il supporto
            tp_long = resistances[0] * 0.995  # Leggermente sotto la resistenza

            # Short: SL sopra prima resistenza, TP al primo supporto
            sl_short = resistances[0] * 1.005  # Leggermente sopra la resistenza
            tp_short = supports[0] * 1.005  # Leggermente sopra il supporto

        return sl_long, tp_long, sl_short, tp_short


# Singleton pattern
_aggregator_instance: Optional[MicrostructureAggregator] = None


def get_microstructure_aggregator() -> MicrostructureAggregator:
    """Restituisce l'istanza singleton dell'aggregator"""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = MicrostructureAggregator()
    return _aggregator_instance
