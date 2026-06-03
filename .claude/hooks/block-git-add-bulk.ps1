# PreToolUse hook：擋 `git add -A` / `git add .`（CLAUDE.md ⛔#4 強制執法）
#
# 輸入：stdin JSON（Claude Code 標準 hook input；含 tool_input.command）
# 輸出：JSON 決策（PermissionDecision deny）→ Claude 看到 reason 後改用明列檔名
#
# 通過則 exit 0 無輸出（讓正常 permission flow 處理）。

$ErrorActionPreference = 'Stop'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK，PRC 區域）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中 deny reason 會被當 cp936 解碼成亂碼。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

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
#
# 註：本 hook 在 settings.json 帶 `if: "Bash(git add *)"` gate（逐 subcommand 比對，
#     引號內不解析）→ 只有真的以 git add 開頭的子命令才 spawn 本 script。故 commit
#     message 內文含字面 -A/. 不再誤觸（gotcha K 已由 if gate 根治，毋須收緊此 regex）。
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
