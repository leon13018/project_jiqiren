# PostToolUse hook (Edit|Write)：偵測 sales/ 編輯 → 寫 flag 檔
#
# 設計：Stop hook 沒有 tool 歷史可讀（官方確認），所以走 flag file 三方協作：
#   1. 本 script：每次 Edit/Write 到 sales/* → 寫 flag (status=pending)
#   2. state-clear-on-pytest.ps1：偵測到 pytest 跑 → 刪 flag
#   3. stop-check-sales-pytest.ps1：Stop 時若 flag=pending → block 一次 + 改 reminded
#
# Flag 檔：.claude/hooks/state/sales-dirty.flag（gitignored）
# Flag 內容：<status>|<timestamp>|<file_path>

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

$filePath = $payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($filePath)) {
    exit 0
}

# 規範化路徑分隔字元
$normalized = $filePath -replace '\\', '/'

# 偵測：是否動到 sales/ 相關檔（prod 或 test 皆算）
$isSalesProd = $normalized -match '/myProgram/sales/.*\.py$'
$isSalesTest = $normalized -match '/tests/sales/.*\.py$'

if (-not ($isSalesProd -or $isSalesTest)) {
    exit 0
}

# 寫 flag（不論已存在 pending 或 reminded，都重置為 pending）
# 理由：再編一次代表新動作，要再次提醒
$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$stateDir = Join-Path $mainCheckout '.claude/hooks/state'
if (-not (Test-Path $stateDir)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}

$flagFile = Join-Path $stateDir 'sales-dirty.flag'
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"pending|$timestamp|$filePath" | Out-File -FilePath $flagFile -Encoding utf8 -Force

exit 0
