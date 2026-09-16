"""Tests for GitHub reporter and markdown formatting."""

import pytest
from trading_agent.core.models import Action, BacktestResult, MarketSignal
from trading_agent.github_tool.reporter import GitHubReporter


def test_github_scan_report():
    reporter = GitHubReporter()
    signals = [
        MarketSignal(symbol="AAPL", action=Action.BUY, confidence=0.85, price=180.5, stop_loss=175.0, take_profit=195.0, reason="EMA golden cross"),
        MarketSignal(symbol="TSLA", action=Action.HOLD, confidence=0.50, price=210.0, reason="Consolidation"),
    ]
    md = reporter.format_scan_report(signals, "TestStrategy")

    assert "# Trading Agent Market Scan Report" in md
    assert "AAPL" in md
    assert "**[BUY]**" in md
    assert "TSLA" in md


def test_github_issue_payload():
    reporter = GitHubReporter()
    high_conf = [
        MarketSignal(symbol="BTC-USD", action=Action.BUY, confidence=0.90, price=65000.0, reason="Breakout above resistance")
    ]
    payload = reporter.generate_issue_payload(high_conf)
    assert payload is not None
    assert "[Alert] High-Conviction Signal for BTC-USD" in payload["title"]
    assert "BTC-USD" in payload["body"]