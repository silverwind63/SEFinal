# HTTP API Contract: 線上分組搶答活動

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md) | **WebSocket**: [websocket.md](./websocket.md)

沿用 001 [http-api.md](../../001-guided-notes-import/contracts/http-api.md) 的以下規則：
Base URL、Bearer Token、統一錯誤格式、繁體中文訊息、不含堆疊追蹤、非擁有者回應 404。

- **老師 Token**：由 001 的 `POST /api/auth/teacher-login` 取得。
- **學生 Token**：由本文件的 `POST /api/join` 取得。
- **視窗 ID**：所有請求都附上 `X-Window-Id: <每個視窗產生一次的隨機值>`，用來計算加入時的輸錯次數（research R3）。

## 老師端（需要老師 Token）

### POST /api/activities（建立活動）

```json
{
  "worksheet_id": "<uuid>",
  "teams": ["第一組", "第二組", "第三組"],
  "fairness_enabled": true,
  "cooldown_seconds": 10,
  "cooldown_lead": 2
}
```

`fairness_enabled`、`cooldown_seconds`、`cooldown_lead` 都可以省略，省略時使用設定的預設值。

| 回應 | 內容 |
|------|------|
| 201 | `{"id", "phase": "preparing", "units": [BuzzUnit], "teams": [{"id", "name", "code"}], "fairness": {...}}`，組別代碼只出現在這裡和老師的 WebSocket 快照中 |
| 404 | 學習單不存在，或不屬於本人 |
| 409 | `INVALID_STATE`：學習單尚未確認；或 `ACTIVITY_IN_PROGRESS`：已有進行中的活動 |
| 422 | 組名為空、重複或過長；組數超過上限；N、K 超出範圍 |

### POST /api/activities/{id}/start、POST /api/activities/{id}/end

| 回應 | 內容 |
|------|------|
| 200 | `{"phase": "running"}` 或 `{"phase": "ended"}`；`end` 要等結果寫入資料庫後才回應 |
| 409 | `INVALID_STATE`：目前階段不允許這個操作 |
| 500 | `PERSIST_FAILED`：結果寫入失敗，活動維持搶答中，訊息為「結果保存失敗，活動仍在進行中，請再試一次」 |

### POST /api/activities/{id}/teams/{team_id}/regenerate-code

200：`{"team_id", "code"}`。舊代碼和以舊代碼加入的視窗立即失效。只有準備中或搶答中可以操作，否則回應 409。

### POST /api/activities/{id}/units/{unit_key}/invalidate

| 回應 | 內容 |
|------|------|
| 200 | `{"unit_key", "invalidated_team_id", "promoted_team_id": int\|null, "unit_status": "won"\|"open"\|"no_winner"}` |
| 409 | `INVALID_STATE`：這個單位目前沒有成功者，或活動處於準備中或已中斷 |
| 404 | 單位或活動不存在 |

### GET /api/activities/{id}（老師的完整檢視）

200：每個單位的所有送出（組別、答案、順位、結果）、各組成功數、各組冷卻狀態、組別代碼（只有活動未結束時才回傳）。

### GET /api/activities

200：本人的活動清單 `[{"id", "worksheet_id", "phase", "created_at", "ended_at"}]`。
001 的寫回與匯出用這份清單讓老師選擇活動。

## 學生端

### POST /api/join（不需要 Token）

| 回應 | 內容 |
|------|------|
| Request | `{"code": "<6 碼>"}`，比對時不分大小寫並去除空白 |
| 200 | `{"token", "activity_id", "team": {"id", "name"}, "phase"}` |
| 401 | `INVALID_CODE`：「組別代碼錯誤」，不透露任何組別或活動資訊 |
| 429 | `TOO_MANY_ATTEMPTS`：「嘗試次數過多，請於 N 秒後再試」 |
| 422 | 代碼格式不符，例如長度或字元不對 |

### POST /api/submissions（需要學生 Token）

```json
{ "unit_key": "G1", "answers": { "1": "CPU", "2": "作業系統" } }
```

| 回應 | 內容 |
|------|------|
| 200 | `{"unit_key", "rank", "outcome": "success"\|"not_won", "message": "搶答成功！" \| "未搶到，第 2 順位"}` |
| 409 | `NOT_RUNNING` / `ALREADY_SUBMITTED` |
| 409 | `COOLDOWN`：另附 `"retry_after_seconds"` |
| 401 | `UNAUTHORIZED`：Token 無效，或代碼已重新產生 |
| 404 | `UNKNOWN_UNIT` |
| 422 | `INCOMPLETE_GROUP`：另附 `"missing": [題號]` 與 `"unexpected": [題號]`；`INVALID_ANSWER`：另附題號與原因 |

客戶端送來的時間或結果欄位一律忽略；多出來的欄位回應 422。

### GET /api/me（需要學生 Token）

200：目前階段、本組資訊、本組所有送出與結果、本組冷卻狀態、單位清單（只有鍵值和顯示標示）。
**不包含**他組的任何資料，也不包含「哪些單位已被搶走」。

### GET /api/activities/{id}/results（需要老師 Token，或屬於這場活動的學生 Token）

- 活動已結束時回應 200：每個單位的成功組別與成功答案，或「無人搶答」，以及各組成功數；
  老師另外看得到所有送出與順位。
- 活動未結束時回應 409 `NOT_ENDED`，學生和老師都一樣。

## 公開端點

### GET /api/activities/{id}/phase

200：`{"phase": "..."}`；活動不存在時回應 404。不需要 Token，不含任何其他資料。
重啟後前端用這個端點判斷活動是否「已中斷」（research R7）。
