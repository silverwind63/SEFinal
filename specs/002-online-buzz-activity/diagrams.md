# Diagrams: 線上分組搶答活動

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **API**: [contracts/](./contracts/)

依 Constitution 原則 VII，以下圖表須在實作前審閱。圖中「🔒」標示伺服器的權限檢查點，「⚖」標示伺服器的判定點。

## 1. 循序圖：建立活動、學生加入、開始搶答（US1）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師視窗
    actor S as 學生視窗（第一組）
    participant API as HTTP API
    participant ENG as ActivityEngine（鎖）
    participant HUB as 推播中心
    participant DB as SQLite
    T->>API: POST /api/activities {worksheet_id, teams}
    API->>API: 🔒 老師 Token、擁有學習單、學習單已確認
    API->>ENG: 建立（沒有其他進行中的活動）
    ENG->>DB: activities(preparing)、teams(code_hash)
    API-->>T: 201 單位清單、組別代碼
    T-->>S: 課堂上私下告知第一組的代碼
    S->>API: POST /api/join {code}＋X-Window-Id
    API->>API: 🔒 此視窗與全體的輸錯次數
    alt 代碼錯誤
        API-->>S: 401／達上限時 429
    else 正確
        API-->>S: 200 學生 Token（存入 sessionStorage）
    end
    S->>HUB: WS 連線，第一則訊息送 Token
    HUB->>HUB: 🔒 驗證 Token
    HUB-->>S: snapshot（只含本組資料）
    T->>API: POST /start
    API->>ENG: ⚖ 在鎖內 preparing→running
    ENG->>DB: phase=running
    ENG-->>HUB: phase_changed
    HUB-->>T: phase_changed（2 秒內）
    HUB-->>S: phase_changed（2 秒內）
```

## 2. 循序圖：同時送出與公平機制（US2、US5）

```mermaid
sequenceDiagram
    autonumber
    actor A as 第一組
    actor B as 第二組
    participant API as HTTP API
    participant ENG as ActivityEngine（鎖）
    participant HUB as 推播中心
    par 幾乎同時送出
        A->>API: POST /api/submissions {unit: Q5}
    and
        B->>API: POST /api/submissions {unit: Q5}
    end
    API->>API: 🔒 驗證學生 Token 與代碼版本
    API->>ENG: submit(第一組)（先取得鎖）
    ENG->>ENG: ⚖ 階段 → 冷卻 → 單位 → 答案 → 是否已送出
    ENG->>ENG: ⚖ 順位 1，Q5 沒有成功者 → success
    ENG->>ENG: ⚖ 成功數 − 最少成功數 ≥ K？→ 第一組冷卻 N 秒
    ENG-->>API: success, rank 1
    API->>ENG: submit(第二組)（後取得鎖）
    ENG->>ENG: ⚖ 順位 2，Q5 已有成功者 → not_won
    ENG-->>API: not_won, rank 2
    API-->>A: 200 搶答成功！
    API-->>B: 200 未搶到，第 2 順位
    ENG-->>HUB: 事件（鎖釋放後）
    HUB-->>A: team_submission、cooldown（只給第一組）
    HUB-->>B: team_submission（只給第二組）
    Note over HUB: 老師收到兩筆 submission 與 cooldown
    A->>API: 冷卻中送出 Q6
    API->>ENG: submit
    ENG-->>API: ⚖ COOLDOWN（不記錄、不佔順位）
    API-->>A: 409 冷卻中，剩餘 7 秒
```

## 3. 循序圖：判定無效與遞補（US3）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師
    participant API as HTTP API
    participant ENG as ActivityEngine（鎖）
    participant DB as SQLite
    participant HUB as 推播中心
    T->>API: POST /units/Q3/invalidate
    API->>API: 🔒 老師 Token、擁有這場活動
    API->>ENG: invalidate(Q3)
    ENG->>ENG: ⚖ 第一組 success → invalidated
    ENG->>ENG: ⚖ 依順位找下一筆 not_won → 第二組 success
    ENG->>ENG: 若第一組正因這次成功冷卻 → 解除；遞補不觸發冷卻
    alt 活動已結束
        ENG->>DB: 一筆交易更新兩筆送出的結果
    end
    alt 沒有下一順位
        ENG->>ENG: 搶答中 → Q3 重新開放；已結束 → 無人搶答
    end
    ENG-->>HUB: invalidated、promoted
    HUB-->>T: 更新後的檢視
    Note over HUB: 第一組收到「已被判定無效」，第二組收到「遞補成功」，都不含他組答案
```

## 4. 循序圖：結束搶答與重啟（US1、FR-026、FR-027）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師
    participant API as HTTP API
    participant ENG as ActivityEngine（鎖）
    participant DB as SQLite
    participant HUB as 推播中心
    T->>API: POST /end
    API->>ENG: end()
    ENG->>DB: 一筆交易寫入所有送出、答案，並設 phase=ended
    alt 寫入失敗
        ENG-->>API: PERSIST_FAILED（維持 running）
        API-->>T: 500 結果保存失敗，請再試一次
    else 成功
        ENG->>ENG: 記憶體中的階段改為 ended
        ENG-->>HUB: phase_changed、snapshot（含完整結果）
        API-->>T: 200 ended
    end
    Note over DB: 伺服器重啟時：preparing、running 的活動改為 interrupted
    actor S as 學生視窗（重新整理）
    S->>API: GET /api/activities/{id}/phase
    API-->>S: interrupted → 顯示「活動已中斷，請老師重新建立」
