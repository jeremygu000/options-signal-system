from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.data_provider import _parquet_path, _sanitize_ticker, clear_cache, get_daily, get_intraday


def _make_parquet_df(n: int = 30) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n)
    rng = np.random.default_rng(42)
    size = len(dates)
    return pd.DataFrame(
        {
            "Open": rng.uniform(90, 110, size),
            "High": rng.uniform(100, 120, size),
            "Low": rng.uniform(80, 100, size),
            "Close": rng.uniform(90, 110, size),
            "Volume": rng.integers(1_000_000, 10_000_000, size),
        },
        index=dates,
    )


class TestSanitizeTicker:
    def test_caret_removed(self) -> None:
        assert _sanitize_ticker("^VIX") == "VIX"

    def test_slashes_replaced(self) -> None:
        assert _sanitize_ticker("BRK/B") == "BRK_B"

    def test_uppercased(self) -> None:
        assert _sanitize_ticker("qqq") == "QQQ"


class TestGetDaily:
    @patch("app.data_provider._parquet_path")
    def test_returns_empty_when_no_file(self, mock_path: MagicMock) -> None:
        mock_path.return_value = Path("/nonexistent/fake.parquet")
        clear_cache()
        df = get_daily("FAKE")
        assert df.empty

    @patch("app.data_provider.pd.read_parquet")
    @patch("app.data_provider._parquet_path")
    def test_reads_parquet_file(self, mock_path: MagicMock, mock_read: MagicMock, tmp_path: Path) -> None:
        fake_file = tmp_path / "QQQ.parquet"
        fake_file.touch()
        mock_path.return_value = fake_file
        mock_read.return_value = _make_parquet_df()
        clear_cache()

        df = get_daily("QQQ")
        assert not df.empty
        assert len(df) > 0
        mock_read.assert_called_once_with(fake_file)

    @patch("app.data_provider.pd.read_parquet")
    @patch("app.data_provider._parquet_path")
    def test_filters_by_days(self, mock_path: MagicMock, mock_read: MagicMock, tmp_path: Path) -> None:
        fake_file = tmp_path / "QQQ.parquet"
        fake_file.touch()
        mock_path.return_value = fake_file
        mock_read.return_value = _make_parquet_df(60)
        clear_cache()

        df = get_daily("QQQ", days=10)
        assert len(df) <= 10

    @patch("app.data_provider.pd.read_parquet")
    @patch("app.data_provider._parquet_path")
    def test_cache_hit_skips_io(self, mock_path: MagicMock, mock_read: MagicMock, tmp_path: Path) -> None:
        fake_file = tmp_path / "QQQ.parquet"
        fake_file.touch()
        mock_path.return_value = fake_file
        mock_read.return_value = _make_parquet_df()
        clear_cache()

        get_daily("QQQ")
        get_daily("QQQ")
        mock_read.assert_called_once()


class TestGetIntraday:
    @patch("app.data_provider.yf.Ticker")
    def test_returns_data(self, mock_ticker_cls: MagicMock) -> None:
        idx = pd.date_range("2024-01-02 09:30", periods=10, freq="15min")
        mock_df = pd.DataFrame(
            {"Open": [100] * 10, "High": [101] * 10, "Low": [99] * 10, "Close": [100] * 10, "Volume": [1000] * 10},
            index=idx,
        )
        mock_ticker_cls.return_value.history.return_value = mock_df
        clear_cache()

        df = get_intraday("QQQ")
        assert not df.empty
        assert len(df) == 10

    @patch("app.data_provider.yf.Ticker")
    def test_returns_empty_on_error(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker_cls.return_value.history.side_effect = Exception("network")
        clear_cache()

        df = get_intraday("QQQ")
        assert df.empty

    @patch("app.data_provider.yf.Ticker")
    def test_cache_hit_skips_network(self, mock_ticker_cls: MagicMock) -> None:
        idx = pd.date_range("2024-01-02 09:30", periods=5, freq="15min")
        mock_df = pd.DataFrame(
            {"Open": [100] * 5, "High": [101] * 5, "Low": [99] * 5, "Close": [100] * 5, "Volume": [1000] * 5},
            index=idx,
        )
        mock_ticker_cls.return_value.history.return_value = mock_df
        clear_cache()

        get_intraday("QQQ")
        get_intraday("QQQ")
        mock_ticker_cls.return_value.history.assert_called_once()


class TestClearCache:
    @patch("app.data_provider.pd.read_parquet")
    @patch("app.data_provider._parquet_path")
    def test_clear_forces_re_read(self, mock_path: MagicMock, mock_read: MagicMock, tmp_path: Path) -> None:
        fake_file = tmp_path / "QQQ.parquet"
        fake_file.touch()
        mock_path.return_value = fake_file
        mock_read.return_value = _make_parquet_df()
        clear_cache()

        get_daily("QQQ")
        assert mock_read.call_count == 1

        clear_cache()
        get_daily("QQQ")
        assert mock_read.call_count == 2
