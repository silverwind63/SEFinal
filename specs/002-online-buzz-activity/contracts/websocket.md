# WebSocket Contract: 即時同步

**Feature**: [../spec.md](../spec.md) | **HTTP**: [http-api.md](./http-api.md)

- 端點：`ws://127.0.0.1:<GB_PORT>/ws`
- 所有訊息都是 JSON：`{"type": "...", ...}`
- 伺服器只推送狀態；所有操作都走 HTTP API，所以 WebSocket 上沒有任何會改變狀態的指令。

## 連線流程

1. 客戶端連線後，5 秒內必須送出第一則訊息 `{"type": "auth", "token": "<老師或學生 Token>"}`。
   逾時或 Token 無效時，伺服器以關閉代碼 4401 斷線。
2. 驗證成功後，伺服器立即送出 `snapshot`（完整的目前狀態），之後只推送增量事件。
3. 每次重新連線都從第 1 步重來，所以會重新收到完整快照。

## 伺服器 → 客戶端訊息

| type | 對象 | 內容 |
|------|------|------|
| `snapshot` | 老師 | 階段、單位清單、所有送出、各組成功數、冷卻狀態、組別代碼（活動未結束時） |
| `snapshot` | 學生 | 階段、單位清單（只有鍵值和顯示標示）、**本組**的送出與結果、本組冷卻狀態；活動結束後另含完整結果 |
| `phase_changed` | 所有人 | `{"phase"}`；切換為 `ended` 時，緊接著再送一次 `snapshot` |
| `submission` | 老師 | `{"unit_key", "team_id", "answers", "rank", "outcome"}` |
| `team_submission` | 送出組的所有視窗 | `{"unit_key", "rank", "outcome"}`，同組的其他視窗也能看到 |
| `cooldown` | 該組、老師 | `{"team_id", "active", "remaining_seconds"}` |
| `invalidated` | 被判無效的組、老師 | `{"unit_key", "message": "第 X 題的答案已被老師判定無效"}` |
| `promoted` | 遞補成功的組、老師 | `{"unit_key", "message": "第 X 題遞補為搶答成功"}` |
| `session_revoked` | 被撤銷的視窗 | `{"reason": "code_regenerated"}`，送出後以關閉代碼 4403 斷線 |

**權限規則**：伺服器依連線的身分分別產生上述訊息。學生連線在活動結束前，絕對不會收到含有他組 `team_id`、答案、順位，
或任何單位是否已被搶走的訊息（FR-014）。這條規則有專門的整合測試驗證。
