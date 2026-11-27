# Research: 入口頁與老師頁面對齊 OpenSpec 組

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本功能沿用 001、002 的技術（FastAPI、原生 HTML/JS），不新增套件，所以沒有需要額外研究的新技術。
以下記錄的是頁面路由、檔案配置與前端行為上的設計決定。

## R1：頁面路由（`/`、`/teacher`）

- **Decision**：新增 `api/page_routes.py`，由 FastAPI 路由回傳頁面：
  - `GET /` 以 `FileResponse` 回傳 `web/static/student.html`。
  - `GET /teacher` 以 `FileResponse` 回傳 `web/static/teacher.html`。
  - 兩者都設定 `include_in_schema=False`。
  - 在 `create_app` 中，於 `app.mount("/", StaticFiles(...))` **之前**以 `include_router` 掛上。
- **Rationale**：
  - Starlette 依註冊順序比對路由，掛在 mount 之前，`/` 與 `/teacher` 才不會被靜態檔處理。
  - `StaticFiles(html=True)` 只會把目錄對應到 `index.html`，不會把 `/teacher` 對應到 `teacher.html`。
  - 每組路由各放一個模組，與現有的 `auth_routes`、`activity_routes` 等慣例一致。
- **Alternatives considered**：
  - 把學生頁放進 `index.html`，讓 StaticFiles 處理 `/`：仍需另外處理 `/teacher`，結果兩個頁面的處理方式不一致，所以放棄。
  - 在前端用 JS 判斷路徑：首次載入仍需要伺服器回傳正確頁面，無法解決問題。

## R2：舊網址導向（`/student.html`、`/teacher.html`）

- **Decision**：
  - 同一個 `page_routes` 模組提供 `GET /student.html → RedirectResponse("/")` 與 `GET /teacher.html → RedirectResponse("/teacher")`，狀態碼使用預設的 307。
  - 頁面原始檔維持原檔名 `student.html`、`teacher.html`，繼續放在 `web/static/`。
- **Rationale**：
  - 這兩條路由比 StaticFiles 先比對，舊網址一律被導向，不會看到舊畫面（FR-025）。
  - 頁面檔不改名，可以保留 git 歷史，差異最小。
  - 不使用 301（永久），因為瀏覽器會快取 301；萬一之後網址再調整，已快取的瀏覽器會繼續導到舊目標。
- **Alternatives considered**：
  - 在舊檔裡放 `<meta http-equiv="refresh">`：頁面原始檔會被改成空殼，真正的頁面就得改名，反而改動更多。另外 meta refresh 需要先載入 HTML 才會跳轉。
  - 把頁面移到 `web/pages/`：結構比較乾淨，但要搬檔並調整所有路徑；目前只有兩頁，不值得。

## R3：刪除舊的老師入口頁

- **Decision**：刪除 `web/static/index.html` 與 `web/static/app.js`，將其功能併入 `teacher.html`、`teacher.js`。
- **Rationale**：
  - 首頁已經由路由回傳學生頁。保留 `index.html`，`/index.html` 仍會顯示舊的老師登入頁，等於多了一個舊入口。
  - 刪除後，`/index.html` 回 404。它不在需要導向的舊網址清單中（交接文件只列了兩個）。
- **Alternatives considered**：也導向 `/index.html`。這個網址從來沒有寫在說明裡，不需要。

## R4：JS 檔案切分（FR-026）

- **Decision**：
  - `student.html` 只載入 `student.js`，`teacher.html` 只載入 `teacher.js`，兩頁共用 `style.css`。
  - `app.js` 的匯入、確認、寫回、匯出功能併入 `teacher.js`；兩個檔案原本重複的輔助函式（`showMessage`、`formatError`、`readJson`、`api`）合併成一份。
  - `formatError` 採用 `app.js` 的版本，它會逐條列出 `issues`，匯入錯誤需要這個功能。
