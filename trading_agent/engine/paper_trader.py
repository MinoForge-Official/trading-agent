"""Paper trading engine with persistent portfolio state and automated execution."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from trading_agent.core.models import (
    Action,
    MarketSignal,
    Order,
    OrderStatus,
    OrderType,
    Portfolio,
    Position,
)
from trading_agent.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class PaperTrader:
    """Manages a simulated portfolio, executes orders against live/test prices, and persists state."""

    def __init__(
        self,
        storage_file: str = "portfolio_state.json",
        initial_cash: float = 10000.0,
        risk_manager: Optional[RiskManager] = None,
        fee_pct: float = 0.001,
        slippage_pct: float = 0.0005,
    ):
        self.storage_file = Path(storage_file)
        self.initial_cash = initial_cash
        self.risk_manager = risk_manager or RiskManager()
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.portfolio = self._load_or_create()

    def _load_or_create(self) -> Portfolio:
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return Portfolio.model_validate(data)
            except Exception as e:
                logger.warning(f"Could not load portfolio state from {self.storage_file}: {e}. Creating new.")

        return Portfolio(
            cash=self.initial_cash,
            starting_cash=self.initial_cash,
            positions={},
            closed_trades=[],
            peak_equity=self.initial_cash,
            max_drawdown_pct=0.0,
        )

    def save_state(self) -> None:
        """Persist current portfolio to JSON."""
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w", encoding="utf-8") as f:
            f.write(self.portfolio.model_dump_json(indent=2))

    def update_prices(self, current_prices: Dict[str, float]) -> None:
        """Update current market prices for open positions and check stop-loss/take-profit triggers."""
        for sym, pos in list(self.portfolio.positions.items()):
            if sym in current_prices:
                pos.current_price = current_prices[sym]

                # Stop-Loss trigger
                if pos.stop_loss and pos.current_price <= pos.stop_loss:
                    logger.info(f"Stop-Loss triggered for {sym} at {pos.current_price} <= {pos.stop_loss}")
                    self.execute_sell(sym, pos.current_price, pos.quantity, reason="Stop-Loss Triggered")

                # Take-Profit trigger
                elif pos.take_profit and pos.current_price >= pos.take_profit:
                    logger.info(f"Take-Profit triggered for {sym} at {pos.current_price} >= {pos.take_profit}")
                    self.execute_sell(sym, pos.current_price, pos.quantity, reason="Take-Profit Triggered")

        # Update peak equity & drawdown
        eq = self.portfolio.total_equity
        if eq > self.portfolio.peak_equity:
            self.portfolio.peak_equity = eq
        if self.portfolio.peak_equity > 0:
            dd = ((self.portfolio.peak_equity - eq) / self.portfolio.peak_equity) * 100
            if dd > self.portfolio.max_drawdown_pct:
                self.portfolio.max_drawdown_pct = round(dd, 2)

        self.save_state()

    def process_signal(self, signal: MarketSignal) -> Optional[Order]:
        """Evaluate signal with risk manager and execute paper trade if approved."""
        approved, reason, qty = self.risk_manager.validate_order(signal, self.portfolio)

        if not approved:
            logger.info(f"Signal for {signal.symbol} rejected: {reason}")
            return None

        if signal.action == Action.BUY:
            return self.execute_buy(
                symbol=signal.symbol,
                price=signal.price,
                quantity=qty,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )
        elif signal.action == Action.SELL:
            return self.execute_sell(
                symbol=signal.symbol,
                price=signal.price,
                quantity=qty,
                reason=signal.reason,
            )

        return None

    def execute_buy(
        self,
        symbol: str,
        price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Order:
        exec_price = price * (1 + self.slippage_pct)
        gross_cost = quantity * exec_price
        fee = gross_cost * self.fee_pct
        total_cost = gross_cost + fee

        if total_cost > self.portfolio.cash:
            # Scale down
            quantity = (self.portfolio.cash * 0.99) / (exec_price * (1 + self.fee_pct))
            gross_cost = quantity * exec_price
            fee = gross_cost * self.fee_pct
            total_cost = gross_cost + fee

        self.portfolio.cash -= total_cost

        # Update or create position
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
            new_qty = pos.quantity + quantity
            avg_entry = ((pos.quantity * pos.entry_price) + gross_cost) / new_qty
            pos.quantity = new_qty
            pos.entry_price = avg_entry
            pos.current_price = exec_price
            pos.stop_loss = stop_loss or pos.stop_loss
            pos.take_profit = take_profit or pos.take_profit
        else:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=exec_price,
                current_price=exec_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        order = Order(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action=Action.BUY,
            order_type=OrderType.MARKET,
            quantity=round(quantity, 4),
            price=price,
            filled_price=round(exec_price, 2),
            fee=round(fee, 2),
            status=OrderStatus.FILLED,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.save_state()
        return order

    def execute_sell(
        self,
        symbol: str,
        price: float,
        quantity: float,
        reason: str = "",
    ) -> Optional[Order]:
        if symbol not in self.portfolio.positions:
            return None

        pos = self.portfolio.positions[symbol]
        sell_qty = min(pos.quantity, quantity)
        if sell_qty <= 0:
            return None

        exec_price = price * (1 - self.slippage_pct)
        proceeds = sell_qty * exec_price
        fee = proceeds * self.fee_pct
        net_proceeds = proceeds - fee

        pnl = net_proceeds - (sell_qty * pos.entry_price)
        pnl_pct = (pnl / (sell_qty * pos.entry_price)) * 100

        self.portfolio.cash += net_proceeds
        pos.quantity -= sell_qty

        # Record closed trade
        self.portfolio.closed_trades.append(
            {
                "symbol": symbol,
                "entry_price": round(pos.entry_price, 2),
                "exit_price": round(exec_price, 2),
                "quantity": round(sell_qty, 4),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        if pos.quantity <= 0.0001:
            del self.portfolio.positions[symbol]

        order = Order(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action=Action.SELL,
            order_type=OrderType.MARKET,
            quantity=round(sell_qty, 4),
            price=price,
            filled_price=round(exec_price, 2),
            fee=round(fee, 2),
            status=OrderStatus.FILLED,
        )

        self.save_state()
        return order