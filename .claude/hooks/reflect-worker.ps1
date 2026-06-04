# 反思背景 worker：被 stop-reflect.ps1 以 Start-Process 拋出（detached，不阻塞 turn）。
# 職責：組 prompt → claude -p（fresh context、便宜 model、禁工具指示）→ 解析 → slug 去重 →
#       append resources/reflections/proposals.md → 釋放 lock → log。
# 任何故障：log 後靜默結束（session 零感知）。spec §4/§6。

param(
    [Parameter(Mandatory=$true)][string]$MaterialFile,
    [Parameter(Mandatory=$true)][string]$TriggerType,
    [Parameter(Mandatory=$true)][string]$MainCheckout
)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$REFLECT_MODEL = 'claude-haiku-4-5-20251001'
$PROPOSAL_MAX  = 3
$CALL_TIMEOUT_S = 120

$stateDir  = Join-Path $MainCheckout '.claude/hooks/state/reflect'
$lockFile  = Join-Path $stateDir 'lock'
$logFile   = Join-Path $MainCheckout '.claude/hooks/reflect.log'
$proposals = Join-Path $MainCheckout 'resources/reflections/proposals.md'

function Write-Log([string]$msg) {
    $line = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
    Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

try {
    if (-not (Test-Path $MaterialFile)) { Write-Log "material 不存在：$MaterialFile"; exit 0 }
    $material = [System.IO.File]::ReadAllText($MaterialFile, [System.Text.Encoding]::UTF8)

    $promptHeader = @'
你是 fresh-context 審計員，審另一個 coding agent 本輪工作的「學習點」，與其產出無利害關係。
不要使用任何工具，直接輸出文字結論。

只報符合以下任一門檻的學習點（其餘一律不報）：
- 影響程式正確性的坑
- 違反專案紅線（禁改 vendor SDK / 禁 Windows 裝依賴 / 禁 git add -A / 產出須繁體中文）
- 同類錯誤在素材中出現 ≥2 次
- 使用者明確糾正過的行為

風格喜好、一次性小失誤、有能力的 model 本來就會做對的事：不報。
沒有值得報的 → 只輸出 NONE。

有則最多 3 條，每條嚴格用此格式（條間以 --- 分隔）。
SLUG 必須是英文小寫 kebab-case（如 traditional-chinese-comments）；
BODY 一律**繁體中文（台灣用語）**——這條是硬規則，輸出前自查不得出現簡體字：
SLUG: <english-kebab-case>
LAYER: NOTES|CLAUDE.md|skill|memory
BODY: <≤3 行繁體中文，說清楚踩了什麼、建議固化什麼>

以下是素材（
'@
    # 既有提議主題餵進 prompt → 評審端語意去重（事後 slug 字串比對只是保底，攔不住同義異名）。
    # ⚠️ 不可用 Select-String -Path：PS 5.1 對無 BOM UTF-8 檔會以 cp936 誤解碼，全形「｜」匹配必失敗。
    $existing = ''
    if (Test-Path $proposals) { $existing = [System.IO.File]::ReadAllText($proposals, [System.Text.Encoding]::UTF8) }
    $slugLine = ''
    $slugs = @([regex]::Matches($existing, '(?m)^## \d{4}-\d{2}-\d{2} (\S+?)｜') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Last 30)
    if ($slugs.Count -gt 0) {
        $slugLine = "`n已存在的提議主題（與這些**同義或同主題**的一律不要再報，視為已報過）：" + ($slugs -join '、') + "`n"
    }

    $prompt = $promptHeader + $TriggerType + @'
）：

'@ + $slugLine + $material

    # 子行程守衛旗標 + cwd 移出專案（雙保險：專案 hooks 不載入、我們的 Stop hook 也有旗標早退）
    $env:CLAUDE_REFLECT_CHILD = '1'
    Push-Location $env:TEMP

    $claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claudeCmd) { Write-Log 'claude CLI 不存在，跳過'; exit 0 }

    # prompt 走 stdin（免 3s stdin 偵測警告、免 Windows 命令列長度上限、免引號地獄）
    $job = Start-Job -ScriptBlock {
        param($p, $m)
        $env:CLAUDE_REFLECT_CHILD = '1'
        $OutputEncoding = [System.Text.UTF8Encoding]::new($false)            # 餵 stdin 給 claude 用 UTF-8
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8             # 解碼 claude stdout（job host 預設 cp936 → 繁中變亂碼）
        $p | & claude -p --model $m 2>&1 | Out-String
    } -ArgumentList $prompt, $REFLECT_MODEL
    if (-not (Wait-Job $job -Timeout $CALL_TIMEOUT_S)) {
        Stop-Job $job -ErrorAction SilentlyContinue
        Write-Log ('claude -p 逾時（>{0}s），放棄本次' -f $CALL_TIMEOUT_S)
        exit 0
    }
    $output = (Receive-Job $job | Out-String).Trim()
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Pop-Location

    if (-not $output) { Write-Log 'claude -p 無輸出'; exit 0 }
    if ($output -match '(?m)^\s*NONE\s*$' -and $output.Length -lt 40) { Write-Log ("{0} 反思：NONE" -f $TriggerType); exit 0 }

    # 解析 + 去重（$existing 已在 prompt 階段讀入）+ 落地
    if (-not (Test-Path (Split-Path $proposals))) { New-Item -ItemType Directory -Force (Split-Path $proposals) | Out-Null }
    if (-not (Test-Path $proposals)) {
        [System.IO.File]::WriteAllText($proposals, "# 反思提議（append-only；採納/否決後把該條 status 改掉或刪除）`n", [System.Text.UTF8Encoding]::new($false))
    }

    $added = 0
    foreach ($block in ($output -split '(?m)^---\s*$')) {
        if ($added -ge $PROPOSAL_MAX) { break }
        if ($block -notmatch 'SLUG:\s*(?<slug>\S+)') { continue }   # \S+ 容錯：model 可能無視 kebab-case 指示（實測 Haiku 會回中文 slug）
        $slug = $Matches['slug']
        $layer = '未指定'
        if ($block -match 'LAYER:\s*(?<layer>\S+)') { $layer = $Matches['layer'] }
        $body = ''
        if ($block -match '(?s)BODY:\s*(?<body>.+)$') { $body = ($Matches['body'] -replace '(?s)\s*`{3,}\s*$','').Trim() }   # 清掉 model 偶發的尾部 code fence
        if (-not $body) { continue }
        if ($existing -match [regex]::Escape($slug)) { Write-Log ("去重丟棄：{0}" -f $slug); continue }
        $entry = "`n## {0} {1}｜{2}｜建議層:{3}`n{4}`nstatus: pending`n" -f (Get-Date -Format 'yyyy-MM-dd'), $slug, $TriggerType, $layer, $body
        Add-Content -Path $proposals -Value $entry -Encoding UTF8
        $existing += $slug
        $added++
    }
    Write-Log ("{0} 反思完成：新增 {1} 條提議" -f $TriggerType, $added)
} catch {
    Write-Log ("worker 例外：{0}" -f $_.Exception.Message)
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
    Remove-Item $MaterialFile -Force -ErrorAction SilentlyContinue
}
exit 0
