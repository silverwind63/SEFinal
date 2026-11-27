"""學習單匯入、確認、取消與查詢（contracts/http-api.md）。"""

import logging

from fastapi import APIRouter, Depends, Request

from guided_buzz.api.deps import require_teacher
from guided_buzz.api.schemas import ImportRequest, StatusOut, WorksheetPreview, WorksheetSummary
from guided_buzz.domain.errors import ImportFailed
from guided_buzz.sheets.url import parse_spreadsheet_id
from guided_buzz.storage import worksheets
from guided_buzz.worksheet.parser import parse, structure_hash

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/worksheets")


@router.post("", status_code=201, response_model=WorksheetPreview)
def import_worksheet(body: ImportRequest, request: Request, owner: str = Depends(require_teacher)) -> WorksheetPreview:
    state = request.app.state
    try:
        spreadsheet_id = parse_spreadsheet_id(body.spreadsheet_url)
        grid = state.sheets.fetch_grid(spreadsheet_id)
        parsed = parse(grid, state.settings.header_labels, state.settings.max_questions)
    except ImportFailed as e:
        log.info("匯入學習單失敗：%s", ",".join(i.code.value for i in e.issues))
        raise
    ws = worksheets.create_pending(state.db, owner, spreadsheet_id, grid.title, parsed, structure_hash(parsed))
    log.info("匯入學習單成功：%s，題數 %d", ws.id, parsed.question_count)
    return WorksheetPreview.of(ws)


@router.get("", response_model=list[WorksheetSummary])
def list_worksheets(request: Request, owner: str = Depends(require_teacher)) -> list[WorksheetSummary]:
    return [
        WorksheetSummary(
            id=str(ws.id),
            spreadsheet_title=ws.spreadsheet_title,
            status=ws.status.value,
            question_count=ws.parsed.question_count,
            group_count=ws.parsed.group_count,
            created_at=ws.created_at.isoformat(),
            confirmed_at=ws.confirmed_at.isoformat() if ws.confirmed_at else None,
        )
        for ws in worksheets.list_by_owner(request.app.state.db, owner)
    ]


@router.get("/{worksheet_id}", response_model=WorksheetPreview)
def get_worksheet(worksheet_id: str, request: Request, owner: str = Depends(require_teacher)) -> WorksheetPreview:
    return WorksheetPreview.of(worksheets.get(request.app.state.db, worksheet_id, owner))


@router.post("/{worksheet_id}/confirm", response_model=WorksheetPreview)
def confirm_worksheet(worksheet_id: str, request: Request, owner: str = Depends(require_teacher)) -> WorksheetPreview:
    ws = worksheets.confirm(request.app.state.db, worksheet_id, owner)
    log.info("確認學習單：%s", ws.id)
    return WorksheetPreview.of(ws)


@router.post("/{worksheet_id}/cancel", response_model=StatusOut)
def cancel_worksheet(worksheet_id: str, request: Request, owner: str = Depends(require_teacher)) -> StatusOut:
    ws = worksheets.cancel(request.app.state.db, worksheet_id, owner)
    log.info("取消學習單：%s", ws.id)
    return StatusOut(id=str(ws.id), status=ws.status.value)
