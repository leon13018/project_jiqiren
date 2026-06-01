# SDD (Spec-Driven Development) 工作流程 — v3

編寫或修改 `myProgram/` 內任何 `.py` code 之前 **強制** 先寫 spec 檔到 `resources/specs/`，主 agent 與使用者對齊後才實作，**不分規模**。Spec 一律存 `resources/specs/`；完整版拆 `<name>_<date>_spec.md`（WHAT）+ `<name>_<date>_plan.md`（HOW step-by-step），mini 版 5 行單檔。

**v3 演進**（2026-05-31）：在 v2 基礎上借鏡 superpowers v5.1.0 plugin 9 大優化（reverse-engineered）—
Iron Law 驗證明文化 / Red Flags 表 / adversarial 審查 pose / 4 狀態 dispatch / self-review checklist / spec self-review 4 點 / step-by-step plan / spec-plan 分離 / 三段 subagent 迴圈。

**Why（背景與動機）**：主對話對齊期間 context 龐雜（discussion / ambiguity 探索 / 歷史 patch），sales-coder 帶過去會被噪訊污染決策；fresh-context subagent 只看 spec + 必要 reference 注意力最集中。User 2026-05-31 提出 SDD → 同日 v2 正式化（強制 trigger + flat 結構 + 雙軌 TaskCreate + 系統 prompt 整合）→ 同日 v3 升級借鏡 superpowers v5.1.0 plugin 9 大優化點。

設計依據：
- `resources/research/SDD_best_practices_2026-05-31.md`（多源最佳實踐調研）
- `resources/specs/sdd_workflow_formalization_2026-05-31_spec.md`（v2 正式化）
- `resources/specs/sdd_optimization_from_superpowers_2026-05-31_spec.md`（v3 升級）
- 2026-05-31 user 三題對齊（L4_v3 spec 遷移 / 所有 myProgram/ trigger / 雙軌 TaskCreate）
- 2026-05-31 user 三題對齊 v3（全 Phase A + 全 Phase B + 寫 spec 走現行 SDD 實作）

---

## 觸發條件

### 觸發 ✅（必寫 spec）

- 任何 `myProgram/` 下 `.py` code 改動，**不分規模**：
  - `myProgram/sales/**/*.py`（業務邏輯）
  - `myProgram/main.py`（wire-up）
  - `myProgram/tts.py` / `action.py` / `input_reader.py`（worker 層）

### 不觸發 ❌（不需 spec）

- `myProgram/vendor/` 廠商 SDK（禁改，見 ⛔ 絕對禁止 #1）
- `.claude/` 內任何檔（hook / agents / settings / CLAUDE.md 等，結構見 code_map）
- `resources/` 內任何檔（子資料夾見 code_map）
- `tests/sales/` 純測試補強（若伴隨 prod code 改動，**跟 prod 走同一 spec**；獨立補回歸網不需）
- `.gitignore` / `sync_pi.ps1` / `pytest.ini` / `pyproject.toml` 等工具設定
- 純文件 / docstring / 註解 sweep（即使檔在 `myProgram/` 內）

---

## Spec template — 兩種規模

### 完整版（≥ 3 行 / 跨檔 / 新功能 / 重構 / 行為變更）

**v3 起拆兩份 doc**（spec.md = WHAT / plan.md = HOW）— 見下方「Spec 位置與命名」。

#### spec.md（WHAT，8 段）

1. **背景與動機** — why / 現況 / 不對齊處（含 user 觀察 / Pi demo transcript 證據）
2. **設計核心 + 行為規約** — 計時器配置 / 主迴圈虛擬碼 / 子鏈路行為表 / pause-compensate 等
3. **改檔範圍（高層）** — 列每檔 + 概述改動類型（新增 / 修改 / 刪除）+ 行數估計；細節 step-by-step 移到 plan.md
4. **Out of scope** — 明示不動（避免 sales-coder 越界）
5. **規範與參考** — 派發 sales-coder + 預載 SKILL + 相關 memory 引用
6. **測試指令 + 預期結果** — pytest 指令 + 預期數量
7. **Commit 規範** — 拆分建議 + git add 範圍 + commit message 範本
8. **流程鳥瞰** — ASCII 流程圖

#### plan.md（HOW，step-by-step）

每檔加 step-by-step plan，每 step **2-5 分鐘 / 一個原子動作**，依 TDD Red-Green-Refactor 排序：

````markdown
**檔 X：myProgram/sales/states/lN.py**

