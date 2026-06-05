# skill-edd-regression workflow（EDD 回歸 harness 永久化）— Spec

> 日期：2026-06-05 ｜ 狀態：brainstorming 三題已核可（交付物 A / 場景檔+args / 首發全量 e2e）
> 依據：`resources/research/workflows_orchestration_research_2026-06-04.md`（§2 一手 API 實證、§4 pattern 庫、§9 硬限制、§10-1 本專案 EDD 模式）。
> 背景：歷史 EDD 腳本 ×3 已隨 session 目錄清除；本案把該模式重建為 git-tracked 的具名 workflow。
> 後續：plan → `resources/plans/skill_edd_regression_workflow_2026-06-05_plan.md`。

## 1. 目標

把「skill / reference 去噪後的回歸守門」碼化成可重跑的具名 workflow：**Navigate（fresh navigator 跑場景）→ Grade（對抗 grader 逐條核對）→ Verdict（comparator 總判定）**。場景庫與 harness 分離，同一 harness 可測任何主題。

**成功標準**：(1) 缺 args 時清楚 throw；(2) 全量 6 場景 e2e 跑通，verdict + 逐場景 grade 結構完整；(3) grader 證據抽查屬實；(4) merge 後具名觸發（`{name:'skill-edd-regression'}`）生效；(5) code_map 兩層同步。

## 2. 交付物

| 檔 | 職責 | git |
|---|---|---|
| `.claude/workflows/skill-edd-regression.js` | 通用 harness：meta + 三 phase + schema ×3 + pipeline | tracked（`.claude/` → 強制 worktree） |
| `resources/edd/scenarios_workflow_routing.json` | 首發場景庫：6 條 project-01-workflow 路由場景 | tracked |
| `resources/edd/README.md` | 跑法（叫主 agent 讀場景檔 → Workflow args 傳入）+ 場景格式 | tracked |

## 3. Harness 設計

### 3.1 輸入

```javascript
// 主 agent 讀場景檔後以 args 傳入（workflow 腳本無檔案存取）
args = { scenarios: [ { id, model?, task, asserts: [string] } ] }
```
- 開頭守衛：`args.scenarios` 非陣列或空 → `throw new Error('用法：…')`。
- `model`：`'sonnet'` = 降級對照組；省略 = 跟 session 模型。保留 opus/sonnet 混測手法（調研 §10-2）。

### 3.2 編排（調研 §2.4 / §4 fan-out→synthesize + adversarial verification）

```javascript
export const meta = { name, description, phases: [Navigate, Grade, Verdict] }  // 純字面量
phase('Navigate')   // pipeline 內以 opts.phase 歸組
const graded = await pipeline(
  args.scenarios,
  s          => agent(navPrompt(s),        { label:`nav:${s.id}`,   phase:'Navigate',
                                             agentType:'general-purpose', model:s.model, schema:NAV_SCHEMA }),
  (nav, s)   => agent(gradePrompt(nav, s), { label:`grade:${s.id}`, phase:'Grade', schema:GRADE_SCHEMA }),
)
phase('Verdict')
const verdict = await agent(verdictPrompt(graded), { schema: VERDICT_SCHEMA })  // 唯一 barrier
return { verdict, graded }
```

- **禁用** `Date.now()` / `Math.random()` / 無參 `new Date()`（resume journal 限制，調研 §2.7）。
- navigator 用 `general-purpose`（原生載 CLAUDE.md → 路由行為真實）；grader / verdict 不指定 model（跟 session）。

### 3.3 三個 prompt 要點（全繁中）

- **navigator**：「你在 Project_01 收到任務：<task>。依專案協議決定怎麼做——載哪個 skill、依序讀哪些 reference、最終的流程判斷（worktree？SDD？派發？）。只做導航與判斷，不實際改檔。」schema 強制回報讀檔序列 + 判斷 + 逐條自評。
- **grader**：「對抗性核對。**不採信 navigator 自評**，自己 Read `.claude/skills/project-01-workflow/` 原文，逐條判 assertion pass/fail 並附原文證據（檔名+關鍵句）。」
- **verdict**：「吃全部 grade 結果，輸出 overall_pass、failed 清單（場景/assertion/原因）、一段總結。不重新核對，只合成。」

