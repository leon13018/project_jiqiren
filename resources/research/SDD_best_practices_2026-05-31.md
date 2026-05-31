# SDD (Spec-Driven Development) 最佳實踐多源調研報告

> **調研日期：2026-05-31**
> **調研方法**：派發 3 個 opus xhigh subagent 並行 WebSearch + WebFetch，主 agent 整合
> **分工**：
> - 來源 A — Anthropic / Claude 官方（subagent: claude-code-guide opus）
> - 來源 B — Claude Code 社群插件 / GitHub Spec Kit / 跨工具生態（subagent: claude-code-guide opus）
> - 來源 C — Karpathy / Sean Grove / Simon Willison / 等思想家（subagent: general-purpose opus）
> **真實性提醒**：所有 URL 由 subagent 經 WebSearch / WebFetch 取得，主 agent 未逐一 verify；使用者引用前建議 spot-check 關鍵連結。3 個 subagent 對「Spec Kit」與「Karpathy 2026 言論」等高引用度來源都獨立提到 → 跨源 cross-check 提供合理信心。

---

## 0. TL;DR（10 條最關鍵發現）

1. **2025 是 SDD 從邊緣走向主流的分水嶺年**：GitHub 開源 spec-kit（2025-09）、Anthropic 開放 plugin 系統（2025-10）、Superpowers 同期發布；Thoughtworks 將 SDD 列為「2025 年 key new engineering practice」。
2. **「四階段 gated workflow」是跨工具共同骨幹**：`specify → plan → tasks → implement`，每階段都有人類審查 checkpoint。Spec Kit / Superpowers / cc-sdd / BMAD 都採此 backbone。
3. **Anthropic 官方不用「SDD」一詞，但概念全面支持**：以 `Explore → Plan → Implement → Commit` 四階段、Plan mode、subagent frontmatter `skills:` 預載、Harness blog 的 planner/generator/evaluator pattern 等多層機制呈現。
4. **「Spec 是新的 source code」是跨人物共識**：Sean Grove（OpenAI）"the best coder will soon be the best communicator"、Birgitta（Thoughtworks）"the spec is the brain, the code is the body"、a16z "source of truth shifts upstream toward prompts, data schemas, API contracts"。
5. **Karpathy 從「vibe coding」(2025-02) 反轉到「agentic engineering with oversight」(2026-02)** — 但本質一致：oversight、verification、spec 是必需品，只是程度光譜不同。
6. **`Project_01` 現行做法（sales-coder subagent + frontmatter `skills:` 預載 + worktree + 主 agent 審查 + Stop hook 跑 pytest）與 Anthropic 官方 reference impl (`cwc-long-running-agents`) 高度同構**，且符合 Superpowers / cc-sdd 主流社群 pattern。
7. **共識 anti-patterns**：waterfall 化、over-engineering（小 bug 修出 16 acceptance criteria）、stale specs、subagent in isolation → globally inconsistent、agent adherence / laziness、雙寫（既有 rules + 新 SDD framework）。
8. **選型光譜**：lightweight（Karpathy CLAUDE.md / Simon Willison micro-spec / spec_driven_develop 單檔 SKILL）→ middleweight（Anthropic 官方 + Superpowers + cc-sdd）→ heavyweight（Spec Kit + BMAD + Kiro IDE）。Project_01 規模適合 middleweight。
9. **Eval = spec 的執行面**（Hamel Husain + Eugene Yan）：spec 必須附 verifiable success criteria，否則只是文檔；EDD（Eval-Driven Development）= TDD 的 LLM 版本。
10. **Spec 是 living document，不是 one-shot 文件**：Sean Grove（OpenAI Model Spec 是動態 markdown 集）、Birgitta 三層光譜（spec-first / spec-anchored / spec-as-source）、Addy Osmani（spec.md 是日常產物）共識。

---

## 1. 整體圖景（2025-2026 SDD 演進）

### 1.1 名詞學：誰叫 SDD，誰不叫

| 流派 | 用詞 |
|---|---|
| GitHub spec-kit / Microsoft / Thoughtworks | **Spec-Driven Development (SDD)** 明文使用 |
| Anthropic 官方 | `Explore → Plan → Implement → Commit` / `feature-spec` / `sprint contract` — **概念有、名詞無** |
| Karpathy | **Agentic Engineering**（取代 2025 早期的 "Vibe Coding"）— 同一精神不同名 |
| Simon Willison | **Authoritative Specification** 階段（5 階段 workflow 之一）— 不用 SDD 一詞 |
| Birgitta Böckeler（Thoughtworks） | **Spec-first / Spec-anchored / Spec-as-source** 三層光譜 |

**啟示**：「SDD」這個品牌名主要由 GitHub Spec Kit 推起；許多更資深的工程實踐其實一直在做 SDD，只是用不同詞彙。

### 1.2 時間線（過去 12 個月）

