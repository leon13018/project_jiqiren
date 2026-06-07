# code_map 強制守門 Stop hook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增第 4 支 Stop hook `stop-check-codemap.ps1`——turn 結束時用 git 快照比對偵測結構變動（新增/刪除/改名）+ 自動跑 codemap-health 死引用健檢，未處理則 block 一次強制 Claude 更新對應層 code_map。

**Architecture:** 純 PowerShell Stop hook + `.claude/hooks/state/codemap/` 三個 state 檔（快照清單 / 已提醒集合 / 已 ack 死引用）。同變動集只 block 一次（集合包含比對，非 hash——允許 Claude 修掉部分項目後放行）。spec：`codemap_guard_stop_hook_2026-06-07_spec.md`。

**Tech Stack:** PowerShell 5.1（hook 運行時）、git ls-files、現有 `codemap-health.ps1`（in-process 重用）。

**強制前置（執行者必讀）：**
1. skill `project-01-workflow` 的 `reference/hooks-gotchas.md`（.ps1 編碼/BOM/fail-open 全集）與 `reference/hooks-system.md` §維護指南。
2. `.claude/` 是 tracked → **全程在 worktree 內作業**（`reference/worktree.md` 5 階段）。
3. 本 plan 不涉 Pi 端操作 → 無 pineedtodo（階段 3a 跳過）。
4. 測試 hook 時 **cwd 必須是主 checkout**（hook 有 worktree 偵測，在 worktree cwd 下跑會直接早退）——所有驗證指令已寫死 `cd` 到主 checkout。

---

### Task 0: 進 worktree

**Files:** 無（環境準備）

- [ ] **Step 0.1: EnterWorktree**

```
EnterWorktree(name="codemap-guard")
```
預期：cwd 切到 `.claude/worktrees/codemap-guard/`，分支 `worktree-codemap-guard` 自 main 拉出。

---

### Task 1: 新增 hook 腳本 `stop-check-codemap.ps1`

**Files:**
- Create: `<worktree>/.claude/hooks/stop-check-codemap.ps1`

- [ ] **Step 1.1: Write 完整腳本**

完整內容如下（Write 工具寫入後 Step 1.2 必補 BOM——gotcha #1）：

