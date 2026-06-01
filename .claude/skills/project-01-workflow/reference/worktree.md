# Worktree 工作流程（編寫 tracked 檔時必用）

> **🎯 何時讀本檔**：本輪要編寫 / 修改**任何 tracked 檔**（動手前先 EnterWorktree），或要做收尾 ff-merge / cleanup。

每次編寫或修改 tracked 檔（不論派 subagent / agent teams 寫，或主 agent 自己改純文件），**主 agent 必須先
EnterWorktree**，提供隔離工作環境。Subagent / 主 agent 在 worktree 內改檔 + commit，避免污染主 checkout 與其他平行任務。

> **背景 session 限制**：所有 tracked 檔的編輯都要走本 5 階段（不論派 subagent 或主 agent 自己改純文件 / memory
> bootstrap）。改 gitignored 檔則不需進 worktree（worktree 看不到該檔）。

**Why（2026-05-22 實測確認為標準做法）**：worktree 隔離保護主 checkout、subagent 在 worktree 內 commit、主 agent 審查
→ 失敗可丟 worktree、成功 `--ff-only` merge 保留線性歷史。GitHub 視角只看到 main 一條分支，worktree branch 純本地暫存空間。

---

## 5 階段流程

### 階段 1：派發前 — 主 agent EnterWorktree

```
EnterWorktree(name="<task-name>")
```
- cwd 自動切到 `.claude/worktrees/<task-name>/`，新分支 `worktree-<task-name>` 從 main 拉出。
- 之後派發的 subagent 繼承 cwd，自動在 worktree 內工作。

### 階段 2：編輯 — 在 worktree 改檔 + commit

- 明確列檔名 `git add <files>`，**禁用 `-A` / `.`**（PreToolUse hook 會擋）。
- Commit 訊息：英文簡短標題 + 詳細 body + `Co-Authored-By: Claude <Model Tier> <noreply@anthropic.com>`
  （model tier 用實際派發的模型，預設 `Claude Opus`；研究類例外用 sonnet 時則為 `Claude Sonnet 4.6`）。

### 階段 3：審查 — 主 agent Read worktree 內檔案

- 逐項對照 CLAUDE.md 規範（繁中、Linux 路徑、廠商檔、git 操作）。
- 小細節不符 → 主 agent 直接修；大量偏差 → 退回 subagent 重做。
- **驗證 commit branch**：subagent 回報 commit SHA 後跑 `git branch --contains <SHA>` 確認落 `worktree-*`；顯示 `main`
  = 踩到 Gotcha M（見下方專段）。

### 階段 3a（條件性）：撰寫 Pi 端操作說明書

**觸發**：階段 3 審查通過後，主 agent 統整「subagent 回報 + 自身判斷」，確認本輪變更**實際**涉及任何 Pi 端動作（觸發
清單見 [`pi-and-structure.md`](pi-and-structure.md)）。

**動作**：主 agent 在 worktree 內**新增一個檔**到 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`
（**append-only：既有檔不動、不改、不刪**；檔名 / 內容結構規範見 [`pi-and-structure.md`](pi-and-structure.md) §pineedtodo
——寫新檔前必讀），然後 `git add` + `git commit`（subagent 的 code commit 之上多一個 commit）。

**寫完 pineedtodo 後** → 主 agent 必須提醒使用者回報：「完成後請跟我回報哪些**成功**裝上 / 啟用了，我會更新
`resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。失敗 / 未完成的不必回報。」收到回報 → 主 agent 編輯該
清單（純文件編輯例外，主 agent 自己改）。

**為何 subagent 不寫此檔**：內容是「統整 subagent 回報 + 主 agent 自身判斷」的結果，subagent 看不到主 agent 視角的補充
判斷；交由主 agent 集中撰寫保證一致性。Subagent 任務內只需在回報中列出 Pi 端需求清單。

**不觸發**：直接進階段 4。

### 階段 3b（條件性）：結構變動 → 更新 code_map / SKILL.md 路由表

**觸發**：階段 3 審查通過後，主 agent 判斷本輪變更是否**改動到專案資料結構**（觸發清單見
[`pi-and-structure.md`](pi-and-structure.md) §結構變動維護）。

