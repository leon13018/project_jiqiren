# 反思型 Stop Hook（手搓版）— 實施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（hook 工程 = 主 agent 編排 + 手測驗證，不適合整包外包）。Steps 用 checkbox（`- [ ]`）追蹤。

**Goal:** 依 spec 手搓官方 security-guidance 第 2 層同形的反思型 Stop hook：背景 fresh-Claude 評審、只提議不寫入、雙觸發、防迴圈三件套。

**Architecture:** `stop-reflect.ps1`（輕，Stop 事件：守衛/觸發/收料/拋背景/未讀提示）+ `reflect-worker.ps1`（重，背景：`claude -p` 呼叫/解析/去重/落地）+ state 目錄；兩支既有 Stop hook 加遞迴守衛。

**Tech Stack:** Windows PowerShell 5.1（`powershell -NoProfile`，沿用既有 hook 慣例：UTF-8 編碼修正、寫死 `$mainCheckout`、try/catch+log、gitignored state/log）；claude CLI headless（`claude -p`）。

**慣例註記:** spec §7「錨定主 checkout」依既有 hook 慣例用寫死常數實現（非 git 推導）；Task 6 回寫 spec 一行。未讀提示用 `systemMessage`（stop-sync 已驗證的輸出路徑）+ `hookSpecificOutput.additionalContext`（調研 R4 稱 Stop 支援、NOTES 舊註記稱不支援——Task 5 實測定論並記回 NOTES）。

---

### Task 0: 前置檢查 + 進 worktree

**Files:** 無改動。

- [ ] **Step 1: 確認 claude CLI 可用（worker 的硬依賴）**

Run: `powershell -NoProfile -Command "(Get-Command claude).Source; claude --version"`
Expected: 印出路徑與版本。失敗 → 停，向使用者確認 CLI 安裝狀態。

- [ ] **Step 2: 確認起點乾淨 + 進 worktree**

Run: `git status --porcelain`（expect 空）→ `EnterWorktree(name="reflective-stop-hook")`（`.claude/` 改動屬強制範圍）。

---

### Task 1: `stop-reflect.ps1`（hook 本體）

**Files:**
- Create: `.claude/hooks/stop-reflect.ps1`

- [ ] **Step 1: 寫入完整檔案**

