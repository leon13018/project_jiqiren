export const meta = {
  name: 'skill-edd-regression',
  description: '對 project-01-workflow skill 跑 EDD 回歸：fresh navigator 實跑場景 → 對抗 grader 核對 → comparator 總判定',
  phases: [
    { title: 'Navigate', detail: 'fresh navigator 依專案協議跑場景（general-purpose，逐場景可換 model）' },
    { title: 'Grade', detail: '對抗 grader 不採信自評，讀 skill 原文逐條核對 assertion' },
    { title: 'Verdict', detail: 'comparator 合成總判定' },
  ],
}

// 場景由主 agent 讀 resources/evals/ 場景檔後以 args 傳入（workflow 腳本無檔案存取）。
// args 可能以 JSON 字串抵達（Workflow tool 已知陷阱）→ 字串就 parse，兩種都吃。
let input = args
if (typeof input === 'string') {
  try { input = JSON.parse(input) } catch (e) { input = null }
}
const scenarios = (input && Array.isArray(input.scenarios)) ? input.scenarios : null
if (!scenarios || scenarios.length === 0) {
  throw new Error('缺 args.scenarios。用法：讀 resources/evals/ 下場景檔後以 args:{scenarios:[{id, model?, task, asserts:[...]}]} 觸發本 workflow。')
}

// 欄位正規化：相容舊 evals.json（prompt/expectations）與新格式（task/asserts）
const cases = scenarios.map((s) => ({
  id: String(s.id),
  model: s.model,
  task: s.task || s.prompt,
  asserts: s.asserts || s.expectations || [],
  baseline: s.baseline === true,   // true = 加跑一個不載 skill 的 bare 對照（驗證 skill 增益）
}))
const bad = cases.find((c) => !c.task || c.asserts.length === 0)
if (bad) {
  throw new Error(`場景 ${bad.id} 缺 task/prompt 或 asserts/expectations`)
}

// pass@k：skill-variant 每場景跑 k 次（預設 1 = 單跑；正式守門輪建議 3 抓 flaky）
const k = (input && Number.isInteger(input.k) && input.k > 0) ? input.k : 1

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
  required: ['scenario_id', 'asserts', 'pass_count', 'total', 'weak_asserts'],
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
    weak_asserts: {
      type: 'array',
      items: { type: 'string' },
      description: '非鑑別性 assertion：即使導航錯也會 pass（如只查「有 Read X」而不查判斷正確）。沒有就回空陣列',
    },
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

const bareNavPrompt = (s) => `你是一個不熟悉本專案內部協議的一般 coding agent。你收到以下任務情境（只做流程判斷，不實際修改任何檔案）：

${s.task}

【限制】不要載入任何 skill、不要讀 .claude/skills/ 下任何檔案——僅憑一般軟體工程常識與任務文本作答。回報：
- references_read 填空陣列、skill_loaded 填 false
- 最終流程判斷與對以下斷言的逐條自評（met ＋ 一句證據）：
${s.asserts.map((a, i) => `  ${i + 1}. ${a}`).join('\n')}

scenario_id 填 ${s.id}。`

const gradePrompt = (nav, s) => `你是對抗性評分員，核對另一個 agent 的協議導航是否正確。**不要採信它的自評結論**——自己 Read 專案根（你目前的工作目錄）下 \`.claude/skills/project-01-workflow/\` 的 SKILL.md 與相關 reference 原文逐條核對。

任務情境：
${s.task}

待核對斷言：
${s.asserts.map((a, i) => `${i + 1}. ${a}`).join('\n')}

navigator 的回報（僅供對照，其自評不可採信）：
${JSON.stringify(nav)}

逐條判 pass/fail；evidence 必須引 skill 原文（檔名＋關鍵句）。scenario_id 填 ${s.id}。

另以評分員身分批評題目本身：哪些 assertion 即使 navigator 導航錯了也會 pass（非鑑別性、查存在不查正確）？列入 weak_asserts，沒有就回空陣列——弱 assertion 上的 pass 比沒有更糟（製造假信心）。`

const verdictPrompt = (results) => `以下是 ${results.length} 個場景的聚合評分（每場景 skill-variant 跑 k 次後聚合；assertion 帶 pass_rate 與 majority_pass）。你只做合成、不重新核對：任一 assertion 的 majority_pass=false 即 overall_pass=false；failed 列 majority 失敗項；以繁體中文寫一段總結（指出最弱環節；k>1 時註明各場景 rate；有 baseline_graded 的場景報 with-skill vs bare 的 pass 數差＝skill 增益；weak_asserts 非空則末尾彙整為題庫自我改進訊號，全空則不提）。

${JSON.stringify(results)}`

// trial 攤平：每場景 k 個 skill-variant trial + （baseline:true 時）1 個 bare 對照 trial
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

// JS 內聚合：每場景每 assertion 跨 skill-trial 的 pass 率 + majority；bare 對照單獨掛 baseline_graded
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

phase('Verdict')
const verdict = await agent(verdictPrompt(aggregated), { label: 'verdict', phase: 'Verdict', schema: VERDICT_SCHEMA })

return { verdict, aggregated, graded: ok }
