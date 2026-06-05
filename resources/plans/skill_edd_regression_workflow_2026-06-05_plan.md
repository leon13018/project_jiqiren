# skill-edd-regression workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Navigate→Grade→Verdict 的 EDD 回歸 harness 永久化為具名 workflow + 外部場景庫。

**Architecture:** 三個新檔——`.claude/workflows/skill-edd-regression.js`（通用 harness，場景經 `args` 傳入）、`resources/edd/scenarios_workflow_routing.json`（首發 6 場景）、`resources/edd/README.md`（跑法）。spec → `resources/specs/skill_edd_regression_workflow_2026-06-05_spec.md`。

**Tech Stack:** Claude Code dynamic workflow（純 JS、無 TS 註記、無檔案存取、禁 `Date.now()`/`Math.random()`）；場景 JSON UTF-8 無 BOM。e2e 經 Workflow tool 觸發（worktree 期間用 `scriptPath`，merge 後用 `name`）。

---

### Task 0: 進 worktree

- [ ] **Step 0.1:** `EnterWorktree(name="edd-workflow")`。

---

### Task 1: workflow 腳本

**Files:**
- Create: `.claude/workflows/skill-edd-regression.js`

- [ ] **Step 1.1: 寫入完整腳本**（檔名須與 `meta.name` 一致供具名觸發）：

```javascript
export const meta = {
  name: 'skill-edd-regression',
  description: '對 project-01-workflow skill 跑 EDD 回歸：fresh navigator 實跑場景 → 對抗 grader 核對 → comparator 總判定',
  phases: [
    { title: 'Navigate', detail: 'fresh navigator 依專案協議跑場景（general-purpose，逐場景可換 model）' },
    { title: 'Grade', detail: '對抗 grader 不採信自評，讀 skill 原文逐條核對 assertion' },
    { title: 'Verdict', detail: 'comparator 合成總判定' },
  ],
}

// 場景由主 agent 讀 resources/edd/ 場景檔後以 args 傳入（workflow 腳本無檔案存取）
if (!args || !Array.isArray(args.scenarios) || args.scenarios.length === 0) {
  throw new Error('缺 args.scenarios。用法：讀 resources/edd/scenarios_<topic>.json 後以 args:{scenarios:[{id, model?, task, asserts:[...]}]} 觸發本 workflow。')
}

const NAV_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scenario_id', 'skill_loaded', 'references_read', 'decision', 'self_assert'],
  properties: {
    scenario_id: { type: 'string' },
    skill_loaded: { type: 'boolean', description: '是否載入 project-01-workflow skill' },
    references_read: { type: 'array', items: { type: 'string' }, description: '依序 Read 的 reference 檔（相對 skill 根）' },
    decision: { type: 'string', description: '最終流程判斷（worktree？SDD？自做或派發？收尾？）' },
    self_assert: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['assertion', 'met', 'evidence'],
        properties: {
          assertion: { type: 'string' },
          met: { type: 'boolean' },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

const GRADE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scenario_id', 'asserts', 'pass_count', 'total'],
  properties: {
    scenario_id: { type: 'string' },
    asserts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['assertion', 'pass', 'evidence'],
        properties: {
          assertion: { type: 'string' },
          pass: { type: 'boolean' },
          evidence: { type: 'string', description: 'skill 原文證據（檔名＋關鍵句），不可複述 navigator' },
        },
      },
    },
    pass_count: { type: 'integer' },
    total: { type: 'integer' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['overall_pass', 'failed', 'summary'],
  properties: {
    overall_pass: { type: 'boolean' },
    failed: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['scenario_id', 'assertion', 'why'],
        properties: {
          scenario_id: { type: 'string' },
          assertion: { type: 'string' },
          why: { type: 'string' },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const navPrompt = (s) => `你是 Project_01 專案裡的 coding agent。你收到以下任務情境（只做導航與協議判斷，不實際修改任何檔案）：

${s.task}

請依專案協議（CLAUDE.md → project-01-workflow skill 路由表 → 對應 reference）走一遍真實導航：實際 Read 你判斷該讀的 skill reference，然後回報：
- 依序讀了哪些檔
- 最終流程判斷：要不要 worktree？走不走 SDD？主 agent 自做還是派 sales-coder？收尾要做什麼？
- 對以下斷言逐條自評（met ＋ 一句證據）：
${s.asserts.map((a, i) => `  ${i + 1}. ${a}`).join('\n')}

scenario_id 填 ${s.id}。`

const gradePrompt = (nav, s) => `你是對抗性評分員，核對另一個 agent 的協議導航是否正確。**不要採信它的自評結論**——自己 Read "C:/Users/LIN HONG/Desktop/Project_01/.claude/skills/project-01-workflow/" 下的 SKILL.md 與相關 reference 原文逐條核對。

任務情境：
${s.task}

待核對斷言：
${s.asserts.map((a, i) => `${i + 1}. ${a}`).join('\n')}