```powershell
# Stop hook：每 turn 結束反思「本輪有無值得固化的學習點」→ 拋背景 worker 用 fresh-context
# claude -p 評審 → 提議 append 到 resources/reflections/proposals.md（gitignored）等人定奪。
# 藍本：官方 security-guidance plugin 第 2 層（Stop + fresh reviewer + 背景跑 + 不 block）。
# spec：resources/specs/reflective_stop_hook_2026-06-04_spec.md
#
# 設計：exit 0 always、永不 decision:block（同 stop-sync-pi，不受 8-block cap 影響）。
# 觸發：T1 = 本 turn 有 git 變動（status 非空 或 HEAD ≠ last-reflected marker）→ 素材 = diff
#       T2 = 距上次反思已 $TURN_INTERVAL 輪 → 素材 = transcript 尾段
# 防迴圈：CLAUDE_REFLECT_CHILD 旗標（claude -p 子行程早退）｜session 呼叫上限｜worker 端 slug 去重。
#
# 輸入：stdin JSON（session_id / transcript_path）。
# 輸出：有未讀提議時 systemMessage + additionalContext 一行提示；其餘無輸出。
# log：worker 寫 .claude/hooks/reflect.log（本檔自身故障靜默，不影響 session）。

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── 遞迴守衛：claude -p 子行程內不再反思 ──
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }

# ── 常數（調整處集中此區）──
$TURN_INTERVAL  = 8      # T2：每 8 輪無變動也統整一次
$SESSION_CAP    = 10     # 每 session 模型呼叫上限
$DIFF_CAP_LINES = 400    # T1 素材 diff 行數上限
$LOCK_ZOMBIE_MIN = 10    # lock 超過 10 分鐘視為殭屍

$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$stateDir   = Join-Path $mainCheckout '.claude/hooks/state/reflect'
$proposals  = Join-Path $mainCheckout 'resources/reflections/proposals.md'
$workerPath = Join-Path $mainCheckout '.claude/hooks/reflect-worker.ps1'

try {
    $stdinRaw = [Console]::In.ReadToEnd()
    $evt = $null
    try { $evt = $stdinRaw | ConvertFrom-Json } catch {}
    $sessionId = 'unknown'
    if ($evt -and $evt.session_id) { $sessionId = [string]$evt.session_id }
    $transcriptPath = ''
    if ($evt -and $evt.transcript_path) { $transcriptPath = [string]$evt.transcript_path }

    if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force $stateDir | Out-Null }

    # ── 未讀提議提示（每次 Stop 重算，天然防 resume stale）──
    $hint = $null
    if (Test-Path $proposals) {
        $pending = @(Select-String -Path $proposals -Pattern 'status: pending' -SimpleMatch -ErrorAction SilentlyContinue).Count
        $notifiedFile = Join-Path $stateDir 'last-notified.txt'
        $lastNotified = 0
        if (Test-Path $notifiedFile) { $lastNotified = [int](Get-Content $notifiedFile -ErrorAction SilentlyContinue | Select-Object -First 1) }
        if ($pending -gt $lastNotified) {
            $delta = $pending - $lastNotified
            $hint = ('🪞 反思提議 +{0} 條待審（共 {1} 條 pending，見 resources/reflections/proposals.md）' -f $delta, $pending)
            [System.IO.File]::WriteAllText($notifiedFile, [string]$pending, [System.Text.UTF8Encoding]::new($false))
        }
    }

    # ── lock / 上限檢查（不過 → 只發提示就走）──
    $lockFile = Join-Path $stateDir 'lock'
    $skipReflect = $false
    if (Test-Path $lockFile) {
        $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
        if ($age.TotalMinutes -gt $LOCK_ZOMBIE_MIN) { Remove-Item $lockFile -Force -ErrorAction SilentlyContinue }
        else { $skipReflect = $true }
    }
    $callsFile = Join-Path $stateDir ('session-calls_' + ($sessionId -replace '[^\w-]','') + '.txt')
    $calls = 0
    if (Test-Path $callsFile) { $calls = [int](Get-Content $callsFile -ErrorAction SilentlyContinue | Select-Object -First 1) }
    if ($calls -ge $SESSION_CAP) { $skipReflect = $true }

    # ── 觸發判斷 ──
    $trigger = ''
    $materialFile = Join-Path $stateDir ('material_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.txt')
    $counterFile = Join-Path $stateDir 'turn-count.txt'
    $turnCount = 0
    if (Test-Path $counterFile) { $turnCount = [int](Get-Content $counterFile -ErrorAction SilentlyContinue | Select-Object -First 1) }

    if (-not $skipReflect) {
        # T1：本 turn 有 git 變動？
        $statusOut = (& git -C $mainCheckout status --porcelain 2>$null)
        $head = (& git -C $mainCheckout rev-parse HEAD 2>$null)
        $markerFile = Join-Path $stateDir 'last-reflected-commit.txt'
        $marker = ''
        if (Test-Path $markerFile) { $marker = (Get-Content $markerFile -ErrorAction SilentlyContinue | Select-Object -First 1) }

        if ($statusOut -or ($head -and $marker -and $head -ne $marker) -or ($head -and -not $marker)) {
            $trigger = 'T1'
            $parts = @()
            $parts += '## 檔案狀態'
            $parts += ($statusOut | Out-String)
            if ($marker -and $head -ne $marker) {
                $parts += ('## 本輪已提交範圍 {0}..{1}' -f $marker.Substring(0,7), $head.Substring(0,7))
                $parts += ((& git -C $mainCheckout diff "$marker..$head" 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)
            }
            if ($statusOut) {
                $parts += '## 未提交 diff'
                $parts += ((& git -C $mainCheckout diff 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)
            }
            [System.IO.File]::WriteAllText($materialFile, ($parts -join "`n"), [System.Text.UTF8Encoding]::new($false))
            if ($head) { [System.IO.File]::WriteAllText($markerFile, $head, [System.Text.UTF8Encoding]::new($false)) }
        }
        elseif (($turnCount + 1) -ge $TURN_INTERVAL -and $transcriptPath -and (Test-Path $transcriptPath)) {
            $trigger = 'T2'
            $msgs = @()
            foreach ($ln in (Get-Content $transcriptPath -Tail 400 -ErrorAction SilentlyContinue)) {
                try { $o = $ln | ConvertFrom-Json } catch { continue }
                if ($o.type -ne 'user' -and $o.type -ne 'assistant') { continue }
                $text = ''
                $content = $o.message.content
                if ($content -is [string]) { $text = $content }
                else { foreach ($c in $content) { if ($c.type -eq 'text') { $text += $c.text + ' ' } } }
                $text = $text.Trim()
                if ($text) { $msgs += ('[{0}] {1}' -f $o.type, $text) }
            }
            $msgs = $msgs | Select-Object -Last 30
            $material = ($msgs -join "`n---`n")
            if ($material.Length -gt 8192) { $material = $material.Substring($material.Length - 8192) }
            if ($material) {
                [System.IO.File]::WriteAllText($materialFile, $material, [System.Text.UTF8Encoding]::new($false))
            } else { $trigger = '' }
        }
    }

    if ($trigger) {
        # 計數在拋出時就更新（worker 失敗也算一次，保守防超支）
        [System.IO.File]::WriteAllText($callsFile, [string]($calls + 1), [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($counterFile, '0', [System.Text.UTF8Encoding]::new($false))
        New-Item -ItemType File -Force $lockFile | Out-Null
        Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList @(
            '-NoProfile','-File', $workerPath,
            '-MaterialFile', $materialFile, '-TriggerType', $trigger, '-MainCheckout', $mainCheckout
        ) | Out-Null
    } else {
        [System.IO.File]::WriteAllText($counterFile, [string]($turnCount + 1), [System.Text.UTF8Encoding]::new($false))
    }

    if ($hint) {
        $out = @{ systemMessage = $hint
                  hookSpecificOutput = @{ hookEventName = 'Stop'; additionalContext = $hint } } | ConvertTo-Json -Compress
        Write-Output $out
    }
} catch {}
exit 0
```

- [ ] **Step 2: 守衛測（spec 驗證 1）**

Run: `powershell -NoProfile -Command "$env:CLAUDE_REFLECT_CHILD='1'; echo '{}' | powershell -NoProfile -File .claude\hooks\stop-reflect.ps1; echo EXIT:$LASTEXITCODE"`
Expected: 無輸出、`EXIT:0`（注意：守衛看的是子行程環境，故外層先 set 再呼叫）。

- [ ] **Step 3: 空輸入煙霧測**

Run: `echo '{"session_id":"smoke","transcript_path":""}' | powershell -NoProfile -File .claude\hooks\stop-reflect.ps1; echo EXIT:$LASTEXITCODE`
Expected: `EXIT:0`；`.claude/hooks/state/reflect/` 出現（worktree 內跑時素材/拋出以 worktree 的 git 狀態為準——worktree 有未 commit 變動時會嘗試拋 worker，屬預期；可先 `git stash` 或直接觀察 lock/material 檔生成證明 T1 路徑通）。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/stop-reflect.ps1
git commit -m "feat(hooks): add stop-reflect hook body (triggers, guards, hint, dispatch)"
```

---

### Task 2: `reflect-worker.ps1`（背景評審）

**Files:**
- Create: `.claude/hooks/reflect-worker.ps1`

- [ ] **Step 1: 寫入完整檔案**

```powershell
# 反思背景 worker：被 stop-reflect.ps1 以 Start-Process 拋出（detached，不阻塞 turn）。
# 職責：組 prompt → claude -p（fresh context、便宜 model、禁工具指示）→ 解析 → slug 去重 →
#       append resources/reflections/proposals.md → 釋放 lock → log。
# 任何故障：log 後靜默結束（session 零感知）。spec §4/§6。

param(
    [Parameter(Mandatory=$true)][string]$MaterialFile,
    [Parameter(Mandatory=$true)][string]$TriggerType,
    [Parameter(Mandatory=$true)][string]$MainCheckout
)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$REFLECT_MODEL = 'claude-haiku-4-5-20251001'
$PROPOSAL_MAX  = 3
$CALL_TIMEOUT_S = 120

$stateDir  = Join-Path $MainCheckout '.claude/hooks/state/reflect'
$lockFile  = Join-Path $stateDir 'lock'
$logFile   = Join-Path $MainCheckout '.claude/hooks/reflect.log'
$proposals = Join-Path $MainCheckout 'resources/reflections/proposals.md'

function Write-Log([string]$msg) {
    $line = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
    Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

try {
    if (-not (Test-Path $MaterialFile)) { Write-Log "material 不存在：$MaterialFile"; exit 0 }
    $material = [System.IO.File]::ReadAllText($MaterialFile, [System.Text.Encoding]::UTF8)

    $promptHeader = @'
你是 fresh-context 審計員，審另一個 coding agent 本輪工作的「學習點」，與其產出無利害關係。
不要使用任何工具，直接輸出文字結論。

只報符合以下任一門檻的學習點（其餘一律不報）：
- 影響程式正確性的坑
- 違反專案紅線（禁改 vendor SDK / 禁 Windows 裝依賴 / 禁 git add -A / 產出須繁體中文）
- 同類錯誤在素材中出現 ≥2 次
- 使用者明確糾正過的行為

風格喜好、一次性小失誤、有能力的 model 本來就會做對的事：不報。
沒有值得報的 → 只輸出 NONE。

有則最多 3 條，每條嚴格用此格式（條間以 --- 分隔）：
SLUG: <kebab-case-主題>
LAYER: NOTES|CLAUDE.md|skill|memory
BODY: <≤3 行繁體中文，說清楚踩了什麼、建議固化什麼>

以下是素材（
'@
    $prompt = $promptHeader + $TriggerType + @'
）：

'@ + $material

    # 子行程守衛旗標 + cwd 移出專案（雙保險：專案 hooks 不載入、我們的 Stop hook 也有旗標早退）
    $env:CLAUDE_REFLECT_CHILD = '1'
    Push-Location $env:TEMP

    $claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claudeCmd) { Write-Log 'claude CLI 不存在，跳過'; exit 0 }

    $job = Start-Job -ScriptBlock {
        param($p, $m)
        $env:CLAUDE_REFLECT_CHILD = '1'
        & claude -p $p --model $m 2>&1 | Out-String
    } -ArgumentList $prompt, $REFLECT_MODEL
    if (-not (Wait-Job $job -Timeout $CALL_TIMEOUT_S)) {
        Stop-Job $job -ErrorAction SilentlyContinue
        Write-Log ('claude -p 逾時（>{0}s），放棄本次' -f $CALL_TIMEOUT_S)
        exit 0
    }
    $output = (Receive-Job $job | Out-String).Trim()
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Pop-Location

    if (-not $output) { Write-Log 'claude -p 無輸出'; exit 0 }
    if ($output -match '(?m)^\s*NONE\s*$' -and $output.Length -lt 40) { Write-Log ("{0} 反思：NONE" -f $TriggerType); exit 0 }

    # 解析 + 去重 + 落地
    if (-not (Test-Path (Split-Path $proposals))) { New-Item -ItemType Directory -Force (Split-Path $proposals) | Out-Null }
    if (-not (Test-Path $proposals)) {
        [System.IO.File]::WriteAllText($proposals, "# 反思提議（append-only；採納/否決後把該條 status 改掉或刪除）`n", [System.Text.UTF8Encoding]::new($false))
    }
    $existing = [System.IO.File]::ReadAllText($proposals, [System.Text.Encoding]::UTF8)

    $added = 0
    foreach ($block in ($output -split '(?m)^---\s*$')) {
        if ($added -ge $PROPOSAL_MAX) { break }
        if ($block -notmatch 'SLUG:\s*(?<slug>[a-z0-9-]+)') { continue }
        $slug = $Matches['slug']
        $layer = '未指定'
        if ($block -match 'LAYER:\s*(?<layer>\S+)') { $layer = $Matches['layer'] }
        $body = ''
        if ($block -match '(?s)BODY:\s*(?<body>.+)$') { $body = $Matches['body'].Trim() }
        if (-not $body) { continue }
        if ($existing -match [regex]::Escape($slug)) { Write-Log ("去重丟棄：{0}" -f $slug); continue }
        $entry = "`n## {0} {1}｜{2}｜建議層:{3}`n{4}`nstatus: pending`n" -f (Get-Date -Format 'yyyy-MM-dd'), $slug, $TriggerType, $layer, $body
        Add-Content -Path $proposals -Value $entry -Encoding UTF8
        $existing += $slug
        $added++
    }
    Write-Log ("{0} 反思完成：新增 {1} 條提議" -f $TriggerType, $added)
} catch {
    Write-Log ("worker 例外：{0}" -f $_.Exception.Message)
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
    Remove-Item $MaterialFile -Force -ErrorAction SilentlyContinue
}
exit 0
```

- [ ] **Step 2: 假素材實測（spec 驗證 2 的 worker 半段，真打一次 claude -p）**

Run:
```powershell
$m = ".claude\hooks\state\reflect\material_test.txt"
"## 未提交 diff`n- 在 myProgram/sales/logic.py 用了簡體字註解「数量」，使用者糾正過兩次" | Out-File $m -Encoding utf8
New-Item -ItemType File -Force .claude\hooks\state\reflect\lock | Out-Null
powershell -NoProfile -File .claude\hooks\reflect-worker.ps1 -MaterialFile $m -TriggerType T1 -MainCheckout 'C:/Users/LIN HONG/Desktop/Project_01'
Get-Content 'C:/Users/LIN HONG/Desktop/Project_01/.claude/hooks/reflect.log' -Tail 3
Get-Content 'C:/Users/LIN HONG/Desktop/Project_01/resources/reflections/proposals.md' -ErrorAction SilentlyContinue
Test-Path 'C:/Users/LIN HONG/Desktop/Project_01/.claude/hooks/state/reflect/lock'
```
Expected: log 出現「反思完成：新增 N 條」或「NONE」；若有提議則 proposals.md 含 `SLUG` 對應條目 + `status: pending`；lock = `False`（已釋放）；material 檔被清。

- [ ] **Step 3: 去重測（spec 驗證 4）**

把 Step 2 重跑一次（同素材）。
Expected: log 出現「去重丟棄：<slug>」或 NONE；proposals.md 不出現重複 slug 條目。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/reflect-worker.ps1
git commit -m "feat(hooks): add reflect-worker (claude -p reviewer, dedupe, proposals append)"
```