```

## 5. 狀態圖：活動階段

```mermaid
stateDiagram-v2
    [*] --> preparing : 老師建立活動
    preparing --> running : 老師開始（至少 1 組、1 個單位）
    running --> ended : 老師結束（結果寫入資料庫成功）
    preparing --> interrupted : 伺服器重啟
    running --> interrupted : 伺服器重啟
    ended --> [*]
    interrupted --> [*]
```

## 6. 狀態圖：搶答單位

```mermaid
stateDiagram-v2
    [*] --> 尚無人搶答
    尚無人搶答 --> 已搶答 : 第一筆合法送出
    已搶答 --> 已搶答 : 後續送出（not_won，順位遞增）
    已搶答 --> 已搶答 : 判定無效且有下一順位（遞補）
    已搶答 --> 開放中 : 判定無效且沒有下一順位（搶答中）
    已搶答 --> 無人搶答 : 判定無效且沒有下一順位（已結束）
    開放中 --> 已搶答 : 下一筆合法送出（被判無效的組不能再送）
    尚無人搶答 --> 無人搶答 : 活動結束
    開放中 --> 無人搶答 : 活動結束
```

## 7. 狀態圖：組別冷卻

```mermaid
stateDiagram-v2
    [*] --> 可送出
    可送出 --> 冷卻中 : 即時送出成功，且成功數 − 最少成功數 ≥ K（公平機制啟用時）
    冷卻中 --> 可送出 : 經過 N 秒（伺服器 monotonic 時鐘）
    冷卻中 --> 可送出 : 觸發冷卻的那筆成功被判定無效
    冷卻中 --> 冷卻中 : 送出被拒（不記錄、不佔順位）
```

## 8. 類別圖

```mermaid
classDiagram
    class Activity {
        +UUID id
        +UUID worksheet_id
        +str owner
        +ActivityPhase phase
        +bool fairness_enabled
        +int cooldown_seconds
        +int cooldown_lead
    }
    class Team {
        +int id
        +str name
        +str code_hash
        +int code_version
    }
    class BuzzUnit {
        +str key
        +list~int~ question_nos
        +str display
    }
    class Submission {
        +int id
        +str unit_key
        +int team_id
        +dict answers
        +int rank
        +SubmissionOutcome outcome
        +datetime received_at
    }
    class Cooldown {
        +int team_id
        +float until_monotonic
        +int trigger_submission_id
    }
    class ActivityEngine {
        -Lock lock
        +start()
        +submit(team_id, unit_key, answers) SubmitResult
        +invalidate(unit_key) InvalidateResult
        +end()
        +view_for_teacher()
        +view_for_team(team_id)
    }
    class SqliteActivityResultsProvider {
        +get_result(activity_id, requester) ActivityResult
    }
    class ActivityResultsProvider {
        <<interface>>
    }
    Activity "1" *-- "1..*" Team
    Activity "1" *-- "1..*" BuzzUnit
    Activity "1" *-- "0..*" Submission
    Submission --> Team
    Submission --> BuzzUnit
    Cooldown --> Team
    Cooldown --> Submission : trigger
    ActivityEngine --> Activity : 管理
    SqliteActivityResultsProvider ..|> ActivityResultsProvider
    note for BuzzUnit "由 001 的 ParsedWorksheet 產生\n（題組 → G 鍵，單一題目 → Q 鍵）"
```

## 9. 模組相依圖

```mermaid
flowchart LR
    web["web/static<br/>老師頁面・學生頁面"] -->|HTTP| api
    web -->|WebSocket| realtime
    subgraph guided_buzz
        api["api<br/>activity_routes・student_routes"]
        realtime["realtime<br/>連線管理・依身分產生推播"]
        engine["activity.engine<br/>判定（純邏輯＋鎖）"]
        fairness["activity.fairness"]
        units["activity.units<br/>ParsedWorksheet→BuzzUnit"]
        sessions["auth.sessions<br/>老師／學生 Token・輸錯限制"]
        astore["storage.activities"]
        provider["results.sqlite_provider"]
        domain["domain（001 已建立，新增列舉與 BuzzUnit）"]
        wstore["storage.worksheets（001）"]
        config["config"]
    end
    api --> engine & sessions & astore & wstore & units
    realtime --> sessions & engine
    engine --> fairness & units & astore & domain
    provider --> astore & domain
    api & engine & sessions & realtime --> config
    f001["001 寫回／匯出"] --> provider
```

規則：`activity.engine` 不直接處理 HTTP 或 WebSocket，只回傳結果與事件清單；推播由 `realtime` 在鎖釋放後送出。
時鐘以注入方式提供，方便測試冷卻。
