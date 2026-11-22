# Implementation Plan: 學習單匯入、答案寫回與結果匯出

**Branch**: `001-guided-notes-import`（目前在 `master` 工作，尚未建立分支） | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-guided-notes-import/spec.md`

## Summary

老師上傳由 Google Sheets 下載的 .xlsx 學習單後，系統依「表頭（題號／題目／作答）→ 題目列 → 作答範圍內的空白區段」
規則找出填空格，依出現順序編上系統題號，並以題號欄的縱向合併辨識題組，產生預覽供老師確認。
活動結束後，系統以伺服器保存的搶答結果，直接修改 .xlsx 的 XML，只改寫目標儲存格，產生新檔讓老師下載；
結果也可以匯出為 UTF-8 BOM 的 CSV。搶答結果透過唯讀介面 `ActivityResultsProvider` 取得，
在 002 完成前，以 JSON 結果檔的實作進行測試與驗證。

## Technical Context

**Language/Version**: Python 3.12（以 `uv` 與 `.python-version` 固定版本，見 research R1）

**Primary Dependencies**: FastAPI、uvicorn、pydantic v2、openpyxl（解析）、lxml（寫回 XML）、python-multipart、python-dotenv

**Storage**: SQLite（標準庫 `sqlite3`）存放中繼資料；原始檔與寫回檔以 UUID 命名，存放在 `GB_DATA_DIR`（research R6）

**Testing**: pytest、FastAPI TestClient；測試資料為範例 A、B，以及測試時用 openpyxl 動態產生的變體（research R11）

**Target Platform**: 單一 Linux 或 macOS 電腦，伺服器只監聽 `127.0.0.1`，以多個瀏覽器視窗操作

**Project Type**: Web 應用：單一 Python 後端，加上由後端提供的靜態前端（HTML + 原生 JavaScript）

**Performance Goals**: 100 題以內的學習單，從上傳到看到預覽不超過 10 秒（SC-002，實際預期遠低於 1 秒）

**Constraints**: 寫回後非填空格內容 0 處被改動（SC-003）；不使用外部服務或帳號；不寫死路徑或常數；
機敏資料只放環境變數

**Scale/Scope**: 1 位老師；每份學習單 ≤ 500 題、≤ 10 MB（可設定）；約 3 個老師頁面（登入、匯入與確認、寫回與匯出）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 檢查結果 | 依據 |
|------|---------|------|
| I. 不寫死資料與設定 | ✅ | 表頭標籤、上限、資料目錄、連接埠、Token 期限都從 `GB_*` 環境變數讀取（R10）；解析不依賴儲存格位置（R3）；測試使用 2 份範例加上動態產生的變體 |
| II. 輸入驗證與清楚錯誤 | ✅ | 定義 10 種錯誤代碼，全部附上繁體中文訊息與位置（data-model）；一次收集所有問題；統一錯誤格式，不含堆疊追蹤（contracts） |
| III. 機敏資料只放環境變數 | ✅ | 老師密碼只來自 `GB_TEACHER_PASSWORD`，未設定時拒絕啟動；`.env` 列入 `.gitignore`；只提供含佔位值的 `.env.example`；log 不記密碼、Token、答案（R12） |
| IV. 伺服器權威與權限隔離 | ✅ | 所有端點都由伺服器驗證 Token；非擁有者回應 404；寫回只用伺服器保存的判定結果（FR-018）；每個視窗以 sessionStorage 保存獨立身分（R9） |
| V. 模組化與單一定義 | ✅ | 共用結構只放在 `domain/models.py`；parser、writeback、export 是純函式模組；與 002 透過 `ActivityResultsProvider` 介面串接（diagrams 第 6 節） |
| VI. 測試與驗證回報 | ✅ | 每個使用者情境都有正常與邊界案例（quickstart）；`uv run pytest` 一個指令即可執行；quickstart 附有人工驗證步驟 V1–V7 |
| VII. 圖表先行 | ✅ | [diagrams.md](./diagrams.md) 含 3 張循序圖（標示伺服器判定與權限檢查點）、類別圖、狀態圖、模組相依圖；**實作前需審閱** |
| 範圍限制（單機、多視窗） | ✅ | 只監聽本機位址；身分存在 sessionStorage，各視窗互不影響；不使用 Google API |

**Post-design re-check（Phase 1 後）**：✅ 全部通過。設計過程中做了兩個需要確認的決定，都不違反 Constitution：
（1）CSV 新增第 5 欄「結果」（R7，已確認並寫入 FR-020）；
（2）寫回不使用 openpyxl 存檔，改為直接修改 XML（R4），以達成 SC-003。

## Project Structure

### Documentation (this feature)

```text
specs/001-guided-notes-import/
├── plan.md              # 本文件
├── research.md          # Phase 0：技術決策
├── data-model.md        # Phase 1：資料模型
├── diagrams.md          # Phase 1：圖表（Constitution 原則 VII）
├── quickstart.md        # Phase 1：執行與驗證指南
├── contracts/
│   ├── http-api.md          # HTTP API
│   └── results-provider.md  # 與 002 之間的內部介面
├── checklists/requirements.md
└── tasks.md             # Phase 2（/speckit-tasks 產生）
```

### Source Code (repository root)

```text
pyproject.toml               # 相依套件、pytest 設定
.python-version              # 3.12
.env.example                 # 只含佔位值
.gitignore                   # .env、var/、.venv/ 等

