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
    ImportErrorCode.STRUCTURE_CHANGED: "學習單的結構和匯入時不同（例如插入或刪除了列），無法確定答案該寫到哪一格。細節：{detail}。請重新匯入學習單後再寫回。",
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


# ---- 002 搶答活動（specs/002-online-buzz-activity/contracts/http-api.md） ----


class SubmissionRejectCode(str, Enum):
    NOT_RUNNING = "NOT_RUNNING"
    UNAUTHORIZED = "UNAUTHORIZED"
    COOLDOWN = "COOLDOWN"
    UNKNOWN_UNIT = "UNKNOWN_UNIT"
    INCOMPLETE_GROUP = "INCOMPLETE_GROUP"
    INVALID_ANSWER = "INVALID_ANSWER"
    ALREADY_SUBMITTED = "ALREADY_SUBMITTED"


REJECT_MESSAGES = {
    SubmissionRejectCode.NOT_RUNNING: "目前不在搶答時間。",
    SubmissionRejectCode.UNAUTHORIZED: "組別身分已失效（代碼可能已重新產生），請重新輸入組別代碼。",
    SubmissionRejectCode.COOLDOWN: "本組領先其他組別，冷卻中，請在 {seconds} 秒後再送出。",
    SubmissionRejectCode.UNKNOWN_UNIT: "找不到這個搶答單位。",
    SubmissionRejectCode.INCOMPLETE_GROUP: "題組必須一次送出全部題目的答案。{detail}",
    SubmissionRejectCode.INVALID_ANSWER: "第 {question_no} 題的答案{reason}。",
    SubmissionRejectCode.ALREADY_SUBMITTED: "本組已作答此題。",
}


class DomainErrorWithExtra(DomainError):
    """錯誤回應中除了 code、message 以外，還要附帶的欄位（例如剩餘秒數、缺少的題號）。"""

    extra: dict = {}


class SubmissionRejected(DomainErrorWithExtra):
    def __init__(self, code: SubmissionRejectCode, **params):
        self.code = code.value
        self.reject_code = code
        self.extra = {}
        if code is SubmissionRejectCode.COOLDOWN:
            self.extra["retry_after_seconds"] = params["seconds"]
        if code is SubmissionRejectCode.INCOMPLETE_GROUP:
            self.extra["missing"] = params.get("missing", [])
            self.extra["unexpected"] = params.get("unexpected", [])
            parts = []
            if self.extra["missing"]:
                parts.append("缺少第 " + "、".join(map(str, self.extra["missing"])) + " 題")
            if self.extra["unexpected"]:
                parts.append("第 " + "、".join(map(str, self.extra["unexpected"])) + " 題不屬於這個單位")
            params["detail"] = "；".join(parts) + "。" if parts else ""
        if code is SubmissionRejectCode.INVALID_ANSWER:
            self.extra["question_no"] = params["question_no"]
        super().__init__(REJECT_MESSAGES[code].format(**params))


class ActivityInProgress(DomainError):
    code = "ACTIVITY_IN_PROGRESS"
    default_message = "已有一場準備中或搶答中的活動，請先結束它再建立新活動。"


class InvalidCode(DomainError):
    code = "INVALID_CODE"
    default_message = "組別代碼錯誤。"


class TooManyAttempts(DomainErrorWithExtra):
    code = "TOO_MANY_ATTEMPTS"

    def __init__(self, remaining_seconds: int):
        self.extra = {"retry_after_seconds": remaining_seconds}
        super().__init__(f"嘗試次數過多，請在 {remaining_seconds} 秒後再試。")


class NotEnded(DomainError):
    code = "NOT_ENDED"
    default_message = "活動尚未結束，結束後才能檢視結果。"


class PersistFailed(DomainError):
    code = "PERSIST_FAILED"
    default_message = "結果保存失敗，活動仍在進行中，請再試一次。"


class InvalidInput(DomainError):
    code = "VALIDATION_ERROR"
