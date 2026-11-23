"""學生端：加入、送出、本組檢視、結果，以及公開的階段查詢（contracts/http-api.md）。"""

import logging

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from guided_buzz.activity import codes
from guided_buzz.auth.sessions import StudentSession
from guided_buzz.domain.errors import InvalidCode, InvalidInput, SubmissionRejectCode, SubmissionRejected, Unauthorized

log = logging.getLogger(__name__)
router = APIRouter()


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme == "Bearer" else ""


def require_student(request: Request) -> StudentSession:
    state = request.app.state
    session = state.sessions.get(_bearer(request))
    if session is None:
        raise Unauthorized("組別身分無效或已失效，請重新輸入組別代碼。")
    return session


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=32)


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 客戶端的時間或結果欄位一律拒絕
    unit_key: str = Field(min_length=1, max_length=16)
    answers: dict[str, str] = Field(min_length=1, max_length=500)


@router.post("/api/join")
async def join(body: JoinRequest, request: Request, x_window_id: str = Header(default="", max_length=128)) -> dict:
    state = request.app.state
    window = x_window_id or "unknown-window"
    state.sessions.check_allowed(window)
    code = codes.normalize(body.code)
    if not codes.is_well_formed(code):
        raise InvalidInput("組別代碼格式不正確（6 碼英數字）。")
    found = state.registry.find_team_by_code(code)
    if found is None:
        state.sessions.record_failure(window)
        raise InvalidCode()
    engine, team = found
    state.sessions.record_success(window)
    session = state.sessions.issue(engine.id, team.id, team.code_version)
    log.info("活動 %s：組別 %d 有視窗加入", engine.id, team.id)
    return {"token": session.token, "activity_id": str(engine.id), "team": {"id": team.id, "name": team.name}, "phase": engine.phase.value}


def _engine_for(request: Request, session: StudentSession):
    engine = request.app.state.registry.get(session.activity_id)
    team = engine.teams.get(session.team_id)
    if team is None or team.code_version != session.code_version:
        raise SubmissionRejected(SubmissionRejectCode.UNAUTHORIZED)
    return engine


@router.post("/api/submissions")
async def submit(body: SubmitRequest, request: Request, session: StudentSession = Depends(require_student)) -> dict:
    state = request.app.state
    engine = _engine_for(request, session)
    try:
        answers = {int(k): v for k, v in body.answers.items()}
    except ValueError:
        raise InvalidInput("答案的題號必須是數字。") from None
    result, events = await engine.submit(session.team_id, session.code_version, body.unit_key, answers)
    await state.hub.dispatch(engine, events)
    return result


@router.get("/api/me")
async def me(request: Request, session: StudentSession = Depends(require_student)) -> dict:
    return _engine_for(request, session).view_for_team(session.team_id)


@router.get("/api/activities/{activity_id}/results")
async def results(activity_id: str, request: Request) -> dict:
    """老師或屬於這場活動的學生可以讀取；活動未結束時回 409 NOT_ENDED。"""
    state = request.app.state
    token = _bearer(request)
    owner = state.auth.verify(token) if token else None
    if owner:
        return state.registry.get(activity_id, owner).results_view(include_all=True)
    session = state.sessions.get(token) if token else None
    if session is None or str(session.activity_id) != activity_id:
        raise Unauthorized()
    return state.registry.get(activity_id).results_view(include_all=False)


@router.get("/api/activities/{activity_id}/phase")
async def phase(activity_id: str, request: Request) -> dict:
    """公開端點，只回傳階段；重啟後前端以此判斷活動是否已中斷（research R7）。"""
    return {"phase": request.app.state.registry.phase_of(activity_id).value}
