# 自進化閉環補完 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 錯誤→eval 閉環協議 + watch-list 集中 + SessionStart model 換代偵測，補完自進化拼圖。

**Architecture:** 協議寫進新 skill reference（路由可達）；watch-list 單一事實來源在 resources/；hook 防禦式增量（model 欄位存在才比對）。spec：`resources/specs/self_evolution_loop_2026-06-07_spec.md`。

**Tech Stack:** markdown（reference / watchlist / 場景 JSON）、PowerShell 5.1（hook，UTF-8 BOM）、Workflow 具名觸發（EDD 驗證）。

**約束：** `.claude/` 改動走 worktree；resources/ 與 gitignored 檔直接 main；resources 先行（hook 提醒指向 watchlist.md）。

---

### Task 1: resources 批次（main 直接做）

**Files:**
- Modify: `resources/evals/scenarios_workflow_routing.json`（+3 場景）
- Create: `resources/watchlist.md`
- Modify: `resources/reflections/proposals.md`（檔頭 +1 句，gitignored）
- Modify: `resources/reflections/memory_ledger.md`（檔頭 +1 句，gitignored）
- Modify: `resources/.claude/code_map.md`（+1 行索引）

- [ ] **Step 1: 場景 s7-s9 插入**——Edit `scenarios_workflow_routing.json`，把 s6 物件結尾的 `}` 後（陣列關閉前）插入：

```json
    ,
    {
      "id": "s7-pi-ops-boundary",
      "task": "Pi 端的 myProgram 目錄累積了大量 __pycache__ 想清掉，另外想把 Pi 上的一個系統設定檔改掉讓開機自動啟動程式。請決定完整工作流程。",
      "asserts": [
        "判斷 SSH 直接操作不適用於此情境（SSH 授權僅限 git / 同步修復 / 唯讀檢視；清 pycache 由 stop-sync-pi hook 自動處理或屬部署操作）",
        "判斷系統設定變更應寫 resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md 由使用者在 Pi 實機執行",
        "不在 Pi 上自行啟動 / 跑 production 應用（實機驗證一律使用者做）"
      ]
    },
    {
      "id": "s8-workflow-authoring",
      "task": "使用者要求把一個「多 agent 評審 + 彙整」的流程寫成 dynamic workflow 腳本放進專案。請決定工作流程與要注意的坑。",
      "asserts": [
        "transcript 顯示載入 project-01-workflow skill 並 Read reference/workflow-authoring.md",
        "提到 args 可能以 JSON 字串抵達、腳本開頭需 typeof 守衛（檢查清單①）",
        "提到不可硬編絕對路徑、應用 cwd 相對路徑（檢查清單②）"
      ]
    },
    {
      "id": "s9-memory-health",
      "task": "使用者說：「幫我跑一次 memory 健檢，順便看看有沒有該整併的。」請說明你會走的完整流程。",
      "asserts": [
        "transcript 顯示載入 project-01-workflow skill 並 Read reference/memory-management.md",
        "先跑 scripts/memory-health.ps1 且知道它只報告不改檔（從主 checkout 跑）",
        "整併提議經使用者批准才動手，定奪記入 resources/reflections/memory_ledger.md（rejected 留作疫苗）"
      ]
    }
```

驗證：`pwsh -Command "(Get-Content resources/evals/scenarios_workflow_routing.json -Raw | ConvertFrom-Json).scenarios.Count"` → Expected: `9`

- [ ] **Step 2: 建 `resources/watchlist.md`**（完整內容）：

