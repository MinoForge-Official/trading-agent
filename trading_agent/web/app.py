"""FastAPI Web Server powering the modern live trading site automation dashboard."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from trading_agent.core.config import AppSettings, load_settings, save_settings
from trading_agent.core.market_data import MarketDataProvider
from trading_agent.core.models import Action, MarketSignal
from trading_agent.engine.paper_trader import PaperTrader
from trading_agent.live.exchange_connector import ExchangeConnector
from trading_agent.live.order_executor import LiveOrderExecutor
from trading_agent.live.webhook_server import WebhookHandler
from trading_agent.risk.manager import RiskManager
from trading_agent.strategies.ai_agent import AIAgentStrategy
from trading_agent.strategies.technical import (
    BollingerBandStrategy,
    CompositeStrategy,
    EMATrendStrategy,
    RSIOscillatorStrategy,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Agent Pro - Live Automation Desk")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Global singletons
settings = load_settings()
provider = MarketDataProvider()
risk_manager = RiskManager(
    risk_per_trade_pct=settings.risk_per_trade_pct,
    max_position_size_pct=settings.max_position_size_pct,
    max_portfolio_drawdown_pct=settings.max_portfolio_drawdown_pct,
    min_risk_reward_ratio=settings.min_risk_reward_ratio,
)
paper_trader = PaperTrader(storage_file="portfolio_state.json", risk_manager=risk_manager)

# Exchange Connector & Live Executor
exchange_connector = ExchangeConnector(
    exchange_id="binance",
    testnet=True,
)
order_executor = LiveOrderExecutor(connector=exchange_connector, risk_manager=risk_manager)
webhook_handler = WebhookHandler(executor=order_executor)

current_signals_cache: Dict[str, MarketSignal] = {}
system_logs: List[Dict[str, str]] = []


def add_log(msg: str, level: str = "INFO") -> None:
    from datetime import datetime, timezone
    system_logs.append({
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "level": level,
        "message": msg,
    })
    if len(system_logs) > 100:
        system_logs.pop(0)


class SettingsUpdate(BaseModel):
    auto_trading_enabled: bool
    trading_mode: str = "paper"  # "paper", "live", "advisory"
    exchange_id: str = "binance"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = True
    risk_per_trade_pct: float = 1.0
    max_portfolio_drawdown_pct: float = 15.0
    max_position_size_pct: float = 20.0
    min_confidence_to_trade: float = 0.70
    watchlist: List[str] = ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "NVDA"]
    default_strategy: str = "composite"


class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    amount: float
    order_type: str = "market"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Render the modern web trading desk."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "settings": settings,
        },
    )


@app.get("/api/status")
async def get_status():
    """Get system status, exchange connection, and live metrics."""
    conn_info = exchange_connector.test_connection() if (exchange_connector.api_key and exchange_connector.api_secret) else {
        "connected": False,
        "exchange": exchange_connector.exchange_id,
        "testnet": exchange_connector.testnet,
        "message": "Demo / Sandbox mode (Enter API credentials in Settings for live site execution).",
    }

    portfolio = paper_trader.portfolio
    return {
        "auto_trading": settings.auto_trading_enabled,
        "mode": getattr(settings, "trading_mode", "paper"),
        "exchange": conn_info,
        "portfolio": {
            "total_equity": portfolio.total_equity,
            "cash": portfolio.cash,
            "return_pct": portfolio.total_pnl_pct,
            "drawdown_pct": portfolio.max_drawdown_pct,
            "positions_count": len(portfolio.positions),
        },
        "watchlist": settings.watchlist,
        "strategy": settings.default_strategy,
    }


@app.post("/api/scan")
async def run_market_scan():
    """Scan all watchlist symbols in real time and generate signals."""
    strat_name = settings.default_strategy.lower()
    if strat_name == "ema":
        strategy = EMATrendStrategy()
    elif strat_name == "rsi":
        strategy = RSIOscillatorStrategy()
    elif strat_name == "bb":
        strategy = BollingerBandStrategy()
    elif strat_name == "ai":
        strategy = AIAgentStrategy(api_key=settings.gemini_api_key)
    else:
        strategy = CompositeStrategy()

    results = []
    curr_prices = {}

    for sym in settings.watchlist:
        try:
            df = provider.get_historical_data(sym, period="6mo")
            sig = strategy.evaluate(sym, df)
            current_signals_cache[sym] = sig
            curr_prices[sym] = sig.price

            results.append({
                "symbol": sig.symbol,
                "action": sig.action.value,
                "price": sig.price,
                "confidence": round(sig.confidence * 100, 1),
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit,
                "reason": sig.reason,
                "indicators": sig.indicators,
            })

            # Auto-Trading trigger
            if settings.auto_trading_enabled and sig.action in [Action.BUY, Action.SELL]:
                if sig.confidence >= settings.min_confidence_to_trade:
                    if getattr(settings, "trading_mode", "paper") == "live":
                        exec_res = order_executor.execute_signal(sig)
                        add_log(f"LIVE ORDER: {sig.action.value} {sig.symbol} -> {exec_res}", "SUCCESS")
                    else:
                        order = paper_trader.process_signal(sig)
                        if order:
                            add_log(f"PAPER ORDER: {order.action.value} {order.quantity} {order.symbol} @ ${order.filled_price:.2f}", "SUCCESS")

        except Exception as e:
            logger.error(f"Error scanning {sym}: {e}")
            results.append({"symbol": sym, "error": str(e)})

    paper_trader.update_prices(curr_prices)
    add_log(f"Market scan completed for {len(results)} assets using {strategy.name}.", "INFO")
    return {"status": "success", "signals": results}


@app.get("/api/chart-data/{symbol:path}")
async def get_chart_candles(symbol: str):
    """Fetch OHLCV historical candle series formatted for TradingView charts."""
    df = provider.get_historical_data(symbol, period="6mo")
    candles = []
    for idx, row in df.iterrows():
        # timestamp in seconds
        ts = int(idx.timestamp()) if hasattr(idx, "timestamp") else int(idx.value // 10**9)
        candles.append({
            "time": ts,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": round(float(row.get("Volume", 0)), 2),
        })

    signal = current_signals_cache.get(symbol)
    return {
        "symbol": symbol,
        "candles": candles,
        "signal": signal.model_dump() if signal else None,
    }


@app.post("/api/order/manual")
async def place_manual_order(req: OrderRequest):
    """Place a manual order (Live on exchange or Paper)."""
    mode = getattr(settings, "trading_mode", "paper")
    side = req.side.lower()

    if mode == "live":
        res = order_executor.place_market_order(
            symbol=req.symbol,
            side=side,
            amount=req.amount,
            stop_loss=req.stop_loss,
            take_profit=req.take_profit,
        )
        add_log(f"Manual LIVE order placed: {side.upper()} {req.amount} {req.symbol}", "INFO")
        return res
    else:
        price = req.price or provider.get_historical_data(req.symbol, period="1mo")["Close"].iloc[-1]
        if side == "buy":
            order = paper_trader.execute_buy(req.symbol, price, req.amount, req.stop_loss, req.take_profit)
        else:
            order = paper_trader.execute_sell(req.symbol, price, req.amount, reason="Manual User Close")

        add_log(f"Manual PAPER order placed: {side.upper()} {req.amount} {req.symbol}", "INFO")
        return {"success": True, "order": order.model_dump() if order else None}


@app.post("/api/webhook/trade")
async def receive_webhook(request: Request):
    """TradingView Alert Webhook Endpoint."""
    try:
        body = await request.json()
        result = webhook_handler.handle_payload(body)
        add_log(f"Webhook received for {body.get('ticker')}: {result.get('status')}", "INFO")
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/portfolio")
async def get_portfolio_data():
    """Get active positions, trade history, and account metrics."""
    p = paper_trader.portfolio
    positions = []
    for sym, pos in p.positions.items():
        positions.append({
            "symbol": sym,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "market_value": pos.market_value,
            "unrealized_pnl": pos.unrealized_pnl,
            "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
        })

    return {
        "cash": p.cash,
        "total_equity": p.total_equity,
        "total_pnl": p.total_pnl,
        "total_pnl_pct": p.total_pnl_pct,
        "peak_equity": p.peak_equity,
        "max_drawdown_pct": p.max_drawdown_pct,
        "positions": positions,
        "closed_trades": p.closed_trades[-15:],
        "logs": system_logs[-30:],
    }


@app.post("/api/settings")
async def update_settings(update: SettingsUpdate):
    """Save user configuration and re-initialize connections."""
    global settings, risk_manager, order_executor, exchange_connector

    settings.auto_trading_enabled = update.auto_trading_enabled
    setattr(settings, "trading_mode", update.trading_mode)
    settings.risk_per_trade_pct = update.risk_per_trade_pct
    settings.max_portfolio_drawdown_pct = update.max_portfolio_drawdown_pct
    settings.max_position_size_pct = update.max_position_size_pct
    settings.min_confidence_to_trade = update.min_confidence_to_trade
    settings.watchlist = [s.strip().upper() for s in update.watchlist if s.strip()]
    settings.default_strategy = update.default_strategy

    save_settings(settings)

    # Update risk manager
    risk_manager.risk_per_trade_pct = update.risk_per_trade_pct
    risk_manager.max_position_size_pct = update.max_position_size_pct
    risk_manager.max_portfolio_drawdown_pct = update.max_portfolio_drawdown_pct

    # Re-initialize exchange if credentials provided
    if update.api_key and update.api_secret:
        exchange_connector = ExchangeConnector(
            exchange_id=update.exchange_id,
            api_key=update.api_key,
            api_secret=update.api_secret,
            testnet=update.testnet,
        )
        order_executor.connector = exchange_connector

    add_log("Settings updated successfully.", "SUCCESS")
    return {"status": "success", "message": "Settings updated"}


@app.post("/api/emergency/halt")
async def emergency_halt():
    """Emergency Circuit Breaker: disable auto-trading immediately."""
    settings.auto_trading_enabled = False
    save_settings(settings)
    add_log("EMERGENCY KILLSWITCH TRIGGERED: All automated trading HALTED.", "ERROR")
    return {"status": "halted", "auto_trading": False}