```powershell
# stop-check-codemap.ps1 — Stop hook：code_map 強制守門
#
# 偵測（確定性，零模型參與）：
#   1. git 快照比對（tracked + untracked，自然排除 gitignored）→ 新增/刪除集合（改名＝刪+增成對）
#   2. codemap-health.ps1 死引用掃描（in-process 重用）
# 過關機制（同 sales-dirty 哲學，block 一次不 deadlock）：
#   - 有未處理項目且未提醒過 → decision:block + 路徑清單；項目集寫入 reminded.txt
#   - 再次 Stop 且無「新」項目（當前集合 ⊆ reminded 集合）→ 放行、前移快照、ack 死引用
#   - 集合包含比對而非 hash：Claude 修掉部分死引用後集合縮小，仍應放行
# 邊界（spec §邊界 case）：worktree session 跳過、首次安裝只初始化不回溯、
#   CLAUDE_REFLECT_CHILD 子行程早退、任何例外 fail-open exit 0。
# spec：resources/specs/codemap_guard_stop_hook_2026-06-07_spec.md

$ErrorActionPreference = 'Continue'

# PS 5.1 預設 OutputEncoding = cp936：不修繁中 reason 變亂碼（gotcha #2，input/output 都要設）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 反思 worker 子行程守衛（與其他三支 Stop hook 一致）
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }

$mainCheckout = 'C:\Users\LIN HONG\Desktop\Project_01'

try {
    # worktree session 跳過：state 不進 worktree、gitignored 檔在 worktree 看不到會誤報死引用；
    # merge 回 main 後主 checkout 的下一輪 Stop 自然抓到全部新檔
    $gitDir    = git rev-parse --git-dir 2>$null
    $commonDir = git rev-parse --git-common-dir 2>$null
    if ($gitDir -and $commonDir -and ($gitDir -ne $commonDir)) { exit 0 }

    $stateDir     = Join-Path $mainCheckout '.claude\hooks\state\codemap'
    if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
    $snapFile     = Join-Path $stateDir 'last-snapshot.txt'
    $remindedFile = Join-Path $stateDir 'reminded.txt'
    $ackFile      = Join-Path $stateDir 'acked-deadrefs.txt'
    $logFile      = Join-Path $mainCheckout '.claude\hooks\stop-check-codemap.log'
    $utf8NoBom    = New-Object System.Text.UTF8Encoding $false   # state 檔比對用，BOM 會混進比對值（gotcha #6）

    function Write-Log([string]$msg) {
        if ((Test-Path $logFile) -and ((Get-Item $logFile).Length -gt 1MB)) {
            Move-Item $logFile "$logFile.1" -Force
        }
        ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) | Out-File $logFile -Append -Encoding utf8
    }

    # ── 1. 當前結構快照（-c core.quotePath=false 保中文檔名；gitignored 天然不在內）──
    $tracked   = @(git -C $mainCheckout -c core.quotePath=false ls-files 2>$null)
    if ($LASTEXITCODE -ne 0) { exit 0 }   # git 異常 → fail-open
    $untracked = @(git -C $mainCheckout -c core.quotePath=false ls-files --others --exclude-standard 2>$null)
    if ($LASTEXITCODE -ne 0) { exit 0 }

    # 排除清單（spec §3：append-only / 目錄級描述已涵蓋；regex 比對 git 的 / 分隔路徑）
    $excludeRe = @(
        '^resources/changelogs/',
        '^resources/pineedtodo/',
        '^resources/specs/',
        '^resources/plans/',
        '^resources/reviews/',
        '^resources/evals/iteration-[^/]*/',
        '^resources/evals/baseline/',
        '(^|/)\.claude/code_map\.md$'        # 索引本身：補建子層索引不觸發
    ) -join '|'
    $snapshot = @($tracked + $untracked | Where-Object { $_ -and ($_ -notmatch $excludeRe) } | Sort-Object -Unique)

    # ── 2. 首次安裝：初始化基線，不回溯歷史 ──
    if (-not (Test-Path $snapFile)) {
        [System.IO.File]::WriteAllLines($snapFile, [string[]]$snapshot, $utf8NoBom)
        Write-Log ("init snapshot ({0} files)" -f $snapshot.Count)
        exit 0
    }

    # ── 3. 快照 diff ──
    $old = @([System.IO.File]::ReadAllLines($snapFile, [System.Text.Encoding]::UTF8) | Where-Object { $_ })
    $added   = @($snapshot | Where-Object { $old -notcontains $_ }      | ForEach-Object { "新增：$_" })
    $removed = @($old      | Where-Object { $snapshot -notcontains $_ } | ForEach-Object { "刪除：$_" })

    # ── 4. 死引用健檢（in-process 呼叫；script 內的 exit 只結束該 script、$LASTEXITCODE 可取）──
    $deadRefs = @()
    $healthScript = Join-Path $mainCheckout '.claude\skills\project-01-workflow\scripts\codemap-health.ps1'
    if (Test-Path $healthScript) {
        try {
            $healthOut = & $healthScript -RepoRoot $mainCheckout
            $deadRefs = @($healthOut | Where-Object { $_ -match '死引用' } | ForEach-Object { $_.Trim() })
        } catch { Write-Log ("health check failed: {0}" -f $_) }   # 健檢失敗 → 跳過 D，C 照常
    }
    $acked = @()
    if (Test-Path $ackFile) { $acked = @([System.IO.File]::ReadAllLines($ackFile, [System.Text.Encoding]::UTF8) | Where-Object { $_ }) }
    $newDead = @($deadRefs | Where-Object { $acked -notcontains $_ })

    # ── 5. 過關判定 ──
    $outstanding = @($added + $removed + $newDead)

    if ($outstanding.Count -eq 0) {
        # 乾淨（或變動全在排除清單）→ 靜默前移
        [System.IO.File]::WriteAllLines($snapFile, [string[]]$snapshot, $utf8NoBom)
        [System.IO.File]::WriteAllLines($ackFile, [string[]]$deadRefs, $utf8NoBom)   # acked←current：修好的死引用自動移出
        if (Test-Path $remindedFile) { Remove-Item $remindedFile -Force }
        exit 0
    }

    $remembered = @()
    if (Test-Path $remindedFile) { $remembered = @([System.IO.File]::ReadAllLines($remindedFile, [System.Text.Encoding]::UTF8) | Where-Object { $_ }) }
    $allKnown = ($remembered.Count -gt 0)
    foreach ($item in $outstanding) {
        if ($remembered -notcontains $item) { $allKnown = $false; break }
    }

    if ($allKnown) {
        # 已提醒過且無新項目（當前 ⊆ reminded）→ 放行 + 前移
        [System.IO.File]::WriteAllLines($snapFile, [string[]]$snapshot, $utf8NoBom)
        [System.IO.File]::WriteAllLines($ackFile, [string[]]$deadRefs, $utf8NoBom)
        Remove-Item $remindedFile -Force
        Write-Log ("pass after remind ({0} items)" -f $outstanding.Count)
        exit 0
    }

    # ── 6. block 一次 ──
    [System.IO.File]::WriteAllLines($remindedFile, [string[]]$outstanding, $utf8NoBom)
    $display = @($outstanding | Select-Object -First 50)
    $more = if ($outstanding.Count -gt 50) { "`n…等共 {0} 項" -f $outstanding.Count } else { '' }
    $reason = ("偵測到結構變動 / code_map 死引用尚未處理：`n{0}{1}`n→ 請逐項處理：更新「變動所在那層」的 .claude/code_map.md（巢狀判準見 skill reference/pi-and-structure.md §結構變動維護），或判定該項已被現有目錄級描述涵蓋。處理完直接再次收工即放行（同一變動集只擋一次）。" -f ($display -join "`n"), $more)
    Write-Log ("block ({0} items)" -f $outstanding.Count)
    @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Depth 5 -Compress
    exit 0

} catch {
    exit 0   # fail-open：hook 自身任何例外絕不卡死收工
}
```

- [ ] **Step 1.2: 補 BOM（Write 工具產出無 BOM，PS 5.1 含中文必 parse error——gotcha #1）**

```powershell
$p = '<worktree絕對路徑>\.claude\hooks\stop-check-codemap.ps1'
[System.IO.File]::WriteAllText($p, (Get-Content $p -Raw -Encoding UTF8), (New-Object System.Text.UTF8Encoding $true))
```

- [ ] **Step 1.3: 驗 BOM + 語法**

```powershell
# BOM：頭 3 byte 必為 ef bb bf
$b = [System.IO.File]::ReadAllBytes('<worktree>\.claude\hooks\stop-check-codemap.ps1')[0..2]
($b | ForEach-Object { $_.ToString('x2') }) -join ' '
```
預期輸出：`ef bb bf`

```powershell
# 語法 parse（不執行）：
$errs = $null
[System.Management.Automation.Language.Parser]::ParseFile('<worktree>\.claude\hooks\stop-check-codemap.ps1', [ref]$null, [ref]$errs) | Out-Null
$errs.Count
```
預期輸出：`0`

---

### Task 2: codemap-health.ps1 的 PS 5.1 相容性確認（spec 驗證項 2）

**Files:** 無（只跑不改）

- [ ] **Step 2.1: 用 5.1（hook 運行時）實跑一次**

```powershell
powershell -NoProfile -File "C:\Users\LIN HONG\Desktop\Project_01\.claude\skills\project-01-workflow\scripts\codemap-health.ps1" -RepoRoot "C:\Users\LIN HONG\Desktop\Project_01"
```
預期：正常輸出健檢報告（`✅ 全綠` 或既有 warn），**無 parse/runtime error**。若有 5.1 不相容錯誤 → 停下回報使用者（修 codemap-health 超出本 plan 範圍，spec §不做）。

---

### Task 3: 本地模擬測試（spec 驗證項 1；全部 cwd=主 checkout）

**Files:** 無（行為驗證；hook 跑的是 worktree 內的新腳本，操作的是主 checkout 的 git/state）

> 共用前綴（每條指令都要）：`powershell -NoProfile -Command "cd 'C:\Users\LIN HONG\Desktop\Project_01'; & '<worktree>\.claude\hooks\stop-check-codemap.ps1'"`，以下簡記 `RUN-HOOK`。
> 本 hook 不讀 stdin，不需餵 JSON。

- [ ] **Step 3.1: 首次安裝（snapshot 不存在）→ 初始化 + 靜默**

確認 `.claude\hooks\state\codemap\` 不存在（全新）→ `RUN-HOOK`
預期：無 stdout；`last-snapshot.txt` 生成（行數≈repo 檔數）；log 出現 `init snapshot`。

- [ ] **Step 3.2: 無變動 → 靜默前移**

再跑一次 `RUN-HOOK`。預期：無 stdout，exit 0。

- [ ] **Step 3.3: 新增檔 → block 一次，列出路徑**

```powershell
New-Item -ItemType File 'C:\Users\LIN HONG\Desktop\Project_01\resources\tmp_codemap_test.md' | Out-Null
```
`RUN-HOOK` 預期 stdout：`{"decision":"block","reason":"偵測到結構變動…新增：resources/tmp_codemap_test.md…"}`；`reminded.txt` 生成含該行。

- [ ] **Step 3.4: 同變動集第二次 → 放行 + 前移**

`RUN-HOOK` 預期：無 stdout；`reminded.txt` 消失；`last-snapshot.txt` 已含 `resources/tmp_codemap_test.md`；log 出現 `pass after remind`。

- [ ] **Step 3.5: 刪除檔 → block 一次（刪除事件）→ 再跑放行**

```powershell
Remove-Item 'C:\Users\LIN HONG\Desktop\Project_01\resources\tmp_codemap_test.md'
```
`RUN-HOOK` 預期 block，reason 含 `刪除：resources/tmp_codemap_test.md`。再 `RUN-HOOK` 預期放行（state 回乾淨）。

- [ ] **Step 3.6: 排除清單內新增 → 靜默**

```powershell
New-Item -ItemType File 'C:\Users\LIN HONG\Desktop\Project_01\resources\changelogs\tmp_excl_test.md' | Out-Null
```
`RUN-HOOK` 預期：無 stdout（被 `^resources/changelogs/` 排除）。清理：`Remove-Item` 該檔，再 `RUN-HOOK` 一次確認仍靜默。

- [ ] **Step 3.7: 死引用 → block；恢復後放行**

```powershell
Rename-Item 'C:\Users\LIN HONG\Desktop\Project_01\resources\watchlist.md' 'watchlist_tmp9.md'
```
`RUN-HOOK` 預期 block，reason 同時含：`新增：resources/watchlist_tmp9.md`、`刪除：resources/watchlist.md`、`死引用：…watchlist.md`（resources 層 code_map 有索引它）。
復原 + 收斂：
```powershell
Rename-Item 'C:\Users\LIN HONG\Desktop\Project_01\resources\watchlist_tmp9.md' 'watchlist.md'
```
`RUN-HOOK` 預期：無 stdout（outstanding 歸零走乾淨分支，reminded 自動清除）。

- [ ] **Step 3.8: worktree cwd → 跳過**

```powershell
powershell -NoProfile -Command "cd '<worktree>'; & '<worktree>\.claude\hooks\stop-check-codemap.ps1'"
```
預期：無 stdout、立即返回（git-dir ≠ git-common-dir 早退）；state 檔 mtime 不變。

- [ ] **Step 3.9: 測試殘留檢查**

```powershell
Get-Content 'C:\Users\LIN HONG\Desktop\Project_01\.claude\hooks\state\codemap\last-snapshot.txt' | Select-String 'tmp_'
```
預期：無輸出（無測試殘留）。`reminded.txt` 不存在。

---

### Task 4: 註冊 settings.json + 文檔同步

**Files:**
- Modify: `<worktree>/.claude/settings.json`（Stop 陣列）
- Modify: `<worktree>/.claude/skills/project-01-workflow/reference/hooks-system.md`（一覽表 + flag 架構段）
- Modify: `<worktree>/resources/watchlist.md`（W-3 → closed）

- [ ] **Step 4.1: settings.json — Stop 陣列插入第 3 個 entry（stop-sync-pi 之後、stop-reflect 之前）**

在 `stop-sync-pi.ps1` 的 entry（`},`）之後插入：

```json
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": ["-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop-check-codemap.ps1"]
          }
        ]
      },
