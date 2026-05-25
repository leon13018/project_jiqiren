# PreToolUse hook：擋 `git add -A` / `git add .`（CLAUDE.md ⛔#4 強制執法）
#
# 輸入：stdin JSON（Claude Code 標準 hook input；含 tool_input.command）
# 輸出：JSON 決策（PermissionDecision deny）→ Claude 看到 reason 後改用明列檔名
#
# 通過則 exit 0 無輸出（讓正常 permission flow 處理）。

$ErrorActionPreference = 'Stop'

# 讀 stdin JSON
$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) {
    exit 0
}

try {
    $payload = $rawInput | ConvertFrom-Json
} catch {
    # 解析失敗不擋 — 寧可放過也別誤殺
    exit 0
}

$cmd = $payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($cmd)) {
    exit 0
}

# Regex 同時擋：
#   git add -A
#   git add --all
#   git add .        （點號做為唯一 path 參數，或後面只接空白）
# 不擋：git add ./path/to/file（點號後接路徑分隔字元）
if ($cmd -match '\bgit\s+add\s+(-A\b|--all\b|\.(?:\s|$))') {
    $decision = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = "禁用 'git add -A' / 'git add .'（CLAUDE.md ⛔#4）— 請明列檔名，避免誤加 untracked 檔（如 .env / 大檔 / 私密檔）"
        }
    }
    $decision | ConvertTo-Json -Depth 10 -Compress
    exit 0
}

exit 0
