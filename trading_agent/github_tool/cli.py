"""Command line runner optimized for GitHub Actions execution."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List
import requests

from trading_agent.core.market_data import MarketDataProvider
from trading_agent.core.models import Action, MarketSignal
from trading_agent.engine.backtester import Backtester
from trading_agent.engine.paper_trader import PaperTrader
from trading_agent.github_tool.reporter import GitHubReporter
from trading_agent.strategies.ai_agent import AIAgentStrategy
from trading_agent.strategies.base import BaseStrategy
from trading_agent.strategies.technical import (
    BollingerBandStrategy,
    CompositeStrategy,
    EMATrendStrategy,
    RSIOscillatorStrategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_strategy(name: str) -> BaseStrategy:
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


def post_github_issue(title: str, body: str, token: str, repo: str) -> bool:
    """Post an alert issue to GitHub repository."""
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.post(url, headers=headers, json={"title": title, "body": body})
    if resp.status_code == 201:
        logger.info(f"Successfully posted GitHub Issue: {title}")
        return True
    else:
        logger.error(f"Failed to post GitHub Issue ({resp.status_code}): {resp.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Trading Agent GitHub Actions Tool")
    parser.add_argument(
        "--symbols",
        type=str,
        default="AAPL,MSFT,NVDA,BTC-USD",
        help="Comma-separated list of symbols to analyze",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="composite",
        choices=["ema", "rsi", "bb", "composite", "ai"],
        help="Strategy to run",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="scan",
        choices=["scan", "backtest", "paper-trade"],
        help="Action mode",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Historical lookback days for backtesting",
    )
    parser.add_argument(
        "--create-issue-alert",
        action="store_true",
        help="Create a GitHub Issue if high-conviction buy/sell signals occur",
    )
    parser.add_argument(
        "--summary-file",
        type=str,
        default=None,
        help="Path to save markdown report (defaults to GITHUB_STEP_SUMMARY env var)",
    )

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    strategy = get_strategy(args.strategy)
    provider = MarketDataProvider()
    reporter = GitHubReporter(summary_path=args.summary_file)

    logger.info(f"Running Trading Agent in '{args.mode}' mode with strategy '{strategy.name}' on {symbols}")

    if args.mode == "scan":
        signals: List[MarketSignal] = []
        for sym in symbols:
            try:
                df = provider.get_historical_data(sym, period="6mo")
                signal = strategy.evaluate(sym, df)
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error evaluating {sym}: {e}")

        report_md = reporter.format_scan_report(signals, strategy_name=strategy.name)
        print("\n" + report_md + "\n")
        reporter.write_to_github_summary(report_md)

        # Issue alert if requested
        if args.create_issue_alert:
            high_conf = [s for s in signals if s.confidence >= 0.75 and s.action in [Action.BUY, Action.SELL]]
            if high_conf:
                payload = reporter.generate_issue_payload(high_conf)
                token = os.getenv("GITHUB_TOKEN")
                repo = os.getenv("GITHUB_REPOSITORY")
                if token and repo and payload:
                    post_github_issue(payload["title"], payload["body"], token, repo)
                else:
                    logger.warning("GITHUB_TOKEN or GITHUB_REPOSITORY missing; skipping issue creation.")

    elif args.mode == "backtest":
        backtester = Backtester()
        all_reports = []
        for sym in symbols:
            try:
                df = provider.get_historical_data(sym, period=f"{max(args.days, 60)}d")
                res = backtester.run(sym, df, strategy)
                md = reporter.format_backtest_report(res)
                print("\n" + md + "\n")
                all_reports.append(md)
            except Exception as e:
                logger.error(f"Error backtesting {sym}: {e}")

        if all_reports:
            reporter.write_to_github_summary("\n\n---\n\n".join(all_reports))

    elif args.mode == "paper-trade":
        trader = PaperTrader(storage_file="portfolio_state.json")
        current_prices = {}
        for sym in symbols:
            try:
                df = provider.get_historical_data(sym, period="3mo")
                price = float(df["Close"].iloc[-1])
                current_prices[sym] = price
                sig = strategy.evaluate(sym, df)
                trader.process_signal(sig)
            except Exception as e:
                logger.error(f"Error processing paper trade for {sym}: {e}")

        trader.update_prices(current_prices)
        port_md = reporter.format_portfolio_report(trader.portfolio)
        print("\n" + port_md + "\n")
        reporter.write_to_github_summary(port_md)


if __name__ == "__main__":
    main()