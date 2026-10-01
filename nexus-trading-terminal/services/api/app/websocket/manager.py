"""WebSocket connection manager with topic subscriptions.

Topics: quotes, signals, notifications, paper, system, backtests.
Clients receive every topic unless they send {"action": "subscribe", "topics": [...]}.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("nexus.ws")
TOPICS = {"quotes", "signals", "notifications", "paper", "system", "backtests"}


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()
        self.sent = 0

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[ws] = set(TOPICS)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(ws, None)

    async def subscribe(self, ws: WebSocket, topics: list[str]) -> None:
        async with self._lock:
            if ws in self._clients:
                self._clients[ws] = {t for t in topics if t in TOPICS}

    async def broadcast(self, topic: str, payload: Any) -> None:
        if not self._clients:
            return
        message = json.dumps(
            {"topic": topic, "ts": datetime.now(UTC).isoformat(), "data": payload}, default=str
        )
        dead = []
        for ws, topics in list(self._clients.items()):
            if topic not in topics:
                continue
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=2.0)
                self.sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)
