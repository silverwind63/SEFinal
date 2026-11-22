---

description: "Task list for 001 學習單匯入、答案寫回與結果匯出"
---

# Tasks: 學習單匯入、答案寫回與結果匯出

**Input**: Design documents from `/specs/001-guided-notes-import/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, diagrams.md, contracts/, quickstart.md

**Tests**: 包含測試任務。Constitution 原則 VI 規定每個功能至少要有一個正常案例與一個邊界案例測試；
各使用者情境都是先寫測試、確認測試失敗，再進行實作。

**Organization**: 依使用者情境分組，每個情境都能獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行進行（修改不同檔案，且不依賴尚未完成的任務）
- **[Story]**: 所屬使用者情境（US1、US2、US3）
- 路徑依 plan.md 的單一專案結構：`src/guided_buzz/`、`tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 圖表審閱與專案初始化

- [ ] T001 審閱 specs/001-guided-notes-import/diagrams.md 的 6 張圖，確認與 spec.md、data-model.md、contracts/ 一致，並在檔案開頭加上「已審閱：日期」；未審閱不得開始 Phase 2（Constitution 原則 VII）
- [ ] T002 建立 pyproject.toml（套件名稱 guided-buzz，src 結構；相依套件：fastapi、uvicorn、pydantic>=2、openpyxl、lxml、python-multipart、python-dotenv；開發用：pytest、httpx；設定 pytest 的 testpaths=tests）與 .python-version（內容為 3.12），並執行 `uv sync` 確認可以安裝
- [ ] T003 [P] 建立 .gitignore（.env、.venv/、var/、__pycache__/、*.pyc、.pytest_cache/）與 .env.example，列出 research R10 的所有 GB_* 變數，只填佔位值與預設值說明（GB_TEACHER_PASSWORD=change-me）
- [ ] T004 [P] 依 plan.md 的 Source Code 結構建立 src/guided_buzz/ 下各子套件（domain、worksheet、export、results、storage、auth、api、web/static）與 tests/unit、tests/integration、tests/fixtures/worksheets，並加入 __init__.py
- [ ] T005 [P] 將範例 A、B 存為 tests/fixtures/worksheets/sample_a.xlsx 與 sample_b.xlsx（來源：spec.md「參考範例學習單」的兩個網址，網址後加上 `/export?format=xlsx` 即可下載），並以 openpyxl 確認兩份都有「學習單」工作表

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 設定、共用資料結構、儲存、身分驗證、API 骨架、搶答結果介面

**⚠️ CRITICAL**: 本階段完成前不得開始任何使用者情境

