"""Watchlist manager — CRUD for watchlists and their items, plus seeding."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.utils import now_ny
from app.watchlist_models import Watchlist, WatchlistItem

VALID_BIASES = {"long", "short", "auto"}

DEFAULT_WATCHLIST_ITEMS: list[dict[str, str]] = [
    # Technology
    {"symbol": "AAPL", "sector": "Technology", "bias": "auto"},
    {"symbol": "MSFT", "sector": "Technology", "bias": "auto"},
    {"symbol": "GOOGL", "sector": "Technology", "bias": "auto"},
    {"symbol": "AMZN", "sector": "Technology", "bias": "auto"},
    {"symbol": "NVDA", "sector": "Technology", "bias": "auto"},
    {"symbol": "META", "sector": "Technology", "bias": "auto"},
    {"symbol": "TSLA", "sector": "Technology", "bias": "auto"},
    {"symbol": "CRM", "sector": "Technology", "bias": "long"},
    # Finance
    {"symbol": "JPM", "sector": "Finance", "bias": "auto"},
    {"symbol": "GS", "sector": "Finance", "bias": "auto"},
    {"symbol": "BAC", "sector": "Finance", "bias": "auto"},
    {"symbol": "V", "sector": "Finance", "bias": "auto"},
    # Energy
    {"symbol": "XOM", "sector": "Energy", "bias": "short"},
    {"symbol": "CVX", "sector": "Energy", "bias": "auto"},
    {"symbol": "USO", "sector": "Energy", "bias": "short"},
    {"symbol": "XLE", "sector": "Energy", "bias": "short"},
    # Healthcare
    {"symbol": "JNJ", "sector": "Healthcare", "bias": "auto"},
    {"symbol": "UNH", "sector": "Healthcare", "bias": "auto"},
    {"symbol": "PFE", "sector": "Healthcare", "bias": "auto"},
    # Consumer
    {"symbol": "WMT", "sector": "Consumer", "bias": "auto"},
    {"symbol": "KO", "sector": "Consumer", "bias": "auto"},
    {"symbol": "MCD", "sector": "Consumer", "bias": "auto"},
    # ETFs / Index
    {"symbol": "SPY", "sector": "ETF", "bias": "auto"},
    {"symbol": "QQQ", "sector": "ETF", "bias": "auto"},
    {"symbol": "IWM", "sector": "ETF", "bias": "auto"},
    {"symbol": "DIA", "sector": "ETF", "bias": "auto"},
]


# ── Watchlist CRUD ───────────────────────────────────────────────────


async def create_watchlist(
    session: AsyncSession,
    *,
    name: str,
    description: str = "",
    is_active: bool = False,
) -> Watchlist:
    wl = Watchlist(name=name, description=description, is_active=is_active)
    session.add(wl)
    await session.flush()
    if is_active:
        await _deactivate_others(session, exclude_id=wl.id)
        await session.flush()
    return wl


async def get_watchlist(session: AsyncSession, watchlist_id: str) -> Watchlist | None:
    stmt = (
        select(Watchlist)
        .where(Watchlist.id == watchlist_id)
        .options(selectinload(Watchlist.items))
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_watchlists(session: AsyncSession) -> Sequence[Watchlist]:
    stmt = (
        select(Watchlist)
        .order_by(Watchlist.created_at.asc())
        .options(selectinload(Watchlist.items))
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_watchlist(
    session: AsyncSession,
    watchlist_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Watchlist | None:
    wl = await get_watchlist(session, watchlist_id)
    if wl is None:
        return None
    if name is not None:
        wl.name = name
    if description is not None:
        wl.description = description
    wl.updated_at = now_ny()
    await session.flush()
    return wl


async def activate_watchlist(session: AsyncSession, watchlist_id: str) -> Watchlist | None:
    wl = await get_watchlist(session, watchlist_id)
    if wl is None:
        return None
    await _deactivate_others(session, exclude_id=watchlist_id)
    wl.is_active = True
    wl.updated_at = now_ny()
    await session.flush()
    return wl


async def delete_watchlist(session: AsyncSession, watchlist_id: str) -> bool:
    wl = await get_watchlist(session, watchlist_id)
    if wl is None:
        return False
    await session.delete(wl)
    await session.flush()
    return True


async def get_active_watchlist(session: AsyncSession) -> Watchlist | None:
    stmt = (
        select(Watchlist)
        .where(Watchlist.is_active.is_(True))
        .options(selectinload(Watchlist.items))
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_symbols(session: AsyncSession) -> list[str]:
    wl = await get_active_watchlist(session)
    if wl is None:
        return []
    return [item.symbol for item in wl.items]


async def get_active_bias_map(session: AsyncSession) -> dict[str, str]:
    wl = await get_active_watchlist(session)
    if wl is None:
        return {}
    return {item.symbol: item.bias for item in wl.items}


# ── WatchlistItem CRUD ───────────────────────────────────────────────


async def add_item(
    session: AsyncSession,
    watchlist_id: str,
    *,
    symbol: str,
    sector: str = "",
    bias: str = "auto",
    sort_order: int = 0,
) -> WatchlistItem | None:
    wl = await get_watchlist(session, watchlist_id)
    if wl is None:
        return None
    item = WatchlistItem(
        watchlist_id=watchlist_id,
        symbol=symbol.upper(),
        sector=sector,
        bias=bias if bias in VALID_BIASES else "auto",
        sort_order=sort_order,
    )
    session.add(item)
    await session.flush()
    return item


async def remove_item(session: AsyncSession, item_id: str) -> bool:
    item = await session.get(WatchlistItem, item_id)
    if item is None:
        return False
    await session.delete(item)
    await session.flush()
    return True


async def update_item(
    session: AsyncSession,
    item_id: str,
    *,
    sector: str | None = None,
    bias: str | None = None,
    sort_order: int | None = None,
) -> WatchlistItem | None:
    item = await session.get(WatchlistItem, item_id)
    if item is None:
        return None
    if sector is not None:
        item.sector = sector
    if bias is not None and bias in VALID_BIASES:
        item.bias = bias
    if sort_order is not None:
        item.sort_order = sort_order
    await session.flush()
    return item


# ── Seed ─────────────────────────────────────────────────────────────


async def seed_default_watchlist(session: AsyncSession) -> Watchlist | None:
    existing = await list_watchlists(session)
    if existing:
        return None

    wl = Watchlist(name="Default", description="Auto-seeded watchlist with popular tickers", is_active=True)
    session.add(wl)
    await session.flush()

    for idx, item_data in enumerate(DEFAULT_WATCHLIST_ITEMS):
        session.add(
            WatchlistItem(
                watchlist_id=wl.id,
                symbol=item_data["symbol"],
                sector=item_data["sector"],
                bias=item_data["bias"],
                sort_order=idx,
            )
        )
    await session.flush()
    return wl


# ── Internal helpers ─────────────────────────────────────────────────


async def _deactivate_others(session: AsyncSession, exclude_id: str) -> None:
    stmt = (
        update(Watchlist)
        .where(Watchlist.is_active.is_(True))
        .where(Watchlist.id != exclude_id)
        .values(is_active=False, updated_at=now_ny())
    )
    await session.execute(stmt)
