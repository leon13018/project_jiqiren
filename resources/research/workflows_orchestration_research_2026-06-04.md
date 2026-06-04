# Dynamic Workflows 與多 Agent 編排深掘

> 日期：2026-06-04 ｜ 研究員：dispatch 的 research subagent。
> 定位：**淨增量補充**。基礎概念（何時用 workflow、執行/監視/恢復、權限模式、bundled `/deep-research`、關閉設定）已在 `CC-Dynamic workflows.md`（官方文檔繁中轉述，下稱「**文檔筆記**」）與 `CC_hooks_automation_best_practices_2026-06-03.md §9.2`（下稱「**主筆記**」）。
> 本檔只寫那兩份沒有的：**真實 JS API 簽名與設計準則、pattern 庫範例碼、三大失敗模式對策、選擇表、engineering blog 實測編排經驗**。重疊處指回不重述。
> 最珍貴來源：**使用者本機 `~/.claude/projects/.../workflows/scripts/` 裡 3 份真實跑過的 workflow 腳本**（本專案 skill EDD 回歸用），是 API 的一手權威證據。

---

## 目錄

1. [來源清單](#1-來源清單)
2. [Workflow Script 完整 API（一手腳本實證）](#2-workflow-script-完整-api一手腳本實證)
3. [pipeline vs parallel：判準](#3-pipeline-vs-parallel判準)
4. [官方 Pattern 庫（7 式 + 範例碼）](#4-官方-pattern-庫7-式--範例碼)
5. [三大失敗模式與對策設計](#5-三大失敗模式與對策設計)
6. [何時不用 workflow（成本判準）](#6-何時不用-workflow成本判準)
7. [選擇表：workflow vs subagent vs agent teams vs skill](#7-選擇表workflow-vs-subagent-vs-agent-teams-vs-skill)
8. [多 Agent 編排：engineering blog 實測經驗](#8-多-agent-編排engineering-blog-實測經驗)
9. [踩坑與硬限制](#9-踩坑與硬限制)
10. [本專案對照](#10-本專案對照)

---

## 1. 來源清單

| # | 標題 | URL | 角色 |
|---|---|---|---|
| S1 | A harness for every task: dynamic workflows | claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code | 官方 blog — pattern 庫 + 失敗模式（**權威**） |
| S2 | Orchestrate subagents at scale with dynamic workflows | code.claude.com/docs/en/workflows | 官方 docs（英文版，比文檔筆記**新**：含 `args`、agent teams 欄、`ultracode` keyword） |
| S3 | Orchestrate teams of Claude Code sessions | code.claude.com/docs/en/agent-teams | 官方 docs — agent teams 全貌（選擇表用） |
| S4 | How we built our multi-agent research system | anthropic.com/engineering/multi-agent-research-system | 官方 engineering — 編排實測（token 經濟、委派原則） |
| S5 | Claude Code Workflows: Deterministic Multi-Agent Orchestration | alexop.dev/posts/claude-code-workflows-deterministic-orchestration | 第三方深技術文 — 補 API 細節（**需與 S6 一手腳本交叉驗證才採信**） |
| S6 | 本機真實 workflow 腳本 ×3 | `~/.claude/projects/C--Users-LIN-HONG-Desktop-Project-01[...]/workflows/scripts/*.js` | **一手證據** — 本專案實跑過的 EDD 回歸 harness |

> S5 的 API 細節（`Date.now()`/`Math.random()` 在 workflow 內 throw、`parallel` thunk 拋錯解析為 `null`、`schema` 在 tool-call 層驗證重試）**未被 S6 一手腳本直接證實**（腳本沒用到那些路徑），標記為「第三方未交叉驗證」，下文會註明。S6 已證實的部分（`meta`/`phase`/`pipeline`/`agent` 選項/schema 結構）為**高信度**。

---

## 2. Workflow Script 完整 API（一手腳本實證）

> 以下標 ✅ 者 = S6 一手腳本逐字證實；標 ⚠ 者 = 僅 S2 文檔或 S5 第三方，未在本機腳本見到。

### 2.1 腳本骨架（✅ 三份腳本一致）

```javascript
export const meta = {            // ✅ 必須是純字面量（pure literal），不可含計算
  name: 'dispatch-cleanup-regression',
  description: 'EDD 回歸：fresh navigator 實跑場景對精簡後 dispatch.md...',
  phases: [                      // ✅ 宣告階段，餵給審批卡與進度 UI
    { title: 'Navigate', detail: 'fresh navigator 跑場景 ...' },
    { title: 'Grade',    detail: '逐條 assertion pass/fail ...' },
    { title: 'Verdict',  detail: 'comparator 查去噪是否誤砍 ...' },
  ],
}

// ... 常數 / SCHEMA 定義 ...

phase('Navigate')                // ✅ 開一個進度群組（無回傳值，純標記）
const graded = await pipeline(/* ... */)

phase('Verdict')
const verdict = await agent(/* ... */)

return { graded, verdict }       // ✅ 頂層 return 最終結果，回到 Claude 上下文
```

**關鍵：腳本是 top-level `await` 的 ES module**。`export const meta` + 末尾 `return`，中間用 `phase()` 分段、`await agent()/pipeline()/parallel()` 編排。中間結果留在 **JS 變數**（`graded`、`verdict`），只有 `return` 的東西進 Claude 上下文（呼應文檔筆記「Claude 的上下文只保存最終答案」）。

### 2.2 `agent(prompt, opts)` — 生成單一 subagent（✅）

S6 實證的選項（逐字出現在腳本）：

```javascript
agent(promptString, {
  label: `nav:${s.id}`,          // ✅ 進度 UI 顯示名
  phase: 'Navigate',             // ✅ 歸入哪個 phase 群組
  agentType: 'general-purpose',  // ✅ subagent 類型（可填自訂 subagent 名）
  model: s.model,                // ✅ 覆寫模型；填 undefined = 用 session 模型，'sonnet' = 降級
  schema: NAV_SCHEMA,            // ✅ JSON Schema → 強制 subagent 回結構化資料
})
```

- **`model` 逐 agent 路由**：腳本用 `model: undefined`（跟 session 走，本案 opus）與 `model: 'sonnet'`（對照組）混搭 → 同一次執行內 opus/sonnet 並存。這就是文檔筆記「指令碼將階段路由到不同模型」的真身。
- **`agentType`**：S6 全用 `'general-purpose'`；S2 文檔說可填**任何自訂 subagent 名**（如本專案的 `sales-coder`）。
- **回傳值**：`await agent(...)` 直接回**已解析的結構化物件**（不是字串）。腳本後續 `JSON.stringify(nav)` 把它塞進下一個 agent 的 prompt。

### 2.3 `schema` — 結構化輸出（✅ 強力證據）

S6 三份腳本**大量**用 schema，這是 workflow 可靠性的核心機制。範例（NAV_SCHEMA，逐字）：

```javascript
const NAV_SCHEMA = {
  type: 'object',
  additionalProperties: false,   // ✅ 慣用：禁額外欄位，逼模型精確填
  required: ['scenario_id', 'skill_loaded', 'references_read',
             'forced_second_hop', 'forced_second_hop_detail', 'answer', 'self_assert'],
  properties: {
    scenario_id: { type: 'string' },
    references_read: { type: 'array', items: { type: 'string' },
                       description: '依序 Read 的檔（相對 skill 根）' },
    forced_second_hop: { type: 'boolean', description: '是否被迫第 2 跳...' },
    self_assert: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['assertion', 'met', 'evidence'],
        properties: { assertion: {type:'string'}, met:{type:'boolean'}, evidence:{type:'string'} },
      },
    },
  },
}
```

要點：標準 **JSON Schema**（`type`/`properties`/`required`/`enum`/`additionalProperties`/巢狀 `items`），每欄可帶 `description` 引導模型。S5（第三方，未交叉驗證）補充：schema 在 **tool-call 層**驗證，不符會讓模型重試 —「遠比叫 agent『請回 JSON』然後祈禱可靠」。本案經驗印證：grader/verdict agent 全靠 schema 拿到可程式化處理的 verdict。

### 2.4 `pipeline(items, stage1, stage2, ...)` — 流式分段（✅ 核心）

S6 主力編排原語。逐字（dispatch-cleanup 腳本）：

```javascript
phase('Navigate')
const graded = await pipeline(
  SCENARIOS,                                   // ① 輸入陣列
  (s) => agent(/* navigator prompt */, { label:`nav:${s.id}`, phase:'Navigate',
                 agentType:'general-purpose', model:s.model, schema:NAV_SCHEMA }),  // ② stage 1
  (nav, s) => agent(/* grader prompt 含 JSON.stringify(nav) */,
                 { label:`grade:${s.id}`, phase:'Grade', schema:GRADE_SCHEMA }),     // ③ stage 2
)
```

- **stage 簽名**：`(prevResult, originalItem, index) => ...`。stage 1 收 `(s)`＝原始 item；stage 2 收 `(nav, s)`＝**上一階段結果 + 原始 item**。這讓 grader 同時拿到 navigator 輸出與原場景定義。
- **流式、無 barrier**：每個 item 各自流過所有 stage，快的先完成，慢的不擋。`pipeline` 回傳「每個 item 跑完所有 stage 後的最終結果」陣列。
- 本案：6 個場景各自 navigate→grade，互不等待 → 比 parallel barrier 省 idle。

### 2.5 `parallel(thunks)` — 並行 barrier（⚠ S2/S5，S6 未用）

S6 三份腳本**都沒用** `parallel`（全用 pipeline，因為每階段對前階段有依賴、且要逐 item 流）。以下來自 S2/S5：

```javascript
// S5 範例（第三方，未交叉驗證細節）
const raw = await parallel(
  SOURCES.map((s) => () => agent(s.prompt, { label:`research:${s.key}`, schema:ITEM_SCHEMA }))
);
const collected = raw.filter(Boolean);  // S5：拋錯的 thunk 解析為 null，故總是 .filter(Boolean)
```

- **是 barrier**：等所有 fan-out agent 完成、把結構化輸出合併成一個結果（文檔筆記措辭：「等待所有 fan-out 代理，然後合併」）。
- 注意 thunk 形式：`() => agent(...)`（**惰性**，傳函式而非已啟動的 promise）。

### 2.6 其他原語（⚠ S2/S5，S6 未用）

| 原語 | 來源 | 說明 |
|---|---|---|
| `args` | S2（官方✅文檔層） | 存檔成 `/<name>` 命令後，啟動時傳入的輸入。腳本內讀全域 `args`（如 `args.weekStart`）。Claude 以結構化資料傳入，可直接 `.map()`；省略則 `args === undefined`。 |
| `budget` | S5（未交叉驗證） | 全域 token 目標；`budget.total` 有值才動態加深，無目標時為 `null`。 |
| `workflow(nameOrRef, args?)` | S5（未交叉驗證） | 在腳本內內聯呼叫另一個 workflow（如 `await workflow('deep-research', { question })`）。 |
| `meta` | S6✅ | 純字面量；`name`/`description`/`phases[]`。`phases` 餵審批卡（使用者執行前看到階段列表）。 |

### 2.7 非確定性限制（⚠ S5，未交叉驗證但機制合理）

S5 稱：`Date.now()`、`Math.random()`、無參 `new Date()` 在 workflow 內**會 throw**。原因：runtime journal 每個 `agent()` 呼叫以支援 resume，非確定性會讓 cache 失效。對策：時間戳走 `args` 傳入；要變化就用 index 變 prompt。**未被 S6 證實**（腳本確實沒碰這些），但與「resumable + journal」機制（文檔筆記已述）邏輯自洽，列為待驗證假設。

---

## 3. pipeline vs parallel：判準

文檔筆記只說了「parallel 是 barrier、pipeline 不是」。實作層判準（S5 整理 + S6 印證）：

**預設用 `pipeline()`**。只在「某 stage 需要**一次拿到全部**前序結果」時才用 `parallel()` barrier。

| 該用 parallel（barrier）的合法理由 | 不該用 barrier（應 pipeline）的理由 |
|---|---|
| 跑昂貴下游前要先 **dedupe / merge 整個結果集** | 純逐 item 轉換、item 間無依賴 |
| 基於**總體發現**做 early-exit 決策 | 只是「概念上分階段」想分開 |
| prompt 要比較**跨 item 關係** | 只為程式碼整潔 |

**延遲差異**：parallel 強迫所有 agent 等最慢的；pipeline 讓快的先完成、零 idle gap。

**S6 本案的選擇**：用 pipeline，因 navigate→grade 是逐場景的鏈式依賴（grade 只需該場景自己的 nav 結果，不需別場景的），無跨 item merge 需求 → 正確避開 barrier。最後的 `verdict` 才是 barrier 點（需要**全部** grader 結果一次比對），所以它寫成 `pipeline` 之後**獨立一個 `await agent()`**（吃 `JSON.stringify(graded)` 全集），等於手動實現「等全部完成再合成」—— 這是 fan-out→synthesize 的乾淨寫法。

---

## 4. 官方 Pattern 庫（7 式 + 範例碼）

以下定義**逐字引自 S1 官方 blog**（quote），範例碼來自 S5/S6（標來源）。

| Pattern | S1 官方定義（quote） | 適用場景 |
|---|---|---|
| **Classify-and-act** | "Use a classifier agent to decide on the type of task, and then route to different agents or behavior based on the task. Or, use a classifier at the end to determine output." | 異質輸入先分類再分流；或末端用分類器決定輸出格式 |
| **Fan-out-and-synthesize** | "Split up a task into many smaller steps, run an agent on each step and then synthesize those results." 「each requires its own isolated context to prevent interference」 | 大任務切小、各跑獨立 context 防干擾，再合成 |
| **Adversarial verification** | "For each spawned agent, run a separate spawned agent to adversarially verify its output against a rubric or criteria." | 對每個產出派**獨立** agent 依 rubric 對抗驗證（治 self-preferential bias） |
| **Generate-and-filter** | "Generate a number of ideas on a topic and then filter them by a rubric or by verification, dedupe duplicates and return only the highest quality, tested ideas." | 先發散產想法，再用 rubric/驗證過濾、去重，只留高品質 |
| **Tournament** | "Instead of dividing the work, have agents compete on it. Spawn N agents that each attempt the same task using different approaches. Prompts or models then judge the results in a pairwise fashion using a judging agent until you have a winner." | 不分工而是競賽：N agent 不同解法，pairwise 評審到出冠軍 |
| **Loop until done** | "For tasks with an unknown amount of work, loop spawning agents until a stop condition is met (no new findings, or no more errors in the logs) instead of a fixed number of passes." | 工作量未知時，迴圈派 agent 直到停止條件（無新發現 / log 無錯），而非固定次數 |
| **Loop until dry**（loop-until-done 的具體型） | （S5 命名）連續 N 輪無新發現才停 | 掃 bug / 找來源類：直到「乾涸」 |

### 範例碼

**Adversarial verification + fan-out（巢狀 parallel，S5，未交叉驗證細節）：**
```javascript
const judged = await parallel(fresh.map((b) => () =>
  parallel(['correctness', 'security', 'repro'].map((lens) => () =>
    agent(`Judge "${b.desc}" via the ${lens} lens — real?`, { schema: VERDICT })
  ))
));
```
每個候選 `b` 派 3 個不同 lens 的獨立評審 agent — 對抗驗證 + 多視角。

**Loop until dry（S5，未交叉驗證）：**
```javascript
const seen = new Set();
let dry = 0;
while (dry < 2) {                          // 連續 2 輪無新發現才停
  const found = (await parallel(/* ... */)).flatMap(r => r.bugs);
  const fresh = found.filter(b => !seen.has(key(b)));
  if (!fresh.length) { dry++; continue; }
  dry = 0;
  fresh.forEach(b => seen.add(key(b)));
}
```

**Fan-out→Grade→Synthesize（S6 本機一手實證，最可信）**：見 §2.4 的 pipeline + §2.1 末尾獨立 `verdict` agent。完整鏈是 **6 場景 fan-out（navigate）→ 逐場景對抗 grade（grader 被明令「不採信 navigator 自評、自己核對」）→ 單一 comparator synthesize（吃全部 grader 結果出回歸判定）**。這是 fan-out-synthesize + adversarial-verification 的合體，是本專案實際在用的 **EDD（eval-driven development）回歸 harness**。

---

## 5. 三大失敗模式與對策設計

定義**逐字引自 S1**（quote）：

| 失敗模式 | S1 官方定義（quote） | 對策設計 |
|---|---|---|
| **Agentic laziness** | "when Claude stops before finishing a particularly complex, multi-part task and declares the job done after partial progress, for example addressing 35 of the 50 items in a security review." | **把工作切成獨立 subagent**：每個 agent 只背一小塊（如 1 個 endpoint / 1 個檔），自然不會「做 35/50 就宣告完成」——因為沒有單一 agent 看到 50 項全集去偷懶。配 **loop-until-done** 確保掃到乾涸。 |
| **Self-preferential bias** | "Claude's tendency to prefer its own results or findings, especially when asked to verify or judge them against a rubric." | **Adversarial verification**：用**另一個獨立 agent**（不同 context、不知道前者推理）驗證，而非叫同一 agent 自評。S6 本案明示：grader prompt 寫死「**不採信它的自評結論、自己核對**」。 |
| **Goal drift** | "the gradual loss of fidelity to the original objective across many turns, especially after compaction. Each summarization step is lossy, and details like edge-case requirements or 'don't do X' constraints can get lost." | **多個隔離 context window + 聚焦目標**：S1 原文 "orchestrating separate Claude subagents with their own context windows and focused, isolated goals."。每個 subagent 起點乾淨、目標單一、不經歷 compaction → 不會漂移。把 'don't do X' 約束直接寫進該 agent 的 prompt + schema。 |

**核心洞察（S1）**：workflow 對抗這三者的根本機制 = **把 plan 移進確定性的 JS 控制流**，把易漂移/易偷懶/易自戀的「長對話」拆成**多個短命、隔離、目標單一的 subagent**。腳本（不是 LLM）持有迴圈/分支/中間結果，所以這些不受 LLM 的注意力衰退影響。

---

## 6. 何時不用 workflow（成本判準）

S1 官方原話（quote）：
- "Workflows are not needed for every task and may end up using significantly more tokens."
- "For regular coding tasks, try and ask yourself: **does it really need more compute?** For example, **most traditional coding tasks do not need a panel of 5 reviewers.**"

S2 文檔補充的成本控制手段：
- 大任務前先**跑小切片探成本**（一個目錄而非整 repo、窄問題而非廣問題）。
- `/workflows` view 顯示每個 agent 的 token 用量，可隨時停而不丟已完成工作。
- agent cap（16 並行 / 1000 總）本身就是 runaway 成本上限。
- 不需最強模型的階段 → prompt 裡叫 Claude 用較小模型（呼應 §2.2 `model` 路由）。

**判準濃縮**：workflow 值得用 ⟺ 任務(a) 需要超過一次對話能協調的 agent 數，或(b) 想把編排碼化成可重跑腳本，**且**(c) 任務價值高到付得起 token 溢價。否則用預設 harness。

---

## 7. 選擇表：workflow vs subagent vs agent teams vs skill

S2 官方四欄對照（**比文檔筆記新增 agent teams 欄**）：

|  | Subagents | Skills | Agent teams | Workflows |
|---|---|---|---|---|
| 它是什麼 | Claude 生成的 worker | Claude 遵循的指示 | lead agent 監督**對等 session** | runtime 執行的腳本 |
| 誰決定下一步 | Claude，逐輪 | Claude，照 prompt | lead agent，逐輪 | **腳本** |
| 中間結果在哪 | Claude 上下文 | Claude 上下文 | **共享 task list** | **腳本變數** |
| 可重複的是 | worker 定義 | 指示 | team 定義 | **編排本身** |
| 規模 | 每輪幾個委派 | 同 subagent | 少數長命對等 | **每次數十~數百 agent** |
| 中斷 | 重啟該輪 | 重啟該輪 | **隊友續跑** | **同 session 可恢復** |

**決策樹（綜合 S2/S3）**：
1. 只是「Claude 跟著一套流程做」→ **Skill**（無額外 agent，最省）。
2. 「派幾個 worker 做完回報、worker 間不需對話」→ **Subagent**（token 較低，結果摘要回主上下文）。
3. 「worker 需要**互相溝通、挑戰彼此、自行協調共享 task list**」→ **Agent teams**（S3：研究/審查、各擁模組、競爭假設 debug、跨層協調；token 最高、experimental、預設關閉需 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`）。
4. 「**數十~數百 agent、要確定性控制流、要可重跑/可恢復、要 quality pattern（對抗驗證/多角度起草）**」→ **Workflow**。

**Agent teams vs Workflow 的關鍵分界（最易混淆）**：
- Agent teams = **Claude 逐輪當協調者**（lead 是個還在思考的 LLM session），隊友是**對等完整 session**、能彼此發訊息、共享 task list、可被使用者直接插話。適合**需要討論協作、邊做邊調整**的工作。中斷時隊友續跑。
- Workflow = **腳本（非 LLM）當協調者**，確定性控制流，agent 是隔離 worker 不互通、無 mid-run 使用者輸入（文檔筆記：階段間簽核要拆成各自獨立 workflow）。適合**編排本身要碼化、可重跑、規模大**。
- 經驗法則：要「**一群人開會討論**」用 teams；要「**一條跑得動的生產線**」用 workflow。

---

## 8. 多 Agent 編排：engineering blog 實測經驗（S4）

Anthropic 自家 Research 系統（orchestrator-worker）的**實測數字與原則**，是設計 workflow/teams prompt 的金標準。引述（quote）：

### 8.1 Token 經濟（量化判準）
- "Token usage by itself explains **80% of the variance**" in research performance；加上 tool calls + model choice 共解釋 95%。
- "agents typically use about **4× more tokens** than chat interactions, and multi-agent systems use about **15× more tokens** than chats." → 直接呼應 §6「任務價值要付得起」。
- 並行工具呼叫（3+ 同時）"cut research time by **up to 90%**"。
- 績效：Opus 4 lead + Sonnet 4 subagents "outperformed single-agent Claude Opus 4 by **90.2%**"。

### 8.2 委派原則（治 §5 失敗模式的 prompt 工程）
- **Scale effort to query complexity**（quote）："Simple fact-finding requires just 1 agent with 3-10 tool calls, direct comparisons might need 2-4 subagents with 10-15 calls each, and complex research might use more than 10 subagents."
- **Teach the orchestrator how to delegate**：指示模糊會害「subagents 誤解任務或跑跟別人一模一樣的搜尋」。每個 subagent 要給 **objective + output format + tool/source 指引 + 清楚的任務邊界**，否則「agents duplicate work, leave gaps, or fail to find necessary information」。
- **Think like your agents**：建模擬看 agent 怎麼失敗，「immediately revealed failure modes」。
- **Let agents improve themselves**：Claude 4 能當 prompt engineer 診斷自己為何失敗、提改進 → "40% decrease in task completion time"。
- 策略：先廣搜再收斂；用 extended/interleaved thinking 規劃與評估。

### 8.3 結果彙整（context 隔離 + 不全塞 lead）
- subagent 各有**獨立 context window**、「don't know the other subagents exist」→ 真並行壓縮資訊。
- **不要把所有東西都灌回 lead**：用 **artifact / external memory** — "Subagents call tools to store their work in external systems, then pass **lightweight references** back to the coordinator. This prevents information loss... and reduces token overhead."（對映 workflow 的「中間結果留腳本變數、只 return 最終答案」）。
- 評估用 **end-state evaluation**（看最終狀態對不對）而非逐輪 process 審查。

### 8.4 多 agent 不適用的領域（quote）
- "Most domains that **require all agents to share the same context** or involve **many dependencies between agents** are not a good fit."
- "**Most coding tasks** involve fewer truly parallelizable tasks than research." → 與 S1「一般 coding 不需 5 人評審團」一致。
- agents "not yet great at coordinating" real-time → 強依賴/需即時協調的任務別硬上多 agent。

---

## 9. 踩坑與硬限制

| 項目 | 細節 | 來源 |
|---|---|---|
| **agent 並行上限** | 最多 **16 並行**（CPU 核少更低）、**1000 agent/run**（防 runaway） | S2✅ |
| **無 mid-run 使用者輸入** | 只有 agent 權限提示能暫停。**階段間要簽核 → 把每階段拆成獨立 workflow** | S2✅ |
| **workflow 本身無檔案/shell 存取** | 是 agent 在讀寫/跑命令，腳本只協調 | S2✅ |
| **resume 限同 session** | 退出 Claude Code 後下個 session 會**從頭重跑**（非續跑）；同 session 內已完成 agent 回 cached 結果 | S2✅（文檔筆記已述） |
| **spawned agent 權限** | 永遠在 `acceptEdits` 跑、繼承你的 tool allowlist、檔案編輯自動批准；但 **shell/web fetch/非 allowlist MCP 仍會 mid-run 提示** → 長跑前先把需要的命令加 allowlist | S2✅ |
| **`meta` 須純字面量** | 不可含計算 | S5/S6 |
| **`parallel` thunk 拋錯 → null** | 故總是 `.filter(Boolean)` | S5（⚠未交叉驗證） |
| **非確定性 throw** | `Date.now()`/`Math.random()`/無參 `new Date()`（時間走 `args`） | S5（⚠未交叉驗證） |
| **腳本存放位置** | 每次 run 寫到 `~/.claude/projects/<proj>/<session>/workflows/scripts/`，Claude 拿到路徑可要你看/diff/編輯後重跑 | S2✅ + S6 路徑實證 |
| **觸發關鍵字變更** | v2.1.160 起觸發詞是 **`ultracode`**（舊版是 `workflow`）；自然語「run a workflow」兩版都行 | S2✅（**文檔筆記過時**，仍寫 `workflow`） |
| **存檔位置** | `.claude/workflows/`（專案共享）/ `~/.claude/workflows/`（個人）；同名專案優先 | S2（文檔筆記已述） |
| **需 v2.1.154+、research preview** | Pro 要在 `/config` 開 Dynamic workflows 列 | S2（文檔筆記已述） |

---

## 10. 本專案對照

> 主筆記 §9.2 已下結論：sync hook 是單一確定性動作不需 workflow；workflow 適用本專案「大型 refactor / 多檔掃描」。以下是**淨增量**。

1. **本專案已實際在用 workflow 做 skill 的 EDD 回歸**（S6 三份腳本）。模式固定為 **Navigate（fresh-context navigator 跑場景）→ Grade（對抗 grader，明令不採信自評）→ Verdict（comparator 查去噪是否誤砍 load-bearing）**。這正是 fan-out-synthesize + adversarial-verification 的標準應用，且**正確規避了 §5 self-preferential bias**（grader 是獨立 agent + schema 強制逐條核對）。未來改 skill/reference 去噪時，這套 workflow 是現成的回歸守門。

2. **opus/sonnet 雙模型對照**是本專案 workflow 的固定手法（`model: undefined` vs `'sonnet'`）：同一 prompt 同時驗「精簡後的 reference 連 sonnet 也讀得懂」。這是 §2.2 逐 agent model 路由的高價值用例，省 token 又測健壯性。

3. **派 sales-coder 做跨檔 refactor 時可考慮 workflow 化**：若某次 refactor 要掃 myProgram/sales 多檔 + 連動 tests，符合 §6「超過一次對話能協調」門檻時，可用 fan-out（每檔一 agent）→ adversarial verify（獨立 agent 跑 pytest 驗）→ synthesize。但**注意 S4/S1 警告：多數 coding 任務並非真並行**（檔間有依賴），多半仍該用單一 sales-coder subagent（主筆記結論不變）。判準：refactor 各檔**真獨立**才 workflow，有跨檔依賴就單 agent。

4. **EDD 回歸要簽核時拆 workflow**：§9「無 mid-run 輸入」意味著「跑完看結果再決定改哪」這種需人介入的流程，要拆成「驗證 workflow」+ 人看 + 「修正 workflow」兩段（S6 的 iter3 腳本正是這樣分輪迭代的）。

---

*完。本檔不 commit；交回主 agent。*
