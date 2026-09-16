"""Tests for application settings and configuration management."""

from trading_agent.core.config import AppSettings, load_settings, save_settings


def test_app_settings_defaults():
    s = AppSettings()
    assert not s.auto_trading_enabled
    assert s.risk_per_trade_pct == 1.0
    assert s.max_portfolio_drawdown_pct == 15.0
    assert "AAPL" in s.watchlist
    assert s.default_strategy == "composite"


def test_save_and_load_settings(tmp_path):
    path = tmp_path / "custom_settings.json"
    s = AppSettings(
        auto_trading_enabled=True,
        risk_per_trade_pct=2.0,
        watchlist=["BTC-USD", "SOL-USD"],
    )
    save_settings(s, path)

    loaded = load_settings(path)
    assert loaded.auto_trading_enabled is True
    assert loaded.risk_per_trade_pct == 2.0
    assert loaded.watchlist == ["BTC-USD", "SOL-USD"]