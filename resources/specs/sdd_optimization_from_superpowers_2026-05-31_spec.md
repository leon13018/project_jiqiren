# SDD 流程優化 — 借鏡 Superpowers 插件最佳實踐 (SDD spec)

> **狀態**：規劃中（2026-05-31 提出）
> **依據**：使用者 2026-05-31 安裝 superpowers v5.1.0 plugin（`~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/`）後要求 reverse-engineer 其架構，整合可借鏡部分到我們現有 SDD 流程。
> **對齊結論**：Phase A 6 項 + Phase B 3 項全引入（見 §2.1）；Phase C 不引入（見 §4）。
> **Trigger 例外**：本 spec 改動 `.claude/rules/` + `.claude/agents/` + memory（非 myProgram/ code），現行 SDD trigger 條款不強制；本輪 user 明示走 SDD 流程作為「SDD 流程演進」的一致 pattern（呼應 2026-05-31 SDD formalization 同樣 self-applied 模式）。

---

## 1. 背景與動機

### 1.1 Superpowers v5.1.0 SDD 流程結構

Superpowers 把 SDD 拆成 5 個獨立 skill + 3 cross-cutting：

```
[Phase 1] brainstorming         → design.md (WHAT)
[Phase 2] writing-plans         → plan.md (HOW，含 2-5min/step)
[Phase 3] subagent-driven-dev   → 三段 subagent 迴圈 / task
            (implementer → spec-reviewer → code-quality-reviewer)
            OR
          executing-plans       → 單 session 順序執行
[Phase 4] verification-before-completion (Iron Law cross-cutting)
[Phase 5] finishing-a-development-branch → 4-way menu
            (merge / PR / keep / discard)

Cross-cutting:
  using-git-worktrees  (isolation)
  test-driven-development  (TDD)
  writing-skills  (meta)
  using-superpowers  (entry point auto-invoker)
```

### 1.2 與我們現行 SDD v2 對比

| 維度 | Superpowers | 我們 v2 SDD | 差距 |
|---|---|---|---|
| Spec / Plan 分離 | design.md + plan.md | 單 spec.md | 我們合併 |
| Plan 顆粒度 | 2-5 min / step + 完整 code + commit msg | 高層改檔範圍 + 測試清單 | 我們較粗 |
| 審查 subagent 數 | 3（impl + spec-rev + code-rev） | 1（主 agent 審）| 我們 1 段 |
| Iron Law verification | 明文化 cross-cutting skill | 慣例（無明文） | 我們無明文 |
| 4-狀態 dispatch | DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT | 自由格式 | 我們無強制 |
| Self-review checklist | 4 大類（Completeness / Quality / Discipline / Testing） | 無正式 | 我們無 |
| Adversarial reviewer pose | 明文 "Do NOT trust report" | 慣例 | 我們無明文 |
| Red Flags table | 每 skill 必有 | 散落各 rule anti-patterns | 我們無統一表 |
| Spec self-review | 4 點 sweep（placeholder / consistency / scope / ambiguity） | user-only review | 我們缺主 agent 自查 |
| Finishing menu | 4 options | 永遠 ff-merge | 我們單一路徑 |

### 1.3 user 三題對齊結論

| 題 | 選擇 |
|---|---|
| Phase A 6 項（高 ROI）| **全 6 項一起引入** |
| Phase B 3 項（中等改動）| **全 3 項一起引入** |
| 落地方式 | **寫 SDD optimization spec → 走現行 SDD 流程實作** |

---

## 2. 設計核心

### 2.1 9 個整合點（按改動類型分組）

#### A. Rule / Memory 層改動（5 項）

**A1 — Iron Law 驗證明文化**（借鏡 superpowers verification-before-completion）

加到 `.claude/rules/sdd-workflow.md` 階段 3「主 agent 審查」段：

