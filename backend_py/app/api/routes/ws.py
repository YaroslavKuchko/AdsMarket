from __future__ import annotations

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.realtime.hub import hub

router = APIRouter(tags=["ws"])


def _decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        telegram_id = payload.get("telegram_id")
        if telegram_id is None:
            return None
        return int(telegram_id)
    except Exception:
        return None


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = ws.query_params.get("token") or ""
    telegram_id = _decode_token(token)
    if not telegram_id:
        await ws.close(code=4401)
        return

    await ws.accept()
    await hub.connect(telegram_id, ws)

    try:
        # keep connection open; we don't require client messages for now
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(telegram_id, ws)
    except Exception:
        await hub.disconnect(telegram_id, ws)
        try:
            await ws.close()
        except Exception:
            pass


