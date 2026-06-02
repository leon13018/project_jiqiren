# SDD (Spec-Driven Development) 工作流程 — v3

> **🎯 何時讀本檔**：要寫 / 改 `myProgram/` 下**任何 `.py` code**（sales / main / tts / action / input_reader，不分規模）——動手前先走 SDD 寫 spec。

## 目錄
- 觸發條件
- Spec template（完整版 / mini）
- Spec 位置與命名
- SDD 4 階段流程
- Spec self-review 4 點
- Iron Law（完成宣告驗證）
- Adversarial 審查 pose
- 三段 subagent 迴圈（含為何 fresh-context + 模型選擇 + Status 表）
- 雙軌 TaskCreate
- Sales-coder 派發 prompt 範本
- Red Flags
- 與其他規則的關係 / Anti-patterns / 何時不必走 SDD

編寫或修改 `myProgram/` 內任何 `.py` code 前 **強制**先寫 spec 到 `resources/specs/`，主 agent 與使用者對齊後才實作，**不分規模**。完整版拆 `<name>_<date>_spec.md`（WHAT）+ `_plan.md`（HOW step-by-step），mini 版 5 行單檔。

> **Why**：主對話對齊期 context 龐雜（discussion / ambiguity / 歷史 patch），sales-coder 帶過去會被噪訊污染；fresh-context subagent 只看 spec + 必要 reference 注意力最集中。v3（2026-05-31）借鏡 superpowers v5.1.0：Iron Law 明文 / Red Flags / adversarial pose / 4 狀態 dispatch / self-review / spec-plan 分離 / 三段 subagent 迴圈。設計依據存 `resources/specs/sdd_*_spec.md` + `resources/research/SDD_best_practices_2026-05-31.md`。

---

## 觸發條件

**觸發 ✅（必寫 spec）**：任何 `myProgram/` 下 `.py` 改動，不分規模——`sales/**/*.py`（業務邏輯）/ `main.py`（wire-up）/ `tts.py`、`action.py`、`input_reader.py`（worker）。

**不觸發 ❌**：`vendor/` 廠商 SDK（禁改）｜`.claude/` 內任何檔 + 根 `CLAUDE.md`｜`resources/` 內任何檔｜`tests/sales/` 純測試補強（伴隨 prod 改動則跟 prod 走同一 spec；獨立補回歸網不需）｜`.gitignore`/`sync_pi.ps1`/`pytest.ini` 等工具設定｜純文件 / docstring / 註解 sweep（即使檔在 `myProgram/`）。

---

## Spec template — 兩種規模

### 完整版（≥ 3 行 / 跨檔 / 新功能 / 重構 / 行為變更）— 拆 spec.md + plan.md

**spec.md（WHAT，8 段）**：
1. 背景與動機（why / 現況 / 不對齊處，含 user 觀察 / Pi demo 證據）
2. 設計核心 + 行為規約（計時配置 / 主迴圈虛擬碼 / 子鏈路行為表 / pause-compensate 等）
3. 改檔範圍（高層）：列每檔 + 改動類型 + 行數估計；step-by-step 移 plan.md
4. Out of scope（明示不動，避免越界）
5. 規範與參考（派 sales-coder + 預載 SKILL + 相關引用）
6. 測試指令 + 預期結果（pytest 指令 + 預期數量）
7. Commit 規範（拆分建議 + git add 範圍 + message 範本）
8. 流程鳥瞰（ASCII）

**plan.md（HOW，step-by-step）**：每檔每 step **2-5 分鐘 / 一原子動作**，依 TDD Red-Green-Refactor 排序（寫 failing test → 跑見 FAIL → 寫最小 prod → 跑見 PASS → commit）。
**No Placeholders（禁寫）**：「TBD / TODO / implement later」「Add appropriate error handling（無具體 code）」「Write tests for the above（無實際 test）」「Similar to Step N（要 repeat code）」。
**例外**：v3 升級前既有 spec 不回填 plan.md；只對 v3 後新 spec 強制。

### Mini 版（≤ 3 行單檔純值替換 / typo / 單一 const tweak）— 5 行單檔不拆 plan
```markdown
# <task_name> — Mini SDD spec
- **檔**：`<file_path>:<line>`
- **改前**：`<before>`
- **改後**：`<after>`
- **Why**：<一句>
- **驗證**：`<pytest 指令>` / 或「Pi 端跑 X 看 Y」
```

---

