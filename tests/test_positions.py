from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.position_models import Position
from app.positions import (
    aggregate_greeks,
    calc_realized_pnl,
    calc_total_cost,
    calc_unrealized_pnl,
    close_position,
    create_position,
    delete_position,
    get_expiring_positions,
    get_position,
    group_by_strategy,
    list_positions,
    mark_expired_positions,
    refresh_greeks_for_position,
    update_position,
)

# ── In-memory test DB setup ──────────────────────────────────────────

_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

_test_session_factory = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def _test_session() -> AsyncIterator[AsyncSession]:
    async with _test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
def _setup_db() -> None:
    async def _init() -> None:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_init())


def _run(coro: object) -> object:
    return asyncio.get_event_loop().run_until_complete(coro)  # type: ignore[arg-type]


_FUTURE_EXP = date.today() + timedelta(days=30)
_PAST_EXP = date.today() - timedelta(days=5)


# ── CRUD tests ───────────────────────────────────────────────────────


class TestCreatePosition:
    def test_creates_with_defaults(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=2,
                    entry_price=5.50,
                )
                assert pos.id is not None
                assert len(pos.id) == 12
                assert pos.symbol == "AAPL"
                assert pos.option_type == "call"
                assert pos.strike == 150.0
                assert pos.quantity == 2
                assert pos.entry_price == 5.50
                assert pos.status == "open"
                assert pos.entry_commission == 0.0
                assert pos.tags == ""
                assert pos.notes == ""
                assert pos.delta == 0.0

        _run(_go())

    def test_creates_with_all_fields(self) -> None:
        async def _go() -> None:
            now = datetime(2025, 6, 1, 10, 0, 0)
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="spy",
                    option_type="put",
                    strike=500.0,
                    expiration=_FUTURE_EXP,
                    quantity=-3,
                    entry_price=8.25,
                    entry_date=now,
                    entry_commission=1.95,
                    strategy_name="iron_condor",
                    tags="hedge,weekly",
                    notes="Short put leg",
                )
                assert pos.symbol == "SPY"
                assert pos.quantity == -3
                assert pos.entry_date == now
                assert pos.entry_commission == 1.95
                assert pos.strategy_name == "iron_condor"
                assert pos.tags == "hedge,weekly"

        _run(_go())


