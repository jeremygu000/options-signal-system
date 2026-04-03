# Options Signal System

Rule-based options trading signal scanner. Evaluates market regime (QQQ + VIX), applies per-symbol directional strategies, and outputs clear, actionable signals with options structure suggestions. **This is a signal system, not an auto-execution system.**

## Features

- **Market regime detection** — Classifies current environment as `risk_on`, `neutral`, or `risk_off` using QQQ trend and VIX levels
- **Per-symbol strategies** — Bearish setups (USO, XOM, XLE) and bullish setups (CRM) with transparent scoring
- **Signal levels** — Strong signal / Watch signal / No signal, with full rationale
- **Options structure suggestions** — Bear Call Spread, Put Debit Spread, Bull Call Spread, etc.
- **Multi-channel notifications** — Telegram bot + WeChat Work (Enterprise WeChat) webhook, silently disabled when unconfigured
- **CLI + loop mode** — One-shot or polling with configurable intervals
- **Market hours filter** — Runs only during US market hours (09:30–16:00 ET, Mon–Fri) by default
- **Web dashboard** — Next.js + MUI real-time dashboard with light/dark theme
- **REST API** — FastAPI server exposing all data for the web UI

## Project Structure

```
options-signal-system/
  app/
    config.py           # Pydantic Settings — env vars + .env file
    models.py           # Signal, MarketRegimeResult, StrategyConfig, enums
    data_provider.py    # Daily data from Parquet store, intraday from yfinance
    indicators.py       # SMA, ATR, VWAP, rolling high/low, prev day high/low
    market_regime.py    # MarketRegimeEngine — QQQ/VIX rule-based scoring
    strategy_engine.py  # StrategyEngine — per-symbol directional scoring
    report.py           # Chinese-language console + notification report builder
    notifier.py         # Telegram + WeChat + CompositeNotifier
    server.py           # FastAPI REST API (port 8200)
    main.py             # CLI entry point
    utils.py            # Timezone helpers, market hours check, logging
  tests/
    test_indicators.py
    test_market_regime.py
    test_strategy_engine.py
  web/                  # Next.js dashboard (see Web Dashboard section)
  pyproject.toml
  requirements.txt
  .env.example
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [yahoo-finance-data](https://github.com/jeremygu000/yahoo-finance-data) package installed and Parquet data populated at `~/.market_data/parquet/`
- Node.js 20+ (for web dashboard)

## Installation

```bash
# Clone and enter project
cd options-signal-system

# Install Python dependencies with uv
uv sync

# Or with pip
pip install -r requirements.txt

# Copy and edit environment file
cp .env.example .env
```

## Running

### CLI — One-shot scan

```bash
python -m app.main                              # Run once (market hours only)
python -m app.main --always-run                 # Run once (ignore market hours)
```

### CLI — Loop mode

```bash
python -m app.main --loop                       # Poll every 600s (default)
python -m app.main --loop --every-seconds 300   # Poll every 5 minutes
python -m app.main --loop --always-run          # Poll outside market hours too
```

### REST API server

```bash
uvicorn app.server:app --host 0.0.0.0 --port 8200 --reload
```

### Web dashboard

```bash
cd web
npm install
npm run dev     # Starts on http://localhost:3000
```

Make sure the FastAPI server is running on port 8200 before starting the dashboard.

## Environment Variables

| Variable             | Default           | Description                                |
| -------------------- | ----------------- | ------------------------------------------ |
| `TELEGRAM_BOT_TOKEN` | _(empty)_         | Telegram bot API token (optional)          |
| `TELEGRAM_CHAT_ID`   | _(empty)_         | Telegram chat/group ID (optional)          |
| `WECHAT_WEBHOOK_URL` | _(empty)_         | WeChat Work robot webhook URL (optional)   |
| `POLL_INTERVAL`      | `600`             | Polling interval in seconds                |
| `SYMBOLS`            | `USO,XOM,XLE,CRM` | Comma-separated symbols to evaluate        |
| `STRONG_ONLY`        | `false`           | Only send notifications for strong signals |

Notifications are silently disabled when tokens/URLs are not configured — no errors.

## REST API Endpoints

| Endpoint                               | Method | Description                                                |
| -------------------------------------- | ------ | ---------------------------------------------------------- |
| `/api/health`                          | GET    | Health check                                               |
| `/api/symbols`                         | GET    | List configured symbols with data availability             |
| `/api/regime`                          | GET    | Current market regime evaluation                           |
| `/api/signals`                         | GET    | Evaluate all symbols                                       |
| `/api/scan`                            | GET    | Full scan — regime + all signals (main dashboard endpoint) |
| `/api/indicators/{symbol}`             | GET    | Technical indicators snapshot for a symbol                 |
| `/api/ohlcv/{symbol}?days=90`          | GET    | OHLCV candlestick data                                     |
| `/api/compare?tickers=QQQ,USO&days=90` | GET    | Normalized price comparison                                |

## Strategy Overview

### Market Regime

The system first evaluates the broad market environment using QQQ and VIX:

| Condition                        | Effect     |
| -------------------------------- | ---------- |
| QQQ 3-day consecutive up closes  | +1 risk_on |
| QQQ above 5-day SMA              | +1 risk_on |
| QQQ broke above last week's high | +1 risk_on |
| VIX below 20                     | +1 risk_on |
| VIX below last week's low        | +1 risk_on |

Opposite conditions score toward risk_off. **Score >= 3 → risk_on**, **score <= -3 → risk_off**, otherwise neutral.

### Symbol Strategies

**Bearish setups (USO, XOM, XLE)** — "Sell the rip"

- Scores based on: proximity to yesterday's high, SMA5/10 death cross, position in 20-day range, VWAP rejection, regime alignment
- Suggested structures: Bear Call Spread, Put Debit Spread

**Bullish setups (CRM)** — "Buy the dip"

- Scores based on: proximity to support (yesterday's low, SMA, 20-day low), VWAP reclaim, price stabilization, regime alignment
- Suggested structures: Bull Call Spread, Call Debit Spread

**Signal thresholds**: Score >= 5 → Strong signal, Score >= 3 → Watch signal, otherwise No signal.

### Sample Output

```
════════════════════════════════════════════
  期权信号系统 — 扫描报告
  2025-04-04 10:30:15 (America/New_York)
