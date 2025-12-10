from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class OrderBookLevel:
    """Singolo livello dell'order book"""
    price: float
    size: float
    size_usd: float


@dataclass
class OrderBookSnapshot:
    """Snapshot dell'order book da un exchange"""
    exchange: str
    symbol: str
    timestamp: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    best_bid: float
    best_ask: float
    spread_pct: float
    mid_price: float
    bid_depth_usd: float  # Depth entro 2% dal mid price
    ask_depth_usd: float
    imbalance: float  # bid_depth / ask_depth

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'spread_pct': self.spread_pct,
            'mid_price': self.mid_price,
            'bid_depth_usd': self.bid_depth_usd,
            'ask_depth_usd': self.ask_depth_usd,
            'imbalance': self.imbalance,
            'bids_count': len(self.bids),
            'asks_count': len(self.asks)
        }


class BaseProvider(ABC):
    """
    Interfaccia base per tutti i provider di dati di mercato.
    Ogni nuovo exchange deve ereditare da questa classe.
    """

    @abstractmethod
    def check_availability(self) -> bool:
        """
        Verifica se il provider è configurato correttamente e raggiungibile.
        Returns:
            bool: True se disponibile, False altrimenti.
        """
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Ottiene i dati di mercato standardizzati per un simbolo.

        Args:
            symbol: Simbolo (es. 'BTC', 'ETH')

        Returns:
            Dict con chiavi standard:
            - price (float)
            - volume_24h (float)
            - funding_rate (float, opzionale)
            - open_interest (float, opzionale)
            - source (str)
        """
        pass

    # ===== NUOVI METODI PER MICROSTRUCTURE =====

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 50
    ) -> Optional[OrderBookSnapshot]:
        """
        Ottiene l'order book per un simbolo.
        Default: restituisce None (provider non supporta order book).
        Override nei provider che lo supportano.

        Args:
            symbol: Simbolo base (es. 'BTC')
            depth: Numero di livelli da richiedere

        Returns:
            OrderBookSnapshot o None se non supportato
        """
        return None

    async def get_funding_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene funding rate dettagliato.
        Default: estrae da get_market_data() se disponibile.
        """
        data = await self.get_market_data(symbol)
        if data and 'funding_rate' in data and data['funding_rate'] is not None:
            return {
                'symbol': symbol,
                'funding_rate': data['funding_rate'],
                'source': data.get('source', 'unknown')
            }
        return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Ottiene open interest.
        Default: estrae da get_market_data() se disponibile.
        """
        data = await self.get_market_data(symbol)
        if data and 'open_interest' in data and data['open_interest'] is not None:
            return {
                'symbol': symbol,
                'open_interest': data['open_interest'],
                'source': data.get('source', 'unknown')
            }
        return None

    def _calculate_order_book_metrics(
        self,
        bids: List[OrderBookLevel],
        asks: List[OrderBookLevel],
        exchange_name: str,
        symbol: str
    ) -> Optional[OrderBookSnapshot]:
        """
        Helper per calcolare metriche order book.
        Usato dai provider che implementano get_order_book().
        """
        if not bids or not asks:
            return None

        best_bid = bids[0].price
        best_ask = asks[0].price
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0

        # Calcola depth entro 2% dal mid price
        bid_depth = sum(
            b.size_usd for b in bids
            if b.price >= mid_price * 0.98
        )
        ask_depth = sum(
            a.size_usd for a in asks
            if a.price <= mid_price * 1.02
        )

        imbalance = bid_depth / ask_depth if ask_depth > 0 else 1.0

        return OrderBookSnapshot(
            exchange=exchange_name,
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread_pct=spread_pct,
            mid_price=mid_price,
            bid_depth_usd=bid_depth,
            ask_depth_usd=ask_depth,
            imbalance=imbalance
        )

