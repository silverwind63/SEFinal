"""學習單解析：SpreadsheetGrid → ParsedWorksheet（research R3 的 9 個步驟，純函式）。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from guided_buzz.domain.a1 import parse_a1, parse_range, to_a1
from guided_buzz.domain.errors import ImportErrorCode, ImportFailed, ImportIssue, issue
from guided_buzz.domain.models import Blank, CellRef, ParsedWorksheet, QuestionGroup, SheetGrid, SpreadsheetGrid


@dataclass(frozen=True)
class _Merge:
    r1: int
    c1: int
    r2: int
    c2: int


class _Sheet:
    """方便以（列, 欄）查詢值與合併範圍的工作表包裝。"""

    def __init__(self, grid: SheetGrid):
        self.grid = grid
        self.values = {parse_a1(a1): text for a1, text in grid.values.items()}
        self.merges = [_Merge(*parse_range(m)) for m in grid.merges]
        self.max_row = max([r for r, _ in self.values] + [m.r2 for m in self.merges] + [0])

    def text(self, row: int, col: int) -> str:
        return self.values.get((row, col), "").strip()

    def merge_at(self, row: int, col: int) -> _Merge | None:
        return next((m for m in self.merges if m.r1 <= row <= m.r2 and m.c1 <= col <= m.c2), None)

    def col_span(self, row: int, col: int) -> tuple[int, int]:
        m = self.merge_at(row, col)
        return (m.c1, m.c2) if m else (col, col)


def _find_header(sheet: _Sheet, labels: tuple[str, str, str]) -> tuple[int, list[tuple[int, int]]] | None:
    for row in range(1, sheet.max_row + 1):
        spans = []
        for label in labels:
            col = next((c for (r, c), t in sheet.values.items() if r == row and t.strip() == label), None)
            if col is None:
                break
            spans.append(sheet.col_span(row, col))
        else:
            return row, spans
    return None


def _answer_slots(sheet: _Sheet, row: int, c1: int, c2: int) -> list[tuple[int, str]]:
    """作答範圍內的槽位（欄, 文字）：合併範圍算一個槽位，以左上角代表；不是左上角的被合併儲存格略過。"""
    slots = []
    for col in range(c1, c2 + 1):
        m = sheet.merge_at(row, col)
        if m and (m.r1, m.c1) != (row, col):
            continue
        slots.append((col, sheet.text(row, col)))
    return slots


def parse(grid: SpreadsheetGrid, labels: tuple[str, str, str], max_questions: int) -> ParsedWorksheet:
    problems: list[ImportIssue] = []
    rows_found: list[tuple[SheetGrid, int, int, str | None, str | None, int | None]] = []  # sheet, row, blank col, 原題號, 子題, 題組 key
    group_labels: dict[tuple[int, int, int], str | None] = {}
    any_header = False

    for grid_sheet in grid.sheets:
        sheet = _Sheet(grid_sheet)
        header = _find_header(sheet, labels)
        if header is None:
            continue
        any_header = True
        header_row, ((n1, n2), (q1, q2), (a1, a2)) = header

        question_rows = [
            r
            for r in range(header_row + 1, sheet.max_row + 1)
            if any(sheet.text(r, c) and not (sheet.merge_at(r, c) and sheet.merge_at(r, c).r1 != r) for c in range(q1, q2 + 1))
        ]
        question_set = set(question_rows)

        # 題組：題號欄位內縱跨 2 列以上的合併範圍
        group_of_row: dict[int, tuple[int, int, int]] = {}
        for m in sheet.merges:
            if n1 <= m.c1 <= n2 and m.r1 > header_row and m.r2 > m.r1:
                outside = [r for r in range(m.r1, m.r2 + 1) if r not in question_set]
                if outside:
                    for r in outside:
                        problems.append(issue(ImportErrorCode.GROUP_RANGE_INCOMPLETE, sheet=grid_sheet.title, row=r, cell=to_a1(m.r1, m.c1)))
                    continue
                key = (grid_sheet.sheet_id, m.r1, m.c1)
                group_labels[key] = sheet.text(m.r1, m.c1) or None
                for r in range(m.r1, m.r2 + 1):
                    group_of_row[r] = key

        for r in question_rows:
            slots = _answer_slots(sheet, r, a1, a2)
            segments: list[int] = []  # 每段空白區段最左邊的欄
            previous_blank = False
            for col, text in slots:
                if not text and not previous_blank:
                    segments.append(col)
                previous_blank = not text
            if len(segments) != 1:
                code = ImportErrorCode.NO_BLANK_IN_ROW if not segments else ImportErrorCode.MULTIPLE_BLANKS_IN_ROW
                problems.append(issue(code, sheet=grid_sheet.title, row=r, label=labels[2], count=len(segments)))
                continue
            sub_label = next((t for _, t in slots if t), None)
            key = group_of_row.get(r)
            if key:
                source = group_labels[key]
            else:
                source = next((sheet.text(r, c) for c in range(n1, n2 + 1) if sheet.text(r, c)), None)
            rows_found.append((grid_sheet, r, segments[0], source, sub_label, key))

    if not any_header:
        raise ImportFailed([issue(ImportErrorCode.HEADER_NOT_FOUND, labels="、".join(labels))])
    if problems:
        raise ImportFailed(problems)
    if not rows_found:
        raise ImportFailed([issue(ImportErrorCode.NO_QUESTION_ROWS, label=labels[1])])
    if len(rows_found) > max_questions:
        raise ImportFailed([issue(ImportErrorCode.TOO_MANY_QUESTIONS, count=len(rows_found), limit=max_questions)])

    group_numbers: dict[tuple[int, int, int], int] = {}
    blanks = []
    for no, (grid_sheet, r, col, source, sub, key) in enumerate(rows_found, 1):
        group_no = group_numbers.setdefault(key, len(group_numbers) + 1) if key else None
        blanks.append(Blank(no, CellRef(grid_sheet.sheet_id, grid_sheet.title, to_a1(r, col)), source, sub, group_no))
    groups = tuple(
        QuestionGroup(gno, group_labels[key], tuple(b.question_no for b in blanks if b.group_no == gno))
        for key, gno in group_numbers.items()
    )
    return ParsedWorksheet(tuple(blanks), groups)


def structure_hash(parsed: ParsedWorksheet) -> str:
    """填空格位置清單的指紋（research R5）。"""
    items = [(b.question_no, b.location.sheet_id, b.location.cell, b.group_no) for b in parsed.questions]
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()
