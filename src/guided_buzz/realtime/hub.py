"""WebSocket 連線管理與推播（contracts/websocket.md、research R2）。

- Token 由連線後的第一則訊息送出，不放在網址上，避免出現在存取紀錄。
- 推播在引擎的鎖釋放後才進行；送出失敗的連線自動移除。
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from guided_buzz.realtime.views import Connection, snapshot_for, targets

log = logging.getLogger(__name__)
router = APIRouter()

CLOSE_UNAUTHORIZED = 4401
CLOSE_REVOKED = 4403


class Hub:
    def __init__(self, registry):
        self.registry = registry
        self.connections: list[Connection] = []

    async def send(self, conn: Connection, message: dict) -> None:
        try:
            await conn.ws.send_json(message)
        except Exception:
            self.remove(conn)

    def remove(self, conn: Connection) -> None:
        if conn in self.connections:
            self.connections.remove(conn)

    async def dispatch(self, engine, events) -> None:
        for event in events:
            for conn in targets(event, engine, list(self.connections)):
                if event.payload.get("type") == "snapshot":
                    await self.send(conn, snapshot_for(conn, self.registry))
                else:
                    await self.send(conn, event.payload)
                if event.audience == "revoke":
                    self.remove(conn)
                    try:
                        await conn.ws.close(code=CLOSE_REVOKED)
                    except Exception:
                        pass

    async def broadcast_teacher_snapshot(self) -> None:
        for conn in [c for c in self.connections if c.role == "teacher"]:
            await self.send(conn, snapshot_for(conn, self.registry))


def identify(app_state, token: str) -> Connection | None:
    """回傳尚未綁定 WebSocket 的身分；Token 無效或已失效時回傳 None。"""
    if not isinstance(token, str) or not token:
        return None
    if app_state.auth.verify(token):
        return Connection(ws=None, role="teacher")
    session = app_state.sessions.get(token)
    if session is None:
        return None
    try:
        engine = app_state.registry.get(session.activity_id)
    except Exception:
        return None
    team = engine.teams.get(session.team_id)
    if team is None or team.code_version != session.code_version:
        return None
    return Connection(ws=None, role="team", activity_id=session.activity_id, team_id=session.team_id)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    state = ws.app.state
    await ws.accept()
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout=state.settings.ws_auth_timeout_seconds)
        conn = identify(state, message.get("token")) if isinstance(message, dict) and message.get("type") == "auth" else None
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, KeyError):
        conn = None
    if conn is None:
        try:
            await ws.close(code=CLOSE_UNAUTHORIZED)
        except Exception:
            pass
        return
    conn.ws = ws
    hub: Hub = state.hub
    hub.connections.append(conn)
    await hub.send(conn, snapshot_for(conn, state.registry))
    try:
        while True:
            await ws.receive_text()  # 客戶端不需要送任何指令；保持連線直到斷線
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.remove(conn)
