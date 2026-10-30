"""Twitch PubSub listener for realtime drop progress, claim and stream state events.

PubSub only speeds things up. The miner never depends on it: progress is also polled via
GQL and finished drops are found by the periodic inventory sweep, so a dead socket can not
cause missed claims.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from typing import Any, Awaitable, Callable

import aiohttp

from .constants import PUBSUB_URL

logger = logging.getLogger("dropper.pubsub")

Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


class PubSub:
    PING_INTERVAL = 180
    PONG_TIMEOUT = 10

    def __init__(self, client, handler: Handler):
        self.client = client
        self.handler = handler
        self.topics: set[str] = set()
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._pong = asyncio.Event()
        self.connected = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="pubsub")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()

    async def set_topics(self, topics: set[str]) -> None:
        added, removed = topics - self.topics, self.topics - topics
        self.topics = set(topics)
        if self._ws is not None and not self._ws.closed:
            if removed:
                await self._send("UNLISTEN", removed)
            if added:
                await self._send("LISTEN", added)

    async def _send(self, kind: str, topics: set[str]) -> None:
        assert self._ws is not None
        await self._ws.send_json({
            "type": kind,
            "nonce": secrets.token_hex(15),
            "data": {"topics": sorted(topics), "auth_token": self.client.access_token},
        })

    async def _run(self) -> None:
        delay = 1
        while True:
            try:
                session = await self.client.session()
                proxy = self.client._get_settings().proxy or None
                async with session.ws_connect(PUBSUB_URL, proxy=proxy, heartbeat=None) as ws:
                    self._ws = ws
                    self.connected = True
                    delay = 1
                    logger.info("PubSub connected")
                    if self.topics:
                        await self._send("LISTEN", self.topics)
                    pinger = asyncio.create_task(self._pinger(ws))
                    try:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                if await self._on_message(json.loads(msg.data)):
                                    break
                            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                                break
                    finally:
                        pinger.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("PubSub error: %s", exc)
            self.connected = False
            self._ws = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)

    async def _pinger(self, ws) -> None:
        while not ws.closed:
            await asyncio.sleep(self.PING_INTERVAL)
            self._pong.clear()
            await ws.send_json({"type": "PING"})
            try:
                await asyncio.wait_for(self._pong.wait(), self.PONG_TIMEOUT)
            except asyncio.TimeoutError:
                logger.info("PubSub PONG missing, reconnecting")
                await ws.close()
                return

    async def _on_message(self, message: dict[str, Any]) -> bool:
        """Returns True when the connection should be re-established."""
        kind = message.get("type")
        if kind == "PONG":
            self._pong.set()
        elif kind == "RECONNECT":
            return True
        elif kind == "RESPONSE" and message.get("error"):
            logger.warning("PubSub LISTEN error: %s", message["error"])
        elif kind == "MESSAGE":
            data = message.get("data", {})
            try:
                payload = json.loads(data.get("message", "{}"))
                await self.handler(data.get("topic", ""), payload)
            except Exception:
                logger.exception("PubSub handler failed")
        return False
