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
| Live Trading | ❌ | ✅ | ✅ IB | ✅ IB | ❌ | ✅ Alpaca |
| Greeks Calculation | ✅ BS model | ✅ | ✅ | ❌ | ✅ | ❌ |
| Implied Volatility | ✅ IV percentile | ✅ | ✅ | ❌ | ✅ | ❌ |
| Options Chain Data | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Multi-Leg Strategies | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Fundamental Data | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| ML/AI Enhancement | ✅ 5 modules | ✅ | ❌ | ❌ | ❌ | ❌ |
| Symbol Discovery | ✅ DuckDB | ✅ | ✅ | ❌ | ❌ | ❌ |
| WebSocket Real-time | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

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
| 4 | ~~No Implied Volatility Analysis~~ | ✅ IV percentile ranking, IV surface analysis | `app/iv_analysis.py` |
| 8 | ~~No ML/Statistical Enhancement~~ | ✅ 5 modules — signal scoring, regime classification, LLM analysis | `app/ml/` |

### 🔴 High Priority Gaps

| # | Gap | Impact | Reference Projects |
|---|-----|--------|-------------------|
| 3 | **No Broker Integration** | Signals are informational only; no execution capability | Lean (IB), blankly (Alpaca), alpacahq/options-wheel |

### 🟡 Medium Priority Gaps

| # | Gap | Impact | Reference Projects |
|---|-----|--------|-------------------|
| 5 | **No Options Chain Data** | Cannot recommend specific strike/expiry for signals | OpenBB, Lean |
| 6 | **No Multi-Leg Strategy Support** | Cannot construct Iron Condor / Spread / Straddle recommendations | optopsy, optionlab |
| 7 | **No Position Management / P&L** | No tracking after signal is generated | blankly, Lean |

### 🟢 Low Priority Gaps

| # | Gap | Impact |
|---|-----|--------|
| 9 | No fundamental data (earnings, analyst ratings) | Cannot blend fundamental + technical |
| 10 | No WebSocket real-time push | Frontend must poll |
| 11 | No Put/Call Ratio signal | Missing market sentiment quantification |
| 12 | No unusual options volume detection | Missing "smart money" signals |

---

## 5. Recommended Evolution Roadmap

### Phase 1: Signal Credibility ✅ COMPLETE
- ✅ **Backtesting engine** — Event-driven signal replay + walk-forward analysis (`app/signal_backtest.py`)
- ✅ **Greeks integration** — Black-Scholes Delta/Gamma/Theta/Vega/Rho (`app/greeks.py`)
- ✅ **IV analysis** — IV percentile ranking + surface analysis (`app/iv_analysis.py`)
- ✅ **ML enhancement** — Signal scoring, regime classification, LLM analysis (`app/ml/`)
- ✅ **Symbol discovery** — DuckDB-powered metadata scanning + search (`app/symbol_discovery.py`)

### Phase 2: Differentiation
- ❌ **Options chain data** — Recommend specific strike/expiry with each signal
- ❌ **Put/Call ratio + unusual volume** — Market sentiment signals
- ❌ **Multi-leg strategy recommendations** — Based on regime + IV environment

### Phase 3: Production Trading
- ❌ **Broker integration** — Alpaca/IBKR for one-click execution (Alpaca paper keys configured)
- ❌ **Position tracking + P&L** — Real-time portfolio view
- ❌ **WebSocket push** — Real-time signal delivery to frontend

---

## 6. Scoring (Before → Target)

| Dimension | Current | After Phase 3 |
|-----------|---------|---------------|
| Type Safety | 5/5 | 5/5 |
| Code Structure | 5/5 | 5/5 |
| API Security | 4/5 | 5/5 |
| Test Coverage | 5/5 | 5/5 |
| Observability | 4/5 | 5/5 |
| Performance | 4/5 | 5/5 |
| Deployment Readiness | 4/5 | 5/5 |
| **Signal Intelligence** | **4/5** | **5/5** |
| **Trading Capability** | **2/5** | **5/5** |
| **Options Depth** | **3/5** | **5/5** |