- [ ] Step 1：寫 failing test
  `tests/sales/test_states.py::test_xxx`

  ```python
  def test_xxx():
      assert function(input) == expected
  ```

- [ ] Step 2：跑 test 確認 FAIL
  `python -m pytest tests/sales/test_states.py::test_xxx -v`
  預期：FAIL with `AttributeError`

- [ ] Step 3：寫最小 prod code

  ```python
  def function(input):
      return expected
  ```

- [ ] Step 4：跑 test 確認 PASS

- [ ] Step 5：commit
  `git commit -m "feat(lN): add xxx"`
````

**No Placeholders**（plan failures，禁寫）：
- ❌ "TBD" / "TODO" / "implement later" / "fill in details"
- ❌ "Add appropriate error handling" / "handle edge cases"（無具體 code）
- ❌ "Write tests for the above"（無實際 test code）
- ❌ "Similar to Step N"（要 repeat code，engineer 可能跳讀）

**例外**：v3 升級之前的既有 spec（L4_v3 / sdd_workflow_formalization / sdd_optimization）**不回填 plan.md**；只對 v3 後新 spec 強制適用。

### Mini 版（≤ 3 行單檔純值替換 / typo / 單一 const tweak）

5 行模板，**不拆 plan**：

```markdown
# <task_name> — Mini SDD spec

- **檔**：`<file_path>:<line_number>`
- **改前**：`<before_code>`
- **改後**：`<after_code>`
- **Why**：<reason，一句話>
- **驗證**：`<pytest_command>` / 或「Pi 端跑 X 看 Y」
```

---

## Spec 位置與命名

**統一位置**：`resources/specs/`（flat 結構，不分 L 層 / 不分模組）

**命名規範**：
- 完整版：`<short_name>_<YYYY-MM-DD>_spec.md` + `<short_name>_<YYYY-MM-DD>_plan.md`（兩檔同 prefix）
- Mini 版：`<short_name>_<YYYY-MM-DD>_spec.md` 單檔

**為何拆 spec / plan**：
- spec = 跟 user 對齊的契約（穩定）
- plan = 給 sales-coder 的執行指南（隨重構演化）
- 派 sales-coder prompt 內必含兩份檔路徑（spec_path + plan_path）

**Spec 為 living document**：實作後若行為調整 → 在 spec 內 append 變更段；大改動則新開 v 版本 spec。**不刪舊 spec**（git history + 後續維護時對比參考）。

---

## SDD 4 階段流程

```
[階段 1] 主 agent 對齊 + 寫 spec / plan（不派 subagent）
  ↓
  1. user 描述需求
  2. 主 agent AskUserQuestion 對齊 ambiguity（按需，2-4 題）
  3. EnterWorktree
  4. 主 agent 寫 spec.md（+ plan.md 若完整版）到 resources/specs/（**未 commit**）
  5. 主 agent spec self-review 4 點 sweep（見下方）
  6. AskUserQuestion: spec / plan 是否需修？
  7. approval → 主 agent commit spec (+ plan) doc（worktree 首 commit）

[階段 2] 派發 sales-coder 實作（第 1 段 implementer）
  ↓
  1. 主 agent TaskCreate 高層 checklist
  2. Agent({subagent_type: 'sales-coder', prompt: 含 spec_path + plan_path + 任務特化規則})
  3. sales-coder 自行 Read spec + plan → TaskCreate 內部清單 → 逐項實作 → commit
  4. sales-coder 回 4-status 1 選（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）
  5. 主 agent 依 status 處理：BLOCKED/NEEDS_CONTEXT 提供 context 重派；DONE 進階段 3

[階段 3a] 主 agent + spec-reviewer subagent（第 2 段）
  ↓
  1. 主 agent Iron Law 自驗（見下方）— 跑 pytest + branch verify
  2. 派 spec-reviewer subagent（fresh context，prompt 用 examples/spec-reviewer-prompt.md）
  3. ✅ Spec compliant → 進階段 3b
  4. ❌ Issues → 派 sales-coder fix → 回階段 3a 重審

[階段 3b] 主 agent + code-quality-reviewer subagent（第 3 段）
  ↓
  1. 派 code-quality-reviewer subagent（fresh context，prompt 用 examples/code-quality-reviewer-prompt.md）
  2. ✅ Approved → 進階段 3c
  3. ⚠️ Minor concerns → 主 agent 判決：接受 / 自己 fix / 派 sales-coder fix
  4. ❌ Critical/Important → 派 sales-coder fix → 回階段 3b 重審

[階段 3c — 條件性] 結構變動 → 更新 code_map / skill_code_map
  ↓
  1. 結構變動（新 spec / 新 folder / 新 test 檔）→ 更新 .claude/code_map.md
  2. 主 agent commit 上述變動

[階段 4 + 5] worktree 收尾
  ↓
  1. ExitWorktree(action="keep")
  2. git merge worktree-<name> --ff-only
  3. git push origin main
  4. 手動 & sync_pi.ps1（PowerShell tool；統一規則，hook 自動跑時為 idempotent no-op）
  5. git worktree remove + git branch -d worktree-<name>
```

