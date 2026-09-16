"""Live Trading Exchange Connector supporting Binance, Bybit, Kraken, KuCoin, and Alpaca."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import ccxt

logger = logging.getLogger(__name__)


class ExchangeConnector:
    """Manages authenticated live API connection to trading sites and brokers."""

    SUPPORTED_EXCHANGES = ["binance", "bybit", "kraken", "kucoin", "coinbase"]

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
        password: Optional[str] = None,
    ):
        self.exchange_id = exchange_id.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.password = password
        self._exchange = None
        self._initialize_exchange()

    def _initialize_exchange(self) -> None:
        if not hasattr(ccxt, self.exchange_id):
            raise ValueError(f"Exchange '{self.exchange_id}' is not supported by CCXT.")

        exchange_class = getattr(ccxt, self.exchange_id)
        config: Dict[str, Any] = {
            "enableRateLimit": True,
            "timeout": 20000,
        }

        if self.api_key and self.api_secret:
            config["apiKey"] = self.api_key
            config["secret"] = self.api_secret
            if self.password:
                config["password"] = self.password

        self._exchange = exchange_class(config)

        # Set sandbox / testnet if enabled
        if self.testnet:
            try:
                self._exchange.set_sandbox_mode(True)
                logger.info(f"Sandbox / Testnet mode enabled for {self.exchange_id}.")
            except Exception as e:
                logger.warning(f"Could not set sandbox mode on {self.exchange_id}: {e}")

    def test_connection(self) -> Dict[str, Any]:
        """Test the live API connection to the trading site and verify permissions."""
        if not self.api_key or not self.api_secret:
            return {
                "connected": False,
                "exchange": self.exchange_id,
                "testnet": self.testnet,
                "message": "API Key and Secret are not configured.",
            }

        try:
            self._exchange.load_markets()
            balance = self._exchange.fetch_balance()
            total_equity = float(balance.get("total", {}).get("USDT", 0.0) or balance.get("total", {}).get("USD", 0.0))
            return {
                "connected": True,
                "exchange": self.exchange_id,
                "testnet": self.testnet,
                "equity_estimate": total_equity,
                "message": f"Successfully connected to {self.exchange_id.upper()} ({'TESTNET' if self.testnet else 'LIVE'}).",
            }
        except Exception as e:
            return {
                "connected": False,
                "exchange": self.exchange_id,
                "testnet": self.testnet,
                "error": str(e),
                "message": f"Connection failed to {self.exchange_id}: {e}",
            }

    def fetch_live_balance(self) -> Dict[str, Any]:
        """Fetch actual wallet balance and available margin directly from the trading site."""
        try:
            raw = self._exchange.fetch_balance()
            free_cash = float(raw.get("free", {}).get("USDT", 0.0) or raw.get("free", {}).get("USD", 0.0))
            total_cash = float(raw.get("total", {}).get("USDT", 0.0) or raw.get("total", {}).get("USD", 0.0))

            non_zero_assets = {}
            for asset, amt in raw.get("total", {}).items():
                if amt and amt > 0.0001:
                    non_zero_assets[asset] = {
                        "free": float(raw.get("free", {}).get(asset, 0.0)),
                        "total": float(amt),
                    }

            return {
                "free_cash": free_cash,
                "total_cash": total_cash,
                "assets": non_zero_assets,
            }
        except Exception as e:
            logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {"free_cash": 0.0, "total_cash": 0.0, "assets": {}, "error": str(e)}

    def fetch_ticker_price(self, symbol: str) -> float:
        """Fetch real-time bid/ask close price from the exchange orderbook."""
        try:
            ticker = self._exchange.fetch_ticker(symbol)
            return float(ticker.get("last") or ticker.get("close") or 0.0)
        except Exception as e:
            logger.error(f"Could not fetch ticker for {symbol}: {e}")
            return 0.0

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch live pending open orders on the exchange."""
        try:
            return self._exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []

    def fetch_my_trades(self, symbol: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch real executed trade history from the trading site."""
        try:
            if self._exchange.has.get("fetchMyTrades"):
                return self._exchange.fetch_my_trades(symbol, limit=limit)
            return []
        except Exception as e:
            logger.error(f"Error fetching trade history: {e}")
            return []
