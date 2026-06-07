# 逆向採納候選 1-3 落實 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** code_map 死引用健檢 script + grader 兼批 eval + EDD 結果落檔協議（含今天三輪 dogfood 回填）。

**Architecture:** 確定性檢查歸 skill scripts/（落點判準）；grader 增量走 workflow js schema/prompt 三處小改；落檔協議純文件 + 回填。spec：`resources/specs/reverse_adoption_top3_2026-06-07_spec.md`。

**Tech Stack:** PowerShell（UTF-8 BOM）、workflow JS 子集、markdown。

---

### Task 1: worktree——codemap-health.ps1 + workflow js 增量 + reference 文檔

**Files:**
- Create: `.claude/skills/project-01-workflow/scripts/codemap-health.ps1`
- Modify: `.claude/workflows/skill-edd-regression.js`（4 處）
- Modify: `.claude/skills/project-01-workflow/reference/pi-and-structure.md`（+1 小節）
- Modify: `.claude/skills/project-01-workflow/reference/workflow-authoring.md`（+1 行）

- [ ] **Step 1: EnterWorktree（name: reverse-adoption）+ invoke karpathy-guidelines**

- [ ] **Step 2: 寫 codemap-health.ps1（完整內容，存檔須 UTF-8 BOM）**

```powershell
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
$maps = @(Get-ChildItem $RepoRoot -Recurse -Filter 'code_map.md' -File -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -match '\\\.claude\\code_map\.md$' -and $_.FullName -notmatch '\\worktrees\\' })

foreach ($m in $maps) {
    $layerRoot = Split-Path (Split-Path $m.FullName -Parent) -Parent   # <層>/.claude/code_map.md → <層>
    $relMap = $m.FullName.Substring($RepoRoot.Length).TrimStart('\')
    $candidates = 0
    foreach ($line in (Get-Content $m.FullName)) {
        $lineDirs = New-Object System.Collections.Generic.List[string]   # 本行已解析成目錄的 token（新→舊查）
        foreach ($cm in [regex]::Matches($line, '`([^`]+)`')) {
            $tok = $cm.Groups[1].Value.Trim()
            # 只查「像路徑」的：結尾 / 、含 / 、或有副檔名
            $looksPath = ($tok -match '/$') -or ($tok -match '/') -or ($tok -match '\.[A-Za-z0-9]{1,5}$')
            if (-not $looksPath) { continue }
            # 排除：含空白 / 角括號 / @ / 破折號 / 括號、~ 或 / 開頭（非 repo 路徑）、磁碟機開頭
            if ($tok -match '[\s<>@—()]' -or $tok -match '^[~/]' -or $tok -match '^[A-Za-z]:') { continue }
            $candidates++
            $relTok = ($tok.TrimEnd('/')) -replace '/', '\'
            # 三段解析：本層 → 本行已解析目錄（新→舊） → repo root（Test-Path 支援萬用字元）
            $bases = @($layerRoot) + @($lineDirs | Sort-Object -Descending { $lineDirs.IndexOf($_) }) + @($RepoRoot)
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
```

- [ ] **Step 3: 驗 BOM + 靜態解析**（同 memory-health 慣例指令）Expected: `BOM: True`、`ParseErrors: 0`

- [ ] **Step 4: fixture 三組**

```powershell
# ① 死引用 + 巢狀 + 跨層 + 萬用字元
$fx = "$env:CLAUDE_JOB_DIR\tmp\cmfix"; New-Item -ItemType Directory -Force "$fx\.claude","$fx\sub\.claude","$fx\sub\real","$fx\.claude\workflows" | Out-Null
'x' | Set-Content "$fx\real.md"; 'x' | Set-Content "$fx\sub\real\a.py"; 'x' | Set-Content "$fx\.claude\workflows\w.js"; 'x' | Set-Content "$fx\.claude\settings.local.json"
@'
- `real.md` — 存在。
- `sub/` — 子層：`real/` 內含 `a.py`。
- `.claude/` — 配置：`workflows/`、`settings*.json`。
- `ghost.md` — 不存在（應報死引用）。
'@ | Set-Content "$fx\.claude\code_map.md" -Encoding utf8
@'
- `real/` — 真目錄。
- `.claude/workflows/w.js` — 跨層引用（解析到 repo root）。
- `missing/` — 不存在（應報死引用）。
'@ | Set-Content "$fx\sub\.claude\code_map.md" -Encoding utf8
pwsh -File .claude/skills/project-01-workflow/scripts/codemap-health.ps1 -RepoRoot $fx; "exit=$LASTEXITCODE"
```

Expected: ❌ 恰 2 條（`ghost.md`、`missing/`）；`a.py`（行內巢狀）、`.claude/workflows/w.js`（跨層）、`settings*.json`（萬用）皆不誤報；`exit=2`

```powershell
# ② 全綠（把 ① 的兩條死引用行刪掉重跑）→ Expected: ✅ 全綠 exit=0
# ③ 格式異常（code_map 無任何路徑 token）→ Expected: ⚠️ exit=1
```

（②③ 各建最小 fixture 依上模式，plan 不重複碼。）

- [ ] **Step 5: 對真實 repo 跑（主 checkout 為 RepoRoot）**

```powershell
pwsh -File .claude/skills/project-01-workflow/scripts/codemap-health.ps1 -RepoRoot 'C:\Users\LIN HONG\Desktop\Project_01'; "exit=$LASTEXITCODE"
```

Expected: 全綠或抓到真死引用。抓到 → 逐條人工確認屬實後修對應 code_map（本層 code_map 在 worktree 一併修；resources 層的留到 Task 2 main 修），復跑至全綠。**啟發式誤報** → 修 script 再跑（誤報不可留）。

- [ ] **Step 6: workflow js 四處增量**

①第 11 行註解 `resources/edd/` → `resources/evals/`。②`GRADE_SCHEMA` required 改 `['scenario_id', 'asserts', 'pass_count', 'total', 'weak_asserts']`，properties 加：

```js
    weak_asserts: {
      type: 'array',
      items: { type: 'string' },
      description: '非鑑別性 assertion：即使導航錯也會 pass（如只查「有 Read X」而不查判斷正確）。沒有就回空陣列',
    },
```

③`gradePrompt` 末段（「逐條判 pass/fail…」之後）加：

```
另以評分員身分批評題目本身：哪些 assertion 即使 navigator 導航錯了也會 pass（非鑑別性、查存在不查正確）？列入 weak_asserts，沒有就回空陣列——弱 assertion 上的 pass 比沒有更糟（製造假信心）。
```

④`verdictPrompt` 末段加：

```
若各場景 graders 回報了非空 weak_asserts，在 summary 末尾彙整列出（題庫自我改進訊號）；全空則不提。
```

- [ ] **Step 7: reference 兩處**——`pi-and-structure.md` 在 code_map 維護段落附近加小節：

```markdown
## code_map 健檢（死引用）

`pwsh -File .claude/skills/project-01-workflow/scripts/codemap-health.ps1`——掃各層 code_map 的路徑引用逐一驗存活（三段解析：本層→同行目錄→repo root；只報告不改檔；exit 0/1/2）。gitignored 檔不進 worktree，一律從主 checkout 跑。觸發：結構變動收尾時順手跑、或使用者喊「code_map 健檢」。死引用 = 該層 code_map 漏更新——修 code_map 而非刪引用。
```

`workflow-authoring.md` 本專案資產段加一行：

```markdown
- **跑完每輪 EDD → 結果落檔 `resources/evals/iteration-N/<scope>-result.json`**（schema 見 evals/README「結果落檔」段）。
```

- [ ] **Step 8: commit（明列四檔）→ ExitWorktree(keep) → 主 checkout merge（ff 或 cherry-pick）→ push → 清 worktree/branch**

```bash
git add .claude/skills/project-01-workflow/scripts/codemap-health.ps1 .claude/workflows/skill-edd-regression.js .claude/skills/project-01-workflow/reference/pi-and-structure.md .claude/skills/project-01-workflow/reference/workflow-authoring.md
git commit -m "feat(skill,workflows): codemap dead-ref health check + grader eval-critique + result-archive pointers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: resources（main 直接做）——落檔協議 + iteration-5 回填

**Files:**
- Modify: `resources/evals/README.md`（+落檔段）
- Create: `resources/evals/iteration-5/{full-regression-result.json, s3-revalidation-result.json, s10-graduation-result.json, final-consolidated.md}`
- Modify: `resources/research/skillcreator_claudemd_reverse_comparison_2026-06-07.md`（§4 前三條 status → adopted + 落實行）

- [ ] **Step 1: README 加段**

```markdown
## 結果落檔（每跑必落）

跑完任一輪 EDD（全量或部分），主 agent 收到 workflow 回傳後**必須**落檔 `iteration-N/`（N 接續最大值；同一工作弧多次 run 共用同一 N）：

- 檔名：`<scope>-result.json`（例：full-regression / s10-graduation / s3-revalidation）
- schema：`{ "date": "YYYY-MM-DD", "run_id": "wf_…", "scope": "…", "scenario_ids": [...], "verdict": <原樣>, "graded": <原樣> }`
- 大局結論寫/併 `final-consolidated.md`（沿 iteration-2/3/4 慣例）

Why：跨輪聚合（每 assertion 跨輪 pass 率、抓非鑑別 assertion）的資料基礎——不落檔趨勢不可查。
```

- [ ] **Step 2: 回填 iteration-5**——從本 session task output 抽 `result` 欄包上 metadata 寫入：

```powershell
$tmp = "C:\Users\LINHON~1\AppData\Local\Temp\claude\C--Users-LIN-HONG-Desktop-Project-01\3bfdb69d-c1ca-4bc0-a218-c46aff93e18f\tasks"
# 三份：wetisvmvm(全量) / waxybjl6p(s3 復驗) / wnhakmj1g(s10)——各自讀 .output、ConvertFrom-Json 取 .result，
# 包 {date,run_id,scope,scenario_ids,verdict,graded} 後 ConvertTo-Json -Depth 12 寫 iteration-5/<scope>-result.json
```

`final-consolidated.md`：記「全量 56/56（修復後）」弧——14 場景首跑 55/56 → 跨桶路由修復 `52ec1f4` → s3 復驗 6/6 → s10 sonnet graduation 3/3 → 題庫 10 場景全綠。

- [ ] **Step 3: 比對筆記 §4 候選 1-3 status 改 adopted + 落實行（commit SHA 待 Task 1 完成後填）**

- [ ] **Step 4: commit（明列檔名）+ push**

### Task 3: graduation smoke——驗 weak_asserts

- [ ] **Step 1: Workflow 具名觸發單場景（用 s2，最便宜）**，驗回傳 graded[0] 含合法 `weak_asserts` 欄（s2 的 assert 偏行為判斷，預期 weak_asserts 可能非空——「git add 明列檔名」類 assert 是行為性的，存在性類才弱；以實際回報為準）
- [ ] **Step 2: 依新協議落檔 `iteration-5/weak-asserts-smoke-result.json`（首次 dogfood 新協議）**
- [ ] **Step 3: 收尾回報**（四項格式）

---

## Self-Review 記錄

- spec 元件 1↔Task 1 Step 2-5 + Step 7 前半、2↔Step 6、3↔Task 2 + Task 3 Step 2 ✅
- 驗收 1↔T1S4-5、2↔T3、3↔T2 ✅
- 無佔位（②③ fixture 標明「依上模式」屬重複略寫，模式已完整給出）✅
- 名稱一致：weak_asserts / codemap-health.ps1 / iteration-5 / -RepoRoot 全文一致 ✅