**何時跳過三段 subagent 迴圈（階段 3a-3b 簡化）：**

- **Mini spec**（≤ 3 行）：主 agent 自己 patch + Iron Law verify，不派任何 subagent
- **本 meta-task 類**（rules / agents / memory 改動非 myProgram/ code）：主 agent 自實作，不派 subagent

---

## Spec self-review 4 點 sweep（階段 1 寫完 spec 後）

主 agent 寫完 spec → AskUserQuestion approval 前，**先 fresh eyes 自掃**：

1. **Placeholder scan** — 有 "TBD" / "TODO" / "後續" / 模糊需求？修掉
2. **Internal consistency** — §3 改檔範圍 vs §2 設計核心 vs §6 測試清單 互相 contradict？
3. **Scope check** — spec 涵蓋是否單一可實作 plan，還是該拆分？（若 spec 涵蓋多個獨立 subsystem，建議拆 sub-spec 每個獨立可實作）
4. **Ambiguity check** — 任何需求能被兩種解讀？挑一個寫死

inline 修完才 AskUserQuestion。**不必 re-review**，修了就走。

借鏡來源：superpowers `skills/brainstorming/SKILL.md` "Spec Self-Review" 段。

---

## Iron Law — 主 agent 完成宣告驗證

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE**

若本輪未跑驗證指令，**不得宣告完成 / 通過 / 全綠**。

借鏡來源：superpowers `skills/verification-before-completion/SKILL.md`。

### Gate function（claim 前必跑）

```
BEFORE 宣告任何 status / 滿意 / 完成：

1. IDENTIFY: 哪個指令能證明此 claim？
2. RUN: 跑完整指令（fresh，complete）
3. READ: 讀完整輸出，檢查 exit code，數失敗
4. VERIFY: 輸出是否確認 claim？
   - NO  → 陳述實際狀態 + evidence
   - YES → 陳述 claim + evidence
5. ONLY THEN: 宣告 claim
```

### 必跑指令對照表

| Claim | 必跑指令 | 不夠的證據 |
|---|---|---|
| pytest 全綠 | `python -m pytest tests/sales/` 看見 `N passed` | 上輪結果 / sales-coder 回報 / "should pass" |
| Branch 落 worktree | `git branch --contains <SHA>` 看見 `worktree-*` | git push 成功 ≠ branch 對 |
| Spec 全 cover | 逐條對照 spec §3 → 列哪 commit 對應 | "tests passing, done" |
| 改檔範圍正確 | `git diff --stat HEAD~N HEAD` | 信 sales-coder 列表 |
| Spec-reviewer ✅ | 看 subagent 回報的 `Spec compliant` 字串 | 信 implementer 自報 |
| Code-quality ✅ | 看 subagent 回報的 `Approved` 字串 | 跳過審查 |

違反 = 不誠實，不是效率。

---

## Adversarial 審查 pose（階段 3a-3b）

Sales-coder 回報可能不完整 / 不準確 / 過度樂觀（"finished suspiciously quickly"）。
主 agent + reviewer subagent 審查時：

**禁止：**
- 信任 sales-coder 對「實作了什麼」的描述
- 信任 sales-coder 對「完整度」的宣告
- 接受 sales-coder 對 spec 的解讀

**必做：**
- 讀實際改的 code（Read tool）
- 逐行對照 spec §3 vs 實作
- 找 sales-coder 沒提的「extra 加料」
- 找 sales-coder 聲稱實作但 grep 不到的「missing 假完成」

這個 pose 在派 spec-reviewer / code-quality-reviewer 時透過 prompt template 強制；主 agent 自己審查時也採此立場。

借鏡來源：superpowers `skills/subagent-driven-development/spec-reviewer-prompt.md`。

---

