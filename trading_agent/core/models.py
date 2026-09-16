"""Data models for market entities, signals, orders, portfolios, and backtest results."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketType(str, Enum):
    STOCK = "STOCK"
    CRYPTO = "CRYPTO"
    ETF = "ETF"
    FOREX = "FOREX"


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class MarketSignal(BaseModel):
    symbol: str
    action: Action
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    price: float
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    indicators: Dict[str, Any] = Field(default_factory=dict)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class Order(BaseModel):
    id: str
    symbol: str
    action: Action
    order_type: OrderType = OrderType.MARKET
    quantity: float
    price: float
    filled_price: Optional[float] = None
    fee: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Position(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100


class Portfolio(BaseModel):
    cash: float
    starting_cash: float
    positions: Dict[str, Position] = Field(default_factory=dict)
    closed_trades: List[Dict[str, Any]] = Field(default_factory=list)
    peak_equity: float = 0.0
    max_drawdown_pct: float = 0.0

    @property
    def total_equity(self) -> float:
        pos_val = sum(pos.market_value for pos in self.positions.values())
        return self.cash + pos_val

    @property
    def total_pnl(self) -> float:
        return self.total_equity - self.starting_cash

    @property
    def total_pnl_pct(self) -> float:
        if self.starting_cash == 0:
            return 0.0
        return (self.total_pnl / self.starting_cash) * 100


class BacktestResult(BaseModel):
    symbol: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    profit_factor: float = 0.0
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)