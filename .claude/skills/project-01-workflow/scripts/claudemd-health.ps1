# claudemd-health.ps1 — CLAUDE.md 分層健檢：行數預算 + 死引用（只報告，絕不改檔）
# 機器可判定子集；語意維度（分層分配 / 零重複）由 agent 對照 root CLAUDE.md 維護原則人工判。
# 用法：pwsh -File claudemd-health.ps1 [-RepoRoot <path>]（gitignored 檔不進 worktree——從主 checkout 跑）
# Exit：0=全綠 1=僅警告 2=有錯誤
param(
    [string]$RepoRoot = ''
)
$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
$rootMd = Join-Path $RepoRoot 'CLAUDE.md'
if (-not (Test-Path $rootMd)) {
    Write-Output ("❌ 找不到 root CLAUDE.md：{0}" -f $rootMd)
    exit 2
}

$errs  = New-Object System.Collections.Generic.List[string]
$warns = New-Object System.Collections.Generic.List[string]

# worktrees 排除須比對「相對 RepoRoot」路徑——比對完整路徑時，-RepoRoot 指向 worktree 會把所有檔排光（靜默假全綠）
$files = @(Get-ChildItem $RepoRoot -Recurse -Filter 'CLAUDE.md' -File -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName.Substring($RepoRoot.Length) -notmatch '\\worktrees\\' })

foreach ($f in $files) {
    $rel = $f.FullName.Substring($RepoRoot.Length).TrimStart('\')
    $isRoot = ($f.FullName -eq $rootMd)
    $budget = if ($isRoot) { 100 } else { 60 }
    $lines = @(Get-Content $f.FullName).Count

    # ── 1. 行數預算（root ≤100 / 子層 ≤60；90% 預警）──
    if     ($lines -gt $budget)            { $errs.Add(("{0}：{1} 行，超過 {2} 行預算" -f $rel, $lines, $budget)) }
    elseif ($lines -gt [int]($budget * 0.9)) { $warns.Add(("{0}：{1} 行，已達 {2} 行預算的 90%" -f $rel, $lines, $budget)) }

    # ── 2. Currency 死引用：反引號路徑 token 驗存活（本檔層 → repo root 兩段解析）──
    $layerRoot = Split-Path $f.FullName -Parent
    foreach ($line in (Get-Content $f.FullName)) {
        foreach ($cm in [regex]::Matches($line, '`([^`]+)`')) {
            $tok = $cm.Groups[1].Value.Trim()
            $looksPath = ($tok -match '/') -or ($tok -match '\.(md|py|ps1|js|json|ini|txt|yml|yaml|d6a|html|log|cfg|toml|flag)$')
            if (-not $looksPath) { continue }
            if ($tok -match '^\.[A-Za-z0-9]{1,5}$') { continue }                                  # 純副檔名 mention
            if ($tok -match '[\s<>@—()*]' -or $tok -match '^[~/]' -or $tok -match '^[A-Za-z]:') { continue }
            $relTok = ($tok.TrimEnd('/')) -replace '/', '\'
            $hit = (Test-Path (Join-Path $layerRoot $relTok)) -or (Test-Path (Join-Path $RepoRoot $relTok))
            if (-not $hit) {
                # 散文式 bare-name 提及（如 `Board.py`、`SKILL.md`）→ 葉名遞迴找（防呆不防騙）
                $leaf = Split-Path $relTok -Leaf
                $hit = @(Get-ChildItem $RepoRoot -Recurse -Filter $leaf -ErrorAction SilentlyContinue |
                         Where-Object { $_.FullName.Substring($RepoRoot.Length) -notmatch '\\(\.git|worktrees)\\' } | Select-Object -First 1).Count -gt 0
            }
            if (-not $hit) { $errs.Add(("死引用：{0} → {1}" -f $rel, $tok)) }
        }
    }
}

# 報告（同文重複只報一次）
$errs  = @($errs  | Select-Object -Unique)
$warns = @($warns | Select-Object -Unique)
Write-Output ("CLAUDE.md 分層健檢報告（{0}；{1} 份 CLAUDE.md）" -f $RepoRoot, $files.Count)
foreach ($e in $errs)  { Write-Output ("  ❌ {0}" -f $e) }
foreach ($w in $warns) { Write-Output ("  ⚠️ {0}" -f $w) }
if ($errs.Count -eq 0 -and $warns.Count -eq 0) { Write-Output '  ✅ 全綠'; exit 0 }
Write-Output ("小計：{0} error / {1} warn" -f $errs.Count, $warns.Count)
if ($errs.Count -gt 0) { exit 2 } else { exit 1 }