| 時期 | 事件 |
|---|---|
| 2024-12 | Anthropic 發 [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)：orchestrator-worker pattern |
| 2025-02 | Karpathy 提「vibe coding」放任 LLM 自由生成 |
| 2025-04 | Anthropic 發 [Claude Code best practices](https://code.claude.com/docs/en/best-practices)：Explore-Plan-Code-Commit |
| 2025-09 | **GitHub 開源 spec-kit**（成為 SDD 工具典範） |
| 2025-09 | Anthropic 發 [context engineering blog](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 2025-10 | Anthropic 開放 Claude Code plugin 系統；**Superpowers 同日發布** |
| 2025-11 | Anthropic 發 [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) |
| 2026-01-26 | Karpathy LLM coding pitfalls tweet（轉向 oversight） |
| 2026-02 | Karpathy Sequoia AI Ascent 演講提「Agentic Engineering」取代 vibe coding |
| 2026-03 | Anthropic 發 [Harness design for long-running app dev](https://www.anthropic.com/engineering/harness-design-long-running-apps) — **官方對 SDD 最完整論述** |
| 2026-05 | Karpathy 1 周年 retrospective：「programming via LLM agents is increasingly becoming a default workflow for professionals, except with more oversight and scrutiny」 |

### 1.3 三大流派

```
Lightweight ───────────── Middleweight ───────────── Heavyweight
（思想 + 約定）          （框架 + 工具）              （IDE / 完整 SDLC）

Karpathy (CLAUDE.md)     Anthropic 官方              GitHub Spec Kit
Simon Willison           Superpowers plugin          BMAD-METHOD
spec_driven_develop      cc-sdd (Kiro-inspired)      Kiro (AWS IDE)
（單檔 SKILL.md）         knowledge-work-plugins      Tessl
                         /product-management

實踐者：個人 / 小團隊     中型團隊 / 多 agent 協作      大型企業 / agile team
適用：Project_01 規模     已上手 Claude Code 進階用    多人共識 / SDLC 強需求
```

---

## 2. 跨來源共識（9 大原則）

以下原則由 3 個 subagent 獨立提出（≥2 個來源支持算共識）。

### 共識 1 — Spec/Plan 必須先於 code

| 提出者 | 原文 / 來源 |
|---|---|
| Anthropic Claude Code best practices | *"Separate research and planning from implementation to avoid solving the wrong problem."* |
| Karpathy | "agentic engineering with oversight" 取代 vibe coding |
| Sean Grove (OpenAI) | "the best coder will soon be the best communicator" |
| Addy Osmani | "brainstorming a detailed specification _with_ the AI, then outlining a step-by-step plan, _before_ writing any actual code" |
| Eugene Yan | "Before developing an AI feature, we define success criteria, via product evals, to ensure alignment and measurability from day one" |
| a16z | "source of truth may shift upstream toward prompts, data schemas, API contracts" |

**但有 caveat**（Anthropic 官方明文）：*"For tasks where the scope is clear and the fix is small (like fixing a typo, adding a log line, or renaming a variable) ask Claude to do it directly. ... If you could describe the diff in one sentence, skip the plan."* — **SDD 不適用一切**。

### 共識 2 — Spec 寫進 markdown 檔案而非埋在 prompt

| 提出者 | 形式 |
|---|---|
| Karpathy | `CLAUDE.md`（[viral 100K+ stars repo](https://github.com/multica-ai/andrej-karpathy-skills)） |
| Anthropic 官方 | `CLAUDE.md` + `SKILL.md` + per-feature spec files（`BUILD_PLAN.md` / `PROGRESS.md` in `cwc-long-running-agents`） |
| Sean Grove | OpenAI Model Spec 本身就是 markdown 集 |
| Addy Osmani | `spec.md`（rapid waterfall in 15 minutes） |
| GitHub Spec Kit | `specs/<feature>/{spec,plan,tasks}.md` 強制多檔 |
| Superpowers | brainstorming → design doc 落檔 |
| Riley Goodside | "we will look back at all the markdown files we are generating like the polaroids in Memento" |

**啟示**：Spec 不該活在 prompt 內（一次性、不可審查）；活在 git tracked markdown 才能跨 session 持久化 + PR review。

### 共識 3 — 派 subagent 前先給 spec（frontmatter 預載 / prompt 內塞 / 文件介接）

| 機制 | 來源 |
|---|---|
| Subagent frontmatter `skills:` 欄位預載完整 SKILL.md | Anthropic 官方 [sub-agents docs](https://code.claude.com/docs/en/sub-agents) |
| Subagent `initialPrompt` 欄位預塞首輪 user message | Anthropic 官方 sub-agents frontmatter |
| Per-task fresh subagent + spec 完整塞 prompt | Superpowers（"exact file paths, terminal commands, the complete failing test, the minimal implementation"）/ cc-sdd（`/kiro-impl` 每 task fresh subagent） |
| Planner agent 寫完整 product spec → generator agent 實作 | Anthropic Harness blog（"Before each sprint, the generator and evaluator negotiated a sprint contract"） |

**結論**：「派 subagent 前先寫 spec」是 SDD 在 Claude Code 內的具體載體。**`Project_01` 的 sales-coder + frontmatter `skills:` 預載 karpathy + TDD SKILL 完整內容**就是此 pattern 的本地化實現。

### 共識 4 — 至少 4 階段流程 + human gates

跨工具的共同 backbone：

| 工具 | 階段 |
|---|---|
| Anthropic 官方 | Explore → Plan → Implement → Commit |
| GitHub Spec Kit | constitution → specify → clarify → plan → tasks → analyze → implement |
| Superpowers | brainstorm → worktree → write-plan → execute |
| cc-sdd（Kiro-inspired） | discovery → requirements → design → tasks → impl |
| BMAD | Analysis → Planning → Solutioning → Implementation |
| a16z 共識 | Plan → Code → Review |

**核心：每階段都是 human checkpoint，不是 LLM 自動跑完整 pipeline**。

### 共識 5 — Per-task fresh subagent + 兩段審查（spec compliance → code quality）

| 來源 |
|---|
| Superpowers：明文 "fresh subagent per task with two-stage review" |
| cc-sdd：每 task spawn fresh implementer subagent |
| Anthropic 官方：[best-practices §"Add an adversarial review step"](https://code.claude.com/docs/en/best-practices) |
| Karpathy：「You can outsource your thinking, but you can't outsource your understanding」 |

**`Project_01`** 已落實：派 sales-coder → 主 agent 審查 → 自跑 pytest → 拒絕不合規退回。

### 共識 6 — Worktree / branch 隔離不再是 nice-to-have

| 來源 |
|---|
| Superpowers：強制 "git worktree on a new branch protecting main" |
| Anthropic 官方：[sub-agents frontmatter `isolation: worktree`](https://code.claude.com/docs/en/sub-agents) |
| `Project_01`：`.claude/rules/worktree-workflow.md` 5 階段流程已落實 |

### 共識 7 — TDD / Evals 與 SDD 強耦合

| 來源 | 觀點 |
|---|---|
| Anthropic 官方 | "Give Claude a way to verify its work... Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available" |
| Superpowers | TDD red-green-refactor 強制嵌在 `execute` 階段（非 optional） |
| cc-sdd | EARS-format requirements + TDD |
| Hamel Husain | Evals = spec 的執行面 |
| Eugene Yan | "EDD follows the same philosophy [as TDD]" |

**`Project_01`** 已落實：`tests/sales/` 380+ tests = evals；Stop hook 強制改 sales/ 後必跑 pytest = spec compliance gate。

### 共識 8 — Constitution / Steering / CLAUDE.md 角色等價

| 工具 | 對應檔 |
|---|---|
| GitHub Spec Kit | `.specify/memory/constitution.md` |
| Kiro IDE | `steering` |
| Claude Code | `CLAUDE.md` + `.claude/rules/*.md` |
| Cursor | `.cursor/rules/*.mdc` |

**所有工具都需要「專案級不變律」這層**，叫法不同，作用相同。

### 共識 9 — Spec 是 living document，不是一次寫死

| 來源 |
|---|
| Sean Grove：OpenAI Model Spec 持續迭代 |
| Birgitta：三層光譜（spec-first / spec-anchored / spec-as-source）— anchored 表示開發完仍維護 spec |
| Addy Osmani：spec.md 是日常產物，每次新 feature 都寫 |
| Project_01 經驗：`L4.md`（v1）→ `L4_v3_dual_timer_spec.md`（v3）並列保留 |

---

## 3. 主要分歧（4 條軸線）

### 分歧 1 — Spec 該多重？

| 派別 | 代表 | 核心主張 |
|---|---|---|
| **重型派** | Sean Grove / Birgitta / Addy Osmani / Spec Kit / BMAD | Spec is the new code；80-90% value 在溝通；spec-as-source 是終極形態 |
| **輕型派** | Simon Willison / Geoffrey Litt / spec_driven_develop | Micro-spec per task；manual context paste；spec 是工具不是終點 |

**對 Project_01 啟示**：規模小（單人專題、~1000 行 sales/、~400 tests），**偏輕型 ~ 中型**較合理。重型工具（Spec Kit / BMAD）的 ceremony 對單人專題會超載。

### 分歧 2 — 人是否該繼續實際寫 code？

| 派別 | 代表 | 核心主張 |
|---|---|---|
| **委派派** | Karpathy / Sean Grove | 「best communicator」、80% 委派 agent |
| **動手派** | Geoffrey Litt / Simon Willison | Surgeon analogy：核心親手做、邊緣可委派 |

**Geoffrey Litt 的 autonomy slider**：
- 核心設計：「I still do a lot of coding by hand, and when I do use AI, I'm more careful and in the details」
- 邊緣任務：「Fix typescript errors or bugs which have a clear specification ... I'm much much looser with it」

**對 Project_01 啟示**：[[dispatch-threshold-by-change-size]] memory 的「超級小改動主 agent 動手 / 中以上派 sales-coder」**正是 autonomy slider 已落實**。

### 分歧 3 — Spec 從哪來？

| 派別 | 代表 | 主張 |
|---|---|---|
| **AI brainstorm spec** | Addy Osmani / Karpathy（plan mode 互動） | 人提供方向，AI 反向 interview / brainstorm，產 spec |
| **人先寫 spec** | Sean Grove / Eugene Yan | 人精確表達 intent / 定 eval criteria，AI 只負責實作 |

**Anthropic 官方混合派**：[best-practices §"Let Claude interview you"](https://code.claude.com/docs/en/best-practices) 明文背書 AI interview → SPEC.md → 新 session 執行的模式。

**對 Project_01 啟示**：本次 L4 v3 重設計的流程（user 描述需求 → 主 agent AskUserQuestion 對齊 ambiguity → 寫 spec → 派 sales-coder）**正是混合派**：人提供高層 intent，AI 透過 Q&A 將其結構化為 spec。

### 分歧 4 — SDD vocabulary 是否必要？

| 派別 | 代表 |
|---|---|
| **支持術語化** | Birgitta（三層光譜）/ Thoughtworks / Spec Kit 圈 |
| **不用術語派** | Karpathy（"agentic engineering"）/ Simon Willison / Anthropic 官方 |

**Anthropic 的微妙立場**：機制全做（plan mode / SKILL / subagent / Harness blog 完整論述），但**拒絕將 SDD 作為 named methodology 推廣** — 暗示「方法論名詞不重要，工程實踐才重要」。

---

## 4. 具體實踐光譜（按 weight 排序）

| 工具 / 框架 | Weight | 安裝 | 適用情境 | URL |
|---|---|---|---|---|
| **CLAUDE.md + memory + karpathy SKILL** | Light | 手動建檔 | 個人 / 小團隊 / 小型專題 | （`Project_01` 當前架構） |
| **spec_driven_develop（單檔 SKILL.md）** | Light | 複製單檔 | 跨工具中立、最低公分母 | [zhu1090093659/spec_driven_develop](https://github.com/zhu1090093659/spec_driven_develop) |
| **Aider Architect mode** | Light | `aider --architect` | 兩個 LLM 拆 reasoning/editing | [aider.chat/docs/usage/modes](https://aider.chat/docs/usage/modes.html) |
| **Anthropic 官方 plugin（product-management）** | Light-Mid | `claude plugins add knowledge-work-plugins/product-management` | 需要 PRD workflow | [knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins/tree/main/product-management) |
| **Superpowers** | Mid | `/plugin install superpowers@claude-plugins-official` | brainstorm + worktree + per-task subagent + TDD 強耦合 | [obra/superpowers](https://github.com/obra/superpowers) |
| **cc-sdd（Kiro-inspired）** | Mid | `npx cc-sdd@latest` | 跨 8 個 agent 通用、EARS-format requirements + Mermaid 架構圖 | [gotalab/cc-sdd](https://github.com/gotalab/cc-sdd) |
| **GitHub Spec Kit** | Mid-Heavy | `specify init` | 跨 agent 中立（30+ agent 支援）、PR review 友善 | [github/spec-kit](https://github.com/github/spec-kit) |
| **BMAD-METHOD** | Heavy | clone repo + skill 載入 | 完整 agile team simulation（PM/Architect/SM/Dev 角色） | [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) |
| **Kiro IDE（AWS）** | Heavy | 下載 IDE | IDE 級 SDD、`.kiro/specs/*` native concept | （AWS Kiro 官方） |

---

## 5. Anti-patterns（跨來源共識，必避）

### 5.1 Waterfall 化

> **Thoughtworks 警告**：「heavy up-front specification and big-bang releases」是 SDD 最大失敗模式。

Spec 寫 3 週才開始 code → 等於回到 waterfall。**SDD 的 spec 是「dispatch 前 15-30 分鐘的對齊」，不是「3 週的大文件」**。

### 5.2 Over-engineering

> **Augment Code 案例**：小 bug 修出 4 stories 16 acceptance criteria。
> **Karpathy 第二條 pitfall**：「really like to overcomplicate code and APIs, bloat abstractions, and implement a bloated construction over 1000 lines when 100 would do」

**對策**：Project_01 的「超級小改動主 agent 動手 + karpathy-guidelines 強制 invoke」是直接對應。

### 5.3 Stale specs（比沒 spec 更危險）

> Spec 與 code 不同步時，agent 會「confidently execute on a plan that no longer matches reality」。

**對策**：每次 implement 完回頭 sync spec；spec 是 living document（共識 9）；用 git PR review 強制看到 spec diff。

### 5.4 Subagent in isolation → globally inconsistent

> Fresh context 是雙面刃：解決污染問題，但跨 task 的 invariant 必須在 spec / constitution 明示。

**對策**：Constitution / CLAUDE.md + SubagentStart hook 注入規範（Project_01 已落實）。

### 5.5 Agent adherence / laziness

> HN 共識：spec 寫再細，subagent 還是會偷懶 / 偏離。

**對策**：兩段審查（spec compliance → code quality）+ 主 agent 自跑 pytest（不信 subagent 回報）。Project_01 已落實。

### 5.6 Token 浪費

> HN 留言：「detailed-enough spec is just code that you can't run」— SDD 對小 task ROI 差。

**對策**：autonomy slider — 不是所有 task 都派 subagent + 寫 spec。

### 5.7 雙寫（既有 rules + 新 SDD framework）

> Spec Kit 的 `.specify/` 與 Project_01 既有 `.claude/rules/` 職責重疊；硬導入會雙寫。

**對策**：選一個體系做 single source of truth。Project_01 若要採 SDD 應用 `.claude/rules/` + memory（已有的）+ `resources/plans/<L?>_v?_spec.md`（本次新增），**不引入 spec-kit 的 `.specify/`**。

### 5.8 BMAD 角色過重

> Solo dev 用 BMAD 4 phase + 4 named role agent 可能跑完比實際寫 code 還久。

**對策**：Project_01 規模不需 BMAD。

---

## 6. 對 Project_01 的具體建議

### 6.1 現行做法 = 主流 SDD 思想的具體落地

| 思想家 / 工具 | Project_01 對應實踐 |
|---|---|
| Karpathy CLAUDE.md / agentic engineering | `.claude/CLAUDE.md` + `andrej-karpathy-skills:karpathy-guidelines` SKILL 強制 invoke |
| Anthropic Plan mode → SPEC.md → fresh session | `AskUserQuestion` 對齊 ambiguity → 寫 `<L?>_v?_spec.md` → 派 sales-coder（fresh context） |
| Anthropic subagent frontmatter `skills:` 預載 | `.claude/agents/sales-coder.md` frontmatter `skills:` 預載 karpathy + TDD SKILL |
| Superpowers worktree-first | `.claude/rules/worktree-workflow.md` 5 階段流程 |
| Superpowers per-task fresh subagent + 兩段審查 | sales-coder 派發 + 主 agent 審查（讀檔 + 跑 pytest + 對照 spec） |
| Geoffrey Litt autonomy slider | [[dispatch-threshold-by-change-size]] memory — 超級小改動主 agent / 中以上派 sales-coder |
| Anthropic Stop hook + verification | `stop-check-sales-pytest.ps1` hook 強制改 sales/ 後跑 pytest |
| Hamel / Eugene Yan EDD | `tests/sales/` 380+ tests = evals = spec acceptance criteria |
| Birgitta living spec | `L4.md`（v1）→ `L4_v3_dual_timer_spec.md`（v3）並列保留 |
| Constitution / steering | `.claude/CLAUDE.md` + `.claude/rules/*.md` + memory/ 三層 |

**結論**：Project_01 已是 Karpathy / Sean Grove / a16z / Birgitta / Anthropic 思想的小型 instance；不需重型 SDD 工具（Spec Kit / Kiro / Tessl / BMAD）。

### 6.2 可考慮加強（低成本高 ROI）

| 加強點 | 來源依據 | 具體做法 |
|---|---|---|
| **每個 SDD spec 內顯式列 "Verification step"** | Anthropic 官方 "Give Claude a way to verify its work" / Hamel evals / Eugene Yan EDD | 在 `<L?>_v?_spec.md` §6 "測試指令" 旁加 §6.1 "Verification command + 預期結果範本"（本次 L4_v3 spec §6 已部分做到，可標準化） |
| **`sales-coder` 派發 prompt 顯式 echo "success criteria"** | Karpathy "Goal-Driven Execution"（第 4 條 pitfall）/ Anthropic `/goal` slash command | 派發 prompt 結尾固定加：「**Definition of done**：(1) pytest 全綠 (2) 我列的 spec §X 全部 covered (3) `git branch --contains` 落 worktree branch (4) commit message 含 spec 引用」 |
| **`sales-coder` frontmatter 加 `initialPrompt`** | Anthropic 官方 sub-agents docs 提到此欄位 | 把「先 Read spec 再開始實作」這條固定行為內建到 frontmatter，主 agent 不必每次塞 |
| **建立 `resources/research/` 永久 folder** | a16z / Thoughtworks 等業界 blog 持續演進 | 本報告 + 未來其他調研報告固定放此，跟 `resources/plans/` / `resources/architecture/` 並列 |
| **SDD spec 命名 convention 標準化** | GitHub Spec Kit 的 `specs/<feature>/spec.md` 強制 multi-artifact 但 Project_01 規模不需拆檔 | 統一 `resources/plans/業務程式邏輯規劃/<L?>_v?_<short_name>_spec.md` 命名（本次 L4_v3 已採此格式） |

### 6.3 不建議引入（會雙寫 / 過載）

| 工具 / 做法 | 不建議理由 |
|---|---|
| GitHub spec-kit (`.specify/` + `specs/` + `constitution.md`） | 與 Project_01 既有 `.claude/rules/` + `CLAUDE.md` + `resources/plans/` 重度重疊，硬導入會雙寫；spec-kit 的多 artifact（spec.md + plan.md + tasks.md）對 Project_01 任務規模超載 |
| BMAD-METHOD（4 階段 + 4 角色 agent） | 單人專題不需 PM/Architect/SM 角色 simulate；ROI 負 |
| Cursor `.cursor/rules/*.mdc` 規範 | Project_01 不用 Cursor，無相關 |
| Kiro IDE | 切換 IDE 成本高；機制與 Anthropic Plan mode + skills + subagents 重疊 |
| Per-feature `BUILD_PLAN.md` + `PROGRESS.md`（Anthropic Harness blog） | 適合多 sprint long-running agent；Project_01 任務粒度小（一個 SDD spec 對應一輪 worktree），不需要跨 session progress tracking |

### 6.4 短期 action items（依優先序）

1. **本輪已落地**：`sdd-workflow` memory 已存、`L4_v3_dual_timer_spec.md` 已驗證流程跑通、本報告已歸檔。
2. **下次派 sales-coder 時測試**：在 prompt 結尾加 "Definition of done" 固定段（見 6.2 §2），觀察 sales-coder 是否更精準執行。
3. **後續若新增 SDD spec**：採 `<L?>_v?_<short_name>_spec.md` 命名 + 8 段結構（背景動機 / 設計核心 / 行為規約 / 改檔範圍 / out-of-scope / 參考 / 測試指令 / commit 規範 / 流程鳥瞰）。
4. **若未來 sales-coder 連續踩同類坑**：考慮加 `initialPrompt` 到 frontmatter（見 6.2 §3）— 但這是 future-proofing，現況不必動。
5. **不必**做：引入 spec-kit / BMAD / 切換 IDE / 拆 multi-artifact spec。

---

## 7. 三大來源詳細報告

### 7.1 來源 A：Anthropic / Claude 官方

#### 7.1.1 官方推薦的 SDD 工作流

[Best practices §"Explore first, then plan, then code"](https://code.claude.com/docs/en/best-practices)：

1. **Explore**：進入 plan mode，讓 Claude 只讀檔不改檔，理解現況
2. **Plan**：要求 Claude 產出 detailed implementation plan；`Ctrl+G` 開編輯器手改 plan
3. **Implement**：切出 plan mode，要求 Claude 依 plan 寫 code + 跑 tests
4. **Commit**：commit + open PR

更接近 SDD 的另一個官方流程（同頁 §"Let Claude interview you"）：

> "Keep interviewing until we've covered everything, then write a complete spec to SPEC.md. Once the spec is complete, start a fresh session to execute it."

對 PRD-style workflow，官方提供獨立 plugin：

```bash
claude plugins add knowledge-work-plugins/product-management
# 安裝 /write-spec + feature-spec skill
```

#### 7.1.2 Claude Code 內建支持 SDD 的 12 個機制

| 機制 | 角色 | URL |
|---|---|---|
| **Plan mode** (`Shift+Tab` / `/plan`) | 互動式 plan：read-only 探索 → 產 plan → 審批 | [permission-modes](https://code.claude.com/docs/en/permission-modes) |
| **Ultraplan** (`/ultraplan`) | Cloud 版 plan mode：inline-comment / emoji react | [ultraplan](https://code.claude.com/docs/en/ultraplan) |
| **Built-in Plan subagent** | Plan mode 下委派 read-only research | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| **CLAUDE.md + @imports** | Spec/conventions 持久化載入 | [memory](https://code.claude.com/docs/en/memory) |
| **Skills (`SKILL.md`)** | 可重用 spec/workflow 單位 | [skills](https://code.claude.com/docs/en/skills) |
| **Custom subagents** | frontmatter 預定義 spec-aware worker；`skills:` / `model` / `effort` / `permissionMode` / `isolation: worktree` | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| **`--agent <name>` flag** | 整 session 套用某 subagent system prompt | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| **`/code-review`** | Adversarial subagent fresh context 查 diff | [commands](https://code.claude.com/docs/en/commands) |
| **Dynamic Workflows** (`/workflows`) | Plan 物化為 JS script | [workflows](https://code.claude.com/docs/en/workflows) |
| **Agent teams** (`SendMessage`) | 多 agent 文件介接 | [agent-teams](https://code.claude.com/docs/en/agent-teams) |
| **Stop hook + `/goal`** | Verification 變 deterministic gate | [hooks](https://code.claude.com/docs/en/hooks) |
| **`product-management` plugin** | `/write-spec` + `feature-spec` skill | [knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) |

#### 7.1.3 最權威的「官方版 SDD playbook」

**[Harness design for long-running application development (2026-03)](https://www.anthropic.com/engineering/harness-design-long-running-apps)**：

> "I created a planner agent that took a simple 1-4 sentence prompt and expanded it into a full product spec... Before each sprint, the generator and evaluator negotiated a sprint contract: agreeing on what 'done' looked like for that chunk of work before any code was written."

對應 reference implementation：[anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents)。

> "the agent maintains the handoff itself: it scopes each session to one feature, writes to a structured `PROGRESS.md` as it works and re-reads it first thing on every restart... Builder and evaluator agree per-feature on what 'done' means and write it to a file the hook enforces"

**這是官方對 SDD 多 agent 模式最完整論述 — 官方版「派 subagent 前先寫 spec」的 reference implementation**。

#### 7.1.4 官方 gaps

- 「Spec-Driven Development」這個名詞**從未出現**在官方文檔／blog
- Plan 不會自動持久化到磁碟（需 `Ctrl+G` 手改或 Ultraplan）
- 沒有 first-class spec 儲存目錄（社群自發約定 `SPEC.md` / `BUILD_PLAN.md` / `PROGRESS.md`）
- 沒有 `/dispatch-with-spec <spec-file>` 這種 first-class command
- 沒有「自動跑 acceptance tests against spec」內建工具（需用 hook + pytest 拼）
- 官方明文 caveat：不是所有 task 都需要 plan/spec

### 7.2 來源 B：社群 / 插件 / 跨工具生態

#### 7.2.1 Superpowers 深度

- **作者**：obra（Jesse Vincent）
- **發布**：2025-10-09，2026-01-15 進 Anthropic 官方 marketplace
- **安裝**：`/plugin install superpowers@claude-plugins-official`
- **核心 skills**：`brainstorming`、`writing-plans`、`executing-plans`、`subagent-driven-development`、`dispatching-parallel-agents`、`requesting-code-review`、`test-driven-development`
- **強制 4 步 workflow**：
  1. **Brainstorm** — "no code until you have a design document that a human has approved"
  2. **Git worktree** — 強制隔離 branch
  3. **Write a plan** — 拆成 2-5 分鐘 task，每 task 包 exact file paths / commands / complete code / 對應 failing test
  4. **Execute** — subagent per task + two-stage review（spec compliance → code quality）+ TDD red-green-refactor 強制
- **與 Project_01 對齊度**：**非常高**。主要差距是 Superpowers 強制 brainstorming 階段落檔（spec.md），Project_01 在本次 L4 v3 之前是 plan mode 對話 + memory 不落檔；本次 SDD 流程定案後對齊。

#### 7.2.2 GitHub Spec Kit 深度

- **發布**：2025-09，現 90k+ stars
- **核心命令**：
  ```
  /speckit.constitution    # 專案憲法
  /speckit.specify         # what / why
  /speckit.clarify         # 補洞
  /speckit.plan            # tech stack / architecture
  /speckit.tasks           # 拆 reviewable units
  /speckit.analyze         # cross-artifact 一致性
  /speckit.implement       # 執行
  ```
- **檔案結構**：
  ```
  .specify/
  ├── memory/constitution.md
  ├── templates/{spec,plan,tasks}-template.md
  └── scripts/bash/{create-new-feature,setup-plan,check-prerequisites}.sh
  specs/
  └── <feature-name>/
      ├── spec.md
      ├── plan.md
      ├── tasks.md
      ├── data-model.md
      └── contracts/
  ```
- **支援 agent**：30+
- **對 Project_01 評估**：see §6.3 — 不建議引入（與既有 `.claude/rules/` 雙寫）

#### 7.2.3 其他社群插件

| 工具 | 重點 | URL |
|---|---|---|
| **cc-sdd** | Kiro-inspired harness，跨 8 agent，EARS-format requirements + Mermaid + per-task fresh subagent + 獨立 review pass + 自動 debug | [gotalab/cc-sdd](https://github.com/gotalab/cc-sdd) |
| **BMAD-METHOD** | 完整 agile team simulation（Analyst/PM/Architect/SM/Dev 角色）+ 4 phase | [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) |
| **claude-code-bmad-skills** | BMAD 移植成 Claude Code skills | [aj-geddes/claude-code-bmad-skills](https://github.com/aj-geddes/claude-code-bmad-skills) |
| **awesome-claude-code-subagents** | 100+ 特化 subagent | [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) |
| **spec_driven_develop** | 單檔 SKILL.md，跨工具中立 | [zhu1090093659/spec_driven_develop](https://github.com/zhu1090093659/spec_driven_develop) |

#### 7.2.4 其他 AI coding agent 的 SDD 借鏡

- **Cursor**：`.cursor/rules/*.mdc` 三種 trigger 模式（Always / Auto-Attached by path / Manual）— **跟 Project_01 `.claude/rules/*.md` 的 path-scoped frontmatter 同型**
- **Aider Architect mode**：兩個 LLM 拆 reasoning / editing — plan 用 strong model、edit 用 fast model。**可借鏡**：Project_01 sales-coder 預設 opus xhigh 全程，未來可考慮 plan opus / impl sonnet 切換省 token

### 7.3 來源 C：思想家觀點

#### 7.3.1 Andrej Karpathy 完整軌跡

```
2025-02 vibe coding  →  2025-12 個人 workflow 反轉
                    →  2026-01-26 LLM coding pitfalls tweet（4 大缺陷）
                    →  2026-02 Sequoia "Agentic Engineering"
                    →  2026-05 1 周年 retrospective 確認方向
```

**4 大 LLM coding pitfalls**（[原 tweet](https://x.com/karpathy/status/2015883857489522876)，2026-01-26）：
1. **Silent assumptions** — "The models make wrong assumptions on your behalf and just run along with them without checking"
2. **Over-complication** — "really like to overcomplicate code and APIs, bloat abstractions, and implement a bloated construction over 1000 lines when 100 would do"
3. **Orthogonal damage** — agents 會「change or delete comments and code that it doesn't fully understand as a side effect」
4. **(隱含第 4 條 Goal-Driven Execution，源於 Sequoia 演講)** — Spec / oversight / verification

**Sequoia AI Ascent 2026 演講重點**：
- "You can outsource your thinking, but you can't outsource your understanding"
- "You are still responsible for your software just as before"
- "Vibe coding raised the floor" (但 lacks oversight at scale)
- "Humans must own design, taste, and specification oversight. Agents fill in blanks but can't yet catch spec errors"

**對 Project_01 的隱含支持**：karpathy-guidelines SKILL（預載到 sales-coder frontmatter）直接植入 Karpathy 思想；4 大 pitfalls 全部在「派 subagent 前寫 spec」可以預防。

#### 7.3.2 Sean Grove (OpenAI) — "The New Code"

[AIE WF 2025 演講](https://www.youtube.com/watch?v=8rABwKRsec4)：

- "The best coder will soon be the best communicator"
- "The code you write is only about 10-20% of the value you bring to a project. The other 80-90% comes from structured communication"
- 比喻寫程式時用 prompt 然後丟掉 = "you shred the source and then very carefully version control the binary"
- OpenAI Model Spec 本身就是 markdown 集 — spec 是 living document

**立場**：SDD 最強支持者；spec = program 的 ultimate 形式。

#### 7.3.3 Geoffrey Litt — Surgeon analogy

[Code like a surgeon (2025-10-24)](https://www.geoffreylitt.com/2025/10/24/code-like-a-surgeon)：

- "A surgeon isn't a manager, they do the actual work! But their skills and time are highly leveraged with a support team"
- **Autonomy slider**：
  - 核心設計：「I still do a lot of coding by hand, and when I do use AI, I'm more careful and in the details. I need fast feedback loops and good visibility」
  - 邊緣任務：「I'm much much looser with it, happy to let an agent churn for hours in the background」

**對 Project_01**：[[dispatch-threshold-by-change-size]] memory 完全對齊此 autonomy slider。

#### 7.3.4 其他思想家速覽

- **Simon Willison**（[How I use LLMs to help me write code, 2025-03](https://simonw.substack.com/p/how-i-use-llms-to-help-me-write-code)）：5 階段 workflow — Research & Planning / **Authoritative Specification** / Context Priming / Iterative Refinement / Mandatory Testing。但「不用 SDD 一詞，不偏好 single big spec.md，偏 micro-spec per task」。
- **Hamel Husain**（[Evals Skills for Coding Agents, 2026-03](https://hamel.dev/blog/posts/evals-skills/)）："Improving the infrastructure around the agent mattered more than improving the model"。三層 instrumentation：Documentation → Telemetry → Evals。
- **Eugene Yan**（[An LLM-as-Judge Won't Save The Product, 2025-04](https://eugeneyan.com/writing/eval-process/)）："Before developing an AI feature, we define success criteria, via product evals... EDD follows the same philosophy [as TDD]"。
- **Addy Osmani**（[My LLM coding workflow going into 2026](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e)）："Brainstorming a detailed specification _with_ the AI, then outlining a step-by-step plan, _before_ writing any actual code"。產 spec.md（"waterfall in 15 minutes"）。
- **Birgitta Böckeler**（[Martin Fowler — SDD: Kiro, spec-kit, Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)）：提出三層光譜 **Spec-first / Spec-anchored / Spec-as-source**。
- **Riley Goodside**（Google DeepMind）：「we will look back at all the markdown files we are generating like the polaroids in Memento」— Spec/rules markdown 是 agent 的「外掛記憶」。

#### 7.3.5 學術 paper（subagent 提供，主 agent 未 verify arXiv ID）

> ⚠️ **真實性提醒**：以下 arXiv ID 由 subagent 提供，主 agent 未逐一 verify；2602.xxxxx 格式可能是 future-dated（arXiv 採 YYMM.xxxxx 格式，2602 = 2026-02）。引用前請自行 search arXiv。

- arXiv 2602.00180 — *Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants*
- arXiv 2605.02455 — *LLM-Assisted Repository-Level Generation with Structured Spec-Driven Engineering*
- arXiv 2602.09447 — *SWE-AGI: Benchmarking Specification-Driven Software Construction with MoonBit*
- arXiv 2508.00083 — *A Survey on Code Generation with LLM-based Agents*

#### 7.3.6 業界 blog 引言

- **a16z**（[Nine Emerging Developer Patterns for the AI Era, 2025-05-07](https://a16z.com/nine-emerging-developer-patterns-for-the-ai-era/)）："The source of truth may shift upstream toward prompts, data schemas, API contracts, and architectural intent, with code becoming the byproduct of those inputs, more like a compiled artifact than a manually authored source."
- **Thoughtworks**（[SDD 2025 unpacking](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)）：定調 SDD 是 2025 key new practice。

---

## 8. 完整 URL 清單（去重 + 分類）

### 8.1 Anthropic / Claude 官方

**Claude Code 文檔**
- [Best practices](https://code.claude.com/docs/en/best-practices)
- [Common workflows](https://code.claude.com/docs/en/common-workflows)
- [Permission modes（Plan mode）](https://code.claude.com/docs/en/permission-modes)
- [Ultraplan](https://code.claude.com/docs/en/ultraplan)
- [Sub-agents](https://code.claude.com/docs/en/sub-agents)
- [Skills](https://code.claude.com/docs/en/skills)
- [Workflows](https://code.claude.com/docs/en/workflows)
- [Agent teams](https://code.claude.com/docs/en/agent-teams)
- [Memory (CLAUDE.md)](https://code.claude.com/docs/en/memory)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Goal command](https://code.claude.com/docs/en/goal)
- [Commands](https://code.claude.com/docs/en/commands)
- [Headless mode](https://code.claude.com/docs/en/headless)

**Anthropic Engineering Blog**
- [Building effective agents (2024-12)](https://www.anthropic.com/engineering/building-effective-agents)
- [Claude Code best practices for agentic coding (2025-04, redirects)](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Effective context engineering for AI agents (2025-09)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Equipping agents for the real world with Agent Skills (2025-10)](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Effective harnesses for long-running agents (2025-11)](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- **[Harness design for long-running application development (2026-03)](https://www.anthropic.com/engineering/harness-design-long-running-apps)** ← 最關鍵 SDD-adjacent 論述

**GitHub 官方 repos**
- [anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents) ← Harness blog reference impl
- [anthropics/knowledge-work-plugins (product-management)](https://github.com/anthropics/knowledge-work-plugins/tree/main/product-management)
- [anthropics/anthropic-cookbook (patterns/agents)](https://github.com/anthropics/anthropic-cookbook/tree/main/patterns/agents)

**Claude.com Blog**
- [How Anthropic teams use Claude Code](https://claude.com/blog/how-anthropic-teams-use-claude-code)
- [agentskills.io (open standard)](https://agentskills.io)

### 8.2 社群插件 / 工具

**Superpowers**
- [obra/superpowers (repo)](https://github.com/obra/superpowers)
- [Anthropic plugin marketplace page](https://claude.com/plugins/superpowers)
- [Builder.io: Structured Workflow That Actually Works](https://www.builder.io/blog/claude-code-superpowers-plugin)
- [作者 release blog](https://blog.fsck.com/2025/10/09/superpowers/)

**GitHub Spec Kit**
- [github/spec-kit (repo)](https://github.com/github/spec-kit)
- [Official docs](https://github.github.com/spec-kit/)
- [GitHub Blog announcement](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [Microsoft Developer Blog](https://developer.microsoft.com/blog/spec-driven-development-spec-kit)
- [SpecKit gist with Claude Code](https://gist.github.com/arun-gupta/e1c2c3a826a0605f6b615d25da918f75)

**其他 SDD 框架**
- [gotalab/cc-sdd (Kiro-inspired)](https://github.com/gotalab/cc-sdd)
- [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- [aj-geddes/claude-code-bmad-skills](https://github.com/aj-geddes/claude-code-bmad-skills)
- [24601/BMAD-AT-CLAUDE](https://github.com/24601/BMAD-AT-CLAUDE)
- [zhu1090093659/spec_driven_develop](https://github.com/zhu1090093659/spec_driven_develop)
- [IBM/iac-spec-kit](https://github.com/IBM/iac-spec-kit)

**Awesome lists**
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [VoltAgent/awesome-agent-skills (1000+)](https://github.com/VoltAgent/awesome-agent-skills)
- [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills)

**其他 agent SDD 參考**
- [Aider Architect mode](https://aider.chat/docs/usage/modes.html)
- [Augment Code: Cursor for SDD 評估](https://www.augmentcode.com/guides/cursor-spec-driven-development)
- [Augment Code: What SDD gets wrong](https://www.augmentcode.com/blog/what-spec-driven-development-gets-wrong)
- [Tim Wang: Spec-kit / BMAD / Agent OS / Kiro 比較](https://medium.com/@tim_wang/spec-kit-bmad-and-agent-os-e8536f6bf8a4)

**社群討論**
- [HN: SDD Workflow for Claude Code](https://news.ycombinator.com/item?id=48231575)
- [HN: BMAD-method 討論](https://news.ycombinator.com/item?id=45156172)
- [HN: Aider architect 討論](https://news.ycombinator.com/item?id=42932741)
- [Thoughtworks: SDD as 2025 key practice](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)
- [DataCamp: SDD with Claude Code tutorial](https://www.datacamp.com/tutorial/spec-driven-development-with-claude-code)
- [alexop.dev: SDD with Claude Code in Action](https://alexop.dev/posts/spec-driven-development-claude-code-in-action/)

### 8.3 思想家

**Karpathy**
- [LLM coding pitfalls tweet (2026-01-26)](https://x.com/karpathy/status/2015883857489522876)
- [Vibe coding 1-yr retrospective (2026-05)](https://x.com/karpathy/status/2019137879310836075)
- [Karpathy 2025 Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/)
- [Sequoia AI Ascent 2026 talk recap](https://analyticsdrift.com/andrej-karpathy-agentic-engineering-software-3/)
- [12 lessons Sequoia talk](https://philippdubach.com/posts/karpathys-software-3.0-playbook/)
- [CLAUDE.md viral file analysis](https://byteiota.com/karpathy-claude-md-ai-coding-pitfalls-accuracy-2/)

**Sean Grove (OpenAI)**
- [The New Code talk (YouTube)](https://www.youtube.com/watch?v=8rABwKRsec4)
- [Specification > Code summary (Evan Halley)](https://evanhalley.dev/post/2025-08-02-the-new-code/)

**Simon Willison**
- [How I use LLMs to help me write code (2025-03)](https://simonw.substack.com/p/how-i-use-llms-to-help-me-write-code)
- [Coding with LLMs summer 2025 update](https://simonwillison.net/2025/Jul/21/coding-with-llms/)

**Geoffrey Litt**
- [Code like a surgeon (2025-10-24)](https://www.geoffreylitt.com/2025/10/24/code-like-a-surgeon)
- [Litt tweet on surgeon analogy](https://x.com/geoffreylitt/status/1981720163968749736)

**Hamel Husain / Eugene Yan / Addy Osmani**
- [Hamel: Evals Skills for Coding Agents (2026-03)](https://hamel.dev/blog/posts/evals-skills/)
- [Eugene Yan: An LLM-as-Judge Won't Save The Product (2025-04)](https://eugeneyan.com/writing/eval-process/)
- [Eugene Yan: Patterns for Building LLM-based Systems & Products](https://eugeneyan.com/writing/llm-patterns/)
- [Addy Osmani: LLM coding workflow going into 2026](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e)

**Birgitta Böckeler / Thoughtworks**
- [Martin Fowler: SDD — Kiro, spec-kit, Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [Thoughtworks SDD 2025 unpacking](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)

**a16z**
- [Nine Emerging Developer Patterns for the AI Era (2025-05-07)](https://a16z.com/nine-emerging-developer-patterns-for-the-ai-era/)
- [The Trillion Dollar AI Software Development Stack](https://a16z.com/the-trillion-dollar-ai-software-development-stack/)

**Latent Space**
- [Latent Space "Scaling without Slop" (2026-01-23)](https://www.latent.space/p/2026)
- [Latent Space Agent Engineering](https://www.latent.space/p/agent)

**學術 paper（subagent 提供，未 verify）**
- arXiv 2602.00180 / 2605.02455 / 2602.09447 / 2508.00083 / 2602.20478

**綜述文章**
- [Towards Data Science: From Vibe Coding to SDD](https://towardsdatascience.com/from-vibe-coding-to-spec-driven-development/)
- [Red Hat Developer: How SDD improves AI coding quality](https://developers.redhat.com/articles/2025/10/22/how-spec-driven-development-improves-ai-coding-quality)

---

## 9. 結語

SDD 不是新發明的方法論，而是 LLM coding 走過 vibe coding 階段後的自然回歸。**Project_01 在本次 L4 v3 重設計過程中跑通的流程**（user 描述 → AskUserQuestion 對齊 → 寫 SDD spec doc → user approval → EnterWorktree → 派 sales-coder（fresh context + frontmatter 預載 SKILL）→ 主 agent 審查 → projectStructure 更新 → ff-merge / push / sync / cleanup），**已經是 Anthropic 官方 + Superpowers 主流社群 + Karpathy / Sean Grove / a16z 等思想家觀點的合理整合**。

短期建議：保持現有架構，僅在 sales-coder 派發 prompt 結尾加固定「Definition of done」段（對應 Karpathy 第 4 條 Goal-Driven Execution pitfall），其他 spec-kit / BMAD / Kiro 等重型工具不引入。

長期關注點：當 Project_01 擴展到「需多人協作 / 跨檔大型 refactor / 長期維護」時，可再評估引入 spec-kit 或 BMAD 中的部分 pattern；但需先評估與既有 `.claude/rules/` 體系的雙寫成本。
