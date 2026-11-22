"""以 Google Sheets API 讀寫雲端試算表（research R3、R4、R13）。"""

from __future__ import annotations

import logging

import google.auth.exceptions
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from guided_buzz.domain.a1 import to_a1
from guided_buzz.domain.errors import GoogleAuthExpired, SheetForbidden, SheetNotFound, SheetsUnavailable
from guided_buzz.domain.models import CellRef, SheetGrid, SpreadsheetGrid

log = logging.getLogger(__name__)

FIELDS = "spreadsheetId,properties(title),sheets(properties(sheetId,title,index),merges,data(rowData(values(formattedValue))))"


def grid_from_response(response: dict) -> SpreadsheetGrid:
    sheets = []
    for sheet in sorted(response.get("sheets", []), key=lambda s: s["properties"].get("index", 0)):
        props = sheet["properties"]
        values: dict[str, str] = {}
        for block in sheet.get("data", []):
            start_row = block.get("startRow", 0)
            start_col = block.get("startColumn", 0)
            for r, row in enumerate(block.get("rowData", [])):
                for c, cell in enumerate(row.get("values", [])):
                    text = cell.get("formattedValue")
                    if text is not None and text != "":
                        values[to_a1(start_row + r + 1, start_col + c + 1)] = text
        merges = tuple(
            f"{to_a1(m['startRowIndex'] + 1, m['startColumnIndex'] + 1)}:{to_a1(m['endRowIndex'], m['endColumnIndex'])}"
            for m in sheet.get("merges", [])
        )
        sheets.append(SheetGrid(props.get("sheetId", 0), props["title"], values, merges))
    return SpreadsheetGrid(response["spreadsheetId"], response.get("properties", {}).get("title", ""), tuple(sheets))


def a1_range(ref: CellRef) -> str:
    return "'" + ref.sheet_title.replace("'", "''") + "'!" + ref.cell


class GoogleSheetsGateway:
    def __init__(self, credentials=None, timeout_seconds: float = 10, *, service=None, account_email: str = ""):
        if service is None:
            http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=timeout_seconds))
            service = build("sheets", "v4", http=http, cache_discovery=False)
        self._service = service
        self.account_email = account_email

    def fetch_grid(self, spreadsheet_id: str) -> SpreadsheetGrid:
        request = self._service.spreadsheets().get(spreadsheetId=spreadsheet_id, includeGridData=True, fields=FIELDS)
        return grid_from_response(self._execute(request))

    def write_cells(self, spreadsheet_id: str, values: dict[CellRef, str]) -> None:
        if not values:
            return
        body = {"valueInputOption": "RAW", "data": [{"range": a1_range(ref), "values": [[text]]} for ref, text in values.items()]}
        self._execute(self._service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body))

    def _execute(self, request):
        try:
            return request.execute()
        except HttpError as e:
            status = int(e.resp.status)
            log.warning("Google Sheets API 回應錯誤：HTTP %s", status)  # 不記錄回應原文
            if status == 401:
                raise GoogleAuthExpired() from None
            if status == 403:
                raise SheetForbidden(self.account_email) from None
            if status == 404:
                raise SheetNotFound() from None
            raise SheetsUnavailable() from None
        except google.auth.exceptions.RefreshError:
            log.warning("Google 授權已失效或被撤銷")
            raise GoogleAuthExpired() from None
        except (OSError, httplib2.HttpLib2Error, google.auth.exceptions.GoogleAuthError):
            log.warning("無法連線到 Google Sheets 或憑證無法使用")
            raise SheetsUnavailable() from None
