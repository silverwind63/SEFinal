# Implementation Plan: 入口頁與老師頁面對齊 OpenSpec 組

**Branch**: `003-align-entry-pages`（從 `main` 開功能分支） | **Date**: 2026-11-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-align-entry-pages/spec.md`；需求來源為 [OpenSpec 組交接文件](./handoff-from-openspec.md)

**Depends on**: [001](../001-guided-notes-import/plan.md)、[002](../002-online-buzz-activity/plan.md)（皆已完成）

## Summary

首頁 `/` 改為學生頁：加入組別、作答、看結果都在同一頁，並提供「我是老師」按鈕。老師的所有功能合併到 `/teacher` 單一頁面，
依序是匯入學習單、已確認的學習單、建立搶答活動、目前活動（結束後可直接寫回與下載 CSV）、活動清單。

技術做法：
- **頁面路由**：新增 `api/page_routes.py`，回傳兩個頁面，並把舊網址 `/student.html`、`/teacher.html` 以 307 導向新網址。
  這個 router 掛在 StaticFiles 之前。
- **前端合併**：舊的老師入口 `index.html`、`app.js` 併入 `teacher.html`、`teacher.js`。兩頁各自只載入自己的 JS。
- **伺服器端**：判定、權限、推播與資料都不變，唯一的 API 變更是學習單清單多回傳 `confirmed_at`。

## Technical Context

**Language/Version**: Python 3.12（伺服器）；原生 HTML、CSS、JavaScript（瀏覽器端，不使用框架或建置工具）

**Primary Dependencies**: 與 001、002 相同（FastAPI、uvicorn、pydantic v2 等），**不新增任何套件**

**Storage**: SQLite，與 001、002 共用，結構不變；瀏覽器端用 sessionStorage 保存各視窗的身分，鍵名沿用既有設計

**Testing**: pytest＋FastAPI TestClient（頁面網址、導向、各頁載入的程式、`confirmed_at`）；前端互動依 quickstart V1–V8 人工驗證

**Target Platform**: 單一電腦，伺服器只監聽 `127.0.0.1`；同一瀏覽器開多個視窗（1 個老師、多組學生）

**Project Type**: Web 應用（擴充同一個專案）

**Performance Goals**: 沿用 002 SC-001（階段變更與送出結果 2 秒內同步）；頁面切換、清單更新不需要重新整理

**Constraints**:
- 伺服器端的業務行為不變（spec FR-027）。
- 每個視窗獨立身分（Constitution「專案範圍與限制」）。
- 畫面文字使用繁體中文。
- 頁面路由必須掛在 StaticFiles 之前。

**Scale/Scope**: 2 個頁面（學生、老師）；新增 1 個後端模組、1 個測試檔；改寫 2 個 HTML、2 個 JS，刪除 2 個檔案；同步 9 份文件與 3 張元件圖

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 檢查結果 | 依據 |
|------|---------|------|
| I. 不寫死資料與設定 | ✅ | 不新增任何設定或資料；網址為固定的頁面路徑，主機與連接埠仍由 `GB_HOST`、`GB_PORT` 決定 |
| II. 輸入驗證與清楚錯誤 | ✅ | 所有輸入仍送到既有 API 驗證；前端沿用既有的繁體中文錯誤訊息（`formatError` 會逐條列出匯入問題）；新增「此活動沒有任何送出紀錄」與「檢視已中斷活動」的說明（research R8、R9） |
| III. 機敏資料只放環境變數 | ✅ | 不新增任何機敏資料；Token 仍只存在各視窗的 sessionStorage，不出現在網址上，也不寫入 log |
| IV. 伺服器權威、公平一致、權限隔離 | ✅ | 判定、權限檢查與推播內容完全不變；頁面路由不需要登入，因為頁面本身不含任何資料，資料仍要通過既有 API 的權限檢查（contracts/pages.md）；學生頁不載入老師程式（FR-026） |
| V. 模組化與單一定義 | ✅ | 頁面路由獨立成 `api/page_routes.py`，與其他 router 的慣例一致；`WorksheetSummary` 只在 `api/schemas.py` 新增欄位，沒有另外建立新結構；`app.js` 併入 `teacher.js` 後，重複的輔助函式只保留一份（research R4） |
| VI. 測試與驗證回報 | ✅ | 新增 `test_pages.py`，每條網址都有正常與邊界案例（導向、404、不含密碼欄、只載入自己的程式）；`confirmed_at` 有已確認與未確認兩種案例；quickstart V1–V8 對應 E-01～E-10 |
| VII. PlantUML 設計優先 | ✅ | `diagrams/003-align-entry-pages/` 有組件圖、類別圖、2 張時序圖、狀態圖（.puml＋PNG）。本計畫依計畫內容更新了 003 的組件圖，以及 001、002 組件圖中的前端標示（先改圖，再改程式）；見 [diagrams.md](./diagrams.md) |
| 範圍限制（單機、多視窗） | ✅ | 身分存在 sessionStorage，以分頁為範圍，同一瀏覽器的視窗之間互不影響（research R5） |

**Post-design re-check（Phase 1 後）**：✅ 全部通過。有一項需要說明：spec FR-027 允許 `GET /api/worksheets` 新增 `confirmed_at`。
這只是新增唯讀欄位，向下相容（contracts/api-changes.md），不違反「伺服器端行為不變」。

## Project Structure

### Documentation (this feature)

```text
specs/003-align-entry-pages/
├── handoff-from-openspec.md   # 需求來源（OpenSpec 組原文）
├── spec.md
├── plan.md                    # 本文件
├── research.md                # R1–R11
├── data-model.md              # WorksheetSummary.confirmed_at、各視窗狀態
├── diagrams.md                # 5 張圖的索引與預覽
├── quickstart.md              # 自動化測試＋人工驗證 V1–V8（E-01～E-10）
├── contracts/
│   ├── pages.md               # 頁面網址與畫面結構
│   └── api-changes.md         # 相對 001、002 的唯一 API 變更
├── checklists/requirements.md
└── tasks.md                   # /speckit-tasks 產生
```

### Source Code（標示「修改」的是既有檔案）

```text
src/guided_buzz/
├── api/
│   ├── page_routes.py          # 新增：GET / 與 GET /teacher 回傳頁面；/student.html、/teacher.html 以 307 導向（research R1、R2）
│   ├── app.py                  # 修改：include_router(page_routes.router)，放在 app.mount("/", StaticFiles) 之前
│   ├── schemas.py              # 修改：WorksheetSummary 新增 confirmed_at: str | None
│   └── worksheet_routes.py     # 修改：list_worksheets 填入 confirmed_at
└── web/static/
    ├── student.html            # 修改：成為首頁；加入區加上說明與「我是老師」按鈕；只載入 student.js
    ├── student.js              # 修改：加入後隱藏「我是老師」；其餘沿用（身分檢查、重連、失效處理）
    ├── teacher.html            # 修改：合併成單一老師頁，依序 5 個區塊；頁首只有「登出」；只載入 teacher.js
    ├── teacher.js              # 修改：併入 app.js 的匯入、確認、取消；新增已確認清單、活動清單、檢視；
    │                           #       依目前活動顯示寫回與下載；快照只更新檢視中的活動；登出時不重連（research R4–R9）
    ├── style.css               # 修改：按鈕並排、表格等少量樣式
    ├── index.html              # 刪除（research R3）
    └── app.js                  # 刪除（併入 teacher.js）

