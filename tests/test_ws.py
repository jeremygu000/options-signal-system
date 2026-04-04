from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ws import (
    CHANNELS,
    DEFAULT_INTERVALS,
    Broadcaster,
    ConnectionManager,
    _make_msg,
    handle_client_message,
)
from starlette.websockets import WebSocketState


class _FakeWS:
    def __init__(self, *, state: WebSocketState = WebSocketState.CONNECTED) -> None:
        self.client_state = state
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


class TestMakeMsg:
    def test_basic_msg(self) -> None:
        raw = _make_msg("pong")
        msg = json.loads(raw)
        assert msg["type"] == "pong"
        assert "ts" in msg
        assert "channel" not in msg
        assert "data" not in msg

    def test_with_channel_and_data(self) -> None:
        raw = _make_msg("push", channel="signals", data={"foo": 1})
        msg = json.loads(raw)
        assert msg["type"] == "push"
        assert msg["channel"] == "signals"
        assert msg["data"] == {"foo": 1}

    def test_with_error(self) -> None:
        raw = _make_msg("error", error="bad request")
        msg = json.loads(raw)
        assert msg["error"] == "bad request"

    def test_serializes_non_json_types(self) -> None:
        from datetime import datetime

        raw = _make_msg("push", data={"dt": datetime(2025, 1, 1)})
        msg = json.loads(raw)
        assert "2025" in msg["data"]["dt"]


class TestConstants:
    def test_channels_has_expected_values(self) -> None:
        assert CHANNELS == {"signals", "regime", "broker", "health"}

    def test_default_intervals_keys_match_channels(self) -> None:
        assert set(DEFAULT_INTERVALS.keys()) == CHANNELS


