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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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

engine = create_async_engine(
    get_database_url(),
    echo=False,
    # SQLite-specific: allow same connection across threads for testing
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ── Session context manager ─────────────────────────────────────────


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session with automatic commit/rollback."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Init / teardown ──────────────────────────────────────────────────


async def init_db() -> None:
    """Create all tables if they don't exist."""
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import models so Base.metadata knows about them
    import app.position_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