- **Rationale**：符合「各頁只載入需要的程式」。目前只有兩頁，輔助函式各自一份，比另外抽出共用檔簡單。
- **Alternatives considered**：抽出 `common.js` 給兩頁共用。可以減少約 20 行重複，但多一個檔案和載入順序的相依；兩頁的 `api()` 行為不同（學生頁要帶 `X-Window-Id`，老師頁遇到 401 要回到登入畫面），能共用的部分不多。

## R5：視窗身分與重新整理（FR-006、FR-022、FR-024）

- **Decision**：
  - 沿用現有的 sessionStorage 鍵名：
    - 老師：`guided_buzz_teacher_token`、`guided_buzz_teacher_activity`
    - 學生：`guided_buzz_student_token`、`guided_buzz_student_activity`、`guided_buzz_window_id`
  - 重新整理時：
    - 老師頁以 `GET /api/auth/session` 確認身分。
    - 學生頁以 `GET /api/me` 確認身分；回 401 時查詢 `/api/activities/{id}/phase`，再決定要顯示哪一種提示。這部分沿用現有的 `checkInterrupted`。
- **Rationale**：
  - sessionStorage 以「分頁＋網域」為範圍，同一個瀏覽器的不同視窗彼此獨立（E-08），伺服器不需要任何改變。
  - 鍵名不變，更新程式後，已登入的視窗不會被登出。
- **Alternatives considered**：改用 cookie。cookie 會在同一個瀏覽器的所有視窗之間共用，違反 Constitution「每個視窗獨立身分」。

## R6：即時連線只在登入或加入後建立（FR-021、FR-023）

- **Decision**：
  - 老師頁只在 `showLoggedIn(true)` 時呼叫 `connect()`。
  - 登出時先把 `socket.onclose` 設為 `null`，再 `close()`，避免自動重連。學生頁的 `leave()` 已經是這種寫法。
  - 學生頁維持現況：只在加入成功或身分驗證通過後才連線。
- **Rationale**：現在的 `teacher.js` 登出時只呼叫 `socket.close()`。`onclose` 會在 1 秒後重連；雖然因為沒有 Token 會被以 4401 拒絕，但仍多了一次無用連線，也不符合「登出時關閉」。
- **Alternatives considered**：無。

## R7：「目前活動」區塊顯示哪一場（FR-014、FR-019）

- **Decision**：
  - 頁面保存「正在檢視的活動」：`current`，並把它的 ID 存進 sessionStorage。
  - 收到 WebSocket 的 `snapshot` 時，只有在「目前沒有檢視中的活動」或「快照就是檢視中的那一場」時才更新畫面。
  - 其他事件一律重新取得 `current` 這一場（沿用現有的 `refresh()`）。
  - 自己建立活動時，直接用 `POST /api/activities` 的回應更新 `current`。
  - 按「檢視」時，以 `GET /api/activities/{id}` 的回應更新 `current`。
- **Rationale**：
  - 伺服器送給老師的快照固定是「本次啟動後最近建立的活動」（002 `registry.latest`）。
  - 如果老師正在檢視一場舊活動，此時進行中的活動送來快照，畫面就會被切走，老師的操作會被打斷。
- **Alternatives considered**：讓伺服器依老師正在檢視的活動送快照。需要修改 002 的推播協定，違反 FR-027。

## R8：寫回與下載 CSV 直接使用目前活動（FR-015～FR-017）

- **Decision**：
  - 「目前活動」的 `phase` 為 `ended` 時，才顯示「寫回答案」「下載 CSV」。
  - 寫回時呼叫 `POST /api/worksheets/{current.worksheet_id}/writeback`，body 為 `{"activity_id": current.id}`。
  - 下載時呼叫 `GET /api/activities/{current.id}/results.csv`，下載方式沿用 `app.js` 現有的 blob 與 `X-Record-Count` 做法。
  - 筆數為 0 時的訊息改成「此活動沒有任何送出紀錄」；仍然下載只有表頭的檔案。