- [ ] T006 實作 src/guided_buzz/config.py：以 python-dotenv 載入 .env，再讀取 research R10 列出的 GB_* 環境變數，轉成不可變的 Settings 物件並驗證型別與範圍（上限必須 > 0、連接埠 1–65535）；缺少 GB_TEACHER_PASSWORD 或值不合法時，以繁體中文說明變數名稱並停止啟動；不得輸出密碼值
- [ ] T007 [P] 撰寫 tests/unit/test_config.py：正常（預設值、覆寫值）與邊界（缺少密碼、上限為 0、非數字、表頭標籤為空字串），並確認錯誤訊息不含密碼值
- [ ] T008 [P] 實作 src/guided_buzz/domain/models.py：依 data-model.md 定義 WorksheetStatus、SubmissionOutcome 列舉，以及 CellRef（data-model.md CellRef.sheet、CellRef.cell）、Blank（Blank.question_no、Blank.location、Blank.group_no）、QuestionGroup（QuestionGroup.group_no、QuestionGroup.question_nos）、ParsedWorksheet（ParsedWorksheet.questions、ParsedWorksheet.groups）、Worksheet（Worksheet.original_filename、Worksheet.stored_path、Worksheet.status、Worksheet.sha256）、SubmissionRecord（SubmissionRecord.question_nos、SubmissionRecord.answers、SubmissionRecord.rank、SubmissionRecord.outcome）、ActivityResult（ActivityResult.worksheet_id、ActivityResult.owner、ActivityResult.ended、ActivityResult.submissions）、WritebackResult；建構時驗證欄位規則，這是全專案唯一的定義處
- [ ] T009 [P] 實作 src/guided_buzz/domain/errors.py：data-model.md ImportIssue.code（ImportErrorCode 表中 10 個代碼）、ImportIssue.message 的繁體中文訊息範本（含工作表、列、儲存格與上限值等參數），以及 NotFound、InvalidState、StructureChanged、ImportFailed（包含 list[ImportIssue]）例外
- [ ] T010 [P] 實作 src/guided_buzz/domain/ports.py：依 contracts/results-provider.md 定義 ActivityResultsProvider Protocol（get_result(activity_id, requester) -> ActivityResult）
- [ ] T011 撰寫 tests/unit/test_models.py：正常建構，以及違反 data-model.md CellRef.cell 格式、QuestionGroup.question_nos 少於 2 或不連續、SubmissionRecord.answers 的鍵與 question_nos 不符、SubmissionRecord.rank < 1、ActivityResult 中同一搶答單位出現兩筆 success 等邊界情況
- [ ] T012 實作 src/guided_buzz/storage/db.py：依 data-model.md 的「SQLite 資料表」建立 worksheets、questions、question_groups、writebacks；資料庫檔放在 Settings.data_dir 下，啟用外鍵，提供以交易進行的連線函式
- [ ] T013 [P] 實作 src/guided_buzz/storage/files.py：在 data_dir 下的 uploads/、writebacks/ 以 UUID 檔名存取檔案（data-model.md Worksheet.stored_path），不是合法 UUID 的識別碼一律拒絕，並計算 SHA-256（Worksheet.sha256）
- [ ] T014 實作 src/guided_buzz/auth/teacher.py：以 hmac.compare_digest 比對 GB_TEACHER_PASSWORD；用 secrets 產生 Token，存在記憶體並依設定的期限失效；連續錯誤達上限時暫時鎖定並回傳剩餘秒數；只記錄登入成功或失敗事件，不記錄密碼與 Token
- [ ] T015 實作 src/guided_buzz/api/app.py 與 src/guided_buzz/api/schemas.py 的錯誤 schema：create_app(settings) 掛上路由與 web/static；把 domain 例外與 pydantic 驗證錯誤轉成 contracts/http-api.md 的統一錯誤格式（繁體中文，不含堆疊追蹤）；提供 require_teacher 相依函式（缺少或無效 Token 回 401）；設定 logging
- [ ] T016 實作 src/guided_buzz/api/auth_routes.py：POST /api/auth/teacher-login，依 contracts/http-api.md 回應 200、401、422，鎖定期間回應錯誤並附剩餘秒數
- [ ] T017 [P] 實作 src/guided_buzz/__main__.py：以 Settings.host/port 啟動 uvicorn（預設 127.0.0.1）
- [ ] T018 撰寫 tests/conftest.py（使用 tmp_path 作為 GB_DATA_DIR、測試用密碼、TestClient、取得 Token 的 fixture）與 tests/integration/test_auth.py：正確密碼取得 Token；錯誤密碼回 401；連續錯誤被鎖定；沒有 Token 或 Token 過期時受保護端點回 401；caplog 中不含密碼與 Token
- [ ] T019 實作 src/guided_buzz/results/json_provider.py：JsonFileResultsProvider 讀取 <GB_RESULTS_DIR>/<activity_id>.json，activity_id 必須是合法 UUID；依 data-model.md SubmissionRecord.answers、SubmissionRecord.rank、SubmissionRecord.outcome、ActivityResult.owner 驗證內容，錯誤時以繁體中文指出第幾筆；不存在或 requester 不符時拋出 NotFound
- [ ] T020 [P] 撰寫 tests/unit/test_json_provider.py：正常載入 contracts/results-provider.md 的範例；邊界情況包含非 UUID 的 activity_id（含 `../`）、檔案不存在、requester 不符、同一搶答單位兩筆 success、answers 的鍵不符

**Checkpoint**: `uv run pytest` 全部通過；伺服器可以啟動並登入

---

## Phase 3: User Story 1 - 匯入學習單並確認題目 (Priority: P1) 🎯 MVP

**Goal**: 老師上傳 .xlsx，看到題數、題組與「題號↔儲存格」對照，並可以確認或取消

**Independent Test**: 匯入範例 A、B，系統回報的題數、題號、位置與題組和 spec.md 的對照表完全一致（quickstart V1–V4）

### Tests for User Story 1 ⚠️

> 先撰寫測試，確認測試失敗後再進行實作

