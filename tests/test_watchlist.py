from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_session
from app.models import WatchlistCreate, WatchlistItemCreate, WatchlistUpdate, WatchlistItemUpdate
from app.server import app
from app.watchlist import (
    activate_watchlist,
    add_item,
    create_watchlist,
    delete_watchlist,
    get_active_symbols,
    get_active_watchlist,
    get_watchlist,
    list_watchlists,
    remove_item,
    seed_default_watchlist,
    update_item,
    update_watchlist,
)
from app.watchlist_models import Watchlist, WatchlistItem


@pytest.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestWatchlistCRUD:
    async def test_create_watchlist(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test", description="Test watchlist", is_active=False)
        assert wl.name == "Test"
        assert wl.description == "Test watchlist"
        assert wl.is_active is False
        assert wl.id is not None

    async def test_create_watchlist_active(self, db_session: AsyncSession) -> None:
        wl1 = await create_watchlist(db_session, name="First", is_active=True)
        wl2 = await create_watchlist(db_session, name="Second", is_active=True)
        refreshed_wl1 = await get_watchlist(db_session, wl1.id)
        refreshed_wl2 = await get_watchlist(db_session, wl2.id)
        assert refreshed_wl1 is not None
        assert refreshed_wl2 is not None
        assert refreshed_wl2.is_active is True
        assert refreshed_wl1.is_active is False

    async def test_get_watchlist(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        retrieved = await get_watchlist(db_session, wl.id)
        assert retrieved is not None
        assert retrieved.id == wl.id
        assert retrieved.name == "Test"

    async def test_get_watchlist_not_found(self, db_session: AsyncSession) -> None:
        retrieved = await get_watchlist(db_session, "nonexistent")
        assert retrieved is None

    async def test_list_watchlists(self, db_session: AsyncSession) -> None:
        await create_watchlist(db_session, name="First")
        await create_watchlist(db_session, name="Second")
        wls = await list_watchlists(db_session)
        assert len(wls) == 2
        assert wls[0].name == "First"
        assert wls[1].name == "Second"

    async def test_list_watchlists_empty(self, db_session: AsyncSession) -> None:
        wls = await list_watchlists(db_session)
        assert len(wls) == 0

    async def test_update_watchlist_name(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Old")
        updated = await update_watchlist(db_session, wl.id, name="New")
        assert updated is not None
        assert updated.name == "New"

    async def test_update_watchlist_description(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test", description="Old")
        updated = await update_watchlist(db_session, wl.id, description="New")
        assert updated is not None
        assert updated.description == "New"

    async def test_update_watchlist_not_found(self, db_session: AsyncSession) -> None:
        updated = await update_watchlist(db_session, "nonexistent", name="New")
        assert updated is None

    async def test_activate_watchlist(self, db_session: AsyncSession) -> None:
        wl1 = await create_watchlist(db_session, name="First", is_active=True)
        wl2 = await create_watchlist(db_session, name="Second")
        activated = await activate_watchlist(db_session, wl2.id)
        assert activated is not None
        assert activated.is_active is True
        refreshed_wl1 = await get_watchlist(db_session, wl1.id)
        assert refreshed_wl1 is not None
        assert refreshed_wl1.is_active is False

    async def test_activate_watchlist_not_found(self, db_session: AsyncSession) -> None:
        activated = await activate_watchlist(db_session, "nonexistent")
        assert activated is None

    async def test_delete_watchlist(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="ToDelete")
        deleted = await delete_watchlist(db_session, wl.id)
        assert deleted is True
        retrieved = await get_watchlist(db_session, wl.id)
        assert retrieved is None

    async def test_delete_watchlist_not_found(self, db_session: AsyncSession) -> None:
        deleted = await delete_watchlist(db_session, "nonexistent")
        assert deleted is False


class TestWatchlistItemCRUD:
    async def test_add_item(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", sector="Technology", bias="long")
        assert item is not None
        assert item.symbol == "AAPL"
        assert item.sector == "Technology"
        assert item.bias == "long"

    async def test_add_item_case_insensitive(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="msft", sector="Tech")
        assert item is not None
        assert item.symbol == "MSFT"

    async def test_add_item_invalid_bias_defaults_to_auto(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", bias="invalid")
        assert item is not None
        assert item.bias == "auto"

    async def test_add_item_watchlist_not_found(self, db_session: AsyncSession) -> None:
        item = await add_item(db_session, "nonexistent", symbol="AAPL")
        assert item is None

    async def test_remove_item(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL")
        assert item is not None
        removed = await remove_item(db_session, item.id)
        assert removed is True

    async def test_remove_item_not_found(self, db_session: AsyncSession) -> None:
        removed = await remove_item(db_session, "nonexistent")
        assert removed is False

    async def test_update_item_sector(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", sector="Old")
        updated = await update_item(db_session, item.id, sector="New")
        assert updated is not None
        assert updated.sector == "New"

    async def test_update_item_bias(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", bias="long")
        updated = await update_item(db_session, item.id, bias="short")
        assert updated is not None
        assert updated.bias == "short"

    async def test_update_item_invalid_bias_ignored(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", bias="long")
        updated = await update_item(db_session, item.id, bias="invalid")
        assert updated is not None
        assert updated.bias == "long"

    async def test_update_item_sort_order(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Test")
        item = await add_item(db_session, wl.id, symbol="AAPL", sort_order=0)
        updated = await update_item(db_session, item.id, sort_order=5)
        assert updated is not None
        assert updated.sort_order == 5

    async def test_update_item_not_found(self, db_session: AsyncSession) -> None:
        updated = await update_item(db_session, "nonexistent", sector="New")
        assert updated is None


class TestGetActiveSymbols:
    async def test_get_active_symbols_from_watchlist(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Active", is_active=True)
        await add_item(db_session, wl.id, symbol="AAPL")
        await add_item(db_session, wl.id, symbol="MSFT")
        await db_session.commit()
        symbols = await get_active_symbols(db_session)
        assert symbols == ["AAPL", "MSFT"]

    async def test_get_active_symbols_no_active_watchlist_returns_empty(self, db_session: AsyncSession) -> None:
        symbols = await get_active_symbols(db_session)
        assert isinstance(symbols, list)
        assert len(symbols) == 0

    async def test_get_active_symbols_ordering(self, db_session: AsyncSession) -> None:
        wl = await create_watchlist(db_session, name="Active", is_active=True)
        await add_item(db_session, wl.id, symbol="C", sort_order=2)
        await add_item(db_session, wl.id, symbol="A", sort_order=0)
        await add_item(db_session, wl.id, symbol="B", sort_order=1)
        await db_session.commit()
        symbols = await get_active_symbols(db_session)
        assert symbols == ["A", "B", "C"]


class TestSeedDefaultWatchlist:
    async def test_seed_default_watchlist_creates_watchlist(self, db_session: AsyncSession) -> None:
        wl = await seed_default_watchlist(db_session)
        assert wl is not None
        assert wl.name == "Default"
        assert wl.is_active is True
        refreshed = await get_watchlist(db_session, wl.id)
        assert refreshed is not None
        assert len(refreshed.items) == 26

    async def test_seed_default_watchlist_idempotent(self, db_session: AsyncSession) -> None:
        wl1 = await seed_default_watchlist(db_session)
        wl2 = await seed_default_watchlist(db_session)
        assert wl2 is None
        wls = await list_watchlists(db_session)
        assert len(wls) == 1
        assert wls[0].id == wl1.id
        assert len(wls[0].items) == 26

    async def test_seed_default_watchlist_items_content(self, db_session: AsyncSession) -> None:
        wl = await seed_default_watchlist(db_session)
        assert wl is not None
        refreshed = await get_watchlist(db_session, wl.id)
        assert refreshed is not None
        symbols = {item.symbol for item in refreshed.items}
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "SPY" in symbols
        assert "QQQ" in symbols


class TestAPIEndpoints:
    def _unique_name(self, base: str) -> str:
        import uuid

        return f"{base}_{uuid.uuid4().hex[:8]}"

    def test_get_watchlists(self, client: TestClient) -> None:
        r = client.get("/api/v1/watchlists")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_watchlist(self, client: TestClient) -> None:
        payload = {
            "name": self._unique_name("My_Watchlist"),
            "description": "Test watchlist",
            "is_active": False,
            "items": [
                {"symbol": "AAPL", "sector": "Technology", "bias": "auto", "sort_order": 0},
                {"symbol": "MSFT", "sector": "Technology", "bias": "long", "sort_order": 1},
            ],
        }
        r = client.post("/api/v1/watchlists", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["description"] == "Test watchlist"
        assert len(data["items"]) == 2
        assert data["items"][0]["symbol"] == "AAPL"

    def test_create_watchlist_empty(self, client: TestClient) -> None:
        payload = {"name": self._unique_name("Empty_Watchlist"), "description": "", "is_active": False, "items": []}
        r = client.post("/api/v1/watchlists", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == payload["name"]
        assert len(data["items"]) == 0

    def test_get_watchlist_by_id(self, client: TestClient) -> None:
        payload = {"name": self._unique_name("Test"), "description": "", "is_active": False, "items": []}
        r1 = client.post("/api/v1/watchlists", json=payload)
        wl_id = r1.json()["id"]
        r2 = client.get(f"/api/v1/watchlists/{wl_id}")
        assert r2.status_code == 200
        data = r2.json()
        assert data["id"] == wl_id
        assert data["name"] == payload["name"]

    def test_get_watchlist_not_found(self, client: TestClient) -> None:
        r = client.get("/api/v1/watchlists/nonexistent123")
        assert r.status_code == 404

    def test_update_watchlist(self, client: TestClient) -> None:
        payload = {"name": self._unique_name("Old"), "description": "Old desc", "is_active": False, "items": []}
        r1 = client.post("/api/v1/watchlists", json=payload)
        wl_id = r1.json()["id"]
        update_payload = {"name": self._unique_name("New"), "description": "New desc"}
        r2 = client.put(f"/api/v1/watchlists/{wl_id}", json=update_payload)
        assert r2.status_code == 200
        data = r2.json()
        assert data["name"] == update_payload["name"]
        assert data["description"] == "New desc"

    def test_activate_watchlist(self, client: TestClient) -> None:
        payload1 = {"name": self._unique_name("First"), "description": "", "is_active": True, "items": []}
        payload2 = {"name": self._unique_name("Second"), "description": "", "is_active": False, "items": []}
        r1 = client.post("/api/v1/watchlists", json=payload1)
        wl1_id = r1.json()["id"]
        r2 = client.post("/api/v1/watchlists", json=payload2)
        wl2_id = r2.json()["id"]
        r3 = client.post(f"/api/v1/watchlists/{wl2_id}/activate")
        assert r3.status_code == 200
        assert r3.json()["is_active"] is True
        r4 = client.get(f"/api/v1/watchlists/{wl1_id}")
        assert r4.json()["is_active"] is False

    def test_delete_watchlist(self, client: TestClient) -> None:
        payload = {"name": self._unique_name("ToDelete"), "description": "", "is_active": False, "items": []}
        r1 = client.post("/api/v1/watchlists", json=payload)
        wl_id = r1.json()["id"]
        r2 = client.delete(f"/api/v1/watchlists/{wl_id}")
        assert r2.status_code == 204
        r3 = client.get(f"/api/v1/watchlists/{wl_id}")
        assert r3.status_code == 404

    def test_get_active_symbols(self, client: TestClient) -> None:
        r = client.get("/api/v1/watchlists/active/symbols")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_add_watchlist_item(self, client: TestClient) -> None:
        payload = {"name": self._unique_name("Test"), "description": "", "is_active": False, "items": []}
        r1 = client.post("/api/v1/watchlists", json=payload)
        wl_id = r1.json()["id"]
        item_payload = {"symbol": "AAPL", "sector": "Technology", "bias": "auto", "sort_order": 0}
        r2 = client.post(f"/api/v1/watchlists/{wl_id}/items", json=item_payload)
        assert r2.status_code == 201
        data = r2.json()
        assert data["symbol"] == "AAPL"
        assert data["sector"] == "Technology"

    def test_add_watchlist_item_not_found(self, client: TestClient) -> None:
        item_payload = {"symbol": "AAPL", "sector": "Technology", "bias": "auto", "sort_order": 0}
        r = client.post("/api/v1/watchlists/nonexistent123/items", json=item_payload)
        assert r.status_code == 404

    def test_update_watchlist_item(self, client: TestClient) -> None:
        payload = {
            "name": self._unique_name("Test"),
            "description": "",
            "is_active": False,
            "items": [{"symbol": "AAPL", "sector": "Tech", "bias": "long", "sort_order": 0}],
        }
        r1 = client.post("/api/v1/watchlists", json=payload)
        item_id = r1.json()["items"][0]["id"]
        update_payload = {"sector": "Healthcare", "bias": "short", "sort_order": 5}
        r2 = client.put(f"/api/v1/watchlists/items/{item_id}", json=update_payload)
        assert r2.status_code == 200
        data = r2.json()
        assert data["sector"] == "Healthcare"
        assert data["bias"] == "short"
        assert data["sort_order"] == 5

    def test_delete_watchlist_item(self, client: TestClient) -> None:
        payload = {
            "name": self._unique_name("Test"),
            "description": "",
            "is_active": False,
            "items": [{"symbol": "AAPL", "sector": "Tech", "bias": "auto", "sort_order": 0}],
        }
        r1 = client.post("/api/v1/watchlists", json=payload)
        item_id = r1.json()["items"][0]["id"]
        r2 = client.delete(f"/api/v1/watchlists/items/{item_id}")
        assert r2.status_code == 204
