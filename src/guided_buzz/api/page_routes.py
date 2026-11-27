"""頁面網址（specs/003-align-entry-pages/contracts/pages.md）：首頁是學生頁，老師頁在 /teacher，舊網址導向新網址。

必須在 app.mount("/", StaticFiles(...)) 之前掛上，否則會被靜態檔處理。
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"

router = APIRouter(include_in_schema=False)


@router.get("/")
def student_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "student.html")


@router.get("/teacher")
def teacher_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "teacher.html")


@router.get("/student.html")
def old_student_page() -> RedirectResponse:
    return RedirectResponse("/")


@router.get("/teacher.html")
def old_teacher_page() -> RedirectResponse:
    return RedirectResponse("/teacher")
