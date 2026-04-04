"""Synthetic options chain generator using Black-Scholes pricing.

Generates a full historical options chain from daily stock OHLCV data.
All pricing is done via vectorized numpy/scipy operations — no row-by-row loops.

The output DataFrame is compatible with optopsy's simulate() function:
    underlying_symbol, option_type, expiration, quote_date, strike,
    bid, ask, delta, implied_volatility, gamma, theta, vega
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from app.greeks import bs_price_and_greeks

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Max DTE for generated options (calendar days)
MAX_DTE: int = 60

# Strike range: from S * (1 - STRIKE_HALF_RANGE) to S * (1 + STRIKE_HALF_RANGE)
STRIKE_HALF_RANGE: float = 0.15

# Number of strikes above and below ATM
DEFAULT_NUM_STRIKES: int = 10

# Bid/ask spread: ±5% around the theoretical mid
BID_ASK_SPREAD: float = 0.05

# Minimum option mid price — below this the option is considered worthless
MIN_OPTION_MID: float = 0.01

# Historical volatility window (trading days)
HV_WINDOW: int = 20

# Annualisation factor
TRADING_DAYS_PER_YEAR: float = 252.0

# IV clamp bounds
IV_MIN: float = 0.10
IV_MAX: float = 1.50


# ── Strike grid helper ────────────────────────────────────────────────


def _strike_grid(spot: float, num_strikes: int) -> np.ndarray:
    """Generate a symmetric strike grid around the spot price.

    Strike increment is rounded to the nearest $0.50 for cheap stocks (< $50)
    and $1.00 for everything else.

    Args:
        spot:        Current stock price.
        num_strikes: Number of strikes above and below ATM (total = 2*n + 1).

    Returns:
        Sorted numpy array of strike prices.
    """
    increment = 0.50 if spot < 50 else 1.00
    atm = round(spot / increment) * increment
    offsets = np.arange(-num_strikes, num_strikes + 1) * increment
    strikes = atm + offsets
    # Enforce the ±15 % range and positivity
    lo = spot * (1.0 - STRIKE_HALF_RANGE)
    hi = spot * (1.0 + STRIKE_HALF_RANGE)
    return strikes[(strikes >= lo) & (strikes <= hi) & (strikes > 0)]


# ── Main generator ────────────────────────────────────────────────────


def generate_synthetic_chain(
    symbol: str,
    stock_data: pd.DataFrame,
    *,
    num_strikes: int = DEFAULT_NUM_STRIKES,
    max_dte: int = MAX_DTE,
    risk_free_rate: float = 0.05,
) -> pd.DataFrame:
    """Generate a synthetic historical options chain via Black-Scholes.

    Uses **fixed weekly expiration dates** (every Friday) so the same contract
    (strike + expiration + type) appears across many consecutive quote_dates —
    exactly what optopsy ``simulate()`` needs for entry/exit matching.

    Args:
        symbol:          Ticker symbol (e.g. ``"USO"``).
        stock_data:      DataFrame with ``DatetimeIndex`` and at least a
                         ``Close`` column (standard OHLCV from Parquet store).
        num_strikes:     Strikes above *and* below ATM (total ≈ 2×n+1).
        max_dte:         Maximum calendar days to expiration.
        risk_free_rate:  Annualised risk-free rate (decimal).

    Returns:
        optopsy-compatible DataFrame. Empty if *stock_data* is empty.
    """
    if stock_data.empty or "Close" not in stock_data.columns:
        logger.warning("%s: stock_data is empty or missing Close column", symbol)
        return pd.DataFrame()

    df = stock_data.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    closes: pd.Series = df["Close"].astype(float)

    log_returns: pd.Series = closes.div(closes.shift(1)).apply(np.log)
    hv_series: pd.Series = log_returns.rolling(HV_WINDOW).std() * math.sqrt(TRADING_DAYS_PER_YEAR)
    hv_series = hv_series.ffill().bfill().clip(IV_MIN, IV_MAX)

    dates: pd.DatetimeIndex = df.index  # type: ignore[assignment]
    closes_arr = closes.values
    hv_arr = hv_series.values

    first_date = dates[0]
    last_date = dates[-1]

    fridays = pd.date_range(
        start=first_date - pd.Timedelta(days=first_date.weekday()) + pd.Timedelta(days=4),
        end=last_date + pd.Timedelta(days=max_dte + 7),
        freq="W-FRI",
    )

    exp_strike_map: dict[pd.Timestamp, np.ndarray] = {}
    for exp in fridays:
        first_active_idx = int(dates.searchsorted(exp - pd.Timedelta(days=max_dte)))
        if first_active_idx >= len(dates):
            continue
        ref_price = float(closes_arr[min(first_active_idx, len(dates) - 1)])
        exp_strike_map[exp] = _strike_grid(ref_price, num_strikes)

    rows_S: list[np.ndarray] = []
    rows_K: list[np.ndarray] = []
    rows_T: list[np.ndarray] = []
    rows_sigma: list[np.ndarray] = []
    rows_exp: list[np.ndarray] = []
    rows_qdate: list[np.ndarray] = []

    for date_idx in range(len(dates)):
        quote_date = dates[date_idx]
        S = float(closes_arr[date_idx])
        sigma_date = float(hv_arr[date_idx])

        if S <= 0 or not math.isfinite(S):
            continue

        active_expirations = fridays[(fridays >= quote_date) & (fridays <= quote_date + pd.Timedelta(days=max_dte))]

        for expiration in active_expirations:
            strikes = exp_strike_map.get(expiration)
            if strikes is None or len(strikes) == 0:
                continue

            n = len(strikes)
            dte_days = (expiration - quote_date).days
            T = dte_days / 365.0

            rows_S.append(np.full(n, S))
            rows_K.append(strikes)
            rows_T.append(np.full(n, T))
            rows_sigma.append(np.full(n, sigma_date))
            rows_exp.append(np.full(n, expiration.value, dtype="datetime64[ns]"))
            rows_qdate.append(np.full(n, quote_date.value, dtype="datetime64[ns]"))

    if not rows_S:
        logger.warning("%s: no synthetic options generated (empty chain)", symbol)
        return pd.DataFrame()

    all_S = np.concatenate(rows_S)
    all_K = np.concatenate(rows_K)
    all_T = np.concatenate(rows_T)
    all_sigma = np.concatenate(rows_sigma)
    all_exp = np.concatenate(rows_exp)
    all_qdate = np.concatenate(rows_qdate)

    all_frames: list[pd.DataFrame] = []

    for opt_type in ("c", "p"):
        mid, delta_arr, gamma_arr, theta_arr, vega_arr, _rho_arr = bs_price_and_greeks(
            all_S, all_K, all_T, risk_free_rate, all_sigma, opt_type
        )

        keep = mid >= MIN_OPTION_MID
        if not keep.any():
            continue

        frame = pd.DataFrame(
            {
                "underlying_symbol": symbol.upper(),
                "option_type": opt_type,
                "expiration": all_exp[keep],
                "quote_date": all_qdate[keep],
                "strike": all_K[keep],
                "bid": mid[keep] * (1.0 - BID_ASK_SPREAD),
                "ask": mid[keep] * (1.0 + BID_ASK_SPREAD),
                "delta": delta_arr[keep],
                "gamma": gamma_arr[keep],
                "theta": theta_arr[keep],
                "vega": vega_arr[keep],
                "implied_volatility": all_sigma[keep],
                "underlying_price": all_S[keep],
            }
        )
        all_frames.append(frame)

    if not all_frames:
        logger.warning("%s: no synthetic options generated (empty chain)", symbol)
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)

    # Ensure datetime columns are nanosecond precision (optopsy requirement)
    result["quote_date"] = result["quote_date"].astype("datetime64[ns]")
    result["expiration"] = result["expiration"].astype("datetime64[ns]")

    logger.info(
        "%s: generated %d synthetic option rows across %d quote_dates",
        symbol,
        len(result),
        result["quote_date"].nunique(),
    )
    return result
