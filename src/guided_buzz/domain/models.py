"""全專案共用資料結構的唯一定義處（Constitution 原則 V、data-model.md）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

CELL_RE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
SPREADSHEET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,100}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class WorksheetStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class SubmissionOutcome(str, Enum):
    SUCCESS = "success"
    NOT_WON = "not_won"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class CellRef:
    sheet_id: int
    sheet_title: str
    cell: str

    def __post_init__(self):
        _require(self.sheet_id >= 0, "工作表 ID 不可為負數")
        _require(bool(self.sheet_title), "工作表名稱不可為空")
        _require(bool(CELL_RE.match(self.cell)), f"儲存格位置格式不正確：{self.cell}")


@dataclass(frozen=True)
class SheetGrid:
    sheet_id: int
    title: str
    values: dict[str, str]  # A1 → 顯示文字；沒有值的儲存格不列出
    merges: tuple[str, ...]  # 'G5:H5'


@dataclass(frozen=True)
class SpreadsheetGrid:
    spreadsheet_id: str
    title: str
    sheets: tuple[SheetGrid, ...]


@dataclass(frozen=True)
class Blank:
    question_no: int
    location: CellRef
    source_label: str | None
    sub_label: str | None
    group_no: int | None


@dataclass(frozen=True)
class QuestionGroup:
    group_no: int
    source_label: str | None
    question_nos: tuple[int, ...]

    def __post_init__(self):
        nos = self.question_nos
        _require(len(nos) >= 2, "題組至少要有 2 題")
        _require(all(b == a + 1 for a, b in zip(nos, nos[1:])), "題組的題號必須遞增且連續")


@dataclass(frozen=True)
class ParsedWorksheet:
    questions: tuple[Blank, ...]
    groups: tuple[QuestionGroup, ...]

    def __post_init__(self):
        _require(bool(self.questions), "至少要有 1 題")
        _require([b.question_no for b in self.questions] == list(range(1, len(self.questions) + 1)), "系統題號必須從 1 開始連續")
        grouped = [n for g in self.groups for n in g.question_nos]
        _require(len(grouped) == len(set(grouped)), "每個題號最多屬於一個題組")

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def group_count(self) -> int:
        return len(self.groups)


@dataclass(frozen=True)
class Worksheet:
    id: UUID
    owner: str
    spreadsheet_id: str
    spreadsheet_title: str
    structure_hash: str
    status: WorksheetStatus
    parsed: ParsedWorksheet
    created_at: datetime
    confirmed_at: datetime | None = None

    def __post_init__(self):
        _require(bool(SPREADSHEET_ID_RE.match(self.spreadsheet_id)), "試算表 ID 格式不正確")
        _require(len(self.spreadsheet_title) <= 255, "試算表名稱過長")


@dataclass(frozen=True)
class SubmissionRecord:
    question_nos: tuple[int, ...]
    team_name: str
    answers: dict[int, str]
    rank: int
    outcome: SubmissionOutcome

    def __post_init__(self):
        _require(bool(self.question_nos), "搶答紀錄至少要有一個題號")
        _require(set(self.answers) == set(self.question_nos), "answers 的題號必須與 question_nos 相同")
        _require(self.rank >= 1, "搶答順位必須 ≥ 1")


@dataclass(frozen=True)
class ActivityResult:
    activity_id: UUID
    worksheet_id: UUID
    owner: str
    ended: bool
    submissions: tuple[SubmissionRecord, ...]

    def __post_init__(self):
        winners = [s.question_nos for s in self.submissions if s.outcome is SubmissionOutcome.SUCCESS]
        _require(len(winners) == len(set(winners)), "同一個搶答單位最多只能有一筆成功紀錄")


@dataclass(frozen=True)
class WritebackResult:
    filled: tuple[int, ...]
    unfilled: tuple[int, ...]
    skipped_non_empty: tuple[int, ...]


# ---- 002 搶答活動（specs/002-online-buzz-activity/data-model.md） ----

UNIT_KEY_RE = re.compile(r"^[GQ][1-9][0-9]*$")


class ActivityPhase(str, Enum):
    PREPARING = "preparing"
    RUNNING = "running"
    ENDED = "ended"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class BuzzUnit:
    """搶答單位：題組（G<group_no>）或不屬於題組的單一題目（Q<question_no>）。"""

    key: str
    question_nos: tuple[int, ...]
    display: str

    def __post_init__(self):
        _require(bool(UNIT_KEY_RE.match(self.key)), f"搶答單位鍵值格式不正確：{self.key}")
        _require(bool(self.question_nos), "搶答單位至少要有一個題號")
        _require(list(self.question_nos) == sorted(set(self.question_nos)), "搶答單位的題號必須遞增且不重複")
        if self.key.startswith("Q"):
            _require(self.question_nos == (int(self.key[1:]),), "單一題目的鍵值必須等於它的題號")
        else:
            _require(len(self.question_nos) >= 2, "題組至少要有 2 題")
