# Verification Record: 線上分組搶答活動

**Feature**: [spec.md](./spec.md) | **Quickstart**: [quickstart.md](./quickstart.md) | **Tasks**: T064

依 Constitution 原則 VI 記錄測試指令、結果與人工驗證。

## 環境

| 項目 | 內容 |
|------|------|
| 日期 | 2026-11-23 |
| 系統 | Linux，Python 3.12（uv 管理），伺服器 `127.0.0.1:8000`（uvicorn workers=1） |
| 操作方式 | 同一台電腦、同一個瀏覽器的多個視窗：老師視窗（`/`、`/teacher.html`）與各組學生視窗（`/student.html`） |
| 學習單 | 以 Google Sheets 匯入並確認的 Guided Notes |

## 自動化測試

```bash
uv run pytest -v
```

| 執行處 | 結果 |
|--------|------|
| 本機（commit `a97498e` 之後） | 262 passed（001 的 130 個加上 002 的 132 個） |

002 的測試重點：

| 項目 | 測試檔 |
|------|--------|
| 判定、順位、題組送出、判定無效與遞補、檢視過濾 | `tests/unit/test_engine.py` |
| 同時送出重複 100 次，每個搶答單位恰好一個成功者（SC-002） | `tests/unit/test_engine_concurrency.py` |
| 公平機制（假時鐘），以及有無公平機制的模擬比較（SC-006） | `tests/unit/test_fairness.py`、`tests/integration/test_fairness_simulation.py` |
| 結束前學生取得他組資料一律被拒（FR-014、SC-003） | `tests/integration/test_isolation.py` |
| WebSocket 驗證、快照、階段同步、撤銷 | `tests/integration/test_realtime.py` |
| 1 個老師與 12 個學生連線，2 秒內同步（SC-001） | `tests/integration/test_latency.py` |
| 重啟後未結束的活動作廢、已結束的結果保留（FR-026、FR-027） | `tests/integration/test_restart.py` |
| 結果接上 001 的寫回與 CSV（FR-017） | `tests/integration/test_results_provider.py` |
| log 不含組別代碼、Token、答案 | `tests/integration/test_no_secrets.py` |

## 人工驗證

依 [quickstart.md](./quickstart.md) 以多個瀏覽器視窗操作，使用者於 2026-11-23 回報驗證通過。

## 驗證過程中發現並修正的問題

| 問題 | 原因 | 修正（commit `a97498e`） |
|------|------|--------------------------|
| 學生加入組別後要手動重新整理才看得到題目 | 未安裝 WebSocket 函式庫，`/ws` 回 404；TestClient 不需要該函式庫，自動化測試沒有發現 | 新增 `websockets` 相依套件與檢查測試；加入後先以 HTTP 取得本組畫面 |
| 填了答案卻顯示「第 1 題的答案不可為空白」 | 輸入框名稱為題號，`form.elements["1"]` 被瀏覽器當成索引而讀到其他元素 | 輸入框名稱改為 `q<題號>`，以名稱精確查詢 |
| log 出現 `/favicon.ico` 404 | 瀏覽器自動要求網站圖示 | 頁面加上空白圖示 |
