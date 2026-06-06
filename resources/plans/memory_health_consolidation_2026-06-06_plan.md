# memory 健檢 + 整併迴圈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 auto-memory 建立手動觸發的維護迴圈：確定性健檢 script + skill reference 流程 + 獨立定奪帳本。

**Architecture:** PowerShell script 做機器可判定檢查（只報告不改檔）；skill reference 定義主 agent 的整併判斷六步流程；帳本在 gitignored 的 `resources/reflections/`。spec：`resources/specs/memory_health_consolidation_2026-06-06_spec.md`。

**Tech Stack:** PowerShell（UTF-8 BOM）、markdown（skill reference）。

**約束：** `.claude/` 改動走 worktree 5 階段；寫碼前 invoke karpathy-guidelines；script 對真實 memory 只讀不寫。

---

### Task 1: 進 worktree + 寫健檢 script

**Files:**
- Create: `.claude/skills/project-01-workflow/scripts/memory-health.ps1`

- [ ] **Step 1: EnterWorktree（name: memory-health）**

- [ ] **Step 2: invoke karpathy-guidelines（本輪實作開始）**

- [ ] **Step 3: 寫 script（完整內容如下，存檔須 UTF-8 with BOM）**

```powershell
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
        if (-not $hit -and $rel -notmatch '\\') {
            # 純檔名 → repo 內遞迴找（排除 .git）
            $hit = @(Get-ChildItem $repoRoot -Recurse -Filter $rel -File -ErrorAction SilentlyContinue |
                     Where-Object { $_.FullName -notmatch '\\\.git\\' } | Select-Object -First 1).Count -gt 0
        }
        if (-not $hit) { $warns.Add(("引用的檔案在 repo 找不到（可能已移動/改名）：{0} in {1}" -f $cand, $f.Name)) }
    }
}

# ── 報告 ──
Write-Output ("memory 健檢報告（{0}；{1} 個記憶檔）" -f $MemoryDir, $entryFiles.Count)
foreach ($e in $errs)  { Write-Output ("  ❌ {0}" -f $e) }
foreach ($w in $warns) { Write-Output ("  ⚠️ {0}" -f $w) }
if ($errs.Count -eq 0 -and $warns.Count -eq 0) { Write-Output '  ✅ 全綠'; exit 0 }
Write-Output ("小計：{0} error / {1} warn" -f $errs.Count, $warns.Count)
if ($errs.Count -gt 0) { exit 2 } else { exit 1 }
```

- [ ] **Step 4: 驗 BOM + 靜態解析**

```powershell
$p = '.claude/skills/project-01-workflow/scripts/memory-health.ps1'
$b = [System.IO.File]::ReadAllBytes($p)[0..2]; ('BOM: ' + (($b[0] -eq 0xEF) -and ($b[1] -eq 0xBB) -and ($b[2] -eq 0xBF)))
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $p), [ref]$null, [ref]$err); ('ParseErrors: ' + @($err).Count)
```

Expected: `BOM: True`、`ParseErrors: 0`

### Task 2: 基線實測（真實 memory，只讀安全）

- [ ] **Step 1: 顯式 -MemoryDir 跑真目錄**

```powershell
pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1 -MemoryDir "$env:USERPROFILE\.claude\projects\C--Users-LIN-HONG-Desktop-Project-01\memory"; "exit=$LASTEXITCODE"
```

Expected: 報告列出 6 個記憶檔狀態；現有檔 name kebab vs 檔名底線**不得誤報**（`-`/`_` 等價已處理）。若抓到真問題照實記下，留給 Task 6 e2e 處理，不在此修。

### Task 3: 壞型注入測試（fixture 三組）

- [ ] **Step 1: 建 error fixture（孤兒檔 + 死索引連結 + 壞 frontmatter + 缺 type）**

```powershell
$fx = "$env:CLAUDE_JOB_DIR\tmp\memfix-err"; New-Item -ItemType Directory -Force $fx | Out-Null
@'
- [Good](good.md) — 正常條目
- [Dead](dead_link.md) — 指向不存在的檔
'@ | Set-Content "$fx\MEMORY.md" -Encoding utf8
@'
---
name: good
description: 正常檔
metadata:
  type: user
---
內文。
'@ | Set-Content "$fx\good.md" -Encoding utf8
@'
---
name: orphan
description: 不在索引的孤兒
metadata:
  type: feedback
---
內文。
'@ | Set-Content "$fx\orphan.md" -Encoding utf8
'沒有 frontmatter 的檔。' | Set-Content "$fx\bad_fm.md" -Encoding utf8
@'
---
name: no-type
description: metadata 缺 type
metadata:
  foo: bar
---
內文。
'@ | Set-Content "$fx\no_type.md" -Encoding utf8
pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1 -MemoryDir $fx; "exit=$LASTEXITCODE"
```

