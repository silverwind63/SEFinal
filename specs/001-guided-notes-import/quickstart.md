# Quickstart & Validation: 學習單匯入、答案寫回與結果匯出

**Feature**: [spec.md](./spec.md) | **API**: [contracts/http-api.md](./contracts/http-api.md)

本文件是**驗證指南**：說明如何在本機執行，並逐項確認各驗收情境。實作完成後，實際的測試指令與結果
依 Constitution 原則 VI 另行回報。

## 前置需求

- Linux 或 macOS，已安裝 `uv`（`uv --version`）
- 一般瀏覽器（Chrome 或 Firefox）
- 不需要網路連線、Google 帳號或任何雲端服務

## 設定

```bash
cp .env.example .env          # .env 已列入 .gitignore，不可提交
# 編輯 .env，至少設定：
#   GB_TEACHER_PASSWORD=<自行設定的密碼>
#   GB_DATA_DIR=<資料目錄，例如 ./var>
uv sync                        # 依 .python-version 建立 Python 3.12 環境並安裝相依套件
```

未設定 `GB_TEACHER_PASSWORD` 時，伺服器必須拒絕啟動，並以繁體中文說明缺少哪一個環境變數。

## 啟動

```bash
uv run python -m guided_buzz   # 預設 http://127.0.0.1:8000（可用 GB_HOST、GB_PORT 調整）
```

## 自動化測試

```bash
uv run pytest                          # 全部測試
uv run pytest tests/unit/test_parser.py -v      # 解析規則（範例 A、B 與動態產生的變體）
uv run pytest tests/unit/test_writeback.py -v   # 寫回只改動目標儲存格
uv run pytest tests/unit/test_csv_export.py -v
uv run pytest tests/integration -v              # API、權限、錯誤格式
```

測試資料：`tests/fixtures/worksheets/sample_a.xlsx`、`sample_b.xlsx`
（由規格中的兩份範例 Google Sheet 匯出），其餘變體在測試中動態產生。

## 人工驗證步驟

### V1：匯入範例 A（US1 情境 1）

1. 開啟 `http://127.0.0.1:8000`，以老師密碼登入。
2. 匯入 `tests/fixtures/worksheets/sample_a.xlsx`。
3. **預期**：題數 6、題組 0；系統題號 1–6 依序對應 G5、G7、G9、G11、G13、G15；畫面上沒有題目敘述。
4. 按「確認」，**預期**：狀態變成「已確認」。

### V2：匯入範例 B（US1 情境 2）

1. 匯入 `sample_b.xlsx`。
2. **預期**：題數 6、題組 2；題組 1 = 系統題號 1、2（H5「（1）」、H6「（2）」，原題號 1）；
   題組 2 = 系統題號 3、4（H8、H9，原題號 2）；系統題號 5 = G11、6 = G13，都不屬於題組。

### V3：取消與錯誤（US1 情境 3–5）

1. 匯入任一範例後按「取消」，**預期**：狀態變成「已取消」，無法再確認。
2. 匯入一個文字檔改副檔名而成的 `.xlsx`，**預期**：「檔案格式不符」。
3. 在 Google Sheets 複製範例 A，刪除「作答」表頭後下載再匯入，**預期**：「找不到表頭列」，並說明應有的三個表頭。
4. 在範例 A 的 G7 預先填入文字後匯入，**預期**：拒絕匯入，並指出「學習單」第 7 列沒有填空格。

### V4：不同排版（SC-001）

1. 在 Google Sheets 建立一份新學習單：表頭放在第 2 列、「作答」欄放在 B 欄、「題目」欄放在 C:E，共 3 題，
   其中第 2、3 題的題號儲存格縱向合併；下載後匯入。
2. **預期**：題數 3、題組 1（系統題號 2、3），填空格位置正確，不需要任何額外設定。

### V5：寫回（US2）

002 完成之前，以 JSON 結果檔驗證（格式見 [contracts/results-provider.md](./contracts/results-provider.md)）：

1. 確認範例 B 後，記下學習單 ID，依 contracts 中的範例建立 `demo-results.json`
   （第一組成功題組 1，第三組遞補成功第 5 題）。
2. 在 `.env` 設定 `GB_RESULTS_DIR=<目錄>` 並重新啟動，把檔案存成 `<目錄>/<activity_id>.json`，
   在頁面輸入活動 ID 後執行寫回。
3. **預期**：完成訊息顯示已填 1、2、5，未填 3、4、6。
4. 下載檔案並用 Google Sheets 開啟。**預期**：H5=CPU、H6=作業系統、G11=0；
   「（1）」「（2）」標籤、合併儲存格、欄寬與框線都和原檔相同。

### V6：匯出 CSV（US3）

1. 對 V5 的活動匯出 CSV，用 Excel 或 Google Sheets 開啟。
2. **預期**：標題列為「題號,組別,答案,搶答順位,結果」；第 1、2 題各一列（第一組、順位 1、成功），
   第 5 題兩列（第二組順位 1 無效、第三組順位 2 成功）；中文沒有亂碼。
3. 在答案中加入逗號、引號與換行後再匯出，**預期**：欄位沒有錯位。

### V7：權限（FR-023、FR-024）

1. 不帶 Token 呼叫 `GET /api/worksheets`，**預期**：401。
2. 以錯誤密碼連續登入超過上限，**預期**：暫時被限制，並顯示剩餘等待時間。
3. 在另一個瀏覽器視窗不登入，直接開啟寫回下載網址，**預期**：401，無法下載。
