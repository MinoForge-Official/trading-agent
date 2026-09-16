"""Abstract base strategy class for all trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd
from trading_agent.core.models import MarketSignal


class BaseStrategy(ABC):
    """Abstract base strategy."""

    def __init__(self, name: str, params: Optional[dict] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        """Evaluate the latest market data candle and return a MarketSignal."""
        pass

    @abstractmethod
    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        """Generate a pandas Series of signals (-1: SELL, 0: HOLD, 1: BUY) for backtesting."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"