```markdown
## 主 agent 審查 Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE**

若本輪未跑驗證指令，**不得宣告完成 / 通過 / 全綠**。

驗證閘門（claim 前必跑）：

| Claim | 必跑指令 | 不夠的證據 |
|---|---|---|
| pytest 全綠 | `python -m pytest tests/sales/` 看見 `N passed` | 上輪結果 / sales-coder 回報 / "should pass" |
| Branch 落 worktree | `git branch --contains <SHA>` 看見 `worktree-*` | git push 成功 ≠ branch 對 |
| Spec 全 cover | 逐條對照 spec §3 → 列哪 commit | "tests passing, done" |
| 改檔範圍正確 | `git diff --stat HEAD~N HEAD` | 信 sales-coder 列表 |

違反 = 不誠實，不是效率。
```

**A2 — Red Flags 反模式表**（借鏡 superpowers using-superpowers / verification）

加到 `.claude/rules/sdd-workflow.md` 末段：

```markdown
## Red Flags（看到這些想法 STOP，你正在合理化）

| 想法 | 真相 |
|---|---|
| 「這太簡單不需 spec」 | 我們強制所有 myProgram/ code 都要 spec（即使 mini 5 行） |
| 「sales-coder 回報全綠了」 | 主 agent 仍要自己 Read + 跑 pytest verify |
| 「我記得規則」 | 規則會演進，重讀 .claude/rules/sdd-workflow.md |
| 「先 patch 看看再說」 | SDD 強制：先 spec → user approval → 才動 code |
| 「主 agent 自己改一下就好」 | myProgram/ code 改動屬 sales-coder 範圍，連 1 行也派 |
| 「commit 落 main 應該是巧合」 | Gotcha M 偶發 bug 確實會發生，每次 `git branch --contains` 驗 |
| 「skip pytest 沒差，反正是 docstring」 | 改 sales/ 後 Stop hook 會 block；明文跑一次省麻煩 |
```

**A3 — Adversarial 審查 pose 明文**（借鏡 superpowers spec-reviewer-prompt.md）

加到 `.claude/rules/sdd-workflow.md` 階段 3：

```markdown
### 審查心態（adversarial）

Sales-coder 回報可能不完整 / 不準確 / 過度樂觀（"finished suspiciously quickly"）。
主 agent 審查時：

**禁止：**
- 信任 sales-coder 對「實作了什麼」的描述
- 信任 sales-coder 對「完整度」的宣告
- 接受 sales-coder 對 spec 的解讀

**必做：**
- 讀實際改的 code（Read tool）
- 逐行對照 spec §3 vs 實作
- 找 sales-coder 沒提的「extra 加料」
- 找 sales-coder 聲稱實作但 grep 不到的「missing 假完成」
```

**A4 — 4 狀態 dispatch 強制**（借鏡 superpowers implementer-prompt.md）

加到 `.claude/agents/sales-coder.md` 系統 prompt §回報格式：

```markdown
### Status 強制 4 選 1（取代自由回報）

每次任務結束**必選**一個 status 開頭：

- **DONE** — 全部完成，自我驗證通過，準備交主 agent 審查
- **DONE_WITH_CONCERNS** — 完成但有疑慮（如「這檔越來越大但 spec 沒提拆分」）
- **BLOCKED** — 卡住跑不完（如「spec §X 跟現有 code 衝突，需 user 拍板」）
- **NEEDS_CONTEXT** — 需要 spec / prompt 沒給的資訊

**禁止**："基本完成"、"應該 OK"、"先這樣"、無 status 開頭直接列改動 — 一律視為違規。
```

**A5 — Implementer self-review 4 類**（借鏡 superpowers implementer-prompt.md）

加到 `.claude/agents/sales-coder.md` 系統 prompt：

```markdown
### Handoff 前 self-review（fresh eyes 自查）

報告主 agent 前，**自己掃一遍**：

**Completeness（完整度）**
- spec §3 改檔範圍每條都做了嗎？
- spec §3.3 測試清單每條都加了嗎？
- 有沒有 edge case 漏處理？

**Quality（品質）**
- 這是我最好的工作嗎？
- 命名清楚反映「做什麼」而非「怎麼做」？
- code 乾淨易維護？

**Discipline（紀律）**
- 沒 overbuild（YAGNI）？
- 只做了 spec 要求的、沒加料？
- 跟既有 pattern 一致（karpathy surgical）？

**Testing（測試）**
- test 真的驗證行為（不是測 mock 行為）？
- TDD 順序對（先 RED 才 GREEN）？
- 測試夠充分？

**找到問題 → 立刻修，別等主 agent 抓** — 抓到了會退回，更慢。
```