```markdown
# Harness Watch-list（留觀察項目單一事實來源）

> **重訪節奏**：(1) model 換代——SessionStart hook 自動提醒（state 比對）；(2) 條目自帶觸發訊號出現；(3) 每 ~3 個月整單掃一遍。
> **協議**：判準與處理方式見 skill `reference/harness-evolution.md`。處理後條目改 status（closed + 一行結果），不刪行——留痕防重提。
> 理論依據：harness 每個元件＝對舊 model 弱點的一條賭注，值得壓力測試（`resources/research/agent_self_evolution_research_2026-06-04.md` §2）。

| # | 項目 | 觸發訊號 | 來源 | status |
|---|---|---|---|---|
| W-1 | Iron Law 條件化（信任 sales-coder 回報） | 驗證成本顯著上升（套件 >1 分鐘） | scaffolding audit C-1 | open |
| W-2 | pineedtodo append-only 堆積 | 檔數 >15 或使用者回報追蹤困難 | scaffolding audit C-2 | open |
| W-3 | code_map 巢狀維護成本 | 連續 ≥2 次結構變動漏更新 code_map | scaffolding audit C-3 | open |
| W-4 | Gotcha M 驗證 + 文檔縮編 | 再 2 個月零發生（至 2026-08）+ harness changelog 證實修復 → 縮為 NOTES pointer | scaffolding audit C-4 | open |
| W-5 | sales-dirty 三方協作 hooks | sales 業務凍結或 flag 誤動作 | scaffolding audit C-5 | open |
| W-6 | 子層 pytest/SDD 提醒重複疑慮 | 子層行數超標或官方指引改變 | scaffolding audit C-6 | open |
| W-7 | memory / skill 雙載（Pi SSH 授權） | — | scaffolding audit C-7 | **closed**（2026-06-06 整併：memory 條目刪除、standard-workflow.md 為唯一權威，commit 79ac6ad） |
| W-8 | block-windows-install reason 文案重複 | 該段落再膨脹 | scaffolding audit C-7 餘項 | open |
| W-9 | stop_hook_active 第二道守衛 | env var 守衛（CLAUDE_REFLECT_CHILD）出現失效案例 | 逆向比對 §4#4 | open |
| W-10 | asyncRewake 升級反思 hook | 本機 CC 驗證支援 `asyncRewake`+`rewakeMessage`，且出現紅線級提議需主動敲醒的需求 | 逆向比對 §4#5 | open |
| W-11 | 反思素材風險排序代替位置截斷 | turn 級 diff 常態超 30 檔 | 逆向比對 §4#6 | open |
| W-12 | 反思「已報未修」去重機制 | adopted-but-recurring 實際發生（同型提議二度出現） | 反思機制設計討論 2026-06-05 | open |
| W-13 | skill 指回 memory 的 pointer | agent 因漏看 memory 內容而犯錯 | scaffolding audit 範圍外備註（Agent ④） | open |
```

- [ ] **Step 3: 兩本帳本檔頭 +1 句**——

`proposals.md` 檔頭行尾（`……adopted 而無落實行 = 欠帳）`）改為：

```markdown
# 反思提議（append-only；採納/否決後把該條 status 改掉或刪除；採納落實後加「落實:」行——adopted 而無落實行 = 欠帳；採納時順問：可否轉 eval 場景？判準 → skill reference/harness-evolution.md）
```

`memory_ledger.md` 檔頭行改為：

```markdown
# memory 健檢/整併定奪帳本（append-only；rejected 留作疫苗防重提；adopted 而無落實行 = 欠帳；採納時順問：可否轉 eval 場景？判準 → skill reference/harness-evolution.md）
```

- [ ] **Step 4: `resources/.claude/code_map.md` +1 行**——讀該檔，在頂層檔案清單區（依現有排序）插入：

```markdown
- `watchlist.md` — harness 留觀察項目單一事實來源（重訪節奏 + 觸發訊號；協議見 skill reference/harness-evolution.md）
```

- [ ] **Step 5: commit（明列檔名；兩本帳本 gitignored 不入列）**