**動作**：主 agent 在 worktree 內 **結構變動 → 更新 `.claude/code_map.md`**（skill 內部檔案則更 `SKILL.md` 路由表） — 然後
`git add` + `git commit`（可跟 3a 的 pineedtodo commit 合併為單一 commit）。

**不觸發**：直接進階段 4。

**場景 B（使用者手動改 → 回報）**：使用者在 VSCode / 檔案總管手動改了目錄結構 → 跟主 agent 回報 → 主 agent 觸發本
事件，純文件編輯例外，走 [`standard-workflow.md`](standard-workflow.md) 5 步收尾。

### 階段 4：收尾 — 合規後依序

```powershell
ExitWorktree(action="keep")                          # 回主 checkout
git merge worktree-<name> --ff-only                  # FF merge
git push origin main                                 # push → PostToolUse hook 嘗試自動跑 sync_pi（不可依賴）
& sync_pi.ps1                                         # 永遠手動跑（統一規則，hook 自動跑時為 idempotent no-op）
```

> **為何用 `keep` 不用 `remove`**：subagent 的 commit 還在 worktree branch 上，要從這個 branch merge 進 main；merge +
> push + sync 完才到階段 5 真正刪除。直接 `remove` 會把分支跟尚未 merge 的 commit 一起殺掉。
>
> **sync 規範**：push 後的 PostToolUse hook 是「最佳努力」、background session 內非 deterministic、**不可依賴**；
> 步驟末手動 `& sync_pi.ps1` 才是收尾保證。詳見 [`standard-workflow.md`](standard-workflow.md)。

### 階段 5：清理 — push + sync 成功後**立即執行**

```powershell
git worktree remove .claude/worktrees/<name>
git branch -d worktree-<name>
```

驗證 `git worktree list` 與 `git branch` 都乾淨。`.claude/worktrees/` 已 gitignored，即使留個空殼也不會汙染 git status。

**Windows file lock fallback（2026-05-24 L0 第一輪實測踩到）**：
- 跑過 pytest 後 worktree 內可能殘留 `__pycache__/` / `.pytest_cache/`（已加 .gitignore 但本地檔還在），Windows 上偶爾
  lock 住 `.pyc` → `git worktree remove --force` 出 `Permission denied`，連 `--force` 都救不了。
- fallback：
  ```powershell
  Remove-Item -Recurse -Force "C:\path\to\worktree" -ErrorAction SilentlyContinue
  git worktree prune       # 清掉 git 內部對該 worktree 的追蹤
  git branch -d worktree-<name>
  ```
- 為何 `-ErrorAction SilentlyContinue`：若 `Remove-Item` 也吃 lock，至少不要 throw；再 `prune` 一次往往就成功。

### 為何 cleanup 要立即執行（而非保留）

- `--ff-only` merge 後 `worktree-<name>` 與 `main` 指向同一 commit，分支沒有 unique commit、沒有資訊損失。
- 不刪 → `git branch` 越來越長、`git worktree list` 累積殘留目錄。
- 因此**預設動作就是刪**，不問使用者。例外（保留）：merge 失敗 → 必須保留以便調查。

---

## 例外狀況

### A. Merge 衝突或非 FF

`--ff-only` 失敗 → **不要 force**，保留 worktree，跟使用者討論：rebase / reset / 手動解衝突，由使用者決定。

### B. 任務只涉及 gitignored 檔

Gitignored 路徑：`resources/userPrompt/` / `resources/presentation/` / `sync_pi.ps1` /
`.claude/settings.local.json` / `.claude/worktrees/`。

**重要觀察**：subagent **不受 worktree 隔離限制**，可直接編輯主 checkout 路徑下的 gitignored 檔；但主 agent 在
worktree mode 下用 Edit/Write 寫主 checkout 會被 harness 擋掉。**結論**：純 gitignored 任務直接派 subagent 處理最順，
**主 agent 不必進 worktree**（沒可 commit 的東西，進去也沒用）。

### C. Bootstrap 例外（gitignored → tracked 轉變）

