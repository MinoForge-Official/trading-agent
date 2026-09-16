"""FastAPI Web Server powering Trading Agent Pro Live Automation Desk.

Includes:
- Full User Account Management with duplicate email prevention and password strength validation
- Dual Engine: Full Autonomous Real-Trade Execution vs Copilot Tips & Advisory
- AI Chat Interface powered by Gemini 3.6 Flash
- Institutional Safety Barriers, Exchange Connector, and Theme Engine
- Release Version & Date Metadata
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from trading_agent.ai.chat_engine import TradingChatEngine
from trading_agent.core.auth import AuthManager, check_password_strength
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

# Official Release Metadata
RELEASE_INFO = {
    "version": "v2.5.0-LTS",
    "release_date": "September 16, 2026",
    "build_target": "Windows x64 Standalone Executable",
    "author": "MinoForge-Official",
    "ai_engine": "Google Gemini 3.6 Flash",
    "status": "Production Stable",
}

# Global Singletons
settings = load_settings()
provider = MarketDataProvider()
auth_manager = AuthManager(storage_file="data/users.json")
chat_engine = TradingChatEngine()

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
active_user_session: Optional[Dict[str, Any]] = None


def add_log(msg: str, level: str = "INFO") -> None:
    from datetime import datetime, timezone
    system_logs.append({
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "level": level,
        "message": msg,
    })
    if len(system_logs) > 100:
        system_logs.pop(0)


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    experience_level: str = "Intermediate"
    trading_website: str = "binance"
    traded_assets: Optional[List[str]] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordStrengthRequest(BaseModel):
    password: str


class ModeRequest(BaseModel):
    mode: str  # "autonomous" or "copilot"


class ChatMessageRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    asset: Optional[str] = None


class SafetyBarriersUpdate(BaseModel):
    max_risk_per_trade_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_drawdown_pct: float
    max_open_positions: int
    require_manual_confirmation: bool


class ExchangeCredentialsUpdate(BaseModel):
    exchange_id: str
    testnet: bool
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class SettingsFullUpdate(BaseModel):
    theme: Optional[str] = None
    trading_mode: Optional[str] = None
    trading_website: Optional[str] = None
    traded_assets: Optional[List[str]] = None
    safety_barriers: Optional[SafetyBarriersUpdate] = None
    exchange_credentials: Optional[ExchangeCredentialsUpdate] = None


class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    amount: float
    order_type: str = "market"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


# ==============================================================================
# ROUTE HANDLERS
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Render the modern web trading desk."""
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={"settings": settings, "release": RELEASE_INFO},
    )


@app.get("/api/status")
async def get_system_status():
    """Get overall system, portfolio, exchange, and watchlist status."""
    p = paper_trader.portfolio
    conn_info = exchange_connector.test_connection() if (exchange_connector.api_key and exchange_connector.api_secret) else {
        "connected": False,
        "exchange": exchange_connector.exchange_id,
        "testnet": exchange_connector.testnet,
        "message": "Demo Sandbox Mode",
    }
    return {
        "status": "online",
        "mode": getattr(settings, "trading_mode", "paper"),
        "portfolio": {
            "total_equity": p.total_equity,
            "cash": p.cash,
            "total_pnl_pct": p.total_pnl_pct,
            "drawdown_pct": p.max_drawdown_pct,
        },
        "watchlist": settings.watchlist,
        "exchange": conn_info,
        "release": RELEASE_INFO,
    }


# --- AUTHENTICATION & ACCOUNT ROUTES ---

@app.post("/api/auth/strength")
async def evaluate_password(req: PasswordStrengthRequest):
    """Evaluate password strength and return score and checklist."""
    result = check_password_strength(req.password)
    return result