#### B. Spec 自身改動 / 新增（3 項）

**B1 — Spec self-review 4 點 sweep**（借鏡 superpowers brainstorming）

加到 `.claude/rules/sdd-workflow.md` 階段 1「寫 spec」段：

```markdown
### 寫完 spec 主 agent 自查 4 點（user approval 前）

主 agent 寫完 spec → AskUserQuestion approval 前，**先 fresh eyes 自掃**：

1. **Placeholder scan** — 有 "TBD" / "TODO" / "後續" / 模糊需求？修掉
2. **Internal consistency** — §3 改檔範圍 vs §2 設計核心 vs §6 測試清單 互相 contradict？
3. **Scope check** — spec 涵蓋是否單一可實作 plan，還是該拆分？
4. **Ambiguity check** — 任何需求能被兩種解讀？挑一個寫死

inline 修完才 AskUserQuestion。**不必 re-review**，修了就走。
```

**B2 — Plan 拆 2-5min/step（含完整 code）**（借鏡 superpowers writing-plans）

加到 `.claude/rules/sdd-workflow.md` Spec template §3 「改檔範圍」加新子段：

```markdown
### §3 改檔範圍 — 加 step-by-step plan 子段

完整版 spec 的 §3 改檔範圍，**每個檔加 step-by-step plan**：

每 step **2-5 分鐘 / 一個原子動作**，依 TDD Red-Green-Refactor 排序：

```markdown
**檔 X：myProgram/sales/states/lN.py**

- [ ] Step 1：寫 failing test
   `tests/sales/test_states.py::test_xxx`
   ```python
   def test_xxx():
       assert function(input) == expected
   ```

- [ ] Step 2：跑 test 確認 FAIL
   `python -m pytest tests/sales/test_states.py::test_xxx -v`
   預期：FAIL with "AttributeError"

- [ ] Step 3：寫最小 prod code
   ```python
   def function(input):
       return expected
   ```

- [ ] Step 4：跑 test 確認 PASS

- [ ] Step 5：commit
   `git commit -m "feat(lN): add xxx"`
```

**No Placeholders：** 每 step 必含實際內容，禁寫「TBD」「fill in」「similar to step N」（要 repeat code）。

**例外（mini spec）**：≤3 行改動的 mini spec 不需 step-by-step，直接 spec 表頭 5 行格式即可。
```

**B3 — spec / plan 兩份 doc 分離**（借鏡 superpowers brainstorming + writing-plans）

修 `.claude/rules/sdd-workflow.md` 流程 + spec 位置：

```markdown
### 兩份 doc：spec.md（WHAT）+ plan.md（HOW）

**新規範：** 完整版 spec 拆兩份：

| 檔 | 內容 | 階段 |
|---|---|---|
| `resources/specs/<name>_spec.md` | WHAT：背景動機 / 設計核心 / 行為規約 / out-of-scope / 參考 | 階段 1 主 agent 寫 |
| `resources/specs/<name>_plan.md` | HOW：改檔範圍 step-by-step + 測試清單 + commit 規範 | 階段 1 主 agent 寫（spec 後續）|

**為何分**：spec 是「跟 user 對齊的契約」（穩定）；plan 是「給 sales-coder 的執行指南」（隨重構演化）。

**mini spec 不拆**：≤3 行改動 5 行 mini spec 包含全部，不另寫 plan。

**派 sales-coder prompt 內必含兩份檔路徑**（spec_path + plan_path）。
```

#### C. 新增三段 subagent 迴圈（1 項，最大改動）

**C1 — 三段 subagent 迴圈**（借鏡 superpowers subagent-driven-development）

**我們 scale 的 adaptation**：superpowers 是「每 task 派 3 subagents」（task = 一個 file 改動）；我們的 spec 通常 = 一輪整套 sales-coder 改動（≥10 tasks）。**不每 task 3x，而每 spec 3x**。

