# 專案資料結構維護觸發條件（給工作流程 1b / 3b 步驟參考）

主 agent 在審查後須判斷本輪變更是否會**動到專案目錄結構**（不論 tracked 或 gitignored）。

**觸發 ✅：**
- 新增 / 刪除 / 移動 / 改名 **檔案**
- 新增 / 刪除 / 移動 / 改名 **資料夾**
- **包括 gitignored 路徑下的變動**（例如 `resources/userPrompt/` 內新增檔案）
- 修改 `.gitignore`（會改變 projectStructure.md 內 tracked vs ignored 標註）

**不觸發 ❌：**
- 純內容修改（檔名 / 路徑不變）
- commit message / git config 等不影響結構的變動

**輸出位置與主 agent 動作：**
- 編輯 `resources/projectStructure/projectStructure.md`
- 同步更新：(1) 完整結構目錄樹、(2) 對應職責表（新檔加職責；刪掉的撤行）、(3) 「更新紀錄」加一行 `<YYYY-MM-DD>` 簡述變更

**場景 B：使用者手動改結構 → 回報 → 主 agent 更新**
使用者在 VSCode / 檔案總管手動改了目錄結構 → 跟主 agent 回報「我改了 X」→ 主 agent 觸發此事件，純文件編輯例外，走「✅ 標準任務收尾循環」5 步收尾。
