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

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK，PRC 區域）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中會被當 cp936 解碼成亂碼（注入內容變廢）。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 讀 stdin JSON
# 用 UTF-8 StreamReader 直讀 stdin（[Console]::In 受 console code page 影響；NOTES §12 踩坑 #7）
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
$rawInput = $reader.ReadToEnd()
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

    # model 換代偵測（harness-evolution）：model 欄位存在才比對；換代 → 提醒重訪 watchlist
    $modelNote = ''
    $curModel = ''
    if ($payload -and $payload.PSObject.Properties.Match('model').Count -gt 0 -and $payload.model) {
        $curModel = if ($payload.model -is [string]) { $payload.model } else { [string]$payload.model.id }
    }
    if (-not [string]::IsNullOrWhiteSpace($curModel)) {
        $modelStateFile = '.claude/hooks/state/last-model.txt'
        $prevModel = if (Test-Path $modelStateFile) { (Get-Content $modelStateFile -Raw -ErrorAction SilentlyContinue).Trim() } else { '' }
        if ($prevModel -and $prevModel -ne $curModel) {
            $modelNote = "`n- ⚠️ model 已換代（$prevModel → $curModel）：harness 假設可能過時，建議重訪 resources/watchlist.md（協議見 skill reference/harness-evolution.md）"
        }
        if ($prevModel -ne $curModel) {
            try {
                $stateDir = Split-Path $modelStateFile -Parent
                if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force $stateDir | Out-Null }
                [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $modelStateFile), $curModel, (New-Object System.Text.UTF8Encoding($false)))
            } catch {}
        }
    }

    # 輸出 — 直接 stdout 自動進 Claude context
    $summary = @"
## 專案狀態快照（SessionStart hook 注入，source=$source）

- 分支：``$branch``
- 最新 commit：``$lastCommit``
- 未提交變動：$statusCount 個檔
$statusPreview
- sales/ 測試總數：$salesTestCount（會被 Stop hook 守住 — 改了 sales/* 必跑 pytest）$flagNote$modelNote

（本 summary 由 ``.claude/hooks/session-start-context.ps1`` 產生；要關掉編輯 ``.claude/settings.json``。）
"@

    Write-Output $summary
} finally {
    Pop-Location -ErrorAction SilentlyContinue
}

exit 0
