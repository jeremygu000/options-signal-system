from __future__ import annotations

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.models import (
    SignalBacktestRequest,
    SignalBacktestResponse,
    SignalOutcome,
    WalkForwardRequest,
    WalkForwardResponse,
)
from app.signal_backtest import (
    _forward_return,
    _get_daily_as_of,
    _is_hit,
    run_signal_backtest,
    run_walk_forward,
)


def _make_daily(n: int = 300, start: str = "2024-01-02") -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=n)
    rng = np.random.default_rng(42)
    prices = 100.0 + np.cumsum(rng.normal(0.05, 1.0, n))
    prices = np.maximum(prices, 10.0)
    return pd.DataFrame(
        {
            "Open": prices - rng.uniform(0, 0.5, n),
            "High": prices + rng.uniform(0, 1.0, n),
            "Low": prices - rng.uniform(0, 1.0, n),
            "Close": prices,
            "Volume": rng.integers(1_000_000, 10_000_000, n),
        },
        index=dates,
    )


class TestGetDailyAsOf:
    def test_slices_up_to_date(self) -> None:
        df = _make_daily(100)
        mid_date = df.index[49].date()
        sliced = _get_daily_as_of(df, mid_date, lookback=60)
        assert len(sliced) == 50
        assert sliced.index[-1].date() == mid_date

    def test_respects_lookback(self) -> None:
        df = _make_daily(200)
        late_date = df.index[150].date()
        sliced = _get_daily_as_of(df, late_date, lookback=60)
        assert len(sliced) == 60

    def test_returns_all_if_less_than_lookback(self) -> None:
        df = _make_daily(30)
        last_date = df.index[-1].date()
        sliced = _get_daily_as_of(df, last_date, lookback=60)
        assert len(sliced) == 30


class TestForwardReturn:
    def test_computes_correctly(self) -> None:
        df = _make_daily(50)
        signal_date = df.index[10].date()
        entry = float(df.iloc[10]["Close"])
        exit_ = float(df.iloc[15]["Close"])
        ret = _forward_return(df, signal_date, 5)
        assert ret is not None
        expected = (exit_ - entry) / entry
        assert abs(ret - expected) < 1e-9

    def test_returns_none_if_insufficient(self) -> None:
        df = _make_daily(10)
        last_date = df.index[-1].date()
        ret = _forward_return(df, last_date, 5)
        assert ret is None


class TestIsHit:
    def test_long_positive_is_hit(self) -> None:
        assert _is_hit(0.01, "逢低做多") is True

    def test_long_negative_is_miss(self) -> None:
        assert _is_hit(-0.01, "逢低做多") is False

    def test_short_negative_is_hit(self) -> None:
        assert _is_hit(-0.01, "逢高做空") is True

    def test_short_positive_is_miss(self) -> None:
        assert _is_hit(0.01, "逢高做空") is False