## Spec 位置與命名

**統一位置**：`resources/specs/`（flat，不分 L 層 / 模組）。
- 完整版：`<short_name>_<YYYY-MM-DD>_spec.md` + `_plan.md`（同 prefix）。Mini：`<short_name>_<YYYY-MM-DD>_spec.md` 單檔。
- **拆 spec/plan 理由**：spec = 跟 user 對齊的契約（穩定）；plan = 給 sales-coder 的執行指南（隨重構演化）。派 sales-coder prompt 必含兩檔路徑。
- **Living document**：實作後行為調整 → spec 內 append 變更段；大改新開 v 版本。**不刪舊 spec**（git history + 維護對比）。

---

## SDD 4 階段流程

```
[階段 1] 主 agent 對齊 + 寫 spec / plan（不派 subagent）
  1. user 描述需求
  2. AskUserQuestion 對齊 ambiguity（按需 2-4 題）
  3. EnterWorktree
  4. 寫 spec.md（+ plan.md 若完整版）到 resources/specs/（未 commit）
  5. spec self-review 4 點 sweep（見下）
  6. AskUserQuestion：spec/plan 是否需修？
  7. approval → commit spec(+plan) doc（worktree 首 commit）

[階段 2] 派 sales-coder 實作（第 1 段 implementer）
  1. 主 agent TaskCreate 高層 checklist
  2. Agent({subagent_type:'sales-coder', prompt: spec_path + plan_path + 任務特化})
  3. sales-coder 自行 Read spec+plan → TaskCreate 內部清單 → 逐項實作 → commit
  4. 回 4-status（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）
  5. 主 agent 依 status 處理：BLOCKED/NEEDS_CONTEXT 提供 context 重派；DONE 進 3a

[階段 3a] 主 agent + spec-reviewer subagent（第 2 段）
  1. 主 agent Iron Law 自驗（pytest + branch verify）
  2. 派 spec-reviewer（fresh，prompt 用 examples/spec-reviewer-prompt.md）
  3. ✅ → 進 3b ；❌ → 派 sales-coder fix → 回 3a 重審

[階段 3b] 主 agent + code-quality-reviewer subagent（第 3 段）
  1. 派 code-quality-reviewer（fresh，prompt 用 examples/code-quality-reviewer-prompt.md）
  2. ✅ → 進 3c ；⚠️ Minor → 主 agent 判決 ；❌ Critical/Important → 派 sales-coder fix → 回 3b

[階段 3c — 條件性] 結構變動 → 更新該層 code_map / SKILL.md 路由表，commit

[階段 4 + 5] worktree 收尾
  ExitWorktree(keep) → git merge worktree-<name> --ff-only → git push origin main
  → 手動 & sync_pi.ps1 → git worktree remove + git branch -d worktree-<name>
```

**何時跳過三段迴圈**：Mini spec（≤3 行）→ 主 agent 自 patch + Iron Law，不派 subagent。Meta-task（rules/agents/memory 等非 myProgram code）→ 主 agent 自實作。

---

## Spec self-review 4 點 sweep（階段 1 寫完 spec、approval 前 fresh eyes 自掃）

1. **Placeholder scan**：「TBD/TODO/後續/模糊需求」→ 修掉。
2. **Internal consistency**：§3 改檔範圍 vs §2 設計 vs §6 測試清單 互相 contradict？
3. **Scope check**：單一可實作 plan 還是該拆分（涵蓋多獨立 subsystem → 拆 sub-spec）？
4. **Ambiguity check**：任何需求能兩種解讀？挑一個寫死。

inline 修完才 AskUserQuestion，不必 re-review。（借鏡 superpowers brainstorming "Spec Self-Review"。）

---

## Iron Law — 主 agent 完成宣告驗證

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.** 本輪未跑驗證指令，不得宣告完成 / 通過 / 全綠。

**Gate function（claim 前必跑）**：
```
1. IDENTIFY：哪個指令能證明此 claim？
2. RUN：跑完整指令（fresh, complete）
3. READ：讀完整輸出、檢查 exit code、數失敗
4. VERIFY：輸出確認 claim？ NO → 陳述實際狀態 + evidence；YES → 陳述 claim + evidence
5. ONLY THEN 宣告
```

