# 逆向採納候選 4-7 落實 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pass@k 變異數 + baseline 對照（workflow js）、CLAUDE.md 分層健檢 + 跨輪聚合（2 支 PS script）、s2 斷言改寫與重畢業。

**Architecture:** spec：`resources/specs/reverse_adoption_4to7_2026-06-07_spec.md`。js 改動集中在 trial 攤平 + JS 內聚合 + verdict 餵聚合結構；兩支 script 沿 memory/codemap-health 模式。

---

### Task 0: s2 斷言 3 改寫（main 直接做）

- [ ] `scenarios_workflow_routing.json` s2 斷言 3 改為：「收尾計畫中 git add 明列的檔名恰為本次新增的那一個檔（非 -A/.、亦無夾帶無關檔）」；JSON 驗證 10 場景；commit。

### Task 1: worktree——workflow js（C4+C5）

**Files:** Modify `.claude/workflows/skill-edd-regression.js`

- [ ] **Step 1: EnterWorktree（name: adoption-4to7）+ invoke karpathy-guidelines**
- [ ] **Step 2: args 解析段加 k**（在 cases 正規化之後）：

```js
const k = (input && Number.isInteger(input.k) && input.k > 0) ? input.k : 1
```

- [ ] **Step 3: navPrompt 改雙變體**——加 `bareNavPrompt(s)`（明令不載 skill）：

```js
const bareNavPrompt = (s) => `你是一個不熟悉本專案內部協議的一般 coding agent。你收到以下任務情境（只做流程判斷，不實際修改任何檔案）：

${s.task}

【限制】不要載入任何 skill、不要讀 .claude/skills/ 下任何檔案——僅憑一般軟體工程常識與任務文本作答。回報：
- references_read 填空陣列、skill_loaded 填 false
- 最終流程判斷與對以下斷言的逐條自評（met ＋ 一句證據）：
${s.asserts.map((a, i) => `  ${i + 1}. ${a}`).join('\n')}

scenario_id 填 ${s.id}。`
```

- [ ] **Step 4: trial 攤平 + pipeline**——取代現行 `pipeline(cases, ...)`：

```js
// trial 攤平：每場景 k 個 skill-variant trial + （baseline:true 時）1 個 bare trial
const trials = cases.flatMap((c) => {
  const t = Array.from({ length: k }, (_, i) => ({ ...c, variant: 'skill', trial: i + 1 }))
  if (c.baseline) t.push({ ...c, variant: 'bare', trial: 1 })
  return t
})

phase('Navigate')
const gradedTrials = await pipeline(
  trials,
  (s) => agent(s.variant === 'bare' ? bareNavPrompt(s) : navPrompt(s),
    { label: `nav:${s.id}${s.variant === 'bare' ? ':bare' : (k > 1 ? `:t${s.trial}` : '')}`, phase: 'Navigate', agentType: 'general-purpose', model: s.model, schema: NAV_SCHEMA }),
  (nav, s) => agent(gradePrompt(nav, s),
    { label: `grade:${s.id}${s.variant === 'bare' ? ':bare' : (k > 1 ? `:t${s.trial}` : '')}`, phase: 'Grade', schema: GRADE_SCHEMA })
    .then((g) => ({ ...g, variant: s.variant, trial: s.trial })),
)

const ok = gradedTrials.filter(Boolean)
if (ok.length < gradedTrials.length) {
  log(`⚠ ${gradedTrials.length - ok.length} 個 trial 中途失敗（null），聚合只算 ${ok.length} 份`)
}

// JS 內聚合：每場景每 assertion 跨 skill-trial 的 pass 率 + majority；bare 單獨掛 baseline_graded
const byId = {}
for (const g of ok) {
  if (!byId[g.scenario_id]) byId[g.scenario_id] = { skill: [], bare: null }
  if (g.variant === 'bare') byId[g.scenario_id].bare = g
  else byId[g.scenario_id].skill.push(g)
}
const aggregated = Object.entries(byId).map(([id, grp]) => {
  const trialsN = grp.skill.length
  const asserts = (grp.skill[0] ? grp.skill[0].asserts : []).map((a0, idx) => {
    const passes = grp.skill.filter((g) => g.asserts[idx] && g.asserts[idx].pass).length
    return { assertion: a0.assertion, pass_count: passes, trials: trialsN, pass_rate: trialsN ? passes / trialsN : 0, majority_pass: passes >= Math.ceil(trialsN / 2) }
  })
  const weak = [...new Set(grp.skill.flatMap((g) => g.weak_asserts || []))]
  return { scenario_id: id, k: trialsN, asserts, weak_asserts: weak, baseline_graded: grp.bare }
})
```

