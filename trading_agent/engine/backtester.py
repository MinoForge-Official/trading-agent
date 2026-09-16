"""Backtesting engine for simulating and evaluating trading strategies on historical data."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from trading_agent.core.models import Action, BacktestResult, MarketSignal
from trading_agent.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class Backtester:
    """Simulates strategy execution over historical candle data with fees, slippage, and performance metrics."""

    def __init__(
        self,
        initial_cash: float = 10000.0,
        fee_pct: float = 0.001,       # 0.1% commission fee
        slippage_pct: float = 0.0005,  # 0.05% slippage
        risk_free_rate: float = 0.03,
    ):
        self.initial_cash = initial_cash
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.risk_free_rate = risk_free_rate

    def run(self, symbol: str, data: pd.DataFrame, strategy: BaseStrategy) -> BacktestResult:
        """Run backtest for strategy across the given DataFrame."""
        if len(data) < 30:
            raise ValueError(f"Insufficient historical data: need at least 30 bars, got {len(data)}")

        cash = self.initial_cash
        position_qty = 0.0
        position_entry_price = 0.0
        trades: List[Dict] = []
        equity_curve: List[Dict] = []

        peak_equity = self.initial_cash
        max_drawdown = 0.0

        for i in range(25, len(data)):
            window = data.iloc[: i + 1]
            current_bar = data.iloc[i]
            timestamp_str = str(data.index[i])
            close_price = float(current_bar["Close"])

            signal = strategy.evaluate(symbol, window)

            # Execution logic
            if signal.action == Action.BUY and position_qty == 0:
                # Buy with 95% of available cash
                exec_price = close_price * (1 + self.slippage_pct)
                investable = cash * 0.95
                qty = investable / exec_price

                if qty > 0.0001:
                    fee = (qty * exec_price) * self.fee_pct
                    cost = (qty * exec_price) + fee
                    if cost <= cash:
                        cash -= cost
                        position_qty = qty
                        position_entry_price = exec_price

            elif signal.action == Action.SELL and position_qty > 0:
                exec_price = close_price * (1 - self.slippage_pct)
                proceeds = position_qty * exec_price
                fee = proceeds * self.fee_pct
                net_proceeds = proceeds - fee

                pnl = net_proceeds - (position_qty * position_entry_price)
                pnl_pct = (pnl / (position_qty * position_entry_price)) * 100

                trades.append(
                    {
                        "exit_time": timestamp_str,
                        "entry_price": round(position_entry_price, 2),
                        "exit_price": round(exec_price, 2),
                        "quantity": round(position_qty, 4),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "type": "WIN" if pnl > 0 else "LOSS",
                    }
                )

                cash += net_proceeds
                position_qty = 0.0
                position_entry_price = 0.0

            # Mark to market equity
            current_equity = cash + (position_qty * close_price)
            if current_equity > peak_equity:
                peak_equity = current_equity

            dd = ((peak_equity - current_equity) / peak_equity) * 100 if peak_equity > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

            equity_curve.append(
                {
                    "date": timestamp_str,
                    "equity": round(current_equity, 2),
                    "cash": round(cash, 2),
                    "close": round(close_price, 2),
                }
            )

        # Close any open position at the end
        final_price = float(data["Close"].iloc[-1])
        if position_qty > 0:
            proceeds = position_qty * final_price * (1 - self.slippage_pct)
            fee = proceeds * self.fee_pct
            net = proceeds - fee
            pnl = net - (position_qty * position_entry_price)
            trades.append(
                {
                    "exit_time": str(data.index[-1]),
                    "entry_price": round(position_entry_price, 2),
                    "exit_price": round(final_price, 2),
                    "quantity": round(position_qty, 4),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (position_qty * position_entry_price)) * 100, 2),
                    "type": "WIN" if pnl > 0 else "LOSS",
                }
            )
            cash += net

        final_equity = cash
        total_return_pct = ((final_equity - self.initial_cash) / self.initial_cash) * 100

        # Benchmark return
        start_price = float(data["Close"].iloc[25])
        benchmark_return_pct = ((final_price - start_price) / start_price) * 100

        # Performance statistics
        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0.0

        gross_profits = sum(t["pnl"] for t in winning_trades)
        gross_losses = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)

        # Sharpe & Sortino
        eq_df = pd.DataFrame(equity_curve)
        if len(eq_df) > 1:
            returns = eq_df["equity"].pct_change().dropna()
            mean_ret = returns.mean()
            std_ret = returns.std()
            neg_returns = returns[returns < 0]
            downside_std = neg_returns.std() if not neg_returns.empty else 1e-6

            daily_rf = self.risk_free_rate / 252.0
            sharpe = float(((mean_ret - daily_rf) / (std_ret + 1e-10)) * np.sqrt(252))
            sortino = float(((mean_ret - daily_rf) / (downside_std + 1e-10)) * np.sqrt(252))
        else:
            sharpe = 0.0
            sortino = 0.0

        # Annualized CAGR
        days = max(1, (data.index[-1] - data.index[25]).days)
        years = days / 365.25
        cagr = (((final_equity / self.initial_cash) ** (1 / years)) - 1) * 100 if years > 0 and final_equity > 0 else 0.0

        return BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start_date=str(data.index[25]),
            end_date=str(data.index[-1]),
            initial_cash=round(self.initial_cash, 2),
            final_equity=round(final_equity, 2),
            total_return_pct=round(total_return_pct, 2),
            cagr_pct=round(cagr, 2),
            benchmark_return_pct=round(benchmark_return_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            win_rate_pct=round(win_rate, 1),
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            profit_factor=round(profit_factor, 2),
            trades=trades,
            equity_curve=equity_curve,
        )