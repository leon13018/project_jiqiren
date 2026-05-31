# SDD (Spec-Driven Development) 工作流程

編寫或修改 `myProgram/` 內任何 `.py` code 之前 **強制** 先寫 spec 檔到 `resources/specs/`，主 agent 與使用者對齊後才實作。

設計依據：`resources/research/SDD_best_practices_2026-05-31.md`（多源最佳實踐調研）+ 2026-05-31 user 三題對齊（L4_v3 spec 遷穻 / 所有 myProgram/ trigger / 雙軌 TaskCreate）。

---

## 觸發條件

### 觸發 ✅（必寫 spec）

- 任何 `myProgram/` 下 `.py` code 改動，**不分規模**：
  - `myProgram/sales/**/*.py`（業務邏輯）
  - `myProgram/main.py`（wire-up）
  - `myProgram/tts.py` / `action.py` / `input_reader.py`（worker 層）

### 不觸發 ❌（不需 spec）

- `myProgram/vendor/` 廠商 SDK（禁改，見 ⛔ 絕對禁止 #1）
- `.claude/` 內任何檔（rules / hook / agents / settings / CLAUDE.md）
- `resources/` 內任何檔（plans / specs / architecture / reviews / research / projectStructure / pineedtodo / examples）
- `tests/sales/` 純測試補強（若伴隨 prod code 改動，**跟 prod 走同一 spec**；獨立補回歸網不需）
- `.gitignore` / `sync_pi.ps1` / `pytest.ini` / `pyproject.toml` 等工具設定
- 純文件 / docstring / 註解 sweep（即使檔在 `myProgram/` 內）

---

## Spec template — 兩種規模

### 完整版（≥ 3 行 / 跨檔 / 新功能 / 重構 / 行為變更）

8 段結構（沿用 `resources/specs/L4_v3_dual_timer_spec.md` 範本）：

1. **背景與動機** — why / 現況 / 不對齊處（含 user 觀察 / Pi demo transcript 證據）
2. **設計核心 + 行為規約** — 計時器配置 / 主迴圈虛擬碼 / 子鏈路行為表 / pause-compensate 等
3. **改檔範圍** — 每檔細節 + 行數估計 + 新增 / 修改 / 刪除分類
4. **Out of scope** — 明示不動（避免 sales-coder 越界）
5. **規範與參考** — 派發 sales-coder + 預載 SKILL + 相關 memory 引用
6. **測試指令 + 預期結果** — pytest 指令 + 預期數量 + 新增 test 清單
7. **Commit 規範** — 拆分建議 + git add 範圍 + commit message 範本
8. **流程鳥瞰** — ASCII 流程圖

### Mini 版（≤ 3 行單檔純值替換 / typo / 單一 const tweak）

5 行模板：

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

**命名規範**：`<short_name>_<YYYY-MM-DD>_spec.md`
- 例：`sdd_workflow_formalization_2026-05-31_spec.md`
- 例：`L4_v3_dual_timer_spec.md`（既有遷穻 spec，無日期後綴沿用）
- 未來新 spec 一律加日期，避免同主題多版本撞檔（如 `L4_v4_xxx_2026-06-15_spec.md`）

**Spec 為 living document**：實作後若行為調整 → 在 spec 內 append 變更段；大改動則新開 v 版本 spec。**不刪舊 spec**（git history + 後續維護時對比參考）。

---

## SDD 4 階段流程

