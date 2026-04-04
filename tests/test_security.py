from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.server import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


VALID_KEY = "test-api-key-abc123"
WRONG_KEY = "wrong-key-xyz"


class TestApiKeyAuth:
    @patch("app.security.settings")
    def test_protected_route_rejects_without_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary")
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_protected_route_rejects_invalid_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {WRONG_KEY}"})
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_protected_route_accepts_valid_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_auth_disabled_allows_all(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = False  # type: ignore[attr-defined]
        mock_settings.api_keys = []  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary")
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_auth_enabled_no_keys_returns_503(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = []  # type: ignore[attr-defined]
        r = client.get(
            "/api/v1/portfolio/summary",
            headers={"Authorization": f"Bearer {VALID_KEY}"},
        )
        assert r.status_code == 503

    @patch("app.security.settings")
    def test_public_route_unaffected_by_auth(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_multiple_keys_accepted(self, mock_settings: object, client: TestClient) -> None:
        key2 = "second-api-key-def456"
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY, key2]  # type: ignore[attr-defined]
        r1 = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
        r2 = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {key2}"})
        assert r1.status_code == 200
        assert r2.status_code == 200

    @patch("app.security.settings")
    def test_broker_route_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/broker/account")
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_ml_train_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.post("/api/v1/ml/train", json={"lookback_days": 30})
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_positions_crud_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        r = client.get("/api/v1/positions")
        assert r.status_code == 401

        r = client.post(
            "/api/v1/positions",
            json={
                "symbol": "AAPL",
                "option_type": "call",
                "strike": 180.0,
                "expiration": "2025-12-19",
                "quantity": 1,
                "entry_price": 5.0,
            },
        )
        assert r.status_code == 401
