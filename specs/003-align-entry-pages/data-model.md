# Data Model: 入口頁與老師頁面對齊 OpenSpec 組

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

本功能**沒有新增資料表，也沒有新增實體**。資料庫結構完全不變。只有兩處變更：

1. 伺服器回傳的 `WorksheetSummary` 多一個欄位。
2. 前端兩個頁面各自保存的「視窗狀態」。

## 1. WorksheetSummary（001 `api/schemas.py`，新增一個欄位）

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | str | 不變 |
| spreadsheet_title | str | 不變 |
| status | str | 不變（`pending`、`confirmed`、`cancelled`） |
| question_count | int | 不變 |
| group_count | int | 不變 |
| created_at | str（ISO 8601） | 不變（匯入時間） |
| **confirmed_at** | str（ISO 8601）或 `null` | **新增**。資料來源是 `Worksheet.confirmed_at`；尚未確認或已取消時為 `null` |

驗證規則：
- 只新增欄位，不改變既有欄位。
- 狀態為 `confirmed` 時，`confirmed_at` 必定有值，因為 001 在確認時就會寫入。

## 2. 視窗狀態（前端，存在各視窗的 sessionStorage，鍵名沿用 001、002）

### 學生頁 `/`（`student.js`）

| 鍵 | 內容 | 何時寫入 | 何時清除 |
|----|------|---------|---------|
| `guided_buzz_window_id` | 視窗 ID（計算輸錯次數用） | 第一次送出請求時 | 不清除 |
| `guided_buzz_student_token` | 學生身分 | 加入成功 | 身分失效（`leave()`） |
| `guided_buzz_student_activity` | 加入的活動 ID | 加入成功 | 不清除，用來判斷活動是否已中斷 |

畫面狀態（[狀態圖](../../diagrams/003-align-entry-pages/05-state-window.puml)）：

```text
確認身分（重新整理時）─有效→ 作答畫面
        └─無效→ 加入組別（顯示提示）
加入組別 ─代碼正確→ 作答畫面 ─代碼重新產生／活動中斷→ 加入組別（顯示提示）
```

### 老師頁 `/teacher`（`teacher.js`）

| 鍵／變數 | 內容 | 說明 |
|----------|------|------|
| `guided_buzz_teacher_token` | 老師身分 | 登入時寫入；登出或伺服器回 401 時清除 |
| `guided_buzz_teacher_activity` | 正在檢視的活動 ID | 建立或檢視活動時寫入；重新整理後用它找回同一場 |
| `current`（記憶體） | 正在檢視的活動資料（002 老師檢視資料，含 `worksheet_id`） | 寫回與下載 CSV 直接使用 `current.id`、`current.worksheet_id` |
| `worksheets`（記憶體） | 學習單清單（`WorksheetSummary[]`） | 用來顯示已確認清單和建立活動的選單，也用來對照活動清單中的學習單名稱 |

「目前活動」區塊的顯示規則（research R7、R8）：

| `current` | 顯示內容 |
|-----------|---------|
| 沒有 | 「目前沒有活動」說明 |
| `preparing`、`running` | 主控台（開始、結束、組別、作答狀況、判定無效），不顯示寫回與下載 |
| `ended` | 主控台（唯讀部分，以及判定無效）＋「寫回答案」「下載 CSV」 |
| 檢視到 `interrupted` | 不會成為 `current`；只顯示伺服器的錯誤訊息 |

## 3. 不變的資料

以下全部沿用 001、002，本功能不修改：
- 學習單（`worksheets`、`questions`、`question_groups`）、寫回紀錄（`writebacks`）
- 活動（`activities`、`teams`、`submissions`、`submission_answers`）
- 老師與學生的 Session、WebSocket 訊息格式
