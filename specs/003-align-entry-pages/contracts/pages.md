# Page Contract: 頁面網址與畫面結構

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md)

這份合約定義使用者看得到的網址，以及每一頁必須有哪些元素。自動化測試（`tests/integration/test_pages.py`）與人工驗證都以本文件為準。

## 網址

| 方法與路徑 | 回應 | 說明 |
|-----------|------|------|
| `GET /` | 200，`text/html`，學生頁（`web/static/student.html`） | FR-001 |
| `GET /teacher` | 200，`text/html`，老師頁（`web/static/teacher.html`） | FR-007 |
| `GET /student.html` | 307，`Location: /` | FR-025 |
| `GET /teacher.html` | 307，`Location: /teacher` | FR-025 |
| `GET /index.html`、`GET /app.js` | 404 | 舊的老師入口已刪除（research R3） |
| `GET /student.js`、`/teacher.js`、`/style.css` | 200 | 靜態檔，不變 |

- 以上頁面路由都不需要登入；身分由頁面載入後的程式自行檢查。
- `/api/` 以外的回應（頁面、JS、CSS、導向）都帶 `Cache-Control: no-cache`：瀏覽器每次都要先向伺服器確認，檔案沒有變更時回 304。這樣程式更新後，不會出現新後端配舊畫面（2026-11-28 新增）。
- 頁面路由不出現在 OpenAPI 文件中（`include_in_schema=False`）。

## 學生頁 `/`

| 元素 | 要求 |
|------|------|
| 載入的程式 | 只有 `/student.js`（FR-026） |
| 「加入組別」區塊 | 標題「加入組別」；說明「每個瀏覽器視窗各自保有自己的身分，可以在不同視窗分別開啟老師與各組畫面。」；組別代碼欄位 |
| 按鈕 | 「加入」（送出表單）與「我是老師」（連結到 `/teacher`）並排 |
| 不可出現 | 密碼欄位（`type="password"`）、任何老師功能 |
| 加入後 | 隱藏「加入組別」區塊（含「我是老師」），顯示原學生作答畫面，網址不變 |

## 老師頁 `/teacher`

| 元素 | 要求 |
|------|------|
| 載入的程式 | 只有 `/teacher.js`（FR-026） |
| 頁首 | 標題，以及只在登入後出現的「登出」按鈕；沒有任何指向其他頁面的 `<a href>`（FR-008） |
| 未登入 | 只顯示「老師登入」：密碼欄、「登入」按鈕 |
| 登入後，由上而下依序顯示 | ① 匯入學習單 ② 已確認的學習單 ③ 建立搶答活動 ④ 目前活動 ⑤ 活動清單（FR-009） |
| ② 已確認的學習單 | 表格欄位：編號、試算表、題數、題組數、確認時間 |
| ④ 目前活動 | 學習單名稱、活動建立時間、活動編號（2026-11-28 補上前兩項，方便分辨同一份學習單的多場活動）；階段、開始搶答、結束搶答；組別表（組別、組別代碼、成功題數、冷卻、重新產生代碼）；作答狀況、判定無效。活動已結束時多出「寫回答案」「下載 CSV」 |
| ⑤ 活動清單 | 表格欄位：編號、學習單、階段、建立時間、結束時間、「檢視」按鈕；目前活動那一列以底色標示，按鈕文字為「目前檢視中」 |
| 被移除的區塊 | 原本的「寫回答案與匯出結果」（已結束活動選單、學習單 ID、活動 ID 輸入框）、「學生請開啟 /student.html…」提示（FR-020） |

## 使用的既有 API（行為不變）

| 頁面 | API |
|------|-----|
| 學生頁 | `POST /api/join`、`GET /api/me`、`POST /api/submissions`、`GET /api/activities/{id}/phase`、`/ws` |
| 老師頁 | `POST /api/auth/teacher-login`、`GET /api/auth/session`、`POST /api/worksheets`、`POST /api/worksheets/{id}/confirm`、`POST /api/worksheets/{id}/cancel`、`GET /api/worksheets`、`POST /api/activities`、`GET /api/activities`、`GET /api/activities/{id}`、`POST /api/activities/{id}/start`、`POST /api/activities/{id}/end`、`POST /api/activities/{id}/teams/{team_id}/regenerate-code`、`POST /api/activities/{id}/units/{unit_key}/invalidate`、`POST /api/worksheets/{id}/writeback`、`GET /api/activities/{id}/results.csv`、`/ws` |

唯一的 API 變更見 [api-changes.md](./api-changes.md)。
