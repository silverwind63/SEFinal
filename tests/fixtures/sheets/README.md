# Google Sheets 回應快照

`sample_a.json`、`sample_b.json` 是期末專題說明附的兩份範例學習單（單題範本、題組＋單題範本）的
Sheets API `spreadsheets.get` 真實回應，於 2026-11-22 以 `scripts/capture_sheet_fixture.py` 取得（tasks T005）。

- 只包含試算表內容（名稱、儲存格文字、合併範圍），不含任何憑證、token 或帳號資訊。
- 範例學習單更新時，重新執行下列指令覆蓋，並確認 `uv run pytest` 仍然通過：

```bash
uv run python scripts/capture_sheet_fixture.py <範例網址> tests/fixtures/sheets/sample_a.json
```