Expected: ❌ 含「索引指向不存在的檔：dead_link.md」「孤兒記憶檔：orphan.md」「缺 frontmatter：bad_fm.md」「缺合法 metadata.type：no_type.md」（bad_fm/no_type 也會是孤兒——預期內）；`exit=2`

- [ ] **Step 2: 建 warn-only fixture（死 wiki-link + 死路徑引用 + name/檔名不一致）**

```powershell
$fx = "$env:CLAUDE_JOB_DIR\tmp\memfix-warn"; New-Item -ItemType Directory -Force $fx | Out-Null
@'
- [W](w_entry.md) — 警告測試
'@ | Set-Content "$fx\MEMORY.md" -Encoding utf8
@'
---
name: w-entry-other
description: 警告齊全測試
metadata:
  type: project
---
參考 [[ghost-memory]] 與 `no_such_file_xyz.py`，另外 `pi@host:/x.py` 與 `C:\abs\x.py` 應被跳過。
'@ | Set-Content "$fx\w_entry.md" -Encoding utf8
pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1 -MemoryDir $fx; "exit=$LASTEXITCODE"
```

Expected: ⚠️ 三條——wiki-link `[[ghost-memory]]`、引用 `no_such_file_xyz.py` 找不到、name 不一致（w-entry-other vs w_entry.md）；**無** pi@host / C:\ 誤報；`exit=1`

- [ ] **Step 3: 建全綠 fixture**

```powershell
$fx = "$env:CLAUDE_JOB_DIR\tmp\memfix-ok"; New-Item -ItemType Directory -Force $fx | Out-Null
@'
- [Clean](clean.md) — 全綠
'@ | Set-Content "$fx\MEMORY.md" -Encoding utf8
@'
---
name: clean
description: 全綠檔
metadata:
  type: reference
---
內文不含任何引用。
'@ | Set-Content "$fx\clean.md" -Encoding utf8
pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1 -MemoryDir $fx; "exit=$LASTEXITCODE"
```

Expected: `✅ 全綠`；`exit=0`

- [ ] **Step 4: 超門檻測試（>200 行 MEMORY.md）**

```powershell
$fx = "$env:CLAUDE_JOB_DIR\tmp\memfix-big"; New-Item -ItemType Directory -Force $fx | Out-Null
$lines = @(1..210 | ForEach-Object { "- 第 $_ 行" }); $lines | Set-Content "$fx\MEMORY.md" -Encoding utf8
pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1 -MemoryDir $fx; "exit=$LASTEXITCODE"
```

Expected: ❌「210 行，超過 200 行載入上限」；`exit=2`

### Task 4: skill reference + 路由表

**Files:**
- Create: `.claude/skills/project-01-workflow/reference/memory-management.md`
- Modify: `.claude/skills/project-01-workflow/SKILL.md`（路由表加一行）

- [ ] **Step 1: 寫 reference（完整內容如下）**

