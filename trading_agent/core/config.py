"""Application settings and safety configuration management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """User-configurable settings, safety barriers, and autonomous execution rules."""

    # Autonomous Trading Controls
    auto_trading_enabled: bool = Field(
        default=False,
        description="When enabled, the agent automatically executes approved buy/sell orders.",
    )
    min_confidence_to_trade: float = Field(
        default=0.70,
        ge=0.50,
        le=1.0,
        description="Minimum strategy confidence required before an auto-trade is triggered.",
    )

    # Safety Barriers & Risk Limits
    risk_per_trade_pct: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Maximum percent of total portfolio equity risked on a single trade.",
    )
    max_position_size_pct: float = Field(
        default=20.0,
        ge=1.0,
        le=50.0,
        description="Maximum portfolio allocation permitted in any single asset.",
    )
    max_portfolio_drawdown_pct: float = Field(
        default=15.0,
        ge=5.0,
        le=50.0,
        description="Circuit Breaker: halts all new buy orders if account drops by this % from peak.",
    )
    min_risk_reward_ratio: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="Minimum potential reward vs risk required to enter a trade.",
    )
    default_stop_loss_pct: float = Field(
        default=3.0,
        ge=0.5,
        le=15.0,
        description="Default stop loss percentage if no technical ATR stop is available.",
    )

    # Watchlist & Strategy Configuration
    watchlist: List[str] = Field(
        default=["AAPL", "MSFT", "NVDA", "TSLA", "BTC-USD", "ETH-USD"],
        description="List of stock or crypto ticker symbols to monitor.",
    )
    default_strategy: str = Field(
        default="composite",
        description="Default strategy to run (composite, ema, rsi, bb, ai).",
    )
    scan_interval_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Auto-scan frequency in minutes when auto-pilot is running.",
    )

    # Integrations
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Optional Gemini API key for deep AI market thesis reasoning.",
    )
    trading_mode: str = Field(
        default="paper",
        description="Trading execution mode: 'paper' or 'live'.",
    )
    trading_website: str = Field(
        default="binance",
        description="Connected exchange or broker platform.",
    )

    model_config = {"extra": "allow"}


def get_default_config_path() -> Path:
    return Path("settings.json")


def load_settings(config_path: Optional[str | Path] = None) -> AppSettings:
    path = Path(config_path) if config_path else get_default_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AppSettings.model_validate(data)
        except Exception:
            pass
    settings = AppSettings()
    save_settings(settings, path)
    return settings


def save_settings(settings: AppSettings, config_path: Optional[str | Path] = None) -> None:
    path = Path(config_path) if config_path else get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(settings.model_dump_json(indent=2))