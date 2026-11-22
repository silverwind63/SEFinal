"""寫回規劃與結構一致性檢查（research R4、R5），純函式、不做 I/O。"""

from dataclasses import replace

from guided_buzz.domain.errors import ImportFailed, StructureChanged
from guided_buzz.domain.models import CellRef, ParsedWorksheet, SpreadsheetGrid
from guided_buzz.worksheet.parser import parse


def _value(grid: SpreadsheetGrid, ref: CellRef) -> str:
    sheet = next((s for s in grid.sheets if s.sheet_id == ref.sheet_id), None)
    return sheet.values.get(ref.cell, "").strip() if sheet else ""


def plan(answers: dict[CellRef, str], current: SpreadsheetGrid) -> tuple[dict[CellRef, str], set[CellRef]]:
    """只寫入目前仍為空白的填空格；已有內容者不覆蓋（FR-026）。"""
    to_write = {ref: text for ref, text in answers.items() if not _value(current, ref)}
    return to_write, set(answers) - set(to_write)


def verify_unchanged(parsed: ParsedWorksheet, current: SpreadsheetGrid, labels: tuple[str, str, str], max_questions: int) -> None:
    """以目前的雲端內容重新解析，比對填空格位置；已有內容的填空格仍視為填空格（FR-019）。"""
    blanks = {}
    for b in parsed.questions:
        blanks.setdefault(b.location.sheet_id, set()).add(b.location.cell)
    cleared = replace(
        current,
        sheets=tuple(replace(s, values={k: v for k, v in s.values.items() if k not in blanks.get(s.sheet_id, set())}) for s in current.sheets),
    )
    try:
        now = parse(cleared, labels, max_questions)
    except ImportFailed as e:
        raise StructureChanged(e.issues[0].message.rstrip("。")) from None
    if now.question_count != parsed.question_count:
        raise StructureChanged(f"題數由 {parsed.question_count} 題變成 {now.question_count} 題")
    for old, new in zip(parsed.questions, now.questions):
        if (old.location, old.group_no) != (new.location, new.group_no):
            raise StructureChanged(f"第 {old.question_no} 題原本在 {old.location.sheet_title}!{old.location.cell}，現在在 {new.location.sheet_title}!{new.location.cell}")
