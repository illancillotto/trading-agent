"""
Test Data Export & Analytics
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_export_presets():
    """Test get export presets"""
    print("\n=== Test 1: Get Export Presets ===")
    response = requests.get(f"{BASE_URL}/api/export/presets")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Available presets: {len(data['presets'])}")
        for preset in data['presets']:
            print(f"  - {preset['key']}: {preset['label']}")


def test_export_7d_json():
    """Test export last 7 days (JSON)"""
    print("\n=== Test 2: Export Last 7 Days (JSON) ===")
    response = requests.get(
        f"{BASE_URL}/api/export/full",
        params={'period': '7d', 'include_metrics': True}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Trades: {data['summary']['total_trades']}")
        print(f"Decisions: {data['summary']['total_decisions']}")
        if 'analytics' in data:
            metrics = data['analytics']['performance_metrics']
            print(f"Win Rate: {metrics['win_rate']:.2%}")
            print(f"Total P&L: ${metrics['total_pnl_usd']:.2f}")
            print(f"Sharpe Ratio: {metrics['sharpe_ratio']}")


def test_export_30d_csv():
    """Test export last 30 days (CSV)"""
    print("\n=== Test 3: Export Last 30 Days (CSV) ===")
    response = requests.get(
        f"{BASE_URL}/api/export/full",
        params={'period': '30d', 'format': 'csv'}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        csv_data = response.text
        lines = csv_data.split('\n')
        print(f"CSV Lines: {len(lines)}")
        print(f"First 3 lines:")
        for line in lines[:3]:
            print(f"  {line}")


def test_backtest_export():
    """Test backtest format export"""
    print("\n=== Test 4: Backtest Format Export ===")
    response = requests.get(
        f"{BASE_URL}/api/export/backtest",
        params={'days': 30}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Decisions: {data['stats']['total_decisions']}")
        print(f"Trades: {data['stats']['total_trades']}")
        print(f"Execution Rate: {data['stats']['execution_rate']:.2%}")
        print(f"Correlation entries: {len(data['correlation'])}")


def test_performance_analytics():
    """Test performance analytics"""
    print("\n=== Test 5: Performance Analytics ===")
    response = requests.get(
        f"{BASE_URL}/api/analytics/performance",
        params={'days': 30}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        metrics = data['metrics']
        print(f"\nPerformance Metrics (30 days):")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        print(f"  Total P&L: ${metrics['total_pnl_usd']:.2f}")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']}")
        print(f"  Sortino Ratio: {metrics['sortino_ratio']}")
        print(f"  Max Drawdown: ${metrics['max_drawdown_usd']:.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        print(f"  Calmar Ratio: {metrics['calmar_ratio']:.2f}")

        print(f"\nEquity Curve Points: {len(data['equity_curve'])}")
        print(f"Symbols Traded: {len(data['breakdown_by_symbol'])}")


def test_performance_btc_only():
    """Test performance analytics for BTC only"""
    print("\n=== Test 6: Performance Analytics (BTC Only) ===")
    response = requests.get(
        f"{BASE_URL}/api/analytics/performance",
        params={'days': 30, 'symbol': 'BTC'}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        metrics = data['metrics']
        print(f"\nBTC Performance (30 days):")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        print(f"  Total P&L: ${metrics['total_pnl_usd']:.2f}")


if __name__ == "__main__":
    print("=" * 60)
    print("DATA EXPORT & ANALYTICS - Test Suite")
    print("=" * 60)

    try:
        test_export_presets()
        test_export_7d_json()
        test_export_30d_csv()
        test_backtest_export()
        test_performance_analytics()
        test_performance_btc_only()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
