# 交接：002 線上分組搶答活動

**寫給**：接手實作 002 的組員 | **日期**：2026-11-23 | **期限**：11/30（一）00:00（期末專題說明）

001（匯入學習單、寫回答案、匯出 CSV）已經完成並在真實的 Google Sheets 上驗證過。接下來要做 002：老師開始與結束搶答、
各組送出答案、最快的組別成功、結束前看不到他組的作答、階段即時同步。規格、計畫和任務清單都寫好了，照
[tasks.md](./tasks.md) 的 T001–T064 依 Phase 實作即可。

## 目前狀態

| 項目 | 狀態 |
|------|------|
| `main` | `608bd3c`，CI 通過，130 個測試全過 |
| 001 | 57 個任務全部完成，真實環境人工驗證 V1–V8 通過（[verification.md](../001-guided-notes-import/verification.md)） |
| 002 文件 | spec、plan、research、data-model、contracts（HTTP、WebSocket）、quickstart、tasks 都已完成 |
| 002 圖表 | 9 張 PlantUML（`.puml` 和 PNG）已完成，**尚未審閱**（T001 要做） |
| 002 程式碼 | 還沒開始寫 |

## 建議閱讀順序

1. 期末專題說明：需求的來源
2. [constitution.md](../../.specify/memory/constitution.md)：7 條原則，特別是 III（機敏資料）、IV（伺服器權威與權限隔離）、
   VI（測試與回報）、VII（先畫 PlantUML 圖再實作）
3. [spec.md](./spec.md)：5 個使用者情境，以及 Clarifications 裡已經定案的決定：
   - 題組整組一起搶答
   - 所有題目同時開放
   - 公平機制：領先 K 題就冷卻 N 秒
   - 老師可以判定答案無效，由下一順位遞補
   - 每組一個組別代碼
   - 伺服器重啟後，未結束的活動作廢
4. [plan.md](./plan.md)、[tasks.md](./tasks.md)、[diagrams.md](./diagrams.md)

## 第一次設定環境

```bash
git clone https://github.com/silverwind63/SEFinal.git
cd SEFinal
uv sync
cp .env.example .env
```

1. 編輯 `.env`：`GB_TEACHER_PASSWORD` 自己訂一組，`GB_GOOGLE_OAUTH_CLIENT_FILE` 指向你自己的 OAuth client JSON（見下一步）。
2. **Google OAuth 自己建一套**：照 [README](../../README.md)「一次性設定：Google OAuth」，用你自己的 Google 帳號建立
   Google Cloud 專案和 OAuth client，再把你自己的 Gmail 加到**你自己專案**的「測試使用者」。
   client JSON 和 token 檔不要跟別人要，也不要傳給別人。
3. 執行 `uv run python -m guided_buzz login-google`，登入你的 Google 帳號。
4. 用你自己的帳號，把期末專題說明附的範例 A、B 各複製一份到你的雲端硬碟。啟動伺服器後，匯入並確認範例 B 的副本：
   002 的 quickstart 以它為前提，會產生 4 個搶答單位（G1、G2、Q5、Q6）。
5. 執行 `uv run pytest`，應該是 130 passed。

只跑自動化測試**不需要** Google，測試一律用 `FakeSheetsGateway`。只有手動操作時才需要：伺服器沒登入 Google 會拒絕啟動，
而且建立活動前，必須先匯入並確認一份學習單。

專案如果放在 iCloud 同步的資料夾（桌面、文件），可能遇到 `No module named guided_buzz`，解法在 README 的「常見問題」。

## SpecKit 設定

`.specify/feature.json` 不進版控，SpecKit 靠它判斷目前在做哪個 feature。開工前先指向 002：

```bash
printf '{\n  "feature_directory": "specs/002-online-buzz-activity"\n}\n' > .specify/feature.json
```

接著執行 `/speckit-implement`，建議附上「請依 Phase 來完成任務，前一階段測試通過後才能進入下一階段。」

## 001 已有、可以直接沿用的部分

不要另外再寫一份（Constitution 原則 V）。

