# Research: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-22

本文件記錄 Technical Context 中各項技術決策的理由。依據為規格、Constitution v2.0.0、
助教 11/17 補充公告〈關於 Guided Notes 的串接方式〉，以及對兩份範例學習單（範例 A、範例 B）的實際結構分析。

---

## R1. 程式語言與執行環境

- **Decision**: Python 3.12，以 `uv` 管理虛擬環境與相依套件，並以 `.python-version` 固定版本。
- **Rationale**: 本機已有 `uv`。系統 Python 為 3.15，部分以原生程式碼編譯的套件（如 pydantic-core）
  可能尚無 3.15 的預編譯版本；`uv` 可自動下載 3.12，讓每台電腦得到相同環境。
  Google 官方提供 Python 的 Sheets API 用戶端（google-api-python-client、google-auth），
  且 002 搶答活動需要的即時推播也有現成支援。
- **Alternatives considered**: Node.js（本機未安裝）；
  直接使用系統 Python 3.15（相依套件相容性風險高）。

## R2. Web 框架與前端

- **Decision**: 後端使用 FastAPI（HTTP API，002 另用其 WebSocket 功能）；前端為伺服器直接提供的
  靜態 HTML + 原生 JavaScript，不使用前端建置工具。
- **Rationale**: 專案只在單一電腦上以多個瀏覽器視窗操作，畫面數量少；免建置工具可減少環境依賴
  （本機沒有 Node.js）。FastAPI 以 pydantic 做輸入驗證，正好對應 Constitution 原則 II；
  它也能自動產生 OpenAPI 文件，方便對照 contracts。
- **Alternatives considered**: Flask（需另外處理 WebSocket 與驗證）；React/Vue SPA（需要 Node.js 建置）。

## R3. 學習單讀取與解析方式

- **Decision**: 以 Sheets API `spreadsheets.get` 一次讀取整份試算表，只取需要的欄位：
  `sheets(properties(sheetId,title,index),merges,data(rowData(values(formattedValue))))`。
  `GoogleSheetsGateway` 把回應轉成與來源無關的 `SpreadsheetGrid`（每個工作表的儲存格值與合併範圍），
  解析器只處理 `SpreadsheetGrid`，所以解析演算法與資料來源無關，可以用假的資料完整測試。
  所有表頭標籤與上限值都從設定讀取。
- **Rationale**: 合併範圍是判斷填空格與題組的關鍵，`spreadsheets.get` 的 `merges` 直接提供；
  只讀值的 `values.get` 拿不到合併範圍。使用 `formattedValue` 可以取得畫面上看到的文字。

**解析演算法**（對應 FR-002～FR-012）：

1. 依活頁簿中的工作表順序逐一處理。在每個工作表由上而下找第一個「同一列同時有三個表頭標籤」的列
   作為表頭列（比對時去除前後空白）。沒有表頭的工作表略過；所有工作表都沒有表頭時，回報錯誤。
2. 每個表頭標籤的**欄位範圍** = 該儲存格所屬合併範圍涵蓋的欄（未合併時就是單一欄）。
3. **題目列**：表頭列以下、「題目」欄位範圍內有非空白文字的列。合併儲存格只以左上角所在的列計算。
4. **作答槽位**：在題目列的「作答」欄位範圍內，把儲存格切成槽位。每個合併範圍算一個槽位（以左上角代表），
   其餘未合併的儲存格各算一個槽位。沒有 `formattedValue` 或去除空白後為空字串的槽位是「空白槽位」。
   橫向相鄰的空白槽位合併成一段**空白區段**。
5. 每個題目列恰好要有 1 段空白區段，這段區段就是**填空格**，位置記為區段最左邊的槽位左上角。
   有 0 段或 2 段以上時回報錯誤，並指出工作表與列號。
6. 作答範圍內的非空白槽位文字（例如「（1）」）記為**子題標籤**。
7. **題組**：「題號」欄位範圍內的合併範圍若縱跨 2 個以上的列，它涵蓋的每一列都必須是題目列，
   否則回報「題組範圍不完整」。全部是題目列時，這些列的填空格構成一個題組。
   題號儲存格（合併時取左上角）的值記為**學習單原始題號**。
8. 依「工作表順序 → 列號」給予系統題號 1..N。N 為 0 時回報「找不到任何題目列」；
   N 超過上限時回報錯誤並附上上限值。
9. 驗證以「收集所有錯誤」的方式進行：一次回報所有問題的位置，不在遇到第一個錯誤時就停止。

