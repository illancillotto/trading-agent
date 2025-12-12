"""
Tests for NOF1.ai integration
Validates trade decision rules, performance metrics, and validation logic
"""
import pytest
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_agent import validate_trade_decision, TRADE_DECISION_SCHEMA, _get_max_leverage_for_confidence
from performance_metrics import PerformanceCalculator, PerformanceMetrics


class TestTradeDecisionValidation:
    """Test trade decision validation against NOF1.ai rules"""

    def test_valid_decision(self):
        """Valid decision should pass validation"""
        decision = {
            "operation": "open",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.15,
            "leverage": 3,
            "stop_loss_pct": 2.5,
            "take_profit_pct": 5.0,  # 2x R:R
            "invalidation_condition": "BTC breaks below $95,000 support level",
            "confidence": 0.65,
            "risk_usd": 25.0,
            "reason": "Strong bullish momentum with MACD crossover and volume confirmation"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert is_valid, f"Should be valid but got: {error}"

    def test_rr_ratio_too_low(self):
        """Should reject if R:R ratio < 1.5"""
        decision = {
            "operation": "open",
            "symbol": "ETH",
            "direction": "long",
            "target_portion_of_balance": 0.10,
            "leverage": 2,
            "stop_loss_pct": 3.0,
            "take_profit_pct": 3.5,  # Only 1.17x R:R
            "invalidation_condition": "ETH breaks below EMA50",
            "confidence": 0.6,
            "risk_usd": 20.0,
            "reason": "Testing R:R validation"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "R:R ratio" in error

    def test_missing_invalidation_condition(self):
        """Should reject if invalidation_condition is missing or too short"""
        decision = {
            "operation": "open",
            "symbol": "SOL",
            "direction": "short",
            "target_portion_of_balance": 0.15,
            "leverage": 3,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "Short",  # Too short
            "confidence": 0.7,
            "risk_usd": 15.0,
            "reason": "Testing invalidation condition validation"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "invalidation" in error.lower()

    def test_confidence_too_low_for_open(self):
        """Should reject open if confidence < 0.5"""
        decision = {
            "operation": "open",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.10,
            "leverage": 2,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "BTC drops below $90k support",
            "confidence": 0.4,  # Too low
            "risk_usd": 10.0,
            "reason": "Testing confidence threshold"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "confidence" in error.lower()

    def test_risk_exceeds_3_percent(self):
        """Should reject if risk_usd > 3% of account"""
        decision = {
            "operation": "open",
            "symbol": "ETH",
            "direction": "long",
            "target_portion_of_balance": 0.20,
            "leverage": 3,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "ETH breaks below $3000",
            "confidence": 0.7,
            "risk_usd": 50.0,  # 5% of $1000 account - too high
            "reason": "Testing risk limit"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "risk" in error.lower() or "3%" in error

    def test_leverage_too_high_for_confidence(self):
        """Should reject if leverage exceeds max for confidence level"""
        decision = {
            "operation": "open",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.15,
            "leverage": 8,  # Too high for 0.55 confidence
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "BTC breaks below $95k",
            "confidence": 0.55,  # Should only allow 2x leverage
            "risk_usd": 12.0,
            "reason": "Testing leverage validation"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "leverage" in error.lower()

    def test_position_size_exceeds_30_percent(self):
        """Should reject if position size > 30% of balance"""
        decision = {
            "operation": "open",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.35,  # 35% - too high
            "leverage": 2,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "BTC breaks below $95k",
            "confidence": 0.7,
            "risk_usd": 14.0,
            "reason": "Testing position size limit"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        assert not is_valid
        assert "30%" in error or "position size" in error.lower()

    def test_hold_decision_always_valid(self):
        """Hold decisions should generally be valid"""
        decision = {
            "operation": "hold",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.0,
            "leverage": 1,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "invalidation_condition": "N/A - holding position",
            "confidence": 0.3,  # Low confidence is OK for hold
            "risk_usd": 0.0,
            "reason": "Market conditions unclear, waiting for better setup"
        }
        is_valid, error = validate_trade_decision(decision, account_balance=1000)
        # Hold with low confidence should be valid (only open needs confidence >= 0.5)
        assert is_valid or "confidence" not in error.lower()


class TestLeverageConfidenceMapping:
    """Test confidence-based leverage limits"""

    def test_very_low_confidence(self):
        """Confidence < 0.5 should return 1x leverage"""
        assert _get_max_leverage_for_confidence(0.3) == 1
        assert _get_max_leverage_for_confidence(0.49) == 1

    def test_low_confidence(self):
        """Confidence 0.5-0.59 should return 2x leverage"""
        assert _get_max_leverage_for_confidence(0.50) == 2
        assert _get_max_leverage_for_confidence(0.55) == 2
        assert _get_max_leverage_for_confidence(0.59) == 2

    def test_moderate_confidence(self):
        """Confidence 0.6-0.69 should return 4x leverage"""
        assert _get_max_leverage_for_confidence(0.60) == 4
        assert _get_max_leverage_for_confidence(0.65) == 4
        assert _get_max_leverage_for_confidence(0.69) == 4

    def test_high_confidence(self):
        """Confidence 0.7-0.84 should return 6x leverage"""
        assert _get_max_leverage_for_confidence(0.70) == 6
        assert _get_max_leverage_for_confidence(0.75) == 6
        assert _get_max_leverage_for_confidence(0.84) == 6

    def test_very_high_confidence(self):
        """Confidence >= 0.85 should return 8x leverage"""
        assert _get_max_leverage_for_confidence(0.85) == 8
        assert _get_max_leverage_for_confidence(0.90) == 8
        assert _get_max_leverage_for_confidence(1.00) == 8


class TestPerformanceMetrics:
    """Test Sharpe Ratio and performance calculations"""

    def test_sharpe_ratio_positive_returns(self):
        """Sharpe ratio should be positive for consistent gains"""
        calc = PerformanceCalculator()
        trades = [
            {'pnl_pct': 2.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': 1.5, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -0.5, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': 3.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': 1.0, 'closed_at': datetime.now(timezone.utc)},
        ]
        metrics = calc.calculate_metrics(trades, [], lookback_days=30)
        assert metrics.sharpe_ratio > 0
        assert metrics.win_rate == 80.0
        assert metrics.total_trades == 5
        assert metrics.profitable_trades == 4

    def test_sharpe_ratio_negative_returns(self):
        """Sharpe ratio should be negative for consistent losses"""
        calc = PerformanceCalculator()
        trades = [
            {'pnl_pct': -2.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -1.5, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': 0.5, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -3.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -1.0, 'closed_at': datetime.now(timezone.utc)},
        ]
        metrics = calc.calculate_metrics(trades, [], lookback_days=30)
        assert metrics.sharpe_ratio < 0
        assert metrics.win_rate == 20.0

    def test_consecutive_losses(self):
        """Should correctly count consecutive losses from most recent"""
        calc = PerformanceCalculator()
        trades = [
            {'pnl_pct': 2.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': 1.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -1.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -2.0, 'closed_at': datetime.now(timezone.utc)},
            {'pnl_pct': -1.5, 'closed_at': datetime.now(timezone.utc)},  # Most recent
        ]
        metrics = calc.calculate_metrics(trades, [], lookback_days=30)
        assert metrics.consecutive_losses == 3

    def test_max_drawdown(self):
        """Should calculate maximum drawdown correctly"""
        calc = PerformanceCalculator()
        # Add dummy trade to prevent early return
        dummy_trades = [{'pnl_pct': 0.0, 'closed_at': datetime.now(timezone.utc)}]
        snapshots = [
            {'balance_usd': 1000, 'timestamp': datetime.now(timezone.utc)},
            {'balance_usd': 1100, 'timestamp': datetime.now(timezone.utc)},  # Peak
            {'balance_usd': 950, 'timestamp': datetime.now(timezone.utc)},   # Drawdown
            {'balance_usd': 1050, 'timestamp': datetime.now(timezone.utc)},
        ]
        metrics = calc.calculate_metrics(dummy_trades, snapshots, lookback_days=30)
        # Max drawdown from 1100 to 950 = 13.64%
        assert metrics.max_drawdown_pct > 13.0
        assert metrics.max_drawdown_pct < 14.0

    def test_prompt_string_format(self):
        """Metrics should format correctly for prompt inclusion"""
        metrics = PerformanceMetrics(
            sharpe_ratio=1.5,
            total_return_pct=15.0,
            win_rate=65.0,
            avg_win_pct=3.0,
            avg_loss_pct=-1.5,
            max_drawdown_pct=8.0,
            consecutive_losses=1,
            total_trades=20,
            profitable_trades=13
        )
        prompt_str = metrics.to_prompt_string()
        assert "Sharpe Ratio: 1.50" in prompt_str
        assert "Win Rate: 65.0%" in prompt_str
        assert "13/20" in prompt_str
        assert "✅ GOOD" in prompt_str  # Interpretation for Sharpe 1.5

    def test_empty_trades(self):
        """Should handle empty trades gracefully"""
        calc = PerformanceCalculator()
        metrics = calc.calculate_metrics([], [], lookback_days=30)
        assert metrics.sharpe_ratio == 0.0
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0


class TestRiskCalculations:
    """Test risk calculation formulas"""

    def test_risk_calculation_formula(self):
        """Verify risk_usd calculation matches spec"""
        # Formula: risk_usd = portion * balance * (sl_pct / 100) * leverage
        portion = 0.20
        balance = 1000
        sl_pct = 2.5
        leverage = 3

        expected_risk = portion * balance * (sl_pct / 100) * leverage
        # 0.20 * 1000 * 0.025 * 3 = 15.0

        assert expected_risk == 15.0

    def test_3_percent_risk_limit(self):
        """3% risk limit should be enforced"""
        balance = 1000
        max_risk = balance * 0.03  # 30 USD

        # Valid: 25 USD risk
        decision_valid = {
            "operation": "open",
            "symbol": "BTC",
            "direction": "long",
            "target_portion_of_balance": 0.15,
            "leverage": 3,
            "stop_loss_pct": 2.5,
            "take_profit_pct": 5.0,
            "invalidation_condition": "BTC breaks below $95k",
            "confidence": 0.7,
            "risk_usd": 25.0,
            "reason": "Valid risk"
        }
        is_valid, _ = validate_trade_decision(decision_valid, balance)
        assert is_valid

        # Invalid: 40 USD risk
        decision_invalid = decision_valid.copy()
        decision_invalid["risk_usd"] = 40.0
        is_valid, error = validate_trade_decision(decision_invalid, balance)
        assert not is_valid


class TestSchemaCompliance:
    """Test JSON schema compliance"""

    def test_schema_has_required_fields(self):
        """Schema should include all NOF1.ai required fields"""
        required = TRADE_DECISION_SCHEMA["required"]
        assert "invalidation_condition" in required
        assert "risk_usd" in required
        assert "confidence" in required
        assert "stop_loss_pct" in required
        assert "take_profit_pct" in required

    def test_schema_constraints(self):
        """Schema should have correct constraints"""
        props = TRADE_DECISION_SCHEMA["properties"]

        # Leverage 1-8
        assert props["leverage"]["minimum"] == 1
        assert props["leverage"]["maximum"] == 8

        # Stop loss 1.5-5.0
        assert props["stop_loss_pct"]["minimum"] == 1.5
        assert props["stop_loss_pct"]["maximum"] == 5.0

        # Take profit >= 2.25
        assert props["take_profit_pct"]["minimum"] == 2.25

        # Position size max 0.30
        assert props["target_portion_of_balance"]["maximum"] == 0.30


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
