"""Tests for paper trading portfolio."""

import pytest
import os
from trading_agent.core.models import Action, MarketSignal
from trading_agent.engine.paper_trader import PaperTrader


def test_paper_trader_flow(tmp_path):
    storage = str(tmp_path / "test_portfolio.json")
    trader = PaperTrader(storage_file=storage, initial_cash=10000.0)

    assert trader.portfolio.cash == 10000.0
    assert len(trader.portfolio.positions) == 0

    # Execute Buy
    sig = MarketSignal(symbol="AAPL", action=Action.BUY, price=150.0, stop_loss=140.0, take_profit=175.0)
    order = trader.process_signal(sig)

    assert order is not None
    assert order.symbol == "AAPL"
    assert "AAPL" in trader.portfolio.positions
    assert trader.portfolio.cash < 10000.0

    # Execute Sell
    sell_sig = MarketSignal(symbol="AAPL", action=Action.SELL, price=160.0)
    sell_order = trader.process_signal(sell_sig)

    assert sell_order is not None
    assert "AAPL" not in trader.portfolio.positions
    assert len(trader.portfolio.closed_trades) == 1
    assert trader.portfolio.closed_trades[0]["pnl"] > 0