---

### Task 3: 兩支既有 Stop hook 加遞迴守衛

**Files:**
- Modify: `.claude/hooks/stop-sync-pi.ps1:18`（`$OutputEncoding` 行之後）
- Modify: `.claude/hooks/stop-check-sales-pytest.ps1:22`（`$OutputEncoding` 行之後）

- [ ] **Step 1: stop-sync-pi.ps1 插入守衛**

在 `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)` 之後、`try {` 之前插入：

```powershell

# 反思 hook 的 claude -p 子行程守衛（見 stop-reflect.ps1）：子 session 不 sync
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }
```

- [ ] **Step 2: stop-check-sales-pytest.ps1 插入守衛**

在其 `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)` 之後、`$mainCheckout = ...` 之前插入：

```powershell

# 反思 hook 的 claude -p 子行程守衛（見 stop-reflect.ps1）：子 session 不 block
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }
```

- [ ] **Step 3: 迴歸測（spec 驗證 7 前半）**

Run:
```powershell
powershell -NoProfile -Command "$env:CLAUDE_REFLECT_CHILD='1'; echo '{}' | powershell -NoProfile -File .claude\hooks\stop-sync-pi.ps1; echo A:$LASTEXITCODE"
powershell -NoProfile -Command "$env:CLAUDE_REFLECT_CHILD='1'; echo '{}' | powershell -NoProfile -File .claude\hooks\stop-check-sales-pytest.ps1; echo B:$LASTEXITCODE"
echo '{}' | powershell -NoProfile -File .claude\hooks\stop-sync-pi.ps1; echo C:$LASTEXITCODE
```
Expected: `A:0`、`B:0`（旗標下秒退無輸出）；`C:0` 且行為同改前（無旗標時正常走 marker 比對邏輯）。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/stop-sync-pi.ps1 .claude/hooks/stop-check-sales-pytest.ps1
git commit -m "feat(hooks): add reflect-child recursion guard to existing Stop hooks"
```

---

### Task 4: settings.json 掛載 + .gitignore + NOTES.md

**Files:**
- Modify: `.claude/settings.json:63-82`（Stop 區段加第三組）
- Modify: `.gitignore`（加 `resources/reflections/`）
- Modify: `.claude/hooks/NOTES.md`（文末新增反思 hook 段）

- [ ] **Step 1: settings.json Stop 區段加掛**

在 Stop 陣列的 stop-sync-pi 群組之後（`]` 收尾前）加第三組：

```json
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": ["-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop-reflect.ps1"]
          }
        ]
      }
