from fastapi import APIRouter, Depends, Request

from guided_buzz.api.deps import require_teacher
from guided_buzz.api.schemas import LoginRequest, SessionOut, TokenOut

router = APIRouter(prefix="/api/auth")


@router.post("/teacher-login", response_model=TokenOut)
def teacher_login(body: LoginRequest, request: Request) -> TokenOut:
    token = request.app.state.auth.login(body.password)
    return TokenOut(token=token, expires_in=request.app.state.settings.token_ttl_seconds)


@router.get("/session", response_model=SessionOut)
def session(owner: str = Depends(require_teacher)) -> SessionOut:
    return SessionOut(owner=owner)
