# Data Model: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Diagrams**: [diagrams.md](./diagrams.md)

所有跨模組共用的資料結構**只在** `src/guided_buzz/domain/models.py` 定義一次（Constitution 原則 V），
其他模組（parser、writeback、sheets、export、storage、api）與 002 一律從那裡引用。
類別圖見 [`diagrams/001-guided-notes-import/04-class.puml`](../../diagrams/001-guided-notes-import/04-class.puml)。
API 回應使用的 pydantic schema 定義在 `src/guided_buzz/api/schemas.py`，由 domain 模型轉換而來，不重複定義欄位規則。

## 共用列舉

| 名稱 | 值 | 說明 |
|------|----|------|
| `WorksheetStatus` | `pending` / `confirmed` / `cancelled` | 學習單匯入狀態 |
| `SubmissionOutcome` | `success` / `not_won` / `invalidated` | 送出結果（由 002 產生） |
| `ImportErrorCode` | 見下方錯誤代碼表 | 匯入驗證錯誤代碼 |

## 實體

### CellRef（儲存格位置，值物件）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `sheet_id` | int | Google Sheets 工作表 ID（工作表改名後仍不變），≥ 0 |
| `sheet_title` | str | 工作表名稱，非空；只用於顯示與組成 A1 範圍 |
| `cell` | str | A1 表示法，符合 `^[A-Z]{1,3}[1-9][0-9]*$` |

### SpreadsheetGrid / SheetGrid（與來源無關的表格資料）

由 `SheetsGateway` 產生，解析器與寫回規劃只處理這個結構，不直接接觸 Google API 回應。

| 欄位 | 型別 | 規則 |
|------|------|------|
| `SpreadsheetGrid.spreadsheet_id` | str | 試算表 ID |
| `SpreadsheetGrid.title` | str | 試算表名稱（只用於顯示） |
| `SpreadsheetGrid.sheets` | list[SheetGrid] | 依工作表順序 |
| `SheetGrid.sheet_id` | int | 工作表 ID |
| `SheetGrid.title` | str | 工作表名稱 |
| `SheetGrid.values` | dict[str, str] | A1 位置 → 顯示文字（`formattedValue`）；沒有值的儲存格不列出 |
| `SheetGrid.merges` | list[str] | 合併範圍，A1 範圍表示法（如 `G5:H5`） |

### Blank（填空格）＝ Question（題目）

依規格，題目與填空格一對一，所以合併成一個實體，以 `question_no` 識別。

| 欄位 | 型別 | 規則 |
|------|------|------|
| `question_no` | int | 系統題號，1..N 連續、不重複 |
| `location` | CellRef | 填空格位置（空白區段最左邊槽位的左上角） |
| `source_label` | str \| None | 學習單原始題號（題號儲存格的值） |
| `sub_label` | str \| None | 子題標籤，如「（1）」 |
| `group_no` | int \| None | 所屬題組編號；不屬於題組時為 None |

### QuestionGroup（題組）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `group_no` | int | 1..G，依出現順序編號 |
| `source_label` | str \| None | 學習單原始題號 |
| `question_nos` | list[int] | 至少 2 個，遞增且連續 |

### ParsedWorksheet（解析結果）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `questions` | list[Blank] | 長度 N ≥ 1 且 ≤ 題數上限 |
| `groups` | list[QuestionGroup] | 每個題號最多屬於一個題組 |

衍生值：`question_count = len(questions)`，`group_count = len(groups)`。

### Worksheet（已匯入的學習單，持久化）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `id` | UUID | 系統產生 |
| `owner` | str | 匯入的老師帳號識別 |
| `spreadsheet_id` | str | Google Sheets 試算表 ID，符合 `^[A-Za-z0-9_-]{20,100}$` |
| `spreadsheet_title` | str | 只用於顯示，長度 ≤ 255 |
| `structure_hash` | str | 填空格位置清單的雜湊（結構指紋，R5） |
| `status` | WorksheetStatus | 見狀態轉換 |
| `parsed` | ParsedWorksheet | 匯入時的解析結果 |
| `created_at` / `confirmed_at` | datetime | 伺服器時間 |

