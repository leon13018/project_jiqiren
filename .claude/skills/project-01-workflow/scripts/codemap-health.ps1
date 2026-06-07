# codemap-health.ps1 — code_map 死引用健檢（只報告，絕不改檔）
# 用法：pwsh -File codemap-health.ps1 [-RepoRoot <path>]
#   gitignored 檔不進 worktree——一律從主 checkout 跑（或 -RepoRoot 指主 checkout）。
# Exit：0=全綠 1=僅警告 2=有死引用
param(
    [string]$RepoRoot = ''
)
$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
if (-not (Test-Path (Join-Path $RepoRoot '.claude\code_map.md'))) {
    Write-Output ("❌ 找不到 root code_map：{0}\.claude\code_map.md" -f $RepoRoot)
    exit 2
}

$errs  = New-Object System.Collections.Generic.List[string]
$warns = New-Object System.Collections.Generic.List[string]

# 找全部 <層>/.claude/code_map.md（排除 worktrees）
# worktrees 排除須比對「相對 RepoRoot」路徑——比對完整路徑時，-RepoRoot 指向 worktree 會把所有檔排光（靜默假全綠）
$maps = @(Get-ChildItem $RepoRoot -Recurse -Filter 'code_map.md' -File -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -match '\\\.claude\\code_map\.md$' -and $_.FullName.Substring($RepoRoot.Length) -notmatch '\\worktrees\\' })

foreach ($m in $maps) {
    $layerRoot = Split-Path (Split-Path $m.FullName -Parent) -Parent   # <層>/.claude/code_map.md → <層>
    $relMap = $m.FullName.Substring($RepoRoot.Length).TrimStart('\')
    $candidates = 0
    foreach ($line in (Get-Content $m.FullName)) {
        $lineDirs = New-Object System.Collections.Generic.List[string]   # 本行已解析成目錄的 token 完整路徑
        foreach ($cm in [regex]::Matches($line, '`([^`]+)`')) {
            $tok = $cm.Groups[1].Value.Trim()
            # 只查「像路徑」的：結尾 / 、含 / 、或（無斜線時）副檔名在白名單——擋套件名如 RPi.GPIO
            $looksPath = ($tok -match '/') -or ($tok -match '\.(md|py|ps1|js|json|ini|txt|yml|yaml|d6a|html|log|cfg|toml|flag)$')
            if (-not $looksPath) { continue }
            # 排除：純副檔名 mention（如 `.d6a`）、含空白 / 角括號 / @ / 破折號 / 括號、~ 或 / 開頭、磁碟機開頭
            if ($tok -match '^\.[A-Za-z0-9]{1,5}$') { continue }
            if ($tok -match '[\s<>@—()]' -or $tok -match '^[~/]' -or $tok -match '^[A-Za-z]:') { continue }
            $candidates++
            $relTok = ($tok.TrimEnd('/')) -replace '/', '\'
            # 解析順序：本層 → 本行已解析目錄（新→舊） → 祖先層逐級上行至 repo root
            # （子層行文常提及上層檔，如 states 層提 `logic.py`＝sales/logic.py）
            $bases = New-Object System.Collections.Generic.List[string]
            $bases.Add($layerRoot)
            for ($i = $lineDirs.Count - 1; $i -ge 0; $i--) { $bases.Add($lineDirs[$i]) }
            $walk = $layerRoot
            while ($walk -ne $RepoRoot -and $walk.StartsWith($RepoRoot)) {
                $walk = Split-Path $walk -Parent
                $bases.Add($walk)
            }
            if ($bases -notcontains $RepoRoot) { $bases.Add($RepoRoot) }
            $hitPath = $null
            foreach ($b in $bases) {
                $p = Join-Path $b $relTok
                if (Test-Path $p) { $hitPath = $p; break }
            }
            if ($hitPath) {
                if (($tok -match '/$') -or (Test-Path $hitPath -PathType Container)) { $lineDirs.Add($hitPath) }
            } else {
                $errs.Add(("死引用：{0} → {1}" -f $relMap, $tok))
            }
        }
    }
    if ($candidates -eq 0) { $warns.Add(("{0} 沒有任何可驗證的路徑引用（格式異常？）" -f $relMap)) }
}

# 報告（同文重複只報一次）
$errs  = @($errs  | Select-Object -Unique)
$warns = @($warns | Select-Object -Unique)
Write-Output ("code_map 健檢報告（{0}；{1} 份 code_map）" -f $RepoRoot, $maps.Count)
foreach ($e in $errs)  { Write-Output ("  ❌ {0}" -f $e) }
foreach ($w in $warns) { Write-Output ("  ⚠️ {0}" -f $w) }
if ($errs.Count -eq 0 -and $warns.Count -eq 0) { Write-Output '  ✅ 全綠'; exit 0 }
Write-Output ("小計：{0} error / {1} warn" -f $errs.Count, $warns.Count)
if ($errs.Count -gt 0) { exit 2 } else { exit 1 }
