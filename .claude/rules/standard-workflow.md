# 標準任務收尾循環（滿足條件才做）

> **背景 session 限制：所有 tracked 檔的編輯都要走「Worktree 工作流程」5 階段**（不論派 subagent 或主 agent 自己改純文件 / memory bootstrap）。本節定義 git 收尾的**內核步驟**，會內嵌在 Worktree 階段 2 / 3a（commit）與階段 4（push / sync）內。差別只在「誰寫」 — 派 subagent 寫 vs 主 agent 自己寫。
> 改 gitignored 檔則不需進 worktree（worktree 看不到該檔）。

**觸發條件：** 本輪有任何 **git 會追蹤的檔案**改動（即 `.gitignore` 之外的檔案，新增 / 修改 / 刪除皆算）。判斷依據：`git status` 是否非空。

**不觸發 → 直接結束，跳過收尾：**
- 純聊天 / 解答問題 / 上網查資料
- Plan mode 規劃討論（尚未動手實作）
- 變更全在 ignored 路徑（`resources/presentation/` / `resources/userPrompt/` / `sync_pi.ps1` / `.claude/settings.local.json` / `.claude/worktrees/`）→ `git status` 看不到任何 diff
- 沒有任何檔案改動

**觸發時依序執行（5 步）：**
1. `git status` + `git diff` 確認變更範圍
1a. **（條件性）撰寫 Pi 端操作說明書**：若本輪變更涉及 Pi 端動作（見 `.claude/rules/pi-side-trigger.md`），主 agent **新增一個檔**到 `resources/pineedtodo/<檔名>.md`（**append-only：既有檔不動**），納入下一步的 `git add`。不觸發直接跳過。
1b. **（條件性）更新 projectStructure.md**：若本輪變更改動到專案資料結構（見 `.claude/rules/projectstructure-trigger.md`），主 agent 編輯 `resources/projectStructure/projectStructure.md`（目錄樹 + 職責表 + 更新紀錄），納入下一步的 `git add`。不觸發直接跳過。
2. `git add <具體檔名>`（不用 `-A` / `.` — PreToolUse hook 會擋）
3. `git commit -m "..."` 英文簡短訊息，附 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
4. `git push origin main` — PostToolUse hook 會自動跑 `auto-sync-pi.ps1`（async + 120s timeout），但 **background session 內非 deterministic**。
5. **永遠手動跑** `& sync_pi.ps1`（PowerShell tool）— **統一規則，不分 session 類型**。hook 自動跑時手動跑是 idempotent no-op（git pull → Already up to date），~3s SSH 成本可接受；省得判斷 session 類型 / 記憶 hook 觸發行為。

> 🪝 自動化說明：步驟 4 的 hook 是「最佳努力」、不是依賴；步驟 5 才是收尾保證。失敗 / 重跑 / background-session-skip 細節見 `.claude/hooks/NOTES.md` §6 Gotcha N。

詳細補充準則 / 歷史 bug 教訓 → memory `standard-workflow`