## 三段 subagent 迴圈（C1 詳解）

**Superpowers 模式**：每 task 三 agents（impl + spec-rev + code-rev）。
**我們 scale adaptation**：每 spec 三 agents（sales-coder 整套改完才派 spec-reviewer，spec-reviewer ✅ 才派 code-quality-reviewer）。

### 為何 fresh-context reviewer subagent（不主 agent 自己審）

1. **新眼光**：主 agent 帶著「派 sales-coder + 看到回報」context；fresh subagent 只看 spec + diff，無偏見
2. **平行驗證**：spec-reviewer + code-quality-reviewer 獨立眼光，雙重保險
3. **覆現性**：每次審查模式一致（同 prompt template），不依賴主 agent 當輪注意力
4. **省主 agent context window**：審查 detail 不污染主對話

### 模型選擇（adapt superpowers Model Selection）

| 角色 | 模型 | 理由 |
|---|---|---|
| Implementer (sales-coder) | opus（effort 繼承當前 session）| frontmatter `model: opus`、無 effort 欄位 |
| Spec-reviewer (general-purpose) | sonnet | 任務簡單：對照 spec vs code，cost-effective |
| Code-quality-reviewer (general-purpose) | opus xhigh | 架構判斷，prompt 內塞 extended thinking |

### Prompt template 集中存放

| Template | 路徑 | 用途 |
|---|---|---|
| spec-reviewer | [`examples/spec-reviewer-prompt.md`](../examples/spec-reviewer-prompt.md) | 階段 3a 派 spec-reviewer subagent 用 |
| code-quality-reviewer | [`examples/code-quality-reviewer-prompt.md`](../examples/code-quality-reviewer-prompt.md) | 階段 3b 派 code-quality-reviewer subagent 用 |

主 agent 派 reviewer 時複製對應 template + 填空（SHA / spec path / sales-coder 回報）。

### Status 4 選 1 + 處理表

Sales-coder 必回 1 個 status（依 [dispatch.md](dispatch.md) 規模門檻 + sales-coder.md frontmatter 強制）：

| Status | 主 agent 動作 |
|---|---|
| **DONE** | 進階段 3a（spec-reviewer） |
| **DONE_WITH_CONCERNS** | 讀 concerns；correctness/scope 概念→修；observation→記下進階段 3a |
| **NEEDS_CONTEXT** | 提供缺漏 context → 重派 sales-coder（同模型） |
| **BLOCKED** | 評估 blocker：(a) context 不足 → 提供再派 (b) 任務太難 → 升級 model (c) 任務太大 → 拆小 (d) 規格錯 → 升級 user |

---

## 雙軌 TaskCreate（主 agent + subagent 各自）

session-scoped 不可共享：主 agent 維護高層（含三段 reviewer 步驟）/ subagent 維護內部實作清單（依 plan 每 step）/ reviewer subagent 不必 TaskCreate（單一任務）。

### 主 agent 軌（高層 checklist）

每輪 SDD 任務必建主 agent TaskList，**v3 起新增三段 reviewer 步驟**，典型 10-13 條：

| Task | 動作 |
|---|---|
| 1 | 主 agent AskUserQuestion 對齊 ambiguity（可能多輪） |
| 2 | EnterWorktree |
| 3 | 寫 spec doc + 自查 4 點 + plan doc（若完整版） |
| 4 | AskUserQuestion: spec/plan approval |
| 5 | Commit spec + plan doc（worktree 首 commit） |
| 6 | 派 sales-coder（implementer，傳 spec_path + plan_path + 任務特化） |
| 7 | sales-coder 回 status → 主 agent 依 status 處理 |
| 8 | 主 agent Iron Law 自驗（pytest + branch verify） |
| 9 | 派 spec-reviewer subagent → ✅ / ❌ 處理 |
| 10 | 派 code-quality-reviewer subagent → ✅ / ⚠️ / ❌ 處理 |
| 11 | 階段 3c：code_map 更新 + commit |
| 12 | 階段 4+5：ExitWorktree + ff-merge + push + sync + cleanup |

### Subagent 軌（sales-coder 內部實作清單）

Sales-coder 拿到 spec + plan 後**自行 TaskCreate** 拆內部清單，對應 plan 每檔每 step。每完成一 step → TaskUpdate completed。

**雙軌不共享**：TaskCreate 是 session-scoped；各自管理。Subagent 完成後回報內 echo 其 TaskList 摘要。

