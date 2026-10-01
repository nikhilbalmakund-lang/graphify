"""WebSocket endpoint for live updates (quotes, signals, notifications, paper, system)."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    container = ws.app.state.container
    origin = ws.headers.get("origin")
    if origin and origin not in container.env.cors_origins:
        await ws.close(code=1008)
        return
    manager = container.ws
    await manager.connect(ws)
    await ws.send_text(
        json.dumps({"topic": "system", "data": {"event": "HELLO", "mode": container.market.mode}})
    )
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 4096:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if (
                isinstance(msg, dict)
                and msg.get("action") == "subscribe"
                and isinstance(msg.get("topics"), list)
            ):
                await manager.subscribe(ws, [str(t) for t in msg["topics"]][:10])
            elif isinstance(msg, dict) and msg.get("action") == "ping":
                await ws.send_text(json.dumps({"topic": "system", "data": {"event": "PONG"}}))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
