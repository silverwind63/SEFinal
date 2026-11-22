# Quickstart & Validation: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **API**: [contracts/http-api.md](./contracts/http-api.md)

本文件是**驗證指南**：說明如何在本機執行，並逐項確認各驗收情境。實作完成後，實際的測試指令與結果
依 Constitution 原則 VI 另行回報。

## 前置需求

- Linux 或 macOS，已安裝 `uv`（`uv --version`）
- 一般瀏覽器（Chrome 或 Firefox）
- 匯入與寫回需要網路連線（直接讀寫雲端 Google Sheets）；自動化測試不需要網路
- 一個 Google 帳號，用來建立 Google Cloud 專案與 OAuth client（見下方一次性設定）

## 一次性設定：Google OAuth

每位組員在自己的電腦各做一次。OAuth client 設定檔與登入後的 token 檔**不可**放進 repo，也不可透過聊天或雲端硬碟傳給別人。

1. 到 Google Cloud Console 建立專案，啟用「Google Sheets API」。
2. 設定「OAuth 同意畫面」：使用者類型選「外部」，並把要登入的 Google 帳號（組員、Demo 用帳號）加入「測試使用者」。
3. 建立 OAuth client，應用程式類型選「**桌面應用程式**」，下載 client JSON，存放在 repo 以外的位置
   （例如 `~/.config/guided-buzz/oauth-client.json`）。
4. 在 `.env` 設定 `GB_GOOGLE_OAUTH_CLIENT_FILE` 指向這個檔案，然後執行：

   ```bash
   uv run python -m guided_buzz login-google
   ```

   瀏覽器會開啟 Google 登入頁，以老師（或 Demo 用）的帳號登入並同意。完成後終端機顯示登入的帳號，
   token 存到 `GB_GOOGLE_TOKEN_FILE`（預設 `<GB_DATA_DIR>/google-token.json`，權限 600）。
5. 之後這個帳號能編輯的試算表都能直接匯入與寫回。助教以另一份學習單測試時，請擁有者把試算表共用給登入的帳號
   （編輯者），或複製一份到這個帳號的雲端硬碟。

同意畫面在「測試中」狀態時，授權約 7 天後失效（依 Google 目前政策，以 Console 顯示為準）。
**Demo 前請重新執行一次 `login-google`**；授權失效時，系統會在匯入或寫回時提示重新登入。

## 設定

```bash
cp .env.example .env          # .env 已列入 .gitignore，不可提交
# 編輯 .env，至少設定：
#   GB_TEACHER_PASSWORD=<自行設定的密碼>
#   GB_DATA_DIR=<資料目錄，例如 ./var>
#   GB_GOOGLE_OAUTH_CLIENT_FILE=<OAuth client JSON 的完整路徑>
uv sync                        # 依 .python-version 建立 Python 3.12 環境並安裝相依套件
```

未設定 `GB_TEACHER_PASSWORD` 或 `GB_GOOGLE_OAUTH_CLIENT_FILE`（或設定檔不存在）時，伺服器必須拒絕啟動，
並以繁體中文說明缺少哪一個環境變數；尚未執行 `login-google` 時，伺服器拒絕啟動並提示登入指令。都不顯示憑證或 token 內容。

## 啟動

```bash
uv run python -m guided_buzz   # 預設 http://127.0.0.1:8000（可用 GB_HOST、GB_PORT 調整）
```

## 自動化測試

```bash
uv run pytest                          # 全部測試（不連網，以 FakeSheetsGateway 取代 Google 服務）
uv run pytest tests/unit/test_parser.py -v          # 解析規則（範例 A、B 快照與動態產生的變體）
uv run pytest tests/unit/test_writeback.py -v       # 只寫入原本空白的填空格
uv run pytest tests/unit/test_google_gateway.py -v  # API 回應轉換與錯誤對應
uv run pytest tests/unit/test_csv_export.py -v
uv run pytest tests/integration -v                  # API、權限、錯誤格式
```

測試資料：`tests/fixtures/sheets/sample_a.json`、`sample_b.json`（規格中兩份範例學習單的 Sheets API 回應快照，
不含任何憑證），其餘變體在測試中動態產生。

## 人工驗證步驟

以下步驟會讀寫真實的 Google Sheets。請先在自己的雲端硬碟建立範例 A、範例 B 的**副本**，
（登入的帳號建立的副本本身就有編輯權限），不要直接修改原始範例。

