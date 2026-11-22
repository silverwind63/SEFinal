"""驗證老師輸入的試算表網址並取出試算表 ID。"""

import re

from guided_buzz.domain.errors import ImportErrorCode, ImportFailed, issue
from guided_buzz.domain.models import SPREADSHEET_ID_RE

_URL = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([^/?#]+)")
MAX_LENGTH = 2048


def parse_spreadsheet_id(text: str) -> str:
    text = (text or "").strip()
    match = _URL.match(text)
    candidate = match.group(1) if match else text
    if len(text) > MAX_LENGTH or not SPREADSHEET_ID_RE.match(candidate):
        raise ImportFailed([issue(ImportErrorCode.INVALID_SHEET_URL)])
    return candidate
