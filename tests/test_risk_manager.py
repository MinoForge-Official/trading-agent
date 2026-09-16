"""Tests for risk management and position sizing."""

import pytest
from trading_agent.core.models import Action, MarketSignal, Portfolio, Position
from trading_agent.risk.manager import RiskManager


def test_killswitch_drawdown():
    rm = RiskManager(max_portfolio_drawdown_pct=15.0)
    p = Portfolio(cash=8000, starting_cash=10000, max_drawdown_pct=16.0)
    sig = MarketSignal(symbol="AAPL", action=Action.BUY, price=150.0)

    approved, reason, qty = rm.validate_order(sig, p)
    assert not approved
    assert "KILL-SWITCH ACTIVE" in reason
    assert qty == 0.0


def test_position_sizing_calculation():
    rm = RiskManager(risk_per_trade_pct=1.0, max_position_size_pct=20.0)
    p = Portfolio(cash=10000, starting_cash=10000)
    # Stop loss distance = $5 (Price 100, SL 95). Risk budget = 1% of 10000 = $100.
    # Qty = 100 / 5 = 20 units.
    sig = MarketSignal(symbol="XYZ", action=Action.BUY, price=100.0, stop_loss=95.0, take_profit=115.0)

    approved, reason, qty = rm.validate_order(sig, p)
    assert approved
    assert qty == 20.0


def test_risk_reward_filtering():
    rm = RiskManager(min_risk_reward_ratio=2.0)
    p = Portfolio(cash=10000, starting_cash=10000)
    # Risk = 10 (100 - 90), Reward = 10 (110 - 100) -> R:R = 1.0 (< 2.0)
    sig = MarketSignal(symbol="XYZ", action=Action.BUY, price=100.0, stop_loss=90.0, take_profit=110.0)

    approved, reason, qty = rm.validate_order(sig, p)
    assert not approved
    assert "Risk/Reward ratio" in reason