"""
Trading Configuration
Timeframe and trading mode configuration (NOF1.ai)
"""

import os
from typing import Dict, Any

# ============================================================
# TIMEFRAME CONFIGURATION
# ============================================================

# Scalping mode DISABLED by default (NOF1.ai) - too much noise on 5m timeframe
# Can be overridden with ALLOW_SCALPING=true in .env (not recommended)
SCALPING_MODE_ENABLED = os.getenv("ALLOW_SCALPING", "false").lower() in ("true", "1", "yes")

# Primary timeframe for analysis (was 5m in scalping mode)
PRIMARY_TIMEFRAME = os.getenv("PRIMARY_TIMEFRAME", "15m")  # Options: "15m", "1h", "4h"

# Secondary timeframe for trend context
SECONDARY_TIMEFRAME = os.getenv("SECONDARY_TIMEFRAME", "4h")  # Options: "1h", "4h", "1d"

# Minimum interval between trading cycles (in minutes)
# 15m timeframe → cycle every 15-30 minutes
# 1h timeframe → cycle every 30-60 minutes
CYCLE_INTERVAL_MINUTES = int(os.getenv("CYCLE_INTERVAL_MINUTES", "30"))

# Timeframe-specific settings
TIMEFRAME_CONFIG = {
    "5m": {  # DISABLED - Scalping
        "enabled": False,
        "cycle_interval": 5,
        "min_atr_threshold": 0.001,
        "max_leverage": 5,
        "description": "Scalping - DISABLED due to noise"
    },
    "15m": {  # DEFAULT - Intraday
        "enabled": True,
        "cycle_interval": 15,
        "min_atr_threshold": 0.002,
        "max_leverage": 6,
        "description": "Intraday trading - Recommended"
    },
    "1h": {  # Swing trading
        "enabled": True,
        "cycle_interval": 30,
        "min_atr_threshold": 0.003,
        "max_leverage": 8,
        "description": "Swing trading - Lower frequency"
    },
    "4h": {  # Position trading
        "enabled": True,
        "cycle_interval": 60,
        "min_atr_threshold": 0.005,
        "max_leverage": 10,
        "description": "Position trading - Long term"
    }
}


def get_timeframe_config(timeframe: str = None) -> Dict[str, Any]:
    """
    Get configuration for specified or primary timeframe.

    Args:
        timeframe: Timeframe string (e.g., "15m", "1h", "4h")

    Returns:
        Configuration dict for the timeframe
    """
    tf = timeframe or PRIMARY_TIMEFRAME
    return TIMEFRAME_CONFIG.get(tf, TIMEFRAME_CONFIG["15m"])


def validate_timeframe(timeframe: str) -> bool:
    """
    Check if timeframe is valid and enabled.

    Args:
        timeframe: Timeframe string

    Returns:
        True if valid and enabled
    """
    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        return False
    return config.get("enabled", False)


# ============================================================
# RISK MANAGEMENT (NOF1.ai Standards)
# ============================================================

# Maximum risk per trade (percentage of account)
MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "3.0"))

# Minimum R:R ratio required
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", "1.5"))

# Minimum distance from liquidation price (percentage)
MIN_LIQUIDATION_DISTANCE_PCT = float(os.getenv("MIN_LIQUIDATION_DISTANCE_PCT", "15.0"))

# Maximum leverage allowed (absolute cap)
MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "8"))

# Maximum position size as percentage of balance
MAX_POSITION_SIZE_PCT = float(os.getenv("MAX_POSITION_SIZE_PCT", "30.0"))


# ============================================================
# TRADING MODE SETTINGS
# ============================================================

# Confidence-based leverage mapping
CONFIDENCE_LEVERAGE_MAP = {
    (0.00, 0.49): 0,  # Don't trade
    (0.50, 0.59): 2,  # Low conviction
    (0.60, 0.69): 4,  # Moderate conviction
    (0.70, 0.84): 6,  # High conviction
    (0.85, 1.00): 8,  # Very high conviction
}


def get_max_leverage_for_confidence(confidence: float) -> int:
    """
    Get maximum allowed leverage for given confidence level.

    Args:
        confidence: Confidence level (0.0-1.0)

    Returns:
        Maximum leverage
    """
    for (min_conf, max_conf), leverage in CONFIDENCE_LEVERAGE_MAP.items():
        if min_conf <= confidence < max_conf:
            return leverage
    return 1  # Fallback to minimum


# ============================================================
# PERFORMANCE TRACKING
# ============================================================

# Sharpe ratio calculation settings
SHARPE_LOOKBACK_DAYS = int(os.getenv("SHARPE_LOOKBACK_DAYS", "30"))
RISK_FREE_RATE_ANNUAL = float(os.getenv("RISK_FREE_RATE_ANNUAL", "0.05"))  # 5%

# Performance thresholds
MIN_SHARPE_FOR_NORMAL_TRADING = float(os.getenv("MIN_SHARPE_FOR_NORMAL_TRADING", "-0.5"))
MIN_SHARPE_FOR_AGGRESSIVE_TRADING = float(os.getenv("MIN_SHARPE_FOR_AGGRESSIVE_TRADING", "1.0"))


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of current configuration.

    Returns:
        Dict with key configuration values
    """
    return {
        "timeframe": {
            "primary": PRIMARY_TIMEFRAME,
            "secondary": SECONDARY_TIMEFRAME,
            "cycle_interval_minutes": CYCLE_INTERVAL_MINUTES,
            "scalping_enabled": SCALPING_MODE_ENABLED,
        },
        "risk_management": {
            "max_risk_per_trade_pct": MAX_RISK_PER_TRADE_PCT,
            "min_rr_ratio": MIN_RR_RATIO,
            "max_leverage": MAX_LEVERAGE,
            "max_position_size_pct": MAX_POSITION_SIZE_PCT,
        },
        "performance": {
            "sharpe_lookback_days": SHARPE_LOOKBACK_DAYS,
            "min_sharpe_normal": MIN_SHARPE_FOR_NORMAL_TRADING,
            "min_sharpe_aggressive": MIN_SHARPE_FOR_AGGRESSIVE_TRADING,
        }
    }


# Example usage
if __name__ == "__main__":
    import json

    print("📊 Trading Configuration (NOF1.ai)")
    print("=" * 50)

    config = get_config_summary()
    print(json.dumps(config, indent=2))

    print("\n🕐 Available Timeframes:")
    for tf, cfg in TIMEFRAME_CONFIG.items():
        status = "✅ ENABLED" if cfg["enabled"] else "❌ DISABLED"
        print(f"  {tf}: {status} - {cfg['description']}")

    print("\n⚖️ Confidence-based Leverage:")
    for (min_c, max_c), lev in CONFIDENCE_LEVERAGE_MAP.items():
        if lev == 0:
            print(f"  {min_c:.2f}-{max_c:.2f}: Don't trade (HOLD)")
        else:
            print(f"  {min_c:.2f}-{max_c:.2f}: Max {lev}x leverage")
