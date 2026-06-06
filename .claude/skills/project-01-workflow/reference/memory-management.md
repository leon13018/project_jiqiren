# memory 健檢與整併（agent 記憶管理）

> 🎯 **何時讀本檔**：使用者要求「memory 健檢 / 記憶整併 / 記憶維護」，或健檢 script 報異常要跟進時。

auto-memory（`~/.claude/projects/<專案slug>/memory/`）的手動維護迴圈：確定性健檢（script）→ agent 整併判斷 → 對話內人定奪 → 帳本記錄。**提議經使用者批准才動手**；唯機械性修復（索引補行/刪行、frontmatter 補欄）呈報後可直接修。

## 流程（六步）

1. **跑健檢 script**（零 token，只讀不寫）：
   `pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1`
   exit 0=全綠 / 1=僅警告 / 2=有錯誤。worktree 內 cwd 推導 slug 會錯、gitignored 檔也不在 worktree——健檢一律從主 checkout 跑（必要時 `-MemoryDir` 顯式指定）。
2. **機械修復**：error 級的索引/frontmatter 結構問題，呈報後直接修；內容性問題（引用失效、過期嫌疑）進第 4 步判斷。
3. **讀帳本疫苗**：`resources/reflections/memory_ledger.md` 的 rejected 條目——已否決的提議不重提。
4. **整併四問**（逐條記憶）：
   - **還真嗎**——指名的檔案/行為/flag 實際驗證（Read/Glob 查證，不憑記憶宣稱）
   - **該升層嗎**——選層判準 hook > root CLAUDE.md > skill reference > NOTES > memory（標準：犯錯前一刻 agent 會看到哪裡）；memory 該只剩「使用者個人特質/授權/節奏」這類無處可歸的事實
   - **重複/可合併嗎**——條目間 overlap
   - **該刪嗎**——已失效或已被其他層覆蓋
5. **對話內人定奪**：每條提議用「**Why:** 一行 + diff」格式呈現，逐條批准才執行。
6. **記帳**：所有定奪寫進帳本（格式見帳本檔頭）；adopted 落實後加「落實:」行，rejected 留作疫苗。

## 邊界

- 健檢 script 只報告、絕不改檔。
- 升層落實後，原 memory 條目刪除或改成 pointer——不留雙權威。
- 記憶不得寫入敏感資訊（密碼 / 金鑰 / PII）。
