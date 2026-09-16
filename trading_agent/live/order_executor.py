"""Live Order Execution engine that submits real orders to trading sites with strict risk gating."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from trading_agent.core.models import Action, MarketSignal, Portfolio, Position
from trading_agent.live.exchange_connector import ExchangeConnector
from trading_agent.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class LiveOrderExecutor:
    """Executes live orders on real trading platforms with safety barriers."""

    def __init__(
        self,
        connector: ExchangeConnector,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.connector = connector
        self.risk_manager = risk_manager or RiskManager()

    def execute_signal(
        self,
        signal: MarketSignal,
        paper_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Validate signal through RiskManager and submit real order to the trading site."""
        if not self.connector.api_key or not self.connector.api_secret:
            return {
                "success": False,
                "reason": "Exchange API keys not configured. Please enter API Key in settings.",
            }

        # Check live balance from exchange
        balance = self.connector.fetch_live_balance()
        free_cash = balance.get("free_cash", 0.0)

        # Build mock portfolio for risk manager checks
        portfolio = Portfolio(
            cash=free_cash,
            starting_cash=balance.get("total_cash", free_cash),
        )

        approved, reason, qty = self.risk_manager.validate_order(signal, portfolio)
        if not approved:
            logger.warning(f"Live order for {signal.symbol} rejected by RiskManager: {reason}")
            return {
                "success": False,
                "reason": f"Risk Manager Rejected: {reason}",
                "symbol": signal.symbol,
            }

        side = "buy" if signal.action == Action.BUY else "sell"
        return self.place_market_order(
            symbol=signal.symbol,
            side=side,
            amount=qty,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

    def place_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Submit a Market Buy/Sell order directly to the trading site."""
        try:
            exchange = self.connector._exchange
            logger.info(f"Submitting LIVE {side.upper()} order for {amount} {symbol} to {self.connector.exchange_id}...")

            params = {}
            if stop_loss:
                params["stopLoss"] = {"triggerPrice": stop_loss}
            if take_profit:
                params["takeProfit"] = {"triggerPrice": take_profit}

            order = exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
                params=params,
            )

            logger.info(f"Live order executed successfully: ID {order.get('id')}")
            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": order.get("price") or order.get("average"),
                "status": order.get("status"),
                "exchange": self.connector.exchange_id,
            }
        except Exception as exc:
            logger.error(f"Live order submission failed on {self.connector.exchange_id}: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "symbol": symbol,
                "side": side,
                "amount": amount,
            }

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        """Submit a Limit order to the exchange order book."""
        try:
            exchange = self.connector._exchange
            order = exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=amount,
                price=price,
            )
            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "status": order.get("status"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order on the trading site."""
        try:
            res = self.connector._exchange.cancel_order(order_id, symbol)
            return {"success": True, "result": res}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
