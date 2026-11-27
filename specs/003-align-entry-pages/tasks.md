---

description: "Task list for 003 入口頁與老師頁面對齊 OpenSpec 組"
---

# Tasks: 入口頁與老師頁面對齊 OpenSpec 組

**Input**: Design documents from `/specs/003-align-entry-pages/`

**Prerequisites**:
- 文件：plan.md、spec.md、research.md、data-model.md、contracts/（pages.md、api-changes.md）、quickstart.md、diagrams.md。
- 前置功能：001、002 皆已完成。

**Tests**: 包含測試任務（Constitution 原則 VI）。可以自動化的部分（頁面網址、導向、頁面元素、`confirmed_at`）都先寫測試，確認測試失敗後再實作。
前端互動依 quickstart.md 人工驗證。

**Organization**: 依使用者指定分成 4 個 Phase：
1. 路由與舊網址導向
2. 學生首頁
3. 合併老師頁
4. 文件、圖表與人工驗證

使用者情境對應：

| Phase | 使用者情境 |
|-------|-----------|
| Phase 1 | 完成 US5，並提供 US1、US2 的路由部分 |
| Phase 2 | US1 |
| Phase 3 | US2、US3、US4 |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可以平行進行（修改不同檔案，且不依賴尚未完成的任務）
- **[Story]**: US1–US5（spec.md）
- 路徑：`src/guided_buzz/`、`tests/`（與 001、002 同一個專案）

---

## Phase 1: 頁面路由與舊網址導向（Foundational，含 US5）

**Purpose**: 讓 `/`、`/teacher` 與兩個舊網址都指到正確的頁面。後續所有 Phase 都以這些路由為前提。
對應 E-01、E-03 的路由部分，以及 E-10。

**⚠️ CRITICAL**: 本階段完成前，不得開始 Phase 2、Phase 3

- [X] T001 撰寫 tests/integration/test_pages.py 的路由測試（contracts/pages.md「網址」表）：
  - `GET /` 回 200、`text/html`，內容是學生頁（含「加入組別」）。
  - `GET /teacher` 回 200，內容含「老師登入」。
  - 以 `follow_redirects=False` 請求 `/student.html`、`/teacher.html`：回 307，`Location` 分別為 `/`、`/teacher`。
  - 以上 4 條路由都不出現在 `/openapi.json`。
  - `/student.js`、`/teacher.js`、`/style.css` 仍回 200。
  - 執行並確認 `/teacher`、兩條導向等新路由的測試失敗。
- [X] T002 實作 src/guided_buzz/api/page_routes.py（research R1、R2）：
  - 在這個模組定義 `STATIC_DIR`，作為 `web/static` 路徑的唯一定義（原則 V）。
  - `APIRouter` 提供以下路由，全部設定 `include_in_schema=False`：
    - `GET /` 以 `FileResponse` 回傳 `STATIC_DIR / "student.html"`。
    - `GET /teacher` 以 `FileResponse` 回傳 `STATIC_DIR / "teacher.html"`。
    - `GET /student.html` 以 `RedirectResponse("/")` 導向。
    - `GET /teacher.html` 以 `RedirectResponse("/teacher")` 導向。
- [X] T003 修改 src/guided_buzz/api/app.py：
  - 刪除本檔的 `STATIC_DIR`，改從 `page_routes` 匯入。
  - `app.include_router(page_routes.router)` 必須放在 `app.mount("/", StaticFiles(...))` 之前。
  - 執行 `uv run pytest`，確認 T001 與所有既有測試都通過。

**Checkpoint**：`uv run pytest` 全部通過。此時的過渡狀態如下，Phase 3 會整理：
- `/` 顯示現有的學生頁。
- `/teacher` 顯示現有的搶答主控台。
- 舊的匯入頁暫時只能從 `/index.html` 開啟。

---

## Phase 2: User Story 1 - 學生從首頁加入組別並作答 (Priority: P1) 🎯 MVP

**Goal**: 首頁就是學生頁，有「加入組別」與「我是老師」；加入後在同一頁作答；重新整理與身分失效的處理都正確。對應 E-01 的畫面部分、E-02、E-08 的學生部分、E-09。

**Independent Test**: quickstart V1、V5（學生視窗）、V6、V7 第 1 點；老師端可暫時使用 Phase 1 過渡狀態的 `/teacher` 建立與開始活動

