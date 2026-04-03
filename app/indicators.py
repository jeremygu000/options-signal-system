"""Technical indicators — pure functions operating on DataFrames / Series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    """Simple moving average over *n* periods."""
    return series.rolling(window=n, min_periods=n).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range over *n* periods.

    Requires columns: High, Low, Close.
    """
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    return tr.rolling(window=n, min_periods=n).mean()


def session_vwap(intraday_df: pd.DataFrame) -> pd.Series:
    """Volume-Weighted Average Price, computed per trading day.

    Requires columns: High, Low, Close, Volume.
    Returns a Series aligned with the input index.
    """
    if intraday_df.empty:
        return pd.Series(dtype=float)

    typical_price = (intraday_df["High"] + intraday_df["Low"] + intraday_df["Close"]) / 3
    tpv = typical_price * intraday_df["Volume"]

    # Group by calendar date to reset VWAP each session
    idx = pd.DatetimeIndex(intraday_df.index)
    dates = idx.normalize()
    cum_tpv = tpv.groupby(dates).cumsum()
    cum_vol = intraday_df["Volume"].groupby(dates).cumsum()

    vwap = cum_tpv / cum_vol.replace(0, np.nan)
    return vwap


def rolling_high(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Rolling highest High over *n* periods."""
    return df["High"].rolling(window=n, min_periods=1).max()


def rolling_low(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Rolling lowest Low over *n* periods."""
    return df["Low"].rolling(window=n, min_periods=1).min()


def prev_day_high(df: pd.DataFrame) -> float:
    """Yesterday's High from daily data. Returns NaN if insufficient data."""
    if len(df) < 2:
        return float("nan")
    return float(df["High"].iloc[-2])


def prev_day_low(df: pd.DataFrame) -> float:
    """Yesterday's Low from daily data. Returns NaN if insufficient data."""
    if len(df) < 2:
        return float("nan")
    return float(df["Low"].iloc[-2])
