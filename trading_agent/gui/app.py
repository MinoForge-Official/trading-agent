"""Desktop Graphical User Interface for Trading Agent with safety controls and auto-trading."""

from __future__ import annotations

import logging
import queue
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from trading_agent.core.config import AppSettings, load_settings, save_settings
from trading_agent.core.market_data import MarketDataProvider
from trading_agent.core.models import Action, MarketSignal
from trading_agent.engine.backtester import Backtester
from trading_agent.engine.paper_trader import PaperTrader
from trading_agent.risk.manager import RiskManager
from trading_agent.strategies.ai_agent import AIAgentStrategy
from trading_agent.strategies.base import BaseStrategy
from trading_agent.strategies.technical import (
    BollingerBandStrategy,
    CompositeStrategy,
    EMATrendStrategy,
    RSIOscillatorStrategy,
)

logger = logging.getLogger(__name__)

# Dark Pro Theme Colors
COLOR_BG = "#131722"
COLOR_CARD = "#1e222d"
COLOR_CARD_HOVER = "#2a2e39"
COLOR_TEXT = "#d1d4dc"
COLOR_TEXT_MUTED = "#787b86"
COLOR_TEXT_WHITE = "#ffffff"
COLOR_GREEN = "#089981"
COLOR_RED = "#f23645"
COLOR_BLUE = "#2962ff"
COLOR_GOLD = "#f0b90b"