### Tests for User Story 1 ⚠️

- [X] T004 [P] [US1] 在 tests/integration/test_pages.py 新增學生頁元素測試（contracts/pages.md「學生頁」）。`GET /` 的內容須符合：
  - 有「加入組別」標題，以及說明文字（FR-001 原文）。
  - 有組別代碼欄位、「加入」按鈕，以及 `href="/teacher"` 的「我是老師」。
  - 沒有 `type="password"`。
  - `<script>` 只有 `/student.js`，不含 `teacher.js`、`app.js`。
  - 執行並確認失敗。

### Implementation for User Story 1

- [X] T005 [US1] 修改 src/guided_buzz/web/static/student.html：
  - 在 `#join-section` 的標題下方加上說明文字（FR-001）。
  - 把「加入」按鈕和「我是老師」連結（`<a href="/teacher" class="button">`）放在同一列。
  - 兩者都在 `#join-section` 內，加入後會隨區塊一起隱藏（FR-003）。
  - 頁面只載入 `/student.js`。
- [X] T006 [US1] 對照以下需求檢查 src/guided_buzz/web/static/student.js，只修改不符合的地方（現有程式大多已經符合）：
  - 加入成功，或重新整理時 `GET /api/me` 確認身分有效：隱藏 `#join-section`，顯示作答畫面（FR-003、FR-006）。
  - 加入失敗（代碼錯誤、格式不符、輸錯達上限）時，留在 `#join-section`，並顯示既有的錯誤訊息（FR-004）。
  - `leave()`：顯示 `#join-section`，並顯示提示訊息（FR-005）。
  - 即時連線只在加入或身分有效之後才建立（FR-023）。
  - sessionStorage 的鍵名沿用 data-model.md 第 2 節「學生頁」。
- [X] T007 [P] [US1] 修改 src/guided_buzz/web/static/style.css：加入按鈕並排的樣式，以及讓 `a.button` 看起來和 `button` 一樣。

**Checkpoint**：
- T004 通過，`uv run pytest` 全部通過。
- quickstart V1、V5（學生視窗）、V6、V7 第 1 點人工確認通過。

---

## Phase 3: User Story 2、3、4 - 合併老師頁 (Priority: P1、P1、P2)

**Goal**: `/teacher` 一頁包含所有老師功能，依序為匯入學習單、已確認的學習單、建立搶答活動、目前活動、活動清單。
活動結束後直接寫回與下載 CSV；可以從清單檢視過去的活動。對應 E-04～E-07。

**Independent Test**: quickstart V2（US2）、V3（US3）、V4（US4）、V8（登出）

### Tests for User Story 2、3 ⚠️

- [ ] T008 [P] [US2] 在 tests/integration/test_pages.py 新增老師頁元素測試（contracts/pages.md「老師頁」）。`GET /teacher` 的內容須符合：
  - 有「老師登入」與密碼欄。
  - `<script>` 只有 `/teacher.js`。
  - 整頁沒有任何 `<a href`（FR-008）。
  - 5 個區塊標題依序出現：匯入學習單、已確認的學習單、建立搶答活動、目前活動、活動清單（FR-009）。
  - 沒有「學習單 ID」「活動 ID」輸入框，也沒有「寫回答案與匯出結果」（FR-020）。
  - `GET /index.html`、`GET /app.js` 回 404（research R3）。
  - 執行並確認失敗。
- [ ] T009 [P] [US3] 在 tests/integration/test_worksheet_api.py 新增 `GET /api/worksheets` 的 data-model.md `WorksheetSummary.confirmed_at` 測試：
  - 匯入後（pending）為 `null`。
  - 確認後為可以用 `datetime.fromisoformat` 解析的字串。
  - 取消後（cancelled）為 `null`。
  - 其他欄位名稱與值都不變（contracts/api-changes.md）。
  - 執行並確認失敗。

### Implementation for User Story 2、3、4

- [ ] T010 [US3] 實作 data-model.md `WorksheetSummary.confirmed_at`，使 T009 通過：
  - src/guided_buzz/api/schemas.py：`WorksheetSummary` 新增 `confirmed_at: str | None`。
  - src/guided_buzz/api/worksheet_routes.py：`list_worksheets` 填入 `ws.confirmed_at.isoformat()` 或 `None`。