```

- [ ] **Step 2: .gitignore 加一行**

```
resources/reflections/
```

- [ ] **Step 3: NOTES.md 文末新增段（內容如下，編號接續既有章節）**

```markdown
## stop-reflect（反思型 Stop hook，手搓版）

- 事件：Stop（與 stop-check / stop-sync 並行，互不依賴）。exit 0 always、永不 block。
- 觸發：T1 = 本 turn 有 git 變動（status 非空或 HEAD ≠ last-reflected marker）→ 素材 = diff（cap 400 行）；
  T2 = 連續 8 輪無反思 → 素材 = transcript 尾段（30 條 / 8KB cap）。
- 引擎：Start-Process 拋背景 reflect-worker.ps1 → `claude -p`（Haiku、fresh context、prompt 禁工具）→
  提議 append `resources/reflections/proposals.md`（gitignored）；只提議、絕不自動寫入規範檔。
- 防迴圈：`CLAUDE_REFLECT_CHILD=1` 旗標（本 hook + stop-sync + stop-check 三支開頭早退）+
  worker cwd 移出專案（專案 hooks 不載入，雙保險）｜session 呼叫上限 10｜slug 去重｜lock 防並發（10 分鐘殭屍自清）。
- 未讀提示：proposals pending 數增加時，下一次 Stop 輸出 systemMessage（+ additionalContext，實測結果：<驗證後回填：支援/被忽略>）。
- state：`.claude/hooks/state/reflect/`；log：`.claude/hooks/reflect.log`（皆 gitignored）。
- 關閉方式：settings.json 移除該 Stop 群組；或暫時 `$SESSION_CAP=0`。
- spec / plan：`resources/specs|plans/reflective_stop_hook_2026-06-04_*.md`。
```

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json .gitignore .claude/hooks/NOTES.md
git commit -m "feat(hooks): wire stop-reflect into settings, gitignore reflections, document in NOTES"
```