tests/
└── integration/
    ├── test_pages.py           # 新增：contracts/pages.md 的網址、導向、各頁載入的程式、畫面元素
    └── test_worksheet_api.py   # 修改：GET /api/worksheets 的 confirmed_at（已確認有值、未確認為 null）
```

**Structure Decision**：延續同一個專案。頁面路由跟著既有 router 放在 `api/`；頁面原始檔留在 `web/static/`，保留原檔名，以保留 git 歷史。
直接開舊網址時，由 `page_routes` 的導向路由先攔下，所以不會顯示舊畫面（research R2）。

## 文件與圖表同步清單（FR-029、research R11）

依使用者要求，列出需要同步修改的位置。行號以 `main`（`f004bae`）為準。

**現行文件：直接改寫內容**

| 檔案 | 位置 | 修改內容 |
|------|------|---------|
| `README.md` | 第 73–84 行「頁面網址」表 | 改成兩列：學生頁 `http://127.0.0.1:8000/`；老師頁 `http://127.0.0.1:8000/teacher`（也可以在首頁按「我是老師」）。並註明舊網址會自動導向 |
| `README.md` | 第 122–128 行「1. 匯入並確認學習單」 | 第 1 步改成開啟 `/teacher`，或在首頁按「我是老師」後登入；之後說明都在同一頁 |
| `README.md` | 第 130–141 行「2. 建立搶答活動」 | 刪除第 132 行「點右上角『搶答主控台』或開啟 `/teacher.html`」，改成「在同一頁往下的『建立搶答活動』區塊」；學習單確認後選單會立即更新 |
| `README.md` | 第 153–159 行「4. 結束搶答、寫回學習單、匯出 CSV」 | 刪除第 156 行「回到 `/`，在『寫回答案與匯出結果』選擇活動…」，改成「結束後在『目前活動』直接按『寫回答案』『下載 CSV』；過去的活動從『活動清單』按『檢視』」；0 筆時的訊息改為「此活動沒有任何送出紀錄」 |
| `README.md` | 第 163–175 行「學生操作說明」 | 第 165 行網址改成 `http://127.0.0.1:8000/`；並補充：加入後同一頁就是作答畫面 |
| `specs/001-guided-notes-import/plan.md` | 第 37 行 Scale/Scope；第 114–116 行 `web/static/` 結構 | 「約 3 個老師頁面」改成「老師頁 `/teacher` 一頁（003 起）」；`index.html`、`app.js` 改成 `teacher.html`、`teacher.js`，並註明「003 合併」 |
| `specs/001-guided-notes-import/quickstart.md` | 第 78 行 | 「開啟 `http://127.0.0.1:8000`」改成「開啟 `http://127.0.0.1:8000/teacher`」 |
| `specs/001-guided-notes-import/contracts/http-api.md` | 第 102–104 行 `GET /api/worksheets` | 回應欄位加上 `confirmed_at`（見 contracts/api-changes.md） |
| `specs/001-guided-notes-import/spec.md` | Clarifications（第 11 行起） | 經檢查，沒有提到舊頁面網址或頁面名稱；只補一行：「2026-11-27：老師與學生的入口改由 003 定義（老師 `/teacher`、學生 `/`），本規格的需求不變。」 |
| `specs/002-online-buzz-activity/plan.md` | 第 39 行 Scale/Scope；第 107–109 行 `web/static/` 結構 | 「學生頁面與老師主控台各一個」改成「學生頁 `/` 與老師頁 `/teacher`（003 起）」；檔案說明改成「學生頁（首頁）」「老師頁（含匯入、寫回與匯出）」 |