**狀態轉換**：`pending → confirmed`（老師確認）、`pending → cancelled`（老師取消）。
`confirmed` 與 `cancelled` 都是終止狀態。只有 `confirmed` 的學習單可以建立搶答活動（002）、寫回與匯出。

### ImportIssue（匯入驗證錯誤）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `code` | ImportErrorCode | 見下表 |
| `message` | str | 繁體中文，可直接顯示給使用者 |
| `sheet` | str \| None | 發生位置 |
| `cell` / `row` | str \| int \| None | 發生位置 |

| 代碼 | 情況（對應 FR-013） |
|------|------|
| `INVALID_SHEET_URL` | 輸入的不是 Google Sheets 網址或試算表 ID |
| `SHEET_NOT_FOUND` | 試算表不存在 |
| `SHEET_FORBIDDEN` | 目前登入的 Google 帳號沒有編輯權限（訊息包含該帳號 email，FR-025） |
| `GOOGLE_AUTH_EXPIRED` | Google 授權過期或被撤銷，需重新執行登入指令（FR-027） |
| `SHEETS_UNAVAILABLE` | Google 服務無法連線或逾時，可稍後重試 |
| `HEADER_NOT_FOUND` | 所有工作表都找不到表頭列 |
| `NO_QUESTION_ROWS` | 找不到任何題目列 |
| `NO_BLANK_IN_ROW` | 題目列沒有填空格 |
| `MULTIPLE_BLANKS_IN_ROW` | 題目列有兩段以上的空白區段 |
| `GROUP_RANGE_INCOMPLETE` | 題組合併範圍內有不是題目列的列 |
| `TOO_MANY_QUESTIONS` | 超過題數上限 |
| `STRUCTURE_CHANGED` | 寫回前重新讀取，發現填空格位置與匯入時不同（FR-019） |

### SubmissionRecord（搶答紀錄，由 002 產生、001 唯讀）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `activity_id` | UUID | 所屬活動 |
| `question_nos` | list[int] | 單一題目為 1 個；題組為該題組的全部題號 |
| `team_name` | str | 組別名稱 |
| `answers` | dict[int, str] | 題號 → 答案，鍵必須等於 `question_nos` |
| `rank` | int | 該搶答單位內的順位，≥ 1 |
| `outcome` | SubmissionOutcome | 每個搶答單位最多一筆 `success` |

### ActivityResult（活動結果，唯讀）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `activity_id` | UUID | |
| `worksheet_id` | UUID | 必須對應一份 `confirmed` 的 Worksheet |
| `owner` | str | 活動老師；必須等於學習單的 `owner` |
| `ended` | bool | 只有已結束的活動可以寫回或匯出 |
| `submissions` | list[SubmissionRecord] | |

### WritebackResult（寫回結果）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `filled` | list[int] | 已寫入答案的題號 |
| `unfilled` | list[int] | 沒有成功答案、維持空白的題號（FR-017） |
| `skipped_non_empty` | list[int] | 有成功答案，但雲端填空格已有內容而未覆蓋的題號（FR-026） |

## SQLite 資料表（storage 模組內部）

- `worksheets(id PK, owner, spreadsheet_id, spreadsheet_title, structure_hash, status, created_at, confirmed_at)`
- `questions(worksheet_id FK, question_no, sheet_id, sheet_title, cell, source_label, sub_label, group_no, PK(worksheet_id, question_no))`
- `question_groups(worksheet_id FK, group_no, source_label, PK(worksheet_id, group_no))`
- `writebacks(id PK, worksheet_id FK, activity_id, filled, unfilled, skipped_non_empty, created_at)`（寫回紀錄）

資料表只由 storage 模組存取，其他模組透過 repository 函式取得 domain 物件。