### V1：匯入範例 A（US1 情境 1）

1. 開啟 `http://127.0.0.1:8000`，以老師密碼登入。
2. 貼上範例 A 副本的網址並匯入。
3. **預期**：題數 6、題組 0；系統題號 1–6 依序對應 G5、G7、G9、G11、G13、G15；畫面上沒有題目敘述。
4. 按「確認」，**預期**：狀態變成「已確認」。

### V2：匯入範例 B（US1 情境 2）

1. 貼上範例 B 副本的網址並匯入。
2. **預期**：題數 6、題組 2；題組 1 = 系統題號 1、2（H5「（1）」、H6「（2）」，原題號 1）；
   題組 2 = 系統題號 3、4（H8、H9，原題號 2）；系統題號 5 = G11、6 = G13，都不屬於題組。

### V3：取消與錯誤（US1 情境 3–5）

1. 匯入任一範例後按「取消」，**預期**：狀態變成「已取消」，無法再確認。
2. 輸入 `https://example.com/abc`，**預期**：「網址格式不正確」。
3. 輸入一份登入的帳號**沒有**編輯權限的試算表網址，**預期**：拒絕匯入，訊息中顯示目前登入的帳號，並說明如何取得權限。
4. 在範例 A 副本刪除「作答」表頭後匯入，**預期**：「找不到表頭列」，並說明應有的三個表頭。
5. 在範例 A 副本的 G7 預先填入文字後匯入，**預期**：拒絕匯入，並指出「學習單」第 7 列沒有填空格。

### V4：不同排版（SC-001）

1. 在 Google Sheets 建立一份新學習單：表頭放在第 2 列、「作答」欄放在 B 欄、「題目」欄放在 C:E，共 3 題，
   其中第 2、3 題的題號儲存格縱向合併；匯入。
2. **預期**：題數 3、題組 1（系統題號 2、3），填空格位置正確，不需要任何額外設定。

### V5：寫回（US2）

002 完成之前，以 JSON 結果檔驗證（格式見 [contracts/results-provider.md](./contracts/results-provider.md)）：

1. 確認範例 B 副本後，記下學習單 ID，依 contracts 中的範例建立 `demo-results.json`
   （第一組成功題組 1，第三組遞補成功第 5 題）。
2. 在 `.env` 設定 `GB_RESULTS_DIR=<目錄>` 並重新啟動，把檔案存成 `<目錄>/<activity_id>.json`，
   在頁面輸入活動 ID 後執行寫回。
3. **預期**：完成訊息顯示已填 1、2、5，未填 3、4、6。
4. 在 Google Sheets 開啟範例 B 副本。**預期**：H5=CPU、H6=作業系統、G11=0；
   「（1）」「（2）」標籤、合併儲存格、欄寬與框線都和寫回前相同。
5. 把 G11 清空、在 H5 改填其他文字後再寫回一次。**預期**：G11 重新填入 0；H5 不被覆蓋，
   完成訊息列出第 1 題「已有內容，未覆蓋」（FR-026）。
6. 在範例 B 副本第 7 列上方插入一列後寫回。**預期**：拒絕寫回，說明填空格位置已改變（FR-019）。

### V6：匯出 CSV（US3）

1. 對 V5 的活動匯出 CSV，用 Excel 或 Google Sheets 開啟。
2. **預期**：標題列為「題號,組別,答案,搶答順位,結果」；第 1、2 題各一列（第一組、順位 1、成功），
   第 5 題兩列（第二組順位 1 無效、第三組順位 2 成功）；中文沒有亂碼。
3. 在答案中加入逗號、引號與換行後再匯出，**預期**：欄位沒有錯位。

### V7：權限（FR-023、FR-024）

1. 不帶 Token 呼叫 `GET /api/worksheets`，**預期**：401。
2. 以錯誤密碼連續登入超過上限，**預期**：暫時被限制，並顯示剩餘等待時間。
3. 在另一個瀏覽器視窗不登入，直接呼叫寫回 API，**預期**：401，雲端試算表沒有任何改變。

### V8：Google 授權（FR-025、FR-027）

1. 刪除 token 檔後啟動伺服器，**預期**：拒絕啟動，提示執行 `login-google`。
2. 到 Google 帳號的「第三方應用程式存取權」撤銷本系統的授權，再匯入一份學習單，
   **預期**：回應「Google 授權已失效」並提示重新登入的指令；重新執行 `login-google` 並重啟後恢復正常。