**歷史文件：保留原文，只在開頭加註**

| 檔案 | 位置 | 修改內容 |
|------|------|---------|
| `specs/001-guided-notes-import/tasks.md` | 標題下方 | 加註：「T032、T041、T047 的老師頁面已在 003 併入 `/teacher`（`teacher.html`、`teacher.js`）；任務內容保留當時的實作紀錄。」 |
| `specs/002-online-buzz-activity/tasks.md` | 標題下方 | 加註：「T028、T029、T037、T044、T050、T056、T058 提到的頁面已在 003 調整：學生頁改為 `/`，老師頁改為 `/teacher`；任務內容保留當時的實作紀錄。」 |
| `specs/002-online-buzz-activity/verification.md` | 第 13 行「操作方式」與 2026-11-27 段落 | 保留原紀錄；在「環境」表格下方加註：「當時的入口為 `/`、`/teacher.html`、`/student.html`；003 起改為學生 `/`、老師 `/teacher`，舊網址會自動導向。」 |

**程式內的提示文字**

| 檔案 | 處理 |
|------|------|
| `src/guided_buzz/web/static/index.html` 第 30 行「學生請開啟 `/student.html`…」 | 整個檔案刪除（research R3），這段提示一併移除 |

**圖表**（本次 plan 已完成：先改圖，再改程式）

| 檔案 | 修改內容 |
|------|---------|
| `diagrams/003-align-entry-pages/01-component.puml`＋PNG | 依計畫補上 `api.page_routes`、各頁載入的 JS、StaticFiles 的順序，以及刪除的檔案 |
| `diagrams/001-guided-notes-import/06-component.puml`＋PNG | 前端元件改成「老師頁 `/teacher`（`teacher.html`、`teacher.js`）」 |
| `diagrams/002-online-buzz-activity/09-component.puml`＋PNG | 前端元件改成「學生頁 `/`（`student.html`、`student.js`）、老師頁 `/teacher`（`teacher.html`、`teacher.js`）」 |
| 001、002 的類別圖與時序圖 | 經檢查，這些圖沒有畫出前端頁面，所以不需要修改 |

## Complexity Tracking

無違反 Constitution 的項目。
