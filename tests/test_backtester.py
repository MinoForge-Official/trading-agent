"""Tests for backtesting engine."""

import pytest
from trading_agent.core.market_data import MarketDataProvider
from trading_agent.engine.backtester import Backtester
from trading_agent.strategies.technical import EMATrendStrategy


def test_backtester_execution():
    provider = MarketDataProvider(cache_enabled=False)
    df = provider.generate_synthetic_data(symbol="TEST", days=180, seed=42)
    df = provider.compute_indicators(df)

    strat = EMATrendStrategy(fast_period=5, slow_period=15, trend_period=30)
    bt = Backtester(initial_cash=10000.0)
    result = bt.run("TEST", df, strat)

    assert result.symbol == "TEST"
    assert result.initial_cash == 10000.0
    assert result.final_equity > 0
    assert result.total_return_pct is not None
    assert result.max_drawdown_pct >= 0.0
    assert len(result.equity_curve) > 0