src/guided_buzz/
├── __main__.py              # 啟動 uvicorn（host/port 來自設定）
├── config.py                # 讀取並驗證 GB_* 環境變數；缺少必要值時拒絕啟動
├── domain/
│   ├── models.py            # 共用資料結構與列舉（唯一定義處）
│   ├── errors.py            # ImportIssue、錯誤代碼與繁體中文訊息
│   └── ports.py             # ActivityResultsProvider 介面
├── worksheet/
│   ├── parser.py            # bytes → ParsedWorksheet | list[ImportIssue]（純函式）
│   └── writeback.py         # bytes + {CellRef: 答案} → bytes（純函式，XML 修改）
├── export/
│   └── csv_export.py        # ActivityResult + ParsedWorksheet → CSV（純函式）
├── results/
│   └── json_provider.py     # JsonFileResultsProvider
├── storage/
│   ├── db.py                # SQLite 連線與資料表建立
│   ├── worksheets.py        # 學習單 repository
│   └── files.py             # 以 UUID 存取原始檔與寫回檔
├── auth/
│   └── teacher.py           # 密碼驗證、Token 簽發與驗證、錯誤次數限制
├── api/
│   ├── app.py               # 建立 FastAPI app、錯誤處理、靜態檔
│   ├── schemas.py           # 請求與回應 schema（由 domain 模型轉換）
│   ├── auth_routes.py
│   ├── worksheet_routes.py
│   └── result_routes.py     # 寫回、下載、CSV
└── web/static/
    ├── index.html           # 老師登入、匯入與確認、寫回與匯出
    ├── app.js               # Token 存在 sessionStorage
    └── style.css

tests/
├── fixtures/worksheets/     # sample_a.xlsx、sample_b.xlsx
├── factories.py             # 用 openpyxl 動態產生變體學習單
├── unit/
│   ├── test_parser.py
│   ├── test_writeback.py
│   ├── test_csv_export.py
│   ├── test_json_provider.py
│   └── test_config.py
└── integration/
    ├── test_worksheet_api.py
    ├── test_result_api.py
    └── test_auth.py
```

**Structure Decision**: 採用單一 Python 專案，並以 `src/` 結構組織。前端是後端提供的靜態檔，所以不拆成前後端兩個專案。
002 會在同一個套件中新增 `activity/`、`realtime/` 等模組，並沿用 `domain/`、`auth/`、`storage/`、`config.py`。

## Complexity Tracking

無違反 Constitution 的項目。