修 `.claude/rules/sdd-workflow.md` 階段 2-3：

```markdown
### 派發階段升級為三段迴圈（每 spec 整體 dispatch）

舊：派 sales-coder → 主 agent 審查 → 完。

新：

```
spec / plan 寫完
  ↓
[第 1 段] 派 sales-coder 實作（implementer）
  ↓
  Status: DONE / DONE_WITH_CONCERNS → 進第 2 段
  Status: BLOCKED / NEEDS_CONTEXT → 主 agent 提供 + re-dispatch
  ↓
[第 2 段] 派 spec-reviewer subagent（fresh context，僅看 spec + diff）
  prompt: superpowers spec-reviewer-prompt.md adapted
  輸出: ✅ 全符 / ❌ 列 missing + extra
  ↓
  ❌ → 派 sales-coder fix → 回第 2 段重審
  ✅ → 進第 3 段
  ↓
[第 3 段] 派 code-quality-reviewer subagent（fresh context，僅看 code）
  prompt: superpowers code-quality-reviewer-prompt.md adapted
  輸出: ✅ Approved / ❌ Issues (Critical/Important/Minor)
  ↓
  ❌ Critical/Important → 派 sales-coder fix → 回第 3 段
  ❌ Minor only → 主 agent 判決（接受或修）
  ✅ → 主 agent 跑 pytest + branch verify → 進階段 3b
```

**模型選擇**（借鏡 superpowers Model Selection）：

| 角色 | 模型 |
|---|---|
| Implementer (sales-coder) | opus xhigh（既有，不變）|
| Spec-reviewer | sonnet（任務簡單：對照 spec vs code）|
| Code-quality-reviewer | opus xhigh（架構判斷）|

**Subagent type**：spec-reviewer / code-quality-reviewer 都派 `general-purpose` model 覆寫 — 因為這兩個 reviewer 不需 sales-coder frontmatter 預載的 karpathy + TDD SKILL（只查 spec 一致性 / code quality）。

**何時跳過三段**：mini spec（≤3 行）改動成本太低，主 agent 自己 patch + verify 即可，不派 subagent。
```

加新檔 `.claude/rules/sdd-prompts/spec-reviewer.md` + `.claude/rules/sdd-prompts/code-quality-reviewer.md`（prompt template 集中存）：

```markdown
# spec-reviewer subagent prompt template

你的工作是審查 sales-coder 的實作是否符合 spec。

## Spec
[完整 spec 路徑 + §3 改檔範圍 + §3.3 測試清單]

## Sales-coder 回報
[從 sales-coder DONE 回報 paste]

## CRITICAL: 不要信回報

Sales-coder 完成得 suspiciously quickly。回報可能不完整 / 不準確 / 過度樂觀。
你**必須**獨立 verify：

**禁止：**
- 信 sales-coder 列的「實作了什麼」
- 信 sales-coder 對 spec 的解讀

**必做：**
- Read 實際改的 code
- 逐行對照 spec §3 改檔範圍 vs 實作
- 找 sales-coder 沒提的「extra 加料」
- 找 sales-coder 聲稱實作但 grep 不到的「假完成」

## 回報
- ✅ Spec compliant（全部符合，沒 missing 沒 extra）
- ❌ Issues found：
   - Missing: spec §X.Y 規定 [...] 但 grep 不到（file:line 引用）
   - Extra: 實作了 [...] 但 spec 沒要求（file:line）
   - Misinterpreted: spec §X.Y 意思 [...] 但實作做成 [...]
```

```markdown
# code-quality-reviewer subagent prompt template

你的工作是審查 sales-coder commit 的 code quality（spec compliance 已通過）。

## 改動範圍
[從 git diff 摘要]

## SHA 範圍
BASE: [pre-task SHA]
HEAD: [final SHA]

## 審查重點（依 karpathy-guidelines）

**Strengths：** 哪些做得好

**Issues（依嚴重度）：**
- Critical：bug / 安全 / 規格錯誤
- Important：karpathy 違反（over-engineering / abstraction premature / missing surgical）
- Minor：命名 / 註解 / docstring

**Specific checks：**
- 每檔有清楚單一責任 + 介面 well-defined？
- 各 unit 可獨立 understood + tested？
- 跟 spec §3 file structure 一致？
- 新檔 / 既有檔成長合理（不是肥到失控）？

## 回報
- ✅ Approved
- ❌ Issues（每條 file:line 引用 + 具體建議）+ 嚴重度
```

