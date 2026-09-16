"""GitHub Actions Step Summary and Alert Issue reporter."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from trading_agent.core.models import Action, BacktestResult, MarketSignal, Portfolio


class GitHubReporter:
    """Formats trading agent findings into GitHub Markdown tables, step summaries, and issue alerts."""

    def __init__(self, summary_path: Optional[str] = None):
        self.summary_path = summary_path or os.getenv("GITHUB_STEP_SUMMARY")

    def write_to_github_summary(self, markdown_content: str) -> None:
        """Write markdown to GitHub Actions $GITHUB_STEP_SUMMARY environment file."""
        if self.summary_path:
            with open(self.summary_path, "a", encoding="utf-8") as f:
                f.write(markdown_content + "\n\n")

    def format_scan_report(
        self,
        signals: List[MarketSignal],
        strategy_name: str,
    ) -> str:
        """Create a GitHub Markdown report of scanned assets."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        buy_signals = [s for s in signals if s.action == Action.BUY]
        sell_signals = [s for s in signals if s.action == Action.SELL]
        hold_signals = [s for s in signals if s.action == Action.HOLD]

        lines = [
            f"# Trading Agent Market Scan Report",
            f"> **Strategy:** `{strategy_name}` | **Scan Time:** {now} | **Assets Analyzed:** {len(signals)}",
            "",
            "## Executive Summary",
            f"- **Buy Opportunities:** {len(buy_signals)}",
            f"- **Sell / Profit-Taking:** {len(sell_signals)}",
            f"- **Neutral / Hold:** {len(hold_signals)}",
            "",
            "## Market Signals & Recommendations",
            "| Asset | Action | Price | Conf. | Stop Loss | Take Profit | Key Drivers / Thesis |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]

        for s in signals:
            if s.action == Action.BUY:
                badge = "**[BUY]**"
            elif s.action == Action.SELL:
                badge = "**[SELL]**"
            else:
                badge = "[HOLD]"

            sl_str = f"${s.stop_loss:.2f}" if s.stop_loss else "-"
            tp_str = f"${s.take_profit:.2f}" if s.take_profit else "-"
            conf_pct = f"{s.confidence * 100:.0f}%"

            lines.append(
                f"| **{s.symbol}** | {badge} | ${s.price:.2f} | {conf_pct} | {sl_str} | {tp_str} | {s.reason} |"
            )

        lines.extend([
            "",
            "> [!NOTE]",
            "> *All signals are generated for automated screening and simulated testing. Follow strict risk controls.*",
        ])

        return "\n".join(lines)

    def format_backtest_report(self, result: BacktestResult) -> str:
        """Format backtest result into a GitHub Step Summary."""
        lines = [
            f"# Backtest Performance: `{result.symbol}`",
            f"> **Strategy:** `{result.strategy_name}` | **Period:** {result.start_date[:10]} to {result.end_date[:10]}",
            "",
            "## Key Performance Metrics",
            "| Metric | Strategy | Benchmark (Buy & Hold) |",
            "| :--- | :---: | :---: |",
            f"| **Total Return** | **{result.total_return_pct:+.2f}%** | {result.benchmark_return_pct:+.2f}% |",
            f"| **CAGR (Annualized)** | {result.cagr_pct:.2f}% | - |",
            f"| **Sharpe Ratio** | {result.sharpe_ratio:.2f} | - |",
            f"| **Sortino Ratio** | {result.sortino_ratio:.2f} | - |",
            f"| **Max Drawdown** | `{result.max_drawdown_pct:.2f}%` | - |",
            f"| **Win Rate** | {result.win_rate_pct:.1f}% ({result.winning_trades}/{result.total_trades}) | - |",
            f"| **Profit Factor** | {result.profit_factor:.2f} | - |",
            f"| **Initial / Final Capital** | ${result.initial_cash:,.2f} | **${result.final_equity:,.2f}** |",
            "",
        ]

        if result.trades:
            lines.extend([
                "### Recent Executed Trades",
                "| Exit Date | Entry | Exit | Qty | PnL ($) | Return (%) | Outcome |",
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
            ])
            for t in result.trades[-8:]:
                outcome = "WIN" if t["type"] == "WIN" else "LOSS"
                lines.append(
                    f"| {t['exit_time'][:10]} | ${t['entry_price']:.2f} | ${t['exit_price']:.2f} | {t['quantity']} | ${t['pnl']:+.2f} | {t['pnl_pct']:+.2f}% | {outcome} |"
                )

        return "\n".join(lines)

    def format_portfolio_report(self, portfolio: Portfolio) -> str:
        """Format live simulated portfolio state."""
        lines = [
            "# Trading Agent Portfolio State",
            f"> **Total Equity:** **${portfolio.total_equity:,.2f}** | **Cash:** ${portfolio.cash:,.2f} | **Total Return:** {portfolio.total_pnl_pct:+.2f}%",
            "",
            "## Open Positions",
        ]

        if not portfolio.positions:
            lines.append("_No active open positions. Cash is 100% deployed or idle._")
        else:
            lines.extend([
                "| Asset | Quantity | Avg Entry | Current Price | Market Value | Unrealized PnL | Stop Loss | Take Profit |",
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            ])
            for sym, pos in portfolio.positions.items():
                sl_str = f"${pos.stop_loss:.2f}" if pos.stop_loss else "-"
                tp_str = f"${pos.take_profit:.2f}" if pos.take_profit else "-"
                lines.append(
                    f"| **{sym}** | {pos.quantity:.4f} | ${pos.entry_price:.2f} | ${pos.current_price:.2f} | ${pos.market_value:,.2f} | ${pos.unrealized_pnl:+.2f} ({pos.unrealized_pnl_pct:+.2f}%) | {sl_str} | {tp_str} |"
                )

        lines.extend([
            "",
            f"**Max Peak Equity Recorded:** ${portfolio.peak_equity:,.2f}  ",
            f"**Historical Max Drawdown:** {portfolio.max_drawdown_pct:.2f}%  ",
            f"**Total Realized Closed Trades:** {len(portfolio.closed_trades)}  ",
        ])

        return "\n".join(lines)

    def generate_issue_payload(self, high_conviction_signals: List[MarketSignal]) -> Optional[Dict[str, str]]:
        """Generate title and markdown body for a GitHub Issue alert."""
        if not high_conviction_signals:
            return None

        symbols = ", ".join(s.symbol for s in high_conviction_signals)
        title = f"[Alert] High-Conviction Signal for {symbols}"
        body = [
            f"# High-Conviction Market Alert",
            f"The trading agent detected {len(high_conviction_signals)} high-confidence signal(s):",
            "",
        ]
        for s in high_conviction_signals:
            body.append(f"### {s.symbol} - {s.action.value} ({s.confidence*100:.0f}% Confidence)")
            body.append(f"- **Price:** ${s.price:.2f}")
            if s.stop_loss:
                body.append(f"- **Stop Loss:** ${s.stop_loss:.2f}")
            if s.take_profit:
                body.append(f"- **Take Profit:** ${s.take_profit:.2f}")
            body.append(f"- **Thesis:** {s.reason}")
            body.append("")

        return {"title": title, "body": "\n".join(body)}