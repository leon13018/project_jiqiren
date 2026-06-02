# Worktree 工作流程（編寫 tracked 檔時必用）

> **🎯 何時讀本檔**：本輪要編寫 / 修改**任何 tracked 檔**（動手前先 EnterWorktree），或要做收尾 ff-merge / cleanup / 處理 commit 落 main（Gotcha M）。

## 目錄
- 5 階段流程（含條件性 3a/3b）
- 例外狀況 A/B/C
- Subagent 視野範圍速查
- Gotcha M：subagent commit 落 main 的完整處理

每次編寫 / 修改 tracked 檔（不論派 subagent 或主 agent 自己改純文件）**主 agent 必須先 EnterWorktree**，提供隔離環境、避免污染主 checkout 與平行任務。改 gitignored 檔則不需進 worktree（worktree 看不到該檔）。

> **Why**：worktree 隔離保護主 checkout、subagent 在內 commit、主 agent 審查 → 失敗可丟、成功 `--ff-only` merge 保留線性歷史。GitHub 只見 main 一條，worktree branch 是本地暫存。

---

## 5 階段流程

**階段 1 — 派發前 EnterWorktree**
```
EnterWorktree(name="<task-name>")
```
cwd 切到 `.claude/worktrees/<task-name>/`，新分支 `worktree-<task-name>` 從 main 拉出；派發的 subagent 繼承 cwd 自動在內工作。

**階段 2 — 編輯 + commit**
- 明列 `git add <files>`，**禁 `-A`/`.`**（hook 擋）。
- Commit：英文簡短標題 + body + `Co-Authored-By: Claude <Model Tier> <noreply@anthropic.com>`（用實際派發模型，預設 Opus）。

**階段 3 — 審查**：主 agent Read worktree 內檔，逐項對照 CLAUDE.md（繁中 / Linux 路徑 / 廠商檔 / git）。小細節不符自己修、大量偏差退回重做。**驗 branch**：subagent 回報 SHA 後 `git branch --contains <SHA>` 確認落 `worktree-*`；顯示 `main` = Gotcha M（見文末）。

**階段 3a（條件性）— Pi 端操作說明書**：本輪變更涉 Pi 端動作（觸發清單見 [pi-and-structure.md](pi-and-structure.md) §Pi 端操作觸發條件）→ 主 agent 在 worktree 內**新增**一檔 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（append-only，格式見 pi-and-structure.md §pineedtodo）→ add + commit → 提醒使用者回報成功項。subagent 不寫此檔（只在回報列 Pi 需求），由主 agent 集中撰寫保一致。不觸發直接進階段 4。

**階段 3b（條件性）— 結構變動更新 code_map**：本輪動到專案結構（觸發 + 巢狀判準見 [pi-and-structure.md](pi-and-structure.md) §結構變動維護）→ 更新「變動所在那層」的 `.claude/code_map.md`（skill 內部檔則更 SKILL.md 路由表）→ commit（可與 3a 合併）。不觸發直接進階段 4。

**階段 4 — 收尾**
```powershell
ExitWorktree(action="keep")              # 回主 checkout（commit 還在 branch 上要拿來 merge，故 keep 不 remove）
git merge worktree-<name> --ff-only
git push origin main
& sync_pi.ps1                            # 永遠手動跑（背景 session hook 非 deterministic、不可依賴；雙保險理由見 standard-workflow.md）
```

**階段 5 — 清理（push+sync 成功後立即執行；預設就刪不問人）**
```powershell
git worktree remove .claude/worktrees/<name>
git branch -d worktree-<name>
```
`--ff-only` 後兩 branch 同 commit、無資訊損失，故預設刪（例外：merge 失敗 → 保留以便調查）。
**Windows file lock fallback**（pytest 後殘留 `__pycache__`/`.pytest_cache` 偶 lock `.pyc`，`git worktree remove --force` 報 Permission denied）：
```powershell
Remove-Item -Recurse -Force "C:\path\to\worktree" -ErrorAction SilentlyContinue
git worktree prune
git branch -d worktree-<name>
```

---

## 例外狀況

- **A. Merge 非 FF / 衝突**：`--ff-only` 失敗 → **不要 force**，保留 worktree、跟使用者討論 rebase/reset/手動解。
- **B. 只涉 gitignored 檔**（`resources/userPrompt/` / `resources/presentation/` / `sync_pi.ps1` / `.claude/settings.local.json` / `.claude/worktrees/`）：subagent 不受 worktree 隔離、可直接編主 checkout 的 gitignored 檔；主 agent 在 worktree mode 寫主 checkout 會被 harness 擋。→ 純 gitignored 任務直接派 subagent，**主 agent 不必進 worktree**。
- **C. Bootstrap（gitignored→tracked）**：新 worktree 不 checkout gitignored 內容 → 看不到要 add 的檔。解法：bootstrap 任務不進 worktree，subagent 直接在主 checkout 工作（一次性例外）。

---

## Subagent 視野範圍速查（派發前必看）

| 路徑類別 | Subagent 可編輯 | 主 agent 在 worktree mode |
|---|---|---|
| Worktree 路徑下檔案 | ✅ | ✅ Edit/Write |
| 主 checkout tracked 檔 | ✅ | ❌ Edit/Write 被擋（可 Read） |
| 主 checkout gitignored 檔 | ✅ | ❌ Edit/Write 被擋（可 Read） |
| 任意絕對路徑 Bash | ✅ | ✅（heredoc 可繞但儘量別用） |

**判準**：任務需編輯 gitignored / 主 checkout 檔 → 派 subagent 比主 agent 自己動手順。

---

## Gotcha M：subagent commit 落 main 的完整處理

已知**偶發 bug**：subagent 在 worktree 內 commit，commit 卻落到 `main` 而非 `worktree-*`。**驗證**：`git branch --contains <SHA>` 顯示 `main` 即觸發，依下表處理：

| 階段 | 動作 | 注意 |
|---|---|---|
| 1. 驗證 | `git branch --contains <SHA>` | `main` = Gotcha M；`worktree-*` = 正常 |
| 2. 審查產出 | `ExitWorktree(remove)` 切回主 checkout 才看得到新檔 | worktree branch 無新 commit，可安全 remove |
| 3. 跑驗證 | 主 checkout 跑 pytest/lint | 主 checkout HEAD 已是 subagent commit |
| 4a. 不需後續編輯 | 直接 `git push origin main` + 手動 sync | 一次到位 |
| 4b. 需主 agent 後續編輯 | 進**新** worktree 編輯 + commit + ExitWorktree(keep) + **cherry-pick**（非 ff-merge）+ push | 見下 |

**4b 的 diverge 陷阱**：新 worktree 從 Gotcha M 之前的 base 分出 → branch 歷史比 main 短一 commit → `git merge --ff-only` **必失敗** `Diverging branches can't be fast-forwarded`。**解法用 cherry-pick**：
```bash
git cherry-pick <worktree-commit-SHA>
git push origin main
git worktree remove .claude/worktrees/<name>
git branch -D worktree-<name>   # -D 大寫，因未被 ff-merged
```
**徵兆速查**：ff-merge 失敗訊息 `Diverging branches can't be fast-forwarded`；`git log --oneline -5` 主 main 比 worktree branch 多 ≥1 commit。踩到不必再想，直接 cherry-pick + `-D`（2026-05-26 Wave 0 `d60798e`→cherry-pick `bd77ded` 驗證可行）。

---

**相關 reference**：[dispatch.md](dispatch.md) / [standard-workflow.md](standard-workflow.md) / [pi-and-structure.md](pi-and-structure.md)
