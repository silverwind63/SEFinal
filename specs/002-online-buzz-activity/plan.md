# Implementation Plan: 線上分組搶答活動

**Branch**: 從 `main` 開功能分支（例如 `feat/002-us1`） | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-online-buzz-activity/spec.md`

**Depends on**: [001 學習單匯入](../001-guided-notes-import/plan.md)。共用 `guided_buzz` 套件中的 config、domain、storage、
auth、api 骨架，並使用 001 確認後的 `ParsedWorksheet`。

## Summary

老師以已確認的學習單建立活動並設定組別，系統為每組產生代碼，學生在各自的瀏覽器視窗輸入代碼加入。
所有搶答單位（單一題目或整個題組）同時開放，送出由單一程序中的 `ActivityEngine` 在一把鎖內依序判定：
最先送出者成功，順位依序遞增，並套用「領先 K 題就冷卻 N 秒」的公平機制。老師可以判定無效並由下一順位遞補。
狀態透過 WebSocket，依連線的身分分別推送，學生在活動結束前只收得到自己組別的資料。
活動結束時，結果以一筆交易寫入 SQLite，並透過 `ActivityResultsProvider` 提供給 001 寫回與匯出；
伺服器重啟時，未結束的活動標示為已中斷。

## Technical Context

**Language/Version**: Python 3.12（與 001 相同）

**Primary Dependencies**: FastAPI（HTTP 與 WebSocket）、uvicorn（固定 workers=1）、pydantic v2；沿用 001 的其他相依套件，不新增任何套件

**Storage**: SQLite（與 001 共用同一個資料庫檔）；進行中的狀態只存在記憶體，結束時才寫入（research R7）

**Testing**: pytest、pytest-asyncio（同時送出測試）、FastAPI TestClient（WebSocket）、假時鐘

**Target Platform**: 單一電腦，伺服器只監聽 `127.0.0.1`；1 個老師視窗加上多個學生視窗

**Project Type**: Web 應用（擴充 001 的同一個專案）

**Performance Goals**: 1 個老師視窗加 12 個學生視窗時，階段變更與送出結果在 2 秒內同步（SC-001）；
判定結果與伺服器處理順序 100% 一致（SC-002）

**Constraints**: 單一程序（記憶體中的狀態與鎖）；學生不可取得他組資料（FR-014）；組別代碼與 Token 不寫入 log；
參數全部可以設定（research R10）

**Scale/Scope**: 同時只有一場活動；組數 ≤ 20（可設定）；搶答單位 ≤ 500；學生頁面與老師主控台各一個

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 檢查結果 | 依據 |
|------|---------|------|
| I. 不寫死資料與設定 | ✅ | 組數與組名由老師輸入；N、K、答案長度、輸錯限制、組數上限都從 `GB_*` 讀取，建立活動時也可覆寫（research R10）；搶答單位由任一份學習單動態產生（research R4） |
| II. 輸入驗證與清楚錯誤 | ✅ | 送出依序做 7 項檢查，每項有獨立的錯誤代碼與繁體中文訊息，題組缺漏時列出題號（research R5）；組名與 N、K 都有範圍驗證（data-model） |
| III. 機敏資料只放環境變數 | ✅ | 老師密碼沿用 001 的做法；組別代碼只在記憶體保存明文，資料庫只存雜湊；Token 不放在 WebSocket 網址上（research R2）；log 不記錄代碼、Token、答案 |
| IV. 伺服器權威、公平一致、權限隔離 | ✅ | 單一鎖依序判定，忽略客戶端提供的時間（research R1、R5）；冷卻使用伺服器的 monotonic 時鐘；推播依身分分別產生，並有專門測試驗證不洩漏他組資料（contracts/websocket.md）；有同時送出測試，重複 100 次 |
| V. 模組化與單一定義 | ✅ | `BuzzUnit`、`ActivityPhase`、`SubmissionRejectCode` 加到 001 的 `domain/`，不另建一份；引擎內部的狀態只在 `activity/state.py`；引擎不依賴 HTTP 或 WebSocket（diagrams 第 9 節） |
| VI. 測試與驗證回報 | ✅ | 每個使用者情境都有正常與邊界測試；quickstart 提供 V1–V7 人工驗證步驟 |
| VII. PlantUML 設計優先 | ✅ | `diagrams/002-online-buzz-activity/` 含 4 張時序圖（標示 [權限檢查] 與 [判定] 點）、3 張狀態圖、類別圖、組件圖（.puml＋PNG），本計畫以其為藍圖（見 [diagrams.md](./diagrams.md)）；**實作前需審閱** |
| 範圍限制（單機、多視窗） | ✅ | 每個視窗以 sessionStorage 保存獨立的 Token；輸錯限制以視窗 ID 計算，不以 IP 計算，另有全體上限（research R3） |

**Post-design re-check（Phase 1 後）**：✅ 全部通過。有一項設計取捨需要說明：
輸錯限制依賴客戶端提供的視窗 ID，使用者可以偽造。在單機課堂情境下，以「每個視窗的限制 + 全體上限 + 6 碼代碼」
作為可接受的風險；如果改用 IP 限制，會因為所有視窗都在同一台電腦而封鎖全班，違反規格。

## Project Structure

### Documentation (this feature)

```text
specs/002-online-buzz-activity/
├── plan.md
├── research.md
├── data-model.md
├── diagrams.md
├── quickstart.md
├── contracts/
│   ├── http-api.md
│   └── websocket.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 產生
```

### Source Code（在 001 的結構上新增或修改；標示「修改」的是 001 已有的檔案）

```text
src/guided_buzz/
├── config.py                    # 修改：加入 research R10 的設定
├── domain/
│   ├── models.py                # 修改：新增 ActivityPhase、BuzzUnit
│   └── errors.py                # 修改：新增 SubmissionRejectCode 與繁體中文訊息
├── activity/
│   ├── units.py                 # ParsedWorksheet → list[BuzzUnit]
│   ├── state.py                 # 引擎內部狀態：TeamState、UnitState、Cooldown
│   ├── fairness.py              # 冷卻規則（純函式）
│   ├── engine.py                # ActivityEngine：鎖、判定、判定無效、結束
│   ├── registry.py              # 目前的活動、同時只有一場、啟動時標示中斷
│   └── codes.py                 # 組別代碼產生與雜湊
├── auth/
│   └── sessions.py              # 老師與學生的 Session、撤銷、以視窗 ID 計算輸錯限制
├── realtime/
│   ├── hub.py                   # WebSocket 連線管理與推播
│   └── views.py                 # 依身分產生快照與事件（老師版、學生版）
├── storage/
│   ├── db.py                    # 修改：新增 activities、teams、submissions、submission_answers
│   └── activities.py            # 活動的建立、階段更新、結束時一次寫入、判定無效更新
├── results/
│   └── sqlite_provider.py       # 實作 ActivityResultsProvider
├── api/
│   ├── app.py                   # 修改：掛上新路由與 /ws，啟動時處理中斷活動
│   ├── activity_routes.py       # 老師端
│   └── student_routes.py        # 加入、送出、/me、結果、公開的 phase
└── web/static/
    ├── teacher.html / teacher.js # 活動主控台
    └── student.html / student.js # 學生頁面

tests/
├── unit/
│   ├── test_units.py
│   ├── test_fairness.py
│   ├── test_engine.py
│   ├── test_engine_concurrency.py
│   ├── test_codes.py
│   └── test_sessions.py
└── integration/
    ├── test_activity_api.py
    ├── test_student_api.py
    ├── test_realtime.py
    ├── test_isolation.py
    ├── test_restart.py
    └── test_fairness_simulation.py
```

**Structure Decision**: 延續 001 的單一 Python 專案。判定邏輯集中在 `activity/`，不依賴 HTTP 或 WebSocket；
即時推播在 `realtime/`；兩者透過「引擎回傳的事件清單」連接，使判定引擎可以完全以單元測試驗證。

## Complexity Tracking

無違反 Constitution 的項目。
