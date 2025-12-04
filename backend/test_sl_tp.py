"""
Test script per verificare la funzione place_sl_tp_orders
"""
import os
from dotenv import load_dotenv
from hyperliquid_trader import HyperLiquidTrader

# Load environment
load_dotenv()

def test_sl_tp_structure():
    """Test the structure of SL/TP orders without placing them"""

    print("🧪 Testing SL/TP order structure...")
    print("=" * 60)

    # Simulazione parametri
    symbol = "BTC"
    direction = "long"
    entry_price = 45000.0
    stop_loss_pct = 2.0
    take_profit_pct = 5.0
    position_size_coin = 0.01

    # Calcola prezzi
    if direction == "long":
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        take_profit_price = entry_price * (1 + take_profit_pct / 100)
    else:
        stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
        take_profit_price = entry_price * (1 - take_profit_pct / 100)

    print(f"\n📊 Position Details:")
    print(f"   Symbol: {symbol}")
    print(f"   Direction: {direction.upper()}")
    print(f"   Entry Price: ${entry_price:,.2f}")
    print(f"   Position Size: {position_size_coin} {symbol}")
    print(f"\n🎯 Risk Management:")
    print(f"   Stop Loss: ${stop_loss_price:,.2f} ({stop_loss_pct}% below entry)")
    print(f"   Take Profit: ${take_profit_price:,.2f} ({take_profit_pct}% above entry)")

    # Mostra la struttura dell'ordine
    from hyperliquid.utils.signing import OrderRequest

    sl_order = OrderRequest(
        coin=symbol,
        is_buy=(direction == "short"),
        sz=position_size_coin,
        limit_px=stop_loss_price,
        order_type={
            "trigger": {
                "triggerPx": stop_loss_price,
                "isMarket": True,
                "tpsl": "sl"
            }
        },
        reduce_only=True
    )

    tp_order = OrderRequest(
        coin=symbol,
        is_buy=(direction == "short"),
        sz=position_size_coin,
        limit_px=take_profit_price,
        order_type={
            "trigger": {
                "triggerPx": take_profit_price,
                "isMarket": True,
                "tpsl": "tp"
            }
        },
        reduce_only=True
    )

    print(f"\n📝 Order Structures Created:")
    print(f"   SL Order: {sl_order}")
    print(f"   TP Order: {tp_order}")
    print(f"\n✅ Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    test_sl_tp_structure()
