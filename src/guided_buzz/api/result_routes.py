"""答案寫回與結果匯出（contracts/http-api.md）。"""

import logging

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response

from guided_buzz.api.deps import require_teacher
from guided_buzz.api.schemas import WritebackOut, WritebackRequest
from guided_buzz.domain.errors import InvalidState, NotFound
from guided_buzz.domain.models import ActivityResult, WorksheetStatus, WritebackResult
from guided_buzz.export.csv_export import to_csv
from guided_buzz.results.mapping import success_answers
from guided_buzz.storage import worksheets
from guided_buzz.worksheet.writeback import plan, verify_unchanged

log = logging.getLogger(__name__)
router = APIRouter()


def ended_result(request: Request, activity_id: str, owner: str) -> ActivityResult:
    provider = request.app.state.results
    if provider is None:
        raise NotFound("尚未設定搶答結果來源，找不到這場活動。")
    result = provider.get_result(activity_id, owner)
    if not result.ended:
        raise InvalidState("活動尚未結束，結束後才能寫回或匯出。")
    return result


@router.post("/api/worksheets/{worksheet_id}/writeback", response_model=WritebackOut)
def writeback(worksheet_id: str, body: WritebackRequest, request: Request, owner: str = Depends(require_teacher)) -> WritebackOut:
    state = request.app.state
    ws = worksheets.get(state.db, worksheet_id, owner)
    if ws.status is not WorksheetStatus.CONFIRMED:
        raise InvalidState("學習單尚未確認，確認後才能寫回。")
    result = ended_result(request, body.activity_id, owner)
    if result.worksheet_id != ws.id:
        raise NotFound("這場活動不屬於這份學習單。")

    current = state.sheets.fetch_grid(ws.spreadsheet_id)
    verify_unchanged(ws.parsed, current, state.settings.header_labels, state.settings.max_questions)
    answers, won, unfilled = success_answers(result, ws.parsed)
    to_write, skipped_refs = plan(answers, current)
    state.sheets.write_cells(ws.spreadsheet_id, to_write)

    location = {b.question_no: b.location for b in ws.parsed.questions}
    skipped = tuple(n for n in won if location[n] in skipped_refs)
    outcome = WritebackResult(tuple(n for n in won if n not in skipped), unfilled, skipped)
    worksheets.record_writeback(state.db, ws.id, result.activity_id, outcome)
    log.info("寫回學習單 %s（活動 %s）：已填 %d、未填 %d、跳過 %d", ws.id, result.activity_id, len(outcome.filled), len(outcome.unfilled), len(outcome.skipped_non_empty))
    return WritebackOut(filled=list(outcome.filled), unfilled=list(outcome.unfilled), skipped_non_empty=list(outcome.skipped_non_empty))


@router.get("/api/activities/{activity_id}/results.csv")
def export_csv(activity_id: str, request: Request, owner: str = Depends(require_teacher)) -> Response:
    result = ended_result(request, activity_id, owner)
    ws = worksheets.get(request.app.state.db, result.worksheet_id, owner)
    text, count = to_csv(result, ws.parsed)
    log.info("匯出活動 %s 的結果 CSV：%d 筆", result.activity_id, count)
    filename = f"搶答結果_{result.activity_id}.csv"
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"X-Record-Count": str(count), "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
