"""老師端：建立活動、開始與結束、重新產生代碼、判定無效、檢視（contracts/http-api.md）。"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from guided_buzz.api.deps import require_teacher

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/activities")


class CreateActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worksheet_id: str = Field(min_length=1, max_length=64)
    teams: list[str] = Field(min_length=1, max_length=1000)
    fairness_enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=1, le=600)  # data-model.md Activity.cooldown_seconds
    cooldown_lead: int | None = Field(default=None, ge=1, le=100)  # data-model.md Activity.cooldown_lead


@router.post("", status_code=201)
async def create_activity(body: CreateActivityRequest, request: Request, owner: str = Depends(require_teacher)) -> dict:
    state = request.app.state
    engine = state.registry.create(owner, body.worksheet_id, body.teams, body.fairness_enabled, body.cooldown_seconds, body.cooldown_lead)
    await state.hub.broadcast_teacher_snapshot()
    return engine.view_for_teacher()


@router.get("")
async def list_activities(request: Request, owner: str = Depends(require_teacher)) -> list[dict]:
    return [
        {
            "id": str(i.id),
            "worksheet_id": str(i.worksheet_id),
            "phase": request.app.state.registry.phase_of(i.id).value,
            "created_at": i.created_at.isoformat(),
            "ended_at": i.ended_at.isoformat() if i.ended_at else None,
        }
        for i in request.app.state.registry.repo.list_by_owner(owner)
    ]


@router.get("/{activity_id}")
async def get_activity(activity_id: str, request: Request, owner: str = Depends(require_teacher)) -> dict:
    return request.app.state.registry.get(activity_id, owner).view_for_teacher()


@router.post("/{activity_id}/start")
async def start(activity_id: str, request: Request, owner: str = Depends(require_teacher)) -> dict:
    state = request.app.state
    engine = state.registry.get(activity_id, owner)
    events = await engine.start()
    await state.hub.dispatch(engine, events)
    return {"phase": engine.phase.value}


@router.post("/{activity_id}/end")
async def end(activity_id: str, request: Request, owner: str = Depends(require_teacher)) -> dict:
    state = request.app.state
    engine = state.registry.get(activity_id, owner)
    events = await engine.end()
    await state.hub.dispatch(engine, events)
    return {"phase": engine.phase.value}


@router.post("/{activity_id}/teams/{team_id}/regenerate-code")
async def regenerate_code(activity_id: str, team_id: int, request: Request, owner: str = Depends(require_teacher)) -> dict:
    state = request.app.state
    engine = state.registry.get(activity_id, owner)
    code, events = await engine.regenerate_code(team_id)
    state.sessions.revoke_team(engine.id, team_id)
    await state.hub.dispatch(engine, events)
    return {"team_id": team_id, "code": code}


@router.post("/{activity_id}/units/{unit_key}/invalidate")
async def invalidate(activity_id: str, unit_key: str, request: Request, owner: str = Depends(require_teacher)) -> dict:
    state = request.app.state
    engine = state.registry.get(activity_id, owner)
    result, events = await engine.invalidate(unit_key)
    await state.hub.dispatch(engine, events)
    return result