```

改完用 `ConvertFrom-Json` 驗格式：
```powershell
Get-Content '<worktree>\.claude\settings.json' -Raw | ConvertFrom-Json | Out-Null; 'JSON OK'
```
預期輸出：`JSON OK`

- [ ] **Step 4.2: hooks-system.md — 一覽表加一列（stop-reflect 列之後）**

```markdown
| `stop-check-codemap.ps1` | Stop | — | 結構變動（git 快照 diff）/ 死引用（codemap-health 重用）未反映到 code_map → block 一次（spec：codemap_guard_stop_hook_2026-06-07_spec.md） |
```

並在「Flag file 協作架構」清單補一條：

```markdown
- **codemap 守門（state/codemap/）**：`last-snapshot.txt` 檔案清單基線（過關才前移）＋ `reminded.txt` 已提醒集合（當前 ⊆ 它即放行，包含比對非 hash）＋ `acked-deadrefs.txt` 已提醒死引用（同批只擋一次）。皆 no-BOM UTF-8。
```

- [ ] **Step 4.3: watchlist.md — W-3 改 closed**

W-3 該列 status 欄 `open` 改為：

```markdown
**closed**（2026-06-07 stop-check-codemap hook 確定性接管：快照 diff 抓漏登錄 + 自動死引用健檢；spec: codemap_guard_stop_hook_2026-06-07_spec.md）
```

- [ ] **Step 4.4: code_map 確認（不改）**

對照：root `.claude/code_map.md` 對 `.claude/hooks/` 是目錄級描述（不逐檔列）→ 新 hook 檔已涵蓋，**無需改任何 code_map**。spec「連帶文檔更新」第 2 條以此結論為準。

- [ ] **Step 4.5: Commit（worktree 內，明列檔名）**

```bash
git add .claude/hooks/stop-check-codemap.ps1 .claude/settings.json .claude/skills/project-01-workflow/reference/hooks-system.md resources/watchlist.md
git commit -m "feat(hooks): add stop-check-codemap guard (snapshot diff + dead-ref health)

