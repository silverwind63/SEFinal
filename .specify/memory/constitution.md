<!--
Sync Impact Report
- 版本變更：1.2.0 → 2.0.0（MAJOR：重新定義原則 VII，並修改專案範圍限制）
- 修改的原則：VII. Diagram First Development（圖表先行開發）→ VII. 圖表生成：PlantUML 設計優先
  （依《期末專題說明》附錄：改用 PlantUML 組件圖／類別圖／時序圖，存於 ./diagrams/ 並轉成 PNG，
  於 specify 階段產出；移除「優先使用 Mermaid、存放於規格目錄」）
- 修改章節：
  - 專案範圍與限制：依助教 11/17 補充公告，允許且要求直接讀寫雲端 Google Sheets，不得以下載 .xlsx 取代；
    Google 憑證只透過環境變數提供；自動化測試不得連線真實 Google 服務
  - 開發流程與品質關卡：圖表改在 specify 階段產出，plan 以圖表為藍圖
- 前次（1.1.0 → 1.2.0）：明訂只在單一電腦運作，以多個瀏覽器視窗模擬老師與各組學生
- 新增章節：無
- 移除章節：無
- 受影響文件：specs/001-guided-notes-import（spec、plan、research、data-model、contracts、quickstart、tasks、
  diagrams 皆以 .xlsx 上傳／下載為前提，須更新）；specs/002-online-buzz-activity（diagrams 須轉為 PlantUML、
  quickstart 引用 sample_b.xlsx）
- 後續 TODO：無
-->

# 課堂線上活動系統 Constitution

本專案為軟體工程期末專題，目標是在本機環境下模擬一個可實際用於課堂的線上活動系統。

## Core Principles

### I. 不寫死資料與設定

- 程式碼中 MUST NOT 寫死任何資料檔案路徑、資料位置或業務常數（如人數上限、時間限制、分數規則）。
- 資料來源與可調參數 MUST 透過命令列參數、設定檔或環境變數提供，並有文件說明其預設值。
- 系統 MUST 能處理「同格式但內容不同」的輸入檔案；測試 MUST 至少使用兩份不同內容的輸入檔驗證。

理由：課堂情境中的名單、題目與活動規則每次都不同，寫死會使系統無法重複使用。

### II. 全面輸入驗證與清楚錯誤訊息

- 所有外部輸入（使用者請求、上傳/讀入的檔案、設定值、環境變數）MUST 在進入業務邏輯前經過驗證，
  包含型別、格式、範圍、必要欄位與長度。
- 驗證失敗時 MUST 回傳清楚、可操作的繁體中文錯誤訊息，指出哪個欄位或哪一行有什麼問題；
  MUST NOT 讓未處理例外或堆疊追蹤直接呈現給使用者。
- 錯誤訊息 MUST NOT 洩漏機敏資料或其他使用者的資料。

理由：課堂使用者輸入不可控，清楚的錯誤訊息能降低現場排錯成本。

### III. 機敏資料僅存於環境變數（不可妥協）

- 密碼、金鑰、Token、連線字串等機敏資料 MUST 只透過環境變數提供。
- 機敏資料 MUST NOT 出現在程式碼、文件、測試資料、log 輸出或版本庫中；
  文件與範例只能使用佔位值（如 `.env.example` 中的 `SECRET_KEY=change-me`）。
- `.env` 等含實際值的檔案 MUST 列入 `.gitignore`；缺少必要環境變數時，系統 MUST 在啟動時以清楚訊息失敗，
  而非使用內建預設密鑰。

理由：機敏資料一旦進入版本庫或 log 即難以收回。

### IV. 伺服器權威、公平一致與權限隔離（不可妥協）

- 所有判定（如作答對錯、先後順序、計分、名額、時間截止）MUST 由伺服器執行並作為唯一依據；
  MUST NOT 信任客戶端送出的時間、分數或判定結果。
- 多使用者同時操作時，判定 MUST 公平且具決定性：以伺服器接收順序或伺服器時間為準，
  並以適當的同步機制（鎖、交易或原子操作）避免競態條件，相同輸入 MUST 得到相同結果。
- 每個資料存取 MUST 在伺服器端檢查身分與權限；使用者只能取得自己有權看到的資料
  （例如學生不可看到他人作答或正解，除非活動規則允許）。
- 同時操作與越權存取 MUST 有對應測試。

理由：課堂活動的公信力取決於結果公平且不可被客戶端竄改。

### V. 模組化與單一資料結構定義

- 程式碼 MUST 依職責切分模組（如輸入解析、驗證、業務邏輯、資料存取、介面/API），模組之間透過明確介面溝通。
- 模組之間共用的資料結構（模型、Schema、型別、常數列舉）MUST 只在單一位置定義，其他模組一律引用；
  MUST NOT 複製或重新宣告相同結構。
- 新增模組或跨模組相依時，MUST 在計畫文件中說明其職責與介面。

理由：單一定義避免資料結構不同步，模組化讓功能可獨立測試與替換。

### VI. 測試與驗證回報

- 每個功能 MUST 至少有一個正常案例測試與一個邊界案例測試（如空輸入、上限值、同時操作、無權限存取）。
- 測試 MUST 可在本機以單一指令執行，且不依賴寫死的路徑或真實機敏資料。
- 每個功能完成時 MUST 回報：執行的測試指令、測試結果（通過/失敗數與失敗輸出）、以及人工驗證步驟
  （操作步驟與預期結果）。測試失敗 MUST 如實回報，不得省略。

