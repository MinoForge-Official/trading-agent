"""User-facing CLI interface for the Trading Agent using Rich."""

from __future__ import annotations

import argparse
import sys
from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading_agent.core.market_data import MarketDataProvider
from trading_agent.core.models import Action
from trading_agent.engine.backtester import Backtester
from trading_agent.engine.paper_trader import PaperTrader
from trading_agent.strategies.ai_agent import AIAgentStrategy
from trading_agent.strategies.base import BaseStrategy
from trading_agent.strategies.technical import (
    BollingerBandStrategy,
    CompositeStrategy,
    EMATrendStrategy,
    RSIOscillatorStrategy,
)

console = Console()


def resolve_strategy(name: str) -> BaseStrategy:
    name = name.lower()
    if name == "ema":
        return EMATrendStrategy()
    elif name == "rsi":
        return RSIOscillatorStrategy()
    elif name == "bb":
        return BollingerBandStrategy()
    elif name == "ai":
        return AIAgentStrategy()
    return CompositeStrategy()


def cmd_scan(args: argparse.Namespace) -> None:
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    strategy = resolve_strategy(args.strategy)
    provider = MarketDataProvider()

    console.print(
        Panel(
            f"[bold cyan]Market Scanner[/bold cyan] | Strategy: [yellow]{strategy.name}[/yellow] | Watchlist: [green]{', '.join(symbols)}[/green]",
            border_style="cyan",
        )
    )

    table = Table(title="Live Market Signal Matrix", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="bold")
    table.add_column("Action", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Conf.", justify="center")
    table.add_column("Stop Loss", justify="right")
    table.add_column("Take Profit", justify="right")
    table.add_column("Key Rationale / Drivers", justify="left")

    for sym in symbols:
        with console.status(f"Fetching & analyzing [yellow]{sym}[/yellow]..."):
            try:
                df = provider.get_historical_data(sym, period="6mo")
                sig = strategy.evaluate(sym, df)

                if sig.action == Action.BUY:
                    action_display = "[bold green]BUY[/bold green]"
                elif sig.action == Action.SELL:
                    action_display = "[bold red]SELL[/bold red]"
                else:
                    action_display = "[dim white]HOLD[/dim white]"

                sl_txt = f"${sig.stop_loss:.2f}" if sig.stop_loss else "-"
                tp_txt = f"${sig.take_profit:.2f}" if sig.take_profit else "-"
                conf_txt = f"{sig.confidence*100:.0f}%"

                table.add_row(
                    sym,
                    action_display,
                    f"${sig.price:.2f}",
                    conf_txt,
                    sl_txt,
                    tp_txt,
                    sig.reason[:80] + ("..." if len(sig.reason) > 80 else ""),
                )
            except Exception as e:
                table.add_row(sym, "[red]ERROR[/red]", "-", "-", "-", "-", str(e))

    console.print(table)


def cmd_backtest(args: argparse.Namespace) -> None:
    symbol = args.symbol.strip().upper()
    strategy = resolve_strategy(args.strategy)
    provider = MarketDataProvider()
    backtester = Backtester(initial_cash=args.cash)

    console.print(
        Panel(
            f"[bold cyan]Backtest Simulator[/bold cyan] | Asset: [bold yellow]{symbol}[/bold yellow] | Strategy: [magenta]{strategy.name}[/magenta] | Period: [green]{args.days} days[/green]",
            border_style="cyan",
        )
    )

    with console.status(f"Running backtest for [yellow]{symbol}[/yellow]..."):
        df = provider.get_historical_data(symbol, period=f"{max(args.days, 60)}d")
        result = backtester.run(symbol, df, strategy)

    # Metrics Table
    m_table = Table(title=f"Performance Summary: {symbol}", show_header=True, header_style="bold blue")
    m_table.add_column("Metric", style="bold")
    m_table.add_column("Value", justify="right")

    m_table.add_row("Initial Cash", f"${result.initial_cash:,.2f}")
    m_table.add_row("Final Equity", f"${result.final_equity:,.2f}")
    ret_color = "green" if result.total_return_pct >= 0 else "red"
    m_table.add_row("Strategy Total Return", f"[{ret_color}]{result.total_return_pct:+.2f}%[/{ret_color}]")
    m_table.add_row("Benchmark Return", f"{result.benchmark_return_pct:+.2f}%")
    m_table.add_row("CAGR", f"{result.cagr_pct:.2f}%")
    m_table.add_row("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
    m_table.add_row("Sortino Ratio", f"{result.sortino_ratio:.2f}")
    m_table.add_row("Max Drawdown", f"[red]{result.max_drawdown_pct:.2f}%[/red]")
    m_table.add_row("Total Trades", str(result.total_trades))
    m_table.add_row("Win Rate", f"{result.win_rate_pct:.1f}% ({result.winning_trades} wins)")
    m_table.add_row("Profit Factor", f"{result.profit_factor:.2f}")

    console.print(m_table)

    if result.trades:
        t_table = Table(title="Recent Trades (Last 5)", show_header=True)
        t_table.add_column("Date", justify="center")
        t_table.add_column("Entry", justify="right")
        t_table.add_column("Exit", justify="right")
        t_table.add_column("Qty", justify="right")
        t_table.add_column("PnL ($)", justify="right")
        t_table.add_column("Return (%)", justify="right")
        t_table.add_column("Result", justify="center")

        for t in result.trades[-5:]:
            col = "green" if t["pnl"] > 0 else "red"
            t_table.add_row(
                t["exit_time"][:10],
                f"${t['entry_price']:.2f}",
                f"${t['exit_price']:.2f}",
                str(t["quantity"]),
                f"[{col}]${t['pnl']:+.2f}[/{col}]",
                f"[{col}]{t['pnl_pct']:+.2f}%[/{col}]",
                f"[{col}]{t['type']}[/{col}]",
            )
        console.print(t_table)


def cmd_portfolio(args: argparse.Namespace) -> None:
    trader = PaperTrader(storage_file=args.file)
    p = trader.portfolio

    console.print(
        Panel(
            f"[bold cyan]Simulated Paper Portfolio[/bold cyan] | Total Equity: [bold green]${p.total_equity:,.2f}[/bold green] | Cash: [yellow]${p.cash:,.2f}[/yellow] | Total Return: {p.total_pnl_pct:+.2f}%",
            border_style="green",
        )
    )

    if not p.positions:
        console.print("[dim italic]No active open positions. Cash is 100% available.[/dim italic]")
    else:
        table = Table(title="Open Positions", show_header=True)
        table.add_column("Symbol", style="bold")
        table.add_column("Qty", justify="right")
        table.add_column("Entry Price", justify="right")
        table.add_column("Current Price", justify="right")
        table.add_column("Market Value", justify="right")
        table.add_column("Unrealized PnL", justify="right")
        table.add_column("Stop Loss", justify="right")
        table.add_column("Take Profit", justify="right")

        for sym, pos in p.positions.items():
            pnl_col = "green" if pos.unrealized_pnl >= 0 else "red"
            table.add_row(
                sym,
                f"{pos.quantity:.4f}",
                f"${pos.entry_price:.2f}",
                f"${pos.current_price:.2f}",
                f"${pos.market_value:,.2f}",
                f"[{pnl_col}]${pos.unrealized_pnl:+.2f} ({pos.unrealized_pnl_pct:+.2f}%)[/{pnl_col}]",
                f"${pos.stop_loss:.2f}" if pos.stop_loss else "-",
                f"${pos.take_profit:.2f}" if pos.take_profit else "-",
            )
        console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Trading Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan watchlist symbols for buy/sell opportunities")
    p_scan.add_argument("--symbols", type=str, default="AAPL,MSFT,NVDA,BTC-USD", help="Watchlist symbols")
    p_scan.add_argument("--strategy", type=str, default="composite", choices=["ema", "rsi", "bb", "composite", "ai"])
    p_scan.set_defaults(func=cmd_scan)

    # backtest
    p_bt = subparsers.add_parser("backtest", help="Simulate historical strategy performance")
    p_bt.add_argument("--symbol", type=str, default="AAPL", help="Ticker symbol")
    p_bt.add_argument("--strategy", type=str, default="composite", choices=["ema", "rsi", "bb", "composite", "ai"])
    p_bt.add_argument("--days", type=int, default=180, help="Lookback days")
    p_bt.add_argument("--cash", type=float, default=10000.0, help="Starting cash balance")
    p_bt.set_defaults(func=cmd_backtest)

    # portfolio
    p_port = subparsers.add_parser("portfolio", help="View simulated paper trading portfolio")
    p_port.add_argument("--file", type=str, default="portfolio_state.json", help="Path to portfolio JSON file")
    p_port.set_defaults(func=cmd_portfolio)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()