class TradingAgentApp:
    """Main Desktop GUI Application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Trading Agent Pro - Autonomous Trading Desk")
        self.root.geometry("1150x760")
        self.root.minsize(960, 640)
        self.root.configure(bg=COLOR_BG)

        # Load persisted settings
        self.settings: AppSettings = load_settings()

        # Engine objects
        self.provider = MarketDataProvider()
        self.risk_manager = self._build_risk_manager()
        self.paper_trader = PaperTrader(storage_file="portfolio_state.json", risk_manager=self.risk_manager)
        self.backtester = Backtester()

        # Threading & status flags
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.is_scanning = False
        self.auto_pilot_running = True
        self.last_scan_time: Optional[datetime] = None
        self.current_signals: List[MarketSignal] = []

        self._setup_styles()
        self._build_header()
        self._build_tabs()
        self._build_statusbar()

        # Start periodic GUI queue consumer and background auto-pilot
        self.root.after(200, self._process_log_queue)
        self._start_background_autopilot()

        self.log(f"System initialized. Loaded {len(self.settings.watchlist)} watchlist symbols.")
        self.log(
            f"Safety limits: Max risk/trade={self.settings.risk_per_trade_pct}%, "
            f"Killswitch={self.settings.max_portfolio_drawdown_pct}%."
        )
        if self.settings.auto_trading_enabled:
            self.log("AUTONOMOUS TRADING IS ENABLED. Agent will execute approved trades automatically.", level="WARN")
        else:
            self.log("Autonomous trading is PAUSED (Advisory mode).", level="INFO")

    def _build_risk_manager(self) -> RiskManager:
        return RiskManager(
            risk_per_trade_pct=self.settings.risk_per_trade_pct,
            max_position_size_pct=self.settings.max_position_size_pct,
            max_portfolio_drawdown_pct=self.settings.max_portfolio_drawdown_pct,
            min_risk_reward_ratio=self.settings.min_risk_reward_ratio,
        )

    def _get_strategy(self, name: Optional[str] = None) -> BaseStrategy:
        st_name = (name or self.settings.default_strategy).lower()
        if st_name == "ema":
            return EMATrendStrategy()
        elif st_name == "rsi":
            return RSIOscillatorStrategy()
        elif st_name == "bb":
            return BollingerBandStrategy()
        elif st_name == "ai":
            return AIAgentStrategy(api_key=self.settings.gemini_api_key)
        return CompositeStrategy()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_CARD_HOVER), ("active", COLOR_CARD_HOVER)],
            foreground=[("selected", COLOR_BLUE), ("active", COLOR_TEXT_WHITE)],
        )

        style.configure(
            "Treeview",
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_CARD,
            font=("Segoe UI", 9),
            rowheight=26,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=COLOR_CARD_HOVER,
            foreground=COLOR_TEXT_WHITE,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", COLOR_BLUE)], foreground=[("selected", COLOR_TEXT_WHITE)])

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLOR_CARD, height=60)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        title_frame = tk.Frame(header, bg=COLOR_CARD)
        title_frame.pack(side=tk.LEFT, padx=15, pady=8)

        title = tk.Label(
            title_frame,
            text="TRADING AGENT PRO",
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg=COLOR_CARD,
        )
        title.pack(side=tk.LEFT)

        subtitle = tk.Label(
            title_frame,
            text=" | Autonomous Algorithmic Desk",
            font=("Segoe UI", 11),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
        )
        subtitle.pack(side=tk.LEFT)

        self.autopilot_label = tk.Label(
            header,
            text=self._get_autopilot_status_text(),
            font=("Segoe UI", 10, "bold"),
            fg=COLOR_GREEN if self.settings.auto_trading_enabled else COLOR_TEXT_MUTED,
            bg=COLOR_CARD_HOVER,
            padx=12,
            pady=4,
            relief=tk.FLAT,
        )
        self.autopilot_label.pack(side=tk.RIGHT, padx=15, pady=10)

    def _get_autopilot_status_text(self) -> str:
        if self.settings.auto_trading_enabled:
            return "[AUTO-TRADING: ACTIVE]"
        return "[AUTO-TRADING: PAUSED]"

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_dashboard = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_settings = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_portfolio = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_backtest = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_logs = tk.Frame(self.notebook, bg=COLOR_BG)

        self.notebook.add(self.tab_dashboard, text="Live Scanner")
        self.notebook.add(self.tab_settings, text="Safety & Settings")
        self.notebook.add(self.tab_portfolio, text="Paper Portfolio")
        self.notebook.add(self.tab_backtest, text="Backtest Simulator")
        self.notebook.add(self.tab_logs, text="Activity Log")

        self._init_tab_dashboard()
        self._init_tab_settings()
        self._init_tab_portfolio()
        self._init_tab_backtest()
        self._init_tab_logs()

    # -------------------------------------------------------------
    # TAB 1: DASHBOARD / SCANNER
    # -------------------------------------------------------------
    def _init_tab_dashboard(self) -> None:
        control_bar = tk.Frame(self.tab_dashboard, bg=COLOR_CARD)
        control_bar.pack(fill=tk.X, padx=5, pady=5)

        self.btn_scan = tk.Button(
            control_bar,
            text="Scan Watchlist Now",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BLUE,
            fg=COLOR_TEXT_WHITE,
            activebackground="#1e40af",
            activeforeground=COLOR_TEXT_WHITE,
            padx=12,
            pady=6,
            relief=tk.FLAT,
            command=self.trigger_scan,
        )
        self.btn_scan.pack(side=tk.LEFT, padx=10, pady=8)

        self.lbl_scan_status = tk.Label(
            control_bar,
            text="Status: Ready | Last Scan: Never",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
        )
        self.lbl_scan_status.pack(side=tk.LEFT, padx=10)

        self.btn_manual_exec = tk.Button(
            control_bar,
            text="Execute Selected Signal",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_CARD_HOVER,
            fg=COLOR_GREEN,
            relief=tk.FLAT,
            padx=10,
            pady=6,
            command=self._manual_execute_selected,
        )
        self.btn_manual_exec.pack(side=tk.RIGHT, padx=10, pady=8)

        columns = ("symbol", "action", "price", "confidence", "stop_loss", "take_profit", "rationale")
        self.tree_scan = ttk.Treeview(self.tab_dashboard, columns=columns, show="headings", selectmode="browse")
        self.tree_scan.heading("symbol", text="Asset")
        self.tree_scan.heading("action", text="Signal")
        self.tree_scan.heading("price", text="Price")
        self.tree_scan.heading("confidence", text="Confidence")
        self.tree_scan.heading("stop_loss", text="Stop Loss")
        self.tree_scan.heading("take_profit", text="Take Profit")
        self.tree_scan.heading("rationale", text="Reason / Drivers")

        self.tree_scan.column("symbol", width=90, anchor=tk.W)
        self.tree_scan.column("action", width=80, anchor=tk.CENTER)
        self.tree_scan.column("price", width=95, anchor=tk.E)
        self.tree_scan.column("confidence", width=90, anchor=tk.CENTER)
        self.tree_scan.column("stop_loss", width=95, anchor=tk.E)
        self.tree_scan.column("take_profit", width=95, anchor=tk.E)
        self.tree_scan.column("rationale", width=480, anchor=tk.W)

        self.tree_scan.tag_configure("BUY", foreground=COLOR_GREEN, font=("Segoe UI", 9, "bold"))
        self.tree_scan.tag_configure("SELL", foreground=COLOR_RED, font=("Segoe UI", 9, "bold"))
        self.tree_scan.tag_configure("HOLD", foreground=COLOR_TEXT_MUTED)

        scrollbar = ttk.Scrollbar(self.tab_dashboard, orient=tk.VERTICAL, command=self.tree_scan.yview)
        self.tree_scan.configure(yscroll=scrollbar.set)

        self.tree_scan.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)

    def trigger_scan(self) -> None:
        if self.is_scanning:
            return
        self.is_scanning = True
        self.btn_scan.config(state=tk.DISABLED, text="Scanning...")
        self.lbl_scan_status.config(text="Status: Scanning market data in background...", fg=COLOR_GOLD)

        thread = threading.Thread(target=self._worker_run_scan, daemon=True)
        thread.start()

    def _worker_run_scan(self) -> None:
        try:
            strategy = self._get_strategy()
            symbols = list(self.settings.watchlist)
            signals: List[MarketSignal] = []

            for sym in symbols:
                try:
                    df = self.provider.get_historical_data(sym, period="6mo")
                    sig = strategy.evaluate(sym, df)
                    signals.append(sig)
                except Exception as e:
                    self.log(f"Error scanning {sym}: {e}", level="ERROR")

            curr_prices = {s.symbol: s.price for s in signals}
            self.paper_trader.update_prices(curr_prices)

            if self.settings.auto_trading_enabled:
                for sig in signals:
                    if sig.action in [Action.BUY, Action.SELL] and sig.confidence >= self.settings.min_confidence_to_trade:
                        order = self.paper_trader.process_signal(sig)
                        if order:
                            self.log(
                                f"[AUTO-TRADE] Executed {order.action.value} for {order.symbol}: "
                                f"{order.quantity} units @ ${order.filled_price:.2f}",
                                level="SUCCESS",
                            )

            self.root.after(0, self._render_scan_results, signals)

        except Exception as exc:
            self.log(f"Scan failed: {exc}", level="ERROR")
        finally:
            self.root.after(0, self._reset_scan_ui)

    def _render_scan_results(self, signals: List[MarketSignal]) -> None:
        self.current_signals = signals
        for item in self.tree_scan.get_children():
            self.tree_scan.delete(item)

        for s in signals:
            sl_str = f"${s.stop_loss:.2f}" if s.stop_loss else "-"
            tp_str = f"${s.take_profit:.2f}" if s.take_profit else "-"
            tag = s.action.value
            self.tree_scan.insert(
                "",
                tk.END,
                values=(
                    s.symbol,
                    s.action.value,
                    f"${s.price:.2f}",
                    f"{s.confidence * 100:.0f}%",
                    sl_str,
                    tp_str,
                    s.reason,
                ),
                tags=(tag,),
            )

        self.last_scan_time = datetime.now(timezone.utc)
        self.lbl_scan_status.config(
            text=f"Status: Complete | Last Scan: {self.last_scan_time.strftime('%H:%M:%S UTC')} ({len(signals)} assets)",
            fg=COLOR_TEXT,
        )
        self._refresh_portfolio_tab()

    def _reset_scan_ui(self) -> None:
        self.is_scanning = False
        self.btn_scan.config(state=tk.NORMAL, text="Scan Watchlist Now")

    def _manual_execute_selected(self) -> None:
        selected = self.tree_scan.selection()
        if not selected:
            messagebox.showinfo("Select Asset", "Please select a row in the table first.")
            return

        item = self.tree_scan.item(selected[0])
        symbol = item["values"][0]
        match = next((s for s in self.current_signals if s.symbol == symbol), None)
        if not match:
            return

        if match.action == Action.HOLD:
            messagebox.showinfo("Signal is HOLD", f"{symbol} is currently neutral (HOLD). No trade recommendation.")
            return

        confirm = messagebox.askyesno(
            "Confirm Trade Execution",
            f"Do you want to manually execute {match.action.value} on {symbol} at ${match.price:.2f}?",
        )
        if confirm:
            order = self.paper_trader.process_signal(match)
            if order:
                self.log(
                    f"[MANUAL TRADE] Executed {order.action.value} for {order.symbol}: "
                    f"{order.quantity} units @ ${order.filled_price:.2f}",
                    level="SUCCESS",
                )
                self._refresh_portfolio_tab()
                messagebox.showinfo("Trade Executed", f"Successfully executed order for {order.symbol}!")
            else:
                messagebox.showwarning("Trade Rejected", "Order was rejected by Risk Manager. Check Activity Log.")

    # -------------------------------------------------------------
    # TAB 2: SAFETY BARRIERS & SETTINGS
    # -------------------------------------------------------------
    def _init_tab_settings(self) -> None:
        canvas = tk.Canvas(self.tab_settings, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_settings, orient="vertical", command=canvas.yview)
        content_frame = tk.Frame(canvas, bg=COLOR_BG)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")

        sec1 = self._create_settings_card(content_frame, "Autonomous Trading Mode (Auto Buy & Sell)")

        self.var_auto_trading = tk.BooleanVar(value=self.settings.auto_trading_enabled)
        chk_auto = tk.Checkbutton(
            sec1,
            text="Enable Autonomous Auto-Trading (Agent automatically buys and sells without asking)",
            variable=self.var_auto_trading,
            font=("Segoe UI", 10, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg=COLOR_CARD,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_GREEN,
            selectcolor=COLOR_CARD_HOVER,
            command=self._on_auto_trading_toggled,
        )
        chk_auto.pack(anchor=tk.W, padx=15, pady=(8, 2))

        tk.Label(
            sec1,
            text="When enabled, the bot will periodically evaluate signals and execute approved trades in your paper account.",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
        ).pack(anchor=tk.W, padx=35, pady=(0, 8))

        f_conf = tk.Frame(sec1, bg=COLOR_CARD)
        f_conf.pack(anchor=tk.W, padx=35, pady=(0, 10))
        tk.Label(f_conf, text="Minimum Signal Confidence for Auto-Trade (%):", font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_min_conf = tk.DoubleVar(value=round(self.settings.min_confidence_to_trade * 100, 1))
        spn_conf = tk.Spinbox(f_conf, from_=50, to=95, increment=5, textvariable=self.var_min_conf, width=6, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE)
        spn_conf.pack(side=tk.LEFT, padx=10)

        sec2 = self._create_settings_card(content_frame, "Safety Barriers & Capital Preservation Limits")

        r1 = tk.Frame(sec2, bg=COLOR_CARD)
        r1.pack(fill=tk.X, padx=15, pady=4)
        tk.Label(r1, text="Max Risk Per Trade (% of Total Equity):", width=38, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_risk_per_trade = tk.DoubleVar(value=self.settings.risk_per_trade_pct)
        tk.Spinbox(r1, from_=0.1, to=5.0, increment=0.25, textvariable=self.var_risk_per_trade, width=8, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT)
        tk.Label(r1, text="(Limits max loss if stop-loss triggers. Standard is 1.0%)", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side=tk.LEFT, padx=10)

        r2 = tk.Frame(sec2, bg=COLOR_CARD)
        r2.pack(fill=tk.X, padx=15, pady=4)
        tk.Label(r2, text="Max Position Size (% of Total Portfolio):", width=38, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_max_pos = tk.DoubleVar(value=self.settings.max_position_size_pct)
        tk.Spinbox(r2, from_=5.0, to=50.0, increment=5.0, textvariable=self.var_max_pos, width=8, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT)
        tk.Label(r2, text="(Prevents over-concentration in a single asset)", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side=tk.LEFT, padx=10)

        r3 = tk.Frame(sec2, bg=COLOR_CARD)
        r3.pack(fill=tk.X, padx=15, pady=4)
        tk.Label(r3, text="Circuit Breaker / Max Drawdown Kill-Switch (%):", width=38, anchor=tk.W, font=("Segoe UI", 9, "bold"), fg=COLOR_RED, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_killswitch = tk.DoubleVar(value=self.settings.max_portfolio_drawdown_pct)
        tk.Spinbox(r3, from_=5.0, to=30.0, increment=1.0, textvariable=self.var_killswitch, width=8, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT)
        tk.Label(r3, text="(Freezes ALL buy orders if portfolio drops by this % from peak)", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side=tk.LEFT, padx=10)

        r4 = tk.Frame(sec2, bg=COLOR_CARD)
        r4.pack(fill=tk.X, padx=15, pady=4)
        tk.Label(r4, text="Minimum Risk / Reward Ratio:", width=38, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_rr_ratio = tk.DoubleVar(value=self.settings.min_risk_reward_ratio)
        tk.Spinbox(r4, from_=1.0, to=4.0, increment=0.25, textvariable=self.var_rr_ratio, width=8, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT)
        tk.Label(r4, text="(Rejects setups where upside is less than 1.5x risk)", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side=tk.LEFT, padx=10)

        sec3 = self._create_settings_card(content_frame, "Strategy & Watchlist Configuration")

        r5 = tk.Frame(sec3, bg=COLOR_CARD)
        r5.pack(fill=tk.X, padx=15, pady=6)
        tk.Label(r5, text="Default Strategy:", width=22, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_strat = tk.StringVar(value=self.settings.default_strategy)
        cbo_strat = ttk.Combobox(
            r5,
            textvariable=self.var_strat,
            values=["composite", "ema", "rsi", "bb", "ai"],
            state="readonly",
            width=18,
        )
        cbo_strat.pack(side=tk.LEFT)

        r6 = tk.Frame(sec3, bg=COLOR_CARD)
        r6.pack(fill=tk.X, padx=15, pady=6)
        tk.Label(r6, text="Watchlist Symbols:", width=22, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_watchlist = tk.StringVar(value=", ".join(self.settings.watchlist))
        entry_watch = tk.Entry(r6, textvariable=self.var_watchlist, width=50, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE, relief=tk.FLAT)
        entry_watch.pack(side=tk.LEFT)

        r7 = tk.Frame(sec3, bg=COLOR_CARD)
        r7.pack(fill=tk.X, padx=15, pady=6)
        tk.Label(r7, text="Auto-Scan Interval (Minutes):", width=26, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_interval = tk.IntVar(value=self.settings.scan_interval_minutes)
        tk.Spinbox(r7, from_=1, to=120, increment=5, textvariable=self.var_interval, width=6, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT)

        r8 = tk.Frame(sec3, bg=COLOR_CARD)
        r8.pack(fill=tk.X, padx=15, pady=6)
        tk.Label(r8, text="Gemini API Key (Optional):", width=22, anchor=tk.W, font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT)
        self.var_gemini = tk.StringVar(value=self.settings.gemini_api_key or "")
        entry_gem = tk.Entry(r8, textvariable=self.var_gemini, show="*", width=50, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE, relief=tk.FLAT)
        entry_gem.pack(side=tk.LEFT)

        btn_save = tk.Button(
            content_frame,
            text="Save & Apply Settings",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_GREEN,
            fg=COLOR_TEXT_WHITE,
            activebackground="#057a67",
            activeforeground=COLOR_TEXT_WHITE,
            padx=20,
            pady=8,
            relief=tk.FLAT,
            command=self._save_settings_from_gui,
        )
        btn_save.pack(anchor=tk.W, padx=15, pady=15)

    def _create_settings_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLOR_CARD, relief=tk.FLAT)
        frame.pack(fill=tk.X, pady=8, ipady=5)

        lbl = tk.Label(frame, text=title, font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_WHITE, bg=COLOR_CARD)
        lbl.pack(anchor=tk.W, padx=15, pady=(10, 8))

        sep = tk.Frame(frame, height=1, bg=COLOR_CARD_HOVER)
        sep.pack(fill=tk.X, padx=15, pady=(0, 10))
        return frame

    def _on_auto_trading_toggled(self) -> None:
        state = self.var_auto_trading.get()
        if state:
            resp = messagebox.askyesno(
                "Enable Auto-Trading",
                "Are you sure you want to enable autonomous trading?\n\n"
                "The agent will automatically buy and sell in your simulated account "
                "based on detected signals and risk limits.",
            )
            if not resp:
                self.var_auto_trading.set(False)
                return

        self.autopilot_label.config(
            text="[AUTO-TRADING: ACTIVE]" if state else "[AUTO-TRADING: PAUSED]",
            fg=COLOR_GREEN if state else COLOR_TEXT_MUTED,
        )

    def _save_settings_from_gui(self) -> None:
        try:
            wl = [s.strip().upper() for s in self.var_watchlist.get().split(",") if s.strip()]
            self.settings.auto_trading_enabled = self.var_auto_trading.get()
            self.settings.min_confidence_to_trade = round(self.var_min_conf.get() / 100.0, 2)
            self.settings.risk_per_trade_pct = self.var_risk_per_trade.get()
            self.settings.max_position_size_pct = self.var_max_pos.get()
            self.settings.max_portfolio_drawdown_pct = self.var_killswitch.get()
            self.settings.min_risk_reward_ratio = self.var_rr_ratio.get()
            self.settings.default_strategy = self.var_strat.get()
            self.settings.watchlist = wl
            self.settings.scan_interval_minutes = self.var_interval.get()
            self.settings.gemini_api_key = self.var_gemini.get().strip() or None

            save_settings(self.settings)

            self.risk_manager = self._build_risk_manager()
            self.paper_trader.risk_manager = self.risk_manager

            self.autopilot_label.config(
                text=self._get_autopilot_status_text(),
                fg=COLOR_GREEN if self.settings.auto_trading_enabled else COLOR_TEXT_MUTED,
            )

            self.log("Settings successfully saved and applied.", level="SUCCESS")
            messagebox.showinfo("Settings Saved", "Settings and safety barriers have been successfully updated!")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")

    # -------------------------------------------------------------
    # TAB 3: PAPER PORTFOLIO
    # -------------------------------------------------------------
    def _init_tab_portfolio(self) -> None:
        cards_frame = tk.Frame(self.tab_portfolio, bg=COLOR_BG)
        cards_frame.pack(fill=tk.X, padx=5, pady=5)

        self.card_equity = self._create_metric_card(cards_frame, "Total Equity", "$10,000.00", COLOR_GREEN)
        self.card_cash = self._create_metric_card(cards_frame, "Cash Available", "$10,000.00", COLOR_TEXT_WHITE)
        self.card_pnl = self._create_metric_card(cards_frame, "Total Return", "+0.00%", COLOR_GREEN)
        self.card_drawdown = self._create_metric_card(cards_frame, "Max Drawdown", "0.00%", COLOR_RED)

        f_pos = tk.Frame(self.tab_portfolio, bg=COLOR_CARD)
        f_pos.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        header_bar = tk.Frame(f_pos, bg=COLOR_CARD)
        header_bar.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(header_bar, text="Open Positions", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_WHITE, bg=COLOR_CARD).pack(side=tk.LEFT)

        btn_close_pos = tk.Button(
            header_bar,
            text="Sell / Close Selected",
            font=("Segoe UI", 9),
            bg=COLOR_RED,
            fg=COLOR_TEXT_WHITE,
            relief=tk.FLAT,
            padx=10,
            command=self._close_selected_position,
        )
        btn_close_pos.pack(side=tk.RIGHT, padx=5)

        btn_reset_port = tk.Button(
            header_bar,
            text="Reset Account ($10,000)",
            font=("Segoe UI", 9),
            bg=COLOR_CARD_HOVER,
            fg=COLOR_TEXT_MUTED,
            relief=tk.FLAT,
            padx=10,
            command=self._reset_portfolio,
        )
        btn_reset_port.pack(side=tk.RIGHT, padx=5)

        cols = ("symbol", "qty", "entry_price", "curr_price", "market_value", "unrealized_pnl", "sl", "tp")
        self.tree_pos = ttk.Treeview(f_pos, columns=cols, show="headings", height=8, selectmode="browse")
        self.tree_pos.heading("symbol", text="Asset")
        self.tree_pos.heading("qty", text="Quantity")
        self.tree_pos.heading("entry_price", text="Entry Price")
        self.tree_pos.heading("curr_price", text="Current Price")
        self.tree_pos.heading("market_value", text="Market Value")
        self.tree_pos.heading("unrealized_pnl", text="PnL ($ / %)")
        self.tree_pos.heading("sl", text="Stop Loss")
        self.tree_pos.heading("tp", text="Take Profit")

        for c in cols:
            self.tree_pos.column(c, width=120, anchor=tk.CENTER)

        self.tree_pos.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        f_closed = tk.Frame(self.tab_portfolio, bg=COLOR_CARD, height=180)
        f_closed.pack(fill=tk.X, padx=5, pady=(0, 5))

        tk.Label(f_closed, text="Closed Trades History", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_WHITE, bg=COLOR_CARD).pack(anchor=tk.W, padx=10, pady=5)

        c_cols = ("exit_time", "symbol", "qty", "entry", "exit", "pnl", "return_pct", "reason")
        self.tree_closed = ttk.Treeview(f_closed, columns=c_cols, show="headings", height=5)
        for c in c_cols:
            self.tree_closed.heading(c, text=c.replace("_", " ").title())
            self.tree_closed.column(c, width=110, anchor=tk.CENTER)
        self.tree_closed.pack(fill=tk.X, padx=10, pady=(0, 8))

        self._refresh_portfolio_tab()

    def _create_metric_card(self, parent: tk.Widget, label: str, val: str, val_color: str) -> tk.Label:
        frame = tk.Frame(parent, bg=COLOR_CARD, padx=16, pady=10)
        frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        tk.Label(frame, text=label, font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor=tk.W)
        lbl_val = tk.Label(frame, text=val, font=("Segoe UI", 15, "bold"), fg=val_color, bg=COLOR_CARD)
        lbl_val.pack(anchor=tk.W, pady=(4, 0))
        return lbl_val

    def _refresh_portfolio_tab(self) -> None:
        p = self.paper_trader.portfolio

        self.card_equity.config(text=f"${p.total_equity:,.2f}")
        self.card_cash.config(text=f"${p.cash:,.2f}")
        pnl_col = COLOR_GREEN if p.total_pnl >= 0 else COLOR_RED
        self.card_pnl.config(text=f"{p.total_pnl_pct:+.2f}% (${p.total_pnl:+.2f})", fg=pnl_col)
        self.card_drawdown.config(text=f"{p.max_drawdown_pct:.2f}%")

        for i in self.tree_pos.get_children():
            self.tree_pos.delete(i)

        for sym, pos in p.positions.items():
            sl_s = f"${pos.stop_loss:.2f}" if pos.stop_loss else "-"
            tp_s = f"${pos.take_profit:.2f}" if pos.take_profit else "-"
            self.tree_pos.insert(
                "",
                tk.END,
                values=(
                    sym,
                    f"{pos.quantity:.4f}",
                    f"${pos.entry_price:.2f}",
                    f"${pos.current_price:.2f}",
                    f"${pos.market_value:,.2f}",
                    f"${pos.unrealized_pnl:+.2f} ({pos.unrealized_pnl_pct:+.2f}%)",
                    sl_s,
                    tp_s,
                ),
            )

        for i in self.tree_closed.get_children():
            self.tree_closed.delete(i)

        for t in reversed(p.closed_trades[-20:]):
            self.tree_closed.insert(
                "",
                tk.END,
                values=(
                    t["timestamp"][:16].replace("T", " "),
                    t["symbol"],
                    str(t["quantity"]),
                    f"${t['entry_price']:.2f}",
                    f"${t['exit_price']:.2f}",
                    f"${t['pnl']:+.2f}",
                    f"{t['pnl_pct']:+.2f}%",
                    t.get("reason", "Manual Close"),
                ),
            )

    def _close_selected_position(self) -> None:
        sel = self.tree_pos.selection()
        if not sel:
            messagebox.showinfo("Select Position", "Please select a position to close.")
            return

        symbol = self.tree_pos.item(sel[0])["values"][0]
        pos = self.paper_trader.portfolio.positions.get(symbol)
        if not pos:
            return

        confirm = messagebox.askyesno(
            "Confirm Close Position",
            f"Are you sure you want to exit position in {symbol} at current price of ${pos.current_price:.2f}?",
        )
        if confirm:
            order = self.paper_trader.execute_sell(symbol, pos.current_price, pos.quantity, reason="User Manual Close")
            if order:
                self.log(f"Position in {symbol} closed manually at ${order.filled_price:.2f}.", level="INFO")
                self._refresh_portfolio_tab()

    def _reset_portfolio(self) -> None:
        confirm = messagebox.askyesno(
            "Reset Portfolio",
            "This will clear all open positions and reset starting cash balance to $10,000.00. Continue?",
        )
        if confirm:
            self.paper_trader.portfolio.cash = 10000.0
            self.paper_trader.portfolio.starting_cash = 10000.0
            self.paper_trader.portfolio.positions.clear()
            self.paper_trader.portfolio.closed_trades.clear()
            self.paper_trader.portfolio.peak_equity = 10000.0
            self.paper_trader.portfolio.max_drawdown_pct = 0.0
            self.paper_trader.save_state()
            self._refresh_portfolio_tab()
            self.log("Paper portfolio successfully reset to $10,000 cash.", level="INFO")

    # -------------------------------------------------------------
    # TAB 4: BACKTEST SIMULATOR
    # -------------------------------------------------------------
    def _init_tab_backtest(self) -> None:
        ctrl = tk.Frame(self.tab_backtest, bg=COLOR_CARD)
        ctrl.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(ctrl, text="Symbol:", font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT, padx=(10, 2))
        self.var_bt_sym = tk.StringVar(value="AAPL")
        tk.Entry(ctrl, textvariable=self.var_bt_sym, width=10, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT, padx=5)

        tk.Label(ctrl, text="Strategy:", font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT, padx=(10, 2))
        self.var_bt_strat = tk.StringVar(value="composite")
        ttk.Combobox(ctrl, textvariable=self.var_bt_strat, values=["composite", "ema", "rsi", "bb", "ai"], width=12, state="readonly").pack(side=tk.LEFT, padx=5)

        tk.Label(ctrl, text="Lookback (Days):", font=("Segoe UI", 9), fg=COLOR_TEXT, bg=COLOR_CARD).pack(side=tk.LEFT, padx=(10, 2))
        self.var_bt_days = tk.IntVar(value=180)
        tk.Spinbox(ctrl, from_=30, to=365, increment=30, textvariable=self.var_bt_days, width=6, bg=COLOR_CARD_HOVER, fg=COLOR_TEXT_WHITE).pack(side=tk.LEFT, padx=5)

        self.btn_run_bt = tk.Button(
            ctrl,
            text="Run Backtest Simulation",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_BLUE,
            fg=COLOR_TEXT_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=self._run_backtest_thread,
        )
        self.btn_run_bt.pack(side=tk.LEFT, padx=15)

        self.bt_results_frame = tk.Frame(self.tab_backtest, bg=COLOR_BG)
        self.bt_results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.lbl_bt_summary = tk.Label(
            self.bt_results_frame,
            text="Select an asset and click 'Run Backtest Simulation' to evaluate historical performance.",
            font=("Segoe UI", 10),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG,
            justify=tk.LEFT,
        )
        self.lbl_bt_summary.pack(anchor=tk.W, padx=10, pady=10)

    def _run_backtest_thread(self) -> None:
        self.btn_run_bt.config(state=tk.DISABLED, text="Simulating...")
        self.lbl_bt_summary.config(text="Running simulation across historical market bars...")

        def _worker():
            try:
                sym = self.var_bt_sym.get().strip().upper()
                strat = self._get_strategy(self.var_bt_strat.get())
                days = self.var_bt_days.get()

                df = self.provider.get_historical_data(sym, period=f"{max(days, 60)}d")
                res = self.backtester.run(sym, df, strat)
                self.root.after(0, self._display_backtest_results, res)
            except Exception as e:
                self.root.after(0, lambda: self.lbl_bt_summary.config(text=f"Simulation error: {e}", fg=COLOR_RED))
            finally:
                self.root.after(0, lambda: self.btn_run_bt.config(state=tk.NORMAL, text="Run Backtest Simulation"))

        threading.Thread(target=_worker, daemon=True).start()

    def _display_backtest_results(self, res) -> None:
        text = (
            f"Asset: {res.symbol}  |  Strategy: {res.strategy_name}  |  Period: {res.start_date[:10]} to {res.end_date[:10]}\n\n"
            f"- Initial Cash: ${res.initial_cash:,.2f}  ->  Final Equity: ${res.final_equity:,.2f}\n"
            f"- Strategy Return: {res.total_return_pct:+.2f}%  vs  Benchmark (Buy & Hold): {res.benchmark_return_pct:+.2f}%\n"
            f"- CAGR: {res.cagr_pct:.2f}%  |  Sharpe Ratio: {res.sharpe_ratio:.2f}  |  Sortino: {res.sortino_ratio:.2f}\n"
            f"- Max Drawdown: {res.max_drawdown_pct:.2f}%\n"
            f"- Total Trades: {res.total_trades}  |  Win Rate: {res.win_rate_pct:.1f}% ({res.winning_trades} wins / {res.losing_trades} losses)\n"
            f"- Profit Factor: {res.profit_factor:.2f}"
        )
        self.lbl_bt_summary.config(text=text, font=("Segoe UI", 11), fg=COLOR_TEXT_WHITE)

    # -------------------------------------------------------------
    # TAB 5: SYSTEM ACTIVITY LOG
    # -------------------------------------------------------------
    def _init_tab_logs(self) -> None:
        ctrl = tk.Frame(self.tab_logs, bg=COLOR_CARD)
        ctrl.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(ctrl, text="Real-Time Event & Execution Feed", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_WHITE, bg=COLOR_CARD).pack(side=tk.LEFT, padx=10, pady=6)

        btn_clear = tk.Button(
            ctrl,
            text="Clear Log",
            font=("Segoe UI", 9),
            bg=COLOR_CARD_HOVER,
            fg=COLOR_TEXT,
            relief=tk.FLAT,
            command=self._clear_logs,
        )
        btn_clear.pack(side=tk.RIGHT, padx=10, pady=6)

        self.txt_log = tk.Text(
            self.tab_logs,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            font=("Consolas", 9),
            wrap=tk.WORD,
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.txt_log.tag_config("SUCCESS", foreground=COLOR_GREEN)
        self.txt_log.tag_config("WARN", foreground=COLOR_GOLD)
        self.txt_log.tag_config("ERROR", foreground=COLOR_RED)
        self.txt_log.tag_config("INFO", foreground=COLOR_TEXT)

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        self.log_queue.put((formatted, level))

    def _process_log_queue(self) -> None:
        try:
            while True:
                formatted, level = self.log_queue.get_nowait()
                self.txt_log.insert(tk.END, formatted + "\n", level)
                self.txt_log.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(200, self._process_log_queue)

    def _clear_logs(self) -> None:
        self.txt_log.delete("1.0", tk.END)

    def _build_statusbar(self) -> None:
        statusbar = tk.Frame(self.root, bg=COLOR_CARD, height=26)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(
            statusbar,
            text="Trading Agent Desktop v0.1.0 | Press 'Save & Apply Settings' to update configuration.",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_CARD,
        ).pack(side=tk.LEFT, padx=10, pady=2)

    # -------------------------------------------------------------
    # BACKGROUND AUTOPILOT
    # -------------------------------------------------------------
    def _start_background_autopilot(self) -> None:
        def _loop():
            time.sleep(3)
            while self.auto_pilot_running:
                if self.settings.auto_trading_enabled:
                    self.log("Background timer: executing scheduled scan & auto-trade cycle...")
                    self.trigger_scan()

                interval_secs = max(60, self.settings.scan_interval_minutes * 60)
                for _ in range(int(interval_secs / 2)):
                    if not self.auto_pilot_running:
                        break
                    time.sleep(2)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()


def launch_gui() -> None:
    root = tk.Tk()
    app = TradingAgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