### 2.2 兼容性與不衝突

| 既有 | 新加 | 互動 |
|---|---|---|
| `[[dispatch-threshold-by-change-size]]` 超級小改動主 agent patch | C1 三段迴圈 | 超級小 = mini spec = 不派 subagent，三段迴圈不適用，主 agent 自 verify（A1 Iron Law） |
| `[[worker-level-changes-dispatch-sales-coder]]` worker 必派 sales-coder | A4 4 狀態 dispatch | sales-coder 自己 follow status 規定 |
| `[[bdd-tdd-workflow]]` dormant | B2 step-by-step plan | plan §3 各檔 step-by-step 即內嵌 TDD Red-Green-Refactor，不必重啟 BDD |
| `[[karpathy-guidelines]]` SKILL | A5 self-review + C1 code-quality-reviewer | reviewer 用 karpathy 當審查 yardstick |
| `[[wave-workflow-6-protections]]` | C1 三段迴圈 | wave 6 招（先列再做 / 每改完跑 pytest / commit 前自檢 / verbose / 規格衝突必停 / fail 必停）仍適用 sales-coder；三段迴圈是迴圈外加層 |

---

## 3. 改檔範圍

### 3.1 修改

| 檔案 | 改動 | 行數估計 |
|---|---|---|
| `.claude/rules/sdd-workflow.md` | 加 A1 Iron Law / A2 Red Flags / A3 adversarial / B1 spec self-review / B2 step-by-step / B3 spec-plan 分離 / C1 三段迴圈 7 大段 | +180 |
| `.claude/agents/sales-coder.md` | 加 A4 4 狀態 + A5 self-review 4 類 段 | +60 |
| `.claude/CLAUDE.md` | 📐 SDD 段補一句「v3：含三段審查 + 4 狀態 dispatch + Iron Law」+ 查閱表 1 新行（sdd-prompts/） | +3 |
| `resources/projectStructure/projectStructure.md` | 樹加 `.claude/rules/sdd-prompts/` + 2 prompt 檔行；更新紀錄 append entry | +5 |
| 更新 `<memory>/sdd_workflow.md` | 反映 v3 三段迴圈 + 4 狀態 + Iron Law | rewrite 約 -5/+20 |

### 3.2 新增

| 路徑 | 內容 | 行數 |
|---|---|---|
| `.claude/rules/sdd-prompts/spec-reviewer.md` | spec-reviewer subagent prompt template | ~50 |
| `.claude/rules/sdd-prompts/code-quality-reviewer.md` | code-quality-reviewer subagent prompt template | ~50 |
| `resources/specs/sdd_optimization_from_superpowers_2026-05-31_spec.md` | 本 spec doc | ~400 |
| `resources/specs/sdd_optimization_from_superpowers_2026-05-31_plan.md` | 本 spec 的 plan doc（demo B2 + B3） | ~150 |

### 3.3 不改

- 既有 SDD spec docs（`L4_v3_dual_timer_spec.md` / `sdd_workflow_formalization_2026-05-31_spec.md`）— 已落地，不回填新格式
- `myProgram/` 任何 .py code — 純流程改動，無業務變化
- `tests/` 任何 — pytest 仍 386 passed 不變
- 其他 `.claude/rules/*.md`（vendor-sdk-api / threading-conventions / path-conventions / worktree-workflow 等）— 不衝突
- `[[bdd-tdd-workflow]]` rule — 仍 dormant，B2 step-by-step plan 內嵌 TDD 不重啟 BDD

---

## 4. Out of scope（明確不引入）

### 4.1 借鏡 Phase C 不引入（5 項）

