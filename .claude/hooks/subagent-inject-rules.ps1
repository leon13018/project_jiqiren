# SubagentStart hook：只對「啟動時不載入 CLAUDE.md」的 subagent 補最小 context。
#
# 官方 sub-agents.md：只有 built-in Explore / Plan 啟動時跳過 CLAUDE.md + git status；
# 其餘（general-purpose / claude-code-guide / statusline-setup / 自訂 sales-coder 等）
# 都原生載入專案 CLAUDE.md → 紅線與 skill 路由本就看得到，不需再注入（避免重複佔 attention）。
# 且 Explore / Plan 為唯讀研究 agent，主對話會帶 CLAUDE.md context 解讀其結果，故連紅線都不必傳給它們；
# 對它們真正有用的只是「繁中產出 + 專案文檔指標」這最小集（補它們看不到的 CLAUDE.md 導航）。
#
# 失敗不影響派發（exit 0 always；只是少注入）。

$ErrorActionPreference = 'Continue'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK，PRC 區域）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中會被當 cp936 解碼成亂碼（注入內容變廢）。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 用 UTF-8 StreamReader 直讀 stdin（[Console]::In 受 console code page 影響；NOTES §12 踩坑 #7）
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
$rawInput = $reader.ReadToEnd()
$payload = $null
if (-not [string]::IsNullOrWhiteSpace($rawInput)) {
    try { $payload = $rawInput | ConvertFrom-Json } catch {}
}

$agentType = if ($payload -and $payload.agent_type) { $payload.agent_type } else { 'unknown' }

# 只有 Explore / Plan 跳過 CLAUDE.md → 補最小 context；其餘 agent 原生載入 CLAUDE.md，直接放行。
$skipsClaudeMd = @('Explore', 'Plan')
if ($agentType -notin $skipsClaudeMd) {
    exit 0
}

Write-Output @"
---
## SubagentStart 注入（agent_type=$agentType；本 agent 啟動跳過 CLAUDE.md，補最小導航）

- 輸出語言：產出物（文件 / 引用 / plan）一律繁體中文（成果在台灣展示）。
- Project context 入口（本 agent 不自動載入 CLAUDE.md）：``CLAUDE.md`` + ``project-01-workflow`` skill + 巢狀 ``.claude/code_map.md``（逐層下沉、第一優先查）。
---
"@

exit 0
