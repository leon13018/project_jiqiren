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
4. `git push origin main`
5. **`& sync_pi.ps1`（PowerShell tool）— 永遠手動跑，不論 live / background session**。hook 即使自動跑也是 idempotent no-op（`Already up to date`，~3s 成本可接受）。

> ⚠️ **為何不能信賴 hook 自動 sync（2026-05-28 更新）：** PostToolUse hook 在 background session 已知非 deterministic；**live session 也確認偶發不觸發**（push `048ddc2`：regex 測試 True，script 正常，log 完全無 entry）。根因不明（Claude Code 端）。完整記錄：`.claude/hooks/NOTES.md` Gotcha N。

詳細補充準則 / 歷史 bug 教訓 → memory `standard-workflow`
