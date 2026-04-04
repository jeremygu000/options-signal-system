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
from scipy.stats import norm  # type: ignore[import-untyped]

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

# Small epsilon to avoid log(0) or division by zero in BS
_EPS: float = 1e-8


# ── Black-Scholes core (vectorised) ──────────────────────────────────


def _bs_price_and_greeks(
    S: np.ndarray,
    K: np.ndarray,
    T: np.ndarray,
    r: float,
    sigma: np.ndarray,
    option_type: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute Black-Scholes price + Greeks for a vector of options.

    All inputs must be 1-D arrays of the same length.

    Args:
        S:           Underlying price (per option row).
        K:           Strike price.
        T:           Time to expiration in years (DTE / 365). Must be > 0.
        r:           Risk-free rate (scalar).
        sigma:       Implied volatility (per option row).
        option_type: "c" for call, "p" for put.

    Returns:
        Tuple of (price, delta, gamma, theta, vega) as numpy arrays.
        Rows where T <= 0 are set to intrinsic value / zero Greeks.
    """
    valid = T > _EPS
    price = np.zeros_like(S)
    delta = np.zeros_like(S)
    gamma = np.zeros_like(S)
    theta = np.zeros_like(S)
    vega = np.zeros_like(S)

    S_v = S[valid]
    K_v = K[valid]
    T_v = T[valid]
    sigma_v = sigma[valid]

    sqrt_T = np.sqrt(T_v)
    sigma_sqrt_T = sigma_v * sqrt_T

    d1 = (np.log(S_v / K_v + _EPS) + (r + 0.5 * sigma_v**2) * T_v) / (sigma_sqrt_T + _EPS)
    d2 = d1 - sigma_sqrt_T

    nd1 = norm.cdf(d1)
    nd2 = norm.cdf(d2)
    nd1_neg = norm.cdf(-d1)
    nd2_neg = norm.cdf(-d2)
    pdf_d1 = norm.pdf(d1)

    disc = np.exp(-r * T_v)

    if option_type == "c":
        price[valid] = S_v * nd1 - K_v * disc * nd2
        delta[valid] = nd1
    else:
        price[valid] = K_v * disc * nd2_neg - S_v * nd1_neg
        delta[valid] = nd1 - 1.0  # negative for puts

    gamma[valid] = pdf_d1 / (S_v * sigma_sqrt_T + _EPS)
    vega[valid] = S_v * pdf_d1 * sqrt_T / 100.0  # per 1% move in vol
    theta_annual = -(S_v * pdf_d1 * sigma_v) / (2.0 * sqrt_T + _EPS) - r * K_v * disc
    if option_type == "c":
        theta[valid] = theta_annual / 365.0
    else:
        theta[valid] = (theta_annual + r * K_v * disc) / 365.0

    # Intrinsic value for expired/zero-time options
    expired = ~valid
    if option_type == "c":
        price[expired] = np.maximum(S[expired] - K[expired], 0.0)
        delta[expired] = (S[expired] > K[expired]).astype(float)
    else:
        price[expired] = np.maximum(K[expired] - S[expired], 0.0)
        delta[expired] = -((K[expired] > S[expired]).astype(float))

    return price, delta, gamma, theta, vega


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

    all_frames: list[pd.DataFrame] = []

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

            dte_days = (expiration - quote_date).days
            T = dte_days / 365.0

            n = len(strikes)
            S_arr = np.full(n, S)
            T_arr = np.full(n, T)
            sigma_arr = np.full(n, sigma_date)

            for opt_type in ("c", "p"):
                mid, delta_arr, gamma_arr, theta_arr, vega_arr = _bs_price_and_greeks(
                    S_arr, strikes, T_arr, risk_free_rate, sigma_arr, opt_type
                )

                keep = mid >= MIN_OPTION_MID
                if not keep.any():
                    continue

                frame = pd.DataFrame(
                    {
                        "underlying_symbol": symbol.upper(),
                        "option_type": opt_type,
                        "expiration": expiration,
                        "quote_date": quote_date,
                        "strike": strikes[keep],
                        "bid": mid[keep] * (1.0 - BID_ASK_SPREAD),
                        "ask": mid[keep] * (1.0 + BID_ASK_SPREAD),
                        "delta": delta_arr[keep],
                        "gamma": gamma_arr[keep],
                        "theta": theta_arr[keep],
                        "vega": vega_arr[keep],
                        "implied_volatility": sigma_date,
                        "underlying_price": S,
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
