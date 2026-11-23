# 課堂搶答系統（SpecKit 組）

軟體工程期末專題。老師把填空式學習單（Guided Notes，存放在 Google Sheets）匯入系統作為搶答題目，
活動結束後再把搶答成功的答案直接寫回原本的 Google Sheets 填空格，並可匯出活動結果 CSV。

規格、計畫與任務都在 [`specs/`](specs/)，PlantUML 圖表在 [`diagrams/`](diagrams/)，專案原則見
[`.specify/memory/constitution.md`](.specify/memory/constitution.md)。

| 功能 | 規格 | 狀態 |
|------|------|------|
| 001 學習單匯入、答案寫回與結果匯出 | [specs/001-guided-notes-import](specs/001-guided-notes-import/) | 已實作 |
| 002 線上分組搶答活動 | [specs/002-online-buzz-activity](specs/002-online-buzz-activity/) | 已實作（待人工驗證） |

## 需求

- macOS 或 Linux，已安裝 [`uv`](https://docs.astral.sh/uv/)（會自動準備 Python 3.12）
- 匯入與寫回需要網路連線；自動化測試不需要
- 一個 Google 帳號，用來建立 OAuth client（見下方）
- 修改圖表時需要 Java 與 PlantUML（`brew install plantuml`）

## 一次性設定：Google OAuth

系統以老師自己的 Google 帳號（OAuth）直接讀寫 Google Sheets。每位組員在自己的電腦各做一次。OAuth client 設定檔與登入後的 token 檔**不可**放進 repo，也不可透過聊天或雲端硬碟傳給別人。

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

## 設定與啟動

```bash
cp .env.example .env    # .env 已列入 .gitignore，不可提交
# 編輯 .env，至少設定 GB_TEACHER_PASSWORD 與 GB_GOOGLE_OAUTH_CLIENT_FILE
uv sync
uv run python -m guided_buzz login-google   # 第一次使用，或授權失效時
uv run python -m guided_buzz
```

開啟 http://127.0.0.1:8000 ，以老師密碼登入。缺少必要環境變數或尚未登入 Google 時，伺服器會拒絕啟動並說明原因。

伺服器固定只執行一個程序（uvicorn `workers=1`）：搶答活動的狀態與判定用的鎖都在記憶體中，多個程序會各自判定而失去一致性。

### 進行一場搶答活動（002）

本專題只在單一電腦上運作，以同一個瀏覽器的多個**視窗或分頁**分別扮演老師與各組學生；每個視窗的身分各自獨立。

1. 老師視窗：在首頁匯入並確認學習單，再開啟「搶答主控台」（`/teacher.html`），選擇學習單、輸入組名（每行一組）後建立活動。
2. 主控台會顯示每組的組別代碼，請私下告訴各組。
3. 學生視窗：開啟 `/student.html`，輸入組別代碼加入。同一組可以有多個視窗。
4. 老師按「開始搶答」：所有題目同時開放，最先送出的組別搶答成功；題組要一次送出全部答案。
   領先其他組 K 題以上的組別，每次成功後冷卻 N 秒。
5. 老師可在主控台即時看到所有送出與順位，並可把成功答案「判定無效」，由下一順位遞補。
6. 老師按「結束搶答」：結果寫入資料庫，學生畫面顯示結果。回到首頁，從「已結束的活動」選單選擇這場活動，即可寫回學習單或匯出 CSV。

伺服器重新啟動時，尚未結束的活動會標示為「已中斷」，需要重新建立；已結束的活動結果會保留。

### 環境變數

只列名稱與用途，實際值請放在 `.env`（範例見 [`.env.example`](.env.example)）。

| 變數 | 必填 | 用途（預設值） |
|------|------|----------------|
| `GB_TEACHER_PASSWORD` | ✅ | 老師登入密碼 |
| `GB_GOOGLE_OAUTH_CLIENT_FILE` | ✅ | OAuth client JSON（桌面應用程式）路徑 |
| `GB_GOOGLE_TOKEN_FILE` | | `login-google` 儲存 token 的位置（`<GB_DATA_DIR>/google-token.json`） |
| `GB_DATA_DIR` | | SQLite 資料庫目錄（`./var`） |
| `GB_HOST`、`GB_PORT` | | 監聽位址與連接埠（`127.0.0.1`、`8000`） |
| `GB_SHEETS_TIMEOUT_SECONDS` | | Sheets API 逾時秒數（10） |
| `GB_MAX_QUESTIONS` | | 每份學習單的題數上限（500） |
| `GB_HEADER_LABEL_NUMBER`、`GB_HEADER_LABEL_QUESTION`、`GB_HEADER_LABEL_ANSWER` | | 表頭標籤（題號、題目、作答） |
| `GB_TOKEN_TTL_SECONDS` | | 老師 Token 有效秒數（28800） |
| `GB_LOGIN_MAX_FAILURES`、`GB_LOGIN_LOCK_SECONDS` | | 連續登入失敗上限與鎖定秒數（5、300） |
| `GB_RESULTS_DIR` | | 搶答結果 JSON 檔目錄，只供測試與驗證；設定後寫回與匯出改讀 JSON 檔（未設定時讀取搶答活動保存的結果） |
| `GB_MAX_TEAMS`、`GB_TEAM_NAME_MAX` | | 組數上限、組名長度上限（20、20） |
| `GB_MAX_ANSWER_LENGTH` | | 答案長度上限（200） |
| `GB_FAIRNESS_ENABLED`、`GB_COOLDOWN_SECONDS`、`GB_COOLDOWN_LEAD` | | 公平機制預設值：是否啟用、冷卻秒數 N、領先門檻 K（true、10、2）；建立活動時可覆寫 |
| `GB_JOIN_MAX_FAILURES`、`GB_JOIN_LOCK_SECONDS` | | 每個視窗輸錯組別代碼的上限與鎖定秒數（5、60） |
| `GB_JOIN_GLOBAL_FAILURES_PER_MIN` | | 全體每分鐘輸錯上限（60） |
| `GB_WS_AUTH_TIMEOUT_SECONDS` | | WebSocket 連線後必須送出驗證訊息的秒數（5） |

## 學習單格式規則

系統不寫死任何儲存格位置，只要學習單遵守以下規則即可（詳見 [research R3](specs/001-guided-notes-import/research.md)）：

1. **表頭列**：同一列同時有「題號」「題目」「作答」三個表頭（文字可用環境變數修改），每個表頭的欄位範圍以其合併範圍為準。
2. **題目列**：表頭以下、「題目」欄位範圍內有文字的列；空白分隔列會被略過。
3. **填空格**：題目列在「作答」欄位範圍內的空白儲存格（合併儲存格算一格）；每個題目列必須恰好有一個。
   作答範圍內的非空白文字（例如「（1）」）視為子題標籤。
4. **題組**：「題號」欄的儲存格向下合併、跨越多個題目列時，這些題目列構成一個題組。
5. 有多個工作表時，只處理含表頭的工作表，題號依工作表順序連續編號。

## 測試

```bash
uv run pytest -v
```

每次開 pull request 或推送到 `main` 時，GitHub Actions（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）會自動執行同一個指令；
CI 通過後才 merge 進 `main`。

自動化測試一律使用 `FakeSheetsGateway` 取代 Google 服務，不連網。`tests/fixtures/sheets/` 是兩份範例學習單的
真實 Sheets API 回應快照（取得方式見該目錄的 README）。
需要實際連線 Google 的流程，請照 [001 quickstart](specs/001-guided-notes-import/quickstart.md) 的 V1–V8 人工驗證；
搶答活動請照 [002 quickstart](specs/002-online-buzz-activity/quickstart.md) 的 V1–V7 以多個瀏覽器視窗驗證。

## 圖表

修改 `diagrams/**/*.puml` 後，在 repo 根目錄重新產生 PNG，並與 `.puml` 一起提交：

```bash
plantuml -tpng "./diagrams/**/*.puml"
```

## 常見問題

- **`No module named guided_buzz`**：如果專案放在 iCloud 同步的資料夾（例如「桌面」或「文件」），iCloud 會把 `.venv`
  裡的檔案標成隱藏，Python 就讀不到。請把虛擬環境放在 iCloud 不會同步的 `.venv.nosync`：

  ```bash
  rm -rf .venv && mkdir .venv.nosync && ln -s .venv.nosync .venv && uv sync
  ```

## 外部套件與授權

| 套件 | 用途 | 授權 |
|------|------|------|
| FastAPI | Web 框架 | MIT |
| Uvicorn | ASGI 伺服器 | BSD-3-Clause |
| Pydantic | 輸入驗證 | MIT |
| google-api-python-client、google-auth、google-auth-oauthlib | Google Sheets API、OAuth 登入 | Apache-2.0 |
| python-dotenv | 載入 `.env` | BSD-3-Clause |
| pytest、HTTPX | 測試 | MIT、BSD-3-Clause |
| PlantUML | 產生圖表（開發工具，不隨程式散布） | GPL（PlantUML 另提供其他授權版本） |

版本以 `uv.lock` 為準。
