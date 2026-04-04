"""Implied Volatility analysis — rank, percentile, skew, term structure, HV comparison.

Provides comprehensive IV analytics for a given symbol by combining:
- Current options chain IV data (via yfinance)
- Historical price data for realized volatility computation
- ATM IV extraction across expirations for term structure
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IVSkewPoint:
    """Single point on the IV skew curve."""

    strike: float
    implied_volatility: float
    option_type: str  # "c" or "p"
    moneyness: float  # strike / spot


@dataclass(frozen=True, slots=True)
class IVTermPoint:
    """Single point on the IV term structure curve."""

    expiration: str
    dte_days: int
    atm_iv: float


@dataclass(frozen=True, slots=True)
class HVPoint:
    """Historical volatility at a specific window."""

    window_days: int
    realized_vol: float  # annualised, e.g. 0.25 = 25%
    label: str  # e.g. "20-day HV"


@dataclass(slots=True)
class IVAnalysisResult:
    """Complete IV analysis for a symbol."""

    symbol: str
    spot_price: float = 0.0

    # ATM IV (nearest expiration)
    current_atm_iv: float = 0.0

    # IV Rank & Percentile (based on 1-year IV proxy from HV)
    iv_rank: float = 0.0  # 0-100
    iv_percentile: float = 0.0  # 0-100
    iv_high_52w: float = 0.0
    iv_low_52w: float = 0.0

    # IV Skew (nearest expiration)
    skew_points: list[IVSkewPoint] = field(default_factory=list)
    put_call_skew: float = 0.0  # ATM put IV - ATM call IV

    # IV Term Structure
    term_structure: list[IVTermPoint] = field(default_factory=list)

    # Historical / Realized Volatility
    hv_points: list[HVPoint] = field(default_factory=list)
    iv_rv_spread: float = 0.0  # current ATM IV - 20d RV (volatility risk premium)

    error: str | None = None


# ── Public API ───────────────────────────────────────────────────────


def compute_iv_analysis(symbol: str) -> IVAnalysisResult:
    """Run full IV analysis for a symbol.

    Fetches current option chains and 1-year price history to compute:
    - IV rank / percentile (using rolling HV as IV proxy)
    - IV skew for nearest expiration
    - IV term structure across expirations
    - Historical volatility at multiple windows
    - IV vs RV spread (volatility risk premium)
    """
    result = IVAnalysisResult(symbol=symbol)

    try:
        ticker = yf.Ticker(symbol)

        hist_1y = ticker.history(period="1y")
        if hist_1y.empty:
            result.error = f"No price history for {symbol}"
            return result

        close_prices = hist_1y["Close"]
        result.spot_price = float(close_prices.iloc[-1])
        result.hv_points = _compute_hv(close_prices)

        hv_series = _rolling_hv_series(close_prices, window=20)

        expirations = ticker.options
        if not expirations:
            result.error = f"No options available for {symbol}"
            return result

        nearest_exp = expirations[0]
        chain = ticker.option_chain(nearest_exp)
        atm_iv, skew_points, put_call_skew = _extract_skew(chain, result.spot_price, nearest_exp)
        result.current_atm_iv = atm_iv
        result.skew_points = skew_points
        result.put_call_skew = put_call_skew

        if not hv_series.empty and atm_iv > 0:
            result.iv_rank, result.iv_percentile, result.iv_high_52w, result.iv_low_52w = _compute_iv_rank_percentile(
                atm_iv, hv_series
            )

        result.term_structure = _compute_term_structure(ticker, expirations[:8], result.spot_price)

        hv_20d = next((h.realized_vol for h in result.hv_points if h.window_days == 20), 0.0)
        result.iv_rv_spread = atm_iv - hv_20d

    except Exception:
        logger.exception("%s: IV analysis failed", symbol)
        result.error = f"IV analysis failed for {symbol}"

    return result


# ── IV Rank & Percentile ────────────────────────────────────────────


def compute_iv_rank(current_iv: float, iv_low: float, iv_high: float) -> float:
    """IV Rank = (current - low) / (high - low) × 100."""
    if iv_high <= iv_low:
        return 50.0
    rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100.0
    return max(0.0, min(100.0, rank))


def compute_iv_percentile(current_iv: float, iv_history: pd.Series) -> float:
    """IV Percentile = % of days with IV lower than current."""
    if iv_history.empty:
        return 50.0
    days_lower = int((iv_history < current_iv).sum())
    return (days_lower / len(iv_history)) * 100.0


def _compute_iv_rank_percentile(
    current_atm_iv: float,
    hv_series: pd.Series,
) -> tuple[float, float, float, float]:
    """Compute rank and percentile using rolling HV as IV proxy."""
    clean = hv_series.dropna()
    if clean.empty:
        return 50.0, 50.0, current_atm_iv, current_atm_iv

    iv_high = float(clean.max())
    iv_low = float(clean.min())

    rank = compute_iv_rank(current_atm_iv, iv_low, iv_high)
    percentile = compute_iv_percentile(current_atm_iv, clean)

    return rank, percentile, iv_high, iv_low


# ── Historical Volatility ───────────────────────────────────────────


def compute_realized_volatility(
    close_prices: pd.Series,
    window: int = 20,
    trading_days: int = 252,
) -> float:
    """Compute annualised realised volatility (close-to-close).

    Formula: std(log returns) × sqrt(trading_days)
    """
    if len(close_prices) < window + 1:
        return 0.0

    log_returns: pd.Series = pd.Series(np.log(close_prices / close_prices.shift(1))).dropna()
    if len(log_returns) < window:
        return 0.0

    recent = log_returns.iloc[-window:]
    rv = float(recent.std()) * math.sqrt(trading_days)
    return rv


def _compute_hv(close_prices: pd.Series) -> list[HVPoint]:
    """Compute HV at standard windows."""
    windows = [
        (5, "5-day HV"),
        (10, "10-day HV"),
        (20, "20-day HV"),
        (60, "60-day HV"),
    ]
    points: list[HVPoint] = []
    for window, label in windows:
        rv = compute_realized_volatility(close_prices, window)
        if rv > 0:
            points.append(HVPoint(window_days=window, realized_vol=round(rv, 6), label=label))
    return points


def _rolling_hv_series(close_prices: pd.Series, window: int = 20) -> pd.Series:
    """Compute rolling annualised HV for IV rank/percentile proxy."""
    log_returns = pd.Series(np.log(close_prices / close_prices.shift(1)))
    rolling_std: pd.Series = log_returns.rolling(window).std()
    hv_series: pd.Series = rolling_std * math.sqrt(252)
    return hv_series.dropna()


# ── IV Skew ──────────────────────────────────────────────────────────


def _extract_skew(
    chain: object,
    spot: float,
    expiration: str,
) -> tuple[float, list[IVSkewPoint], float]:
    """Extract IV skew data from an option chain.

    Returns (atm_iv, skew_points, put_call_skew).
    """
    calls: pd.DataFrame = getattr(chain, "calls", pd.DataFrame())
    puts: pd.DataFrame = getattr(chain, "puts", pd.DataFrame())

    if calls.empty and puts.empty:
        return 0.0, [], 0.0

    # Filter to strikes within ±30% of spot for cleaner skew
    low_bound = spot * 0.70
    high_bound = spot * 1.30

    skew_points: list[IVSkewPoint] = []
    atm_call_iv = 0.0
    atm_put_iv = 0.0

    for opt_type, df in (("c", calls), ("p", puts)):
        if df.empty:
            continue

        strikes = df["strike"].to_numpy(dtype=np.float64)
        ivs = df["impliedVolatility"].fillna(0).to_numpy(dtype=np.float64)

        mask = (ivs > 0) & (strikes >= low_bound) & (strikes <= high_bound)
        if not mask.any():
            continue

        filt_strikes = strikes[mask]
        filt_ivs = ivs[mask]
        filt_moneyness = filt_strikes / spot

        skew_points.extend(
            IVSkewPoint(
                strike=round(float(s), 2),
                implied_volatility=round(float(v), 6),
                option_type=opt_type,
                moneyness=round(float(m), 4),
            )
            for s, v, m in zip(filt_strikes, filt_ivs, filt_moneyness)
        )

        dists = np.abs(filt_strikes - spot)
        atm_idx = int(np.argmin(dists))
        atm_iv_val = float(filt_ivs[atm_idx])

        if opt_type == "c":
            atm_call_iv = atm_iv_val
        else:
            atm_put_iv = atm_iv_val

    # ATM IV is average of nearest call and put IVs
    if atm_call_iv > 0 and atm_put_iv > 0:
        atm_iv = (atm_call_iv + atm_put_iv) / 2.0
    elif atm_call_iv > 0:
        atm_iv = atm_call_iv
    else:
        atm_iv = atm_put_iv

    put_call_skew = atm_put_iv - atm_call_iv

    # Sort by strike for clean charting
    skew_points.sort(key=lambda p: p.strike)

    return round(atm_iv, 6), skew_points, round(put_call_skew, 6)


# ── IV Term Structure ────────────────────────────────────────────────


def _compute_term_structure(
    ticker: yf.Ticker,
    expirations: list[str] | tuple[str, ...],
    spot: float,
) -> list[IVTermPoint]:
    """Compute ATM IV for each expiration to build term structure."""
    today = date.today()
    points: list[IVTermPoint] = []

    for exp_str in expirations:
        try:
            chain = ticker.option_chain(exp_str)
            calls: pd.DataFrame = chain.calls
            puts: pd.DataFrame = chain.puts

            # Find nearest ATM strike
            atm_call_iv = _find_atm_iv(calls, spot)
            atm_put_iv = _find_atm_iv(puts, spot)

            if atm_call_iv > 0 and atm_put_iv > 0:
                atm_iv = (atm_call_iv + atm_put_iv) / 2.0
            elif atm_call_iv > 0:
                atm_iv = atm_call_iv
            elif atm_put_iv > 0:
                atm_iv = atm_put_iv
            else:
                continue

            exp_date = pd.Timestamp(exp_str).date()
            dte = (exp_date - today).days

            if dte <= 0:
                continue

            points.append(
                IVTermPoint(
                    expiration=exp_str,
                    dte_days=dte,
                    atm_iv=round(atm_iv, 6),
                )
            )
        except Exception:
            logger.debug("Skipping expiration %s for term structure", exp_str)
            continue

    points.sort(key=lambda p: p.dte_days)
    return points


def _find_atm_iv(options_df: pd.DataFrame, spot: float) -> float:
    """Find ATM implied volatility from an options DataFrame."""
    if options_df.empty:
        return 0.0

    strikes = np.asarray(options_df["strike"].values, dtype=np.float64)
    ivs = np.asarray(options_df["impliedVolatility"].values, dtype=np.float64)

    dists = np.abs(strikes - spot)
    idx = int(np.argmin(dists))

    iv = float(ivs[idx]) if not np.isnan(ivs[idx]) else 0.0
    return iv if iv > 0 else 0.0
