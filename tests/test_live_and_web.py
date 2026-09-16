"""Tests for live exchange connector, webhooks, and FastAPI web app."""

import pytest
from fastapi.testclient import TestClient
from trading_agent.live.exchange_connector import ExchangeConnector
from trading_agent.live.order_executor import LiveOrderExecutor
from trading_agent.live.webhook_server import WebhookHandler, WebhookTradePayload
from trading_agent.web.app import app


def test_exchange_connector_sandbox():
    connector = ExchangeConnector(exchange_id="binance", testnet=True)
    assert connector.exchange_id == "binance"
    assert connector.testnet is True

    # Test without API key returns structured warning
    res = connector.test_connection()
    assert res["connected"] is False
    assert "not configured" in res["message"]


def test_webhook_handler():
    connector = ExchangeConnector(exchange_id="binance", testnet=True)
    executor = LiveOrderExecutor(connector=connector)
    handler = WebhookHandler(executor=executor, webhook_secret="test1234")

    # Invalid secret rejected
    bad_res = handler.handle_payload({
        "action": "BUY",
        "ticker": "BTC/USDT",
        "secret": "wrong_token",
    })
    assert bad_res["status"] == "error"
    assert "Unauthorized" in bad_res["message"]


def test_web_status_endpoint():
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "portfolio" in data
    assert "watchlist" in data
    assert "exchange" in data