### 3.4 Schema 三件（調研 §2.3 重建）

- `NAV_SCHEMA`：`{ scenario_id, skill_loaded:bool, references_read:[string], decision:string, self_assert:[{assertion, met:bool, evidence}] }`，`additionalProperties:false`。
- `GRADE_SCHEMA`：`{ scenario_id, asserts:[{assertion, pass:bool, evidence}], pass_count:int, total:int }`。
- `VERDICT_SCHEMA`：`{ overall_pass:bool, failed:[{scenario_id, assertion, why}], summary:string }`。

## 4. 首發場景庫（6 條，斷言須機器可核對）

| id | model | 任務情境 | 核心 asserts |
|---|---|---|---|
| s1-sales-bugfix | （session） | 改 `myProgram/sales/order.py` 一個 30 行邏輯 bug | 必走 worktree；走 SDD；超過 ≤10 行門檻 → 派 sales-coder |
| s2-research-note | （session） | 新增一份 `resources/research/` 調研筆記 | 可直接 main；不走 SDD；git add 明列檔名 |
| s3-hook-edit | （session） | 修改 `.claude/hooks/` 一個 hook 的常數 | 強制 worktree；meta-task 主 agent 自實作；UTF-8 BOM 慣例 |
| s4-gotcha-m | （session） | subagent 回報的 commit SHA `git branch --contains` 顯示 main | 識別 Gotcha M；cherry-pick 而非 ff-merge；`git branch -D` |
| s5-sales-bugfix-sonnet | **sonnet** | 同 s1 | 同 s1（驗精簡 reference 對小模型可讀性） |
| s6-pi-dependency | （session） | sales 新功能需要 Pi 端裝新 pip 套件 | 不在 Windows pip；寫 pineedtodo（主 agent 集中寫）；格式/位置正確 |

## 5. 不做清單

- ❌ harness 內建場景（場景永遠外部檔 + args）。
- ❌ `parallel()` barrier 在 Navigate/Grade 段（pipeline 流式即可；唯一 barrier = verdict）。
- ❌ workflow 內呼 `workflow()` 巢狀 / budget 動態加深（首版 YAGNI）。
- ❌ 自動排程跑回歸（去噪時人工觸發即可）。

## 6. 驗證計畫（Iron Law）

1. **錯誤路徑**：無 args 觸發 → throw 訊息含用法說明。
2. **全量 e2e**：6 場景（~13 agent）→ verdict.overall_pass 與逐場景 grade 齊全；sonnet 場景確實以 sonnet 跑（progress/結果可辨識）。
3. **證據抽查**：隨機抽 2 條 grader 的 evidence，對照 skill reference 原文屬實。
4. **具名冒煙**：merge 後以 `{name:'skill-edd-regression'}` + 2 場景小切片觸發，確認 `.claude/workflows/` 存檔被識別。
5. **結構同步**：root + resources 兩層 code_map 更新。

## 7. 實作與收尾規範

- `.claude/` + `resources/` 同輪改動 → 全程 worktree 5 階段；主 agent 自實作（meta-task 既有例外）。
- e2e 在 worktree 期間以 `{scriptPath}` 指 worktree 內腳本；具名冒煙在 merge 後做（workflow 由 runtime 執行、agent 在主 checkout 工作——與 hook 跨版本問題無關，但存檔識別需 merge 後驗）。
- 場景 JSON：UTF-8 無 BOM（非 PS1，不適用 BOM 鐵則）；內文繁中。
- README 守 lean：跑法 + 格式，不解釋 workflow 機制（指回調研筆記）。
