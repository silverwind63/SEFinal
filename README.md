# 課堂搶答系統（SpecKit 組）

軟體工程期末專題。老師把填空式學習單（Guided Notes，存放在 Google Sheets）匯入系統作為搶答題目，
活動結束後再把搶答成功的答案直接寫回原本的 Google Sheets 填空格，並可匯出活動結果 CSV。

規格、計畫與任務都在 [`specs/`](specs/)，PlantUML 圖表在 [`diagrams/`](diagrams/)，專案原則見
[`.specify/memory/constitution.md`](.specify/memory/constitution.md)。

| 功能 | 規格 | 狀態 |
|------|------|------|
| 001 學習單匯入、答案寫回與結果匯出 | [specs/001-guided-notes-import](specs/001-guided-notes-import/) | 已實作 |
| 002 線上分組搶答活動 | [specs/002-online-buzz-activity](specs/002-online-buzz-activity/) | 尚未實作 |

## 需求

- macOS 或 Linux，已安裝 [`uv`](https://docs.astral.sh/uv/)（會自動準備 Python 3.12）
- 匯入與寫回需要網路連線；自動化測試不需要
- 一個 Google 帳號，用來建立 service account（見下方）
- 修改圖表時需要 Java 與 PlantUML（`brew install plantuml`）

## 一次性設定：Google service account

系統以 service account（系統帳號）直接讀寫 Google Sheets。每位組員在自己的電腦各做一次：

1. 到 Google Cloud Console 建立專案，啟用「Google Sheets API」。
2. 建立 service account，下載 JSON 金鑰，存放在 **repo 以外**的位置（例如 `~/.config/guided-buzz/sa.json`）。
3. 記下 service account 的 email（形如 `xxx@<專案>.iam.gserviceaccount.com`）。
4. 在 Google Sheets 把學習單「共用」給這個 email，權限設為「編輯者」。

金鑰檔不可放進 repo，也不可透過聊天或雲端硬碟傳給別人。

## 設定與啟動

```bash
cp .env.example .env    # .env 已列入 .gitignore，不可提交
# 編輯 .env，至少設定 GB_TEACHER_PASSWORD 與 GB_GOOGLE_CREDENTIALS_FILE
uv sync
uv run python -m guided_buzz
```

開啟 http://127.0.0.1:8000 ，以老師密碼登入。缺少必要環境變數或金鑰檔無效時，伺服器會拒絕啟動並說明原因。

### 環境變數

只列名稱與用途，實際值請放在 `.env`（範例見 [`.env.example`](.env.example)）。

| 變數 | 必填 | 用途（預設值） |
|------|------|----------------|
| `GB_TEACHER_PASSWORD` | ✅ | 老師登入密碼 |
| `GB_GOOGLE_CREDENTIALS_FILE` | ✅ | service account 金鑰檔路徑 |
| `GB_DATA_DIR` | | SQLite 資料庫目錄（`./var`） |
| `GB_HOST`、`GB_PORT` | | 監聽位址與連接埠（`127.0.0.1`、`8000`） |
| `GB_SHEETS_TIMEOUT_SECONDS` | | Sheets API 逾時秒數（10） |
| `GB_MAX_QUESTIONS` | | 每份學習單的題數上限（500） |
| `GB_HEADER_LABEL_NUMBER`、`GB_HEADER_LABEL_QUESTION`、`GB_HEADER_LABEL_ANSWER` | | 表頭標籤（題號、題目、作答） |
| `GB_TOKEN_TTL_SECONDS` | | 老師 Token 有效秒數（28800） |
| `GB_LOGIN_MAX_FAILURES`、`GB_LOGIN_LOCK_SECONDS` | | 連續登入失敗上限與鎖定秒數（5、300） |
| `GB_RESULTS_DIR` | | 搶答結果 JSON 檔目錄；002 完成前用來驗證寫回與匯出（未設定則停用） |

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

自動化測試一律使用 `FakeSheetsGateway` 取代 Google 服務，不連網。`tests/fixtures/sheets/` 的兩份範例快照目前是依規格
**手動建構**；取得 service account 後，請用 `scripts/capture_sheet_fixture.py` 抓取真實範例覆蓋（見該目錄的 README）。
需要實際連線 Google 的流程，請照 [quickstart](specs/001-guided-notes-import/quickstart.md) 的 V1–V7 人工驗證。

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
| google-api-python-client、google-auth | Google Sheets API | Apache-2.0 |
| python-dotenv | 載入 `.env` | BSD-3-Clause |
| pytest、HTTPX | 測試 | MIT、BSD-3-Clause |
| PlantUML | 產生圖表（開發工具，不隨程式散布） | GPL（PlantUML 另提供其他授權版本） |

版本以 `uv.lock` 為準。
