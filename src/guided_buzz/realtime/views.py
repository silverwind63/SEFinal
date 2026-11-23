"""依連線身分產生推播內容（contracts/websocket.md）。學生在結束前只會拿到本組資料（FR-014）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import WebSocket


@dataclass(eq=False)
class Connection:
    ws: WebSocket
    role: str  # teacher | team
    activity_id: UUID | None = None
    team_id: int | None = None


def snapshot_for(conn: Connection, registry) -> dict:
    if conn.role == "teacher":
        engine = registry.latest
        return {"type": "snapshot", "activity": engine.view_for_teacher() if engine else None}
    engine = registry.get(conn.activity_id)
    return {"type": "snapshot", **engine.view_for_team(conn.team_id)}


def targets(event, engine, connections: list[Connection]) -> list[Connection]:
    """事件的接收者：teacher → 所有老師連線；team → 該活動該組；all → 老師與該活動所有學生。"""
    students = [c for c in connections if c.role == "team" and c.activity_id == engine.id]
    teachers = [c for c in connections if c.role == "teacher"]
    if event.audience == "teacher":
        return teachers
    if event.audience in ("team", "revoke"):
        return [c for c in students if c.team_id == event.team_id]
    return teachers + students
