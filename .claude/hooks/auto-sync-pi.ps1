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
#
# 2026-05-27 修：之前用 `try { ... } catch` + `$ErrorActionPreference='Stop'` 在處理 `2>&1` 時會
# 把 native command（ssh / git）的 stderr 包成 ErrorRecord 進 pipeline → 觸發 terminating error
# → 跳到 catch。實測踩到兩種 stderr 雜訊：(1) `git pull` 印 "From https://github.com/..." 進度訊息；
# (2) OpenSSH 新版量子安全警告「This session may be vulnerable to "store now, decrypt later"
# attacks. ** The server may need to be upgraded.」。兩者都不是真錯誤，但都會 trigger 誤標
# 並中斷後續流程（特別是 pycache 清理被跳過 → demo 跑 stale .pyc）。
#
# 修法：inline 切 ErrorActionPreference='Continue' 跑 native command，改用 $LASTEXITCODE
# 判斷成功失敗（這是 native command 才有的可靠指標）；finally 恢復原 EAP。
$eapBackup = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $syncScript 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $syncExit = $LASTEXITCODE
    if ($syncExit -eq 0) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 completed exit=0" | Out-File -FilePath $logFile -Append -Encoding utf8
    } else {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 exit=$syncExit (非零 — sync 可能失敗，需檢查上方輸出)" | Out-File -FilePath $logFile -Append -Encoding utf8
    }
} catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 unexpected exception: $_" | Out-File -FilePath $logFile -Append -Encoding utf8
} finally {
    $ErrorActionPreference = $eapBackup
}

# 2026-05-27 加：sync 後清 Pi 端 __pycache__，避免 stale .pyc 攔截 latest source。
# 背景：Pi 實機 reproduce 顯示 git pull 拉到 latest source 但 Python 仍 import
# cached .pyc（NLU HP-1「沒」strict_short → 結帳 修補不生效，「沒」走 unclear）。
# 清光 __pycache__ 後 Python 強制重新 compile latest source。
# idempotent — 沒有 __pycache__ 也只是 find 返 0 個結果，cost ~50ms SSH latency。
#
# **獨立 try（不接前面 sync_pi.ps1 的 try）**：確保「sync 即使被誤標 error 也仍清 pycache」。
# 同樣 inline 切 EAP='Continue' 處理 ssh 自身的 stderr 警告（OpenSSH 量子安全 / host key 等）。
try {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Clearing Pi __pycache__ ..." | Out-File -FilePath $logFile -Append -Encoding utf8
    $ErrorActionPreference = 'Continue'
    ssh "pi@raspberrypi.local" "find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +" 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $cleanExit = $LASTEXITCODE
    if ($cleanExit -eq 0) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Pi __pycache__ cleared exit=0" | Out-File -FilePath $logFile -Append -Encoding utf8
    } else {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Pi __pycache__ clean exit=$cleanExit (非零)" | Out-File -FilePath $logFile -Append -Encoding utf8
    }
} catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Pi __pycache__ clean unexpected exception: $_" | Out-File -FilePath $logFile -Append -Encoding utf8
} finally {
    $ErrorActionPreference = $eapBackup
}

exit 0