navigator 的回報（僅供對照，其自評不可採信）：
${JSON.stringify(nav)}

逐條判 pass/fail；evidence 必須引 skill 原文（檔名＋關鍵句）。scenario_id 填 ${s.id}。`

const verdictPrompt = (results) => `以下是 ${results.length} 個場景的對抗評分結果。你只做合成、不重新核對：任一 assertion fail 即 overall_pass=false；列出 failed 清單；以繁體中文寫一段總結（指出最弱環節）。

${JSON.stringify(results)}`

phase('Navigate')
const graded = await pipeline(
  args.scenarios,
  (s) => agent(navPrompt(s), { label: `nav:${s.id}`, phase: 'Navigate', agentType: 'general-purpose', model: s.model, schema: NAV_SCHEMA }),
  (nav, s) => agent(gradePrompt(nav, s), { label: `grade:${s.id}`, phase: 'Grade', schema: GRADE_SCHEMA }),
)

const ok = graded.filter(Boolean)
if (ok.length < graded.length) {
  log(`⚠ ${graded.length - ok.length} 個場景中途失敗（null），verdict 只合成 ${ok.length} 場`)
}

phase('Verdict')
const verdict = await agent(verdictPrompt(ok), { label: 'verdict', phase: 'Verdict', schema: VERDICT_SCHEMA })

return { verdict, graded: ok }
```

- [ ] **Step 1.2: 錯誤路徑驗證**——以 Workflow tool 觸發（worktree 路徑、**不帶 args**）：

```
Workflow({ scriptPath: '<worktree>/.claude/workflows/skill-edd-regression.js' })
```
預期：workflow 失敗，錯誤訊息含「缺 args.scenarios。用法：…」。

---

### Task 2: 場景庫 + README

**Files:**
- Create: `resources/edd/scenarios_workflow_routing.json`
- Create: `resources/edd/README.md`

- [ ] **Step 2.1: 場景檔**（UTF-8 無 BOM；6 條，s5 為 sonnet 對照組）：

```json
{
  "topic": "project-01-workflow 路由與協議判斷回歸",
  "scenarios": [
    {
      "id": "s1-sales-bugfix",
      "task": "使用者回報 myProgram/sales/order.py 的數量計算在顧客改單時會算錯，初步估計要改約 30 行邏輯並補測試。請決定完整工作流程。",
      "asserts": [
        "判斷必須先 EnterWorktree（myProgram/ 屬強制 worktree 範圍）",
        "判斷必走 SDD（spec/plan → sales-coder → reviewer → Iron Law）",
        "30 行超過 ≤10 行自 patch 門檻，應派 sales-coder 而非主 agent 自改"
      ]
    },
    {
      "id": "s2-research-note",
      "task": "你剛完成一輪網路調研，要把結果寫成一份新的 markdown 筆記放進 resources/research/。請決定完整工作流程。",
      "asserts": [
        "判斷 resources/ 純文件新增可直接在 main 工作，不必進 worktree",
        "判斷不需走 SDD",
        "git add 必須明列檔名（禁 -A / .）"
      ]
    },
    {
      "id": "s3-hook-edit",
      "task": "需要把 .claude/hooks/stop-reflect.ps1 的 TURN_INTERVAL 常數從 20 改成 30。請決定完整工作流程。",
      "asserts": [
        "判斷 .claude/ 改動必須先 EnterWorktree",
        "判斷這是 meta-task，由主 agent 自實作而非派 sales-coder",
        "知道 hook 的 .ps1 檔必須維持 UTF-8 with BOM"
      ]
    },
    {
      "id": "s4-gotcha-m",
      "task": "你派的 subagent 回報完成並給了 commit SHA，但 git branch --contains <SHA> 顯示該 commit 落在 main 而不是 worktree branch。請決定接下來怎麼處理。",
      "asserts": [
        "識別這是 Gotcha M（subagent commit 落 main 的已知偶發 bug）",
        "主 agent 後續需編輯時，要用 cherry-pick 而非 ff-merge（diverge 陷阱）",
        "清理 worktree branch 要用大寫 -D（因未被 ff-merge）"
      ]
    },
    {
      "id": "s5-sales-bugfix-sonnet",
      "model": "sonnet",
      "task": "使用者回報 myProgram/sales/order.py 的數量計算在顧客改單時會算錯，初步估計要改約 30 行邏輯並補測試。請決定完整工作流程。",
      "asserts": [
        "判斷必須先 EnterWorktree（myProgram/ 屬強制 worktree 範圍）",
        "判斷必走 SDD（spec/plan → sales-coder → reviewer → Iron Law）",
        "30 行超過 ≤10 行自 patch 門檻，應派 sales-coder 而非主 agent 自改"
      ]
    },
    {
      "id": "s6-pi-dependency",
      "task": "sales 新功能需要在 Raspberry Pi 上安裝一個新的 pip 套件才能運作。請決定完整工作流程。",
      "asserts": [
        "判斷絕不在 Windows 本機 pip install（紅線 ⛔#2）",
        "判斷應寫 resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md 由使用者在 Pi 上執行",
        "知道 pineedtodo 由主 agent 集中撰寫（subagent 只在回報列需求）"
      ]
    }
  ]
}
```