- 4th Stop hook：git 快照比對抓新增/刪除/改名 + 重用 codemap-health 死引用掃描
- 同變動集只 block 一次（reminded 集合包含比對）；worktree/首裝/反思子行程早退；fail-open
- watchlist W-3 closed；hooks-system.md 一覽表與 state 家族同步

Co-Authored-By: Claude Opus <noreply@anthropic.com>"
```

---

### Task 4b: 修正 sdd.md 的 plan 位置錯誤指引（使用者 2026-06-07 核可，搭本次 worktree 順路修）

**Files:**
- Modify: `<worktree>/.claude/skills/project-01-workflow/reference/sdd.md`（三處）

> 背景：sdd.md 三處明寫「plan 放 `resources/specs/`」，與 `resources/.claude/code_map.md`（`plans/ — SDD 計畫`）矛盾，導致 plan 檔屢次放錯位。正確慣例：**spec → `resources/specs/`、plan → `resources/plans/`**。

- [ ] **Step 4b.1: §Spec 位置與命名 — 改統一位置段**

old：
```markdown
**統一位置**：`resources/specs/`（flat，不分 L 層 / 模組）。
- 完整版：`<short_name>_<YYYY-MM-DD>_spec.md` + `_plan.md`（同 prefix）。Mini：`<short_name>_<YYYY-MM-DD>_spec.md` 單檔。
```
new：
```markdown
**位置**：spec → `resources/specs/`、plan → `resources/plans/`（皆 flat，不分 L 層 / 模組；同 prefix 異目錄）。
- 完整版：`specs/<short_name>_<YYYY-MM-DD>_spec.md` + `plans/<short_name>_<YYYY-MM-DD>_plan.md`。Mini：`specs/<short_name>_<YYYY-MM-DD>_spec.md` 單檔。
```

- [ ] **Step 4b.2: §SDD 4 階段流程 階段 1 步驟 4**

old：
```
  4. 寫 spec.md（+ plan.md 若完整版）到 resources/specs/（未 commit）