理由：期末專題需可展示、可重現，測試與人工驗證步驟是交付品質的證據。

### VII. 圖表生成：PlantUML 設計優先（Design-First with PlantUML）

- **規格制定階段（Specification Phase）**：在 `/speckit-specify` 階段，MUST 使用 PlantUML 語法產生
  **組件圖（Component diagram）**、**類別圖（Class diagram）**與**時序圖（Sequence diagram）**。
  圖表檔案（`.puml`）MUST 存放在 `./diagrams/` 目錄下，並依功能分子目錄（例如 `./diagrams/001-guided-notes-import/`）。
- **產物生成（Artifact Generation）**：`.puml` 建立或修改後，MUST 使用 PlantUML CLI
  （`java -jar plantuml.jar "./diagrams/**/*.puml"` 或等效的 `plantuml` 指令）轉換為 PNG，
  PNG MUST 存放在與 `.puml` 相同的目錄，並與 `.puml` 一起納入版本庫。
- **規劃階段（Planning Phase）**：`/speckit-plan` MUST 以這些圖表作為主要藍圖，用以規劃應用程式的架構與組件；
  plan 與圖表不一致時，MUST 先修正圖表或在 plan 中說明理由。
- **實作階段（Implementation Phase）**：`/speckit-implement` 完成程式碼後，MUST 執行驗證步驟，
  確認最終程式碼與圖表完全一致；設計變更時 MUST 先更新圖表再修改程式碼。
- 時序圖 MUST 標示伺服器判定點與權限檢查點（對應原則 IV）；類別圖 MUST 標示共用資料結構所屬模組（對應原則 V）。
- 涉及狀態變化（如活動開始/進行中/截止）的功能 MUST 另附 PlantUML 狀態圖。
- 圖中文字使用繁體中文，且 MUST NOT 含機敏資料。
- 圖表中的每個互動步驟與邊界情境 SHOULD 對應至少一個測試案例（對應原則 VI）。

理由：《期末專題說明》規定 SpecKit 組須導入 Diagram First Development。先以圖表釐清互動順序、判定位置與
資料結構，可讓 AI 有明確的規劃依據，並在寫程式前發現競態、越權與重複定義等設計問題。

## 專案範圍與限制

- 系統 MUST 能在本機環境運行（含伺服器、資料儲存與前端）。唯一允許的外部服務是課程規定的 Google Sheets：
  系統 MUST 直接讀寫雲端上的 Guided Notes 試算表，MUST NOT 以下載 .xlsx 離線處理取代；
  除此之外不得依賴其他雲端服務或付費服務。
- 存取 Google Sheets 的憑證 MUST 依原則 III 只透過環境變數提供；自動化測試 MUST NOT 連線真實的 Google 服務，
  一律使用假的資料來源。
- 系統只需在單一電腦上運作：以同一台電腦上的多個瀏覽器視窗分別模擬老師與各組學生，
  不需支援其他設備連線。伺服器 SHOULD 只接受本機連線。
- 系統 MUST 支援多個瀏覽器視窗同時操作，且每個視窗 MUST 能獨立維持自己的身分
  （同一瀏覽器的不同視窗可分別為老師與不同組別），不得因共用瀏覽器而互相覆蓋身分。
- 多使用者同時操作的公平性與權限測試 MUST 能在單一電腦上重現（例如以多個瀏覽器視窗或自動化測試模擬同時送出）。
- 所有回覆、文件、使用者介面文字與錯誤訊息 MUST 使用繁體中文；程式識別字可使用英文。
- 啟動方式、所需環境變數清單（僅名稱與用途，不含實際值）與輸入檔格式 MUST 記錄於 README 或 quickstart 文件。

## 開發流程與品質關卡

- 每個功能依 Spec Kit 流程進行：`/speckit-specify` → `/speckit-clarify`（必要時）→ `/speckit-plan`
  → `/speckit-tasks` → `/speckit-implement`。
- 規格階段（specify）MUST 產出原則 VII 要求的 PlantUML 圖表與 PNG。
- 計畫階段（plan）MUST 以這些圖表為藍圖，並執行 Constitution Check，逐條確認原則 I–VII；
  違反之處 MUST 在複雜度追蹤中說明理由。
- 進入實作（implement）前 MUST 確認必要圖表已完成並經審閱。
- 合併或標記功能完成前 MUST 通過以下關卡：
  1. 所有測試通過，且新功能具備正常案例與邊界案例測試。
  2. 搜尋程式碼與 log 確認無寫死路徑、常數或機敏資料。
  3. 共用資料結構無重複定義。
  4. 圖表與最終實作一致。
  5. 已提供測試指令、結果與人工驗證步驟。

## Governance

- 本 Constitution 優先於其他開發慣例與文件；衝突時以本文件為準。
- 修訂 MUST 以 `/speckit-constitution` 進行，並在檔案開頭的 Sync Impact Report 記錄變更內容與影響。
- 版本採語意化版本：
  - MAJOR：移除原則或以不相容方式重新定義原則。
  - MINOR：新增原則或章節，或實質擴充規範。
  - PATCH：措辭澄清、錯字修正等不影響語意的調整。
- 每次程式碼審查與功能完成回報 MUST 確認符合本 Constitution；任何例外 MUST 在計畫文件中記錄理由與替代方案。

**Version**: 2.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
