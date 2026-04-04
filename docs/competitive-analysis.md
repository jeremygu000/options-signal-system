# Competitive Analysis: Options Signal System vs Industry

> Generated: 2026-04-04 | Updated: 2026-04-05 | Based on analysis of 12+ open-source projects

## 1. Competitive Landscape

### Tier 1: Full-Featured Platforms (1,000+ Stars)

| Project | Stars | Focus | Tech Stack | URL |
|---------|-------|-------|------------|-----|
| **OpenBB** | 64,900⭐ | Full-stack financial data platform | Python, FastAPI | github.com/OpenBB-finance/OpenBB |
| **freqtrade** | 48,300⭐ | Crypto trading bot | Python, FastAPI | github.com/freqtrade/freqtrade |
| **backtrader** | 21,000⭐ | Strategy backtesting engine | Python, pandas | github.com/mementum/backtrader |
| **Lean (QuantConnect)** | 18,200⭐ | Multi-asset quant engine | C#/Python | github.com/QuantConnect/Lean |
| **backtesting.py** | 8,100⭐ | Lightweight backtesting | Python, NumPy | github.com/kernc/backtesting.py |
| **jesse** | 7,600⭐ | Crypto trading framework | Python | github.com/jesse-ai/jesse |
| **blankly** | 2,400⭐ | Multi-asset trading framework | Python, FastAPI | github.com/blankly-finance/blankly |
| **optopsy** | 1,297⭐ | Options backtesting | Python | github.com/goldspanlabs/optopsy |

### Tier 2: Options-Specific Tools (100-500 Stars)

| Project | Stars | Focus | URL |
|---------|-------|-------|-----|
| **optionlab** | 487⭐ | Options strategy evaluation + payoff visualization | github.com/rgaveiga/optionlab |
| **py_vollib** | 392⭐ | Black-Scholes pricing + Greeks calculation | github.com/vollib/py_vollib |
| **options-implied-probability** | 330⭐ | IV surface fitting + probability extraction | github.com/tyrneh/options-implied-probability |
| **mibian** | 288⭐ | Lightweight options pricing | github.com/yassinemaaroufi/MibianLib |
| **pyBlackScholesAnalytics** | 125⭐ | Greeks aggregation for portfolios | github.com/gabrielepompa88/pyBlackScholesAnalytics |
| **alpacahq/options-wheel** | 107⭐ | Automated Wheel strategy | github.com/alpacahq/options-wheel |

---

## 2. Feature Comparison Matrix

| Capability | Our System | OpenBB | Lean | backtrader | optopsy | blankly |
|-----------|-----------|--------|------|-----------|---------|---------|
| Market Regime Detection | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ | ❌ |
| Options Signal Generation | ✅ STRONG/WATCH | ❌ | Partial | ❌ | ❌ | ❌ |
| Multi-Symbol Scanning | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| REST API | ✅ FastAPI | ✅ | ✅ | ❌ | ❌ | ✅ |
| Notifications (TG/WeChat) | ✅ | Partial | ❌ | ❌ | ❌ | ✅ |
| Strategy Backtesting | ✅ Signal replay + walk-forward | ✅ | ✅ | ✅ | ✅ | ✅ |
| Live Trading | ✅ Alpaca Paper | ✅ | ✅ IB | ✅ IB | ❌ | ✅ Alpaca |
| Greeks Calculation | ✅ BS model | ✅ | ✅ | ❌ | ✅ | ❌ |
| Implied Volatility | ✅ IV percentile | ✅ | ✅ | ❌ | ✅ | ❌ |
| Options Chain Data | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Multi-Leg Strategies | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Fundamental Data | ✅ yfinance | ✅ | ✅ | ❌ | ❌ | ❌ |
| ML/AI Enhancement | ✅ 5 modules | ✅ | ❌ | ❌ | ❌ | ❌ |
| Symbol Discovery | ✅ DuckDB | ✅ | ✅ | ❌ | ❌ | ❌ |
| WebSocket Real-time | ✅ 4 channels | ❌ | ✅ | ❌ | ❌ | ❌ |
| Unusual Volume Detection | ✅ Smart money | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 3. Our Unique Advantages

1. **Market Regime Detection** — Score-based QQQ/VIX regime classification (RISK_ON / RISK_OFF / NEUTRAL) is not found in any major competitor. Only a 74-star `Market-Regime-Detection-System` does something similar.

2. **Chinese Language Support** — Signal reports in Chinese + WeChat Work notifications. No comparable open-source options signal system serves the Chinese-speaking market.

3. **Focused & Lightweight** — Competitors are either too heavy (OpenBB: 64k lines) or too generic (backtrader: just a framework). Our system is opinionated, use-case-focused, and deployable out-of-the-box.

4. **Directional Bias per Symbol** — Unique SHORT_SYMBOLS/LONG_SYMBOLS classification with asymmetric scoring (short vs long setups) is not found in competitors.