---

### Task 5: 整合驗證（spec §9 全項；在 worktree 內直呼 script 測）

**Files:** 無新改動（驗證結果若需修正則回前面 Task 修）。

- [ ] **Step 1: T1 端到端（spec 驗證 2）**

Run:
```powershell
Remove-Item .claude\hooks\state\reflect\session-calls_e2e.txt -ErrorAction SilentlyContinue
'tmp' | Out-File e2e_dirty.tmp
echo '{"session_id":"e2e","transcript_path":""}' | powershell -NoProfile -File .claude\hooks\stop-reflect.ps1
Start-Sleep 90
Get-Content 'C:/Users/LIN HONG/Desktop/Project_01/.claude/hooks/reflect.log' -Tail 3
Remove-Item e2e_dirty.tmp
```
Expected: lock 先出現後消失；log 有本次 T1 結果（NONE 或新增 N 條）；turn 結束無延遲（hook 秒回）。

- [ ] **Step 2: T2 觸發（spec 驗證 3）**

Run：工作樹乾淨 + marker 已同步 HEAD 時，`'7' | Out-File .claude\hooks\state\reflect\turn-count.txt`，
再 echo stdin（`transcript_path` 指向任一真實 session JSONL，可取 `~\.claude\projects\...\*.jsonl` 最新檔）跑 stop-reflect。
Expected: turn-count 歸 0、material 檔生成（內容為對話尾段）、worker 拋出、log 有 T2 結果。

