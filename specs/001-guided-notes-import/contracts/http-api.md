# HTTP API Contract: 學習單匯入、寫回與匯出

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

- Base URL：`http://127.0.0.1:<GB_PORT>`（只監聽本機）
- 所有 `/api/worksheets*` 與 `/api/activities*` 端點都需要老師 Token：`Authorization: Bearer <token>`。
  沒有 Token 或 Token 無效時回應 401；Token 有效但不是該資源的擁有者時回應 404（不透露資源是否存在）。
- 錯誤回應的統一格式：

```json
{
  "error": {
    "code": "MULTIPLE_BLANKS_IN_ROW",
    "message": "工作表「學習單」第 7 列有 2 個空白作答區，每個題目列只能有一個填空格。",
    "issues": [
      { "code": "MULTIPLE_BLANKS_IN_ROW", "message": "…", "sheet": "學習單", "row": 7, "cell": null }
    ]
  }
}
```

`message` 一律為繁體中文；`issues` 列出所有驗證問題（R3 第 9 點）。回應中不包含堆疊追蹤或系統內部資訊。

---

## POST /api/auth/teacher-login

| 項目 | 內容 |
|------|------|
| Request | `{"password": "<string, 1..128>"}` |
| 200 | `{"token": "<opaque>", "expires_in": <秒>}` |
| 401 | `INVALID_CREDENTIALS`：「密碼錯誤」 |
| 422 | `VALIDATION_ERROR`：欄位缺漏或長度不符 |

連續多次密碼錯誤時暫時限制登入，次數與時間可設定（429 `LOGIN_LOCKED`，訊息含剩餘秒數）。密碼不寫入 log。

## GET /api/auth/session

| 項目 | 內容 |
|------|------|
| 200 | `{"owner": "teacher"}`，Token 有效 |
| 401 | `UNAUTHORIZED`：沒有 Token、Token 無效或已過期 |

前端在重新整理頁面時用來確認 sessionStorage 中的 Token 是否仍有效。

## POST /api/worksheets（匯入並預覽）

| 項目 | 內容 |
|------|------|
| Request | `{"spreadsheet_url": "<Google Sheets 網址或試算表 ID，1..2048 字元>"}` |
| 201 | 預覽，狀態為 `pending`（見下方） |
| 403 | `SHEET_FORBIDDEN`：「目前登入的 Google 帳號（<email>）沒有這份試算表的編輯權限，請改用有權限的帳號重新登入，或請擁有者把試算表共用給這個帳號（編輯者）。」 |
| 404 | `SHEET_NOT_FOUND`：試算表不存在 |
| 422 | `INVALID_SHEET_URL` / `HEADER_NOT_FOUND` / `NO_QUESTION_ROWS` / `NO_BLANK_IN_ROW` / `MULTIPLE_BLANKS_IN_ROW` / `GROUP_RANGE_INCOMPLETE` / `TOO_MANY_QUESTIONS` |
| 503 | `SHEETS_UNAVAILABLE`：Google 服務無法連線或逾時，請稍後再試 |
| 503 | `GOOGLE_AUTH_EXPIRED`：Google 授權已失效，訊息包含重新登入的指令 |

系統直接從雲端讀取試算表，不接受檔案上傳（助教 11/17 補充公告）。

201 回應範例（範例 B 的節錄）：

```json
{
  "id": "6f1c…",
  "status": "pending",
  "spreadsheet_id": "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg",
  "spreadsheet_title": "計概學習單",
  "question_count": 6,
  "group_count": 2,
  "questions": [
    {"question_no": 1, "sheet": "學習單", "cell": "H5", "source_label": "1", "sub_label": "（1）", "group_no": 1},
    {"question_no": 2, "sheet": "學習單", "cell": "H6", "source_label": "1", "sub_label": "（2）", "group_no": 1},
    {"question_no": 5, "sheet": "學習單", "cell": "G11", "source_label": "3", "sub_label": null, "group_no": null}
  ],
  "groups": [
    {"group_no": 1, "source_label": "1", "question_nos": [1, 2]},
    {"group_no": 2, "source_label": "2", "question_nos": [3, 4]}
  ]
}
```

回應中不包含題目敘述文字（FR-007）。

## POST /api/worksheets/{id}/confirm

| 項目 | 內容 |
|------|------|
| 200 | 與預覽格式相同，`status: "confirmed"` |
| 409 | `INVALID_STATE`：學習單不是 `pending`（已確認或已取消） |

## POST /api/worksheets/{id}/cancel

| 項目 | 內容 |
|------|------|
| 200 | `{"id": "…", "status": "cancelled"}` |
| 409 | `INVALID_STATE` |

## GET /api/worksheets/{id}

200：與預覽格式相同。

## GET /api/worksheets

200：`[{"id", "spreadsheet_title", "status", "question_count", "group_count", "created_at"}]`，只列出本人擁有的學習單。

## POST /api/worksheets/{id}/writeback

| 項目 | 內容 |
|------|------|
| Request | `{"activity_id": "<uuid>"}` |
| 200 | `{"filled": [1,2,5], "unfilled": [3,4,6], "skipped_non_empty": []}`；答案已直接寫入原本的 Google Sheets |
| 409 | `INVALID_STATE`：學習單未確認，或活動尚未結束 |
| 409 | `STRUCTURE_CHANGED`：重新讀取後，填空格位置與匯入時不同（FR-019），訊息說明差異 |
| 404 | `NOT_FOUND`：活動不存在、不屬於本人，或不屬於這份學習單 |
| 403 | `SHEET_FORBIDDEN`：登入的帳號已沒有這份試算表的編輯權限 |
| 503 | `GOOGLE_AUTH_EXPIRED`：Google 授權已失效，需重新登入 |
| 503 | `SHEETS_UNAVAILABLE`：Google 服務無法連線或逾時，可稍後重試 |

只寫入「有成功答案且目前仍為空白」的填空格；已有內容的填空格不覆蓋，列在 `skipped_non_empty`（FR-026）。

## GET /api/activities/{activity_id}/results.csv

| 項目 | 內容 |
|------|------|
| 200 | `text/csv; charset=utf-8`，內容以 UTF-8 BOM 開頭，CRLF 換行 |
| 409 | `INVALID_STATE`：活動尚未結束 |
| 404 | `NOT_FOUND` |

CSV 欄位：`題號,組別,答案,搶答順位,結果`（第 5 欄見 spec.md FR-020、research R7）。
沒有任何紀錄時只輸出標題列，並以回應標頭 `X-Record-Count: 0` 讓前端顯示「目前無紀錄」。