- [ ] T011 [US2] 改寫 src/guided_buzz/web/static/teacher.html 為單一老師頁（contracts/pages.md「老師頁」）：
  - 頁首只有標題與 `#logout`，移除 `<nav>` 裡的連結。
  - `#login-section` 不變。
  - `#app` 內依序放 5 個 section：
    - **`#import-section`**：從 index.html 搬入網址表單、預覽表、確認與取消；不搬「學生請開啟 `/student.html`」的提示。
    - **`#worksheets-section`**：已確認的學習單表格（編號、試算表、題數、題組數、確認時間），沒有資料時顯示說明。
    - **`#create-section`**：沿用。
    - **`#activity-section`**：
      - 沿用主控台。
      - 新增沒有活動時的說明。
      - 新增 `#ended-actions`，內含「寫回答案」「下載 CSV」按鈕與寫回結果區，預設隱藏。
    - **`#activities-section`**：活動清單表格（編號、學習單、階段、建立時間、結束時間、檢視）。
  - 頁面只載入 `/teacher.js`。
- [ ] T012 [US2] 修改 src/guided_buzz/web/static/teacher.js 的登入流程（research R4、R6）：
  - 改用 app.js 的 `formatError`（會逐條列出 `issues`），並刪除重複的輔助函式，每個只保留一份。
  - 重新整理時以 `GET /api/auth/session` 確認身分（FR-022）。
  - 登入後才呼叫 `connect()`（FR-023）。
  - 登出時先把 `socket.onclose` 設為 `null`，再 `close()`，然後回到 `#login-section`，網址不變（FR-021）。
  - sessionStorage 的鍵名沿用 data-model.md 第 2 節「老師頁」。
- [ ] T013 [US3] 在 src/guided_buzz/web/static/teacher.js 加入學習單功能：
  - 從 app.js 搬入匯入、預覽、確認、取消。
  - `loadWorksheets()` 取得 `GET /api/worksheets` 後，同時更新已確認的學習單表格與建立活動的選單：
    - 只列出 `status === "confirmed"` 的學習單。
    - 表格的確認時間顯示 data-model.md `WorksheetSummary.confirmed_at`。
  - 確認或取消後立即重新載入（FR-012）。
  - 沒有已確認的學習單時，提示先匯入。
- [ ] T014 [US3] 在 src/guided_buzz/web/static/teacher.js 加入目前活動的寫回與下載（research R7、R8）：
  - 沒有 `current` 時顯示說明。
  - `current.phase === "ended"` 時才顯示 `#ended-actions`（FR-015）。
  - **寫回答案**：
    - 呼叫 `POST /api/worksheets/{current.worksheet_id}/writeback`，body 為 `{"activity_id": current.id}`。
    - 成功時顯示已填、未填、跳過的題號。
    - 失敗時以 `formatError` 顯示錯誤，按鈕保持可用（FR-016）。
  - **下載 CSV**：
    - 沿用 app.js 的 blob 下載，以及讀取 `X-Record-Count` 的做法。
    - 0 筆時顯示「此活動沒有任何送出紀錄」（FR-017）。
  - **WebSocket**：收到 `snapshot` 時，只有在沒有 `current`，或快照 id 等於 `current.id` 時才 `render`。
- [ ] T015 [US4] 在 src/guided_buzz/web/static/teacher.js 加入活動清單（research R9）：
  - `loadActivities()` 取得 `GET /api/activities`。「學習單」欄以 `worksheet_id` 對照 `loadWorksheets()` 的結果，顯示試算表名稱。
  - 以下時機重新載入：登入後、建立活動後、收到 `phase_changed` 時（FR-018）。
  - 「檢視」以 `GET /api/activities/{id}` 取得活動，設為 `current`，並把 id 存進 sessionStorage。
  - 回 409（活動已中斷）時，只顯示伺服器的訊息，`current` 不變（FR-019）。
- [ ] T016 [US2] 刪除 src/guided_buzz/web/static/index.html 與 src/guided_buzz/web/static/app.js（research R3）。刪除後在 `src/`、`tests/` 中 grep `index.html`、`app.js`，確認沒有其他地方引用它們。
- [ ] T017 [P] [US2] 修改 src/guided_buzz/web/static/style.css：補上老師頁新增區塊與表格需要的少量樣式，以沿用既有樣式為主。