- [ ] **Step 3: 上限測（spec 驗證 5）**

Run: `'10' | Out-File .claude\hooks\state\reflect\session-calls_cap.txt` → echo（session_id=cap、有 dirty 檔）跑 stop-reflect。
Expected: 不拋 worker（無新 lock / material）、exit 0；若 proposals 有 pending 仍出提示 JSON。

- [ ] **Step 4: 提示輸出實測（additionalContext 支援性定論）**

proposals.md 手動加一條 `status: pending` → 跑 stop-reflect（last-notified 較小時）。
Expected: stdout 出現 `{"systemMessage":"🪞 反思提議 +1 條...","hookSpecificOutput":{...}}`。
→ 記下 JSON 結構；merge 後在真實 turn 觀察 systemMessage 是否顯示、additionalContext 是否被接受，**回填 NOTES.md 該行**。

- [ ] **Step 5: 清理測試殘留 + Commit（若驗證過程改了檔）**

```powershell
Remove-Item .claude\hooks\state\reflect\session-calls_e2e.txt, .claude\hooks\state\reflect\session-calls_cap.txt -ErrorAction SilentlyContinue
```

---

### Task 6: 收尾（worktree 5 階段 4-5 + spec 回寫 + 實戰觀察）

- [ ] **Step 1: spec §7 回寫一行**（錨定機制：git 推導 → 依既有 hook 慣例寫死 `$mainCheckout`）並 commit 進同 worktree。

