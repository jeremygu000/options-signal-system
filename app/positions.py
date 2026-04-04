"""Position manager — CRUD, P&L, Greeks aggregation, alerts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.greeks import calculate_greeks
from app.position_models import Position
from app.utils import now_ny

CONTRACT_MULTIPLIER = 100


async def create_position(
    session: AsyncSession,
    *,
    symbol: str,
    option_type: str,
    strike: float,
    expiration: date,
    quantity: int,
    entry_price: float,
    entry_date: datetime | None = None,
    entry_commission: float = 0.0,
    strategy_name: str | None = None,
    tags: str = "",
    notes: str = "",
) -> Position:
    pos = Position(
        symbol=symbol.upper(),
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        quantity=quantity,
        entry_price=entry_price,
        entry_date=entry_date or now_ny(),
        entry_commission=entry_commission,
        strategy_name=strategy_name,
        tags=tags,
        notes=notes,
    )
    session.add(pos)
    await session.flush()
    return pos


async def get_position(session: AsyncSession, position_id: str) -> Position | None:
    return await session.get(Position, position_id)


async def list_positions(
    session: AsyncSession,
    *,
    status: str | None = None,
    symbol: str | None = None,
    strategy_name: str | None = None,
) -> Sequence[Position]:
    stmt = select(Position).order_by(Position.expiration.asc(), Position.created_at.desc())
    if status:
        stmt = stmt.where(Position.status == status)
    if symbol:
        stmt = stmt.where(Position.symbol == symbol.upper())
    if strategy_name:
        stmt = stmt.where(Position.strategy_name == strategy_name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_position(
    session: AsyncSession,
    position_id: str,
    **kwargs: object,
) -> Position | None:
    pos = await session.get(Position, position_id)
    if pos is None:
        return None

    allowed = {
        "notes",
        "tags",
        "strategy_name",
        "entry_price",
        "entry_commission",
        "quantity",
    }
    for key, value in kwargs.items():
        if key in allowed:
            setattr(pos, key, value)

    pos.updated_at = now_ny()
    await session.flush()
    return pos


async def close_position(
    session: AsyncSession,
    position_id: str,
    *,
    exit_price: float,
    exit_commission: float = 0.0,
    exit_date: datetime | None = None,
) -> Position | None:
    pos = await session.get(Position, position_id)
    if pos is None:
        return None
    if pos.status != "open":
        raise ValueError(f"Position {position_id} is already {pos.status}")

    pos.exit_price = exit_price
    pos.exit_commission = exit_commission
    pos.exit_date = exit_date or now_ny()
    pos.status = "closed"
    pos.updated_at = now_ny()
    await session.flush()
    return pos


async def delete_position(session: AsyncSession, position_id: str) -> bool:
    pos = await session.get(Position, position_id)
    if pos is None:
        return False
    await session.delete(pos)
    await session.flush()
    return True


# ── P&L calculations ────────────────────────────────────────────────


def calc_unrealized_pnl(pos: Position, current_price: float) -> float:
    """(current_price - entry_price) × quantity × multiplier"""
    return round((current_price - pos.entry_price) * pos.quantity * CONTRACT_MULTIPLIER, 2)


def calc_realized_pnl(pos: Position) -> float:
    if pos.status != "closed" or pos.exit_price is None:
        return 0.0
    gross = (pos.exit_price - pos.entry_price) * pos.quantity * CONTRACT_MULTIPLIER
    commissions = pos.entry_commission + pos.exit_commission
    return round(gross - commissions, 2)


def calc_total_cost(pos: Position) -> float:
    return round(pos.entry_price * abs(pos.quantity) * CONTRACT_MULTIPLIER + pos.entry_commission, 2)


# ── Greeks aggregation ──────────────────────────────────────────────


def refresh_greeks_for_position(
    pos: Position,
    spot: float,
    risk_free_rate: float = 0.05,
    iv: float | None = None,
) -> None:
    """Recalculate Greeks for a single position using current spot price."""
    days_to_exp = (pos.expiration - date.today()).days
    if days_to_exp < 0:
        pos.delta = pos.gamma = pos.theta = pos.vega = pos.rho = 0.0
        return

    otype = "c" if pos.option_type == "call" else "p"
    implied_vol = iv if iv is not None else 0.30

    result = calculate_greeks(
        spot=spot,
        strike=pos.strike,
        dte_days=days_to_exp,
        risk_free_rate=risk_free_rate,
        iv=implied_vol,
        option_type=otype,
    )
    pos.delta = result.delta
    pos.gamma = result.gamma
    pos.theta = result.theta
    pos.vega = result.vega
    pos.rho = result.rho


def aggregate_greeks(positions: Sequence[Position]) -> dict[str, float]:
    """Sum Greeks across positions: greek × quantity × multiplier."""
    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for p in positions:
        if p.status != "open":
            continue
        totals["delta"] += p.delta * p.quantity * CONTRACT_MULTIPLIER
        totals["gamma"] += p.gamma * p.quantity * CONTRACT_MULTIPLIER
        totals["theta"] += p.theta * p.quantity * CONTRACT_MULTIPLIER
        totals["vega"] += p.vega * p.quantity * CONTRACT_MULTIPLIER
        totals["rho"] += p.rho * p.quantity * CONTRACT_MULTIPLIER
    return {k: round(v, 4) for k, v in totals.items()}


# ── Strategy grouping ───────────────────────────────────────────────


def group_by_strategy(positions: Sequence[Position]) -> dict[str, list[Position]]:
    groups: dict[str, list[Position]] = {}
    for p in positions:
        key = p.strategy_name or "ungrouped"
        groups.setdefault(key, []).append(p)
    return groups


# ── Expiration alerts ────────────────────────────────────────────────


async def get_expiring_positions(
    session: AsyncSession,
    days_ahead: int = 7,
) -> Sequence[Position]:
    cutoff = date.today() + timedelta(days=days_ahead)
    stmt = (
        select(Position)
        .where(Position.status == "open")
        .where(Position.expiration <= cutoff)
        .order_by(Position.expiration.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Batch mark expired ──────────────────────────────────────────────


async def mark_expired_positions(session: AsyncSession) -> int:
    today = date.today()
    stmt = (
        update(Position)
        .where(Position.status == "open")
        .where(Position.expiration < today)
        .values(status="expired", updated_at=now_ny())
    )
    result: CursorResult[tuple[()]] = await session.execute(stmt)  # type: ignore[assignment]
    return result.rowcount
