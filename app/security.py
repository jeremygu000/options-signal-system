"""API key authentication + per-key rate limiting via FastAPI dependencies."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


# ── Rate Limiter ─────────────────────────────────────────────────────


class RateLimiter:
    """Sliding-window rate limiter with per-IP and per-API-key buckets.

    - Unauthenticated requests: limited by client IP.
    - Authenticated requests: limited by API key (hashed) independently of IP.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_requests: int, window: float = 60.0) -> None:
        """Check rate limit for *key*. Raises 429 if exceeded."""
        now = time.monotonic()
        timestamps = self._store[key]
        self._store[key] = [t for t in timestamps if now - t < window]
        if len(self._store[key]) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(int(window))},
            )
        self._store[key].append(now)

    def reset(self) -> None:
        """Clear all stored timestamps (useful for testing)."""
        self._store.clear()


rate_limiter = RateLimiter()


def check_rate_limit_ip(request: Request) -> None:
    """Check per-IP rate limit (used in global middleware)."""
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter.check(f"ip:{client_ip}", settings.rate_limit_per_minute)


def check_rate_limit_key(api_key: str) -> None:
    """Check per-API-key rate limit (called after auth validation)."""
    if api_key == "auth-disabled":
        return
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    rate_limiter.check(f"key:{key_hash}", settings.rate_limit_per_key_per_minute)


# ── API Key Validation ───────────────────────────────────────────────


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


async def require_api_key(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> str:
    """FastAPI dependency that validates Bearer token against configured API keys.

    Returns the validated API key (for logging/audit purposes).
    Raises 401 if auth is enabled and no valid key is provided.
    Also enforces per-API-key rate limiting for authenticated requests.
    """
    if not settings.api_auth_enabled:
        return "auth-disabled"

    if credentials is None:
        logger.warning(
            "Unauthenticated request to %s from %s",
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide Authorization: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    valid_keys = settings.api_keys

    if not valid_keys:
        logger.warning("API auth enabled but no keys configured — rejecting all requests")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is enabled but no keys are configured",
        )

    for valid_key in valid_keys:
        if _constant_time_compare(token, valid_key):
            check_rate_limit_key(token)
            return token

    logger.warning(
        "Invalid API key attempt on %s from %s",
        request.url.path,
        request.client.host if request.client else "unknown",
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


ApiKey = Annotated[str, Depends(require_api_key)]


def generate_api_key() -> str:
    """Generate a secure random API key (32-byte hex string)."""
    return secrets.token_hex(32)


def hash_api_key(key: str) -> str:
    """Hash an API key for safe logging/storage."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]
