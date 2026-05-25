# Stop hook：本輪結束前若 sales/* 編輯過但沒跑 pytest → block 一次提醒
#
# 三方協作（見 state-mark-sales-dirty.ps1 docstring）：
#   - flag=pending → output decision:block + reason；改 flag 為 reminded（避免無限循環）
#   - flag=reminded → silent exit 0（已提醒過，本輪不再 block）
#   - flag 不存在 → silent exit 0
#
# 為何只 block 一次：
#   若 Claude 真的不能/不想跑 pytest（例：純 docstring 修改），無限 block 會 deadlock。
#   reminded 後使用者 / Claude 自行判斷。flag 會在下次 sales/ 編輯時 reset 回 pending。
#
# Stop hook 規格（官方確認）：
#   - 不支援 additionalContext，只能 top-level decision:block + reason
#   - exit 2 等同 decision:block
#   - 在 subagent 內 Stop 會自動轉成 SubagentStop，本 hook 不會被誤觸發

$ErrorActionPreference = 'Continue'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK，PRC 區域）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中 reason 會被當 cp936 解碼成亂碼。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
$flagFile = Join-Path $mainCheckout '.claude/hooks/state/sales-dirty.flag'

if (-not (Test-Path $flagFile)) {
    exit 0
}

$flagContent = Get-Content $flagFile -Raw -Encoding utf8 -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($flagContent)) {
    exit 0
}

# Parse flag: <status>|<timestamp>|<file_path>
$parts = $flagContent.Trim() -split '\|', 3
$status = $parts[0]

if ($status -eq 'reminded') {
    # 已提醒過，本輪不再 block
    exit 0
}

if ($status -ne 'pending') {
    # 未知狀態，安全起見當作不提醒
    exit 0
}

# pending → block 並更新為 reminded
$timestamp = if ($parts.Length -ge 2) { $parts[1] } else { 'unknown' }
$editedFile = if ($parts.Length -ge 3) { $parts[2] } else { 'unknown' }

$reason = "本輪有編輯到 sales/* 的檔（最後一次：$editedFile @ $timestamp）但似乎沒跑過 pytest。建議跑一次 ``python -m pytest tests/sales/ -q`` 確認 regression net 沒破再結束。若是純 docstring/註解修改或刻意跳過，再按一次結束即可（本提醒每輪只跑一次）。"

# 更新 flag 為 reminded（避免下次 Stop 又 block）
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"reminded|$timestamp|$editedFile" | Out-File -FilePath $flagFile -Encoding utf8 -Force

# 輸出 block decision JSON
$decision = @{
    decision = 'block'
    reason = $reason
}
$decision | ConvertTo-Json -Depth 5 -Compress
exit 0
