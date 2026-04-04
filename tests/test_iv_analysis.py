from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.iv_analysis import (
    IVAnalysisResult,
    IVSkewPoint,
    IVTermPoint,
    HVPoint,
    compute_iv_rank,
    compute_iv_percentile,
    compute_realized_volatility,
    _compute_hv,
    _rolling_hv_series,
)


class TestIVRank:
    def test_midpoint(self) -> None:
        assert compute_iv_rank(0.30, 0.20, 0.40) == pytest.approx(50.0)

    def test_at_low(self) -> None:
        assert compute_iv_rank(0.20, 0.20, 0.40) == pytest.approx(0.0)

    def test_at_high(self) -> None:
        assert compute_iv_rank(0.40, 0.20, 0.40) == pytest.approx(100.0)

    def test_above_high_clamped(self) -> None:
        assert compute_iv_rank(0.50, 0.20, 0.40) == pytest.approx(100.0)

    def test_below_low_clamped(self) -> None:
        assert compute_iv_rank(0.10, 0.20, 0.40) == pytest.approx(0.0)

    def test_equal_high_low_returns_50(self) -> None:
        assert compute_iv_rank(0.30, 0.30, 0.30) == pytest.approx(50.0)


class TestIVPercentile:
    def test_all_below(self) -> None:
        history = pd.Series([0.10, 0.15, 0.20, 0.25])
        assert compute_iv_percentile(0.30, history) == pytest.approx(100.0)

    def test_all_above(self) -> None:
        history = pd.Series([0.35, 0.40, 0.45, 0.50])
        assert compute_iv_percentile(0.30, history) == pytest.approx(0.0)

    def test_half_below(self) -> None:
        history = pd.Series([0.10, 0.20, 0.40, 0.50])
        assert compute_iv_percentile(0.30, history) == pytest.approx(50.0)

    def test_empty_returns_50(self) -> None:
        assert compute_iv_percentile(0.30, pd.Series([], dtype=float)) == pytest.approx(50.0)


class TestRealizedVolatility:
    def _make_prices(self, n: int = 60, daily_return: float = 0.01) -> pd.Series:
        prices = [100.0]
        for _ in range(n):
            prices.append(prices[-1] * (1 + daily_return))
        return pd.Series(prices)

    def test_positive_rv(self) -> None:
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, 100))))
        rv = compute_realized_volatility(prices, window=20)
        assert 0.05 < rv < 0.80

    def test_constant_prices_zero_rv(self) -> None:
        prices = pd.Series([100.0] * 30)
        rv = compute_realized_volatility(prices, window=20)
        assert rv == pytest.approx(0.0)

    def test_insufficient_data_returns_zero(self) -> None:
        prices = pd.Series([100.0, 101.0])
        rv = compute_realized_volatility(prices, window=20)
        assert rv == 0.0

    def test_window_5(self) -> None:
        np.random.seed(99)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.02, 50))))
        rv = compute_realized_volatility(prices, window=5)
        assert rv > 0

    def test_annualisation_factor(self) -> None:
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 100))))
        rv_252 = compute_realized_volatility(prices, window=20, trading_days=252)
        rv_365 = compute_realized_volatility(prices, window=20, trading_days=365)
        assert rv_365 > rv_252


class TestComputeHV:
    def test_returns_multiple_windows(self) -> None:
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 200))))
        points = _compute_hv(prices)
        assert len(points) >= 3
        assert all(isinstance(p, HVPoint) for p in points)
        windows = {p.window_days for p in points}
        assert 20 in windows
        assert 5 in windows

    def test_short_series(self) -> None:
        prices = pd.Series([100.0, 101.0, 102.0])
        points = _compute_hv(prices)
        assert len(points) == 0


class TestRollingHVSeries:
    def test_returns_series(self) -> None:
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 100))))
        hv = _rolling_hv_series(prices, window=20)
        assert isinstance(hv, pd.Series)
        assert len(hv) > 0
        assert hv.isna().sum() == 0

    def test_all_positive(self) -> None:
        np.random.seed(42)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 100))))
        hv = _rolling_hv_series(prices, window=20)
        assert (hv > 0).all()


class TestIVAnalysisResult:
    def test_default_values(self) -> None:
        r = IVAnalysisResult(symbol="TEST")
        assert r.symbol == "TEST"
        assert r.spot_price == 0.0
        assert r.current_atm_iv == 0.0
        assert r.iv_rank == 0.0
        assert r.iv_percentile == 0.0
        assert r.skew_points == []
        assert r.term_structure == []
        assert r.hv_points == []
        assert r.error is None

    def test_skew_point_frozen(self) -> None:
        p = IVSkewPoint(strike=100.0, implied_volatility=0.30, option_type="c", moneyness=1.0)
        assert p.strike == 100.0
        with pytest.raises(AttributeError):
            p.strike = 200.0  # type: ignore[misc]

    def test_term_point_frozen(self) -> None:
        t = IVTermPoint(expiration="2025-06-20", dte_days=30, atm_iv=0.25)
        assert t.dte_days == 30
        with pytest.raises(AttributeError):
            t.dte_days = 60  # type: ignore[misc]
