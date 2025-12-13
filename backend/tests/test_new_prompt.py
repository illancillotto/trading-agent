"""
Test nuovo system prompt NOF1.ai
Verifica che il prompt venga generato correttamente con tutti i componenti
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.trading_system_prompt import TradingSystemPrompt


def test_prompt_generation():
    """Test che il prompt venga generato correttamente"""

    print("=" * 80)
    print("TEST NUOVO PROMPT NOF1.AI")
    print("=" * 80)

    # Initialize prompt manager
    try:
        prompt_manager = TradingSystemPrompt()
        print("\n✅ TradingSystemPrompt inizializzato correttamente")
    except Exception as e:
        print(f"\n❌ ERRORE inizializzazione: {e}")
        return False

    # Mock data
    mock_metrics = {
        'sharpe_ratio': 1.2,
        'win_rate': 55.0,
        'avg_rr': 2.1,
        'consecutive_losses': 0,
        'total_return_pct': 8.5
    }

    mock_portfolio = """
**Account Balance**: $1,000.00
**Available Cash**: $800.00
**Total Positions Value**: $200.00

**Open Positions**:
- BTC long:
  Entry: $95,000.00
  Current: $96,000.00
  Size: 0.002 ($192.00 USD)
  P&L: $2.00 (+1.05%)
  Leverage: 2x
"""

    mock_market_15m = """
**BTC**:
- Price: $96,000.00
- EMA20: $95,500.00, EMA50: $94,800.00
- MACD: 0.0012, Signal: 0.0008
- RSI(14): 58.00
- Volume: 1,250,000
- ATR: 1,200.00
"""

    mock_market_4h = """
**BTC**:
- Price: $96,000.00
- EMA20: $95,200.00, EMA50: $93,500.00
- MACD: 0.0025, Signal: 0.0015
- RSI(14): 62.00
- Volume: 18,500,000
- ATR: 2,100.00
"""

    mock_market_daily = """
