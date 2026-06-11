# PostToolUse hook (Bash|PowerShell)：偵測 pytest 跑過 → 清 flag
#
# 跟 state-mark-sales-dirty.ps1 + stop-check-sales-pytest.ps1 三方協作。
# 跑過 pytest（不論 PASS / FAIL）就清 flag，由 Claude 看 pytest 輸出自行判斷是否要再改。
#
# matcher 必須含 PowerShell（2026-06-11 修誤報）：兩個 shell 工具的 tool_input 都用
# `command` 欄位，script 本體共用；原只掛 Bash → 用 PowerShell 工具跑 pytest 時
# 本 hook 不 fire、flag 清不掉 → Stop hook 誤報「沒跑過 pytest」。

$ErrorActionPreference = 'Continue'

# 用 UTF-8 StreamReader 直讀 stdin（[Console]::In 受 console code page 影響；NOTES §12 踩坑 #7）
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
$rawInput = $reader.ReadToEnd()
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

# 偵測：command 是否含 pytest 字眼
# 包含：`pytest` / `python -m pytest` / `py.test`
if ($cmd -notmatch '\b(pytest|py\.test)\b') {
    exit 0
}

# 刪 flag（若存在）
$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$flagFile = Join-Path $mainCheckout '.claude/hooks/state/sales-dirty.flag'
if (Test-Path $flagFile) {
    Remove-Item $flagFile -Force -ErrorAction SilentlyContinue
}

exit 0
