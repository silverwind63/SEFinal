# Google Sheets 回應快照

`sample_a.json`、`sample_b.json` 是 Sheets API `spreadsheets.get` 回應格式的測試資料，
內容依 `specs/001-guided-notes-import/spec.md` 的「參考範例學習單」對照表與 research R3 的結構分析**手動建構**
（題目敘述為佔位文字）。

完成 OAuth 設定與 `login-google` 後，請以 `scripts/capture_sheet_fixture.py` 抓取真實範例的回應覆蓋這兩個檔案（tasks T005），
並確認測試仍然通過。快照只含試算表內容，不含任何憑證。