- [ ] T021 [P] [US1] 實作 tests/factories.py：用 openpyxl 產生學習單 bytes 的建構函式，可指定表頭列位置、三個欄位範圍（含合併）、題目列、空白分隔列、作答範圍內的子題標籤、題號縱向合併（題組）、多個工作表、預填的作答格，以及題數
- [ ] T022 [P] [US1] 撰寫 tests/unit/test_parser.py：範例 A、B 結果與 spec.md 對照表完全一致；quickstart V4 的變體（表頭在第 2 列、作答在 B 欄）；多工作表連續編號；跳過沒有表頭的工作表；只含空白字元算空白；相鄰的空白儲存格算同一個填空格並取最左邊；10 個錯誤代碼各有一個案例且附正確的工作表、列或儲存格；同一檔案有多個錯誤時一次全部回報；題數剛好等於上限通過、上限加 1 失敗
- [ ] T023 [P] [US1] 撰寫 tests/integration/test_worksheet_api.py：上傳範例 B 得到 201 預覽，回應中不含題目敘述文字；confirm 回 200；再次 confirm 回 409；cancel 之後 confirm 回 409；超過大小上限回 413 且訊息含上限值；空檔回 422 FILE_EMPTY；非 xlsx 回 422 NOT_XLSX；沒有 Token 回 401；不存在的 id 回 404；GET /api/worksheets 只列出本人擁有的學習單

### Implementation for User Story 1

- [ ] T024 [US1] 實作 src/guided_buzz/worksheet/parser.py：parse(data: bytes, settings) -> ParsedWorksheet，依 research.md R3 的 9 個步驟處理，表頭標籤與題數上限從設定讀取；產生的物件符合 data-model.md Blank.question_no（1..N 連續）、Blank.location、Blank.source_label、Blank.sub_label、QuestionGroup.question_nos；所有問題收集後一次以 ImportFailed 拋出；不讀取或保存題目文字（FR-007）
- [ ] T025 [US1] 實作 src/guided_buzz/storage/worksheets.py：create_pending(owner, filename, bytes, parsed)、get(id, owner)（非擁有者視同不存在，拋出 NotFound）、list_by_owner、confirm、cancel；狀態轉換遵守 data-model.md Worksheet.status（只允許 pending→confirmed、pending→cancelled，其餘拋出 InvalidState）；Worksheet.original_filename 截斷至 255 字元
- [ ] T026 [US1] 在 src/guided_buzz/api/schemas.py 新增 WorksheetPreview、QuestionOut、GroupOut、WorksheetSummary schema，由 domain 模型轉換而來，欄位與 contracts/http-api.md 一致
- [ ] T027 [US1] 實作 src/guided_buzz/api/worksheet_routes.py：POST /api/worksheets（先檢查大小與空檔，再解析）、POST /{id}/confirm、POST /{id}/cancel、GET /{id}、GET /api/worksheets，全部需要 require_teacher
- [ ] T028 [US1] 實作 src/guided_buzz/web/static/index.html、app.js、style.css 的登入與匯入區：Token 存在 sessionStorage；上傳後以表格顯示題數、題組數，以及每題的系統題號、原題號、子題標籤、儲存格、題組；提供確認與取消按鈕；錯誤時逐條列出 message 與位置
- [ ] T029 [US1] 在 src/guided_buzz/api/worksheet_routes.py 記錄匯入成功或失敗、確認與取消事件的 log（只記學習單 ID、題數與錯誤代碼）

**Checkpoint**: T022、T023 全部通過；quickstart V1–V4 人工驗證通過

---

## Phase 4: User Story 2 - 將搶答成功答案寫回原學習單 (Priority: P2)

**Goal**: 依伺服器保存的成功答案產生新的 .xlsx，只改動填空格

**Independent Test**: 用範例 B 加上 JSON 結果檔執行寫回，填空格內容正確，其他內容逐位元組或逐格不變（quickstart V5）

### Tests for User Story 2 ⚠️

