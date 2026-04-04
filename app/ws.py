"""WebSocket hub — real-time push for signals, regime, broker & health.

Channels
--------
- ``signals``        Latest scan results (signal list)
- ``regime``         Market regime state
- ``broker``         Account / positions / orders  (requires broker config)
- ``health``         Periodic heartbeat with API health status

Clients connect to ``/ws``, then send JSON subscribe/unsubscribe messages:

    {"type": "subscribe", "channel": "signals"}
    {"type": "unsubscribe", "channel": "regime"}
    {"type": "ping"}

The server broadcasts to each channel at a configurable interval.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

CHANNELS: set[str] = {"signals", "regime", "broker", "health"}

DEFAULT_INTERVALS: dict[str, float] = {
    "signals": 15.0,
    "regime": 15.0,
    "broker": 10.0,
    "health": 30.0,
}


# ── Helpers ──────────────────────────────────────────────────────────


def _make_msg(msg_type: str, *, channel: str | None = None, data: Any = None, error: str | None = None) -> str:
    """Build a JSON envelope string."""
    payload: dict[str, Any] = {"type": msg_type, "ts": time.time()}
    if channel is not None:
        payload["channel"] = channel
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error
    return json.dumps(payload, default=str)


# ── Connection Manager ───────────────────────────────────────────────


@dataclass(slots=True)
class _Client:
    ws: WebSocket
    client_id: str
    channels: set[str] = field(default_factory=set)


class ConnectionManager:
    """Track connected clients and their channel subscriptions."""

    def __init__(self) -> None:
        self._clients: dict[str, _Client] = {}

    # -- lifecycle -------------------------------------------------

    async def connect(self, ws: WebSocket, client_id: str) -> None:
        await ws.accept()
        self._clients[client_id] = _Client(ws=ws, client_id=client_id)
        logger.info("ws connect  id=%s  total=%d", client_id, len(self._clients))

    def disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        logger.info("ws disconnect  id=%s  total=%d", client_id, len(self._clients))

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # -- subscriptions ---------------------------------------------

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Return True if actually subscribed (channel valid + client exists)."""
        if channel not in CHANNELS:
            return False
        client = self._clients.get(client_id)
        if client is None:
            return False
        client.channels.add(channel)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        client = self._clients.get(client_id)
        if client is None:
            return False
        client.channels.discard(channel)
        return True

    def subscriptions(self, client_id: str) -> set[str]:
        client = self._clients.get(client_id)
        return set(client.channels) if client else set()

    def channel_subscribers(self, channel: str) -> list[str]:
        """Return client_ids subscribed to *channel*."""
        return [c.client_id for c in self._clients.values() if channel in c.channels]

    # -- send / broadcast ------------------------------------------

    async def send(self, client_id: str, message: str) -> None:
        client = self._clients.get(client_id)
        if client is None:
            return
        try:
            if client.ws.client_state == WebSocketState.CONNECTED:
                await client.ws.send_text(message)
        except Exception:
            self.disconnect(client_id)

    async def broadcast(self, channel: str, message: str) -> None:
        """Send *message* to every client subscribed to *channel*."""
        dead: list[str] = []
        for cid, client in self._clients.items():
            if channel not in client.channels:
                continue
            try:
                if client.ws.client_state == WebSocketState.CONNECTED:
                    await client.ws.send_text(message)
                else:
                    dead.append(cid)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def broadcast_all(self, message: str) -> None:
        """Send *message* to every connected client regardless of channels."""
        dead: list[str] = []
        for cid, client in self._clients.items():
            try:
                if client.ws.client_state == WebSocketState.CONNECTED:
                    await client.ws.send_text(message)
                else:
                    dead.append(cid)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)


manager = ConnectionManager()


# ── Message handler ──────────────────────────────────────────────────


async def handle_client_message(client_id: str, raw: str) -> None:
    """Process one inbound JSON message from a client."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await manager.send(client_id, _make_msg("error", error="invalid JSON"))
        return

    msg_type: str = msg.get("type", "")

    if msg_type == "subscribe":
        channel = msg.get("channel", "")
        ok = manager.subscribe(client_id, channel)
        if ok:
            await manager.send(client_id, _make_msg("subscribed", channel=channel))
        else:
            await manager.send(client_id, _make_msg("error", error=f"unknown channel: {channel}"))

    elif msg_type == "unsubscribe":
        channel = msg.get("channel", "")
        manager.unsubscribe(client_id, channel)
        await manager.send(client_id, _make_msg("unsubscribed", channel=channel))

    elif msg_type == "ping":
        await manager.send(client_id, _make_msg("pong"))

    else:
        await manager.send(client_id, _make_msg("error", error=f"unknown type: {msg_type}"))


# ── Background broadcaster ──────────────────────────────────────────


class Broadcaster:
    """Periodically fetch data and push to channel subscribers.

    Register *data providers* — async callables that return JSON-serialisable
    dicts — one per channel.  ``start()`` kicks off an ``asyncio.Task`` per
    channel that loops on the configured interval.
    """

    def __init__(self, mgr: ConnectionManager) -> None:
        self._mgr = mgr
        self._providers: dict[str, Any] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    def register(self, channel: str, provider: Any, interval: float | None = None) -> None:
        """Register an async callable ``provider`` for *channel*.

        *provider* signature: ``async () -> dict | list | None``.
        Return ``None`` to skip broadcasting for that tick.
        """
        self._providers[channel] = (provider, interval or DEFAULT_INTERVALS.get(channel, 15.0))

    async def start(self) -> None:
        self._running = True
        for channel, (provider, interval) in self._providers.items():
            task = asyncio.create_task(self._loop(channel, provider, interval), name=f"ws-broadcast-{channel}")
            self._tasks.append(task)
        logger.info("ws broadcaster started  channels=%s", list(self._providers.keys()))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("ws broadcaster stopped")

    async def _loop(self, channel: str, provider: Any, interval: float) -> None:
        while self._running:
            try:
                # Only fetch if someone is listening.
                if self._mgr.channel_subscribers(channel):
                    data = await provider()
                    if data is not None:
                        msg = _make_msg("push", channel=channel, data=data)
                        await self._mgr.broadcast(channel, msg)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("ws broadcast error  channel=%s", channel)
            await asyncio.sleep(interval)


broadcaster = Broadcaster(manager)