**Checkpoint**：
- T008、T009 通過，`uv run pytest` 全部通過。
- quickstart V2、V3、V4、V8 人工確認通過。

---

## Phase 4: 文件、圖表與人工驗證

**Purpose**：完成 FR-029 的文件同步、原則 VII 的圖表驗證，以及 E-01～E-10 的完整人工驗證。

- [ ] T018 [P] 依 plan.md「文件與圖表同步清單」更新 README.md 的以下段落：
  - 「頁面網址」表
  - 「1. 匯入並確認學習單」
  - 「2. 建立搶答活動」
  - 「4. 結束搶答、寫回學習單、匯出 CSV」
  - 「學生操作說明」
- [ ] T019 [P] 依 plan.md 同步清單更新 001 的文件：
  - **改寫內容**：
    - specs/001-guided-notes-import/plan.md（Scale/Scope 與 web/static 結構）
    - specs/001-guided-notes-import/quickstart.md（第 78 行網址）
    - specs/001-guided-notes-import/contracts/http-api.md（`GET /api/worksheets` 加上 `confirmed_at`）
  - **只加註記**：
    - specs/001-guided-notes-import/spec.md（Clarifications 補一行）
    - specs/001-guided-notes-import/tasks.md（開頭）
- [ ] T020 [P] 依 plan.md 同步清單更新 002 的文件：
  - **改寫內容**：specs/002-online-buzz-activity/plan.md（Scale/Scope 與 web/static 結構）。
  - **只加註記，保留原文**：specs/002-online-buzz-activity/tasks.md（開頭）、specs/002-online-buzz-activity/verification.md（環境表下方）。
- [ ] T021 對照最終程式碼檢查以下圖表（原則 VII 實作階段驗證）：
  - diagrams/003-align-entry-pages/ 的 5 張圖
  - diagrams/001-guided-notes-import/06-component.puml
  - diagrams/002-online-buzz-activity/09-component.puml
  - 不一致時先更新 `.puml`，在 repo 根目錄執行 `plantuml -tpng "./diagrams/**/*.puml"`，再同步 specs/003-align-entry-pages/diagrams.md。
- [ ] T022 在 README.md、specs/001-guided-notes-import/、specs/002-online-buzz-activity/、src/ 中 grep 以下字串：`student.html`、`teacher.html`、`搶答主控台`、`學習單與結果`、`寫回答案與匯出結果`。
  - 確認除了 T019、T020 的歷史註記、檔案名稱本身（例如 `teacher.html` 這個原始檔），以及 `page_routes.py` 的導向路由之外，沒有其他指向舊入口的說明（FR-029）。
- [ ] T023 執行 `uv run pytest -v`（tests/ 全部），回報測試指令、通過數與失敗數，失敗時附上輸出（原則 VI、SC-005）。
- [ ] T024 依 specs/003-align-entry-pages/quickstart.md 的 V1–V8，人工驗證 E-01～E-10：
  - 結果記錄在 specs/003-align-entry-pages/verification.md，格式參考 specs/002-online-buzz-activity/verification.md。
  - 回報人工驗證結果。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（路由）**：沒有前置依賴，但必須最先完成。Phase 2、3 的頁面都要經由這些路由載入，T004、T008 的頁面測試也建立在這些路由上。
- **Phase 2（US1）**：依賴 Phase 1。
- **Phase 3（US2、US3、US4）**：依賴 Phase 1，可以和 Phase 2 平行進行。兩者共同修改的檔案只有 style.css：T007、T017 都改這個檔案，要依序合併。
  Phase 3 內部的順序：
  - T010（API 欄位）完成後，T013 才能顯示確認時間。
  - T011（HTML 結構）是 T012～T015 的前提。
  - T012～T015 都修改 teacher.js，必須依序進行。
  - T016 刪除 index.html、app.js，必須在 T013、T014 搬完程式之後。
- **Phase 4**：依賴 Phase 1–3 全部完成。T018、T019、T020 可以平行；T021、T022 在 T018～T020 之後；T023、T024 最後進行。

### User Story Dependencies

