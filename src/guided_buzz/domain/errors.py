"""錯誤代碼、繁體中文訊息與領域例外（data-model.md ImportErrorCode）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImportErrorCode(str, Enum):
    INVALID_SHEET_URL = "INVALID_SHEET_URL"
    SHEET_NOT_FOUND = "SHEET_NOT_FOUND"
    SHEET_FORBIDDEN = "SHEET_FORBIDDEN"
    SHEETS_UNAVAILABLE = "SHEETS_UNAVAILABLE"
    GOOGLE_AUTH_EXPIRED = "GOOGLE_AUTH_EXPIRED"
    HEADER_NOT_FOUND = "HEADER_NOT_FOUND"
    NO_QUESTION_ROWS = "NO_QUESTION_ROWS"
    NO_BLANK_IN_ROW = "NO_BLANK_IN_ROW"
    MULTIPLE_BLANKS_IN_ROW = "MULTIPLE_BLANKS_IN_ROW"
    GROUP_RANGE_INCOMPLETE = "GROUP_RANGE_INCOMPLETE"
    TOO_MANY_QUESTIONS = "TOO_MANY_QUESTIONS"
    STRUCTURE_CHANGED = "STRUCTURE_CHANGED"


MESSAGES = {
    ImportErrorCode.INVALID_SHEET_URL: "網址格式不正確，請貼上 Google Sheets 試算表的網址（https://docs.google.com/spreadsheets/d/…）或試算表 ID。",
    ImportErrorCode.SHEET_NOT_FOUND: "找不到這份試算表，請確認網址是否正確。",
    ImportErrorCode.SHEET_FORBIDDEN: "目前登入的 Google 帳號（{email}）沒有這份試算表的編輯權限，請改用有權限的帳號重新登入，或請擁有者把試算表共用給這個帳號（編輯者）。",
    ImportErrorCode.SHEETS_UNAVAILABLE: "目前無法連線到 Google Sheets，請稍後再試。",
    ImportErrorCode.GOOGLE_AUTH_EXPIRED: "Google 授權已失效或被撤銷，請在終端機執行 `uv run python -m guided_buzz login-google` 重新登入，並重新啟動伺服器。",
    ImportErrorCode.HEADER_NOT_FOUND: "找不到表頭列：學習單中必須有一列同時包含「{labels}」三個表頭。",
    ImportErrorCode.NO_QUESTION_ROWS: "表頭以下找不到任何題目列（「{label}」欄位有文字的列）。",
    ImportErrorCode.NO_BLANK_IN_ROW: "工作表「{sheet}」第 {row} 列沒有填空格：「{label}」欄位範圍內必須有一個空白儲存格。",
    ImportErrorCode.MULTIPLE_BLANKS_IN_ROW: "工作表「{sheet}」第 {row} 列有 {count} 個空白作答區，每個題目列只能有一個填空格。",
    ImportErrorCode.GROUP_RANGE_INCOMPLETE: "工作表「{sheet}」的題組（{cell}）範圍內第 {row} 列不是題目列，題組的每一列都必須是題目列。",
    ImportErrorCode.TOO_MANY_QUESTIONS: "題數 {count} 超過上限 {limit} 題。",
    ImportErrorCode.STRUCTURE_CHANGED: "學習單在匯入後被修改，填空格位置與匯入時不同：{detail}。請重新匯入學習單。",
}


@dataclass(frozen=True)
class ImportIssue:
    code: ImportErrorCode
    message: str
    sheet: str | None = None
    row: int | None = None
    cell: str | None = None


def issue(code: ImportErrorCode, *, sheet: str | None = None, row: int | None = None, cell: str | None = None, **params) -> ImportIssue:
    message = MESSAGES[code].format(sheet=sheet, row=row, cell=cell, **params)
    return ImportIssue(code, message, sheet, row, cell)


class DomainError(Exception):
    code = "ERROR"
    default_message = "發生錯誤"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFound(DomainError):
    code = "NOT_FOUND"
    default_message = "找不到指定的資料。"


class InvalidState(DomainError):
    code = "INVALID_STATE"
    default_message = "目前的狀態不允許這個操作。"


class Unauthorized(DomainError):
    code = "UNAUTHORIZED"
    default_message = "需要登入，或登入已過期，請重新登入。"


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    default_message = "密碼錯誤。"


class LoginLocked(DomainError):
    code = "LOGIN_LOCKED"

    def __init__(self, remaining_seconds: int):
        self.remaining_seconds = remaining_seconds
        super().__init__(f"密碼錯誤次數過多，請在 {remaining_seconds} 秒後再試。")


class ResultsFileInvalid(DomainError):
    code = "INVALID_RESULTS"


class ImportFailed(DomainError):
    """一次回報所有問題（research R3 第 9 點）。"""

    def __init__(self, issues: list[ImportIssue]):
        self.issues = issues
        self.code = issues[0].code.value
        message = issues[0].message if len(issues) == 1 else f"學習單有 {len(issues)} 個問題，請逐一修正後重新匯入。"
        super().__init__(message)


class StructureChanged(ImportFailed):
    def __init__(self, detail: str):
        super().__init__([issue(ImportErrorCode.STRUCTURE_CHANGED, detail=detail)])


class SheetNotFound(ImportFailed):
    def __init__(self):
        super().__init__([issue(ImportErrorCode.SHEET_NOT_FOUND)])


class SheetForbidden(ImportFailed):
    def __init__(self, email: str):
        super().__init__([issue(ImportErrorCode.SHEET_FORBIDDEN, email=email)])


class SheetsUnavailable(ImportFailed):
    def __init__(self):
        super().__init__([issue(ImportErrorCode.SHEETS_UNAVAILABLE)])


class GoogleAuthExpired(ImportFailed):
    def __init__(self):
        super().__init__([issue(ImportErrorCode.GOOGLE_AUTH_EXPIRED)])
