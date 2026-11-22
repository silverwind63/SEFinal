"""一次性手動腳本：把 Google Sheets 的 spreadsheets.get 回應存成測試快照（tasks T005）。

用法（需先依 quickstart 設定 service account，並把試算表共用給它）：
    GB_GOOGLE_CREDENTIALS_FILE=/path/to/sa.json \
    uv run python scripts/capture_sheet_fixture.py <試算表網址或 ID> tests/fixtures/sheets/sample_a.json

回應只包含試算表內容，不含任何憑證。此腳本不屬於自動化測試。
"""

import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

from guided_buzz.sheets.google_gateway import FIELDS, SCOPES
from guided_buzz.sheets.url import parse_spreadsheet_id


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("用法：capture_sheet_fixture.py <試算表網址或 ID> <輸出 JSON 路徑>")
    key_file = os.environ.get("GB_GOOGLE_CREDENTIALS_FILE")
    if not key_file:
        sys.exit("請先設定環境變數 GB_GOOGLE_CREDENTIALS_FILE")
    creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    spreadsheet_id = parse_spreadsheet_id(sys.argv[1])
    response = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, includeGridData=True, fields=FIELDS)
        .execute()
    )
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(response, f, ensure_ascii=False, indent=2)
    print(f"已寫入 {sys.argv[2]}")


if __name__ == "__main__":
    main()
