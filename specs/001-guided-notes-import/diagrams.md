# Diagrams: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **API**: [contracts/http-api.md](./contracts/http-api.md)

依 Constitution 原則 VII，以下圖表須在實作前審閱。設計變更時先改圖，再改程式。

## 1. 循序圖：匯入學習單並確認（US1）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師（瀏覽器視窗）
    participant API as API 層
    participant AUTH as 身分驗證
    participant P as 學習單解析
    participant S as 儲存
    T->>API: POST /api/worksheets（.xlsx）＋Token
    API->>AUTH: 驗證 Token 與老師身分
    alt Token 無效
        AUTH-->>T: 401 需要登入
    end
    API->>API: 檢查檔案大小與是否為空（設定上限）
    alt 超過上限或空檔
        API-->>T: 413/422 繁體中文錯誤＋上限值
    end
    API->>P: parse(檔案內容, 表頭標籤, 題數上限)
    P->>P: 找表頭 → 題目列 → 填空格 → 題組 → 編號
    alt 有驗證問題
        P-->>API: ImportIssue 清單（含工作表與列/儲存格）
        API-->>T: 422 所有問題與位置
    else 解析成功
        P-->>API: ParsedWorksheet
        API->>S: 保存原始檔（UUID 檔名）＋SHA-256＋解析結果，狀態 pending
        API-->>T: 201 題數、題組、題號與位置對照
    end
    T->>API: POST /api/worksheets/{id}/confirm
    API->>AUTH: 驗證是否為擁有者（否則 404）
    API->>S: pending → confirmed（不是 pending 時回 409）
    API-->>T: 200 已確認
```

## 2. 循序圖：答案寫回（US2）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師
    participant API as API 層
    participant R as ActivityResultsProvider
    participant S as 儲存
    participant P as 學習單解析
    participant W as 寫回
    T->>API: POST /api/worksheets/{id}/writeback {activity_id}
    API->>S: 讀取學習單（擁有者檢查、須為 confirmed）
    API->>R: get_result(activity_id, 老師)
    Note over R: 伺服器保存的判定結果是唯一依據（FR-018）
    alt 活動不存在、不屬於本人或學習單不符
        API-->>T: 404
    else 活動未結束
        API-->>T: 409 INVALID_STATE
    end
    API->>S: 讀取原始檔，比對 SHA-256
    API->>P: 重新解析，比對填空格位置
    alt 雜湊或位置不同
        API-->>T: 409 STRUCTURE_CHANGED（說明差異）
    end
    API->>W: write(原始檔, {儲存格: 成功答案})
    W->>W: 只改寫目標儲存格 XML，其餘壓縮檔項目原樣複製
    W-->>API: 新檔案
    API->>S: 保存 writebacks/<file_id>.xlsx
    API-->>T: 201 下載網址、已填題號、未填題號
    T->>API: GET /api/writebacks/{file_id}
    API-->>T: .xlsx 檔案
```

## 3. 循序圖：匯出 CSV（US3）

```mermaid
sequenceDiagram
    autonumber
    actor T as 老師
    participant API as API 層
    participant R as ActivityResultsProvider
    participant E as CSV 匯出
    T->>API: GET /api/activities/{id}/results.csv
    API->>R: get_result(id, 老師)（擁有者檢查）
    alt 活動未結束
        API-->>T: 409 INVALID_STATE
    end
    API->>E: to_csv(ActivityResult)
    E->>E: 題組送出依填空拆列、依題號與順位排序、UTF-8 BOM
    E-->>API: CSV 內容與筆數
    API-->>T: 200 text/csv（X-Record-Count）
```

## 4. 類別圖：共用資料結構（定義在 domain 模組）

```mermaid
classDiagram
    class CellRef {
        +str sheet
        +str cell
    }
    class Blank {
        +int question_no
        +CellRef location
        +str source_label
        +str sub_label
        +int group_no
    }
    class QuestionGroup {
        +int group_no
        +str source_label
        +list~int~ question_nos
    }
    class ParsedWorksheet {
        +list~Blank~ questions
        +list~QuestionGroup~ groups
    }
    class Worksheet {
        +UUID id
        +str owner
        +str original_filename
        +str sha256
        +WorksheetStatus status
        +ParsedWorksheet parsed
    }
    class ImportIssue {
        +ImportErrorCode code
        +str message
        +str sheet
        +int row
        +str cell
    }
    class SubmissionRecord {
        +list~int~ question_nos
        +str team_name
        +dict answers
        +int rank
        +SubmissionOutcome outcome
    }
    class ActivityResult {
        +UUID activity_id
        +UUID worksheet_id
        +str owner
        +bool ended
        +list~SubmissionRecord~ submissions
    }
    class ActivityResultsProvider {
        <<interface>>
        +get_result(activity_id, requester) ActivityResult
    }
    Worksheet "1" *-- "1" ParsedWorksheet
    ParsedWorksheet "1" *-- "1..*" Blank
    ParsedWorksheet "1" *-- "0..*" QuestionGroup
    Blank --> CellRef
    QuestionGroup "1" o-- "2..*" Blank : question_nos
    ActivityResult "1" *-- "0..*" SubmissionRecord
    ActivityResult --> Worksheet : worksheet_id
    ActivityResultsProvider ..> ActivityResult
```

## 5. 狀態圖：學習單匯入狀態

```mermaid
stateDiagram-v2
    [*] --> pending : 上傳並解析成功
    pending --> confirmed : 老師確認
    pending --> cancelled : 老師取消
    confirmed --> [*]
    cancelled --> [*]
    note right of confirmed : 只有 confirmed 可建立活動、寫回、匯出
```

## 6. 模組相依圖

```mermaid
flowchart LR
    web["web/static<br/>老師頁面"] -->|HTTP + Bearer Token| api
    subgraph guided_buzz
        api["api<br/>路由・輸入驗證・錯誤格式"]
        auth["auth<br/>老師登入・Token"]
        parser["worksheet.parser"]
        writeback["worksheet.writeback"]
        export["export.csv_export"]
        results["results<br/>JsonFileResultsProvider"]
        storage["storage<br/>SQLite・檔案"]
        config["config<br/>環境變數"]
        domain["domain<br/>共用資料結構・介面"]
    end
    api --> auth & parser & writeback & export & results & storage
    parser & writeback & export & results & storage & api --> domain
    api & auth & storage & parser --> config
    buzz["002 搶答活動（未來）"] -.實作 ActivityResultsProvider.-> domain
```

規則：`domain` 不依賴任何其他模組；`parser`、`writeback`、`export` 為不做 I/O 的純函式模組
（輸入 bytes 或物件，輸出結果），可以獨立做單元測試。