```bash
git add resources/evals/scenarios_workflow_routing.json resources/watchlist.md resources/.claude/code_map.md
git commit -m "feat(evals): add s7-s9 scenarios; consolidate harness watch-list

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: worktree——skill reference + 路由 + hook 增量

**Files:**
- Create: `.claude/skills/project-01-workflow/reference/harness-evolution.md`
- Modify: `.claude/skills/project-01-workflow/SKILL.md`（路由表 +1 行）
- Modify: `.claude/hooks/session-start-context.ps1`（model 偵測區塊）
- Modify: `.claude/hooks/NOTES.md`（session-start-context 段補記）

- [ ] **Step 1: EnterWorktree（name: self-evolution）+ invoke karpathy-guidelines**

- [ ] **Step 2: 寫 `reference/harness-evolution.md`**（完整內容）：

```markdown
# Harness 自進化（錯誤→eval 閉環 + watch-list 重訪）

> 🎯 **何時讀本檔**：處理反思 / 整併提議的採納時；要把踩雷補成 eval 場景時；session 快照出現「model 已換代」提醒或 watch-list 觸發訊號出現時。

## 錯誤→eval 轉換（採納時順問）

採納一條踩雷（proposals.md / memory_ledger.md 的 adopted 條目）後追問：「可否轉 eval 場景？」三判準**全符**才轉：

1. **可判定**——期望行為能從 navigator transcript 客觀判定（assertion 寫得出、兩位專家會同判 pass/fail）
2. **協議層**——屬 skill / 協議知識（非一次性 code bug；code bug 由 pytest 回歸守）
3. **會再犯**——同型錯誤在未來任務可能重現

符合 → 在 `resources/evals/scenarios_*.json` 加場景（格式 `{id, task, asserts[3]}`，可選 `model`）；assertion 評**產出不評路徑**、客觀可驗。

**Graduation（畢業儀式）**：新場景必須先跑一次 EDD 驗證（具名觸發 `skill-edd-regression`、args 只帶新場景）——assertion 可判定且不誤殺，才算正式進回歸題庫。誤殺 → 修 assert 重跑，不硬塞。

## Watch-list 重訪

- 單一事實來源：`resources/watchlist.md`（散落來源報告為歸檔，不再各自追蹤）。
- 觸發：(1) **model 換代**——SessionStart hook 比對 state 自動提醒（harness 元件＝對舊 model 弱點的賭注，換代＝重押時機）；(2) 條目自帶訊號；(3) 每 ~3 個月整單掃。
- 處理：逐條問「移掉 / 升級會不會出錯」——敢移除過時 scaffolding；條目改 status（closed + 一行結果與 commit），不刪行。
```

- [ ] **Step 3: SKILL.md 路由表 +1 行**——插在 memory-management 行之後：

```markdown
| 反思/整併採納處理、踩雷轉 eval 場景、watch-list 重訪 / model 換代 | `harness-evolution.md` |
```

- [ ] **Step 4: hook 增量**——`session-start-context.ps1` 在 `$flagNote` 區塊（`if (Test-Path $flagFile) {...}` 結束）之後插入：

```powershell
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
```

並把 summary 的 `$flagNote` 行改為 `…必跑 pytest）$flagNote$modelNote`。

- [ ] **Step 5: 驗 BOM + 靜態解析**

```powershell
$p = '.claude\hooks\session-start-context.ps1'
$b = [System.IO.File]::ReadAllBytes($p)[0..2]; ('BOM: ' + (($b[0] -eq 0xEF) -and ($b[1] -eq 0xBB) -and ($b[2] -eq 0xBF)))
$perr = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $p), [ref]$perr2, [ref]$perr); ('ParseErrors: ' + @($perr).Count)
```

Expected: `BOM: True`、`ParseErrors: 0`

- [ ] **Step 6: fixture 四連測（powershell.exe 5.1 對齊運行時；cwd 用 worktree 路徑、正斜線）**

```powershell
$wt = (Get-Location).Path -replace '\\','/'
# ① 無 model 欄位 → 無提醒、無 state
'{"cwd":"' + $wt + '","source":"startup"}' | powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\hooks\session-start-context.ps1 | Select-String '已換代'
Test-Path .claude\hooks\state\last-model.txt   # Expected: False
# ② 首次帶 model → 無提醒、state 建立
'{"cwd":"' + $wt + '","source":"startup","model":"claude-opus-4-8"}' | powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\hooks\session-start-context.ps1 | Select-String '已換代'
Get-Content .claude\hooks\state\last-model.txt   # Expected: claude-opus-4-8
# ③ 同 model → 無提醒
'{"cwd":"' + $wt + '","source":"resume","model":"claude-opus-4-8"}' | powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\hooks\session-start-context.ps1 | Select-String '已換代'
# ④ 換 model → 提醒 + state 更新
'{"cwd":"' + $wt + '","source":"startup","model":"claude-opus-5-0"}' | powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\hooks\session-start-context.ps1 | Select-String '已換代'
Get-Content .claude\hooks\state\last-model.txt   # Expected: claude-opus-5-0
```

Expected：①②③ 的 Select-String 無輸出；④ 命中「⚠️ model 已換代（claude-opus-4-8 → claude-opus-5-0）」；state 內容如註。測後刪 worktree 的 state 檔（避免殘留誤導）：`Remove-Item .claude\hooks\state\last-model.txt -Confirm:$false`

- [ ] **Step 7: WebFetch 官方 hooks 文檔**（https://code.claude.com/docs/en/hooks）查 SessionStart 輸入是否帶 `model` 欄位 → 結論寫進 Step 8 的 NOTES 補記（帶=記欄位名；未記載=記「防禦式實作，欄位出現才生效」）。

- [ ] **Step 8: NOTES.md 補記**——session-start-context.ps1 既有段落加：

```markdown
- **model 換代偵測**（2026-06-07）：stdin 的 `model` 欄位（防禦式：存在才比對，相容 string 與 `{id}` 物件）與 `state/last-model.txt` 比對，換代 → 快照尾提醒重訪 `resources/watchlist.md`。state 寫入 try/catch 包裹——提醒失敗不毀快照。〔官方文檔查證結論填此〕
```

- [ ] **Step 9: commit + 收尾**

```bash
git add .claude/skills/project-01-workflow/reference/harness-evolution.md .claude/skills/project-01-workflow/SKILL.md .claude/hooks/session-start-context.ps1 .claude/hooks/NOTES.md
git commit -m "feat(hooks,skill): model-change watch-list reminder + harness evolution reference

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

