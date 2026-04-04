"""SQLAlchemy ORM models for position management.

Single table design — easy to query, easy to migrate to PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import now_ny


def _generate_uuid() -> str:
    return uuid.uuid4().hex[:12]


class Position(Base):
    """Options position record.

    Columns are PostgreSQL-compatible types. SQLite handles them transparently.
    """

    __tablename__ = "positions"

    # ── Primary key ──────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_generate_uuid)

    # ── Contract identification ──────────────────────────────────────
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    option_type: Mapped[str] = mapped_column(String(4), nullable=False)  # 'call' or 'put'
    strike: Mapped[float] = mapped_column(Float, nullable=False)
    expiration: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Entry info ───────────────────────────────────────────────────
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # positive=long, negative=short
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)  # per-share price
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny)
    entry_commission: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Exit info (populated on close) ───────────────────────────────
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    exit_commission: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Status ───────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)
    # Values: "open", "closed", "expired"

    # ── Greeks snapshot (refreshed periodically) ─────────────────────
    delta: Mapped[float] = mapped_column(Float, default=0.0)
    gamma: Mapped[float] = mapped_column(Float, default=0.0)
    theta: Mapped[float] = mapped_column(Float, default=0.0)
    vega: Mapped[float] = mapped_column(Float, default=0.0)
    rho: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Metadata ─────────────────────────────────────────────────────
    strategy_name: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny, onupdate=now_ny)

    # ── Indexes for common queries ───────────────────────────────────
    __table_args__ = (
        Index("ix_positions_symbol_status", "symbol", "status"),
        Index("ix_positions_expiration", "expiration"),
        Index("ix_positions_strategy", "strategy_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<Position {self.id} {self.symbol} {self.option_type} "
            f"K={self.strike} exp={self.expiration} qty={self.quantity} "
            f"status={self.status}>"
        )
