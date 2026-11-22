"""模組之間的介面（contracts/results-provider.md、diagrams 04-class.puml）。"""

from typing import Protocol
from uuid import UUID

from guided_buzz.domain.models import ActivityResult, CellRef, SpreadsheetGrid


class ActivityResultsProvider(Protocol):
    def get_result(self, activity_id: UUID | str, requester: str) -> ActivityResult:
        """活動不存在或 requester 不是活動老師時拋出 NotFound。"""


class SheetsGateway(Protocol):
    account_email: str  # 目前登入的 Google 帳號，用於錯誤訊息

    def fetch_grid(self, spreadsheet_id: str) -> SpreadsheetGrid: ...

    def write_cells(self, spreadsheet_id: str, values: dict[CellRef, str]) -> None: ...
