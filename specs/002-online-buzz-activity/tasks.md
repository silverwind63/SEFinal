---

description: "Task list for 002 線上分組搶答活動"
---

# Tasks: 線上分組搶答活動

**Input**: Design documents from `/specs/002-online-buzz-activity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, diagrams.md, contracts/, quickstart.md；
以及 **001 的 Phase 1、Phase 2 與 US1（001 tasks T001–T033）已完成**，因為本功能沿用其 config、domain、storage、auth、api 骨架與已確認的學習單

**Tests**: 包含測試任務（Constitution 原則 VI）。每個使用者情境都先撰寫測試、確認失敗，再進行實作。

**Organization**: 依 spec.md 的 5 個使用者情境分組。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行進行（修改不同檔案，且不依賴尚未完成的任務）
- **[Story]**: US1–US5
- 路徑：`src/guided_buzz/`、`tests/`（與 001 為同一個專案）

---

## Phase 1: Setup

- [ ] T001 以 PlantUML CLI 將 diagrams/002-online-buzz-activity/ 的 9 個 .puml 轉成 PNG，審閱 9 張圖是否與 spec.md、data-model.md、contracts/ 一致，並在 specs/002-online-buzz-activity/diagrams.md 開頭註記審閱日期；未審閱不得開始 Phase 2（Constitution 原則 VII）
- [ ] T002 在 pyproject.toml 的開發相依套件加入 pytest-asyncio（asyncio_mode=auto），並在 src/guided_buzz/__main__.py 固定 uvicorn workers=1，加上註解說明原因（research.md R1）
- [ ] T003 [P] 在 .env.example 加入 research.md R10 的所有新變數，只填佔位值與預設值說明

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: 本階段完成前不得開始任何使用者情境

- [ ] T004 修改 src/guided_buzz/config.py：讀取並驗證 research.md R10 的變數（範圍與 data-model.md 的 Activity.cooldown_seconds、Activity.cooldown_lead 相同；GB_MAX_TEAMS、GB_TEAM_NAME_MAX、GB_MAX_ANSWER_LENGTH 必須 ≥ 1），並在 tests/unit/test_config.py 補上正常與邊界案例
- [ ] T005 [P] 修改 src/guided_buzz/domain/models.py：新增 ActivityPhase 列舉（data-model.md Activity.phase），以及 BuzzUnit（data-model.md BuzzUnit.key、BuzzUnit.question_nos、BuzzUnit.display），建構時驗證鍵值格式與題號；不得重複定義 001 已有的 SubmissionRecord、SubmissionOutcome
- [ ] T006 [P] 修改 src/guided_buzz/domain/errors.py：新增 SubmissionRejectCode 列舉的 7 個代碼，以及 ACTIVITY_IN_PROGRESS、INVALID_CODE、TOO_MANY_ATTEMPTS、NOT_ENDED、PERSIST_FAILED 的繁體中文訊息範本（contracts/http-api.md），並定義 SubmissionRejected 例外，可附帶剩餘秒數、缺少或多出的題號
- [ ] T007 [P] 實作 src/guided_buzz/activity/units.py：build_units(parsed: ParsedWorksheet) -> list[BuzzUnit]，依 research.md R4 產生題組的 G 鍵與單一題目的 Q 鍵，排序與 data-model.md BuzzUnit.question_nos 一致，display 含系統題號、學習單原題號與子題標籤，不含題目敘述
- [ ] T008 [P] 撰寫 tests/unit/test_units.py：範例 B 產生 G1、G2、Q5、Q6；範例 A 產生 Q1–Q6；動態產生的學習單在題組位於中間時排序正確；display 不含題目敘述
- [ ] T009 [P] 實作 src/guided_buzz/activity/codes.py：依 data-model.md Team.code 產生代碼，同一場活動內不重複；計算 Team.code_hash；正規化輸入（去除空白、轉大寫）；並撰寫 tests/unit/test_codes.py（字元集、長度、不重複、正規化、雜湊比對）
- [ ] T010 修改 src/guided_buzz/storage/db.py：依 data-model.md 的「SQLite 資料表（新增）」建立 activities、teams、submissions、submission_answers，包含所有 UNIQUE 限制與外鍵
- [ ] T011 實作 src/guided_buzz/storage/activities.py：create_activity（寫入 data-model.md Activity.id、Activity.worksheet_id、Activity.owner、Activity.phase、Activity.fairness_enabled、Activity.cooldown_seconds、Activity.cooldown_lead、Activity.created_at；Team.id、Team.name、Team.code_hash、Team.code_version；不寫入 Team.code 明文）、update_phase（Activity.started_at、Activity.ended_at）、mark_unfinished_interrupted()、get_activity(id, owner)、list_by_owner
- [ ] T012 實作 src/guided_buzz/auth/sessions.py：擴充 001 的 Token 機制，加入學生 Session（data-model.md Session.token、Session.role，以及 team 角色的 activity_id、team_id、code_version）；提供 revoke_team(activity_id, team_id)；以 X-Window-Id 計算每個視窗的輸錯次數，並加上全體每分鐘上限（research.md R3）；不記錄 Token 與代碼
- [ ] T013 [P] 撰寫 tests/unit/test_sessions.py：老師與學生 Token 互不通用；code_version 過期後 Token 失效；某視窗連續輸錯 5 次被鎖，另一個視窗不受影響；超過全體上限時所有加入請求被延遲；鎖定時間過後恢復
- [ ] T014 實作 src/guided_buzz/realtime/hub.py：/ws 端點必須在 5 秒內收到 auth 訊息，否則以代碼 4401 斷線；連線依 Session 登記；提供 send_to_teacher、send_to_team、send_to_all、close_team(code 4403)；送出失敗的連線自動移除（contracts/websocket.md）
- [ ] T015 實作 src/guided_buzz/activity/state.py：引擎內部的 TeamState、UnitState、Cooldown（data-model.md Cooldown.team_id、Cooldown.until_monotonic、Cooldown.until_utc、Cooldown.trigger_submission_id），以及送出紀錄的記憶體表示（data-model.md Submission.id、Submission.unit_key、Submission.team_id、Submission.received_at、Submission.invalidated_at），並提供衍生值：單位狀態、組別成功數
- [ ] T016 修改 src/guided_buzz/api/app.py：啟動時呼叫 mark_unfinished_interrupted()（research.md R7）；掛上 /ws 與新的路由；前端所有請求都帶 X-Window-Id

**Checkpoint**: 001 的測試與 T004–T016 的測試全部通過

---

## Phase 3: User Story 1 - 老師控制活動階段並即時同步 (Priority: P1) 🎯 MVP

**Goal**: 建立活動、學生以代碼加入、開始與結束搶答，所有視窗在 2 秒內同步；結束時保存結果

**Independent Test**: 1 個老師視窗加 3 個學生視窗，切換階段後所有人在 2 秒內看到相同階段；階段只能往前（quickstart V1、V2、V6 第 1 點、V7）

### Tests for User Story 1 ⚠️

- [ ] T017 [P] [US1] 撰寫 tests/unit/test_engine.py 的階段測試：preparing→running→ended；不允許的轉換拋出 InvalidState；沒有組別或單位時不能開始；end() 遇到資料庫寫入失敗時維持 running（以注入的失敗 repository 模擬）
- [ ] T018 [P] [US1] 撰寫 tests/integration/test_activity_api.py：建立活動回 201 並帶代碼；學習單未確認回 409；已有進行中的活動回 409 ACTIVITY_IN_PROGRESS；組名重複、空白、過長或組數超過上限回 422；學生 Token 呼叫老師端點回 401；start 與 end 的狀態碼；regenerate-code 後舊代碼回 401、舊 Token 的 WebSocket 收到 session_revoked
- [ ] T019 [P] [US1] 撰寫 tests/integration/test_student_api.py 的加入測試：正確代碼回 200；錯誤代碼回 401 且回應不含任何組別資訊；同一視窗連續錯 5 次回 429，另一個 X-Window-Id 仍可加入；同一組多個視窗都能加入
- [ ] T020 [P] [US1] 撰寫 tests/integration/test_realtime.py：沒有送 auth 被斷線（4401）；老師與學生連線後都先收到 snapshot；start 後所有連線收到 phase_changed；斷線重連後重新收到 snapshot；同一個 TestClient 開兩個連線，分別是老師與第一組，彼此身分不互相影響（FR-005a）
- [ ] T021 [P] [US1] 撰寫 tests/integration/test_restart.py：在同一個資料庫上建立兩個 app 實例；第一個實例中 running 的活動，在第二個實例啟動後變成 interrupted，公開的 phase 端點回傳 interrupted，舊代碼無法加入；已 ended 的活動結果完整保留

### Implementation for User Story 1

- [ ] T022 [US1] 實作 src/guided_buzz/activity/engine.py 的骨架：ActivityEngine(activity, units, teams, repo, clock)，以 asyncio.Lock 保護所有操作；start()、end() 依 data-model.md Activity.phase 的轉換表處理；end() 在鎖內以一筆交易呼叫 repo 寫入（research.md R7），成功後才改變階段；所有操作都回傳「事件清單」，不直接推播
- [ ] T023 [US1] 在 src/guided_buzz/storage/activities.py 實作 persist_results(activity_id, submissions)：以一筆交易寫入 submissions 與 submission_answers，並把 phase 設為 ended（data-model.md Submission.rank、Submission.outcome、Submission.answers）
- [ ] T024 [US1] 實作 src/guided_buzz/activity/registry.py：保存目前的引擎，確保同時只有一場活動（research.md R9）；create() 呼叫 build_units 與 codes，並寫入資料庫；保存代碼明文供老師檢視
- [ ] T025 [US1] 實作 src/guided_buzz/realtime/views.py 的階段相關部分：老師快照（含組別代碼）與學生快照（只有本組資訊與單位清單），以及 phase_changed 事件依身分分送
- [ ] T026 [US1] 實作 src/guided_buzz/api/activity_routes.py：POST /api/activities、/start、/end、/teams/{team_id}/regenerate-code、GET /api/activities、GET /api/activities/{id}（目前只含階段與組別），依 contracts/http-api.md 回應；操作後把引擎回傳的事件交給 hub 推播
- [ ] T027 [US1] 實作 src/guided_buzz/api/student_routes.py 的 POST /api/join（以 X-Window-Id 計算輸錯）與公開的 GET /api/activities/{id}/phase
- [ ] T028 [US1] 實作 src/guided_buzz/web/static/teacher.html、teacher.js：選學習單、輸入組名（每行一組）、可選擇覆寫 N、K 與是否啟用公平機制、顯示代碼並提供重新產生按鈕、開始與結束按鈕、顯示目前階段；Token 與活動 ID 存在 sessionStorage；WebSocket 斷線時自動重連
- [ ] T029 [US1] 實作 src/guided_buzz/web/static/student.html、student.js：產生並保存視窗 ID、輸入代碼加入、顯示組名與階段；重新連線時先查詢 phase 端點，若為 interrupted，顯示「活動已中斷，請老師重新建立」
- [ ] T030 [US1] 記錄階段變更、加入成功與失敗、代碼重新產生的 log（只記活動 ID、組別 ID 與結果；不記錄代碼與 Token），寫在 src/guided_buzz/api/activity_routes.py 與 src/guided_buzz/api/student_routes.py

**Checkpoint**: T017–T021 通過；quickstart V1、V2、V7 通過

---

## Phase 4: User Story 2 - 組別送出答案並得知是否搶答成功 (Priority: P1)

**Goal**: 搶答中，各組送出單一題目或整個題組，伺服器依處理順序判定成功與順位，並立即回覆

**Independent Test**: 多組同時送出同一單位，恰好 1 組成功、順位不重複，重複 100 次都成立（quickstart V3 第 1、2、4、5 點）

**Depends on**: US1（需要 running 的活動）

### Tests for User Story 2 ⚠️

- [ ] T031 [P] [US2] 在 tests/unit/test_engine.py 撰寫送出測試：第一筆 success、rank 1；第二筆 not_won、rank 2；research.md R5 的檢查 1、2、4、5、6 各有一個被拒案例（不在搶答時間、代碼版本過期、單位不存在、題組少一題或多一題、答案空白或只有空白、長度剛好等於上限通過、上限加 1 被拒、同一組重複送出）；被拒的送出不產生任何紀錄
- [ ] T032 [P] [US2] 撰寫 tests/unit/test_engine_concurrency.py：5 組以 asyncio.gather 同時對同一單位送出，重複 100 次，每次都恰好 1 筆 success，rank 為 1..5 且不重複；同一組的 3 個視窗同時送出，只接受 1 筆；結束搶答與送出同時發生時，結束後才處理的送出被拒
- [ ] T033 [P] [US2] 在 tests/integration/test_student_api.py 撰寫 POST /api/submissions 測試：200 回應的訊息正確；請求中多出 client_time、outcome 等欄位回 422；各種錯誤代碼對應 contracts/http-api.md 的狀態碼；同組的其他視窗收到 team_submission

### Implementation for User Story 2

- [ ] T034 [US2] 在 src/guided_buzz/activity/engine.py 實作 submit(team_id, code_version, unit_key, answers)：在鎖內依 research.md R5 的 1–7 步處理（第 3 步冷卻檢查先留下呼叫 fairness 的位置，在 US5 實作）；寫入 data-model.md Submission.id、Submission.unit_key、Submission.team_id、Submission.answers、Submission.rank、Submission.outcome、Submission.received_at；回傳結果與事件（team_submission 給該組，submission 給老師）
- [ ] T035 [US2] 在 src/guided_buzz/api/student_routes.py 實作 POST /api/submissions（pydantic 設定 extra="forbid"）與 GET /api/me（只含本組資料，contracts/http-api.md）
- [ ] T036 [US2] 在 src/guided_buzz/realtime/views.py 加入 submission（給老師）與 team_submission（給該組）的事件產生
- [ ] T037 [US2] 在 student.html、student.js（src/guided_buzz/web/static/）加入作答區：列出單位標示；題組一次顯示所有題目的輸入框；送出後顯示「搶答成功！」或「未搶到，第 N 順位」；已送出的單位停用輸入；錯誤訊息逐條顯示

**Checkpoint**: T031–T033 通過；quickstart V3 第 1、2、4、5 點通過

---

## Phase 5: User Story 3 - 老師即時檢視作答狀況與結果 (Priority: P2)

**Goal**: 老師即時看到所有送出、順位、成功者與各組成功數；可以判定無效並由下一順位遞補；結束後可檢視結果

**Independent Test**: 多組送出時，老師畫面在 2 秒內更新；判定無效後由下一順位正確遞補（quickstart V3 第 6 點、V5）

### Tests for User Story 3 ⚠️

- [ ] T038 [P] [US3] 在 tests/unit/test_engine.py 撰寫判定無效的測試：有下一順位時遞補；沒有下一順位時，搶答中重新開放，被判無效的組送出得到 ALREADY_SUBMITTED，其他組可以成功；已結束時標為無人搶答；連續判定無效兩次；對沒有成功者的單位判定無效回 InvalidState；成功數重新計算
- [ ] T039 [P] [US3] 在 tests/integration/test_activity_api.py 撰寫老師檢視與 invalidate 的測試：GET /api/activities/{id} 包含所有送出；在已結束的活動上判定無效後，重新讀取資料庫，結果已更新；學生 Token 呼叫 invalidate 回 401；被判無效與遞補成功的組分別收到 invalidated、promoted，訊息中不含他組答案

### Implementation for User Story 3

- [ ] T040 [US3] 在 src/guided_buzz/activity/engine.py 實作 invalidate(unit_key)：依 research.md R6 處理，設定 data-model.md Submission.outcome 與 Submission.invalidated_at；活動已結束時呼叫 repo 以一筆交易更新；回傳 invalidated 與 promoted 事件（冷卻的解除在 US5 接上）
- [ ] T041 [US3] 在 src/guided_buzz/storage/activities.py 實作 update_invalidation(activity_id, invalidated_id, promoted_id | None)，以一筆交易完成
- [ ] T042 [US3] 擴充 src/guided_buzz/api/activity_routes.py：POST /units/{unit_key}/invalidate；GET /api/activities/{id} 補上所有送出、各組成功數與冷卻狀態
- [ ] T043 [US3] 在 src/guided_buzz/realtime/views.py 加入老師的完整快照與 invalidated、promoted 事件
- [ ] T044 [US3] 在 teacher.html、teacher.js（src/guided_buzz/web/static/）加入即時監控表：每個單位一列，列出所有送出、順位與成功者，成功的送出旁提供「判定無效」按鈕（附確認步驟，不使用 confirm()）；另有各組成功數

**Checkpoint**: T038、T039 通過；quickstart V5 通過

---

## Phase 6: User Story 4 - 學生在結束後檢視結果、結束前看不到他組 (Priority: P2)

**Goal**: 結束前，伺服器不讓學生取得任何他組資料；結束後，學生可以檢視完整結果

**Independent Test**: 搶答中以學生身分嘗試所有可能的管道取得他組資料，全部被拒或拿不到；結束後學生可以看到結果（quickstart V3 第 3 點、V6）

### Tests for User Story 4 ⚠️

- [ ] T045 [P] [US4] 撰寫 tests/integration/test_isolation.py：搶答中，第二組的 /api/me、/api/activities/{id}/results（回 409 NOT_ENDED）、老師端點（回 401），以及 WebSocket 上收到的所有訊息，都不含第一組的 team_id、組名、答案、順位，也看不出任何單位已被搶走；結束後，/results 回 200，內容包含成功組別與答案
- [ ] T046 [P] [US4] 在 tests/unit/test_engine.py 撰寫 view_for_team 的測試：搶答中只含本組的送出；結束後包含每個單位的成功組別與答案、各組成功數，並把沒有成功者的單位標為無人搶答

### Implementation for User Story 4

- [ ] T047 [US4] 在 src/guided_buzz/activity/engine.py 實作 view_for_team(team_id) 與 results_view(role)，依 FR-014、FR-016 過濾資料
- [ ] T048 [US4] 在 src/guided_buzz/api/student_routes.py 實作 GET /api/activities/{id}/results：老師 Token 或屬於這場活動的學生 Token 才能讀取；活動已結束時從資料庫讀取，未結束時回 409
- [ ] T049 [US4] 在 src/guided_buzz/realtime/views.py 補上活動結束時給學生的結果快照
- [ ] T050 [US4] 在 student.html、student.js（src/guided_buzz/web/static/）加入結果頁：每個單位的成功組別與答案或「無人搶答」，以及各組成功數

**Checkpoint**: T045、T046 通過；quickstart V3 第 3 點、V6 第 1、2 點通過

---

## Phase 7: User Story 5 - 公平機制 (Priority: P3)

**Goal**: 組別即時送出成功後，若成功數比全班最少者多 K 題以上，就冷卻 N 秒；判定無效時一併處理冷卻

**Independent Test**: K=2、N=10，第一組領先 2 題後進入冷卻，冷卻中送出被拒且不佔順位，時間到後恢復（quickstart V4）

### Tests for User Story 5 ⚠️

- [ ] T051 [P] [US5] 撰寫 tests/unit/test_fairness.py（假時鐘）：涵蓋 spec.md US5 驗收情境 1–5；只有 1 組時不觸發；停用公平機制時不觸發；冷卻在 N 秒的前一刻仍有效、到了 N 秒就解除；題組成功算 1 題
- [ ] T052 [P] [US5] 在 tests/unit/test_engine.py 撰寫冷卻與判定無效的互動測試：觸發冷卻的成功被判無效時，冷卻立即解除；遞補成功不觸發冷卻；冷卻中被拒的送出不佔順位，冷卻結束後同一組仍可送出該單位
- [ ] T053 [P] [US5] 撰寫 tests/integration/test_fairness_simulation.py：以固定亂數種子模擬一組反應最快的 6 組活動，各跑一次啟用與停用公平機制，啟用時「至少成功一題的組數」較多（SC-006）

### Implementation for User Story 5

- [ ] T054 [US5] 實作 src/guided_buzz/activity/fairness.py：should_cooldown(team_wins, min_wins, Activity.cooldown_lead, Activity.fairness_enabled) 與 remaining(Cooldown.until_monotonic, now)，皆為純函式，參數定義見 data-model.md
- [ ] T055 [US5] 在 src/guided_buzz/activity/engine.py 接上冷卻：submit 第 3 步檢查冷卻（回傳 COOLDOWN 與剩餘秒數）；第 8 步依 data-model.md Activity.cooldown_seconds 建立 Cooldown（trigger_submission_id 指向觸發的成功送出）；invalidate 時，若被判無效的是 Cooldown.trigger_submission_id，就解除冷卻；回傳 cooldown 事件
- [ ] T056 [US5] 在 src/guided_buzz/realtime/views.py 與 teacher.js、student.js（src/guided_buzz/web/static/）加入冷卻顯示：學生看到本組的倒數，老師看到所有組的冷卻狀態；倒數以伺服器回傳的剩餘秒數為準，前端只負責顯示

**Checkpoint**: T051–T053 通過；quickstart V4 通過

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T057 實作 src/guided_buzz/results/sqlite_provider.py：SqliteActivityResultsProvider 實作 001 的 ActivityResultsProvider，從已結束的活動組出 001 data-model.md 的 ActivityResult 與 SubmissionRecord（team_name 取自 Team.name，outcome 取自 Submission.outcome）；requester 不是活動老師時拋出 NotFound；未結束的活動回傳 ended=False
- [ ] T058 修改 001 的 src/guided_buzz/api/result_routes.py 與 web/static：預設使用 SqliteActivityResultsProvider，只有設定 GB_RESULTS_DIR 時才使用 JSON 實作；寫回與匯出畫面改成從 GET /api/activities 選擇已結束的活動（FR-017）
- [ ] T059 [P] 撰寫 tests/integration/test_results_provider.py：完成一場活動（含題組、判定無效與遞補）後，001 的寫回與 CSV 結果和 002 的結果檢視一致；未結束的活動在寫回時得到 409
- [ ] T060 [P] 撰寫 tests/integration/test_latency.py：1 個老師與 12 個學生 WebSocket 連線，量測從 start 到所有連線收到 phase_changed 的時間 < 2 秒，以及送出後老師收到 submission 的時間 < 2 秒（SC-001）
- [ ] T061 [P] 擴充 001 的 tests/integration/test_no_secrets.py：完成一場搶答活動後，caplog 中不含任何組別代碼、學生 Token、老師 Token 與答案字串
- [ ] T062 [P] 更新 README.md：加入搶答活動的操作流程、新增的環境變數名稱與用途、固定 workers=1 的原因、以多個視窗模擬的方法
- [ ] T063 對照實作更新 diagrams/002-online-buzz-activity/ 的 .puml 並重新產生 PNG，確認 9 張圖與最終程式碼一致（Constitution 原則 VII 實作階段驗證）
- [ ] T064 執行 `uv run pytest -v` 與 quickstart.md 的 V1–V7 人工驗證，並回報測試指令、通過與失敗數、失敗輸出及人工驗證結果（Constitution 原則 VI）

---

## Dependencies & Execution Order

### Phase Dependencies

- **前提**：001 tasks T001–T033 已完成
- **Setup (Phase 1)**：T001 是後續所有工作的前提
- **Foundational (Phase 2)**：依賴 Setup
- **US1 (Phase 3)**：依賴 Foundational
- **US2 (Phase 4)**：依賴 US1（需要能開始活動）
- **US3 (Phase 5)**：依賴 US2（需要有送出才能判定無效）
- **US4 (Phase 6)**：依賴 US2；可以和 US3 平行
- **US5 (Phase 7)**：依賴 US2；T052、T055 中與判定無效互動的部分依賴 US3
- **Polish (Phase 8)**：依賴 US1–US4；T057、T058 另外依賴 001 的 US2、US3（001 tasks T034–T047）

### Within Each User Story

- 先寫測試、確認失敗，再實作
- 引擎（純邏輯）→ 儲存 → API 路由 → 推播內容 → 前端

### Parallel Opportunities

- Phase 2：T005、T006、T007、T008、T009、T013 平行
- 各使用者情境內標 [P] 的測試可以同時撰寫
- US3 與 US4 可以平行，但兩者都會修改 engine.py 與 realtime/views.py，要依序合併
- Polish：T059、T060、T061、T062 平行

---

## Parallel Example: User Story 1

```bash
Task: "撰寫 tests/unit/test_engine.py 的階段測試"
Task: "撰寫 tests/integration/test_activity_api.py"
Task: "撰寫 tests/integration/test_student_api.py 的加入測試"
Task: "撰寫 tests/integration/test_realtime.py"
Task: "撰寫 tests/integration/test_restart.py"
```

---

## Implementation Strategy

### MVP（US1 + US2）

US2 依賴 US1，而且兩者都是 P1，所以 MVP 是 Phase 1 → Phase 2 → US1 → US2。
**STOP and VALIDATE**：執行 `uv run pytest`，並完成 quickstart V1、V2、V3、V7。
此時已能進行一場最基本的線上搶答，並保存結果。

### Incremental Delivery

1. MVP（US1 + US2）
2. US3：老師監控與判定無效
3. US4：結果檢視與隔離驗證（可以和 US3 同時進行）
4. US5：公平機制
5. Polish：接上 001 的寫回與匯出、驗證延遲、檢查 log 中沒有機敏資料
6. 每完成一個情境，都要回報測試指令、結果與人工驗證步驟

---

## Notes

- 本清單的 T 編號與 001 的 tasks.md 各自獨立；提到 001 的任務時，一律寫成「001 tasks Txxx」
- 001 的 CSV 為 5 欄（題號、組別、答案、搶答順位、結果），T059 依此比對