```markdown
# memory 健檢與整併（agent 記憶管理）

> 🎯 **何時讀本檔**：使用者要求「memory 健檢 / 記憶整併 / 記憶維護」，或健檢 script 報異常要跟進時。

auto-memory（`~/.claude/projects/<專案slug>/memory/`）的手動維護迴圈：確定性健檢（script）→ agent 整併判斷 → 對話內人定奪 → 帳本記錄。**提議經使用者批准才動手**；唯機械性修復（索引補行/刪行、frontmatter 補欄）呈報後可直接修。

## 流程（六步）

1. **跑健檢 script**（零 token，只讀不寫）：
   `pwsh -File .claude/skills/project-01-workflow/scripts/memory-health.ps1`
   exit 0=全綠 / 1=僅警告 / 2=有錯誤。worktree 內 cwd 推導 slug 會錯，必須 `-MemoryDir` 顯式指定真實 memory 目錄。
2. **機械修復**：error 級的索引/frontmatter 結構問題，呈報後直接修；內容性問題（引用失效、過期嫌疑）進第 4 步判斷。
3. **讀帳本疫苗**：`resources/reflections/memory_ledger.md` 的 rejected 條目——已否決的提議不重提。
4. **整併四問**（逐條記憶）：
   - **還真嗎**——指名的檔案/行為/flag 實際驗證（Read/Glob 查證，不憑記憶宣稱）
   - **該升層嗎**——選層判準 hook > root CLAUDE.md > skill reference > NOTES > memory（標準：犯錯前一刻 agent 會看到哪裡）；memory 該只剩「使用者個人特質/授權/節奏」這類無處可歸的事實
   - **重複/可合併嗎**——條目間 overlap
   - **該刪嗎**——已失效或已被其他層覆蓋
5. **對話內人定奪**：每條提議用「**Why:** 一行 + diff」格式呈現，逐條批准才執行。
6. **記帳**：所有定奪寫進帳本（格式見帳本檔頭）；adopted 落實後加「落實:」行，rejected 留作疫苗。

## 邊界

- 健檢 script 只報告、絕不改檔。
- 升層落實後，原 memory 條目刪除或改成 pointer——不留雙權威。
- 記憶不得寫入敏感資訊（密碼 / 金鑰 / PII）。
```

- [ ] **Step 2: SKILL.md 路由表加一行**（插在「繁簡對照 / 環境 quirk」那行之前）

```markdown
| memory 健檢 / 記憶整併 / 記憶維護 | `memory-management.md` |
```

- [ ] **Step 3: 檢查 root `.claude/code_map.md` 是否逐檔列出 skill 的 reference/scripts**——若有逐檔索引則補 `memory-management.md` + `memory-health.ps1` 兩行；只有目錄級描述則不動。

### Task 5: worktree 收尾（5 階段）

- [ ] **Step 1: `git status` 確認只有三檔變動**（memory-health.ps1 / memory-management.md / SKILL.md，外加可能的 code_map.md）
- [ ] **Step 2: 明確列檔名 `git add`（禁 -A）+ commit**

```bash
git add .claude/skills/project-01-workflow/scripts/memory-health.ps1 .claude/skills/project-01-workflow/reference/memory-management.md .claude/skills/project-01-workflow/SKILL.md
git commit -m "feat(skill): memory health check script + consolidation flow reference

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: 依 reference/worktree.md 收尾**（ExitWorktree → 主 checkout merge → `git branch --contains` 驗 commit → push；Pi sync 由 Stop hook 自動）

### Task 6: 帳本 + e2e 整併實跑（主 checkout）

**Files:**
- Create: `resources/reflections/memory_ledger.md`（gitignored，免 commit）

- [ ] **Step 1: 建帳本**

```markdown
# memory 健檢/整併定奪帳本（append-only；rejected 留作疫苗防重提；adopted 而無落實行 = 欠帳）

<!-- 條目格式：
## YYYY-MM-DD slug｜類型(升層/合併/刪除/修正)
提議內容一兩句（為何 + 動哪個記憶檔）。
status: adopted | rejected
落實: <變更描述（升層需含目的地與 commit）>
-->
```

- [ ] **Step 2: e2e——對真實 memory 跑完整六步流程**：script（這次在主 checkout，預設推導即可）→ 修機械問題（若有）→ 讀帳本（首輪為空）→ 整併四問逐條過 5 個記憶 → 提議呈對話 → 使用者定奪 → 記帳。

Expected: 至少產出一輪真提議（哪怕全部是「維持現狀」也要呈報判斷依據）；定奪結果落帳本。

- [ ] **Step 3: 收尾回報**：改了什麼 / 無 pineedtodo（純 Windows 側）/ Pi sync 狀態 / 後續行動。

---

## Self-Review 記錄

- spec 六項檢查 ↔ script 段落一一對應（門檻/索引→檔/檔→索引/frontmatter/wiki-link/路徑引用）✅
- spec 驗收 1↔Task 2、2↔Task 3、3↔Task 6 ✅
- 無 TBD/佔位；所有步驟含完整代碼與預期輸出 ✅
- 型別一致：`-MemoryDir` 參數名、exit code 約定（0/1/2）全文一致 ✅