- [ ] T030 [P] [US2] 撰寫 tests/unit/test_writeback.py：寫回範例 A、B 後，除了目標工作表 XML 之外，其他壓縮檔項目逐位元組相同；用 openpyxl 比對，除目標儲存格外所有值與合併範圍相同；目標儲存格的樣式 s 屬性保留；目標儲存格原本不存在於 XML 時，依欄順序插入（使用 tests/factories.py 產生）；目標列不存在時，依列順序插入；答案含換行、`<&>"`、emoji 與 1000 字時完整保留
- [ ] T031 [P] [US2] 撰寫 tests/unit/test_answer_mapping.py：從 ActivityResult 只取 outcome=success 的紀錄；題組的一筆送出對應多個儲存格；被判定無效後由遞補者成功；沒有 success 的題號列入 unfilled
- [ ] T032 [P] [US2] 在 tests/integration/test_result_api.py 撰寫寫回測試：正常流程回 201，filled/unfilled 正確，下載內容可被 openpyxl 讀取；活動 ended=false 回 409；學習單未確認回 409；竄改 uploads/ 中的原始檔回 409 STRUCTURE_CHANGED；活動的 worksheet_id 不符回 404；沒有 Token 下載回 401

### Implementation for User Story 2

- [ ] T033 [P] [US2] 實作 src/guided_buzz/worksheet/writeback.py：write(original: bytes, answers: dict[CellRef, str]) -> bytes，依 research.md R4 處理：以 workbook.xml 與 rels 找到工作表 XML 路徑，用 lxml 改寫目標儲存格為行內字串並保留 s 屬性，必要時插入儲存格或列，其餘壓縮檔項目原樣複製（保留原本的壓縮方式與順序）
- [ ] T034 [P] [US2] 實作 src/guided_buzz/results/mapping.py：success_answers(result, parsed) -> (dict[CellRef, str], filled, unfilled)，依 data-model.md SubmissionRecord.outcome、SubmissionRecord.answers 與 Blank.location 對應
- [ ] T035 [US2] 在 src/guided_buzz/storage/worksheets.py 新增寫回紀錄（writebacks 資料表）的新增與查詢，以及 verify_unchanged(worksheet)：比對 SHA-256，再重新解析並比對每題的 Blank.location，不一致時拋出 StructureChanged，並說明差異（research.md R5）
- [ ] T036 [US2] 實作 src/guided_buzz/api/result_routes.py 的 POST /api/worksheets/{id}/writeback 與 GET /api/writebacks/{file_id}：檢查擁有者、學習單須為 confirmed、ActivityResult.ended 須為 true、ActivityResult.worksheet_id 須相符（data-model.md）；下載時 Content-Disposition 以 RFC 5987 編碼「<原檔名>_已填答.xlsx」；從 Settings 取得 provider（設定 GB_RESULTS_DIR 時使用 JsonFileResultsProvider）
- [ ] T037 [US2] 在 src/guided_buzz/web/static/ 新增寫回區：輸入活動 ID、執行寫回、顯示已填與未填題號、提供下載按鈕（以帶 Token 的 fetch 下載成 Blob，再觸發儲存）
- [ ] T038 [US2] 在 src/guided_buzz/api/result_routes.py 記錄寫回事件的 log（學習單 ID、活動 ID、已填與未填題數；不記答案）

**Checkpoint**: T030–T032 通過；quickstart V5 通過，並以 Google Sheets 開啟寫回檔，確認排版不變

---

## Phase 5: User Story 3 - 匯出活動結果 CSV (Priority: P3)

**Goal**: 匯出題號、組別、答案、搶答順位、結果的 CSV

**Independent Test**: 已知結果匯出後，以 Excel 或 Google Sheets 開啟，內容、筆數與中文都正確（quickstart V6）

### Tests for User Story 3 ⚠️

- [ ] T039 [P] [US3] 撰寫 tests/unit/test_csv_export.py：以 UTF-8 BOM 開頭、CRLF 換行；標題列為「題號,組別,答案,搶答順位,結果」；依題號、順位排序；題組送出依填空拆成多列且順位相同；結果欄顯示成功、未搶到、無效；答案含逗號、引號、換行時用 csv 模組讀回後與原值相同；沒有紀錄時只有標題列
- [ ] T040 [P] [US3] 在 tests/integration/test_result_api.py 撰寫 CSV 測試：正常回 200，content-type 與 X-Record-Count 正確；活動未結束回 409；活動不存在或 requester 不符回 404；沒有 Token 回 401

### Implementation for User Story 3