- **US5（舊網址）**：在 Phase 1 完成，沒有其他依賴。
- **US1（學生首頁）**：只依賴 Phase 1。
- **US2（老師入口與登入）**：依賴 Phase 1；是 US3、US4 的畫面基礎。
- **US3（單頁完成整場活動）**：依賴 US2（T011、T012）。
- **US4（活動清單）**：依賴 US2，並依賴 US3 的 `current` 顯示邏輯（T014）。

### Within Each Phase

- 先寫測試並確認失敗，再實作。
- 伺服器端（路由、API 欄位）先做，再做 HTML，最後是 JS 行為。

---

## Parallel Example: Phase 3

```bash
# 測試可以同時撰寫（不同檔案）：
Task: "T008 在 tests/integration/test_pages.py 新增老師頁元素測試"
Task: "T009 在 tests/integration/test_worksheet_api.py 新增 confirmed_at 測試"

# T010（schemas.py、worksheet_routes.py）與 T011（teacher.html）可以同時進行
```

## Parallel Example: Phase 2 與 Phase 3

```bash
# Phase 1 完成後，學生首頁與老師頁可以由兩人分頭進行：
Task: "T004–T007 學生首頁（student.html、student.js）"
Task: "T008–T016 合併老師頁（teacher.html、teacher.js）"
# style.css（T007、T017）要依序合併
```

---

## Implementation Strategy

### MVP

**Phase 1 + Phase 2**：學生可以直接從首頁加入，舊網址也會導向。這解決了兩組之間最明顯的差異。
這時老師仍可使用過渡狀態的 `/teacher` 和 `/index.html` 操作。**STOP and VALIDATE**：執行 `uv run pytest`，並完成 quickstart V1、V6、V7。

### Incremental Delivery

1. Phase 1：路由與導向，自動化測試通過。
2. Phase 2：學生首頁，對應 E-01、E-02、E-08（學生部分）、E-09。
3. Phase 3：合併老師頁，對應 E-04～E-07，並刪除舊的入口頁。
4. Phase 4：文件與圖表同步、完整人工驗證 E-01～E-10。
5. 每完成一個 Phase，都要回報測試指令與結果，通過後才進入下一個 Phase。依照 Git 工作流程，在功能分支上開 PR，CI 通過後再 merge。

---

## Requirement Coverage

| 需求 | 任務 | 驗收情境 |
|------|------|---------|
| FR-001、FR-002（首頁是學生頁、「我是老師」） | T001、T004、T005、T007 | E-01、E-03 |
| FR-003～FR-006（加入、失敗、失效、重新整理） | T005、T006 | E-02、E-09 |
| FR-007～FR-009（`/teacher`、頁首、5 個區塊） | T001、T002、T008、T011 | E-03、E-04 |
| FR-010～FR-013（匯入、已確認清單、選單即時更新、建立活動） | T009、T010、T011、T013 | E-05 |
| FR-014～FR-017（目前活動、寫回、下載 CSV） | T011、T014 | E-06 |
| FR-018～FR-020（活動清單、檢視、取代舊的寫回區） | T008、T011、T015、T016 | E-07 |
| FR-021、FR-022（登出、重新整理） | T012 | quickstart V8、E-08 |
| FR-023、FR-024（連線時機、每個視窗獨立身分） | T006、T012 | E-08 |
| FR-025（舊網址導向，US5） | T001、T002、T003 | E-10 |
| FR-026（各頁只載入自己的程式） | T004、T005、T008、T011、T016 | — |
| FR-027（伺服器端只有允許的變更） | T002、T003、T010、T023（既有測試全部通過） | SC-005 |
| FR-028（繁體中文、沿用既有訊息） | T005、T011、T013～T015 | E-01～E-10 |
| FR-029（文件與圖表同步） | T018～T022 | — |

## Notes

- T 編號只在本功能內有效。提到 001、002 的任務時，寫成「001 tasks Txxx」或「002 tasks Txxx」。
- 伺服器端只有兩項變更：T002、T003 的頁面路由，以及 T010 的 `confirmed_at`。其餘的判定、權限、推播與資料都不變（spec FR-027）。如果實作時發現需要修改其他後端程式，要先回頭更新 spec 與 plan。
- Phase 1–2 的過渡期間，`/teacher` 頁首仍有「學習單與結果」連結，它會連到 `/`，也就是學生頁。這是預期中的過渡狀態，Phase 3 的 T011 會移除。
