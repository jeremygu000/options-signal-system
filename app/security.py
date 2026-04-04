"""API key authentication — Bearer token validation via FastAPI dependency."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


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