- [ ] **Step 2: worktree 收尾**

```powershell
ExitWorktree(action="keep")
git merge worktree-reflective-stop-hook --ff-only
git push origin main
git worktree remove .claude/worktrees/reflective-stop-hook
git branch -d worktree-reflective-stop-hook
```

- [ ] **Step 3: `/hooks` 生效確認**：提醒使用者開 `/hooks` 確認 stop-reflect 已列（settings 熱重載通常自動，保險可重啟 session）。

- [ ] **Step 4: 實戰觀察（spec 驗證 6/7 後半）**：接下來 1-2 個真實 turn——turn 結束零延遲、`Pi synced` 照常、（有變動 turn）reflect.log 出現新 entry、提示行出現後回填 NOTES.md 的 additionalContext 實測結果。

- [ ] **Step 5: 四件套回報**（含「提議檔在哪、怎麼審」的使用說明一句）。

---

## Self-Review 紀錄

- **Spec coverage**：§1 雙觸發+零延遲→Task1；§2 原則→worker prompt/不 block/背景；§3 組件表 7 項→Task1/2/4；§4 資料流→Task1/2 逐段；§5 三件套→Task1（旗標/上限/lock）+Task2（slug 去重）+Task3（既有 hook 守衛）；§6 prompt 要點→Task2 Step1 內嵌全文；§7 邊界（CLI 缺失/逾時/worktree 錨定/resume/transcript 壞檔）→worker try-catch+timeout+Tail 容錯、mainCheckout 常數、提示每次重算；§8 不做清單→無對應 task（正確）；§9 驗證 1-7→Task1 S2、Task5 S1、Task5 S2、Task2 S3、Task5 S3、Task6 S4、Task3 S3+Task6 S4；§10 規範→worktree/NOTES/常數頂部。✅
- **Placeholder scan**：NOTES 段一處刻意的「<驗證後回填>」是驗證輸出佔位（Task5 S4/Task6 S4 明確負責回填），非未完成設計；其餘無 TBD。✅
- **一致性**：守衛旗標名 `CLAUDE_REFLECT_CHILD`、state 路徑、proposals 路徑、參數名（MaterialFile/TriggerType/MainCheckout）跨 Task 統一；PS 5.1 相容（無三元/`??`，用 if-else 與 `-f`）。✅
```