class TestConnectionManager:
    @pytest.fixture()
    def mgr(self) -> ConnectionManager:
        return ConnectionManager()

    @pytest.mark.asyncio()
    async def test_connect_disconnect(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        assert mgr.client_count == 1
        mgr.disconnect("c1")
        assert mgr.client_count == 0

    @pytest.mark.asyncio()
    async def test_disconnect_nonexistent(self, mgr: ConnectionManager) -> None:
        mgr.disconnect("ghost")
        assert mgr.client_count == 0

    @pytest.mark.asyncio()
    async def test_subscribe_valid_channel(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        assert mgr.subscribe("c1", "signals") is True
        assert mgr.subscriptions("c1") == {"signals"}

    @pytest.mark.asyncio()
    async def test_subscribe_invalid_channel(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        assert mgr.subscribe("c1", "invalid_channel") is False

    @pytest.mark.asyncio()
    async def test_subscribe_nonexistent_client(self, mgr: ConnectionManager) -> None:
        assert mgr.subscribe("ghost", "signals") is False

    @pytest.mark.asyncio()
    async def test_unsubscribe(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        assert mgr.unsubscribe("c1", "signals") is True
        assert mgr.subscriptions("c1") == set()

    @pytest.mark.asyncio()
    async def test_unsubscribe_nonexistent_client(self, mgr: ConnectionManager) -> None:
        assert mgr.unsubscribe("ghost", "signals") is False

    @pytest.mark.asyncio()
    async def test_subscriptions_nonexistent_client(self, mgr: ConnectionManager) -> None:
        assert mgr.subscriptions("ghost") == set()

    @pytest.mark.asyncio()
    async def test_channel_subscribers(self, mgr: ConnectionManager) -> None:
        ws1 = _FakeWS()
        ws2 = _FakeWS()
        await mgr.connect(ws1, "c1")  # type: ignore[arg-type]
        await mgr.connect(ws2, "c2")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        mgr.subscribe("c2", "signals")
        mgr.subscribe("c2", "regime")
        subs = mgr.channel_subscribers("signals")
        assert sorted(subs) == ["c1", "c2"]
        assert mgr.channel_subscribers("regime") == ["c2"]

    @pytest.mark.asyncio()
    async def test_send(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        await mgr.send("c1", '{"type":"test"}')
        assert len(ws.sent) == 1
        assert json.loads(ws.sent[0])["type"] == "test"

    @pytest.mark.asyncio()
    async def test_send_nonexistent_client(self, mgr: ConnectionManager) -> None:
        await mgr.send("ghost", '{"type":"test"}')

    @pytest.mark.asyncio()
    async def test_send_disconnected_ws(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS(state=WebSocketState.DISCONNECTED)
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        await mgr.send("c1", '{"type":"test"}')
        assert len(ws.sent) == 0

    @pytest.mark.asyncio()
    async def test_broadcast_to_channel(self, mgr: ConnectionManager) -> None:
        ws1 = _FakeWS()
        ws2 = _FakeWS()
        ws3 = _FakeWS()
        await mgr.connect(ws1, "c1")  # type: ignore[arg-type]
        await mgr.connect(ws2, "c2")  # type: ignore[arg-type]
        await mgr.connect(ws3, "c3")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        mgr.subscribe("c2", "signals")
        await mgr.broadcast("signals", '{"type":"push"}')
        assert len(ws1.sent) == 1
        assert len(ws2.sent) == 1
        assert len(ws3.sent) == 0

    @pytest.mark.asyncio()
    async def test_broadcast_removes_dead_clients(self, mgr: ConnectionManager) -> None:
        ws = _FakeWS(state=WebSocketState.DISCONNECTED)
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        await mgr.broadcast("signals", '{"type":"push"}')
        assert mgr.client_count == 0

    @pytest.mark.asyncio()
    async def test_broadcast_all(self, mgr: ConnectionManager) -> None:
        ws1 = _FakeWS()
        ws2 = _FakeWS()
        await mgr.connect(ws1, "c1")  # type: ignore[arg-type]
        await mgr.connect(ws2, "c2")  # type: ignore[arg-type]
        await mgr.broadcast_all('{"type":"hello"}')
        assert len(ws1.sent) == 1
        assert len(ws2.sent) == 1


class TestHandleClientMessage:
    @pytest.fixture(autouse=True)
    def _setup_manager(self) -> None:
        self.mgr = ConnectionManager()

    @pytest.mark.asyncio()
    async def test_subscribe(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", '{"type":"subscribe","channel":"signals"}')
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "subscribed"
        assert last_msg["channel"] == "signals"

    @pytest.mark.asyncio()
    async def test_subscribe_invalid_channel(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", '{"type":"subscribe","channel":"nope"}')
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "error"

    @pytest.mark.asyncio()
    async def test_unsubscribe(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        self.mgr.subscribe("c1", "signals")
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", '{"type":"unsubscribe","channel":"signals"}')
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "unsubscribed"

    @pytest.mark.asyncio()
    async def test_ping(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", '{"type":"ping"}')
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "pong"

    @pytest.mark.asyncio()
    async def test_invalid_json(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", "not json")
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "error"
        assert "invalid JSON" in last_msg["error"]

    @pytest.mark.asyncio()
    async def test_unknown_type(self) -> None:
        ws = _FakeWS()
        await self.mgr.connect(ws, "c1")  # type: ignore[arg-type]
        with patch("app.ws.manager", self.mgr):
            await handle_client_message("c1", '{"type":"bogus"}')
        last_msg = json.loads(ws.sent[-1])
        assert last_msg["type"] == "error"
        assert "unknown type" in last_msg["error"]


class TestBroadcaster:
    @pytest.mark.asyncio()
    async def test_register_and_start_stop(self) -> None:
        mgr = ConnectionManager()
        bc = Broadcaster(mgr)
        call_count = 0

        async def provider() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"n": call_count}

        bc.register("signals", provider, interval=0.05)
        await bc.start()
        await asyncio.sleep(0.02)
        await bc.stop()
        assert bc._running is False
        assert len(bc._tasks) == 0

    @pytest.mark.asyncio()
    async def test_broadcasts_only_when_subscribers_exist(self) -> None:
        mgr = ConnectionManager()
        bc = Broadcaster(mgr)
        call_count = 0

        async def provider() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"n": call_count}

        bc.register("signals", provider, interval=0.05)
        await bc.start()
        await asyncio.sleep(0.12)
        await bc.stop()
        assert call_count == 0

    @pytest.mark.asyncio()
    async def test_broadcasts_when_subscriber_exists(self) -> None:
        mgr = ConnectionManager()
        bc = Broadcaster(mgr)

        async def provider() -> dict[str, str]:
            return {"status": "ok"}

        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        bc.register("signals", provider, interval=0.05)
        await bc.start()
        await asyncio.sleep(0.12)
        await bc.stop()
        assert len(ws.sent) > 0
        msg = json.loads(ws.sent[0])
        assert msg["type"] == "push"
        assert msg["channel"] == "signals"

    @pytest.mark.asyncio()
    async def test_provider_returning_none_skips_broadcast(self) -> None:
        mgr = ConnectionManager()
        bc = Broadcaster(mgr)

        async def provider() -> None:
            return None

        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        bc.register("signals", provider, interval=0.05)
        await bc.start()
        await asyncio.sleep(0.12)
        await bc.stop()
        assert len(ws.sent) == 0

    @pytest.mark.asyncio()
    async def test_provider_exception_does_not_crash(self) -> None:
        mgr = ConnectionManager()
        bc = Broadcaster(mgr)

        async def bad_provider() -> dict[str, str]:
            raise RuntimeError("boom")

        ws = _FakeWS()
        await mgr.connect(ws, "c1")  # type: ignore[arg-type]
        mgr.subscribe("c1", "signals")
        bc.register("signals", bad_provider, interval=0.05)
        await bc.start()
        await asyncio.sleep(0.12)
        await bc.stop()
        assert len(ws.sent) == 0
