"""Tests for market data provider and indicator calculations."""

import pytest
import pandas as pd
from trading_agent.core.market_data import MarketDataProvider


def test_synthetic_data_generation():
    provider = MarketDataProvider(cache_enabled=False)
    df = provider.generate_synthetic_data(symbol="TEST", days=100, seed=42)
    
    assert len(df) == 100
    assert "Open" in df.columns
    assert "High" in df.columns
    assert "Low" in df.columns
    assert "Close" in df.columns
    assert "Volume" in df.columns
    assert (df["High"] >= df["Low"]).all()


def test_indicator_computation():
    provider = MarketDataProvider(cache_enabled=False)
    df = provider.generate_synthetic_data(symbol="TEST", days=220, seed=42)
    df = provider.compute_indicators(df)

    # Check moving averages and indicators
    assert "SMA_20" in df.columns
    assert "EMA_12" in df.columns
    assert "MACD" in df.columns
    assert "MACD_Hist" in df.columns
    assert "RSI" in df.columns
    assert "BB_Upper" in df.columns
    assert "BB_Lower" in df.columns
    assert "ATR" in df.columns

    # RSI should stay bounded within [0, 100]
    valid_rsi = df["RSI"].dropna()
    assert (valid_rsi >= 0).all()
    assert (valid_rsi <= 100).all()