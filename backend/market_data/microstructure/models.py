"""
Models per Market Microstructure.
RIUSA i modelli da base_provider e coinglass.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# Importa modelli esistenti
from ..exchanges.base_provider import OrderBookSnapshot, OrderBookLevel
from ..exchanges.coinglass import LiquidationData, LiquidationRisk


class MarketBias(Enum):
    """Bias di mercato derivato dalla microstructure"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class WhaleWall:
    """Whale wall identificato nell'order book"""
    price: float
    size_usd: float
    pct_from_price: float
    exchange: str
    side: str  # 'bid' or 'ask'
    strength: str  # 'strong', 'moderate', 'weak'

    def to_dict(self) -> Dict:
        return {
            'price': self.price,
            'size_usd': self.size_usd,
            'pct_from_price': self.pct_from_price,
            'exchange': self.exchange,
            'side': self.side,
            'strength': self.strength
        }


@dataclass
class AggregatedOrderBook:
    """Order book aggregato da multiple exchange"""
    symbol: str
    timestamp: str
    exchanges_included: List[str]
    coverage_pct: float  # Stima copertura mercato

    best_bid: float
    best_ask: float
    spread_pct: float
    mid_price: float

    total_bid_depth_usd: float
    total_ask_depth_usd: float
    imbalance: float
    imbalance_interpretation: str  # 'bullish', 'bearish', 'neutral'

    whale_bids: List[WhaleWall] = field(default_factory=list)
    whale_asks: List[WhaleWall] = field(default_factory=list)

    exchange_snapshots: Dict[str, OrderBookSnapshot] = field(default_factory=dict)
    liquidity_score: float = 0.0  # 0-100

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'exchanges_included': self.exchanges_included,
            'coverage_pct': self.coverage_pct,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'spread_pct': self.spread_pct,
            'mid_price': self.mid_price,
            'total_bid_depth_usd': self.total_bid_depth_usd,
            'total_ask_depth_usd': self.total_ask_depth_usd,
            'imbalance': self.imbalance,
            'imbalance_interpretation': self.imbalance_interpretation,
            'whale_bids': [w.to_dict() for w in self.whale_bids],
            'whale_asks': [w.to_dict() for w in self.whale_asks],
            'liquidity_score': self.liquidity_score
        }


