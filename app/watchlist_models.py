"""SQLAlchemy ORM models for watchlist management.

Two-table design: Watchlist (parent) → WatchlistItem (child).
One watchlist is marked ``is_active`` at a time — that list drives the
signal engine scan, dashboard compare, and WebSocket broadcasts.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_ny


def _generate_uuid() -> str:
    return uuid.uuid4().hex[:12]


class Watchlist(Base):
    """A named collection of symbols the user wants to track."""

    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny, onupdate=now_ny)

    items: Mapped[list[WatchlistItem]] = relationship(
        "WatchlistItem",
        back_populates="watchlist",
        cascade="all, delete-orphan",
        order_by="WatchlistItem.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Watchlist {self.id} name={self.name!r} active={self.is_active}>"


class WatchlistItem(Base):
    """A single symbol entry inside a watchlist."""

    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_generate_uuid)
    watchlist_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    sector: Mapped[str] = mapped_column(String(50), default="")  # e.g. "Technology", "Energy"
    bias: Mapped[str] = mapped_column(String(10), default="auto")  # "long", "short", "auto"
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_ny)

    watchlist: Mapped[Watchlist] = relationship("Watchlist", back_populates="items")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),
        Index("ix_watchlist_items_sector", "sector"),
    )

    def __repr__(self) -> str:
        return f"<WatchlistItem {self.id} {self.symbol} sector={self.sector!r} bias={self.bias}>"
