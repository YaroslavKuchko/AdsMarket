from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import DefaultDict, Set

from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self._connections: DefaultDict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, telegram_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[telegram_id].add(ws)

    async def disconnect(self, telegram_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(telegram_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                self._connections.pop(telegram_id, None)

    async def send(self, telegram_id: int, payload: dict) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            conns = list(self._connections.get(telegram_id, set()))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.get(telegram_id, set()).discard(ws)


hub = RealtimeHub()


