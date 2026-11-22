# Internal Contract: ActivityResultsProvider（001 ↔ 002）

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

001 的寫回與匯出透過這個唯讀介面取得搶答結果。介面與它用到的資料結構
（`ActivityResult`、`SubmissionRecord`、`SubmissionOutcome`）只定義在 `src/guided_buzz/domain/`，
002 引用並實作，不重複宣告。

## 介面

```text
ActivityResultsProvider
  get_result(activity_id: UUID, requester: str) -> ActivityResult
    - 活動不存在，或 requester 不是活動老師 → 拋出 NotFound
    - 回傳的 submissions 依 (question_nos[0], rank) 排序
```

## 實作提供者

| 實作 | 擁有者 | 用途 |
|------|--------|------|
| `JsonFileResultsProvider` | 001 | 從 JSON 結果檔讀取，供測試與 002 完成前的手動驗證使用 |
| 002 的 SQLite 實作 | 002 | 正式版本，讀取已保存的已結束活動 |

## JsonFileResultsProvider 的位置規則

設定 `GB_RESULTS_DIR` 時才會啟用。系統讀取 `<GB_RESULTS_DIR>/<activity_id>.json`，
`activity_id` 必須是合法的 UUID，才能組成檔案路徑，以防止路徑穿越。
002 完成後改用正式實作，這個提供者只保留給測試使用。

## JSON 結果檔格式（JsonFileResultsProvider）

```json
{
  "activity_id": "11111111-1111-1111-1111-111111111111",
  "worksheet_id": "<匯入後取得的 id>",
  "owner": "teacher",
  "ended": true,
  "submissions": [
    {"question_nos": [1, 2], "team_name": "第一組", "answers": {"1": "CPU", "2": "作業系統"}, "rank": 1, "outcome": "success"},
    {"question_nos": [5], "team_name": "第二組", "answers": {"5": "0"}, "rank": 1, "outcome": "invalidated"},
    {"question_nos": [5], "team_name": "第三組", "answers": {"5": "0"}, "rank": 2, "outcome": "success"}
  ]
}
```

載入時以與 API 相同的規則驗證（`answers` 的鍵必須等於 `question_nos`；每個搶答單位最多一筆 `success`；
題號必須存在於學習單中）。不符合時以繁體中文指出是第幾筆紀錄出錯。
