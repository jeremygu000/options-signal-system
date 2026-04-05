from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.broker import get_broker
from app.security import RateLimiter, rate_limiter
from app.server import app


@pytest.fixture()
def client() -> TestClient:  # type: ignore[misc]
    with TestClient(app) as c:
        yield c  # type: ignore[misc]


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    rate_limiter.reset()


VALID_KEY = "test-api-key-abc123"
WRONG_KEY = "wrong-key-xyz"


class TestApiKeyAuth:
    @patch("app.security.settings")
    def test_protected_route_rejects_without_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary")
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_protected_route_rejects_invalid_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {WRONG_KEY}"})
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_protected_route_accepts_valid_key(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_auth_disabled_allows_all(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = False  # type: ignore[attr-defined]
        mock_settings.api_keys = []  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get("/api/v1/portfolio/summary")
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_auth_enabled_no_keys_returns_503(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = []  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get(
            "/api/v1/portfolio/summary",
            headers={"Authorization": f"Bearer {VALID_KEY}"},
        )
        assert r.status_code == 503

    @patch("app.security.settings")
    def test_public_route_unaffected_by_auth(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    @patch("app.security.settings")
    def test_multiple_keys_accepted(self, mock_settings: object, client: TestClient) -> None:
        key2 = "second-api-key-def456"
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY, key2]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r1 = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
        r2 = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {key2}"})
        assert r1.status_code == 200
        assert r2.status_code == 200

    @patch("app.security.settings")
    def test_broker_route_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        app.dependency_overrides[get_broker] = lambda: MagicMock()
        try:
            r = client.get("/api/v1/broker/account")
            assert r.status_code == 401
        finally:
            app.dependency_overrides.pop(get_broker, None)

    @patch("app.security.settings")
    def test_ml_train_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
        r = client.post("/api/v1/ml/train", json={"lookback_days": 30})
        assert r.status_code == 401

    @patch("app.security.settings")
    def test_positions_crud_protected(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 60  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 120  # type: ignore[attr-defined]
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


class TestRateLimiter:
    def test_allows_requests_under_limit(self) -> None:
        limiter = RateLimiter()
        for _ in range(5):
            limiter.check("test-key", max_requests=5)

    def test_blocks_requests_over_limit(self) -> None:
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("test-key", max_requests=3)
        with pytest.raises(Exception, match="Rate limit exceeded"):
            limiter.check("test-key", max_requests=3)

    def test_separate_keys_independent(self) -> None:
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("key-a", max_requests=3)
        limiter.check("key-b", max_requests=3)

    def test_reset_clears_state(self) -> None:
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("test-key", max_requests=3)
        limiter.reset()
        limiter.check("test-key", max_requests=3)

    @patch("app.security.settings")
    def test_per_key_rate_limit_on_protected_route(self, mock_settings: object, client: TestClient) -> None:
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 1000  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 3  # type: ignore[attr-defined]

        headers = {"Authorization": f"Bearer {VALID_KEY}"}
        for _ in range(3):
            r = client.get("/api/v1/portfolio/summary", headers=headers)
            assert r.status_code == 200

        r = client.get("/api/v1/portfolio/summary", headers=headers)
        assert r.status_code == 429

    @patch("app.security.settings")
    def test_different_keys_have_separate_limits(self, mock_settings: object, client: TestClient) -> None:
        key2 = "second-key-for-rate-test"
        mock_settings.api_auth_enabled = True  # type: ignore[attr-defined]
        mock_settings.api_keys = [VALID_KEY, key2]  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_minute = 1000  # type: ignore[attr-defined]
        mock_settings.rate_limit_per_key_per_minute = 2  # type: ignore[attr-defined]

        for _ in range(2):
            r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
            assert r.status_code == 200

        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {VALID_KEY}"})
        assert r.status_code == 429

        r = client.get("/api/v1/portfolio/summary", headers={"Authorization": f"Bearer {key2}"})
        assert r.status_code == 200