**Reviewer subagent 不必 TaskCreate**：只做 1 件事（審查），不需任務拆解。

---

## Sales-coder 派發 prompt 範本

```markdown
## 任務

依 SDD spec + plan 實作 <feature_name>。

**Spec / Plan 檔（必先完整讀）**：
- Spec：`resources/specs/<spec_name>_spec.md`（WHAT）
- Plan：`resources/specs/<spec_name>_plan.md`（HOW，step-by-step）

Spec 涵蓋設計動機 / 行為規約 / 改檔範圍 / out-of-scope / 參考。
Plan 涵蓋每檔 step-by-step + 完整 test/impl code + commit msg。
**所有實作決定以 spec/plan 為準**；spec 沒寫的照 karpathy「最小可驗證」原則。

## 工作環境

- 你已在 worktree `.claude/worktrees/<name>/`，branch `worktree-<name>`
- 上 commit `<SHA>` 是主 agent 寫的 spec/plan doc（**不要改 spec/plan**）
- 你的所有 commit 必須落在 `worktree-<name>` 分支（commit 後 `git branch --contains <SHA>` 驗證；落 main 立刻停回報，防 Gotcha M）

## 強制流程

1. **Spec/Plan first**：Read 兩份 doc → TaskCreate 拆內部清單（對應 plan 每檔每 step）
2. **先列再做**：Read 現有檔後，列出「我要改 X / 加 Y / 刪 Z」清單給主 agent 看；確認與 spec 一致才開始 Edit
3. **TDD Red-Green-Refactor**：依 plan 每 step 順序，先 RED 才 GREEN
4. **每改完跑 pytest**：不累積多改動才跑
5. **commit 前自檢**：`git status` + `git diff --cached` + `git branch --show-current`
6. **規格衝突必停**：spec/plan 跟現有 code 衝突時，停下回報主 agent
7. **fail 必停**：pytest fail 立刻回報，不硬塞 prod code 試圖通過
8. **Self-review 4 類 handoff 前自查**（見 .claude/agents/sales-coder.md §SDD 任務協議）

## Definition of done

- pytest 全綠（指令見 spec §6）
- 我列的 spec §X 全部 covered
- `git branch --contains <最後 SHA>` 落 worktree branch
- commit message 含 spec 引用（路徑 + 段落號）

## 回報格式（Status 強制 4 選 1，見 sales-coder.md）

開頭必選 1 個 status：DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT

後接：改動清單 / 測試對比 / pytest 輸出 / Commit SHA / branch verify / 偏離 / TaskList 摘要
```

---

## Self-review 4 類（sales-coder handoff 前自查）

Sales-coder handoff 前自查找問題立刻修：**Completeness / Quality / Discipline / Testing** 四類（詳見 `.claude/agents/sales-coder.md` §SDD 任務協議）。

---

## Red Flags（看到這些想法 STOP，你正在合理化）

借鏡來源：superpowers `skills/using-superpowers/SKILL.md` Red Flags table。

| 想法 | 真相 |
|---|---|
| 「這太簡單不需 spec」 | 我們強制所有 myProgram/ code 都要 spec（即使 mini 5 行） |
| 「sales-coder 回報全綠了」 | 主 agent 仍要自己 Read + 跑 pytest verify（Iron Law） |
| 「我記得規則」 | 規則會演進，重讀本 reference |
| 「先 patch 看看再說」 | SDD 強制：先 spec → user approval → 才動 code |
| 「主 agent 自己改一下就好」 | myProgram/ code 改動屬 sales-coder 範圍，連 1 行也派 |
| 「commit 落 main 應該是巧合」 | Gotcha M 偶發 bug 確實會發生，每次 `git branch --contains` 驗 |
| 「skip pytest 沒差，反正是 docstring」 | 改 sales/ 後 Stop hook 會 block；明文跑一次省麻煩 |
| 「spec-reviewer 多此一舉」 | fresh-context 新眼光是 v3 防 sales-coder 偷懶的核心 |
| 「reviewer 找的 Minor 不重要」 | Minor 累積成技術債；至少評估再決定 |
| 「先 commit 再說，反正可以 amend」 | amend 會打亂 SHA 鏈，影響 spec/plan trace |
| 「user approval 是形式」 | 缺 approval 寫 code = 後續發現對不上重做，更慢 |
| 「sales-coder 已經跑 pytest 了」 | sales-coder 在 worktree 內跑，可能跟主 agent state 不同；自己再跑 |

---