任務本身要把 gitignored 檔變 tracked 時，新建 worktree 不會包含這些檔（建立時 git 不會 checkout gitignored 內容），
導致 worktree 內看不到要 add 的檔。解法：bootstrap 任務不進 worktree，subagent 直接在主 checkout 工作。一次性例外，
下個任務恢復標準流程。歷史案例：2026-05-22 把 `resources/` 從 gitignored 改為大部分 tracked。

---

## Subagent 視野範圍速查（主 agent 派發前必看）

| 路徑類別 | Subagent 可否編輯 | 主 agent 在 worktree mode |
|---|---|---|
| Worktree 路徑下的檔案 | ✅ | ✅ Edit/Write |
| 主 checkout 下 tracked 檔 | ✅ | ❌ Edit/Write 被 harness 擋（可 Read） |
| 主 checkout 下 gitignored 檔 | ✅ | ❌ Edit/Write 被 harness 擋（可 Read） |
| 任意絕對路徑 Bash 操作 | ✅ | ✅（用 heredoc 可繞道但儘量別用） |

**判斷依據**：任務需要編輯 gitignored 檔 / 主 checkout 檔 → 派 subagent 比主 agent 自己動手順。

---

## Gotcha M：subagent commit 落 main 的完整處理

Gotcha M 是 worktree workflow 已知**偶發 bug**：subagent 在 worktree 內 commit，commit 直接落到 `main` 而非
`worktree-*` branch。完整處理必須包含「踩到後的所有後續操作」，不只第一步 push。

**驗證**：subagent 派發後跑 `git branch --contains <subagent-commit-SHA>`，顯示 `main` = Gotcha M 觸發，依下表處理：

| 階段 | 動作 | 注意 |
|---|---|---|
| 1. 驗證 | `git branch --contains <SHA>` | 顯示 `main` = Gotcha M；`worktree-*` = 正常 |
| 2. 主 agent 審查產出 | 必須 `ExitWorktree(remove)` 切回主 checkout 才能看到新檔（worktree branch 還停在舊 HEAD） | worktree branch 沒新 commit，可安全 `remove` |
| 3. 主 agent 跑驗證 | 在主 checkout 跑 pytest / lint / 任何驗證 | 主 checkout HEAD 已是 subagent commit，檔在 |
| 4a. 純測試 / 不需後續編輯 | 直接 `git push origin main` + 手動 sync | 一次到位 |
| 4b. **需要主 agent 後續編輯**（code_map / pineedtodo / 其他文件） | **進新 worktree** + 編輯 + commit + ExitWorktree(keep) + **cherry-pick** + push | 不能 ff-merge — 必失敗 |

**第二輪 worktree 必踩的 diverge 陷阱（4b 路徑核心）**：新 worktree 從 Gotcha M 之前的 base ref 分出（不是當前 main
HEAD）→ worktree branch 歷史比 main 短一個 commit → `git merge worktree-* --ff-only` **必失敗**
`Diverging branches can't be fast-forwarded`。

**解法：用 cherry-pick 取代 ff-merge**：
```bash
# ExitWorktree(keep) 後在主 checkout
git cherry-pick <worktree-commit-SHA>
git push origin main
git worktree remove .claude/worktrees/<name>
git branch -D worktree-<name>   # 用 -D 因 branch 未被 ff-merged（被 cherry-pick）
```

**徵兆速查**：ff-merge 失敗訊息 `Diverging branches can't be fast-forwarded`；`git log --oneline -5` 主 main 比
worktree branch 多至少一個 commit。

**結論**：踩到 Gotcha M 第二輪 worktree 不必再思考，直接 cherry-pick + `-D` 刪 branch（已驗證可行方案）。

**歷史案例**：2026-05-26 Wave 0：subagent commit `d60798e` 落 main → projectStructure 更新進新 worktree commit
`2976566` → ff-merge fail diverging → cherry-pick 成 main `bd77ded` → push → `branch -D` 清理。

---

**相關 reference**：[dispatch.md](dispatch.md) / [standard-workflow.md](standard-workflow.md) /
[pi-and-structure.md](pi-and-structure.md)
