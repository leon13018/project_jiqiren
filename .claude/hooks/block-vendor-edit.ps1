# PreToolUse hook：擋對廠商 SDK 檔的 Edit/Write（CLAUDE.md ⛔#1 強制執法）
#
# 守住的檔：myProgram/ActionGroupControl.py 與 myProgram/Board.py
# 廠商 Hiwonder TonyPi SDK 含 Pi-only 路徑與底層 import，改了破壞硬體通訊。
#
# 輸入：stdin JSON（含 tool_input.file_path）
# 輸出：JSON 決策（deny）；通過則 exit 0 無輸出。

$ErrorActionPreference = 'Stop'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（台灣機器 = Big5/cp950），
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中 deny reason 會被當 Big5 解碼成亂碼。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) {
    exit 0
}

try {
    $payload = $rawInput | ConvertFrom-Json
} catch {
    exit 0
}

$filePath = $payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($filePath)) {
    exit 0
}

# 規範化路徑分隔字元（Windows 可能傳 \ 也可能 /），統一比對
$normalized = $filePath -replace '\\', '/'

# 命中條件：路徑結尾為 ActionGroupControl.py 或 Board.py（在 myProgram/ 下）
if ($normalized -match '/myProgram/(ActionGroupControl|Board)\.py$') {
    $decision = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = "禁改廠商 SDK ($filePath)。Hiwonder TonyPi SDK 含 Pi-only 路徑與底層庫 import（pigpio / RPi.GPIO / BusServoCmd / smbus2），改了會破壞硬體通訊（CLAUDE.md ⛔#1）。只能 Read 引用、import 使用。"
        }
    }
    $decision | ConvertTo-Json -Depth 10 -Compress
    exit 0
}

exit 0