---

## 4. Gap Analysis (Ranked by Impact)

### ✅ Resolved Gaps

| # | Gap | Resolution | Module |
|---|-----|-----------|--------|
| 1 | ~~No Backtesting Engine~~ | ✅ Event-driven signal replay with walk-forward analysis, multi-horizon evaluation, equity curve | `app/signal_backtest.py` |
| 2 | ~~No Greeks Calculation~~ | ✅ Black-Scholes Greeks (Delta/Gamma/Theta/Vega/Rho) | `app/greeks.py` + `app/synthetic_options.py` |
| 3 | ~~No Broker Integration~~ | ✅ Alpaca paper trading — account, orders, positions, portfolio history | `app/broker.py` |
| 4 | ~~No Implied Volatility Analysis~~ | ✅ IV percentile ranking, IV surface analysis | `app/iv_analysis.py` |
| 5 | ~~No Options Chain Data~~ | ✅ Real-time options chain with strike/expiry selection | `app/options_data.py` |
| 6 | ~~No Multi-Leg Strategy Support~~ | ✅ Iron Condor, Spreads, Straddle, Strangle, Butterfly | `app/multi_leg.py` |
| 7 | ~~No Position Management / P&L~~ | ✅ Full CRUD position tracking + portfolio summary | `app/positions.py` |
| 8 | ~~No ML/Statistical Enhancement~~ | ✅ 5 modules — signal scoring, regime classification, LLM analysis | `app/ml/` |
| 9 | ~~No Fundamental Data~~ | ✅ Valuation, analyst ratings, price targets, earnings surprises, short interest, income highlights | `app/fundamental.py` |
| 10 | ~~No WebSocket Real-time Push~~ | ✅ 4-channel WebSocket hub (signals, regime, broker, health) with auto-reconnect frontend hook | `app/ws.py` |
| 11 | ~~No Put/Call Ratio signal~~ | ✅ Volume/OI ratios, ATM-weighted PCR, contrarian signal, strike distribution, term structure | `app/put_call_ratio.py` |
| 12 | ~~No unusual options volume detection~~ | ✅ V/OI ratio scanning, size classification, clustering detection, 5-factor smart money scoring | `app/unusual_volume.py` |

### 🔴 High Priority Gaps

*All high-priority gaps have been resolved. See Resolved Gaps above.*

### 🟡 Medium Priority Gaps

*All medium-priority gaps have been resolved. See Resolved Gaps above.*

### 🟢 Low Priority Gaps

*All gaps have been resolved. See Resolved Gaps above.*

---

## 5. Recommended Evolution Roadmap

### Phase 1: Signal Credibility ✅ COMPLETE
- ✅ **Backtesting engine** — Event-driven signal replay + walk-forward analysis (`app/signal_backtest.py`)
- ✅ **Greeks integration** — Black-Scholes Delta/Gamma/Theta/Vega/Rho (`app/greeks.py`)
- ✅ **IV analysis** — IV percentile ranking + surface analysis (`app/iv_analysis.py`)
- ✅ **ML enhancement** — Signal scoring, regime classification, LLM analysis (`app/ml/`)
- ✅ **Symbol discovery** — DuckDB-powered metadata scanning + search (`app/symbol_discovery.py`)

### Phase 2: Differentiation ✅ COMPLETE
- ✅ **Options chain data** — Real-time options chain with strike/expiry selection (`app/options_data.py`)
- ✅ **Multi-leg strategy recommendations** — Iron Condor, Spreads, Straddle, Strangle, Butterfly (`app/multi_leg.py`)
- ✅ **Put/Call ratio + unusual volume** — Put/Call ratio with ATM-weighted PCR, contrarian signals, term structure (`app/put_call_ratio.py`) + unusual volume detection with V/OI scanning, clustering, smart money scoring (`app/unusual_volume.py`)

### Phase 3: Production Trading ✅ COMPLETE
- ✅ **Broker integration** — Alpaca paper trading with full order/position management (`app/broker.py`)
- ✅ **Position tracking + P&L** — Full CRUD portfolio view with summary (`app/positions.py`)
- ✅ **WebSocket push** — 4-channel real-time hub with auto-reconnect frontend hook (`app/ws.py`)

---

## 6. Scoring (Before → Target)

| Dimension | Current | After Phase 3 |
|-----------|---------|---------------|
| Type Safety | 5/5 | 5/5 |
| Code Structure | 5/5 | 5/5 |
| API Security | 5/5 | 5/5 |
| Test Coverage | 5/5 | 5/5 |
| Observability | 5/5 | 5/5 |
| Performance | 5/5 | 5/5 |
| Deployment Readiness | 5/5 | 5/5 |
| **Signal Intelligence** | **5/5** | **5/5** |
| **Trading Capability** | **4/5** | **5/5** |
| **Options Depth** | **5/5** | **5/5** |
