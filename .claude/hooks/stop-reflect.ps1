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
