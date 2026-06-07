# aggregate-edd.ps1 — EDD 跨輪聚合：每 (scenario, assertion) 跨輪 pass 率 + weak_asserts 頻次（純分析，exit 恆 0）
# 讀 resources/evals/iteration-*/ 下符合新 schema 的 *-result.json（缺 verdict/graded/scenario_ids 的舊檔跳過）。
# 用法：pwsh -File aggregate-edd.ps1 [-EvalsDir <path>]
param(
    [string]$EvalsDir = 'resources/evals'
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $EvalsDir)) {
    Write-Output ("找不到 evals 目錄：{0}" -f $EvalsDir)
    exit 0
}

$runs = New-Object System.Collections.Generic.List[object]
$skipped = 0
foreach ($f in (Get-ChildItem (Join-Path $EvalsDir 'iteration-*\*.json') -File -ErrorAction SilentlyContinue)) {
    try { $j = Get-Content $f.FullName -Raw | ConvertFrom-Json } catch { $skipped++; continue }
    if (-not ($j.PSObject.Properties.Match('verdict').Count -and $j.PSObject.Properties.Match('graded').Count -and $j.PSObject.Properties.Match('scenario_ids').Count)) { $skipped++; continue }
    $runs.Add([pscustomobject]@{ File = $f.Directory.Name + '/' + $f.Name; Date = $j.date; Scope = $j.scope; Graded = $j.graded })
}

Write-Output ("EDD 跨輪聚合（{0}；{1} 份新 schema run，跳過 {2} 份舊/非 schema 檔）" -f $EvalsDir, $runs.Count, $skipped)
if ($runs.Count -eq 0) { exit 0 }

Write-Output ''
Write-Output '== run 一覽 =='
foreach ($r in $runs) { Write-Output ("  {0}  {1}  {2}" -f $r.Date, $r.Scope, $r.File) }

# 聚合：key = scenario_id ||| assertion
$agg  = @{}
$weak = @{}
foreach ($r in $runs) {
    foreach ($g in $r.Graded) {
        foreach ($a in $g.asserts) {
            $key = '{0} ||| {1}' -f $g.scenario_id, $a.assertion
            if (-not $agg.ContainsKey($key)) { $agg[$key] = @{ pass = 0; total = 0 } }
            $agg[$key].total++
            if ($a.pass) { $agg[$key].pass++ }
        }
        if ($g.PSObject.Properties.Match('weak_asserts').Count) {
            foreach ($w in $g.weak_asserts) {
                $wk = '{0} ||| {1}' -f $g.scenario_id, $w
                if (-not $weak.ContainsKey($wk)) { $weak[$wk] = 0 }
                $weak[$wk]++
            }
        }
    }
}

Write-Output ''
Write-Output '== 跨輪 pass 率 <100% 的 assertion（flaky / 退化訊號優先） =='
$below = @($agg.GetEnumerator() | Where-Object { $_.Value.pass -lt $_.Value.total } | Sort-Object { $_.Value.pass / $_.Value.total })
if ($below.Count -eq 0) { Write-Output '  （無——全部 assertion 跨輪 100%）' }
foreach ($e in $below) {
    $parts = $e.Key -split ' \|\|\| ', 2
    Write-Output ("  {0}/{1}  [{2}] {3}" -f $e.Value.pass, $e.Value.total, $parts[0], $parts[1])
}

Write-Output ''
Write-Output ("== weak_asserts 頻次（{0} 條） ==" -f $weak.Count)
foreach ($e in ($weak.GetEnumerator() | Sort-Object Value -Descending)) {
    $parts = $e.Key -split ' \|\|\| ', 2
    $short = if ($parts[1].Length -gt 80) { $parts[1].Substring(0, 80) + '…' } else { $parts[1] }
    Write-Output ("  ×{0}  [{1}] {2}" -f $e.Value, $parts[0], $short)
}

exit 0