class TestRunSignalBacktest:
    def _mock_get_daily(self, symbol: str, days: int | None = None) -> pd.DataFrame:
        data = self._data.get(symbol.upper().replace("^", ""), pd.DataFrame())
        if days is not None and not data.empty:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            data = data[data.index >= cutoff]
        return data

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        sym_data = _make_daily(300, start="2024-06-01")
        qqq_data = _make_daily(300, start="2024-06-01")
        vix_data = pd.DataFrame(
            {
                "Open": np.full(300, 18.0),
                "High": np.full(300, 19.0),
                "Low": np.full(300, 17.0),
                "Close": np.full(300, 18.0),
                "Volume": np.full(300, 5_000_000, dtype=int),
            },
            index=pd.bdate_range(start="2024-06-01", periods=300),
        )
        self._data: dict[str, pd.DataFrame] = {
            "TEST": sym_data,
            "QQQ": qqq_data,
            "VIX": vix_data,
        }

    @patch("app.signal_backtest.get_daily")
    def test_returns_valid_response(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_signal_backtest(
            "TEST",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 6, 1),
            horizons=[1, 5],
        )
        assert isinstance(result, SignalBacktestResponse)
        assert result.symbol == "TEST"
        assert result.error is None
        assert result.metrics.total_days >= 0
        assert len(result.equity_curve) > 0

    @patch("app.signal_backtest.get_daily")
    def test_outcomes_have_expected_fields(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_signal_backtest(
            "TEST",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 5, 1),
            horizons=[1, 5],
        )
        if result.outcomes:
            o = result.outcomes[0]
            assert isinstance(o, SignalOutcome)
            assert o.signal_level in ("强信号", "观察信号")
            assert o.price > 0

    @patch("app.signal_backtest.get_daily")
    def test_handles_missing_data(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.return_value = pd.DataFrame()
        result = run_signal_backtest("NOSYM")
        assert result.error is not None
        assert "No Parquet data" in result.error

    @patch("app.signal_backtest.get_daily")
    def test_metrics_hit_rate_bounded(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_signal_backtest(
            "TEST",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 6, 1),
        )
        assert 0.0 <= result.metrics.overall_hit_rate <= 1.0
        assert result.metrics.max_drawdown >= 0.0

    @patch("app.signal_backtest.get_daily")
    def test_horizon_breakdowns_present(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_signal_backtest(
            "TEST",
            start_date=date(2025, 1, 2),
            end_date=date(2025, 6, 1),
            horizons=[1, 5, 10],
        )
        horizon_labels = [h.horizon for h in result.metrics.by_horizon]
        assert "1d" in horizon_labels
        assert "5d" in horizon_labels
        assert "10d" in horizon_labels


class TestRunWalkForward:
    def _mock_get_daily(self, symbol: str, days: int | None = None) -> pd.DataFrame:
        data = self._data.get(symbol.upper().replace("^", ""), pd.DataFrame())
        if days is not None and not data.empty:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            data = data[data.index >= cutoff]
        return data

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        n = 500
        sym_data = _make_daily(n, start="2023-01-02")
        qqq_data = _make_daily(n, start="2023-01-02")
        vix_data = pd.DataFrame(
            {
                "Open": np.full(n, 18.0),
                "High": np.full(n, 19.0),
                "Low": np.full(n, 17.0),
                "Close": np.full(n, 18.0),
                "Volume": np.full(n, 5_000_000, dtype=int),
            },
            index=pd.bdate_range(start="2023-01-02", periods=n),
        )
        self._data: dict[str, pd.DataFrame] = {
            "WF": sym_data,
            "QQQ": qqq_data,
            "VIX": vix_data,
        }

    @patch("app.signal_backtest.get_daily")
    def test_returns_valid_response(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_walk_forward("WF", train_days=200, test_days=50, step_days=25, horizon=5)
        assert isinstance(result, WalkForwardResponse)
        assert result.symbol == "WF"
        assert result.error is None
        assert len(result.windows) > 0
        assert 0.0 <= result.avg_oos_hit_rate <= 1.0

    @patch("app.signal_backtest.get_daily")
    def test_stability_ratio_computed(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_walk_forward("WF", train_days=200, test_days=50, step_days=25)
        assert result.stability_ratio >= 0.0

    @patch("app.signal_backtest.get_daily")
    def test_handles_insufficient_data(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.return_value = _make_daily(50)
        result = run_walk_forward("SHORT", train_days=252, test_days=63)
        assert result.error is not None

    @patch("app.signal_backtest.get_daily")
    def test_windows_have_dates(self, mock_gd: object) -> None:
        import unittest.mock as m

        assert isinstance(mock_gd, m.MagicMock)
        mock_gd.side_effect = self._mock_get_daily
        result = run_walk_forward("WF", train_days=200, test_days=50, step_days=25)
        if result.windows:
            w = result.windows[0]
            assert w.train_start < w.train_end
            assert w.test_start < w.test_end
            assert w.train_end <= w.test_start