@dataclass
class MarketMicrostructureContext:
    """Contesto completo di market microstructure per una coin"""
    symbol: str
    timestamp: str
    current_price: float

    # Componenti (riusano modelli esistenti)
    order_book: Optional[AggregatedOrderBook] = None
    liquidations: Optional[LiquidationData] = None
    funding: Optional[Dict[str, Any]] = None
    open_interest: Optional[Dict[str, Any]] = None
    long_short_ratio: Optional[Dict[str, Any]] = None

    # Sintesi
    overall_bias: MarketBias = MarketBias.NEUTRAL
    bias_confidence: float = 0.5
    bias_reasons: List[str] = field(default_factory=list)

    # Warnings e raccomandazioni
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Supporti/Resistenze derivati
    key_support_levels: List[float] = field(default_factory=list)
    key_resistance_levels: List[float] = field(default_factory=list)

    # Suggerimenti SL/TP
    suggested_sl_long: Optional[float] = None
    suggested_tp_long: Optional[float] = None
    suggested_sl_short: Optional[float] = None
    suggested_tp_short: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'current_price': self.current_price,
            'order_book': self.order_book.to_dict() if self.order_book else None,
            'liquidations': self.liquidations.to_dict() if self.liquidations else None,
            'funding': self.funding,
            'open_interest': self.open_interest,
            'long_short_ratio': self.long_short_ratio,
            'overall_bias': self.overall_bias.value,
            'bias_confidence': self.bias_confidence,
            'bias_reasons': self.bias_reasons,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'key_support_levels': self.key_support_levels,
            'key_resistance_levels': self.key_resistance_levels,
            'suggested_sl_long': self.suggested_sl_long,
            'suggested_tp_long': self.suggested_tp_long,
            'suggested_sl_short': self.suggested_sl_short,
            'suggested_tp_short': self.suggested_tp_short
        }

    def to_prompt_context(self) -> str:
        """Genera il contesto formattato per il prompt LLM"""
        lines = [f"<market_microstructure symbol=\"{self.symbol}\">"]

        # Order Book Summary
        if self.order_book:
            ob = self.order_book
            lines.append("<order_book>")
            lines.append(f"  Exchanges: {', '.join(ob.exchanges_included)} ({ob.coverage_pct:.0f}% coverage)")
            lines.append(f"  Spread: {ob.spread_pct:.3f}%")
            lines.append(f"  Depth: Bid ${ob.total_bid_depth_usd/1e6:.1f}M | Ask ${ob.total_ask_depth_usd/1e6:.1f}M")
            lines.append(f"  Imbalance: {ob.imbalance:.2f} ({ob.imbalance_interpretation})")
            lines.append(f"  Liquidity Score: {ob.liquidity_score:.0f}/100")

            if ob.whale_bids:
                lines.append("  Whale Bids (Support):")
                for w in ob.whale_bids[:3]:
                    lines.append(f"    • ${w.price:,.0f} ({w.pct_from_price:+.1f}%): ${w.size_usd/1e6:.1f}M [{w.exchange}]")

            if ob.whale_asks:
                lines.append("  Whale Asks (Resistance):")
                for w in ob.whale_asks[:3]:
                    lines.append(f"    • ${w.price:,.0f} ({w.pct_from_price:+.1f}%): ${w.size_usd/1e6:.1f}M [{w.exchange}]")

            lines.append("</order_book>")

        # Liquidations Summary
        if self.liquidations:
            liq = self.liquidations
            lines.append("<liquidations>")
            lines.append(f"  24h Total: ${liq.total_24h_usd/1e6:.1f}M (Long: {liq.long_ratio:.0%}, Short: {1-liq.long_ratio:.0%})")
            lines.append(f"  Cascade Risk: {liq.cascade_risk.value.upper()}")
            if liq.cascade_risk_reason:
                lines.append(f"  Reason: {liq.cascade_risk_reason}")
            lines.append("</liquidations>")

        # Funding
        if self.funding:
            lines.append("<funding>")
            lines.append(f"  Rate: {self.funding.get('average_rate', 0):.4%} ({self.funding.get('sentiment', 'neutral')})")
            if self.funding.get('extreme'):
                lines.append("  ⚠️ EXTREME FUNDING - potential reversal signal")
            lines.append("</funding>")

        # Open Interest
        if self.open_interest:
            lines.append("<open_interest>")
            lines.append(f"  Total: ${self.open_interest.get('total_oi_usd', 0)/1e9:.2f}B")
            lines.append("</open_interest>")

        # Long/Short Ratio
        if self.long_short_ratio:
            ls = self.long_short_ratio
            lines.append("<long_short_ratio>")
            lines.append(f"  Long Ratio: {ls.get('average_long_ratio', 0.5):.0%} ({ls.get('sentiment', 'balanced')})")
            lines.append("</long_short_ratio>")

        # Summary
        lines.append("<microstructure_summary>")
        lines.append(f"  BIAS: {self.overall_bias.value.upper()} (confidence: {self.bias_confidence:.0%})")
        lines.append(f"  Reasons: {'; '.join(self.bias_reasons)}")

        if self.key_support_levels:
            lines.append(f"  Key Supports: {', '.join(f'${p:,.0f}' for p in self.key_support_levels[:3])}")
        if self.key_resistance_levels:
            lines.append(f"  Key Resistances: {', '.join(f'${p:,.0f}' for p in self.key_resistance_levels[:3])}")

        if self.suggested_sl_long and self.suggested_tp_long:
            lines.append(f"  Suggested LONG: SL ${self.suggested_sl_long:,.0f} | TP ${self.suggested_tp_long:,.0f}")
        if self.suggested_sl_short and self.suggested_tp_short:
            lines.append(f"  Suggested SHORT: SL ${self.suggested_sl_short:,.0f} | TP ${self.suggested_tp_short:,.0f}")

        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")

        lines.append("</microstructure_summary>")
        lines.append("</market_microstructure>")

        return "\n".join(lines)
