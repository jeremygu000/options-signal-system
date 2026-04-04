"""Options chain data provider — fetches chains from yfinance, transforms to optopsy format.

Optopsy requires a specific DataFrame schema:
    Required: underlying_symbol, option_type (c/p), expiration, quote_date,
              strike, bid, ask, delta
    Optional: underlying_price, gamma, theta, vega, implied_volatility,
              volume, open_interest
"""

from __future__ import annotations

import logging
import time
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

from app.greeks import bs_price_and_greeks

logger = logging.getLogger(__name__)

# ── TTL cache ────────────────────────────────────────────────────────

_CHAIN_TTL = 300  # 5 minutes

_chain_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _cache_get(key: str) -> pd.DataFrame | None:
    entry = _chain_cache.get(key)
    if entry is None:
        return None
    ts, df = entry
    if time.monotonic() - ts > _CHAIN_TTL:
        del _chain_cache[key]
        return None
    return df


def _cache_set(key: str, df: pd.DataFrame) -> None:
    _chain_cache[key] = (time.monotonic(), df)


def clear_chain_cache() -> None:
    """Evict all cached chain data."""
    _chain_cache.clear()


# ── Public API ───────────────────────────────────────────────────────


def get_expirations(symbol: str) -> list[str]:
    """Return available option expiration dates for a symbol.

    Returns:
        Sorted list of expiration date strings (YYYY-MM-DD).
    """
    try:
        ticker = yf.Ticker(symbol)
        expirations: tuple[str, ...] = ticker.options
        return sorted(expirations)
    except Exception:
        logger.exception("%s: failed to fetch option expirations", symbol)
        return []


def get_options_chain(
    symbol: str,
    expiration: str | None = None,
) -> pd.DataFrame:
    """Fetch options chain data for a single expiration and convert to optopsy format.

    Args:
        symbol: Ticker symbol (e.g. "USO").
        expiration: Specific expiration date (YYYY-MM-DD). If None, uses the
                    nearest available expiration.

    Returns:
        DataFrame with optopsy-compatible columns. Empty DataFrame on failure.
    """
    cache_key = f"chain:{symbol}:{expiration}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)

        if expiration is None:
            available = ticker.options
            if not available:
                logger.warning("%s: no option expirations available", symbol)
                return pd.DataFrame()
            expiration = available[0]

        chain = ticker.option_chain(expiration)
        calls = chain.calls
        puts = chain.puts

        result = _transform_to_optopsy(symbol, expiration, calls, puts)
        _cache_set(cache_key, result)
        return result

    except Exception:
        logger.exception("%s: failed to fetch options chain (exp=%s)", symbol, expiration)
        return pd.DataFrame()


def get_options_chain_multi(
    symbol: str,
    max_expirations: int = 4,
) -> pd.DataFrame:
    """Fetch options chains for multiple expirations and combine.

    Args:
        symbol: Ticker symbol.
        max_expirations: Maximum number of nearest expirations to fetch.

    Returns:
        Combined DataFrame with optopsy-compatible columns.
    """
    cache_key = f"chain_multi:{symbol}:{max_expirations}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    expirations = get_expirations(symbol)
    if not expirations:
        return pd.DataFrame()

    selected = expirations[:max_expirations]
    frames: list[pd.DataFrame] = []

    for exp in selected:
        df = get_options_chain(symbol, exp)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    _cache_set(cache_key, result)
    return result


# ── Internal ─────────────────────────────────────────────────────────


def _transform_to_optopsy(
    symbol: str,
    expiration: str,
    calls: pd.DataFrame,
    puts: pd.DataFrame,
) -> pd.DataFrame:
    """Transform yfinance option chain DataFrames to optopsy format.

    yfinance columns (typical): contractSymbol, lastTradeDate, strike, lastPrice,
    bid, ask, change, percentChange, volume, openInterest, impliedVolatility,
    inTheMoney.
    """
    today_str = date.today().isoformat()
    frames: list[pd.DataFrame] = []

    for option_type, df in [("c", calls), ("p", puts)]:
        if df.empty:
            continue

        n = len(df)
        strike_arr = np.asarray(df["strike"].values, dtype=np.float64)
        iv_arr = np.asarray(df["impliedVolatility"].fillna(0.20).values, dtype=np.float64)
        iv_arr = np.clip(iv_arr, 0.01, 5.0)

        exp_dt = pd.Timestamp(expiration)
        today_dt = pd.Timestamp(today_str)
        dte_days = max((exp_dt - today_dt).days, 0)
        T_arr = np.full(n, dte_days / 365.0, dtype=np.float64)

        spot_price = float(strike_arr.mean())
        if "lastPrice" in df.columns:
            spot_price = float(np.asarray(df["lastPrice"].values, dtype=np.float64).mean())
        S_arr = np.full(n, spot_price, dtype=np.float64)

        _price, delta_arr, gamma_arr, theta_arr, vega_arr, rho_arr = bs_price_and_greeks(
            S_arr, strike_arr, T_arr, 0.05, iv_arr, option_type
        )

        transformed = pd.DataFrame(
            {
                "underlying_symbol": symbol.upper(),
                "option_type": option_type,
                "expiration": exp_dt,
                "quote_date": today_dt,
                "strike": strike_arr,
                "bid": df["bid"].values,
                "ask": df["ask"].values,
                "delta": delta_arr,
                "gamma": gamma_arr,
                "theta": theta_arr,
                "vega": vega_arr,
                "rho": rho_arr,
                "volume": df["volume"].fillna(0).astype(int).values,
                "open_interest": df["openInterest"].fillna(0).astype(int).values,
                "implied_volatility": df["impliedVolatility"].fillna(0.0).values,
            }
        )

        frames.append(transformed)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
