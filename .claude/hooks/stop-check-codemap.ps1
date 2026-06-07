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
            $deadRefs = @($healthOut | Where-Object { $_ -match '死引用：' } | ForEach-Object { $_.Trim() })
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