@app.post("/api/auth/register")
async def register_account(req: RegisterRequest):
    """Register a new user account with duplicate email prevention."""
    global active_user_session
    try:
        user = auth_manager.register(
            name=req.name,
            email=req.email,
            password=req.password,
            experience_level=req.experience_level,
            trading_website=req.trading_website,
            traded_assets=req.traded_assets,
        )
        active_user_session = user
        add_log(f"New account created for {user['email']}.", "SUCCESS")
        return {"status": "success", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Registration error: {ex}")


@app.post("/api/auth/login")
async def login_account(req: LoginRequest):
    """Authenticate user with email and password."""
    global active_user_session
    user = auth_manager.authenticate(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    active_user_session = user
    add_log(f"User {user['email']} logged in.", "INFO")
    return {"status": "success", "user": user}


@app.get("/api/auth/me")
async def get_current_user():
    """Get active user session or default fallback profile."""
    if active_user_session:
        return {"authenticated": True, "user": active_user_session}
    return {"authenticated": False, "user": None}


@app.post("/api/auth/logout")
async def logout_user():
    """End active user session."""
    global active_user_session
    active_user_session = None
    return {"status": "success"}


# --- OPERATING MODE ROUTES ---

@app.get("/api/mode")
async def get_mode():
    """Get active operating mode (autonomous vs copilot)."""
    mode = "copilot"
    if active_user_session:
        mode = active_user_session.get("trading_mode", "copilot")
    return {"mode": mode}


@app.post("/api/mode")
async def set_mode(req: ModeRequest):
    """Toggle between Full Autonomous Real-Trade control and Copilot Tips."""
    global active_user_session
    mode = req.mode.lower()
    if mode not in ["autonomous", "copilot"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'autonomous' or 'copilot'.")

    settings.auto_trading_enabled = (mode == "autonomous")
    setattr(settings, "trading_mode", "live" if mode == "autonomous" else "paper")
    save_settings(settings)

    if active_user_session:
        active_user_session["trading_mode"] = mode
        auth_manager.update_profile(active_user_session["email"], {"trading_mode": mode})

    mode_label = "FULL AUTONOMOUS (REAL TRADES)" if mode == "autonomous" else "COPILOT (TIPS ONLY)"
    add_log(f"Operating mode switched to: {mode_label}", "SUCCESS")
    return {"status": "success", "mode": mode, "label": mode_label}


# --- AI CHAT & INTELLIGENCE ROUTES ---

@app.post("/api/chat")
async def chat_with_agent(req: ChatMessageRequest):
    """Send message to Gemini 3.6 Flash and receive smart trading advice."""
    user_context = {
        "trading_mode": active_user_session.get("trading_mode", "copilot") if active_user_session else "copilot",
        "trading_website": active_user_session.get("trading_website", "binance") if active_user_session else "binance",
        "traded_assets": active_user_session.get("traded_assets", ["BTC/USDT", "XAU/USD"]) if active_user_session else ["BTC/USDT", "XAU/USD"],
        "safety_barriers": active_user_session.get("safety_barriers", {
            "max_risk_per_trade_pct": settings.risk_per_trade_pct,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "max_drawdown_pct": settings.max_portfolio_drawdown_pct,
        }) if active_user_session else {
            "max_risk_per_trade_pct": settings.risk_per_trade_pct,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "max_drawdown_pct": settings.max_portfolio_drawdown_pct,
        },
    }

    res = chat_engine.chat(
        user_message=req.message,
        history=req.history,
        user_context=user_context,
    )
    return res


# --- SETTINGS & CONFIGURATION ROUTES ---

@app.get("/api/settings")
async def get_all_settings():
    """Retrieve full configuration: Safety Barriers, Theme, Exchange, Assets, Release Info."""
    curr_user = active_user_session or {}
    safety = curr_user.get("safety_barriers", {
        "max_risk_per_trade_pct": settings.risk_per_trade_pct,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 4.0,
        "max_drawdown_pct": settings.max_portfolio_drawdown_pct,
        "max_open_positions": 3,
        "require_manual_confirmation": False,
    })

    creds = curr_user.get("exchange_credentials", {
        "exchange_id": "binance",
        "testnet": True,
        "api_key": "",
        "api_secret": "",
    })

    conn_info = exchange_connector.test_connection() if (exchange_connector.api_key and exchange_connector.api_secret) else {
        "connected": False,
        "exchange": creds.get("exchange_id", "binance"),
        "testnet": creds.get("testnet", True),
        "message": "Demo / Sandbox mode (Enter API credentials in Settings for live site execution).",
    }

    return {
        "release": RELEASE_INFO,
        "theme": curr_user.get("theme", "cyberpunk"),
        "trading_mode": curr_user.get("trading_mode", "copilot"),
        "trading_website": curr_user.get("trading_website", "binance"),
        "traded_assets": curr_user.get("traded_assets", ["BTC/USDT", "XAU/USD", "ETH/USDT", "SOL/USDT", "NVDA", "AAPL"]),
        "safety_barriers": safety,
        "exchange_credentials": {
            "exchange_id": creds.get("exchange_id", "binance"),
            "testnet": creds.get("testnet", True),
            "api_key": creds.get("api_key", ""),
            "has_secret": bool(creds.get("api_secret")),
        },
        "exchange_status": conn_info,
        "user_profile": {
            "name": curr_user.get("name", "Guest Trader"),
            "email": curr_user.get("email", "guest@tradingagent.pro"),
            "experience_level": curr_user.get("experience_level", "Intermediate"),
            "created_at": curr_user.get("created_at", "September 16, 2026"),
        },
    }


@app.post("/api/settings/save")
async def save_all_settings(req: SettingsFullUpdate):
    """Save updated settings across Safety Barriers, Theme, Exchange, and Assets."""
    global active_user_session, risk_manager, exchange_connector, order_executor

    updates: Dict[str, Any] = {}

    if req.theme:
        updates["theme"] = req.theme
    if req.trading_mode:
        updates["trading_mode"] = req.trading_mode
        settings.auto_trading_enabled = (req.trading_mode == "autonomous")
    if req.trading_website:
        updates["trading_website"] = req.trading_website
    if req.traded_assets:
        updates["traded_assets"] = req.traded_assets
        settings.watchlist = req.traded_assets

    if req.safety_barriers:
        safety_dict = req.safety_barriers.model_dump()
        updates["safety_barriers"] = safety_dict
        risk_manager.risk_per_trade_pct = safety_dict["max_risk_per_trade_pct"]
        risk_manager.max_portfolio_drawdown_pct = safety_dict["max_drawdown_pct"]
        settings.risk_per_trade_pct = safety_dict["max_risk_per_trade_pct"]
        settings.max_portfolio_drawdown_pct = safety_dict["max_drawdown_pct"]

    if req.exchange_credentials:
        creds_dict = req.exchange_credentials.model_dump()
        updates["exchange_credentials"] = creds_dict
        if creds_dict.get("api_key") and creds_dict.get("api_secret"):
            exchange_connector = ExchangeConnector(
                exchange_id=creds_dict.get("exchange_id", "binance"),
                api_key=creds_dict.get("api_key"),
                api_secret=creds_dict.get("api_secret"),
                testnet=creds_dict.get("testnet", True),
            )
            order_executor.connector = exchange_connector

    save_settings(settings)

    if active_user_session:
        active_user_session = auth_manager.update_profile(active_user_session["email"], updates)

    add_log("Settings and safety barriers updated successfully.", "SUCCESS")
    return {"status": "success", "message": "Configuration saved."}


@app.post("/api/exchange/test")
async def test_exchange_connection(creds: ExchangeCredentialsUpdate):
    """Directly test exchange credentials against the live trading site."""
    conn = ExchangeConnector(
        exchange_id=creds.exchange_id,
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        testnet=creds.testnet,
    )
    result = conn.test_connection()
    return result


# --- MARKET DATA & CHART ROUTES ---

@app.get("/api/chart-data/{symbol:path}")
async def get_chart_candles(symbol: str):
    """Fetch OHLCV historical candle series formatted for TradingView charts."""
    df = provider.get_historical_data(symbol, period="6mo")
    candles = []
    for idx, row in df.iterrows():
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


@app.post("/api/scan")
async def run_market_scan():
    """Scan all watchlist symbols and generate signals."""
    strategy = CompositeStrategy()
    results = []
    curr_prices = {}

    symbols = settings.watchlist or ["BTC-USD", "ETH-USD", "AAPL", "NVDA"]
    for sym in symbols:
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
            })

            # Autonomous mode execution trigger
            if settings.auto_trading_enabled and sig.action in [Action.BUY, Action.SELL]:
                if sig.confidence >= settings.min_confidence_to_trade:
                    if getattr(settings, "trading_mode", "paper") == "live":
                        exec_res = order_executor.execute_signal(sig)
                        add_log(f"AUTONOMOUS REAL ORDER: {sig.action.value} {sig.symbol} -> {exec_res}", "SUCCESS")
                    else:
                        order = paper_trader.process_signal(sig)
                        if order:
                            add_log(f"AUTONOMOUS SIM ORDER: {order.action.value} {order.quantity} {order.symbol} @ ${order.filled_price:.2f}", "SUCCESS")

        except Exception as e:
            logger.error("Error scanning %s: %s", sym, e)
            results.append({"symbol": sym, "error": str(e)})

    paper_trader.update_prices(curr_prices)
    return {"status": "success", "signals": results}


@app.post("/api/order/manual")
async def place_manual_order(req: OrderRequest):
    """Place a trade execution (Live on exchange or Paper)."""
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
        add_log(f"REAL ORDER on {exchange_connector.exchange_id.upper()}: {side.upper()} {req.amount} {req.symbol}", "INFO")
        return res
    else:
        price = req.price or provider.get_historical_data(req.symbol, period="1mo")["Close"].iloc[-1]
        if side == "buy":
            order = paper_trader.execute_buy(req.symbol, price, req.amount, req.stop_loss, req.take_profit)
        else:
            order = paper_trader.execute_sell(req.symbol, price, req.amount, reason="Manual User Close")

        add_log(f"SIM ORDER: {side.upper()} {req.amount} {req.symbol}", "INFO")
        return {"success": True, "order": order.model_dump() if order else None}


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
        "max_drawdown_pct": p.max_drawdown_pct,
        "positions": positions,
        "closed_trades": p.closed_trades[-15:],
        "logs": system_logs[-30:],
    }


@app.post("/api/emergency/halt")
async def emergency_halt():
    """Emergency Circuit Breaker: disable all trading immediately."""
    settings.auto_trading_enabled = False
    setattr(settings, "trading_mode", "paper")
    save_settings(settings)
    add_log("EMERGENCY KILLSWITCH TRIGGERED: All trading halted immediately.", "ERROR")
    return {"status": "halted", "auto_trading": False}
