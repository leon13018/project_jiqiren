# SessionStart hook：注入專案當前狀態 summary，省主 agent 每次主動跑指令
#
# 注入內容：
#   - 當前 git branch
#   - git status --short（截斷顯示）
#   - 最新 commit
#   - sales/ 測試數
#   - 當前 source（startup / resume / clear / compact）
#
# 規格（官方確認）：
#   - SessionStart hooks 跑得快很重要（每次 session 都跑）
#   - stdout 自動進 Claude context（不必包 JSON）
#   - Subagent 內是否 fire 「未明確記載」→ 防禦寫法：agent_id 存在則 silent exit
#   - 不能 block

$ErrorActionPreference = 'Continue'

# 讀 stdin JSON
$rawInput = [Console]::In.ReadToEnd()
$payload = $null
if (-not [string]::IsNullOrWhiteSpace($rawInput)) {
    try {
        $payload = $rawInput | ConvertFrom-Json
    } catch {
        # JSON parse 失敗也照跑（用 default cwd）
    }
}

# 防禦：若 agent_id 存在 → 我們在 subagent 內 → 不注入（避免污染 subagent context）
if ($payload -and $payload.PSObject.Properties.Match('agent_id').Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($payload.agent_id)) {
    exit 0
}

$cwd = if ($payload -and $payload.cwd) { $payload.cwd } else { 'C:/Users/LIN HONG/Desktop/Project_01' }
$source = if ($payload -and $payload.source) { $payload.source } else { 'unknown' }

# 切到專案目錄
Push-Location $cwd -ErrorAction SilentlyContinue

try {
    # 跑指令收 summary
    $branch = (git rev-parse --abbrev-ref HEAD 2>$null)
    if (-not $branch) { $branch = '(無 git 資訊)' }

    $statusLines = git status --porcelain 2>$null
    $statusCount = if ($statusLines) { @($statusLines).Count } else { 0 }
    $statusPreview = if ($statusLines) {
        @($statusLines) | Select-Object -First 5 | ForEach-Object { "    $_" } | Out-String
    } else {
        "    (clean)"
    }

    $lastCommit = (git log --oneline -1 2>$null)
    if (-not $lastCommit) { $lastCommit = '(無 commit)' }

    # 數 sales/ tests
    $salesTestCount = 0
    $testFiles = Get-ChildItem -Path 'tests/sales/test_*.py' -ErrorAction SilentlyContinue
    foreach ($f in $testFiles) {
        $matches = Select-String -Path $f.FullName -Pattern '^def test_' -ErrorAction SilentlyContinue
        $salesTestCount += @($matches).Count
    }

    # 動到 sales/ 但沒跑 pytest 的 flag 狀態
    $flagFile = '.claude/hooks/state/sales-dirty.flag'
    $flagNote = ''
    if (Test-Path $flagFile) {
        $flagContent = (Get-Content $flagFile -Raw -ErrorAction SilentlyContinue).Trim()
        $flagNote = "`n- ⚠️ sales-dirty flag 存在：$flagContent（上次 session 編了 sales/* 但沒跑 pytest）"
    }

    # 輸出 — 直接 stdout 自動進 Claude context
    $summary = @"
## 專案狀態快照（SessionStart hook 注入，source=$source）

- 分支：``$branch``
- 最新 commit：``$lastCommit``
- 未提交變動：$statusCount 個檔
$statusPreview
- sales/ 測試總數：$salesTestCount（會被 Stop hook 守住 — 改了 sales/* 必跑 pytest）$flagNote

（本 summary 由 ``.claude/hooks/session-start-context.ps1`` 產生；要關掉編輯 ``.claude/settings.json``。）
"@

    Write-Output $summary
} finally {
    Pop-Location -ErrorAction SilentlyContinue
}

exit 0