**BTC**:
- Price: $96,000.00
- EMA20: $93,500.00, EMA50: $89,200.00
- MACD: 0.0042, Signal: 0.0028
- RSI(14): 65.00
- Volume: 125,000,000
- ATR: 3,500.00
"""

    # Generate system prompt
    print("\n" + "=" * 80)
    print("SYSTEM PROMPT GENERATION")
    print("=" * 80)

    try:
        system_prompt = prompt_manager.get_system_prompt()
        print(f"\n✅ System prompt generato: {len(system_prompt):,} caratteri")
    except Exception as e:
        print(f"\n❌ ERRORE generazione system prompt: {e}")
        return False

    print("\n📝 SYSTEM PROMPT PREVIEW (prime 500 caratteri):")
    print("-" * 80)
    print(system_prompt[:500])
    print("..." if len(system_prompt) > 500 else "")
    print("-" * 80)

    # Check for key sections
    print("\n" + "=" * 80)
    print("VERIFICA SEZIONI CHIAVE")
    print("=" * 80)

    checks = [
        ("NOF1.AI TRADING PHILOSOPHY", "NOF1.AI TRADING PHILOSOPHY" in system_prompt),
        ("Common Pitfalls section", "COMMON PITFALLS" in system_prompt),
        ("Fee Impact warnings", "FEE IMPACT" in system_prompt),
        ("Operational Constraints", "OPERATIONAL CONSTRAINTS" in system_prompt),
        ("Trading Rules", "TRADING RULES (MANDATORY" in system_prompt),
        ("Decision Criteria", "Decision Criteria" in system_prompt),
        ("Indicator Analysis - EMA", "EMA (Exponential Moving Average)" in system_prompt),
        ("Indicator Analysis - MACD", "MACD (Moving Average Convergence Divergence)" in system_prompt),
        ("Indicator Analysis - RSI", "RSI (Relative Strength Index)" in system_prompt),
        ("Indicator Analysis - ATR", "ATR (Average True Range)" in system_prompt),
        ("Sentiment Analysis", "SENTIMENT ANALYSIS" in system_prompt),
        ("Market Regime Analysis", "MARKET REGIME ANALYSIS" in system_prompt),
        ("Trend Confirmation", "TREND CONFIRMATION ANALYSIS" in system_prompt),
        ("Output Format", "OUTPUT FORMAT" in system_prompt),
        ("Final Checklist", "FINAL CHECKLIST" in system_prompt),
        ("JSON timeframe_analysis", '"timeframe_analysis"' in system_prompt),
        ("JSON market_context", '"market_context"' in system_prompt),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False

    # Test user prompt generation
    print("\n" + "=" * 80)
    print("USER PROMPT GENERATION")
    print("=" * 80)

    try:
        user_prompt = prompt_manager.build_user_prompt(
            performance_metrics=mock_metrics,
            portfolio_data=mock_portfolio,
            market_data_15m=mock_market_15m,
            market_data_4h=mock_market_4h,
            market_data_daily=mock_market_daily,
            sentiment_data="Fear & Greed Index: 42 (Fear)",
            regime_analysis="**BTC**: TRENDING_UP (confidence: 75%)",
            trend_preanalysis="**BTC**: up trend, confidence 80%, quality strong, entry timing good"
        )
        print(f"\n✅ User prompt generato: {len(user_prompt):,} caratteri")
    except Exception as e:
        print(f"\n❌ ERRORE generazione user prompt: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n📝 USER PROMPT PREVIEW (prime 1000 caratteri):")
    print("-" * 80)
    print(user_prompt[:1000])
    print("..." if len(user_prompt) > 1000 else "")
    print("-" * 80)

    # Check user prompt structure
    print("\n" + "=" * 80)
    print("VERIFICA STRUTTURA USER PROMPT")
    print("=" * 80)

    user_checks = [
        ("Performance Metrics section", "YOUR PERFORMANCE METRICS" in user_prompt),
        ("Sharpe Ratio in metrics", "Sharpe Ratio" in user_prompt and "1.2" in user_prompt),
        ("Portfolio section", "CURRENT PORTFOLIO" in user_prompt),
        ("Market Data section", "MARKET DATA" in user_prompt),
        ("Data ordering warning", "OLDEST → NEWEST" in user_prompt),
        ("15-minute timeframe", "15-MINUTE TIMEFRAME" in user_prompt),
        ("4-hour timeframe", "4-HOUR TIMEFRAME" in user_prompt),
        ("Daily timeframe", "DAILY TIMEFRAME" in user_prompt),
        ("Sentiment (if provided)", "SENTIMENT" in user_prompt),
        ("Regime (if provided)", "REGIME" in user_prompt),
        ("Trend preanalysis (if provided)", "TREND" in user_prompt),
    ]

    for check_name, result in user_checks:
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False

    # Test performance metrics formatting
    print("\n" + "=" * 80)
    print("VERIFICA PERFORMANCE METRICS FORMATTING")
    print("=" * 80)

    try:
        perf_formatted = prompt_manager._format_performance_metrics(mock_metrics)
        print(f"\n✅ Performance metrics formattati: {len(perf_formatted)} caratteri")

        perf_checks = [
            ("Sharpe Ratio value", "1.2" in perf_formatted or "1.20" in perf_formatted),
            ("Win Rate value", "55.0" in perf_formatted),
            ("Avg R:R value", "2.1" in perf_formatted),
            ("Consecutive Losses", "0" in perf_formatted),
            ("Total Return", "8.5" in perf_formatted or "+8.5" in perf_formatted),
            ("Sharpe interpretation", "Good risk-adjusted returns" in perf_formatted),
            ("Action required", "Action Required" in perf_formatted or "CURRENT strategy" in perf_formatted),
        ]

        for check_name, result in perf_checks:
            status = "✅" if result else "❌"
            print(f"{status} {check_name}")
            if not result:
                all_passed = False

    except Exception as e:
        print(f"\n❌ ERRORE formattazione performance metrics: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Final summary
    print("\n" + "=" * 80)
    print("RIEPILOGO TEST")
    print("=" * 80)

    total_prompt_len = len(system_prompt) + len(user_prompt)
    print(f"\n📊 Statistiche:")
    print(f"   - System prompt:  {len(system_prompt):,} caratteri")
    print(f"   - User prompt:    {len(user_prompt):,} caratteri")
    print(f"   - Total prompt:   {total_prompt_len:,} caratteri")
    print(f"   - Checks passed:  {sum(1 for _, r in checks + user_checks + perf_checks if r)}/{len(checks) + len(user_checks) + len(perf_checks)}")

    if all_passed:
        print("\n✅ TUTTI I TEST PASSATI!")
        return True
    else:
        print("\n⚠️ ALCUNI TEST FALLITI - Controlla i dettagli sopra")
        return False


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    success = test_prompt_generation()
    sys.exit(0 if success else 1)
