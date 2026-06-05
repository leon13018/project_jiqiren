# Stop hook：每 turn 結束反思「本輪有無值得固化的學習點」→ 拋背景 worker 用 fresh-context
# claude -p 評審 → 提議 append 到 resources/reflections/proposals.md（gitignored）等人定奪。
# 藍本：官方 security-guidance plugin 第 2 層（Stop + fresh reviewer + 背景跑 + 不 block）。
# spec：resources/specs/reflective_stop_hook_2026-06-04_spec.md
#
# 設計：exit 0 always、永不 decision:block（同 stop-sync-pi，不受 8-block cap 影響）。
# 觸發：T1 = 本 turn 有 git 變動（status 非空 或 HEAD ≠ last-reflected marker）→ 素材 = diff
#       T2 = 距上次反思已 $TURN_INTERVAL 輪 → 素材 = transcript 尾段
# 防迴圈：CLAUDE_REFLECT_CHILD 旗標（claude -p 子行程早退）｜每日呼叫保險絲｜worker 端 slug 去重。
#
# 輸入：stdin JSON（session_id / transcript_path）。
# 輸出：有未讀提議時純 systemMessage 一行提示（Stop 無 hookSpecificOutput，additionalContext 會被 schema 拒收）；其餘無輸出。
# log：worker 寫 .claude/hooks/reflect.log（本檔自身故障靜默，不影響 session）。

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── 遞迴守衛：claude -p 子行程內不再反思 ──
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }

# ── 常數（調整處集中此區）──
$TURN_INTERVAL  = 20     # T2：每 20 輪無變動也統整一次
$DAILY_CAP      = 100    # 每日模型呼叫保險絲（正常用不到，防自動化長跑暴走）
$DIFF_CAP_LINES = 400    # T1 素材 diff 行數上限
$LOCK_ZOMBIE_MIN = 10    # lock 超過 10 分鐘視為殭屍

$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$stateDir   = Join-Path $mainCheckout '.claude/hooks/state/reflect'
$proposals  = Join-Path $mainCheckout 'resources/reflections/proposals.md'
$workerPath = Join-Path $mainCheckout '.claude/hooks/reflect-worker.ps1'

# ── log 輪轉：>1MB 改名 .1（覆蓋舊 .1；仿官方 security-guidance _base.py 1MB rotate）──
$logFile = Join-Path $mainCheckout '.claude/hooks/reflect.log'
if ((Test-Path $logFile) -and ((Get-Item $logFile -ErrorAction SilentlyContinue).Length -gt 1MB)) {
    Move-Item $logFile ($logFile + '.1') -Force -ErrorAction SilentlyContinue
}

