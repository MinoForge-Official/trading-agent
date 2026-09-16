"""Tests for trading strategies."""

import pytest
from trading_agent.core.market_data import MarketDataProvider
from trading_agent.core.models import Action
from trading_agent.strategies.technical import (
    EMATrendStrategy,
    RSIOscillatorStrategy,
    BollingerBandStrategy,
    CompositeStrategy,
)
from trading_agent.strategies.ai_agent import AIAgentStrategy


@pytest.fixture
def market_df():
    provider = MarketDataProvider(cache_enabled=False)
    df = provider.generate_synthetic_data("TEST", days=250, seed=123)
    return provider.compute_indicators(df)


def test_ema_trend_strategy(market_df):
    strat = EMATrendStrategy()
    sig = strat.evaluate("TEST", market_df)
    assert sig.action in [Action.BUY, Action.SELL, Action.HOLD]
    assert 0.0 <= sig.confidence <= 1.0
    assert sig.price > 0

    all_sigs = strat.generate_all_signals("TEST", market_df)
    assert len(all_sigs) == len(market_df)
    assert set(all_sigs.unique()).issubset({-1, 0, 1})


def test_rsi_oscillator_strategy(market_df):
    strat = RSIOscillatorStrategy()
    sig = strat.evaluate("TEST", market_df)
    assert sig.action in [Action.BUY, Action.SELL, Action.HOLD]
    assert "RSI" in sig.indicators


def test_bollinger_band_strategy(market_df):
    strat = BollingerBandStrategy()
    sig = strat.evaluate("TEST", market_df)
    assert sig.action in [Action.BUY, Action.SELL, Action.HOLD]
    assert "BB_Upper" in sig.indicators


def test_composite_strategy(market_df):
    strat = CompositeStrategy()
    sig = strat.evaluate("TEST", market_df)
    assert sig.action in [Action.BUY, Action.SELL, Action.HOLD]
    assert "composite_score" in sig.indicators


def test_ai_agent_strategy(market_df):
    strat = AIAgentStrategy()
    sig = strat.evaluate("TEST", market_df)
    assert sig.action in [Action.BUY, Action.SELL, Action.HOLD]
    assert "trend_state" in sig.indicators
    assert "[AI Agent Thesis" in sig.reason