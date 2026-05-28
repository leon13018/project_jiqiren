# Worktree 工作流程（編寫 tracked 檔時必用）

每次派發 subagent / agent teams 編寫或修改程式碼，**主 agent 必須先 EnterWorktree**，提供隔離工作環境。Subagent 在 worktree 內改檔 / commit，避免污染主 checkout 與其他平行任務。

**5 個階段：**

1. **派發前**：主 agent `EnterWorktree(name="<task-name>")` → cwd 切到 `.claude/worktrees/<task-name>/`，新分支 `worktree-<task-name>`。
2. **編輯**：subagent / team 在 worktree 內改檔 + commit（明確列檔名 `git add <files>`，禁用 `-A` / `.`）。
3. **審查**：主 agent Read worktree 內檔案，逐項對照 CLAUDE.md 規範。不合規退回重做。
3a. **（條件性）撰寫 Pi 端操作說明書**：階段 3 審查通過後，主 agent 統整「subagent 回報 + 自身判斷」，確認本輪變更**實際**涉及任何 Pi 端動作（見 `.claude/rules/pi-side-trigger.md`）→ **新增一個檔**到 `resources/pineedtodo/<檔名>.md`（**append-only：既有檔不動**），在 worktree 內 `git add` + `git commit`（subagent 的 code commit 之上多一個 commit）。不觸發直接進階段 4。
3b. **（條件性）更新 projectStructure.md**：階段 3 審查通過後，主 agent 判斷本輪變更是否**改動到專案資料結構**（觸發清單見 `.claude/rules/projectstructure-trigger.md`）→ 觸發則編輯 `resources/projectStructure/projectStructure.md`（目錄樹 + 職責表 + 更新紀錄），在 worktree 內一併 `git add` + `git commit`（可與 3a 的 commit 合併為單一 commit）。不觸發直接進階段 4。
4. **收尾（合規後）**：
   - `ExitWorktree(action="keep")` → 切回主 checkout
   - `git merge worktree-<task-name> --ff-only`
   - `git push origin main`
   - **`& sync_pi.ps1`（PowerShell tool）— 永遠手動跑**（不論 live / background）。hook 即使自動跑也是 idempotent no-op（`Already up to date`，~3s 成本可接受）。⚠️ hook 在 live session 也偶發不觸發（2026-05-28 確認）— 見 `NOTES.md` Gotcha N。
5. **清理（push + sync 成功後立即執行）**：
   - `git worktree remove .claude/worktrees/<task-name>`
   - `git branch -d worktree-<task-name>`
   - 確認 `git worktree list` 與 `git branch` 乾淨
   - **Windows file lock fallback**（2026-05-24 L0 第一輪實測踩到）：跑過 pytest 後若 `git worktree remove --force` 仍出 `Permission denied`（即使 `.gitignore` 已含 `__pycache__/` + `.pytest_cache/`，本地檔還在且 Windows 偶 lock `.pyc`），改用 PowerShell：
     ```powershell
     Remove-Item -Recurse -Force "C:\path\to\worktree" -ErrorAction SilentlyContinue
     git worktree prune
     git branch -d worktree-<task-name>
     ```

**例外：**
- Merge 衝突或非 FF → 保留 worktree，跟使用者討論。
- 任務只涉及 gitignored 檔（`resources/userPrompt/`、`resources/presentation/`）→ subagent **不受 worktree 隔離限制**，可直接編輯主 checkout 路徑下的 gitignored 檔；但主 agent 在 worktree mode 下 Edit/Write 主 checkout 會被擋。所以這類任務派 subagent 處理最順。

詳細協議 / 視野範圍速查 / cleanup 原理 → memory `worktree-workflow`