```
new：
```
  4. 寫 spec.md 到 resources/specs/（+ plan.md 到 resources/plans/ 若完整版）（未 commit）
```

- [ ] **Step 4b.3: §Sales-coder 派發 prompt 範本 — Plan 路徑**

old：
```markdown
- Plan：`resources/specs/<name>_<date>_plan.md`（HOW，step-by-step）
```
new：
```markdown
- Plan：`resources/plans/<name>_<date>_plan.md`（HOW，step-by-step）
```

- [ ] **Step 4b.4: 驗證無殘留錯誤指引**

```powershell
Select-String -Pattern 'specs/<name>_<date>_plan|plan\.md.*到 resources/specs' -Path '<worktree>\.claude\skills\project-01-workflow\reference\sdd.md'
```
預期：無輸出。

- [ ] **Step 4b.5: Commit（獨立 commit）**

```bash
git add .claude/skills/project-01-workflow/reference/sdd.md
git commit -m "docs(skill): fix sdd.md plan location (resources/plans/, not specs/)

三處錯誤指引與 resources code_map 矛盾，致 plan 檔屢次放錯目錄

Co-Authored-By: Claude Opus <noreply@anthropic.com>"
```

---

### Task 5: spec + plan 文件 commit（主 checkout，resources/ 純文件可直接 main）

**Files:**
- Add: `resources/specs/codemap_guard_stop_hook_2026-06-07_spec.md`（已存在於主 checkout）
- Add: `resources/plans/codemap_guard_stop_hook_2026-06-07_plan.md`（本檔；spec 放 `specs/`、plan 放 `plans/`）

- [ ] **Step 5.1: 在主 checkout commit 兩份文件**

注意：此步在 ExitWorktree 之後做（worktree mode 下主 agent 無法寫主 checkout，但 git add/commit 走 Bash 不受限——為簡化，**排在 Task 6 ExitWorktree 後執行**）。

```bash
git add resources/specs/codemap_guard_stop_hook_2026-06-07_spec.md resources/plans/codemap_guard_stop_hook_2026-06-07_plan.md
git commit -m "docs(specs): codemap guard stop hook spec + plan

