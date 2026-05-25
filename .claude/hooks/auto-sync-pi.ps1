# PostToolUse hook：`git push origin main` 成功後自動跑 sync_pi.ps1
#
# 取代 standard-workflow.md 步驟 5 / worktree-workflow.md 階段 4 最後一步的「手動跑 sync_pi」。
# 設定 async: true → 在背景跑（120s timeout），不卡 Claude 主流程。
#
# 輸入：stdin JSON（含 tool_input.command）
# 輸出：sync 動作 → 日誌寫到 .claude/hooks/auto-sync-pi.log（gitignored）

$ErrorActionPreference = 'Stop'

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) {
    exit 0
}

try {
    $payload = $rawInput | ConvertFrom-Json
} catch {
    exit 0
}

$cmd = $payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($cmd)) {
    exit 0
}

# 只在 push 到 main 時觸發（避免每個 git 命令都觸發）
# Regex 容許 git 與 push 之間有任意 git options（-C / --git-dir 等）；
# 也容許 push 與 origin 之間有任意 push flags（--force / --force-with-lease / -f / -u 等）。
# [^;&|\r\n] 阻止跨 shell separator 誤匹配（例：`git status && git push origin main`
# 仍能命中第二個 git，但 `git status; some_other_thing push origin main` 不會跨進來）。
if ($cmd -notmatch '\bgit\b[^;&|\r\n]*?\bpush\b[^;&|\r\n]*?\borigin\s+main\b') {
    exit 0
}

# 找 sync_pi.ps1 — sync_pi.ps1 是 gitignored，**只存在 main checkout**
# Worktree 內看不到，所以先用 hardcoded 主 checkout 路徑，再 fallback 到 env var
$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$syncScript = Join-Path $mainCheckout 'sync_pi.ps1'

if (-not (Test-Path $syncScript)) {
    # Fallback：env var（萬一 user 把 repo 搬家）
    $projectDir = $env:CLAUDE_PROJECT_DIR
    if (-not [string]::IsNullOrWhiteSpace($projectDir)) {
        $syncScript = Join-Path $projectDir 'sync_pi.ps1'
    }
}

# log 寫到 main checkout 內（worktree cleanup 不會誤刪）
$projectDir = $mainCheckout

if (-not (Test-Path $syncScript)) {
    # script 不在 → 寫個 log 但不報錯
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 not found at $syncScript" | Out-File -FilePath (Join-Path $projectDir '.claude/hooks/auto-sync-pi.log') -Append -Encoding utf8
    exit 0
}

# 日誌（dir 不存在自動建）
$logFile = Join-Path $projectDir '.claude/hooks/auto-sync-pi.log'
$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Triggered by: $cmd" | Out-File -FilePath $logFile -Append -Encoding utf8

# 跑 sync_pi.ps1（output 也進 log）
try {
    & $syncScript 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 completed" | Out-File -FilePath $logFile -Append -Encoding utf8
} catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 ERROR: $_" | Out-File -FilePath $logFile -Append -Encoding utf8
}

exit 0