| 用途 | 位置 | 說明 |
|------|------|------|
| 設定 | `config.py` 的 `load_settings`、`Settings` | 新的 `GB_*` 變數加在這裡（T004）；錯誤訊息只列變數名稱，不印出值 |
| 老師登入與 Token | `auth/teacher.py` 的 `TeacherAuth`、`api/deps.py` 的 `require_teacher` | owner 固定是 `"teacher"`；學生 Session（T012）從這裡擴充 |
| 錯誤格式 | `domain/errors.py` 的 `DomainError`、`api/app.py` 的 `STATUS` | 新的錯誤代碼要在 `STATUS` 補上 HTTP 狀態碼，沒補的一律回 422 |
| 資料庫 | `storage/db.py` 的 `Database` | `SCHEMA` 用 `CREATE TABLE IF NOT EXISTS`；新的資料表加在這裡（T010），寫入用 `transaction()` |
| 已確認的學習單 | `storage/worksheets.get(db, id, owner)` | 回傳的 `ws.parsed` 是 `ParsedWorksheet`（`questions`、`groups`），T007 用它產生搶答單位 |
| 搶答結果型別 | `domain/models.py` 的 `ActivityResult`、`SubmissionRecord`、`SubmissionOutcome` | 002 直接引用，不要重複定義 |
| 測試工具 | `tests/conftest.py`、`tests/fakes.py`、`tests/factories.py`、`tests/fixtures/sheets/` | `settings`、`client` 等 fixture；`FakeSheetsGateway`；`standard_sheet()` 產生各種排版；範例 A、B 的真實 API 快照 |

## 和 001 的對接點（最重要）

001 的寫回（`POST /api/worksheets/{id}/writeback`）和匯出（`GET /api/activities/{id}/results.csv`）
都透過 `ActivityResultsProvider.get_result(activity_id, requester)` 取得搶答結果。介面定義在 `domain/ports.py`，
合約見 [results-provider.md](../001-guided-notes-import/contracts/results-provider.md)。目前接的是替身
`JsonFileResultsProvider`，從 `GB_RESULTS_DIR` 讀取手寫的 JSON 結果檔。

002 要把它換成正式版本：

- **T057** `SqliteActivityResultsProvider`：從已結束的活動組出 `ActivityResult`。
  - 活動不存在，或 requester 不是活動的老師 → 拋出 `NotFound`
  - 活動還沒結束 → `ended=False`（001 會回 409）
  - `worksheet_id` 要是建立活動時選的那份學習單；001 會比對，不符時回「這場活動不屬於這份學習單」
  - `submissions` 依 `(question_nos[0], rank)` 排序；題組的 `question_nos` 是整組的題號，`answers` 的鍵必須等於 `question_nos`
  - 每個搶答單位最多一筆 `success`（`ActivityResult` 建構時會檢查）
- **T058**：`create_app` 預設接 SQLite 版本，只有設定 `GB_RESULTS_DIR` 時才用 JSON 版本；寫回與匯出畫面改成從
  `GET /api/activities` 選擇已結束的活動。
- **T059**：完整跑完一場活動後，001 寫回與 CSV 的內容要和 002 的結果檢視一致。

寫回是期末專題說明的必要功能，這段建議在 US2 完成後就接上，不要拖到最後。

## 容易踩的雷

- `api/app.py` 最後的 `app.mount("/", StaticFiles(...))` 會接走所有路徑，所以新的 router 和 `/ws` 都要在它**之前**掛上。
- 001 已經用了 `/api/activities/{id}/results.csv`；002 要新增 `/api/activities/{id}/results`（JSON）和 `/phase`，
  路徑不衝突，但新增時注意不要蓋掉。
- 伺服器是單一程序：uvicorn 固定 `workers=1`（T002）。活動狀態放在記憶體，所有判定都在同一把 `asyncio.Lock` 內進行。
- 「結束前學生看不到他組」是期末專題說明的必要需求：推播要依身分分別產生，`test_isolation.py`（T045）是驗收重點。
- 機敏資料：
  - 組別代碼、Token、答案都不寫進 log
  - 資料庫只存組別代碼的雜湊
  - Token 不放在 WebSocket 網址上（research R2）
  - T061 會檢查 log
- 測試一律不連網，任何測試都不可以呼叫真的 Google。
- OAuth 同意畫面在「測試中」狀態時，授權大約 7 天就失效。Demo 前要在 Demo 用的那台電腦重新執行 `login-google`。

## 工作流程

1. 從 `main` 開分支（例如 `feat/002-us1`），每完成一個 Phase 或使用者情境就開一個 PR。
2. 每個 Phase 都有 Checkpoint；前一個 Phase 的測試全部通過，才進入下一個。
3. PR 要等 GitHub Actions（`uv run pytest`）通過才 merge。repo 沒有開 auto-merge 和分支保護，CI 有沒有通過要自己確認。
4. 修改 `.puml` 後，在 repo 根目錄重新產生 PNG，並和 `.puml` 一起提交：`plantuml -tpng "./diagrams/**/*.puml"`
   （需要 `brew install plantuml`）。
5. 完成後依原則 VI 回報測試指令與結果；照 002 quickstart 做 V1–V7 人工驗證，結果記錄在 `specs/002-online-buzz-activity/verification.md`
   （格式可以參考 001 的 verification.md）。

時間不夠時：「判定無效與遞補」（US3 的 invalidate，T038–T044 裡相關的部分）是組內自己加的需求，可以最後做。
其他情境都對應期末專題說明的要求，包括公平機制、老師即時檢視、學生在結束後檢視結果。