Co-Authored-By: Claude Opus <noreply@anthropic.com>"
```

---

### Task 6: 收尾（worktree 階段 4-5）+ 端到端驗證

**Files:** 無（流程）

- [ ] **Step 6.1: ExitWorktree + ff-merge + 文件 commit + push**

```powershell
ExitWorktree(action="keep")
git merge worktree-codemap-guard --ff-only
# ← 此處執行 Task 5 Step 5.1（spec/plan commit）
git push origin main
```
預期：merge fast-forward 成功；push 後 stop-sync-pi 會在 turn 結束 sync Pi（本變更不含 myProgram/，Pi 端無感，照常無妨）。
若 ff-merge 失敗 → **不要 force**，依 worktree.md 例外 A 處理。

- [ ] **Step 6.2: 清理 worktree**

```powershell
git worktree remove .claude/worktrees/codemap-guard
git branch -d worktree-codemap-guard
```
（file lock 時用 worktree.md 的 fallback：`Remove-Item -Recurse -Force` + `git worktree prune`。）

- [ ] **Step 6.3: `/hooks` menu 確認註冊（請使用者目視）**

請使用者開 `/hooks` 確認 Stop 事件下出現 `stop-check-codemap.ps1`；保險起見重啟 session（file watcher 通常自動 reload）。

- [ ] **Step 6.4: 端到端首輪行為（預期內，向使用者預告）**

merge 後第一個真實 Stop：快照 diff 會抓到唯一新檔 `新增：.claude/hooks/stop-check-codemap.ps1`（settings/hooks-system/watchlist 是 modify 不觸發；spec/plan 在排除清單）→ **被自己 block 一次** → 回覆「已由 root code_map 的 hooks/ 目錄級描述涵蓋」再收工 → 放行。這就是 spec 驗證項 5 的 live e2e，不需另造假檔。

- [ ] **Step 6.5: 回報**

依 CLAUDE.md 格式回報：(1) 改了什麼 (2) pineedtodo＝無 (3) Pi sync 由 Stop hook 自動處理 (4) 使用者後續：`/hooks` 目視 + 觀察首輪 block 行為。

---

## Self-review（已跑）

- **Spec coverage**：偵測（Task 1 §1-4）／block 一次+集合包含（§5-6，修正 spec 的 hash 描述——hash 等值會在「修掉部分死引用」時誤再擋，plan 改用集合包含比對，語意同「無新項目即放行」）／排除清單（§1）／死引用 ack（§4-5）／worktree 跳過（§開頭+Step 3.8）／首裝基線（Step 3.1）／fail-open（catch）／PS 5.1 相容（Task 2）／文檔+W-3（Task 4）／驗證計畫 5 項全對應（Task 2、3、6.3、6.4、Step 1.3 BOM）。
- **Placeholder scan**：無 TBD/TODO；所有 code 步驟含完整內容與預期輸出。
- **一致性**：state 檔名三處（code/註解/hooks-system 補述）一致；`RUN-HOOK` 前綴在 Task 3 開頭定義。