try {
    # 用 UTF-8 StreamReader 直讀 stdin（自動去 BOM）；[Console]::In 受 console code page（cp936）影響，
    # live 環境曾因此解析不到 session_id（NOTES §12 踩坑 #7）
    $reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
    $stdinRaw = $reader.ReadToEnd()
    $evt = $null
    try { $evt = $stdinRaw | ConvertFrom-Json } catch {}
    $sessionId = 'unknown'
    if ($evt -and $evt.session_id) { $sessionId = [string]$evt.session_id }
    $transcriptPath = ''
    if ($evt -and $evt.transcript_path) { $transcriptPath = [string]$evt.transcript_path }

    if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force $stateDir | Out-Null }

    # 解析不到 session_id → 記診斷（截前 80 字），下次發生可直接確診
    if ($sessionId -eq 'unknown') {
        $san = ($stdinRaw -replace '\s+', ' ')
        if ($san.Length -gt 80) { $san = $san.Substring(0, 80) }
        Add-Content -Path (Join-Path $mainCheckout '.claude/hooks/reflect.log') -Encoding UTF8 -ErrorAction SilentlyContinue `
            -Value ('[{0}] 診斷：stdin 解析不到 session_id（len={1}）：{2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $stdinRaw.Length, $san)
    }

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
        elseif ($pending -lt $lastNotified) {
            # 人工清理 / 改 status 後計數回落 → 同步下修，否則下一條新提議的提示會被吞
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
    # 每日保險絲（按日重置；session_id 只作診斷用，不當計數鍵——live 曾解析失敗成 unknown 導致永不重置）
    $callsFile = Join-Path $stateDir ('daily-calls_' + (Get-Date -Format 'yyyyMMdd') + '.txt')
    Get-ChildItem $stateDir -Filter 'daily-calls_*.txt' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force -ErrorAction SilentlyContinue
    $calls = 0
    if (Test-Path $callsFile) { $calls = [int](Get-Content $callsFile -ErrorAction SilentlyContinue | Select-Object -First 1) }
    if ($calls -ge $DAILY_CAP) { $skipReflect = $true }

    # ── 觸發判斷 ──
    $trigger = ''
    $materialFile = Join-Path $stateDir ('material_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.txt')
    $counterFile = Join-Path $stateDir 'turn-count.txt'
    $turnCount = 0
    if (Test-Path $counterFile) { $turnCount = [int](Get-Content $counterFile -ErrorAction SilentlyContinue | Select-Object -First 1) }

    if (-not $skipReflect) {
        # T1：本 turn 有 git 變動？
        # quotePath=false：中文檔名輸出原始 UTF-8 而非八進位轉義（評審模型才看得懂；仿官方 gitutil.py）
        $statusOut = (& git -C $mainCheckout -c core.quotePath=false status --porcelain 2>$null)
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
                $rangeDiff = @(& git -C $mainCheckout -c core.quotePath=false diff "$marker..$head" 2>$null)
                $parts += ($rangeDiff | Select-Object -First $DIFF_CAP_LINES | Out-String)
                # 截斷必註記（no silent caps）：讓評審知道素材是殘篇，避免下錯結論
                if ($rangeDiff.Count -gt $DIFF_CAP_LINES) { $parts += ('（diff 已截斷：{0} 行 → 前 {1} 行）' -f $rangeDiff.Count, $DIFF_CAP_LINES) }
            }
            if ($statusOut) {
                $parts += '## 未提交 diff'
                $wtDiff = @(& git -C $mainCheckout -c core.quotePath=false diff 2>$null)
                $parts += ($wtDiff | Select-Object -First $DIFF_CAP_LINES | Out-String)
                if ($wtDiff.Count -gt $DIFF_CAP_LINES) { $parts += ('（diff 已截斷：{0} 行 → 前 {1} 行）' -f $wtDiff.Count, $DIFF_CAP_LINES) }
            }
            [System.IO.File]::WriteAllText($materialFile, ($parts -join "`n"), [System.Text.UTF8Encoding]::new($false))
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
        # ⚠️ Start-Process 的 ArgumentList 不自動加引號——路徑含空白（LIN HONG）必須手動包 "
        # MarkerSha 只在 T1 傳：worker 成功（claude 有回應）才前移 marker，失敗下輪重審（spec 改動1）
        $workerArgs = @(
            '-NoProfile','-File', ('"{0}"' -f $workerPath),
            '-MaterialFile', ('"{0}"' -f $materialFile),
            '-TriggerType', $trigger,
            '-MainCheckout', ('"{0}"' -f $mainCheckout)
        )
        if ($trigger -eq 'T1' -and $head) { $workerArgs += @('-MarkerSha', $head) }
        Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList $workerArgs | Out-Null
    } else {
        [System.IO.File]::WriteAllText($counterFile, [string]($turnCount + 1), [System.Text.UTF8Encoding]::new($false))
    }

    if ($hint) {
        # Stop 事件無 hookSpecificOutput union member（2026-06-05 live 實測：帶 additionalContext 整包被
        # schema 驗證拒收，連 systemMessage 都沒顯示）→ 純 systemMessage。提示給「人」看即符合人定奪設計；
        # 要餵 model 只能 decision:block+reason，與本 hook 永不 block 原則衝突，不採。
        Write-Output (@{ systemMessage = $hint } | ConvertTo-Json -Compress)
    }
} catch {}
exit 0