- [ ] T041 [US3] 實作 src/guided_buzz/export/csv_export.py：to_csv(result, parsed) -> (str, record_count)，依 research.md R7 處理；data-model.md SubmissionRecord.question_nos 為題組時依填空拆列，SubmissionRecord.rank 原樣輸出，SubmissionRecord.outcome 轉成中文
- [ ] T042 [US3] 在 src/guided_buzz/api/result_routes.py 新增 GET /api/activities/{activity_id}/results.csv，依 contracts/http-api.md 設定回應標頭，並記錄匯出事件的 log（活動 ID、筆數）
- [ ] T043 [US3] 在 src/guided_buzz/web/static/ 新增匯出按鈕；X-Record-Count 為 0 時顯示「目前無紀錄」

**Checkpoint**: T039、T040 通過；quickstart V6 通過

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T044 [P] 撰寫 README.md（繁體中文）：功能簡介、啟動方式、所需環境變數清單（只列名稱與用途，不含值）、學習單格式規則（表頭、題目列、填空格、題組）、測試指令（Constitution 的專案範圍與限制）
- [ ] T045 [P] 撰寫 tests/integration/test_no_secrets.py：完成匯入、寫回、匯出的完整流程後，確認 caplog 中不含測試密碼、Token 與答案字串；並掃描 src/ 中不含寫死的絕對路徑與密碼字面值
- [ ] T046 [P] 在 tests/unit/test_parser.py 新增效能測試：100 題與 500 題的動態產生學習單，解析時間 < 10 秒（SC-002）
- [ ] T047 對照實作更新 specs/001-guided-notes-import/diagrams.md，確認 6 張圖與最終程式碼一致（Constitution 品質關卡第 4 項）
- [ ] T048 執行 `uv run pytest -v` 與 quickstart.md 的 V1–V7 人工驗證，並將測試指令、通過與失敗數、失敗輸出，以及人工驗證結果回報給使用者（Constitution 原則 VI）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**：T001（圖表審閱）是所有後續工作的前提
- **Foundational (Phase 2)**：依賴 Setup，完成前不能開始任何使用者情境
- **US1 (Phase 3)**：依賴 Foundational
- **US2 (Phase 4)**：依賴 Foundational，以及 US1 的 parser（T024）與 storage（T025），因為寫回需要已確認的學習單
- **US3 (Phase 5)**：依賴 Foundational，以及 US1 的 T024、T025；不依賴 US2，可以和 US2 平行進行
- **Polish (Phase 6)**：依賴所有使用者情境完成

### Within Each User Story

- 先寫測試、確認失敗，再實作
- domain、純函式模組 → storage → API 路由 → 前端 → log

### Parallel Opportunities

- Phase 1：T003、T004、T005
- Phase 2：T007、T008、T009、T010 平行；T013 與 T012 平行；T017、T020 與其他任務平行
- US1：T021、T022、T023 平行
- US2：T030、T031、T032 平行；T033、T034 平行
- US3：T039、T040 平行
- US2 與 US3 整個階段可以平行進行（兩者都會修改 api/result_routes.py 與 tests/integration/test_result_api.py，合併時要注意）
- Polish：T044、T045、T046 平行

---

## Parallel Example: User Story 2

```bash
Task: "撰寫 tests/unit/test_writeback.py"
Task: "撰寫 tests/unit/test_answer_mapping.py"
Task: "在 tests/integration/test_result_api.py 撰寫寫回測試"
# 測試確認失敗後：
Task: "實作 src/guided_buzz/worksheet/writeback.py"
Task: "實作 src/guided_buzz/results/mapping.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 → Phase 2 → Phase 3
2. **STOP and VALIDATE**：執行 `uv run pytest`，並完成 quickstart V1–V4
3. 此時老師已能匯入並確認題目，002 搶答活動可以開始使用這些題目

### Incremental Delivery

1. Setup + Foundational → 可以登入
2. US1 → 匯入與確認（MVP）
3. US2 → 寫回學習單
4. US3 → 匯出 CSV
5. 每完成一個情境，都要回報測試指令、結果與人工驗證步驟

---

## Notes

- CSV 第 5 欄「結果」已由使用者確認（spec.md FR-020，2026-11-22）
- 002 完成後，再以正式的 ActivityResultsProvider 取代 JsonFileResultsProvider（只需改動 T036 的 provider 選擇）
- 每完成一個任務或一組相關任務就提交一次 commit
