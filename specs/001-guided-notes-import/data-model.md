# Data Model: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Diagrams**: [diagrams.md](./diagrams.md)

所有跨模組共用的資料結構**只在** `src/guided_buzz/domain/models.py` 定義一次（Constitution 原則 V），
其他模組（parser、writeback、export、storage、api）與 002 一律從那裡引用。
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
| `sheet` | str | 工作表名稱，非空 |
| `cell` | str | A1 表示法，符合 `^[A-Z]{1,3}[1-9][0-9]*$` |

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
| `original_filename` | str | 只用於顯示，長度 ≤ 255，不用於檔案路徑 |
| `stored_path` | 相對路徑 | `uploads/<id>.xlsx`，相對於 `GB_DATA_DIR` |
| `sha256` | str | 原始檔雜湊（R5） |
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
| `FILE_TOO_LARGE` | 超過檔案大小上限 |
| `FILE_EMPTY` | 空檔案 |
| `NOT_XLSX` | 不是 .xlsx，或檔案已損毀無法讀取 |
| `HEADER_NOT_FOUND` | 所有工作表都找不到表頭列 |
| `NO_QUESTION_ROWS` | 找不到任何題目列 |
| `NO_BLANK_IN_ROW` | 題目列沒有填空格 |
| `MULTIPLE_BLANKS_IN_ROW` | 題目列有兩段以上的空白區段 |
| `GROUP_RANGE_INCOMPLETE` | 題組合併範圍內有不是題目列的列 |
| `TOO_MANY_QUESTIONS` | 超過題數上限 |
| `STRUCTURE_CHANGED` | 寫回前發現原始檔雜湊或填空格位置已改變（FR-019） |

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
| `file_id` | UUID | 產生的新檔案，存於 `writebacks/<file_id>.xlsx` |
| `filled` | list[int] | 已填入答案的題號 |
| `unfilled` | list[int] | 沒有成功答案、維持空白的題號（FR-017） |

## SQLite 資料表（storage 模組內部）

- `worksheets(id PK, owner, original_filename, stored_path, sha256, status, created_at, confirmed_at)`
- `questions(worksheet_id FK, question_no, sheet, cell, source_label, sub_label, group_no, PK(worksheet_id, question_no))`
- `question_groups(worksheet_id FK, group_no, source_label, PK(worksheet_id, group_no))`
- `writebacks(file_id PK, worksheet_id FK, activity_id, created_at)`

資料表只由 storage 模組存取，其他模組透過 repository 函式取得 domain 物件。