- **Rationale**：
  - 002 的老師檢視資料（`view_for_teacher`）已經包含 `worksheet_id`，前端不需要老師輸入任何 ID。
  - 寫回失敗時，沿用 `formatError` 顯示 001 的錯誤訊息；按鈕保持可用，可以重試。
- **Alternatives considered**：無。

## R9：「已確認的學習單」與「活動清單」

- **Decision**：
  - **學習單**：
    - `GET /api/worksheets` 的 `WorksheetSummary` 新增 `confirmed_at: str | None`，前端只顯示 `status === "confirmed"` 的學習單。
    - 確認或取消學習單後，重新載入清單，同時更新「已確認的學習單」表格和「建立搶答活動」的選單（FR-012）。
  - **活動清單**：
    - 使用既有的 `GET /api/activities`；「學習單」欄位以 `worksheet_id` 對照學習單清單，顯示試算表名稱。
    - 以下時機重新載入活動清單：登入後、建立活動後，以及收到 `phase_changed` 事件時。
    - 按「檢視」時，若回應 409（活動已中斷），只顯示伺服器的訊息，不改變 `current`。
- **Rationale**：
  - 資料庫的 `worksheets.confirmed_at` 本來就有，`storage.worksheets.get` 也已經讀出這個值，只是 `WorksheetSummary` 沒有回傳；新增一個唯讀欄位就能滿足 FR-011（spec FR-027 已允許）。
  - 活動清單目前只有 `worksheet_id`，所以由前端對照學習單名稱，避免改動 002 的 API。
- **Alternatives considered**：在 `GET /api/activities` 加上學習單名稱。需要修改 002 的回應格式，而前端對照就能做到，不需要。

## R10：測試策略（Constitution 原則 VI）

- **Decision**：
  - **自動化（pytest＋TestClient，不新增套件）**：新增 `tests/integration/test_pages.py`，涵蓋：
    - `GET /` 回學生頁：有「加入組別」「我是老師」，指向 `/teacher`；沒有密碼欄；只載入 `student.js`。
    - `GET /teacher` 回老師頁：有「老師登入」；只載入 `teacher.js`；沒有指向其他頁面的 `<a href>`。
    - `/student.html`、`/teacher.html` 回 307，`Location` 分別為 `/`、`/teacher`。
    - `/index.html`、`/app.js` 回 404。
  - **自動化（擴充既有測試）**：在 `test_worksheet_api.py` 補上 `GET /api/worksheets` 的 `confirmed_at`，確認後有值、未確認時為 `null`。
  - **人工驗證**：前端互動依 [quickstart.md](./quickstart.md) 驗收 E-01～E-10。
- **Rationale**：專案沒有前端測試框架，為了這個功能另外引入 JS 測試工具不划算（使用者要求不新增套件）。伺服器端可測的部分全部自動化；畫面行為則由驗收情境人工確認，與 001、002 的做法一致。
- **Alternatives considered**：以 Playwright 做端對端測試。需要新增套件與瀏覽器執行環境，不符合「不新增套件」。

## R11：文件與圖表同步範圍（FR-029）

- **Decision**：
  - 會繼續被閱讀的「現行文件」直接改寫內容：README、001 plan、001 quickstart、002 plan、元件圖。
  - 記錄當時做了什麼的「歷史文件」不改寫原文，只在開頭加一行註記，指向 003：001 tasks、002 tasks、002 verification。
  - 001 spec 經檢查，沒有提到舊頁面網址或頁面名稱，只在 Clarifications 補一行入口變更的註記。
  - 完整清單見 [plan.md](./plan.md)「文件與圖表同步清單」。
- **Rationale**：
  - 改寫已完成的任務描述或過去的驗證紀錄，會讓「當時做了什麼、驗證了什麼」失真。
  - 現行文件如果不改，照著操作的人會走錯入口。
- **Alternatives considered**：全部改寫。會破壞歷史紀錄的可信度。