- [ ] **Step 5: verdictPrompt 改吃聚合**：

```js
const verdictPrompt = (results) => `以下是 ${results.length} 個場景的聚合評分（每場景 skill-variant 跑 k 次後聚合；assertion 帶 pass_rate 與 majority_pass）。你只做合成、不重新核對：任一 assertion 的 majority_pass=false 即 overall_pass=false；failed 列 majority 失敗項；繁體中文總結（k>1 時註明各場景 rate；有 baseline_graded 的場景報 with-skill vs bare 的 pass 數差＝skill 增益；weak_asserts 非空則末尾彙整）。

${JSON.stringify(results)}`
```

verdict 呼叫改 `verdictPrompt(aggregated)`；return 改 `{ verdict, aggregated, graded: ok }`。

- [ ] **Step 6: 自查 workflow-authoring 檢查清單八條**（meta 未動、無 Date.now、k 走 args、pipeline 保持流式、filter(Boolean)+log 保留）

### Task 2: worktree——claudemd-health.ps1（C6）

**Files:** Create `.claude/skills/project-01-workflow/scripts/claudemd-health.ps1`；Modify `reference/pi-and-structure.md`（健檢段 +1 條）

- [ ] **Step 1: 寫 script**（模式同 codemap-health：param -RepoRoot / 找全部 CLAUDE.md 排除 worktrees / 行數預算 root>100❌ >90⚠️ 子層>60❌ >54⚠️ / 反引號 token 白名單啟發式 + 本檔層→repo root 兩段解析驗存活 / 報告去重 / exit 0/1/2 / BOM）
- [ ] **Step 2: BOM + parse 驗證；fixture（超預算 ❌ / 死引用 ❌ / 全綠 ✅）；真實 repo 跑**——Expected 全綠（root 55 行、子層 7-9 行）；誤報則修啟發式
- [ ] **Step 3: pi-and-structure.md 健檢條目改成兩項並列**（codemap-health + claudemd-health 一段講完）

### Task 3: worktree——aggregate-edd.ps1（C7）+ 收尾

**Files:** Create `.claude/skills/project-01-workflow/scripts/aggregate-edd.ps1`；Modify `reference/workflow-authoring.md`（資產段 +1 行）

- [ ] **Step 1: 寫 script**——`-EvalsDir`（預設 `resources/evals`）；掃 `iteration-*/`*.json`，符合新 schema（有 verdict+graded+scenario_ids）才收、舊檔計數跳過；聚合每 (scenario_id, assertion) 跨輪 pass 率（rate<100% 優先列出）+ weak_asserts 頻次 + run 一覽；exit 恆 0
- [ ] **Step 2: BOM + parse；對 iteration-5 實資料跑**——Expected：收 4 份、跳過 iteration-3/4 舊檔、表格輸出、場景 3 的 assert 4 顯示 1/2 跨輪 rate（full-regression fail + revalidation pass）
- [ ] **Step 3: workflow-authoring.md 資產段加**：`- 跨輪聚合：scripts/aggregate-edd.ps1（每 assertion 跨輪 pass 率 + weak_asserts 頻次；讀 iteration-*/ 新 schema result.json）。`
- [ ] **Step 4: commit（明列五檔）→ ExitWorktree → merge/cherry-pick → push → 清 worktree**

### Task 4: 驗證 run ×2 + 落檔 iteration-6 + 筆記 status（main）

- [ ] **Step 1: C4 驗證**——`Workflow({name:'skill-edd-regression', args:{k:3, scenarios:[<改寫後 s2>]}})`：聚合結構合法、3 trial rate 正確、改寫斷言重畢業
- [ ] **Step 2: C5 驗證**——`args:{scenarios:[{...s9, baseline:true}]}`：bare navigator 預期落後、summary 報 delta
- [ ] **Step 3: 兩 run 落檔 `iteration-6/`（k3-s2-revalidation / baseline-s9）+ 簡短 final-consolidated.md**
- [ ] **Step 4: 比對筆記 §4 候選 4-7 status → adopted + 落實行；commit + push；收尾回報**

---

## Self-Review 記錄

- spec 元件 0↔T0、1↔T1、2↔T1 Step3-5、3↔T2、4↔T3；驗收 1↔T4S1、2↔T4S2、3↔T2S2、4↔T3S2、5↔T4S3-4 ✅
- 聚合代碼完整內嵌；兩支 PS script 沿既有兩支健檢的已驗證模式（plan 註明模式差異點，非佔位）✅
- 名稱一致：k / baseline / aggregated / majority_pass / iteration-6 全文一致 ✅