**必跑指令對照表**：
| Claim | 必跑 | 不夠的證據 |
|---|---|---|
| pytest 全綠 | `python -m pytest tests/sales/` 看 `N passed` | 上輪結果 / sales-coder 自報 / "should pass" |
| Branch 落 worktree | `git branch --contains <SHA>` 看 `worktree-*` | git push 成功 ≠ branch 對 |
| Spec 全 cover | 逐條對照 spec §3 → 列哪 commit 對應 | "tests passing, done" |
| 改檔範圍正確 | `git diff --stat HEAD~N HEAD` | 信 sales-coder 列表 |
| Spec-reviewer ✅ | 看 subagent 回的 `Spec compliant` 字串 | 信 implementer 自報 |
| Code-quality ✅ | 看 subagent 回的 `Approved` 字串 | 跳過審查 |

違反 = 不誠實，不是效率。（借鏡 superpowers verification-before-completion。）

---

## Adversarial 審查 pose（階段 3a-3b）

Sales-coder 回報可能不完整 / 不準確 / 過度樂觀（"finished suspiciously quickly"）。審查時**禁止**信任它對「實作了什麼 / 完整度 / spec 解讀」的描述；**必做**：Read 實際 code、逐行對照 spec §3、找 extra 加料、找聲稱實作但 grep 不到的假完成。此 pose 在派 reviewer 時透過 [examples/](../examples/) 的 prompt template 強制執行（template 內含完整 禁止/必做 + 3 大類），主 agent 自審時也採此立場。

---

## 三段 subagent 迴圈

**模式**：每 spec 三 agents——sales-coder 整套改完才派 spec-reviewer，spec-reviewer ✅ 才派 code-quality-reviewer。

**為何 fresh-context reviewer（不主 agent 自審）**：
1. **新眼光**：主 agent 帶「派 sales-coder + 看回報」context；fresh subagent 只看 spec + diff，無偏見。
2. **平行驗證**：spec-reviewer + code-quality-reviewer 獨立眼光，雙重保險。
3. **覆現性**：同 prompt template，每次審查模式一致，不依賴主 agent 當輪注意力。
4. **省主 agent context**：審查 detail 不污染主對話。

**模型選擇**：
| 角色 | 模型 | 理由 |
|---|---|---|
| Implementer (sales-coder) | opus（繼承 session effort）| frontmatter `model: opus`、無 effort 欄 |
| Spec-reviewer (general-purpose) | sonnet | 對照 spec vs code，cost-effective |
| Code-quality-reviewer (general-purpose) | opus xhigh | 架構判斷，prompt 內塞 extended thinking |

**Prompt template**：spec-reviewer → [`../examples/spec-reviewer-prompt.md`](../examples/spec-reviewer-prompt.md)；code-quality-reviewer → [`../examples/code-quality-reviewer-prompt.md`](../examples/code-quality-reviewer-prompt.md)。主 agent 複製 + 填空（SHA / spec path / sales-coder 回報）。

**Status 4 選 1 + 處理表**（sales-coder 回報首行必選 1）：
| Status | 主 agent 動作 |
|---|---|
| **DONE** | 進階段 3a |
| **DONE_WITH_CONCERNS** | 讀 concerns；correctness/scope 概念→修；observation→記下進 3a |
| **NEEDS_CONTEXT** | 提供缺漏 context → 重派（同模型） |
| **BLOCKED** | (a) context 不足→提供再派 (b) 太難→升級 model (c) 太大→拆小 (d) 規格錯→升級 user |

---

## 雙軌 TaskCreate（session-scoped 不可共享）

- **主 agent 軌（高層 checklist）**：每輪 SDD 必建，典型 10-13 條——對齊 ambiguity / EnterWorktree / 寫 spec+自查+plan / approval / commit spec doc / 派 sales-coder / 依 status 處理 / Iron Law 自驗 / 派 spec-reviewer / 派 code-quality-reviewer / 3c code_map / 4+5 收尾。
- **Subagent 軌**：sales-coder 拿到 spec+plan 後自行 TaskCreate 拆內部清單（對應 plan 每檔每 step），完成回報內 echo TaskList 摘要。
- **Reviewer subagent 不必 TaskCreate**（單一任務）。

---

## Sales-coder 派發 prompt 範本

> 流程 / DoD / 回報格式 / self-review 都在 `.claude/agents/sales-coder.md`（系統提示恆載），**派發 prompt 只給任務特化、不複寫**。

