# Data Model: 線上分組搶答活動

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Diagrams**: [diagrams.md](./diagrams.md)

本功能沿用 001 的共用資料結構，例如 `Blank`、`QuestionGroup`、`ParsedWorksheet`、`SubmissionRecord`、
`ActivityResult`、`SubmissionOutcome`（見 [001 data-model](../001-guided-notes-import/data-model.md)）。
新增的共用結構同樣只定義在 `src/guided_buzz/domain/models.py`。
只在判定引擎內部使用的狀態（如 `TeamState`、`UnitState`）定義在 `src/guided_buzz/activity/state.py`，不給其他模組使用。

## 共用列舉（新增）

| 名稱 | 值 | 說明 |
|------|----|------|
| `ActivityPhase` | `preparing` / `running` / `ended` / `interrupted` | 活動階段 |
| `SubmissionRejectCode` | `NOT_RUNNING` / `UNAUTHORIZED` / `COOLDOWN` / `UNKNOWN_UNIT` / `INCOMPLETE_GROUP` / `INVALID_ANSWER` / `ALREADY_SUBMITTED` | 送出被拒的原因 |

## 實體

### BuzzUnit（搶答單位，共用）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `key` | str | 題組為 `G<group_no>`，單一題目為 `Q<question_no>`；在同一場活動中不重複 |
| `question_nos` | list[int] | 單一題目時只有 1 個；題組時等於 `QuestionGroup.question_nos` |
| `display` | str | 顯示用的題號標示（R4），不含題目敘述 |

依 `ParsedWorksheet` 產生，排序依 `question_nos[0]` 遞增。

### Activity（搶答活動）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `id` | UUID | 系統產生 |
| `worksheet_id` | UUID | 必須是一份 `confirmed` 的 Worksheet，且擁有者與活動老師相同 |
| `owner` | str | 建立活動的老師 |
| `phase` | ActivityPhase | 見下方狀態轉換 |
| `fairness_enabled` | bool | 預設 `GB_FAIRNESS_ENABLED` |
| `cooldown_seconds` | int | N，1..600，預設 `GB_COOLDOWN_SECONDS` |
| `cooldown_lead` | int | K，1..100，預設 `GB_COOLDOWN_LEAD` |
| `created_at` / `started_at` / `ended_at` | datetime \| None | 伺服器的 UTC 時間 |

**狀態轉換**：

| 從 | 到 | 觸發 | 條件 |
|----|----|------|------|
| preparing | running | 老師按「開始搶答」 | 至少 1 個搶答單位、至少 1 個組別 |
| running | ended | 老師按「結束搶答」 | 結果寫入資料庫成功後才轉換 |
| preparing / running | interrupted | 伺服器啟動時 | 自動 |

其他轉換一律拒絕，回應 `INVALID_STATE`。`ended` 與 `interrupted` 是終止狀態。

**唯一性**：同一時間最多只有一場活動處於 `preparing` 或 `running`。

### Team（組別）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `id` | int | 同一場活動內為 1..T |
| `activity_id` | UUID | |
| `name` | str | 去除前後空白後長度 1..`GB_TEAM_NAME_MAX`；同一場活動內不重複 |
| `code` | str | 6 碼，字元集為 `23456789ABCDEFGHJKLMNPQRSTUVWXYZ`（去除易混淆字元）；**只存在記憶體** |
| `code_hash` | str | SHA-256，存入資料庫 |
| `code_version` | int | 從 1 開始，每重新產生一次加 1 |

組數為 1..`GB_MAX_TEAMS`。

### Session（視窗身分，只存在記憶體）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `token` | str | `secrets.token_urlsafe(32)`，不寫入 log |
| `role` | `teacher` \| `team` | |
| `activity_id` / `team_id` / `code_version` | | 只有 `team` 角色有；`code_version` 不等於組別目前的版本時，Token 失效 |

### Submission（送出紀錄）

即 001 的 `SubmissionRecord`。002 在引擎內部多記錄以下欄位：

| 欄位 | 型別 | 規則 |
|------|------|------|
| `id` | int | 同一場活動內遞增 |
| `unit_key` | str | 對應 `BuzzUnit.key` |
| `team_id` | int | |
| `answers` | dict[int, str] | 鍵的集合必須等於該單位的 `question_nos`；每個值去除前後空白後長度為 1..`GB_MAX_ANSWER_LENGTH` |
| `rank` | int | 同一單位內為 1..n，連續且不重複 |
| `outcome` | SubmissionOutcome | 同一單位在任何時刻最多只有一筆 `success` |
| `received_at` | datetime | 伺服器的 UTC 時間 |
| `invalidated_at` | datetime \| None | |

**唯一性**：（`unit_key`, `team_id`）不重複，也就是每組對每個單位只能送出一次。

### Cooldown（冷卻狀態，只存在記憶體）

| 欄位 | 型別 | 規則 |
|------|------|------|
| `team_id` | int | 每組同時最多只有一筆 |
| `until_monotonic` | float | 冷卻結束的時間點 |
| `until_utc` | datetime | 供畫面顯示 |
| `trigger_submission_id` | int | 觸發冷卻的那筆成功送出；這筆被判無效時，冷卻立即解除 |

### 衍生值

- **單位狀態**：有 `success` 的送出時為「已搶答」；沒有任何送出時為「尚無人搶答」；
  有送出但沒有 `success` 時，搶答中為「開放中（成功者已被判無效）」，已結束為「無人搶答」。
- **組別成功數**：該組 `outcome=success` 的送出筆數（一個題組算 1）。

## SQLite 資料表（新增）

- `activities(id PK, worksheet_id FK, owner, phase, fairness_enabled, cooldown_seconds, cooldown_lead, created_at, started_at, ended_at)`
- `teams(activity_id FK, team_id, name, code_hash, code_version, PK(activity_id, team_id), UNIQUE(activity_id, name))`
- `submissions(activity_id FK, id, unit_key, team_id, rank, outcome, received_at, invalidated_at, PK(activity_id, id), UNIQUE(activity_id, unit_key, team_id), UNIQUE(activity_id, unit_key, rank))`
- `submission_answers(activity_id, submission_id, question_no, answer, PK(activity_id, submission_id, question_no))`

`submissions` 與 `submission_answers` 只在活動結束時寫入（research R7），以及之後判定無效時更新。