## SDD 與其他規則的關係

| 規則 | 關係 |
|---|---|
| [dispatch.md](dispatch.md) §規模門檻 | **不衝突**：SDD spec 強制適用，但「超級小改動主 agent 自己 patch」仍生效（mini spec + 主 agent patch + verify）。dispatch 規模門檻決定誰實作（subagent vs 主 agent），SDD 決定流程（必有 spec） |
| [dispatch.md](dispatch.md) §worker-level changes | **強化**：worker / wire-up 改動既要派 sales-coder、又要走 SDD spec + 三段審查 |
| [bdd-tdd.md](bdd-tdd.md) | **互補**：BDD = scenarios / TDD = 測試先行 / SDD = 實作前契約。新增 sales/ 業務邏輯時 BDD+TDD 重啟 → spec/plan 寫 step-by-step TDD。當前 BDD+TDD dormant；plan step-by-step 內嵌 TDD 不重啟 BDD |
| [worktree.md](worktree.md) | **內嵌**：SDD 階段 1 EnterWorktree、階段 3c commit、階段 4+5 收尾 走既有 5 階段 |
| [standard-workflow.md](standard-workflow.md) | **內嵌**：階段 4 git 收尾 5 步即 standard workflow 內核 |
| [dispatch.md](dispatch.md) §wave-workflow 6 招 | **互補**：wave 6 招（先列再做 / 每改完跑 pytest / commit 前自檢 / verbose / 規格衝突必停 / fail 必停）適用 sales-coder；三段迴圈是迴圈外加層 |

---

## Anti-patterns（高層原則，依 research §5）

- ❌ **Waterfall 化** — spec 寫 3 週才開始 code；本規則 spec/plan 是 15-30 分鐘對齊產物
- ❌ **Over-engineering** — 小 bug 修出 16 acceptance criteria；mini spec template 對應此防護
- ❌ **Stale specs** — 實作後不回頭 sync spec；living document 原則 + 階段 3c 提醒 review
- ❌ **Subagent in isolation → globally inconsistent** — spec 必須含跨檔 invariant 明示
- ❌ **Agent adherence / laziness** — 三段 subagent 迴圈 + 主 agent Iron Law 是必要安全網
- ❌ **雙寫**（既有規範 + 新 SDD framework）— Project_01 SDD 基於既有 `project-01-workflow` skill references + worktree，**不引入** spec-kit / BMAD / Kiro

---

## 何時不必走 SDD（除「不觸發」條款外的例外）

- **純研究 / 探索 / 文件查詢** → 不必 spec
- **CLAUDE.md / rules / memory 自身修訂** → 主 agent 自行編輯（含本規則本身的後續維護）
- **緊急 hotfix Pi demo 當下踩到的 bug**（時間壓力）→ 可先 patch，事後補 mini spec 記錄 root cause
- **既有 L0-L5 業務邏輯回填 SDD spec** → 不必（成本高收益低，僅對新改動適用）

---

## 相關文檔 / memory

- 規格範本：`resources/specs/L4_v3_dual_timer_spec.md`（完整版 8 段範本，v2 形式單檔；首個業務 code 跑 SDD，2026-05-31 從 plans/ 遷移）
- 自身範本：`resources/specs/sdd_workflow_formalization_2026-05-31_spec.md`（v2 meta-spec）
- v3 升級 spec：`resources/specs/sdd_optimization_from_superpowers_2026-05-31_spec.md`（首個跑 v3 流程的 spec doc，meta-spec 正式化 v3 升級自身）
- 設計依據：`resources/research/SDD_best_practices_2026-05-31.md`（多源最佳實踐，Anthropic 官方 / 社群插件 / 思想家三源整合）
- Reviewer prompt templates：[`examples/spec-reviewer-prompt.md`](../examples/spec-reviewer-prompt.md) / [`examples/code-quality-reviewer-prompt.md`](../examples/code-quality-reviewer-prompt.md)（主 agent 派 reviewer 時複製 + 填空 SHA / spec path / sales-coder 回報）
- 派發協議：[dispatch.md](dispatch.md)
- Worktree：[worktree.md](worktree.md)
- 標準收尾：[standard-workflow.md](standard-workflow.md)
- Sales-coder 自訂 subagent：`.claude/agents/sales-coder.md`（含 SDD 任務協議段 + 4 狀態 + self-review 4 類）
- 編寫程式碼準則：invoke `andrej-karpathy-skills:karpathy-guidelines` SKILL
