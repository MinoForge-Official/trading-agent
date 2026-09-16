"""TradingView and Custom Webhook Receiver for automated trade execution on trading sites."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from trading_agent.core.models import Action, MarketSignal
from trading_agent.live.order_executor import LiveOrderExecutor

logger = logging.getLogger(__name__)


class WebhookTradePayload(BaseModel):
    """Payload format for TradingView and automated signal webhooks."""

    action: str = Field(description="BUY, SELL, or CLOSE")
    ticker: str = Field(description="Trading pair symbol (e.g. BTC/USDT, ETH/USDT, AAPL)")
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    secret: Optional[str] = None
    comment: Optional[str] = "TradingView Webhook Trigger"


class WebhookHandler:
    """Processes incoming trade webhooks from trading sites and executes orders."""

    def __init__(
        self,
        executor: LiveOrderExecutor,
        webhook_secret: Optional[str] = None,
    ):
        self.executor = executor
        self.webhook_secret = webhook_secret

    def handle_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and execute webhook order."""
        try:
            payload = WebhookTradePayload.model_validate(data)

            # Validate secret if configured
            if self.webhook_secret and payload.secret != self.webhook_secret:
                logger.warning("Rejected webhook: Invalid webhook secret token.")
                return {"status": "error", "message": "Unauthorized: Invalid webhook secret."}

            action_str = payload.action.upper()
            if action_str not in ["BUY", "SELL", "CLOSE"]:
                return {"status": "error", "message": f"Invalid action: {action_str}"}

            current_price = payload.price or self.executor.connector.fetch_ticker_price(payload.ticker)
            if current_price <= 0:
                return {"status": "error", "message": f"Could not determine price for {payload.ticker}"}

            sig = MarketSignal(
                symbol=payload.ticker,
                action=Action.BUY if action_str == "BUY" else Action.SELL,
                price=current_price,
                confidence=0.90,
                stop_loss=payload.stop_loss,
                take_profit=payload.take_profit,
                reason=payload.comment or "TradingView Automated Alert",
            )

            result = self.executor.execute_signal(sig)
            return {"status": "success", "signal": sig.model_dump(), "execution": result}

        except Exception as e:
            logger.error(f"Error handling webhook payload: {e}")
            return {"status": "error", "message": str(e)}
