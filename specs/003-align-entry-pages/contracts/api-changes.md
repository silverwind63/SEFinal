# API Changes: 相對 001、002 的變更

**Feature**: [../spec.md](../spec.md)（FR-027） | **Data model**: [../data-model.md](../data-model.md)

除了新增頁面路由（見 [pages.md](./pages.md)），只有下面一項 API 變更，而且是**向下相容的新增欄位**。

## `GET /api/worksheets`：每筆多一個 `confirmed_at`

對照：[001 contracts/http-api.md](../../001-guided-notes-import/contracts/http-api.md) 的學習單清單。

```json
[
  {
    "id": "d33beb47-…",
    "spreadsheet_title": "範例B_搶答驗證",
    "status": "confirmed",
    "question_count": 6,
    "group_count": 2,
    "created_at": "2026-11-27T13:11:20+00:00",
    "confirmed_at": "2026-11-27T13:11:26+00:00"
  },
  {
    "id": "a4d25a51-…",
    "spreadsheet_title": "軟工期末專案_題組_範例B",
    "status": "pending",
    "question_count": 6,
    "group_count": 2,
    "created_at": "2026-11-22T15:20:58+00:00",
    "confirmed_at": null
  }
]
```

| 項目 | 規則 |
|------|------|
| 權限 | 不變（需要老師 Token，只列出本人的學習單） |
| `confirmed_at` | 狀態為 `confirmed` 時是 ISO 8601 字串；`pending`、`cancelled` 時為 `null` |
| 既有欄位 | 名稱、型別、意義都不變 |
| 錯誤 | 不變 |

## 確認沒有變更的部分

- 其他所有 HTTP API 的路徑、請求、回應、狀態碼與錯誤代碼。
- WebSocket `/ws` 的驗證方式與所有訊息格式。
- 判定、冷卻、權限檢查與資料庫結構。