════════════════════════════════════════════

▌ 市场环境: NEUTRAL
  QQQ: 478.23  |  VIX: 18.45
  · QQQ 连续3日收阳
  · QQQ 站上5日均线
  · VIX 位于上周低点之上

────────────────────────────────────────────

[强信号] USO | 逢高做空 | 考虑建立熊市价差
  现价: 78.23  |  触发位: 78.10
  建议结构: Bear Call Spread
  执行提示: 可优先观察靠近昨日高点的卖出腿
  原因:
  · 大盘环境为 neutral，允许偏空
  · 当前价格接近昨日高点和5日均线
  · 盘中跌回 VWAP 下方
  · 价格位于近20日高位区域

[观察信号] CRM | 逢低做多 | 关注支撑位企稳
  现价: 265.10  |  触发位: 264.80
  建议结构: Bull Call Spread
  执行提示: 等待价格重新站上 VWAP 后确认
  原因:
  · 价格接近5日均线支撑
  · 盘中回踩后企稳

════════════════════════════════════════════
```

## Web Dashboard

The web dashboard is a Next.js application at `web/` providing real-time visualization:

| Section              | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| Market Regime        | QQQ/VIX environment with color-coded badge and reasons         |
| Signal Dashboard     | Per-symbol signal cards with score, rationale, options hints   |
| Technical Indicators | SMA, ATR, VWAP, range position for each symbol                 |
| Price Charts         | Candlestick + volume charts via TradingView lightweight-charts |
| Price Comparison     | Normalized multi-line comparison of all symbols                |

**Tech stack**: Next.js (App Router), React 19, MUI 7, lightweight-charts 5, TypeScript.

**Dev tooling**: tsgo (typecheck), oxlint (lint), prettier (format).

```bash
cd web
npm run dev           # Development server
npm run build         # Production build
npm run typecheck     # Type checking (tsgo)
npm run lint          # Linting (oxlint)
npm run format        # Format (prettier)
npm run format:check  # Check formatting
```

## Development

### Python tooling

```bash
uv run pytest                    # Run tests
uv run black app/ tests/         # Format
uv run mypy app/                 # Type check
```

### Code quality

| Tool     | Command                       | Scope                              |
| -------- | ----------------------------- | ---------------------------------- |
| pytest   | `uv run pytest`               | Unit tests (22 tests)              |
| black    | `uv run black app/ tests/`    | Code formatting                    |
| mypy     | `uv run mypy app/`            | Static type checking (strict mode) |
| tsgo     | `npm run typecheck` (in web/) | TypeScript type checking           |
| oxlint   | `npm run lint` (in web/)      | Fast JavaScript/TypeScript linting |
| prettier | `npm run format` (in web/)    | Code formatting                    |

## Data Source

Daily OHLCV data is read from `~/.market_data/parquet/` (shared with the [yahoo-finance-data](https://github.com/jeremygu000/yahoo-finance-data) project). Intraday data (15-minute bars) is fetched live from Yahoo Finance via `yfinance`.

Required tickers in the Parquet store: `QQQ`, `VIX` (stored as `VIX.parquet` from `^VIX`), `USO`, `XOM`, `XLE`, `CRM`.

## Important Notes

- This is a **signal system only** — no auto-execution, no order placement
- No real options chain data — structure suggestions are rule-based recommendations
- Daily data depends on the Parquet store being populated (run yahoo-finance-data's data update first)
- Intraday data requires market hours for meaningful VWAP calculations
- Scoring thresholds and rules are configurable — edit `strategy_engine.py` to tune

## Future Extensions

- **IBKR integration** — Connect to Interactive Brokers for live options chain data and real strike selection
- **Options chain analysis** — Fetch actual option prices, implied volatility, Greeks
- **Database storage** — Persist signals to SQLite/PostgreSQL for historical analysis
- **Backtesting** — Replay signals against historical data to validate strategy performance
- **Additional symbols** — Add more ETFs, stocks, or sector-specific strategies
- **Web UI enhancements** — Signal history view, alert management, strategy parameter tuning
- **Scheduled execution** — launchd/systemd/cron for automated periodic scanning