| Superpowers 項 | 不引入理由 |
|---|---|
| **2-3 approaches 必提**（brainstorming） | 我們 task 多為「改 X 從 Y → Z」具體需求，多數有明顯最佳解；強提 alternatives 浪費 token + 慢決策 |
| **嚴格 1 問 / 訊息**（brainstorming）| AskUserQuestion 4-bundle 已足夠，1 問 / 訊息對長 alignment 太慢 |
| **模型分層**（subagent-driven-dev） | sales-coder 全 opus xhigh 既有 setup；spec-reviewer 雖可 sonnet 但本 spec 已含此（§2.1 C1 表）；無需獨立 rule |
| **Finishing 4-way menu**（merge/PR/keep/discard）| 我們無 PR 流程、無 discard 場景；永遠 ff-merge to main + push 即可 |
| **Visual companion**（brainstorming 子）| Pi 機器人純對話 + 規則匹配，無 UI mockup 需求 |

### 4.2 借鏡 Phase C 結構性不適用

| 項 | 不適用理由 |
|---|---|
| **superpowers:using-superpowers 自動 invoke skill** | 屬 plugin 級 entry skill；我們已有 `.claude/rules/` 自動載入 + SubagentStart hook 注入，不引入 plugin-level entry |
| **AGENTS.md / GEMINI.md / .opencode/INSTALL.md 多 harness 支援** | 我們只用 Claude Code，不需跨 harness adapter |
| **Anthropic 官方 PR contribution guidelines** | 我們不貢獻 superpowers upstream，無關 |

### 4.3 不回填既有產出

- `L4_v3_dual_timer_spec.md` 不改用 spec/plan 分離格式 — 已落地、行為穩定
- `sdd_workflow_formalization_2026-05-31_spec.md` 同上
- `tests/sales/` 不重寫 — 386 tests 已是 regression net，不需改格式
- 既有 `[[wave-workflow-6-protections]]` 等 memory 不重寫 — 跟新 C1 三段迴圈 互補不衝突

---

## 5. 規範與參考

### 5.1 派發
- 本 meta-task 屬 rules / agents / memory 改動 — **主 agent 自行實作**（不派 sales-coder）
- 理由：sales-coder 範圍框死 myProgram/sales/ + worker code；本任務全 `.claude/` + memory 改動

### 5.2 TodoList 雙軌（demo 新流程）
- 本輪只用主 agent 軌（無 subagent）— TaskCreate 對應 §3.1 + §3.2 各檔

### 5.3 參考 Superpowers 原檔（reverse-engineering 對照）

| Superpowers 檔 | 我們對應段 |
|---|---|
| `skills/verification-before-completion/SKILL.md` | A1 Iron Law |
| `skills/using-superpowers/SKILL.md` Red Flags table | A2 Red Flags |
| `skills/subagent-driven-development/spec-reviewer-prompt.md` | A3 adversarial + C1 spec-reviewer template |
| `skills/subagent-driven-development/implementer-prompt.md` | A4 4 狀態 + A5 self-review |
| `skills/brainstorming/SKILL.md` (Spec Self-Review 段) | B1 spec self-review 4 點 |
| `skills/writing-plans/SKILL.md` | B2 step-by-step plan + B3 spec/plan 分離 |
| `skills/subagent-driven-development/SKILL.md` | C1 三段迴圈 主架構 |
| `skills/subagent-driven-development/code-quality-reviewer-prompt.md` | C1 code-quality-reviewer template |

### 5.4 相關 memory / rules
- `[[sdd-workflow]]` memory — 待本輪 rewrite 反映 v3 升級
- `.claude/rules/sdd-workflow.md` — 本輪主要修改檔
- `.claude/agents/sales-coder.md` — 本輪附帶修改
- `[[wave-workflow-6-protections]]` memory — 仍適用 sales-coder dispatch；新增三段迴圈是迴圈外加層
- `resources/research/SDD_best_practices_2026-05-31.md` §6 對 Project_01 建議（含此次借鏡來源）

---

## 6. 測試指令 + 預期結果

### 6.1 程式碼 regression

```bash
python -m pytest tests/sales/ -v
```

**預期**：386 passed（與當前一致；本輪純流程改動 + 無 myProgram/ code 改動 → 無回歸）

### 6.2 流程驗證（dry-run / smoke test）

