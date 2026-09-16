# 🤖 Trading Agent & GitHub Tool

[![CI Test Suite](https://github.com/your-username/trading-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/trading-agent/actions/workflows/ci.yml)
[![Scheduled Scanner](https://github.com/your-username/trading-agent/actions/workflows/market-agent.yml/badge.svg)](https://github.com/your-username/trading-agent/actions/workflows/market-agent.yml)
[![License: Custom Non-Commercial](https://img.shields.io/badge/License-Custom%20Non--Commercial-red.svg)](LICENSE)
[![Author: MinoForge-Official](https://img.shields.io/badge/Author-MinoForge--Official-blue.svg)](https://github.com/MinoForge-Official)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

An autonomous, multi-market algorithmic trading framework equipped with technical strategies, AI-assisted market analysis, risk management, historical backtesting, simulated paper trading, and **automated GitHub Actions integration**.

---

## ✨ Key Features

- **Multi-Market Support**: Native analysis for US Equities, ETFs, and Indices (via `yfinance`) and Cryptocurrencies (via `ccxt` / Yahoo Finance).
- **Quantitative & AI Strategies**:
  - `EMA_Trend`: Fast/Slow moving average crossover with ATR trailing stops.
  - `RSI_Oscillator`: Momentum oversold/overbought mean reversion.
  - `Bollinger_Bands`: Volatility squeeze and band breakouts.
  - `Composite_Ensemble`: Multi-factor weighted consensus model.
  - `AI_Agent_Reasoning`: Synthesizes technical indicators into reasoned theses (optional Gemini LLM integration).
- **Institutional-Grade Risk Manager**:
  - Fixed-risk position sizing (e.g. 1% equity risked per trade).
  - Maximum allocation cap per asset.
  - Circuit Breaker: Portfolio max drawdown kill-switch halting buys during sustained market drops.
  - Risk/Reward ratio qualification filter.
- **Engine**:
  - Realistic historical backtesting with slippage, transaction fees, CAGR, Sharpe ratio, Sortino ratio, max drawdown, and win-rate.
  - Persistent paper trading simulation tracking open positions and real-time mark-to-market valuations.
- **GitHub Tool & Action**:
  - Reusable GitHub Action (`action.yml`).
  - Automated GitHub Step Summary generation (`$GITHUB_STEP_SUMMARY`).
  - Automated GitHub Issue trade alerts for high-conviction signals.
  - Scheduled daily market scans running on GitHub's free runners (`.github/workflows/market-agent.yml`).

---

## 🚀 Quick Start

### 1. Installation

Using `uv` (recommended) or standard `pip`:

```bash
# Clone the repository
git clone https://github.com/your-username/trading-agent.git
cd trading-agent

# Create virtual environment and install
uv venv
uv pip install -e .
```

---

## 💻 CLI Usage

### Market Scanner
Scan a watchlist of stocks or crypto pairs:

```bash
python -m trading_agent.cli.main scan --symbols "AAPL,MSFT,NVDA,BTC-USD" --strategy composite
```

### Backtest a Strategy
Simulate 180 days of historical trading on an asset:

```bash
python -m trading_agent.cli.main backtest --symbol "AAPL" --strategy rsi --days 180 --cash 10000
```

### View Paper Trading Portfolio
Inspect current positions, unrealized PnL, and cash balance:

```bash
python -m trading_agent.cli.main portfolio
```

---

## 🛠️ GitHub Actions Integration

### Using as a Reusable Action in any Workflow

Add this step to any `.github/workflows/trade.yml`:

```yaml
name: Market Scan
on:
  schedule:
    - cron: "30 21 * * 1-5" # Daily after US market close
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./
        with:
          symbols: "AAPL,MSFT,NVDA,BTC-USD,ETH-USD"
          strategy: "composite"
          mode: "scan"
          create-issue-alert: "true"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### GitHub Step Summary Output
When the workflow runs, it automatically formats and attaches a beautiful Markdown table directly inside the GitHub Actions run summary tab:

| Asset | Action | Price | Conf. | Stop Loss | Take Profit | Key Drivers / Thesis |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **BTC-USD** | 🟢 **BUY** | $64,250.00 | 85% | $62,100.00 | $68,500.00 | Multi-factor bullish consensus. EMA: BUY, RSI: BUY. |
| **AAPL** | ⚪ HOLD | $182.10 | 50% | - | - | Price within normal volatility band. |

---

## 🧪 Running Tests

```bash
pytest -v tests/
```

---

## 📄 License

CUSTOM SOURCE-AVAILABLE & NON-COMMERCIAL LICENSE.  
Copyright (c) 2026 [MinoForge-Official](https://github.com/MinoForge-Official). All Rights Reserved.  
See [`LICENSE`](LICENSE) for complete terms, conditions, and prohibited uses.