```markdown
## 任務
依 SDD spec + plan 實作 <feature_name>。
- Spec：`resources/specs/<name>_<date>_spec.md`（WHAT）
- Plan：`resources/specs/<name>_<date>_plan.md`（HOW，step-by-step）
所有實作決定以 spec/plan 為準；spec 沒寫的照 karpathy「最小可驗證」，有疑義停下回報。

## 工作環境
- 已在 worktree `.claude/worktrees/<name>/`，branch `worktree-<name>`；上 commit `<SHA>` 是 spec/plan doc（不要改）
- 所有 commit 落 `worktree-<name>`，commit 後 `git branch --contains <SHA>` 自驗（落 main 停回報，Gotcha M）

## 任務特化
- commit message 範本：<...>
- git add 範圍：<明列檔名>
- 既有可 reuse helper / pattern：<spec §5 引用>

## ⛔ 邊界
- 不做 post-commit closeout（不 ExitWorktree / ff-merge / push / worktree remove）— 主 agent 收尾，你只做 編輯→commit→回報
- 不 cd 主 checkout（引發 Gotcha M）
```

> sales-coder handoff 前自查的 self-review 4 類（Completeness / Quality / Discipline / Testing）詳見 `.claude/agents/sales-coder.md` §Handoff 前 self-review。

---

## Red Flags（看到這些想法 STOP，你正在合理化）

| 想法 | 真相 |
|---|---|
| 「這太簡單不需 spec」 | 所有 myProgram/ code 都要 spec（即使 mini 5 行） |
| 「sales-coder 回報全綠了」 | 主 agent 仍要自己 Read + 跑 pytest（Iron Law） |
| 「我記得規則」 | 規則會演進，重讀本 reference |
| 「先 patch 看看再說」 | SDD 強制：先 spec → user approval → 才動 code |
| 「主 agent 自己改一下就好」 | myProgram/ code 改動屬 sales-coder 範圍，連 1 行也派 |
| 「commit 落 main 應該是巧合」 | Gotcha M 偶發確實會發生，每次 `git branch --contains` 驗 |
| 「skip pytest 沒差，反正是 docstring」 | 改 sales/ 後 Stop hook 會 block；明文跑一次省麻煩 |
| 「spec-reviewer 多此一舉」 | fresh-context 新眼光是 v3 防偷懶核心 |
| 「reviewer 找的 Minor 不重要」 | Minor 累積成技術債；至少評估再決定 |
| 「先 commit 再說，反正可 amend」 | amend 打亂 SHA 鏈，影響 spec/plan trace |
| 「user approval 是形式」 | 缺 approval 寫 code = 後續對不上重做，更慢 |

---

## 與其他規則的關係 / Anti-patterns / 何時不必走

**關係**（細節見各檔）：[dispatch.md](dispatch.md) 規模門檻決定**誰實作**（subagent vs 主 agent），SDD 決定**流程**（必有 spec），不衝突；worker/wire-up 改動既派 sales-coder 又走 SDD；[bdd-tdd.md](bdd-tdd.md) 互補（當前 dormant，plan step 內嵌 TDD 不重啟 BDD）；[worktree.md](worktree.md) / [standard-workflow.md](standard-workflow.md) 內嵌於階段 1/3c/4+5。

**Anti-patterns**：❌ Waterfall 化（spec 是 15-30 分鐘對齊產物，非寫 3 週）｜❌ Over-engineering（小 bug 修出 16 criteria；mini spec 對應）｜❌ Stale specs（living document + 階段 3c review）｜❌ Subagent in isolation 全域不一致（spec 含跨檔 invariant）｜❌ 不引入 spec-kit/BMAD/Kiro（SDD 基於既有 skill + worktree）。

**何時不必走 SDD**（除「不觸發」外）：純研究 / 探索 / 文件查詢｜CLAUDE.md/rules/memory/skill 自身修訂（主 agent 自編）｜緊急 hotfix Pi demo 當下 bug（先 patch，事後補 mini spec 記 root cause）｜既有 L0-L5 回填 spec（成本高收益低，僅新改動適用）。

---

**相關**：規格範本 `resources/specs/L4_v3_dual_timer_spec.md`（完整版 8 段範本）；reviewer prompt → [examples/](../examples/)；派發 → [dispatch.md](dispatch.md)；worktree → [worktree.md](worktree.md)；收尾 → [standard-workflow.md](standard-workflow.md)；sales-coder 契約 → `.claude/agents/sales-coder.md`；編碼準則 → invoke `andrej-karpathy-skills:karpathy-guidelines`。