```
[階段 1] 主 agent 對齊 + 寫 spec（不派 subagent）
  ↓
  1. user 描述需求
  2. 主 agent AskUserQuestion 對齊 ambiguity（按需，2-4 題）
  3. EnterWorktree
  4. 主 agent 寫 spec 到 resources/specs/<spec_name>.md（**未 commit**）
  5. AskUserQuestion: spec 是否需修？
  6. approval → 主 agent commit spec doc（worktree 首 commit）

[階段 2] 派發 sales-coder（純 prod code 任務）
  ↓
  1. 主 agent TaskCreate 高層 checklist（含「commit spec」「派 sales-coder」「審查」「projectStructure」「收尾」等大步驟）
  2. Agent({subagent_type: 'sales-coder', prompt: 包含 spec 檔路徑 + 任務特化規則})
  3. sales-coder 自行 Read spec → TaskCreate 內部清單（按 spec §3「改檔範圍」拆）→ 逐項實作 → commit

[階段 3] 主 agent 審查
  ↓
  1. Read worktree 內所有改動的檔
  2. 跑 pytest 自驗
  3. git branch --contains <SHA> 驗 Gotcha M（commit 應落 worktree-* 非 main）
  4. 不合規退回 sales-coder / 合規進階段 3b

[階段 3b — 條件性] projectStructure 更新（新 spec / 新 folder / 新 test 檔）
  ↓
  1. Read resources/projectStructure/projectStructure.md
  2. 加新檔 / 改職責表 / append 更新紀錄
  3. 主 agent commit projectStructure 變動（worktree 末 commit）

[階段 4 + 5] worktree 收尾
  ↓
  1. ExitWorktree(action="keep")
  2. git merge worktree-<name> --ff-only
  3. git push origin main
  4. 手動 & sync_pi.ps1（PowerShell tool；統一規則，hook 自動跑時為 idempotent no-op）
  5. git worktree remove + git branch -d worktree-<name>
```

---

## 雙軌 TaskCreate（主 agent + subagent 各自）

### 主 agent 軌（高層 checklist）

每輪 SDD 任務必建主 agent TaskList，典型 7-10 條：

| Task | 動作 |
|---|---|
| 1 | 主 agent AskUserQuestion 對齊 ambiguity（可能多輪） |
| 2 | EnterWorktree |
| 3 | 寫 spec doc + AskUserQuestion approval |
| 4 | Commit spec doc（worktree 首 commit） |
| 5 | 派 sales-coder（傳 spec 路徑 + 任務特化規則） |
| 6 | 審查 sales-coder 產出（Read 檔 + 跑 pytest + branch verify） |
| 7 | 階段 3b：projectStructure 更新 + commit |
| 8 | 階段 4+5：ExitWorktree + ff-merge + push + sync + cleanup |

### Subagent 軌（sales-coder 內部實作清單）

Sales-coder 拿到 spec 後**自行 TaskCreate** 拆內部清單，對應 spec §3「改檔範圍」每檔 / §3.3（若為完整版 spec）的測試清單每條。每完成一檔 / 一個 scenario → TaskUpdate completed。

**雙軌不共享**：TaskCreate 是 session-scoped；主 agent 看不到 subagent 的 task、subagent 看不到主 agent 的 task。各自管理。Subagent 完成後在回報內 echo 其 TaskList 摘要（"我跑了哪幾條 task"）。

---

## Sales-coder 派發 prompt 範本

```markdown
## 任務

依 SDD spec 實作 <feature_name>。

**Spec 檔（必先完整讀）**：
`resources/specs/<spec_name>.md`

Spec 涵蓋設計動機 / 行為規約 / 改檔範圍 / 測試清單 / commit 拆分。
**所有實作決定以 spec 為準**；spec 沒寫的照 karpathy「最小可驗證」原則。

## 工作環境

- 你已在 worktree `.claude/worktrees/<name>/` 內，branch `worktree-<name>`
- 上一個 commit `<SHA>` 是主 agent 寫的 spec doc（**不要改 spec**）
- 你的所有 commit 必須落在 `worktree-<name>` 分支（commit 後跑 `git branch --contains <SHA>` 驗證；落 main 立刻停下回報，防 Gotcha M）

## 強制流程

1. **Spec first**：Read spec 檔 → TaskCreate 拆內部實作清單（對應 spec §3 + §3.3）
2. **先列再做**：Read 現有檔後，在回報內列出「我要改 X / 加 Y / 刪 Z」清單給主 agent 看；確認與 spec 一致後才開始 Edit
3. **TDD Red-Green-Refactor**（若 spec §3.3 含測試清單）
4. **每改完跑 pytest**：不要累積多個改動才跑
5. **commit 前自檢**：`git status` + `git diff --cached` + `git branch --show-current`
6. **規格衝突必停**：spec 跟現有 code 衝突時，停下回報主 agent
7. **fail 必停**：pytest fail 立刻回報，不硬塞 prod code 試圖通過

## Definition of done

- pytest 全綠（指令見 spec §6）
- 我列的 spec §X 全部 covered（在回報內列出每條 spec 項目對應的 commit）
- `git branch --contains <最後 SHA>` 落 worktree branch
- commit message 含 spec 引用（路徑 + 段落號）

## 回報格式

1. 改動清單（每檔行數 + diff 摘要）
2. 測試數量對比（實作前 X → 實作後 Y）
3. pytest 最終輸出尾端 5-10 行
4. Commit SHA 清單（首行訊息）
5. `git branch --contains <最後 SHA>` 證明
6. 與 spec 偏離（如有）+ 理由
7. **TaskList 摘要**：你拆了幾條內部 task、各自對應 spec 哪段
```

