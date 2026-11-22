"""學習單 repository（data-model.md Worksheet）。資料表只由 storage 模組存取。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from guided_buzz.domain.errors import InvalidState, NotFound
from guided_buzz.domain.models import Blank, CellRef, ParsedWorksheet, QuestionGroup, Worksheet, WorksheetStatus
from guided_buzz.storage.db import Database

NOT_FOUND_MESSAGE = "找不到這份學習單。"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_pending(db: Database, owner: str, spreadsheet_id: str, title: str, parsed: ParsedWorksheet, structure_hash: str) -> Worksheet:
    wid = uuid4()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO worksheets VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (str(wid), owner, spreadsheet_id, title[:255], structure_hash, WorksheetStatus.PENDING.value, _now()),
        )
        conn.executemany(
            "INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (str(wid), b.question_no, b.location.sheet_id, b.location.sheet_title, b.location.cell, b.source_label, b.sub_label, b.group_no)
                for b in parsed.questions
            ],
        )
        conn.executemany("INSERT INTO question_groups VALUES (?, ?, ?)", [(str(wid), g.group_no, g.source_label) for g in parsed.groups])
    return get(db, wid, owner)


def get(db: Database, worksheet_id: UUID | str, owner: str) -> Worksheet:
    try:
        wid = str(UUID(str(worksheet_id)))
    except ValueError:
        raise NotFound(NOT_FOUND_MESSAGE) from None
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM worksheets WHERE id = ? AND owner = ?", (wid, owner)).fetchone()
        if row is None:  # 非擁有者視同不存在
            raise NotFound(NOT_FOUND_MESSAGE)
        questions = conn.execute("SELECT * FROM questions WHERE worksheet_id = ? ORDER BY question_no", (wid,)).fetchall()
        groups = conn.execute("SELECT * FROM question_groups WHERE worksheet_id = ? ORDER BY group_no", (wid,)).fetchall()
    blanks = tuple(
        Blank(q["question_no"], CellRef(q["sheet_id"], q["sheet_title"], q["cell"]), q["source_label"], q["sub_label"], q["group_no"])
        for q in questions
    )
    parsed = ParsedWorksheet(
        blanks,
        tuple(QuestionGroup(g["group_no"], g["source_label"], tuple(b.question_no for b in blanks if b.group_no == g["group_no"])) for g in groups),
    )
    return Worksheet(
        UUID(row["id"]),
        row["owner"],
        row["spreadsheet_id"],
        row["spreadsheet_title"],
        row["structure_hash"],
        WorksheetStatus(row["status"]),
        parsed,
        datetime.fromisoformat(row["created_at"]),
        datetime.fromisoformat(row["confirmed_at"]) if row["confirmed_at"] else None,
    )


def list_by_owner(db: Database, owner: str) -> list[Worksheet]:
    with db.transaction() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM worksheets WHERE owner = ? ORDER BY created_at", (owner,))]
    return [get(db, wid, owner) for wid in ids]


def _transition(db: Database, worksheet_id: UUID | str, owner: str, target: WorksheetStatus) -> Worksheet:
    worksheet = get(db, worksheet_id, owner)
    if worksheet.status is not WorksheetStatus.PENDING:  # 只允許 pending → confirmed／cancelled
        raise InvalidState(f"這份學習單目前是「{worksheet.status.value}」，只有待確認的學習單可以確認或取消。")
    with db.transaction() as conn:
        conn.execute(
            "UPDATE worksheets SET status = ?, confirmed_at = ? WHERE id = ?",
            (target.value, _now() if target is WorksheetStatus.CONFIRMED else None, str(worksheet.id)),
        )
    return get(db, worksheet.id, owner)


def confirm(db: Database, worksheet_id: UUID | str, owner: str) -> Worksheet:
    return _transition(db, worksheet_id, owner, WorksheetStatus.CONFIRMED)


def cancel(db: Database, worksheet_id: UUID | str, owner: str) -> Worksheet:
    return _transition(db, worksheet_id, owner, WorksheetStatus.CANCELLED)


def record_writeback(db: Database, worksheet_id: UUID, activity_id: UUID, result) -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO writebacks VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                str(worksheet_id),
                str(activity_id),
                ",".join(map(str, result.filled)),
                ",".join(map(str, result.unfilled)),
                ",".join(map(str, result.skipped_non_empty)),
                _now(),
            ),
        )