- [ ] **Step 2.2: README**：

```markdown
# EDD 回歸（skill-edd-regression workflow）

skill / reference 去噪後的回歸守門。對 Claude 說：

> 跑 skill-edd-regression，場景檔 resources/edd/scenarios_workflow_routing.json

主 agent 讀場景檔 → 以 `args:{scenarios}` 觸發 `.claude/workflows/skill-edd-regression.js`
（Navigate→Grade→Verdict；機制與 API 見 `resources/research/workflows_orchestration_research_2026-06-04.md`）。

## 場景檔格式（一主題一檔，命名 `scenarios_<topic>.json`）

```json
{ "scenarios": [ { "id": "...", "model": "sonnet（可省略=跟 session）",
                   "task": "任務情境", "asserts": ["機器可核對的斷言"] } ] }
```
```

- [ ] **Step 2.3: JSON 合法性驗證**：

```powershell
(Get-Content '<worktree>/resources/edd/scenarios_workflow_routing.json' -Raw | ConvertFrom-Json).scenarios.Count
```
預期：`6`。

- [ ] **Step 2.4: Commit**

```powershell
git add .claude/workflows/skill-edd-regression.js resources/edd/scenarios_workflow_routing.json resources/edd/README.md
git commit -m "feat(workflows): permanent skill-edd-regression harness with first scenario set"
```

---

### Task 3: 全量 e2e（~13 agent）

- [ ] **Step 3.1:** 讀場景檔 → `Workflow({ scriptPath: '<worktree>/.claude/workflows/skill-edd-regression.js', args: { scenarios: <檔內 scenarios 陣列> } })`（args 傳實際 JSON 值，非字串）。
- [ ] **Step 3.2: 結果驗收**——檢查：(a) `verdict.overall_pass` + `failed` + `summary` 齊；(b) `graded` 6 筆、每筆 `pass_count`/`total`；(c) 進度中 `nav:s5-sales-bugfix-sonnet` 確以 sonnet 跑。
- [ ] **Step 3.3: 證據抽查**——任取 2 條 grader evidence，Read skill reference 原文比對屬實（防虛構）。
- [ ] **Step 3.4:** 若有 assertion fail：先判斷是 **skill 真缺陷**（→ 回報使用者，不在本輪修）還是 **場景斷言寫錯**（→ 修場景檔重跑該場景）。harness 本身跑通即算 e2e 過。

---

### Task 4: code_map 同步（worktree 5 階段之 3b）

**Files:**
- Modify: `.claude/code_map.md`（root 層——新增 `.claude/workflows/` 一行）
- Modify: `resources/.claude/code_map.md`（新增 `edd/` 一節）

- [ ] **Step 4.1:** 先 Read 兩檔現有格式，照既有顆粒度各加最小條目（root：`workflows/ — 具名 dynamic workflow 腳本（EDD 回歸 harness）`；resources：`edd/ — EDD 回歸場景庫 + 跑法 README`）。
- [ ] **Step 4.2: Commit**

```powershell
git add .claude/code_map.md resources/.claude/code_map.md
git commit -m "docs(code_map): index .claude/workflows and resources/edd"
```

---

### Task 5: 收尾（worktree 5 階段之 4-5）

- [ ] **Step 5.1:** `ExitWorktree(action="keep")` → `git merge worktree-edd-workflow --ff-only` → `git push origin main`（Stop hook 自動 sync Pi）。
- [ ] **Step 5.2:** `git worktree remove .claude/worktrees/edd-workflow` + `git branch -d worktree-edd-workflow`。

---

### Task 6: merge 後具名冒煙

- [ ] **Step 6.1:** 讀場景檔取前 2 條 → `Workflow({ name: 'skill-edd-regression', args: { scenarios: <前2條> } })`。
預期：runtime 從 `.claude/workflows/` 解析名稱、workflow 正常跑完（~5 agent）。
- [ ] **Step 6.2:** 回報：改了什麼 / 無 pineedtodo / Pi sync 確認 / 全部驗證證據 + e2e baseline 結果。

---

## Self-Review 紀錄

- **Spec 覆蓋**：§3 harness→Task 1、§4 場景→Task 2、§6.1 錯誤路徑→Step 1.2、§6.2 e2e→Task 3、§6.3 抽查→Step 3.3、§6.4 具名冒煙→Task 6、§6.5 code_map→Task 4。無缺口。
- **Placeholder**：無 TBD；三檔內容完整 inline。
- **一致性**：`meta.name`=檔名=具名觸發名；三 schema 欄位在 prompt 與 schema 定義一致（`scenario_id`/`asserts`/`pass`）；`s.model` 省略=跟 session。
