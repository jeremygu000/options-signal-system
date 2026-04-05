from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.symbol_discovery import SymbolMeta, build_metadata_index, clear_discovery_cache, search_symbols


@pytest.fixture()
def client() -> TestClient:  # type: ignore[misc]
    with TestClient(app) as c:
        yield c  # type: ignore[misc]


@pytest.fixture()
def parquet_dir(tmp_path: Path) -> Path:
    rng = np.random.default_rng(42)
    for sym in ["AAPL", "MSFT", "GOOG"]:
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=252)
        n = len(dates)
        closes = 100.0 + np.cumsum(rng.normal(0, 1, n))
        df = pd.DataFrame(
            {
                "Open": closes + rng.normal(0, 0.5, n),
                "High": closes + rng.uniform(0.5, 2.0, n),
                "Low": closes - rng.uniform(0.5, 2.0, n),
                "Close": closes,
                "Volume": rng.integers(1_000_000, 10_000_000, n).astype(float),
            },
            index=pd.DatetimeIndex(dates, name="Date"),
        )
        df.to_parquet(tmp_path / f"{sym}_1d.parquet")
    return tmp_path


class TestBuildMetadataIndex:
    def test_returns_all_symbols(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            result = build_metadata_index(force=True)
        symbols = {m.symbol for m in result}
        assert symbols == {"AAPL", "MSFT", "GOOG"}

    def test_metadata_fields(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            result = build_metadata_index(force=True)
        aapl = next(m for m in result if m.symbol == "AAPL")
        assert aapl.rows > 200
        assert aapl.avg_volume > 0
        assert aapl.last_close != 0.0
        assert aapl.first_date != ""
        assert aapl.last_date != ""

    def test_empty_dir(self, tmp_path: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = tmp_path
            result = build_metadata_index(force=True)
        assert result == []

    def test_nonexistent_dir(self) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = Path("/nonexistent/dir")
            result = build_metadata_index(force=True)
        assert result == []

    def test_cache_hit(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            first = build_metadata_index(force=True)
            second = build_metadata_index(force=False)
        assert first is second


class TestSearchSymbols:
    def test_filter_by_query(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            build_metadata_index(force=True)
            items, total = search_symbols(query="AA")
        assert total == 1
        assert items[0].symbol == "AAPL"

    def test_sort_by_volume(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            build_metadata_index(force=True)
            items, total = search_symbols(sort_by="volume")
        assert total == 3
        assert items[0].avg_volume >= items[1].avg_volume

    def test_pagination(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            build_metadata_index(force=True)
            items, total = search_symbols(limit=2, offset=0)
        assert len(items) == 2
        assert total == 3

    def test_min_volume_filter(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            build_metadata_index(force=True)
            items, total = search_symbols(min_volume=999_999_999)
        assert total == 0

    def test_min_rows_filter(self, parquet_dir: Path) -> None:
        clear_discovery_cache()
        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            build_metadata_index(force=True)
            items, total = search_symbols(min_rows=200)
        assert total == 3


class TestGetAvailableSymbolsDuckDB:
    def test_returns_symbols(self, parquet_dir: Path) -> None:
        from app.symbol_discovery import get_available_symbols_duckdb

        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = parquet_dir
            symbols = get_available_symbols_duckdb()
        assert symbols == {"AAPL", "MSFT", "GOOG"}

    def test_empty_dir(self, tmp_path: Path) -> None:
        from app.symbol_discovery import get_available_symbols_duckdb

        with patch("app.symbol_discovery.settings") as mock_settings:
            mock_settings.parquet_dir = tmp_path
            symbols = get_available_symbols_duckdb()
        assert symbols == set()


class TestDiscoveryEndpoints:
    @patch("app.server.get_available_symbols")
    def test_available_symbols(self, mock_avail: Any, client: TestClient) -> None:
        mock_avail.return_value = {"AAPL", "MSFT", "GOOG"}
        resp = client.get("/api/v1/symbols/available")
        assert resp.status_code == 200
        data = resp.json()
        assert data == ["AAPL", "GOOG", "MSFT"]

    @patch("app.server.search_symbols")
    def test_search_symbols(self, mock_search: Any, client: TestClient) -> None:
        mock_search.return_value = (
            [
                SymbolMeta(
                    symbol="AAPL",
                    rows=252,
                    first_date="2024-01-02",
                    last_date="2025-01-02",
                    avg_volume=5_000_000.0,
                    last_close=195.5,
                    return_1y=0.25,
                )
            ],
            1,
        )
        resp = client.get("/api/v1/symbols/search?query=AA&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "AAPL"
        assert data["offset"] == 0
        assert data["limit"] == 10

    @patch("app.server.build_metadata_index")
    def test_metadata_all(self, mock_index: Any, client: TestClient) -> None:
        mock_index.return_value = [
            SymbolMeta(
                symbol="MSFT",
                rows=500,
                first_date="2023-01-01",
                last_date="2025-01-01",
                avg_volume=8_000_000.0,
                last_close=400.0,
                return_1y=0.30,
            )
        ]
        resp = client.get("/api/v1/symbols/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "MSFT"


class TestStrategyEngineAutoDetect:
    def test_auto_detect_long_bias(self) -> None:
        from app.strategy_engine import StrategyEngine

        rng = np.random.default_rng(42)
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=60)
        n = len(dates)
        closes = np.linspace(100, 130, n)
        daily = pd.DataFrame(
            {
                "Open": closes,
                "High": closes + 1,
                "Low": closes - 1,
                "Close": closes,
                "Volume": rng.integers(1_000_000, 10_000_000, n),
            },
            index=dates,
        )
        intraday = pd.DataFrame(
            {
                "Open": [130.0],
                "High": [131.0],
                "Low": [129.0],
                "Close": [130.0],
                "Volume": [1_000_000],
            },
            index=pd.date_range("2024-01-02 09:30", periods=1, freq="15min"),
        )

        from app.models import MarketRegime, MarketRegimeResult

        regime = MarketRegimeResult(regime=MarketRegime.RISK_ON, reasons=["test"])

        engine = StrategyEngine()
        with (
            patch("app.strategy_engine.get_daily", return_value=daily),
            patch("app.strategy_engine.get_intraday", return_value=intraday),
        ):
            signal = engine.evaluate_symbol("NEWSTOCK", regime)

        from app.models import Bias

        assert signal.bias == Bias.LONG

    def test_configured_short_symbol(self) -> None:
        from app.strategy_engine import StrategyEngine

        rng = np.random.default_rng(42)
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=60)
        n = len(dates)
        closes = 100.0 + np.cumsum(rng.normal(0, 1, n))
        daily = pd.DataFrame(
            {
                "Open": closes,
                "High": closes + 1,
                "Low": closes - 1,
                "Close": closes,
                "Volume": rng.integers(1_000_000, 10_000_000, n),
            },
            index=dates,
        )
        intraday = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.0],
                "Volume": [1_000_000],
            },
            index=pd.date_range("2024-01-02 09:30", periods=1, freq="15min"),
        )

        from app.models import MarketRegime, MarketRegimeResult

        regime = MarketRegimeResult(regime=MarketRegime.NEUTRAL, reasons=["test"])

        engine = StrategyEngine(bias_map={"NEWSTOCK": "short"})
        with (
            patch("app.strategy_engine.get_daily", return_value=daily),
            patch("app.strategy_engine.get_intraday", return_value=intraday),
        ):
            signal = engine.evaluate_symbol("NEWSTOCK", regime)

        from app.models import Bias

        assert signal.bias == Bias.SHORT


class TestDynamicSymbolValidation:
    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_daily")
    def test_dynamic_symbol_accepted(self, mock_daily: Any, mock_has: Any, client: TestClient) -> None:
        rng = np.random.default_rng(42)
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=30)
        n = len(dates)
        closes = 100.0 + np.cumsum(rng.normal(0, 1, n))
        df = pd.DataFrame(
            {
                "Open": closes,
                "High": closes + 1,
                "Low": closes - 1,
                "Close": closes,
                "Volume": rng.integers(1_000_000, 10_000_000, n),
            },
            index=dates,
        )
        mock_daily.return_value = df
        resp = client.get("/api/v1/ohlcv/NEWSTOCK")
        assert resp.status_code == 200

    @patch("app.server.has_parquet_data", return_value=False)
    def test_unknown_symbol_rejected(self, mock_has: Any, client: TestClient) -> None:
        resp = client.get("/api/v1/ohlcv/NOSUCHSYMBOL")
        assert resp.status_code == 400
        assert "No Parquet data found" in resp.json()["detail"]
