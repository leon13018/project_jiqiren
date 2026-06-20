# myProgram/webui/ — 本層導引

> **本層結構索引：`.claude/code_map.md`——任何「webui 裡的檔在哪 / 結構」務必第一優先讀它。**

點餐網頁前端（buildless：無打包 / 無框架 runtime / 無測試框架）。與 `web/`（FastAPI transport）分工：本層只管畫面，狀態由 `web/` 經 WS 鏡像驅動。

- **雙模式**：**live**（預設，WS 連 `web/app.py`；狀態一律等機器人 emit phase 才變、觸控只送命令）/ **demo**（`?demo=1`，本機假資料切換器 + 觸控直接改 state，供 UI 預覽）。改互動行為**兩模式都要顧**。
- **跑法**：獨立預覽 `python3.11 myProgram/webui/serve.py 8137`；真機 live `python3.11 -m myProgram --web`（FastAPI 出靜態檔 + WS）。
- **Pi 渲染限制**：Pi 4 自瀏覽器跑不動（GPU + Chromium<111 無 OKLCH）→ demo 在 client 筆電渲染、Pi 只當 server；改 CSS 用新特性前先顧相容性。
- **覆蓋層 / 卡片狀態一律靠機器人 emit 的 phase 驅動**（live），不可用前端本地樂觀旗號（觸發可能來自語音 / 自動結帳非 UI）。
- **無 JS 測試框架**：驗證 = `node --check app.js` + 筆電 by-eye（live 路徑 Pi by-ear）。改 `app.js` 比照 myProgram 其餘層走 spec/plan → worktree。
- 設計演進 / 決策見 `resources/specs/webui_*`；完整安全紅線 + 繁中規範見 root `CLAUDE.md`、workflow 協議見 `project-01-workflow` skill，本檔不重述。