class TestGetPosition:
    def test_get_existing(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="TSLA",
                    option_type="call",
                    strike=200.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=10.0,
                )
                pid = pos.id
            async with _test_session() as session:
                found = await get_position(session, pid)
                assert found is not None
                assert found.symbol == "TSLA"

        _run(_go())

    def test_get_nonexistent(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                found = await get_position(session, "nonexistent1")
                assert found is None

        _run(_go())


class TestListPositions:
    def test_list_all(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                await create_position(
                    session,
                    symbol="GOOG",
                    option_type="put",
                    strike=3000.0,
                    expiration=_FUTURE_EXP,
                    quantity=-1,
                    entry_price=20.0,
                )
            async with _test_session() as session:
                all_pos = await list_positions(session)
                assert len(all_pos) == 2

        _run(_go())

    def test_filter_by_status(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                await create_position(
                    session,
                    symbol="GOOG",
                    option_type="put",
                    strike=3000.0,
                    expiration=_FUTURE_EXP,
                    quantity=-1,
                    entry_price=20.0,
                )
                await close_position(session, pos.id, exit_price=7.0)
            async with _test_session() as session:
                open_only = await list_positions(session, status="open")
                assert len(open_only) == 1
                assert open_only[0].symbol == "GOOG"
                closed_only = await list_positions(session, status="closed")
                assert len(closed_only) == 1
                assert closed_only[0].symbol == "AAPL"

        _run(_go())

    def test_filter_by_symbol(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                await create_position(
                    session,
                    symbol="GOOG",
                    option_type="put",
                    strike=3000.0,
                    expiration=_FUTURE_EXP,
                    quantity=-1,
                    entry_price=20.0,
                )
            async with _test_session() as session:
                aapl = await list_positions(session, symbol="aapl")
                assert len(aapl) == 1
                assert aapl[0].symbol == "AAPL"

        _run(_go())

    def test_filter_by_strategy(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                await create_position(
                    session,
                    symbol="SPY",
                    option_type="call",
                    strike=500.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                    strategy_name="bull_call",
                )
                await create_position(
                    session,
                    symbol="SPY",
                    option_type="put",
                    strike=480.0,
                    expiration=_FUTURE_EXP,
                    quantity=-1,
                    entry_price=3.0,
                    strategy_name="iron_condor",
                )
            async with _test_session() as session:
                bull = await list_positions(session, strategy_name="bull_call")
                assert len(bull) == 1

        _run(_go())


class TestUpdatePosition:
    def test_update_fields(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                pid = pos.id
            async with _test_session() as session:
                updated = await update_position(session, pid, notes="updated notes", tags="new_tag")
                assert updated is not None
                assert updated.notes == "updated notes"
                assert updated.tags == "new_tag"

        _run(_go())

    def test_update_nonexistent(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                result = await update_position(session, "nope12345678", notes="x")
                assert result is None

        _run(_go())

    def test_update_ignores_disallowed_fields(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                pid = pos.id
            async with _test_session() as session:
                updated = await update_position(session, pid, status="closed", symbol="GOOG")
                assert updated is not None
                assert updated.status == "open"
                assert updated.symbol == "AAPL"

        _run(_go())


class TestClosePosition:
    def test_close_sets_status_and_exit(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                pid = pos.id
            async with _test_session() as session:
                closed = await close_position(session, pid, exit_price=8.0, exit_commission=0.65)
                assert closed is not None
                assert closed.status == "closed"
                assert closed.exit_price == 8.0
                assert closed.exit_commission == 0.65
                assert closed.exit_date is not None

        _run(_go())

    def test_close_already_closed_raises(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                await close_position(session, pos.id, exit_price=8.0)
            async with _test_session() as session:
                with pytest.raises(ValueError, match="already closed"):
                    await close_position(session, pos.id, exit_price=9.0)

        _run(_go())

    def test_close_nonexistent(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                result = await close_position(session, "nope12345678", exit_price=5.0)
                assert result is None

        _run(_go())


class TestDeletePosition:
    def test_delete_existing(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                pos = await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=5.0,
                )
                pid = pos.id
            async with _test_session() as session:
                assert await delete_position(session, pid) is True
            async with _test_session() as session:
                assert await get_position(session, pid) is None

        _run(_go())

    def test_delete_nonexistent(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                assert await delete_position(session, "nope12345678") is False

        _run(_go())


# ── P&L calculations ────────────────────────────────────────────────


class TestPnLCalculations:
    def _make_position(self, **overrides: object) -> Position:
        defaults = {
            "symbol": "AAPL",
            "option_type": "call",
            "strike": 150.0,
            "expiration": _FUTURE_EXP,
            "quantity": 1,
            "entry_price": 5.0,
            "entry_commission": 0.65,
            "exit_price": None,
            "exit_commission": 0.0,
            "status": "open",
        }
        defaults.update(overrides)
        pos = Position(**defaults)  # type: ignore[arg-type]
        return pos

    def test_unrealized_pnl_long(self) -> None:
        pos = self._make_position(quantity=2, entry_price=5.0)
        assert calc_unrealized_pnl(pos, 7.0) == 400.0

    def test_unrealized_pnl_short(self) -> None:
        pos = self._make_position(quantity=-1, entry_price=5.0)
        assert calc_unrealized_pnl(pos, 7.0) == -200.0

    def test_realized_pnl_closed_long(self) -> None:
        pos = self._make_position(
            quantity=1,
            entry_price=5.0,
            exit_price=8.0,
            status="closed",
            entry_commission=0.65,
            exit_commission=0.65,
        )
        expected = (8.0 - 5.0) * 1 * 100 - (0.65 + 0.65)
        assert calc_realized_pnl(pos) == round(expected, 2)

    def test_realized_pnl_open_returns_zero(self) -> None:
        pos = self._make_position(status="open")
        assert calc_realized_pnl(pos) == 0.0

    def test_total_cost(self) -> None:
        pos = self._make_position(quantity=3, entry_price=5.0, entry_commission=1.95)
        assert calc_total_cost(pos) == 5.0 * 3 * 100 + 1.95

    def test_total_cost_short(self) -> None:
        pos = self._make_position(quantity=-2, entry_price=4.0, entry_commission=1.30)
        assert calc_total_cost(pos) == 4.0 * 2 * 100 + 1.30


# ── Greeks ───────────────────────────────────────────────────────────


class TestGreeks:
    def _make_position(self, **overrides: object) -> Position:
        defaults = {
            "symbol": "AAPL",
            "option_type": "call",
            "strike": 150.0,
            "expiration": _FUTURE_EXP,
            "quantity": 1,
            "entry_price": 5.0,
            "status": "open",
            "delta": 0.5,
            "gamma": 0.03,
            "theta": -0.05,
            "vega": 0.15,
            "rho": 0.08,
        }
        defaults.update(overrides)
        return Position(**defaults)  # type: ignore[arg-type]

    def test_aggregate_greeks_single(self) -> None:
        pos = self._make_position(quantity=2, delta=0.5, gamma=0.03)
        result = aggregate_greeks([pos])
        assert result["delta"] == round(0.5 * 2 * 100, 4)
        assert result["gamma"] == round(0.03 * 2 * 100, 4)

    def test_aggregate_greeks_mixed(self) -> None:
        long_call = self._make_position(quantity=1, delta=0.6, gamma=0.04, theta=-0.05, vega=0.20, rho=0.10)
        short_put = self._make_position(quantity=-1, delta=-0.4, gamma=0.03, theta=-0.04, vega=0.15, rho=-0.08)
        result = aggregate_greeks([long_call, short_put])
        expected_delta = round(0.6 * 1 * 100 + (-0.4) * (-1) * 100, 4)
        assert result["delta"] == expected_delta

    def test_aggregate_skips_closed(self) -> None:
        open_pos = self._make_position(status="open", quantity=1, delta=0.5)
        closed_pos = self._make_position(status="closed", quantity=1, delta=0.5)
        result = aggregate_greeks([open_pos, closed_pos])
        assert result["delta"] == round(0.5 * 1 * 100, 4)

    def test_refresh_greeks(self) -> None:
        pos = self._make_position(
            option_type="call",
            strike=150.0,
            expiration=date.today() + timedelta(days=30),
        )
        refresh_greeks_for_position(pos, spot=150.0, risk_free_rate=0.05, iv=0.25)
        assert pos.delta != 0.0
        assert pos.gamma > 0
        assert pos.theta < 0

    def test_refresh_greeks_expired(self) -> None:
        pos = self._make_position(
            option_type="call",
            strike=150.0,
            expiration=date.today() - timedelta(days=1),
        )
        refresh_greeks_for_position(pos, spot=150.0)
        assert pos.delta == 0.0
        assert pos.gamma == 0.0


# ── Strategy grouping ────────────────────────────────────────────────


class TestGroupByStrategy:
    def _make_position(self, **overrides: object) -> Position:
        defaults = {
            "symbol": "SPY",
            "option_type": "call",
            "strike": 500.0,
            "expiration": _FUTURE_EXP,
            "quantity": 1,
            "entry_price": 5.0,
            "status": "open",
        }
        defaults.update(overrides)
        return Position(**defaults)  # type: ignore[arg-type]

    def test_groups_by_name(self) -> None:
        p1 = self._make_position(strategy_name="bull_call")
        p2 = self._make_position(strategy_name="bull_call")
        p3 = self._make_position(strategy_name="iron_condor")
        groups = group_by_strategy([p1, p2, p3])
        assert len(groups["bull_call"]) == 2
        assert len(groups["iron_condor"]) == 1

    def test_ungrouped_default(self) -> None:
        p1 = self._make_position(strategy_name=None)
        groups = group_by_strategy([p1])
        assert "ungrouped" in groups


# ── Expiration alerts ────────────────────────────────────────────────


class TestExpirationAlerts:
    def test_get_expiring_within_days(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                await create_position(
                    session,
                    symbol="AAPL",
                    option_type="call",
                    strike=150.0,
                    expiration=date.today() + timedelta(days=3),
                    quantity=1,
                    entry_price=5.0,
                )
                await create_position(
                    session,
                    symbol="GOOG",
                    option_type="put",
                    strike=3000.0,
                    expiration=date.today() + timedelta(days=30),
                    quantity=1,
                    entry_price=20.0,
                )
            async with _test_session() as session:
                expiring = await get_expiring_positions(session, days_ahead=7)
                assert len(expiring) == 1
                assert expiring[0].symbol == "AAPL"

        _run(_go())

    def test_mark_expired(self) -> None:
        async def _go() -> None:
            async with _test_session() as session:
                await create_position(
                    session,
                    symbol="OLD",
                    option_type="call",
                    strike=100.0,
                    expiration=_PAST_EXP,
                    quantity=1,
                    entry_price=2.0,
                )
                await create_position(
                    session,
                    symbol="NEW",
                    option_type="call",
                    strike=100.0,
                    expiration=_FUTURE_EXP,
                    quantity=1,
                    entry_price=2.0,
                )
            async with _test_session() as session:
                count = await mark_expired_positions(session)
                assert count == 1
            async with _test_session() as session:
                expired = await list_positions(session, status="expired")
                assert len(expired) == 1
                assert expired[0].symbol == "OLD"

        _run(_go())


# ── API endpoint tests ───────────────────────────────────────────────


class TestPositionEndpoints:
    def test_create_and_get(self) -> None:
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/positions",
                json={
                    "symbol": "AAPL",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": 2,
                    "entry_price": 5.5,
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["symbol"] == "AAPL"
            assert data["quantity"] == 2
            assert data["status"] == "open"

            pid = data["id"]
            resp2 = client.get(f"/api/v1/positions/{pid}")
            assert resp2.status_code == 200
            assert resp2.json()["id"] == pid

    def test_create_zero_quantity_rejected(self) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/positions",
                json={
                    "symbol": "AAPL",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": 0,
                    "entry_price": 5.0,
                },
            )
            assert resp.status_code == 400

    def test_list_and_filter(self) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            client.post(
                "/api/v1/positions",
                json={
                    "symbol": "AAPL",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": 1,
                    "entry_price": 5.0,
                },
            )
            client.post(
                "/api/v1/positions",
                json={
                    "symbol": "GOOG",
                    "option_type": "put",
                    "strike": 3000.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": -1,
                    "entry_price": 20.0,
                },
            )

            resp = client.get("/api/v1/positions")
            assert resp.status_code == 200
            assert len(resp.json()) == 2

            resp2 = client.get("/api/v1/positions?symbol=AAPL")
            assert len(resp2.json()) == 1

    def test_close_and_delete(self) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/positions",
                json={
                    "symbol": "AAPL",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": 1,
                    "entry_price": 5.0,
                },
            )
            pid = resp.json()["id"]

            close_resp = client.post(
                f"/api/v1/positions/{pid}/close",
                json={"exit_price": 8.0, "exit_commission": 0.65},
            )
            assert close_resp.status_code == 200
            assert close_resp.json()["status"] == "closed"
            assert close_resp.json()["realized_pnl"] is not None

            del_resp = client.delete(f"/api/v1/positions/{pid}")
            assert del_resp.status_code == 204

    def test_portfolio_summary(self) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            client.post(
                "/api/v1/positions",
                json={
                    "symbol": "AAPL",
                    "option_type": "call",
                    "strike": 150.0,
                    "expiration": _FUTURE_EXP.isoformat(),
                    "quantity": 1,
                    "entry_price": 5.0,
                },
            )
            resp = client.get("/api/v1/portfolio/summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_positions"] == 1
            assert data["open_positions"] == 1
            assert "greeks" in data

    def test_get_nonexistent_returns_404(self) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.server import app

        async def mock_init() -> None:
            pass

        async def mock_close() -> None:
            pass

        with (
            patch("app.server.init_db", mock_init),
            patch("app.server.close_db", mock_close),
            patch("app.server.get_session", _test_session),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/positions/nonexistent1")
            assert resp.status_code == 404