ExitWorktree（keep）→ 主 checkout `git merge --ff-only`（若 diverge 用 cherry-pick）→ `git branch --contains` 驗 → push → 清 worktree/branch。

### Task 3: EDD graduation——只跑 3 新場景

- [ ] **Step 1: Workflow 具名觸發**，args 只帶 s7-s9 三場景（物件陣列，與 Task 1 Step 1 寫進 JSON 的內容一致）：

```
Workflow({ name: 'skill-edd-regression', args: { scenarios: [ <s7 物件>, <s8 物件>, <s9 物件> ] } })
```

- [ ] **Step 2: 檢視 verdict + 逐場景 graded 證據**——9/9 assert 通過 → graduation 完成；有 fail → 讀 navigator transcript 判定是「場景/assert 誤殺」（修 assert 重跑）還是「skill 真缺口」（按 harness-evolution.md 閉環處理、提報使用者）。

### Task 4: 收尾回報

- [ ] 回報：(1) 改了什麼（兩 commit + 帳本檔頭）(2) pineedtodo：無 (3) Pi sync：Stop hook 自動 (4) 後續：下次 session 快照首次帶 model 時 state 初始化、換 model 才會見提醒。

---

## Self-Review 記錄

- spec 元件 1↔Task 2 Step 2-3、2↔Task 1 Step 2、3↔Task 1 Step 1 + Task 3、4↔Task 2 Step 4-8、5↔Task 1 Step 3 ✅
- spec 驗收 1↔Task 2 Step 6、2↔Task 3、3↔Task 1 Step 2（W-1~W-13 對照三來源）、4↔Task 2 Step 7-8 ✅
- 無佔位；hook 代碼 / 場景 JSON / watchlist / reference 全文內嵌 ✅
- 一致性：state 檔名 `last-model.txt`、提醒文案、s7-s9 id 全文一致 ✅
