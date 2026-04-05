from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.server import app


def _make_daily(n: int = 30, base: float = 100.0) -> pd.DataFrame:
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


def _make_intraday(n: int = 20) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 09:30", periods=n, freq="15min")
    closes = np.linspace(100.0, 99.5, n)
    return pd.DataFrame(
        {
            "Open": closes + 0.1,
            "High": closes + 0.5,
            "Low": closes - 0.5,
            "Close": closes,
            "Volume": np.full(n, 500_000),
        },
        index=idx,
    )


@pytest.fixture()
def client() -> TestClient:  # type: ignore[misc]
    with TestClient(app) as c:
        yield c  # type: ignore[misc]


class TestHealth:
    @patch("app.server.get_daily")
    def test_health_returns_ok(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily()  # type: ignore[union-attr]
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "data_status" in data
        assert "timestamp" in data

    @patch("app.server.get_daily")
    def test_health_backward_compat(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily()  # type: ignore[union-attr]
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestSymbols:
    @patch("app.server.get_daily")
    def test_list_symbols(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily()  # type: ignore[union-attr]
        resp = client.get("/api/v1/symbols")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "symbol" in data[0]
        assert "has_daily" in data[0]


class TestRegime:
    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_get_regime(self, mock_regime_daily: object, mock_server_daily: object, client: TestClient) -> None:
        def side_effect(symbol: str, days: int = 60) -> pd.DataFrame:
            return _make_daily()

        mock_regime_daily.side_effect = side_effect  # type: ignore[union-attr]
        mock_server_daily.return_value = _make_daily()  # type: ignore[union-attr]

        from app.server import get_regime_engine

        get_regime_engine.cache_clear()

        resp = client.get("/api/v1/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
        assert data["regime"] in ("risk_on", "neutral", "risk_off")


class TestValidation:
    def test_unknown_symbol_returns_400(self, client: TestClient) -> None:
        resp = client.get("/api/v1/indicators/INVALID_SYMBOL_XYZ")
        assert resp.status_code == 400

    def test_days_out_of_range(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ohlcv/QQQ?days=0")
        assert resp.status_code == 422

        resp = client.get("/api/v1/ohlcv/QQQ?days=999")
        assert resp.status_code == 422


class TestOHLCV:
    @patch("app.server.get_daily")
    def test_ohlcv_returns_paginated(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily(100)  # type: ignore[union-attr]
        resp = client.get("/api/v1/ohlcv/QQQ?days=90&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert len(data["data"]) <= 10

    @patch("app.server.get_daily")
    def test_ohlcv_empty(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = pd.DataFrame()  # type: ignore[union-attr]
        resp = client.get("/api/v1/ohlcv/QQQ")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0


class TestCompare:
    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_daily")
    def test_compare_basic(self, mock_daily: object, _mock_parquet: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily()  # type: ignore[union-attr]
        resp = client.get("/api/v1/compare?tickers=QQQ,USO")
        assert resp.status_code == 200
        data = resp.json()
        assert "QQQ" in data
        assert "USO" in data

    def test_compare_too_many_tickers(self, client: TestClient) -> None:
        tickers = ",".join([f"T{i}" for i in range(11)])
        resp = client.get(f"/api/v1/compare?tickers={tickers}")
        assert resp.status_code == 400

    def test_compare_unknown_symbol(self, client: TestClient) -> None:
        resp = client.get("/api/v1/compare?tickers=QQQ,FAKESYM")
        assert resp.status_code == 400


class TestMiddleware:
    @patch("app.server.get_daily")
    def test_request_id_header(self, mock_daily: object, client: TestClient) -> None:
        mock_daily.return_value = _make_daily()  # type: ignore[union-attr]
        resp = client.get("/api/v1/health")
        assert "x-request-id" in resp.headers
        assert "x-response-time" in resp.headers


def _make_options_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "underlying_symbol": ["USO"] * 4,
            "option_type": ["c", "c", "p", "p"],
            "expiration": pd.Timestamp("2025-05-16"),
            "quote_date": pd.Timestamp("2025-04-04"),
            "strike": [70.0, 75.0, 70.0, 75.0],
            "bid": [3.10, 1.20, 0.80, 2.50],
            "ask": [3.30, 1.40, 1.00, 2.70],
            "delta": [0.65, 0.40, -0.35, -0.60],
            "gamma": [0.03, 0.04, 0.03, 0.04],
            "theta": [-0.05, -0.04, -0.04, -0.05],
            "vega": [0.12, 0.15, 0.12, 0.15],
            "rho": [0.08, 0.06, -0.06, -0.08],
            "volume": [100, 200, 150, 250],
            "open_interest": [1000, 2000, 1500, 2500],
            "implied_volatility": [0.30, 0.32, 0.31, 0.33],
        }
    )


class TestOptionsChainDetail:
    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_options_chain_multi")
    def test_detail_returns_contracts(self, mock_chain: object, _mock_parquet: object, client: TestClient) -> None:
        mock_chain.return_value = _make_options_df()  # type: ignore[union-attr]
        resp = client.get("/api/v1/options/chain/USO/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "USO"
        assert data["total_contracts"] == 4
        assert data["calls_count"] == 2
        assert data["puts_count"] == 2
        assert len(data["contracts"]) == 4
        assert data["expirations"] == ["2025-05-16"]

        c = data["contracts"][0]
        assert c["option_type"] in ("c", "p")
        assert "strike" in c
        assert "delta" in c
        assert "gamma" in c
        assert "theta" in c
        assert "vega" in c
        assert "rho" in c

    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_options_chain")
    def test_detail_with_expiration_filter(self, mock_chain: object, _mock_parquet: object, client: TestClient) -> None:
        mock_chain.return_value = _make_options_df()  # type: ignore[union-attr]
        resp = client.get("/api/v1/options/chain/USO/detail?expiration=2025-05-16")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["contracts"]) == 4

    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_options_chain_multi")
    def test_detail_empty_chain(self, mock_chain: object, _mock_parquet: object, client: TestClient) -> None:
        mock_chain.return_value = pd.DataFrame()  # type: ignore[union-attr]
        resp = client.get("/api/v1/options/chain/USO/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "USO"
        assert data["total_contracts"] == 0
        assert data["contracts"] == []

    @patch("app.server.has_parquet_data", return_value=True)
    @patch("app.server.get_options_chain_multi")
    def test_detail_backward_compat(self, mock_chain: object, _mock_parquet: object, client: TestClient) -> None:
        mock_chain.return_value = _make_options_df()  # type: ignore[union-attr]
        resp = client.get("/api/options/chain/USO/detail")
        assert resp.status_code == 200
