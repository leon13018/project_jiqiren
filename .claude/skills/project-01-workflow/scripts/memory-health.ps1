# memory-health.ps1 — auto-memory 確定性健檢（只報告，絕不改檔）
# 用法：pwsh -File memory-health.ps1 [-MemoryDir <path>]
#   預設由 cwd 推導專案 slug；worktree 內推導會錯，必須顯式給 -MemoryDir。
# Exit：0=全綠 1=僅警告 2=有錯誤
param(
    [string]$MemoryDir = ''
)
$ErrorActionPreference = 'Stop'

if (-not $MemoryDir) {
    # Claude Code 專案 slug 規則：路徑非英數字元一律轉 '-'
    $slug = (Get-Location).Path -replace '[^A-Za-z0-9]', '-'
    $MemoryDir = Join-Path $env:USERPROFILE ".claude\projects\$slug\memory"
}
if (-not (Test-Path $MemoryDir)) {
    Write-Output ("❌ memory 目錄不存在：{0}（worktree 內請用 -MemoryDir 指定）" -f $MemoryDir)
    exit 2
}

$errs  = New-Object System.Collections.Generic.List[string]
$warns = New-Object System.Collections.Generic.List[string]

$indexPath  = Join-Path $MemoryDir 'MEMORY.md'
$entryFiles = @(Get-ChildItem $MemoryDir -Filter '*.md' -File | Where-Object { $_.Name -ne 'MEMORY.md' })

# ── 1. MEMORY.md 存在 + 載入門檻（前 200 行 / 25KB 先到為準；超過的部分 session 看不到）──
$indexLinks = @()
if (-not (Test-Path $indexPath)) {
    $errs.Add('MEMORY.md 不存在')
} else {
    $indexRaw  = Get-Content $indexPath -Raw
    $lineCount = @(Get-Content $indexPath).Count
    $byteCount = (Get-Item $indexPath).Length
    if     ($lineCount -gt 200) { $errs.Add(("MEMORY.md {0} 行，超過 200 行載入上限" -f $lineCount)) }
    elseif ($lineCount -gt 160) { $warns.Add(("MEMORY.md {0} 行，已達 200 行上限的 80%" -f $lineCount)) }
    if     ($byteCount -gt 25KB) { $errs.Add(("MEMORY.md {0} bytes，超過 25KB 載入上限" -f $byteCount)) }
    elseif ($byteCount -gt 20KB) { $warns.Add(("MEMORY.md {0} bytes，已達 25KB 上限的 80%" -f $byteCount)) }

    # ── 2. 索引 → 檔 ──
    $indexLinks = @([regex]::Matches($indexRaw, '\[[^\]]*\]\(([^)]+\.md)\)') | ForEach-Object { $_.Groups[1].Value })
    foreach ($link in $indexLinks) {
        if (-not (Test-Path (Join-Path $MemoryDir $link))) {
            $errs.Add(("索引指向不存在的檔：{0}" -f $link))
        }
    }
}

# ── 3. 檔 → 索引（孤兒記憶檔）──
foreach ($f in $entryFiles) {
    if ($indexLinks -notcontains $f.Name) {
        $errs.Add(("孤兒記憶檔（MEMORY.md 索引沒有它）：{0}" -f $f.Name))
    }
}

# ── 4. frontmatter：name / description / metadata.type；name 與檔名一致（- 與 _ 視為等價）──
$knownNames = New-Object System.Collections.Generic.List[string]
foreach ($f in $entryFiles) { $knownNames.Add(($f.BaseName -replace '_', '-')) }
foreach ($f in $entryFiles) {
    $raw = Get-Content $f.FullName -Raw
    $fmMatch = [regex]::Match($raw, '(?s)^---\r?\n(.*?)\r?\n---')
    if (-not $fmMatch.Success) { $errs.Add(("缺 frontmatter：{0}" -f $f.Name)); continue }
    $fm = $fmMatch.Groups[1].Value
    $nameMatch = [regex]::Match($fm, '(?m)^name:\s*(\S+)\s*$')
    if (-not $nameMatch.Success) {
        $errs.Add(("frontmatter 缺 name：{0}" -f $f.Name))
    } else {
        $name = $nameMatch.Groups[1].Value
        $knownNames.Add(($name -replace '_', '-'))
        if (($name -replace '_', '-') -ne ($f.BaseName -replace '_', '-')) {
            $warns.Add(("name 與檔名不一致：name={0}，檔={1}" -f $name, $f.Name))
        }
    }
    if ($fm -notmatch '(?m)^description:\s*\S') { $errs.Add(("frontmatter 缺 description：{0}" -f $f.Name)) }
    if ($fm -notmatch '(?m)^\s+type:\s*(user|feedback|project|reference)\s*$') {
        $errs.Add(("frontmatter 缺合法 metadata.type（user|feedback|project|reference）：{0}" -f $f.Name))
    }
}

# ── 5+6. 內文：wiki-link 解析（warn）+ repo 檔案引用存活（warn；啟發式防呆不防騙）──
$repoRoot = (Get-Location).Path
foreach ($f in $entryFiles) {
    $body = (Get-Content $f.FullName -Raw) -replace '(?s)^---\r?\n.*?\r?\n---', ''

    foreach ($wm in [regex]::Matches($body, '\[\[([^\]\r\n]+)\]\]')) {
        $target = $wm.Groups[1].Value -replace '_', '-'
        if ($knownNames -notcontains $target) {
            $warns.Add(("wiki-link 未解析（允許先掛後補）：[[{0}]] in {1}" -f $wm.Groups[1].Value, $f.Name))
        }
    }

    foreach ($cm in [regex]::Matches($body, '`([^`\r\n]+)`')) {
        $cand = $cm.Groups[1].Value.Trim()
        if ($cand -notmatch '\.(ps1|py|md|json|js|txt|yml|yaml)$') { continue }   # 只看像 repo 檔案的
        if ($cand -match '[\s*<>@:]' -or $cand -match '^[/~]') { continue }       # 排除 URL/佔位/主機/絕對路徑
        $rel = $cand -replace '/', '\'
        $hit = Test-Path (Join-Path $repoRoot $rel)
        if (-not $hit) {
            # 相對路徑可能不是相對 repo root（如 skill 內部相對連結）→ 退而以葉檔名遞迴找（排除 .git）
            $leaf = Split-Path $rel -Leaf
            $hit = @(Get-ChildItem $repoRoot -Recurse -Filter $leaf -File -ErrorAction SilentlyContinue |
                     Where-Object { $_.FullName -notmatch '\\\.git\\' } | Select-Object -First 1).Count -gt 0
        }
        if (-not $hit) { $warns.Add(("引用的檔案在 repo 找不到（可能已移動/改名）：{0} in {1}" -f $cand, $f.Name)) }
    }
}

# ── 報告（同文重複只報一次）──
$errs  = @($errs  | Select-Object -Unique)
$warns = @($warns | Select-Object -Unique)
Write-Output ("memory 健檢報告（{0}；{1} 個記憶檔）" -f $MemoryDir, $entryFiles.Count)
foreach ($e in $errs)  { Write-Output ("  ❌ {0}" -f $e) }
foreach ($w in $warns) { Write-Output ("  ⚠️ {0}" -f $w) }
if ($errs.Count -eq 0 -and $warns.Count -eq 0) { Write-Output '  ✅ 全綠'; exit 0 }
Write-Output ("小計：{0} error / {1} warn" -f $errs.Count, $warns.Count)
if ($errs.Count -gt 0) { exit 2 } else { exit 1 }
