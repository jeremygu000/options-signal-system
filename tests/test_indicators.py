from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.indicators import (
    atr,
    prev_day_high,
    prev_day_low,
    rolling_high,
    rolling_low,
    session_vwap,
    sma,
)


def _make_ohlcv(n: int = 20, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n + 5)[-n:]
    closes = base + np.cumsum(rng.normal(0, 1, n))
    highs = closes + rng.uniform(0.5, 2.0, n)
    lows = closes - rng.uniform(0.5, 2.0, n)
    opens = closes + rng.normal(0, 0.5, n)
    volumes = rng.integers(1_000_000, 10_000_000, n)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )


class TestSMA:
    def test_basic(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = sma(s, 3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(2.0)
        assert result.iloc[3] == pytest.approx(3.0)
        assert result.iloc[4] == pytest.approx(4.0)

    def test_window_larger_than_series(self):
        s = pd.Series([1.0, 2.0])
        result = sma(s, 5)
        assert result.isna().all()


class TestATR:
    def test_returns_series(self):
        df = _make_ohlcv(30)
        result = atr(df, 14)
        assert isinstance(result, pd.Series)
        assert len(result) == 30
        assert pd.notna(result.iloc[-1])
        assert result.iloc[-1] > 0

    def test_insufficient_data(self):
        df = _make_ohlcv(5)
        result = atr(df, 14)
        assert result.isna().all()


class TestSessionVWAP:
    def test_basic(self):
        idx = pd.date_range("2024-01-02 09:30", periods=10, freq="15min")
        df = pd.DataFrame(
            {
                "High": [101] * 10,
                "Low": [99] * 10,
                "Close": [100] * 10,
                "Volume": [1000] * 10,
            },
            index=idx,
        )
        result = session_vwap(df)
        assert len(result) == 10
        assert result.iloc[-1] == pytest.approx(100.0)

    def test_empty(self):
        df = pd.DataFrame()
        result = session_vwap(df)
        assert result.empty


class TestRollingHighLow:
    def test_rolling_high(self):
        df = _make_ohlcv(30)
        result = rolling_high(df, 20)
        assert pd.notna(result.iloc[-1])
        assert result.iloc[-1] >= df["High"].iloc[-20:].max() - 1e-10

    def test_rolling_low(self):
        df = _make_ohlcv(30)
        result = rolling_low(df, 20)
        assert pd.notna(result.iloc[-1])
        assert result.iloc[-1] <= df["Low"].iloc[-20:].min() + 1e-10


class TestPrevDay:
    def test_prev_day_high(self):
        df = _make_ohlcv(5)
        result = prev_day_high(df)
        assert result == pytest.approx(df["High"].iloc[-2])

    def test_prev_day_low(self):
        df = _make_ohlcv(5)
        result = prev_day_low(df)
        assert result == pytest.approx(df["Low"].iloc[-2])

    def test_insufficient_data(self):
        df = _make_ohlcv(1)
        assert np.isnan(prev_day_high(df))
        assert np.isnan(prev_day_low(df))
