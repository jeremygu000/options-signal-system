# Optopsy v2.3.0 API Integration Guide

> Complete API reference for production integration with FastAPI options signal system
> Source: [goldspanlabs/optopsy](https://github.com/goldspanlabs/optopsy) | snip PyPI: [optopsy 2.3.0](https://pypi.org/project/optopsy/2.3.0/)

---

## 1. Data Format

### Required Columns

| snip Column | snip Type | snip Description | snip Example |
|snip --------|snip ------|snip -------------|snip ---------|
| snip `underlying_symbol` | snip str | snip Ticker symbol | snip SPX, SPY, QQQ |
| snip `option_type` | snip str | snip Call or Put | snip 'c', 'p', 'call', 'put' |
| snip `expiration` | snip datetime | snip Option expiration date | snip 2023-01-20 |
| snip `quote_date` | snip datetime | snip Date of the quote | snip 2023-01-01 |
| snip `strike` | snip float | snip Strike price | snip 4500.0 |
| snip `bid` | snip float | snip Bid price | snip 10.50 |
| snip `ask` | snip float | snip Ask price | snip 11.00 |
| snip `delta` | snip float | snip **REQUIRED** Option delta | snip 0.30 |

snip ### Optional Columns

| snip Column | snip Type | snip Description |
|snip --------|snip ------|snip -------------|
| snip `underlying_price` | snip float | snip Stock/index price |
| snip `close` | snip float | snip Stock/index close price |
| snip `gamma` | snip float | snip Option gamma |
| snip `theta` | snip float | snip Option theta |
| snip `vega` | snip float | snip Option vega |
| snip `implied_volatility` | snip float | snip IV (for IV Rank signals) |
| snip `volume` | snip int | snip Trading volume (for liquidity slippage) |
| snip `open_interest` | snip int | snip Open interest |

snip ### Loading Data from CSV

```python
import optopsy as op

data = op.csv_data(
    "options_data.csv",
    underlying_symbol=0,  # Column index (0-based)
    option_type=1,
    expiration=2,
    quote_date=3,
    strike=4,
    bid=5,
    ask=6,
    delta=7,  # REQUIRED
    # Optional columns
    gamma=8,
    theta=9,
    vega=10,
    implied_volatility=11,
    volume=12,
    open_interest=13,
)
```

### Loading Data from DataFrame

```python
import pandas as pd
import optopsy as op

df = pd.read_csv('options_data.csv')

# Rename columns to match Optopsy's expected format
df = df.rename(columns={
    'Symbol': 'underlying_symbol',
    'Type': 'option_type',
    'Expiration': 'expiration',
    'QuoteDate': 'quote_date',
    'Strike': 'strike',
    'Bid': 'bid',
    'Ask': 'ask',
    'Delta': 'delta'
})

# Now use directly
results = op.long_calls(df)
```

---

## 2. Core API - All 38 Strategies

### Strategy Function Signature

All strategy functions share the same signature:

```python
def strategy_name(data: pd.DataFrame, **kwargs: Unpack[StrategyParamsDict]) -> pd.DataFrame
```

### Single-Leg Strategies (4)

| snip Function | snip Description | snip Market View |
|snip ----------|snip -------------|snip -------------|
| snip `op.long_calls(data, **kwargs)` | snip Buy call options | snip Bullish |
| snip `op.short_calls(data, **kwargs)` | snip Sell call options | snip Bearish/Neutral |
| snip `op.long_puts(data, **kwargs)` | snip Buy put options | snip Bearish |
| snip `op.short_puts(data, **kwargs)` | snip Sell put options | snip Bullish |

snip ### Straddles & snip Strangles (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_straddles(data, **kwargs)` | snip Long call + long put at same strike |
| snip `op.short_straddles(data, **kwargs)` | snip Short call + short put at same strike |
| snip `op.long_strangles(data, **kwargs)` | snip Long call + long put at different strikes |
| snip `op.short_strangles(data, **kwargs)` | snip Short call + short put at different strikes |

snip ### Vertical Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_call_spread(data, **kwargs)` | snip Bull call spread |
| snip `op.short_call_spread(data, **kwargs)` | snip Bear call spread |
| snip `op.long_put_spread(data, **kwargs)` | snip Bear put spread |
| snip `op.short_put_spread(data, **kwargs)` | snip Bull put spread |

snip ### Ratio Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.call_back_spread(data, **kwargs)` | snip Call ratio backspread (1:2, short ITM, long OTM) |
| snip `op.put_back_spread(data, **kwargs)` | snip Put ratio backspread (1:2) |
| snip `op.call_front_spread(data, **kwargs)` | snip Call ratio spread (1:2, long ITM, short OTM) |
| snip `op.put_front_spread(data, **kwargs)` | snip Put ratio spread (1:2) |

snip ### Butterfly Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_call_butterfly(data, **kwargs)` | snip Long call butterfly |
| snip `op.short_call_butterfly(data, **kwargs)` | snip Short call butterfly |
| snip `op.long_put_butterfly(data, **kwargs)` | snip Long put butterfly |
| snip `op.short_put_butterfly(data, **kwargs)` | snip Short put butterfly |

snip ### Iron Condors & snip Iron Butterflies (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.iron_condor(data, **kwargs)` | snip Iron condor (neutral income) |
| snip `op.reverse_iron_condor(data, **kwargs)` | snip Reverse iron condor (breakout play) |
| snip `op.iron_butterfly(data, **kwargs)` | snip Iron butterfly |
| snip `op.reverse_iron_butterfly(data, **kwargs)` | snip Reverse iron butterfly |

snip ### Condor Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_call_condor(data, **kwargs)` | snip Long call condor |
| snip `op.short_call_condor(data, **kwargs)` | snip Short call condor |
| snip `op.long_put_condor(data, **kwargs)` | snip Long put condor |
| snip `op.short_put_condor(data, **kwargs)` | snip Short put condor |

snip ### Covered & snip Collar Strategies (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.covered_call(data, **kwargs)` | snip Covered call (stock + short call) |
| snip `op.protective_put(data, **kwargs)` | snip Protective put (stock + long put) |
| snip `op.collar(data, **kwargs)` | snip Collar (stock + short call + long put) |
| snip `op.cash_secured_put(data, **kwargs)` | snip Cash-secured put (alias for short puts) |

snip ### Calendar Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_call_calendar(data, **kwargs)` | snip Long call calendar |
| snip `op.short_call_calendar(data, **kwargs)` | snip Short call calendar |
| snip `op.long_put_calendar(data, **kwargs)` | snip Long put calendar |
| snip `op.short_put_calendar(data, **kwargs)` | snip Short put calendar |

snip ### Diagonal Spreads (4)

| snip Function | snip Description |
|snip ----------|snip -------------|
| snip `op.long_call_diagonal(data, **kwargs)` | snip Long call diagonal |
| snip `op.short_call_diagonal(data, **kwargs)` | snip Short call diagonal |
| snip `op.long_put_diagonal(data, **kwargs)` | snip Long put diagonal |
| snip `op.short_put_diagonal(data, **kwargs)` | snip Short put diagonal |

snip ---

## 3. Common Parameters

### Timing Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `max_entry_dte` | snip int | snip 90 | snip Maximum DTE at entry |
| snip `exit_dte` | snip int | snip 0 | snip DTE at exit (0 = hold to expiration) |
| snip `dte_interval` | snip int | snip 7 | snip Grouping interval for DTE ranges |

snip ### Per-Leg Delta Targeting

| snip Parameter | snip Type | snip Description |
|snip -----------|snip ------|snip -------------|
| snip `leg1_delta` | snip TargetRange \| snip dict \| snip None | snip Delta for leg 1 |
| snip `leg2_delta` | snip TargetRange \| snip dict \| snip None | snip Delta for leg 2 |
| snip `leg3_delta` | snip TargetRange \| snip dict \| snip None | snip Delta for leg 3 |
| snip `leg4_delta` | snip TargetRange \| snip dict \| snip None | snip Delta for leg 4 |

snip **TargetRange object:**

```python
from optopsy import TargetRange

delta = TargetRange(target=0.30, min=0.20, max=0.40)

# Or use dict
delta = {"target": 0.30, "min": 0.20, "max": 0.40}
```

### Filtering Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `min_bid_ask` | snip float | snip 0.05 | snip Minimum bid-ask spread |
| snip `delta_interval` | snip float | snip 0.05 | snip Grouping interval for delta ranges |

snip ### Early Exit Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `stop_loss` | snip float \| snip None | snip None | snip Negative P&L threshold (e.g., -0.50 = close at 50% loss) |
| snip `take_profit` | snip float \| snip None | snip None | snip Positive P&L threshold (e.g., 0.50 = close at 50% profit) |
| snip `max_hold_days` | snip int \| snip None | snip None | snip Maximum calendar days to hold |

snip ### Commission Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `commission` | snip Commission \| snip float \| snip None | snip None | snip Commission fee structure |

snip ```python
from optopsy import Commission

# Simple per-contract fee
commission = 0.65

# Full fee structure
commission = Commission(
    per_contract=0.65,   # Per option contract
    per_share=0.0,        # Per share (for stock legs)
    base_fee=9.99,        # Flat fee per trade
    min_fee=0.0,          # Minimum fee per trade
)
```

### Slippage Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `slippage` | snip str | snip 'mid' | snip Slippage model: 'mid', 'spread', 'liquidity', 'per_leg' |
| snip `fill_ratio` | snip float | snip 0.5 | snip Base fill ratio for liquidity mode (0-1) |
| snip `reference_volume` | snip int | snip 1000 | snip Volume threshold for liquidity mode |
| snip `per_leg_slippage` | snip float | snip 0.073 | snip Additive penalty per leg (per_leg mode) |

snip ### Calendar/Diagonal Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `front_dte_min` | snip int | snip 20 | snip Front leg minimum DTE |
| snip `front_dte_max` | snip int | snip 40 | snip Front leg maximum DTE |
| snip `back_dte_min` | snip int | snip 50 | snip Back leg minimum DTE |
| snip `back_dte_max` | snip int | snip 90 | snip Back leg maximum DTE |

snip ### Output Parameters

| snip Parameter | snip Type | snip Default | snip Description |
|snip -----------|snip ------|snip ---------|snip -------------|
| snip `raw` | snip bool | snip False | snip Return raw trade data (True) or aggregated stats (False) |
| snip `drop_nan` | snip bool | snip True | snip Drop rows with NaN values |

snip ---

## 4. Entry/Exit Signals

### Built-in Signals (80+)

Signals are computed on **stock price data**, not options data. Use `signal_dates()` to compute valid dates.

```python
import optopsy as op

# Load stock data (for signals) and options data (for strategy)
stocks = op.load_cached_stocks("SPY")
options = op.load_cached_options("SPY")

# Enter only when RSI(14) is below 30
entry_dates = op.signal_dates(stocks, op.rsi_below(14, 30))
results = op.long_calls(options, entry_dates=entry_dates)
```

### Available Signal Categories

#### Momentum Signals
- `rsi_below(period, threshold)`, `rsi_above(period, threshold)`
- `macd_cross_above(fast, slow, signal_period)`, `macd_cross_below(...)`
- `stoch_below(k_period, d_period, threshold)`, `stoch_above(...)`
- `cci_below(period, threshold)`, `cci_above(...)`
- `roc_above(period, threshold)`, `roc_below(...)`

#### Overlap (Moving Averages)
- `sma_above(period)`, `sma_below(period)`
- `ema_cross_above(fast, slow)`, `ema_cross_below(...)`

#### Volatility
- `atr_above(period, multiplier)`, `atr_below(...)`
- `bb_above_upper(length, std)`, `bb_below_lower(...)`
- `kc_above_upper(length, scalar)`, `kc_below_lower(...)`

#### Trend
- `adx_above(period, threshold)`, `adx_below(...)`
- `supertrend_buy(period, multiplier)`, `supertrend_sell(...)`

#### Volume (requires volume column)
- `mfi_above(period, threshold)`, `mfi_below(...)`
- `obv_cross_above_sma(sma_period)`, `obv_cross_below_sma(...)`

#### IV Rank (runs on options data!)
- `iv_rank_above(threshold, window)`, `iv_rank_below(...)`

#### Calendar
- `day_of_week(*days)` - 0=Mon, 4=Fri

### Custom Signals

```python
import pandas as pd
import optopsy as op

# Any DataFrame with dates and boolean flag
my_signals = pd.DataFrame({
    "underlying_symbol": ["SPY", "SPY"],
    "quote_date": ["2023-01-02", "2023-01-03"],
    "buy": [True, False],
})

sig = op.custom_signal(my_signals, flag_col="buy")
entry_dates = op.signal_dates(my_signals, sig)
results = op.long_calls(options, entry_dates=entry_dates)
```

### Signal Combinators

```python
# AND: all conditions must be true
entry = op.signal(op.rsi_below(14, 30)) & snip op.signal(op.sma_above(50))

# OR: at least one condition
entry = op.signal(op.macd_cross_above()) | snip op.signal(op.bb_below_lower())

# Sustained: condition persists for N days
entry = op.sustained(op.rsi_below(14, 30), days=5)
```

---

## 5. Output Format

### Aggregated Results (default, raw=False)

```python
results = op.long_calls(data)
print(results.columns)
# ['dte_range', 'delta_range', 'count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']
```

**Example output:**

| snip dte_range | snip delta_range | snip count | snip mean | snip std | snip min | snip 25% | snip 50% | snip 75% | snip max |
|snip -----------|snip -------------|snip -------|snip ------|snip -----|snip -----|snip -----|snip -----|snip -----|snip -----|
| snip (0, 7] | snip (0.2, 0.3] | snip 1250 | snip 0.23 | snip 0.45 | snip -1.0 | snip 0.15 | snip 0.18 | snip 0.25 | snip 2.8 |
| snip (0, 7] | snip (0.3, 0.4] | snip 980 | snip 0.18 | snip 0.52 | snip -1.0 | snip 0.10 | snip 0.15 | snip 0.22 | snip 3.2 |

snip ### Raw Trade Data (raw=True)

```python
trades = op.long_calls(data, raw=True)
print(trades.columns)
# ['underlying_symbol', 'expiration', 'dte_entry', 'strike', 'entry', 'exit', 
#  'pct_change', 'quote_date_entry', 'quote_date_exit', 'exit_type', ...]
```

**Raw trade columns:**

| snip Column | snip Description |
|snip --------|snip -------------|
| snip `underlying_symbol` | snip Ticker |
| snip `expiration` | snip Option expiration date |
| snip `dte_entry` | snip DTE at entry |
| snip `strike` | snip Strike price |
| snip `entry` | snip Entry date |
| snip `exit` | snip Exit date |
| snip `pct_change` | snip Percentage return |
| snip `exit_type` | snip Exit reason: 'stop_loss', 'take_profit', 'max_hold', 'expiration' |

snip ---

## 6. Simulator API

For full trade-by-trade simulation with capital tracking:

### `simulate()`

```python
import optopsy as op

result = op.simulate(
    data,
    op.short_puts,
    capital=100_000,        # Starting capital
    quantity=1,              # Contracts per trade
    max_positions=2,        # Concurrent positions
    multiplier=100,          # Options multiplier (100 for equity options)
    selector='nearest',     # 'nearest', 'highest_premium', 'lowest_premium', or callable
    max_entry_dte=45,
    exit_dte=14,
)

# Access results
print(result.summary)        # Summary stats
print(result.trade_log)       # Per-trade P&L
print(result.equity_curve)     # Portfolio value over time
```

### `simulate_portfolio()`

```python
result = op.simulate_portfolio(
    legs=[
        {
            "data": spy_data,
            "strategy": op.short_puts,
            "weight": 0.6,
            "max_entry_dte": 45,
            "exit_dte": 14,
        },
        {
            "data": qqq_data,
            "strategy": op.iron_condor,
            "weight": 0.4,
            "max_entry_dte": 30,
            "exit_dte": 7,
        },
    ],
    capital=100_000,
)

print(result.summary)        # Portfolio-level summary
print(result.trade_log)      # Combined trade log
print(result.equity_curve)   # Portfolio equity curve
```

### SimulationResult Attributes

| snip Attribute | snip Description |
|snip -----------|snip -------------|
| snip `summary` | snip Dict with: win_rate, profit_factor, max_drawdown, sharpe_ratio, sortino_ratio, var_95, cvar_95, etc. |
| snip `trade_log` | snip DataFrame with all trades |
| snip `equity_curve` | snip Series indexed by date with portfolio values |

snip ---

## 7. Risk Metrics

### Standalone Functions

```python
import optopsy as op

trades = op.iron_condor(data, raw=True)
returns = trades['pct_change']

# Individual metrics
sharpe = op.sharpe_ratio(returns)
sortino = op.sortino_ratio(returns)
win_rate = op.win_rate(returns)
profit_factor = op.profit_factor(returns)
max_dd = op.max_drawdown_from_returns(returns)
var_95 = op.value_at_risk(returns, 0.95)
cvar_95 = op.conditional_value_at_risk(returns, 0.95)
calmar = op.calmar_ratio(returns)
omega = op.omega_ratio(returns)
tail = op.tail_ratio(returns)

# All at once
metrics = op.compute_risk_metrics(returns)
# Returns dict with all metrics
```

---

## 8. Integration Patterns for FastAPI

### Basic Integration Pattern

```python
# app/backtest.py
import pandas as pd
import optopsy as op
from pydantic import BaseModel
from typing import Optional

class BacktestRequest(BaseModel):
    underlying: str
    strategy: str
    max_entry_dte: int = 45
    exit_dte: int = 21
    leg1_delta: Optional[dict] = None
    leg2_delta: Optional[dict] = None
    min_bid_ask: float = 0.10
    raw: bool = False

STRATEGY_MAP = {
    "long_calls": op.long_calls,
    "short_puts": op.short_puts,
    "iron_condor": op.iron_condor,
    # ... etc
}

def run_backtest(data: pd.DataFrame, request: BacktestRequest) -> pd.DataFrame:
    strategy_func = STRATEGY_MAP[request.strategy]
    
    params = {
        "max_entry_dte": request.max_entry_dte,
        "exit_dte": request.exit_dte,
        "min_bid_ask": request.min_bid_ask,
        "raw": request.raw,
    }
    
    if request.leg1_delta:
        params["leg1_delta"] = request.leg1_delta
    if request.leg2_delta:
        params["leg2_delta"] = request.leg2_delta
    
    return strategy_func(data, **params)
```

### Data Transformation Helper

```python
# app/transform.py
def options_signal_to_optopsy(df: pd.DataFrame) -> pd.DataFrame:
    """Transform options signal system data to optopsy format."""
    return df.rename(columns={
        'symbol': 'underlying_symbol',
        'type': 'option_type',
        'expiry': 'expiration',
        'date': 'quote_date',
        'strike_price': 'strike',
    }).pipe(lambda df: df.assign(
        option_type=df['option_type'].map({'call': 'c', 'put': 'p'})
    ))
```

### Full Simulation Endpoint

```python
# app/api/backtest.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class SimulationRequest(BaseModel):
    data_path: str
    strategy: str
    capital: float = 100_000
    max_entry_dte: int = 45
    exit_dte: int = 21

@router.post("/simulate")
async def simulate_strategy(req: SimulationRequest):
    data = op.csv_data(req.data_path)
    strategy_func = STRATEGY_MAP.get(req.strategy)
    
    if not strategy_func:
        raise HTTPException(f"Unknown strategy: {req.strategy}")
    
    result = op.simulate(
        data,
        strategy_func,
        capital=req.capital,
        max_entry_dte=req.max_entry_dte,
        exit_dte=req.exit_dte,
    )
    
    return {
        "summary": result.summary,
        "trade_count": len(result.trade_log),
        "equity_curve": result.equity_curve.to_dict(),
    }
```

---

## 9. Type Definitions

```python
from optopsy import (
    # Strategy parameters
    StrategyParams,
    StrategyParamsDict,
    CalendarStrategyParams,
    CalendarStrategyParamsDict,
    
    # Configuration
    TargetRange,
    Commission,
)
```

---

## 10. Quick Reference

### Import

```python
import optopsy as op
```

### Data Loading
```python
data = op.csv_data("file.csv", underlying_symbol=0, option_type=1, ...)
```

### Run Strategy
```python
# Aggregated results
results = op.iron_condor(data, max_entry_dte=45, exit_dte=21)

# Raw trades
trades = op.iron_condor(data, max_entry_dte=45, exit_dte=21, raw=True)
```

### Run Simulation
```python
result = op.simulate(data, op.iron_condor, capital=100_000)
print(result.summary)
```

### Run with Signals
```python
stocks = op.load_cached_stocks("SPY")
options = op.load_cached_options("SPY")

entry = op.rsi_below(14, 30) & snip op.sma_above(50)
entry_dates = op.signal_dates(stocks, entry)

results = op.iron_condor(options, entry_dates=entry_dates)
```

---

## Resources

- GitHub: https://github.com/goldspanlabs/optopsy
- Documentation: https://goldspanlabs.github.io/optopsy/
- API Reference: https://goldspanlabs.github.io/optopsy/api-reference/
- PyPI: https://pypi.org/project/optopsy/
