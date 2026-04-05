"""Database layer — async SQLAlchemy with SQLite (PostgreSQL-ready ORM).

Usage:
    from app.database import get_session, init_db

    # At app startup:
    await init_db()

    # In endpoints:
    async with get_session() as session:
        ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Database path ────────────────────────────────────────────────────

_db_path: Path = settings.parquet_dir / "positions.db"


def get_database_url() -> str:
    """Return the async database URL.

    For SQLite:   sqlite+aiosqlite:///path/to/db
    For Postgres: postgresql+asyncpg://user:pass@host/db
    """
    return f"sqlite+aiosqlite:///{_db_path}"


# ── Engine & session factory ─────────────────────────────────────────
# Lazy initialisation: engine/session_factory are created by init_db()
# and disposed by close_db().  This avoids stale-engine bugs when the
# app lifespan runs more than once (e.g. multiple TestClient instances
# across test files).

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_engine() -> AsyncEngine:
    return create_async_engine(
        get_database_url(),
        echo=False,
        connect_args={"check_same_thread": False},
    )


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ── Session context manager ─────────────────────────────────────────


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session with automatic commit/rollback."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Init / teardown ──────────────────────────────────────────────────


async def init_db() -> None:
    """Create all tables if they don't exist.

    Safe to call multiple times — (re)creates the engine when needed.
    """
    global _engine, _session_factory

    _db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import models so Base.metadata knows about them
    import app.position_models  # noqa: F401
    import app.watchlist_models  # noqa: F401

    _engine = _create_engine()
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    engine = _engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
