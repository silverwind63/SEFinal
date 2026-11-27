"""建立 FastAPI app：路由、統一錯誤格式、靜態檔（contracts/http-api.md）。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from guided_buzz.activity.registry import ActivityRegistry
from guided_buzz.api import activity_routes, auth_routes, page_routes, result_routes, student_routes, worksheet_routes
from guided_buzz.api.page_routes import STATIC_DIR
from guided_buzz.auth.sessions import StudentSessions
from guided_buzz.auth.teacher import TeacherAuth
from guided_buzz.config import Settings
from guided_buzz.domain.errors import DomainError, DomainErrorWithExtra, ImportFailed
from guided_buzz.domain.ports import ActivityResultsProvider, SheetsGateway
from guided_buzz.realtime import hub as realtime
from guided_buzz.results.json_provider import JsonFileResultsProvider
from guided_buzz.results.sqlite_provider import SqliteActivityResultsProvider
from guided_buzz.storage.db import Database

log = logging.getLogger(__name__)

STATUS = {
    "NOT_FOUND": 404,
    "SHEET_NOT_FOUND": 404,
    "INVALID_STATE": 409,
    "STRUCTURE_CHANGED": 409,
    "UNAUTHORIZED": 401,
    "INVALID_CREDENTIALS": 401,
    "SHEET_FORBIDDEN": 403,
    "LOGIN_LOCKED": 429,
    "SHEETS_UNAVAILABLE": 503,
    "GOOGLE_AUTH_EXPIRED": 503,
    # 002 搶答活動（contracts/http-api.md）
    "ACTIVITY_IN_PROGRESS": 409,
    "NOT_RUNNING": 409,
    "ALREADY_SUBMITTED": 409,
    "COOLDOWN": 409,
    "NOT_ENDED": 409,
    "UNKNOWN_UNIT": 404,
    "INCOMPLETE_GROUP": 422,
    "INVALID_ANSWER": 422,
    "INVALID_CODE": 401,
    "TOO_MANY_ATTEMPTS": 429,
    "PERSIST_FAILED": 500,
}


def error_body(code: str, message: str, issues=None, extra=None) -> dict:
    return {"error": {"code": code, "message": message, "issues": issues or [], **(extra or {})}}


def create_app(settings: Settings, sheets_gateway: SheetsGateway, results_provider: ActivityResultsProvider | None = None, clock=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="課堂搶答系統")
    app.state.settings = settings
    app.state.sheets = sheets_gateway
    app.state.db = Database(settings.data_dir)
    app.state.auth = TeacherAuth(settings.teacher_password, settings.token_ttl_seconds, settings.login_max_failures, settings.login_lock_seconds)
    app.state.registry = ActivityRegistry(app.state.db, settings, clock)
    app.state.registry.startup()  # 未結束的活動標示為已中斷（research R7）
    app.state.sessions = StudentSessions(settings.join_max_failures, settings.join_lock_seconds, settings.join_global_failures_per_min)
    app.state.hub = realtime.Hub(app.state.registry)
    if results_provider is None:  # 預設讀取 002 保存的活動結果；設定 GB_RESULTS_DIR 時改用 JSON 結果檔（tasks T058）
        if settings.results_dir is not None:
            results_provider = JsonFileResultsProvider(settings.results_dir)
        else:
            results_provider = SqliteActivityResultsProvider(app.state.registry.repo)
    app.state.results = results_provider

    @app.exception_handler(DomainError)
    def domain_error(_: Request, exc: DomainError):
        issues = None
        if isinstance(exc, ImportFailed):
            issues = [{"code": i.code.value, "message": i.message, "sheet": i.sheet, "row": i.row, "cell": i.cell} for i in exc.issues]
        status = STATUS.get(exc.code, 422)
        extra = exc.extra if isinstance(exc, DomainErrorWithExtra) else None
        return JSONResponse(error_body(exc.code, exc.message, issues, extra), status_code=status)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, exc: RequestValidationError):
        fields = "、".join(".".join(str(p) for p in e["loc"] if p != "body") or "請求內容" for e in exc.errors())
        return JSONResponse(error_body("VALIDATION_ERROR", f"輸入格式不正確：{fields}"), status_code=422)

    @app.exception_handler(Exception)
    def unexpected_error(_: Request, exc: Exception):
        log.error("未預期的錯誤：%s", type(exc).__name__)  # 不輸出堆疊與內容給使用者
        return JSONResponse(error_body("INTERNAL_ERROR", "系統發生錯誤，請稍後再試。"), status_code=500)

    app.include_router(auth_routes.router)
    app.include_router(worksheet_routes.router)
    app.include_router(result_routes.router)
    app.include_router(activity_routes.router)
    app.include_router(student_routes.router)
    app.include_router(realtime.router)  # 新的路由都要在靜態檔之前掛上
    app.include_router(page_routes.router)  # / 與 /teacher 回傳頁面、舊網址導向（003）
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