**以範例驗證演算法**：範例 A 的表頭在第 4 列（題號=B、題目=C:F、作答=G:H），題目列為 5、7、9、11、13、15，
填空格是 G5…G15，共 6 題。範例 B 的表頭也在第 4 列；B5:B6 與 B8:B9 縱向合併形成 2 個題組；
第 5、6、8、9 列的 G 欄是子題標籤、H 欄是填空格；第 11、13 列的填空格是 G11、G13，共 6 題。
兩者都與規格中的對照表一致。

- **Alternatives considered**: 下載 .xlsx 後以 openpyxl 解析（違反助教 11/17 公告）；
  gspread（仍需另外呼叫 metadata 取得合併範圍，多一層依賴）；以儲存格框線或底色判斷填空格（樣式不穩定）；
  要求老師加入特殊記號（使用者已說明填空格就是空白儲存格）。

## R4. 答案寫回方式（只寫入原本空白的填空格）

- **Decision**: 寫回前重新以 `spreadsheets.get` 讀取目前內容（同時供 R5 檢查）。純函式 `writeback.plan()`
  依伺服器保存的成功答案，挑出「有成功答案且目前仍為空白」的填空格；已有內容的填空格跳過並列出題號（FR-026）。
  接著以 `spreadsheets.values.batchUpdate`（`valueInputOption=RAW`）一次送出這些儲存格，
  範圍以 A1 表示法加上工作表名稱（例如 `'學習單'!H5`，名稱中的單引號要重複一次以跳脫）。
- **Rationale**: 只更新目標儲存格的值，不會動到格式、合併範圍與其他儲存格，自然滿足 SC-003；
  `RAW` 讓答案原樣寫入，不會被當成公式或日期轉換（例如以「=」開頭的答案）。
  不覆蓋已有內容，避免誤刪老師課後手動補上的筆記。
- **驗證方式**: 單元測試用 `FakeSheetsGateway` 記錄寫入的儲存格，確認只包含預期的填空格；
  人工驗證在 Google Sheets 上直接檢查（quickstart V5）。
- **Alternatives considered**: 下載 .xlsx 修改 XML 再讓老師上傳（違反助教 11/17 公告）；
  `spreadsheets.batchUpdate` 的 `updateCells`（可以改格式，權限過大且較複雜）。

## R5. 寫回前的結構一致性檢查（FR-019）

- **Decision**: 匯入時保存解析出的填空格位置清單（工作表 ID、儲存格、系統題號、題組）與它的雜湊（結構指紋）。
  寫回前以重新讀取的內容再解析一次，**只比對填空格位置清單**是否與保存的相同；不同就拒絕寫回並說明差異。
  比對時把「已有內容的填空格」視為仍是填空格（否則老師填過的格子會被誤判成結構改變，FR-026 另行處理）。
- **Rationale**: 雲端試算表在匯入後可能被老師或協作者修改（插入列、搬動欄），直接寫入會把答案寫到錯的格子。

## R6. 儲存方式

- **Decision**: 使用 SQLite（Python 標準庫 `sqlite3`）保存學習單、填空格與題組的中繼資料；
  資料庫檔放在設定 `GB_DATA_DIR` 指定的目錄。系統不保存任何試算表檔案，學習單本體一律留在 Google Sheets。
- **Rationale**: 單機專題不需要資料庫伺服器；SQLite 支援交易，也能給 002 用來保存已結束活動的結果。
- **Alternatives considered**: 純 JSON 檔（沒有交易，002 有並行寫入時容易出錯）；PostgreSQL（違反本機執行限制）。

## R7. CSV 匯出格式

- **Decision**: 使用標準庫 `csv` 模組，編碼為 UTF-8 含 BOM（`utf-8-sig`），換行為 CRLF，
  只在必要時加引號（`QUOTE_MINIMAL`）。標題列為「題號,組別,答案,搶答順位,結果」。
  依系統題號遞增、同一題內依順位遞增排序；題組的一筆送出依其中每個填空各輸出一列，順位相同。
- **第 5 欄「結果」的理由**: 搶答紀錄包含被老師判定無效的送出（002 FR-024 保留原順位）。
  只有四欄時，讀者無法分辨某一列是成功、未搶到還是已無效。新增一欄（成功／未搶到／無效）
  不影響原本四欄的位置與意義。此欄已由使用者確認並寫入 spec.md FR-020。
- **Alternatives considered**: 純 UTF-8（Excel 開啟會出現亂碼）；Big5（無法表示所有字元）。

## R8. 搶答結果來源（與 002 的介面）

