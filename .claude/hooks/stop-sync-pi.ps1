# Stop hook：每個 turn 結束時，若 origin/main 已前進到 marker 未記錄的 commit → 自動 sync 到 Pi。
#
# 取代舊 auto-sync-pi.ps1（PostToolUse async，background 觸發非確定性 = NOTES gotcha N）。
# Stop hook 在所有 session 類型（含 headless/background）可靠 fire（官方確認）。
# 自我修正：任何原因漏掉的 sync，下個 turn 結束自動補（marker 未更新就重試）。
#
# 設計：exit 0 always、永不 decision:block（sync 是純 side effect；不阻斷 turn；
#       不受官方「Stop 連續 block 8 次強制 override」cap 影響，不可能 deadlock）。
# marker：.claude/hooks/state/last-synced-commit.marker（gitignored）存上次成功 sync 的 origin/main SHA。
#
# 輸入：stdin JSON（Stop hook；內容用不到，僅 drain）。
# 輸出：log → .claude/hooks/stop-sync-pi.log（gitignored）；實際 sync 成功時 systemMessage 回饋 user。

$ErrorActionPreference = 'Continue'

# PS 5.1 預設 OutputEncoding 為系統 code page（本機 cp936）；輸出 systemMessage 繁中需 UTF-8。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 反思 hook 的 claude -p 子行程守衛（見 stop-reflect.ps1）：子 session 不 sync
if ($env:CLAUDE_REFLECT_CHILD -eq '1') { exit 0 }

try {
    # drain stdin（Stop hook 不需內容，但要讀掉避免 broken pipe）
    $null = (New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)).ReadToEnd()

    $mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
    $markerFile = Join-Path $mainCheckout '.claude/hooks/state/last-synced-commit.marker'
    $logFile    = Join-Path $mainCheckout '.claude/hooks/stop-sync-pi.log'
    # log 輪轉：>1MB 改名 .1（覆蓋舊 .1）
    if ((Test-Path $logFile) -and ((Get-Item $logFile -ErrorAction SilentlyContinue).Length -gt 1MB)) {
        Move-Item $logFile ($logFile + '.1') -Force -ErrorAction SilentlyContinue
    }
    $syncScript = Join-Path $mainCheckout 'sync_pi.ps1'

    # 當前已 push 到遠端的 commit（push 後本地 origin/main remote-tracking ref 即更新；worktree 共用 ref store）
    $pushed = (& git -C $mainCheckout rev-parse origin/main 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pushed)) {
        exit 0   # 無 origin/main ref（如剛 clone 未 push）→ 不做事
    }
    $pushed = $pushed.Trim()

    # 上次成功 sync 的 commit（防禦性去 BOM + trim）
    $lastSync = ''
    if (Test-Path $markerFile) {
        $raw = Get-Content $markerFile -Raw -Encoding utf8 -ErrorAction SilentlyContinue
        if ($null -ne $raw) { $lastSync = $raw.TrimStart([char]0xFEFF).Trim() }
    }

    if ($pushed -eq $lastSync) {
        exit 0   # Pi 已是最新 → 零 SSH（純聊天 / 無 push 的 turn 走這條）
    }

    # --- origin/main 落後於 marker → 跑 sync ---
    if (-not (Test-Path $syncScript)) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 not found at $syncScript" | Out-File -FilePath $logFile -Append -Encoding utf8
        exit 0
    }

    $logDir = Split-Path $logFile -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] origin/main=$pushed marker=$lastSync -> syncing" | Out-File -FilePath $logFile -Append -Encoding utf8

    # 跑 sync_pi.ps1（Pi git pull）。inline EAP=Continue 處理 ssh/git stderr 雜訊，靠 $LASTEXITCODE 判斷成敗。
    # *>&1（非 2>&1）：sync_pi.ps1 用 Write-Host（走 Information stream 6，會繞過 pipeline 噴到 stdout）。
    # Stop hook stdout 會被 Claude Code 解析，混入非 JSON 雜訊會踩 parse 失敗（NOTES gotcha J 類）。
    # *>&1 合併所有串流（1-6）進 Out-File，確保 hook stdout 只剩我們明確 Write-Output 的 systemMessage JSON。
    $eapBackup = $ErrorActionPreference
    $syncExit = 1
    try {
        $ErrorActionPreference = 'Continue'
        & $syncScript *>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        $syncExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $eapBackup
    }

    if ($syncExit -eq 0) {
        # 清 Pi __pycache__（best-effort，獨立 try，失敗不影響 marker；避免 stale .pyc 攔截 latest source）
        try {
            $ErrorActionPreference = 'Continue'
            ssh "pi@raspberrypi.local" "find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +" 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        } catch {
        } finally {
            $ErrorActionPreference = $eapBackup
        }
        # 只有 sync 成功才寫 marker（失敗 → marker 不動 → 下個 turn 自動重試）。no-BOM 寫入避免 SHA 比對受 BOM 干擾。
        [System.IO.File]::WriteAllText($markerFile, $pushed, (New-Object System.Text.UTF8Encoding $false))
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] synced ok, marker=$pushed" | Out-File -FilePath $logFile -Append -Encoding utf8
        # 回饋 user（exit 0 + systemMessage；非 decision，不阻斷 turn）
        $sha7 = $pushed.Substring(0, [Math]::Min(7, $pushed.Length))
        (@{ systemMessage = "Pi synced to $sha7" } | ConvertTo-Json -Compress)
    } else {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync exit=$syncExit, marker NOT updated (下個 turn 重試)" | Out-File -FilePath $logFile -Append -Encoding utf8
    }
    exit 0
} catch {
    exit 0   # fail-open：任何例外都不阻斷 turn
}
