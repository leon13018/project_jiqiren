# PostToolUse hook (Bash)：偵測 pytest 跑過 → 清 flag
#
# 跟 state-mark-sales-dirty.ps1 + stop-check-sales-pytest.ps1 三方協作。
# 跑過 pytest（不論 PASS / FAIL）就清 flag，由 Claude 看 pytest 輸出自行判斷是否要再改。

$ErrorActionPreference = 'Continue'

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