---

## SDD 與其他規則的關係

| 規則 | 關係 |
|---|---|
| [[dispatch-threshold-by-change-size]] | **不衝突**：SDD spec 強制適用，但「超級小改動主 agent 自己 patch」仍生效（spec 是 mini 版 + 主 agent 寫 spec + 主 agent 自己 patch + verify） |
| [[worker-level-changes-dispatch-sales-coder]] | **強化**：worker / wire-up 改動既要派 sales-coder、又要走 SDD spec |
| [[bdd-tdd-workflow]] | **互補**：BDD 是「需求 scenarios」/ TDD 是「測試先行」/ SDD 是「實作前完整契約」。新增 sales/ 業務邏輯時 BDD+TDD 重啟 → spec §3.3 寫測試清單 → sales-coder 走 Red-Green-Refactor |
| [[worktree-workflow]] | **內嵌**：SDD 階段 1 EnterWorktree、階段 3b commit、階段 4+5 收尾 全部走既有 worktree 5 階段 |
| [[standard-workflow]] | **內嵌**：階段 4 的 git 收尾 5 步即 standard workflow 內核 |

---

## Anti-patterns（依 research §5）

- ❌ **Waterfall 化** — spec 寫 3 週才開始 code；本規則 spec 是 15-30 分鐘對齊產物，不是大文件
- ❌ **Over-engineering** — 小 bug 修出 16 acceptance criteria；mini spec template 對應此防護
- ❌ **Stale specs** — 實作後不回頭 sync spec；living document 原則 + 階段 3b 提醒 review
- ❌ **Subagent in isolation → globally inconsistent** — spec 必須含跨檔 invariant 明示
- ❌ **Agent adherence / laziness** — 兩段審查（spec compliance → code quality）+ 主 agent 跑 pytest 是必要安全網
- ❌ **雙寫**（既有 rules + 新 SDD framework）— Project_01 SDD 流程基於既有 `.claude/rules/` + memory + worktree workflow，**不引入** spec-kit / BMAD / Kiro

---

## 何時不必走 SDD（除「不觸發」條款外的例外）

- **純研究 / 探索 / 文件查詢** → 不必 spec
- **CLAUDE.md / rules / memory 自身修訂** → 主 agent 自行編輯（含本規則本身的後續維護）
- **緊急 hotfix Pi demo 當下踩到的 bug**（時間壓力）→ 可先 patch，事後補 mini spec 記錄 root cause
- **既有 L0-L5 業務邏輯回填 SDD spec** → 不必（成本高收益低，僅對新改動適用）

---

## 相關文檔 / memory

- 規格範本：`resources/specs/L4_v3_dual_timer_spec.md`（完整版 8 段範本）
- 自身範本：`resources/specs/sdd_workflow_formalization_2026-05-31_spec.md`（meta-spec，正式化本流程的 spec）
- 設計依據：`resources/research/SDD_best_practices_2026-05-31.md`（多源最佳實踐）
- 背景：memory `sdd-workflow`
- 派發協議：`.claude/rules/subagent-dispatch-protocol.md` + memory `subagent-dispatch`
- Worktree：`.claude/rules/worktree-workflow.md` + memory `worktree-workflow`
- 標準收尾：`.claude/rules/standard-workflow.md` + memory `standard-workflow`
- Sales-coder 自訂 subagent：`.claude/agents/sales-coder.md`（含 SDD 任務協議段）