**Subjective verification**（無 unit test 可跑）：
- 主 agent 自審 `.claude/rules/sdd-workflow.md` 內 Red Flags 表是否實際提醒到典型反模式
- 主 agent 自審 `.claude/agents/sales-coder.md` 內 Status 4 選 1 是否覆蓋 sales-coder 可能情境
- `.claude/rules/sdd-prompts/spec-reviewer.md` 與 `code-quality-reviewer.md` 兩份 prompt template 可直接 copy-paste 用

### 6.3 grep 驗證 cross-reference 完整

```bash
# 確認 CLAUDE.md / sdd-workflow.md / sales-coder.md 三檔互相引用 sdd-prompts/
grep -rn "sdd-prompts" .claude/ resources/
```

**預期**：≥ 3 處命中（rule + agents + projectStructure）

---

## 7. Commit 規範

**推薦拆 4 commit：**

**Commit 1 — Spec docs**：
```
docs(specs): add SDD optimization from superpowers spec + plan

第一個跑 spec/plan 分離（B3）規範的 SDD doc — meta-spec 規劃從 superpowers v5.1.0
借鏡 9 項優化點到我們 SDD 流程（Phase A 6 + Phase B 3）。

git add:
  resources/specs/sdd_optimization_from_superpowers_2026-05-31_spec.md
  resources/specs/sdd_optimization_from_superpowers_2026-05-31_plan.md
```

**Commit 2 — Rule + prompt templates**：
```
feat(SDD v3): integrate Iron Law / 4-status / 3-stage review

- .claude/rules/sdd-workflow.md：加 Iron Law / Red Flags / adversarial review /
  spec self-review 4 點 / step-by-step plan / spec-plan 分離 / 三段迴圈
- 新 .claude/rules/sdd-prompts/spec-reviewer.md
- 新 .claude/rules/sdd-prompts/code-quality-reviewer.md
- 改 .claude/agents/sales-coder.md：加 4 狀態 dispatch + self-review 4 類

依據：resources/specs/sdd_optimization_from_superpowers_2026-05-31_spec.md
+ 借鏡 superpowers v5.1.0 plugin（reverse-engineering）

git add:
  .claude/rules/sdd-workflow.md
  .claude/rules/sdd-prompts/spec-reviewer.md
  .claude/rules/sdd-prompts/code-quality-reviewer.md
  .claude/agents/sales-coder.md
```

**Commit 3 — CLAUDE.md + projectStructure**：
```
docs: record SDD v3 integration (superpowers borrows)

git add:
  .claude/CLAUDE.md
  resources/projectStructure/projectStructure.md
```

**Commit 4 — memory update（不入 git）**：
- `<memory>/sdd_workflow.md` rewrite v3
- `<memory>/MEMORY.md` pointer 更新（reflect v3）
- 不 commit（memory 在 ~/.claude/ 內 untracked）

---

## 8. 流程鳥瞰

```
[已完成] 主 agent 讀 superpowers 11 個檔 + 對齊 3 題 → 寫此 spec
   ↓
[此 spec 待 user 審查 approval]
   ↓
[approval] 主 agent commit spec + plan（worktree 首 commit）
   ↓
[主軌 TaskCreate 10-13 條對應 §3 各檔]
   ↓
   Task A: 寫 .claude/rules/sdd-prompts/spec-reviewer.md
   Task B: 寫 .claude/rules/sdd-prompts/code-quality-reviewer.md
   Task C: 改 .claude/rules/sdd-workflow.md（加 7 大段）
   Task D: 改 .claude/agents/sales-coder.md（加 2 段）
   Task E: 改 .claude/CLAUDE.md（小補）
   Task F: 改 <memory>/sdd_workflow.md（v3 rewrite）
   Task G: 改 <memory>/MEMORY.md pointer
   Task H: 跑 pytest 386 確認 regression net
   Task I: grep sdd-prompts 確認 cross-ref ≥ 3
   Task J: commit feat
   ↓
[階段 3b] 改 projectStructure.md + commit
   ↓
[階段 4 + 5] ExitWorktree → ff-merge → push → 手動 sync_pi.ps1 → cleanup
```
