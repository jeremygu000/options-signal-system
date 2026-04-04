"""Data provider — reads daily data from ~/.market_data/parquet/, intraday from yfinance.

Includes a TTL cache to avoid redundant I/O and network calls within the same
polling cycle.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from app.config import settings

logger = logging.getLogger(__name__)

# ── TTL cache ────────────────────────────────────────────────────────

_DAILY_TTL = 300  # 5 minutes — daily data changes infrequently
_INTRADAY_TTL = 60  # 1 minute — intraday is more volatile

_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _cache_get(key: str, ttl: float) -> pd.DataFrame | None:
    """Return cached DataFrame if it exists and hasn't expired."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, df = entry
    if time.monotonic() - ts > ttl:
        del _cache[key]
        return None
    return df


def _cache_set(key: str, df: pd.DataFrame) -> None:
    _cache[key] = (time.monotonic(), df)


def clear_cache() -> None:
    """Evict all cached data (useful on shutdown or for testing)."""
    _cache.clear()


# ── Helpers ──────────────────────────────────────────────────────────


def _sanitize_ticker(ticker: str) -> str:
    """Match yahoo-finance-data's sanitization: ^VIX → VIX."""
    return ticker.replace("^", "").replace("/", "_").replace("\\", "_").upper()


def _parquet_path(ticker: str) -> Path:
    """Resolve Parquet path, trying both {SYMBOL}.parquet and {SYMBOL}_1d.parquet."""
    base = settings.parquet_dir
    sanitized = _sanitize_ticker(ticker)
    # Prefer {SYMBOL}.parquet, fall back to {SYMBOL}_1d.parquet (yahoo-finance-data format)
    path = base / f"{sanitized}.parquet"
    if not path.exists():
        alt = base / f"{sanitized}_1d.parquet"
        if alt.exists():
            return alt
    return path


# ── Public API ───────────────────────────────────────────────────────


def get_daily(symbol: str, days: int | None = None) -> pd.DataFrame:
    """Load daily OHLCV from local Parquet store.

    Results are cached for 5 minutes.

    Args:
        symbol: Ticker symbol (e.g. "QQQ", "^VIX").
        days: Number of days to look back. None = all available data.

    Returns:
        DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume.
        Empty DataFrame if no data found.
    """
    cache_key = f"daily:{symbol}:{days}"
    cached = _cache_get(cache_key, _DAILY_TTL)
    if cached is not None:
        return cached

    path = _parquet_path(symbol)
    if not path.exists():
        logger.warning("%s: no local data at %s", symbol, path)
        return pd.DataFrame()

    df = pd.read_parquet(path)

    if days is not None:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df.index >= cutoff]

    if df.empty:
        logger.warning("%s: no data after filtering (days=%s)", symbol, days)

    _cache_set(cache_key, df)
    return df


def get_intraday(
    symbol: str,
    period: str | None = None,
    interval: str | None = None,
) -> pd.DataFrame:
    """Fetch intraday data from yfinance (not stored in Parquet).

    Results are cached for 1 minute.

    Args:
        symbol: Ticker symbol.
        period: yfinance period string (default from config: "5d").
        interval: yfinance interval string (default from config: "15m").

    Returns:
        DataFrame with DatetimeIndex and OHLCV columns.
        Empty DataFrame on failure.
    """
    _period = period or settings.intraday_period
    _interval = interval or settings.intraday_interval

    cache_key = f"intraday:{symbol}:{_period}:{_interval}"
    cached = _cache_get(cache_key, _INTRADAY_TTL)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        df: pd.DataFrame = ticker.history(period=_period, interval=_interval)
        if df.empty:
            logger.warning("%s: yfinance returned empty intraday data", symbol)
        _cache_set(cache_key, df)
        return df
    except Exception:
        logger.exception("%s: failed to fetch intraday data", symbol)
        return pd.DataFrame()
