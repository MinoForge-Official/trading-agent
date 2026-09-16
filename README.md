<div align="center">

# 🤖 Trading Agent Pro

**An autonomous multi-market algorithmic trading desk with institutional risk barriers, quantitative & AI strategies, and a standalone Windows desktop application.**

[![Author](https://img.shields.io/badge/Author-MinoForge--Official-00c853?style=for-the-badge&logo=github&logoColor=white)](https://github.com/MinoForge-Official)
[![License](https://img.shields.io/badge/License-Custom%20Non--Commercial-red?style=for-the-badge&logo=shield&logoColor=white)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Desktop](https://img.shields.io/badge/Desktop%20App-TradingAgent.exe-purple?style=for-the-badge&logo=windows&logoColor=white)](TradingAgent.exe)

<br/>

[Key Features](#-key-features) •
[Desktop App (.exe)](#-desktop-application-tradingagentexe) •
[Safety Barriers](#-safety-barriers--capital-preservation) •
[Strategies](#-strategies-included) •
[Quick Start](#-quick-start) •
[License](#-license)

---

</div>

## 🌟 Overview

**Trading Agent Pro** by **[MinoForge-Official](https://github.com/MinoForge-Official)** is an autonomous trading framework and desktop application designed for stocks, ETFs, and cryptocurrencies. 

It combines classical quantitative strategies (EMA Trend, RSI Momentum, Bollinger Bands) and AI-assisted market analysis with **institutional-grade capital protection**: every trade is strictly constrained by the **1% risk rule**, dynamic stop-losses, and an automated **drawdown kill-switch**.

It can be run directly as a portable **Windows Desktop Executable (`TradingAgent.exe`)** with an Autonomous Auto-Trading toggle, or automated via **GitHub Actions** for scheduled cloud scanning.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| 📊 **Multi-Market Data** | Live and historical data ingestion for US Equities/ETFs (`yfinance`) and 100+ Cryptocurrencies (`ccxt`). |
| 🛡️ **Institutional Risk Management** | Never blows up accounts: automatically sizes positions to risk $\le 1\%$ of equity, enforces allocation caps, and freezes trading upon reaching max drawdown. |
| 🧠 **Quantitative & AI Brain** | Multi-factor ensemble models pairing technical indicators with optional Google Gemini AI market reasoning. |
| 💻 **Standalone Desktop GUI** | Beautiful dark-mode dashboard with real-time watchlist scans, interactive portfolio tracking, and an Auto-Trading switch. |
| 📈 **Backtest Simulator** | Bar-by-bar historical simulation with realistic slippage, commissions, CAGR, Sharpe ratio, and drawdown metrics. |
| 💼 **Persistent Paper Trading** | Live virtual portfolio tracking open positions, mark-to-market valuations, and automated trailing stop-loss triggers. |
| ☁️ **GitHub Actions Cloud Tool** | Reusable `action.yml` for running scheduled market screening directly in GitHub's free runners. |

---

## 🖥️ Desktop Application (`TradingAgent.exe`)

The desktop app provides a full graphical user interface without requiring terminal commands.

```
+---------------------------------------------------------------------------------------+
|  TRADING AGENT PRO | Autonomous Algorithmic Desk            [● AUTO-TRADING: ACTIVE]  |
+---------------------------------------------------------------------------------------+
| [📊 Live Scanner]  [⚙️ Safety & Settings]  [💼 Portfolio]  [📈 Backtest]  [📜 Log]      |
|                                                                                       |
|  Asset      Signal     Price        Conf.    Stop Loss    Take Profit    Rationale    |
|  BTC-USD   🟢 BUY     $75,700.00   85%      $73,200.00   $81,000.00     Consensus... |
|  NVDA      ⚪ HOLD     $212.15      50%      -            -              Mixed MA...  |
|  AAPL      🔴 SELL    $331.30      80%      $325.00      $342.00        RSI Peak...  |
+---------------------------------------------------------------------------------------+
```

### The 5 Workspaces:
1. **📊 Live Scanner**: Real-time quotes, BUY/SELL/HOLD signal matrix, dynamic stop loss/take profit levels, and one-click manual execution.
2. **⚙️ Safety & Settings**: The control center. Configure risk limits, stop loss %, default strategy, watchlist symbols, and toggle **Autonomous Auto-Trading** on or off.
3. **💼 Paper Portfolio**: Metric cards (Equity, Cash, Return %, Max Drawdown) and live table of active positions with real-time unrealized PnL and emergency exit buttons.
4. **📈 Backtest Simulator**: Test any strategy across 30 to 365 days of real market history to inspect win-rates, Sharpe ratios, and profit factors.
5. **📜 Activity Log**: Live scrolling feed logging every scan, risk check, and executed order with timestamps.

---

## 🛡️ Safety Barriers & Capital Preservation

The trading agent operates under a strict **Zero-Blown-Account Policy**:

* **The 1% Risk Rule**: The agent calculates the distance between the entry price and the stop-loss. It sizes the order so that even if the stop-loss is hit, the account loses **at most 1%** of total equity.
* **Max Allocation Ceiling**: No individual asset can exceed **20%** of total portfolio value.
* **Circuit Breaker Kill-Switch**: If cumulative account drawdown reaches **15%** from its peak equity, all new buy orders are automatically frozen to preserve capital.
* **Risk/Reward Threshold**: All trades require a minimum **1.5:1** reward-to-risk ratio.

---

## 📐 Strategies Included

| Strategy | Logic & Indicator Triggers |
| :--- | :--- |
| **`EMA_Trend`** | Fast (12) / Slow (26) EMA crossover filtered by the macro trend (EMA 50/200) with dynamic ATR trailing stops. |
| **`RSI_Oscillator`** | Momentum mean-reversion catching oversold bounces ($<30$) and overbought exhaustion ($>70$) with MACD confirmation. |
| **`Bollinger_Bands`** | Volatility squeeze breakouts and 2-standard-deviation statistical mean-reversion. |
| **`Composite_Ensemble`** | Weighted multi-factor consensus combining Trend (40%), Momentum (35%), and Volatility (25%). |
| **`AI_Agent_Reasoning`** | Synthesizes technical setups into structured natural language theses (supports Google Gemini 2.5 Flash). |

---

## 🚀 Quick Start

### Method 1: Desktop App (No Python Required)
1. Download or launch [`TradingAgent.exe`](TradingAgent.exe).
2. Configure your risk limits in the **Safety & Settings** tab.
3. Toggle **Autonomous Trading** ON if you want the agent to auto-trade, or leave it in Advisory mode.
4. Click **Scan Watchlist Now**!

### Method 2: Developer / CLI Mode
Clone the repository and install dependencies with `uv` or `pip`:

```bash
# Clone the repository
git clone https://github.com/MinoForge-Official/trading-agent.git
cd trading-agent

# Install dependencies in editable mode
pip install -e .
```

#### Run CLI Commands:
```bash
# Live Market Scan
python -m trading_agent.cli.main scan --symbols "AAPL,MSFT,NVDA,BTC-USD" --strategy composite

# Historical Backtest
python -m trading_agent.cli.main backtest --symbol "AAPL" --strategy ema --days 180

# View Portfolio
python -m trading_agent.cli.main portfolio

# Launch Desktop GUI
python run_gui.py
```

---

## 🧪 Testing

The repository comes with a comprehensive unit test suite:

```bash
pytest -v tests/
```
```
tests/test_backtester.py PASSED
tests/test_config.py PASSED
tests/test_github_reporter.py PASSED
tests/test_market_data.py PASSED
tests/test_paper_trader.py PASSED
tests/test_risk_manager.py PASSED
tests/test_strategies.py PASSED
======================== 16 passed ========================
```

---

## 📄 License

**CUSTOM SOURCE-AVAILABLE & NON-COMMERCIAL LICENSE**  
Copyright (c) 2026 **[MinoForge-Official](https://github.com/MinoForge-Official)**. All Rights Reserved.

- **Permitted**: Viewing, downloading, and internal non-commercial personal development/testing.
- **Prohibited**: Commercial exploitation, monetization, re-uploading/redistribution to third-party repositories, or false attribution.

See the complete terms in the [`LICENSE`](LICENSE) file.