- **Decision**: 在共用領域模組中定義唯讀介面 `ActivityResultsProvider`，以及資料結構 `SubmissionRecord`、
  `ActivityResult`。001 的寫回與匯出只依賴這個介面；002 實作完成後提供正式版本。
  在 002 完成之前，提供 `JsonFileResultsProvider`，從 JSON 結果檔讀取，供測試與手動驗證使用；
  結果檔路徑由命令列參數提供。
- **Rationale**: 讓 001 可以單獨開發與測試（Constitution 原則 V）。資料結構只在共用模組定義一次，
  002 直接引用，不重複宣告。

## R9. 老師身分驗證與每個視窗的獨立身分

- **Decision**: 老師以密碼登入，密碼從環境變數 `GB_TEACHER_PASSWORD` 讀取；未設定時伺服器拒絕啟動。
  登入後取得隨機 Token（記錄在伺服器記憶體，可設定有效期限），前端存在 `sessionStorage`，
  每個請求以 `Authorization: Bearer` 標頭送出。
- **Rationale**: `sessionStorage` 依瀏覽器分頁或視窗隔離，同一瀏覽器的不同視窗可以分別是老師和各組學生，
  不會互相覆蓋（Constitution 專案範圍與限制、002 FR-005a）。Cookie 由同一瀏覽器的所有視窗共用，無法滿足這項需求。
  Token 與密碼都不寫入 log。
- **Alternatives considered**: Cookie session（各視窗會共用身分）；無驗證（違反權限原則）。

## R10. 設定與機敏資料

- **Decision**: 所有可調整的參數都以 `GB_` 開頭的環境變數提供（可用 `.env` 檔載入，`.env` 列入 `.gitignore`），
  並提供只含佔位值的 `.env.example`。可調參數包括：資料目錄、題數上限（預設 500）、
  表頭標籤（預設「題號」「題目」「作答」）、監聽位址（預設 `127.0.0.1`）與連接埠、Token 有效期限、
  service account 金鑰檔路徑 `GB_GOOGLE_CREDENTIALS_FILE`（必填）、Sheets API 逾時秒數（預設 10）。
- **Rationale**: 對應 Constitution 原則 I（不寫死）與 III（機敏資料只放環境變數）；
  預設只監聽本機位址，符合「只在單一電腦運作」的限制。

## R11. 測試策略

- **Decision**: 使用 pytest 與 FastAPI TestClient，自動化測試一律以 `FakeSheetsGateway` 取代 Google 服務，不連網。
  測試資料分成兩類：（1）範例 A、範例 B 的 Sheets API 回應快照（JSON，只含範例學習單的公開內容，不含任何憑證），
  由開發者以一次性的手動步驟取得後放入 `tests/fixtures/sheets/`；（2）測試時動態產生的 `SpreadsheetGrid` 變體，
  涵蓋不同欄位位置、多個工作表、各種錯誤情況等。`GoogleSheetsGateway` 的回應轉換與錯誤對應（403、404、逾時）
  以快照與假的 HTTP 回應測試。每個功能至少有一個正常案例與一個邊界案例。
- **Rationale**: 對應 Constitution 原則 VI、2.0.0「自動化測試不連線真實 Google 服務」與 SC-001（至少 3 份不同排版的學習單）。
  真正連線 Google 的流程以 quickstart 的人工驗證步驟確認。

## R12. 日誌

- **Decision**: 使用標準庫 `logging`，記錄匯入成功或失敗（只記學習單 ID、題數、錯誤代碼）、寫回、匯出等事件。
  不記錄試算表內容、答案文字、Token、密碼、憑證或 Google API 回應原文。
- **Rationale**: 對應 Constitution 原則 III；答案文字屬學生內容，也不需要寫進 log。

## R13. Google 認證方式

- **Decision**: 使用 Google service account（系統帳號）。組員在自己的 Google Cloud 專案啟用 Sheets API、
  建立 service account 並下載金鑰 JSON，把金鑰檔**路徑**設定在環境變數 `GB_GOOGLE_CREDENTIALS_FILE`；
  老師把學習單共用給 service account 的 email（編輯者權限）。權限範圍只申請
  `https://www.googleapis.com/auth/spreadsheets`。
- **Rationale**: 本機專題不需要做 OAuth 登入畫面與 token 保存；金鑰只存在各自電腦，不進 repo（Constitution 原則 III）。
  沒有權限時，錯誤訊息直接顯示 service account 的 email（不是機敏資料），告訴老師要共用給誰（FR-025）。
- **Alternatives considered**: OAuth（老師用自己的帳號登入，需要登入流程、保存 refresh token，設定較複雜）；
  API key（只能讀取公開試算表，無法寫入）。
