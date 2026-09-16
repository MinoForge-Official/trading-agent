"""Risk management module: position sizing, max drawdown kill-switches, and risk-reward validation."""

from __future__ import annotations

import logging
from typing import Optional, Tuple
from trading_agent.core.models import Action, MarketSignal, Portfolio

logger = logging.getLogger(__name__)


class RiskManager:
    """Enforces strict portfolio risk parameters, sizing, and loss caps."""

    def __init__(
        self,
        risk_per_trade_pct: float = 1.0,     # Max 1% equity risked per trade
        max_position_size_pct: float = 20.0, # Max 20% portfolio allocation in one asset
        max_portfolio_drawdown_pct: float = 15.0, # Kill-switch at 15% drawdown
        min_risk_reward_ratio: float = 1.5,
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_portfolio_drawdown_pct = max_portfolio_drawdown_pct
        self.min_risk_reward_ratio = min_risk_reward_ratio

    def validate_order(
        self,
        signal: MarketSignal,
        portfolio: Portfolio,
    ) -> Tuple[bool, str, float]:
        """
        Validate whether a signal should be executed and determine the safe position quantity.
        Returns: (is_approved: bool, reason: str, approved_quantity: float)
        """
        if signal.action == Action.HOLD:
            return False, "Signal is HOLD", 0.0

        if signal.action == Action.SELL:
            # Check if we own any of the asset to sell
            if signal.symbol not in portfolio.positions or portfolio.positions[signal.symbol].quantity <= 0:
                return False, f"No open position in {signal.symbol} to sell", 0.0
            return True, "Sell order approved to close or reduce position", portfolio.positions[signal.symbol].quantity

        # BUY action checks:
        # 1. Circuit Breaker: Max Drawdown Kill-switch
        if portfolio.max_drawdown_pct >= self.max_portfolio_drawdown_pct:
            return (
                False,
                f"KILL-SWITCH ACTIVE: Portfolio drawdown ({portfolio.max_drawdown_pct:.1f}%) "
                f"exceeds limit ({self.max_portfolio_drawdown_pct:.1f}%). Trading halted.",
                0.0,
            )

        total_equity = portfolio.total_equity
        if total_equity <= 0:
            return False, "Portfolio equity is zero or negative.", 0.0

        if portfolio.cash <= 10.0:
            return False, f"Insufficient available cash (${portfolio.cash:.2f}) to open new positions.", 0.0

        price = signal.price
        if price <= 0:
            return False, f"Invalid asset price: {price}", 0.0

        # 2. Risk-Reward Check (if SL and TP are specified)
        if signal.stop_loss and signal.take_profit:
            risk_per_share = price - signal.stop_loss
            reward_per_share = signal.take_profit - price
            if risk_per_share > 0:
                rr_ratio = reward_per_share / risk_per_share
                if rr_ratio < self.min_risk_reward_ratio:
                    return (
                        False,
                        f"Risk/Reward ratio ({rr_ratio:.2f}) is below minimum required ({self.min_risk_reward_ratio:.2f})",
                        0.0,
                    )

        # 3. Position Sizing based on fixed risk percentage
        # Amount willing to risk = total_equity * (risk_per_trade_pct / 100)
        risk_budget = total_equity * (self.risk_per_trade_pct / 100.0)

        # Determine stop-loss distance
        if signal.stop_loss and signal.stop_loss < price:
            sl_distance = price - signal.stop_loss
        else:
            sl_distance = price * 0.03  # Default 3% stop distance

        # Quantity from risk budget:
        risk_based_qty = risk_budget / sl_distance

        # Max capital allocation for this asset:
        max_asset_capital = total_equity * (self.max_position_size_pct / 100.0)
        current_pos_val = (
            portfolio.positions[signal.symbol].market_value if signal.symbol in portfolio.positions else 0.0
        )
        remaining_allocation = max(0.0, max_asset_capital - current_pos_val)
        alloc_based_qty = remaining_allocation / price

        # Cash constraint:
        cash_based_qty = (portfolio.cash * 0.98) / price  # Reserve 2% buffer for fees/slippage

        # Take the most conservative quantity
        target_qty = min(risk_based_qty, alloc_based_qty, cash_based_qty)

        if target_qty <= 0.0001:
            return False, "Calculated safe order quantity is below minimum trade threshold.", 0.0

        # Round sensibly: integer for high price stocks, decimals for crypto/fractional
        if price > 50:
            final_qty = max(1.0, float(int(target_qty)))
            if final_qty * price > portfolio.cash:
                final_qty = float(int(portfolio.cash / price))
        else:
            final_qty = round(target_qty, 4)

        if final_qty <= 0 or (final_qty * price) > portfolio.cash:
            return False, "Calculated quantity exceeds available cash.", 0.0

        return True, f"Approved {final_qty} units with ${risk_budget:.2f} risk budget", final_qty