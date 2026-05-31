# SDD 工作流程正式化 — SDD 規格書（meta-spec）

> **狀態**：規劃中（2026-05-31 提出）
> **這是 meta-spec**：用本流程正式化「SDD 流程」自身 — 第一個跑 `resources/specs/` 新規範的 spec doc。
> **依據對齊**：本 SDD 流程設計來自 `resources/research/SDD_best_practices_2026-05-31.md` §6 對 Project_01 的具體建議 + 2026-05-31 user 三題對齊答案（L4_v3 遷穻 / 所有 myProgram/ code trigger / 雙軌 TaskCreate）

---

## 1. 背景與動機

### 1.1 現況（2026-05-31 session 結束時）

| 既有產出 | 位置 | 說明 |
|---|---|---|
| `sdd-workflow` memory | `<memory>/sdd_workflow.md` | 流程口述記錄（極簡版，未含「每次都寫 spec」強制條款） |
| L4 v3 spec doc | `resources/plans/業務程式邏輯規劃/L4_v3_dual_timer_spec.md` | 首次走 SDD 的產出，混在「業務邏輯規格」folder 內 |
| SDD 多源調研報告 | `resources/research/SDD_best_practices_2026-05-31.md` | 完整 best practices benchmark + Project_01 具體建議 |

**問題：**
1. SDD 流程**規範等級不夠**：只有 memory（背景），無 `.claude/rules/` 規則檔（流程強制），CLAUDE.md 無 pointer
2. Spec 檔**散落混置**：L4_v3 落在「業務邏輯規格」folder，未來其他 spec 不知該放哪
3. **觸發條件未明示**：「什麼改動要寫 spec」沒寫死規則
4. **TodoList 機制缺**：未明示主 agent + subagent 各自用 TaskCreate 追蹤
5. **sales-coder 系統 prompt 未提及讀 spec / 跑 TaskCreate**：subagent 接到 prompt 才知道，不是 frontmatter 預載行為

### 1.2 user 2026-05-31 三題對齊結論

| 題 | 選擇 |
|---|---|
| L4_v3 spec 遷穻？ | **git mv 到 `resources/specs/`**，同步改 l4.py / timing.py docstring 引用 |
| 觸發範圍？ | **所有 `myProgram/` code 不分規模**（超級小改動也寫 mini spec） |
| TodoList 機制？ | **各自 TaskCreate（雙軌）** — 主 agent 高層 checklist / subagent 內部實作清單 |

---

## 2. 設計核心

### 2.1 觸發條件（強制）

**觸發 ✅ — 必寫 spec：**
- 任何 `myProgram/` 下 `.py` code 改動（含 sales/ / main.py / tts.py / action.py / input_reader.py）
- 不分規模：中大改動走完整 spec template、超級小改動走 mini spec template

**不觸發 ❌ — 不需 spec：**
- `myProgram/vendor/` 廠商 SDK（禁改）
- `.claude/` 內任何檔（rules / hook / agents / settings）
- `resources/` 內任何檔（plans / specs / architecture / reviews / research / projectStructure / pineedtodo / examples）
- `tests/sales/` 純測試補強（若伴隨 prod code 改動則跟 prod 走 SDD；獨立補回歸網不需）
- CLAUDE.md / memory 等規範自身修訂
- `.gitignore` / `sync_pi.ps1` / `pytest.ini` 等工具設定
- 純文件 / docstring / 註解 sweep

### 2.2 Spec template — 兩種規模

#### 2.2.1 完整版（≥ 3 行 / 跨檔 / 新功能 / 重構 / 行為變更）

8 段結構（沿用 L4_v3 spec 範本）：
1. 背景與動機（why / 現況 / 不對齊處）
2. 設計核心 + 行為規約（含主迴圈虛擬碼 / 行為表）
3. 改檔範圍（每檔細節 + 行數估計）
4. Out of scope（明示不動）
5. 規範與參考（派發 sales-coder + 預載 SKILL + 相關 memory）
6. 測試指令 + 預期結果
7. Commit 規範（拆分建議 + git add 範圍 + commit message 範本）
8. 流程鳥瞰

#### 2.2.2 Mini 版（≤ 3 行單檔純值替換 / typo / 單一 const tweak）

5 行模板：
```markdown
# <task_name> — Mini SDD spec

- **檔**：`<file_path>:<line_number>`
- **改前**：`<before_code>`
- **改後**：`<after_code>`
- **Why**：<reason，一句話>
- **驗證**：`<pytest_command>` / 或「Pi 端跑 X 看 Y」
```

### 2.3 Spec 位置與命名

**統一位置**：`resources/specs/`（flat 結構，不分 L 層）

**命名規範**：`<short_name>_<YYYY-MM-DD>_spec.md`
- 例：`sdd_workflow_formalization_2026-05-31_spec.md`
- 例：`L4_v3_dual_timer_spec.md`（L4_v3 沿用既有命名，無日期後綴，因屬已落地 spec 遷穻）
- 未來新 spec 一律加日期，避免同主題多版本撞檔（如 `L4_v4_xxx_2026-06-15_spec.md`）

**Spec 為 living document**：實作後若行為調整 → 在 spec 內 append 變更段或新開 v 版本 spec（不刪舊 spec）。

### 2.4 雙軌 TaskCreate

**主 agent 的 TaskCreate（高層 checklist）：**
- 對齊需求 / 寫 spec / 等 user approval
- EnterWorktree
- 派 sales-coder
- 審查 subagent 產出 / 跑 pytest
- 階段 3b projectStructure 更新
- ExitWorktree + ff-merge + push + sync + cleanup

**Subagent 的 TaskCreate（內部實作清單）：**
- 由 sales-coder 自己在拿到 spec 後產生
- 對應 spec §3「改檔範圍」每個檔 / 每個 scenario
- sales-coder 自己 mark in_progress → completed

**雙軌不共享**：TaskCreate 是 session-scoped；各自管理避免衝突。Subagent 完成後在回報中 echo 其 TaskList 摘要（"我跑了哪幾條 task"）。

### 2.5 SDD 4 階段流程

```
[階段 1] 主 agent 對齊 + 寫 spec（不派 subagent）
  ↓
  - user 描述需求
  - 主 agent AskUserQuestion 對齊 ambiguity
  - EnterWorktree
  - 主 agent 寫 spec 到 resources/specs/<spec_name>.md（未 commit）
  - AskUserQuestion: spec 是否需修？
  - approval → 主 agent commit spec doc（worktree 首 commit）

[階段 2] 派發 sales-coder（純 prod code 任務 / 含 docstring）
  ↓
  - 主 agent TaskCreate 高層 checklist
  - Agent({subagent_type: 'sales-coder', prompt: 包含 spec 檔路徑 + 任務特化規則})
  - sales-coder 自行 Read spec → TaskCreate 內部清單 → 逐項實作 → commit

[階段 3] 主 agent 審查
  ↓
  - Read worktree 內所有改動的檔
  - 跑 pytest 自驗
  - git branch --contains <SHA> 驗 Gotcha M
  - 不合規退回 / 合規進階段 4

[階段 3b 條件] projectStructure 更新（新 spec / 新 folder / 新 test 檔）
  ↓
  - 主 agent commit projectStructure 變動（worktree 末 commit）

[階段 4 + 5] worktree 收尾
  ↓
  - ExitWorktree keep
  - git merge --ff-only
  - git push origin main
  - 手動 & sync_pi.ps1
  - git worktree remove + git branch -d
```

### 2.6 Sales-coder 系統 prompt 增補（frontmatter / system prompt）

新增固定段落要求：
```
## SDD 任務協議（每次接到任務都套用）

1. **Spec first**：拿到 task prompt 後第一件事是 Read prompt 內指定的 spec 檔（`resources/specs/<spec_name>.md`），完整讀完才開始規劃。Spec 沒提的細節**禁止憑空推測**，停下回報主 agent。

2. **TaskCreate 內部清單**：基於 spec §3「改檔範圍」+ §3.3「測試清單」拆內部實作清單（TaskCreate 工具）。每改完一檔 / 一個 scenario → TaskUpdate 標 completed → 才進下一個。

3. **Definition of done**（對應 Karpathy Goal-Driven Execution pitfall）：
   - pytest 全綠（指令見 spec §6）
   - 我列的 spec §X 全部 covered
   - `git branch --contains <SHA>` 落 worktree branch（非 main，防 Gotcha M）
   - commit message 含 spec 引用

4. **與 spec 偏離必標明**：任何超出 / 偏離 spec 的決定 → 在回報內明示「偏離 + 理由」。
```

---

## 3. 改檔範圍

### 3.1 新增

| 路徑 | 內容 |
|---|---|
| `resources/specs/` | 新 folder（flat 結構 spec 集中地）|
| `resources/specs/sdd_workflow_formalization_2026-05-31_spec.md` | 本 spec（meta-spec，第一個跑新規範）|
| `.claude/rules/sdd-workflow.md` | SDD 流程完整 rule 檔（內容見本 spec §2）|

### 3.2 遷穻

| 動作 | 細節 |
|---|---|
| `git mv` | `resources/plans/業務程式邏輯規劃/L4_v3_dual_timer_spec.md` → `resources/specs/L4_v3_dual_timer_spec.md` |

### 3.3 修改

| 檔案 | 動作 |
|---|---|
| `.claude/CLAUDE.md` | 加新段「📐 SDD (Spec-Driven Development) 流程」+ pointer 到 `.claude/rules/sdd-workflow.md`；🔗 查閱表加 2 行（rule + memory）|
| `.claude/agents/sales-coder.md` | system prompt 加「SDD 任務協議」段（內容見本 spec §2.6）|
| `myProgram/sales/states/l4.py` | docstring 內 spec 路徑引用 `resources/plans/業務程式邏輯規劃/L4_v3_dual_timer_spec.md` → `resources/specs/L4_v3_dual_timer_spec.md` |
| `myProgram/sales/constants/timing.py` | 同上（L4_TOTAL_BUDGET / L4_QR_REFRESH_INTERVAL 註解內的 spec path 引用）|
| `<memory>/sdd_workflow.md` | 重寫 — 新增「強制適用所有 myProgram/ code」「雙軌 TaskCreate」「Spec 位置 resources/specs/」「Mini spec template」段|
| `<memory>/MEMORY.md` | sdd-workflow pointer description 更新（反映正式化）|
| `resources/projectStructure/projectStructure.md` | 樹加 `resources/specs/` folder + 移除 plans/ 下的 L4_v3 行；職責表更新；更新紀錄 append 2026-05-31 |

### 3.4 不改

| 路徑 | 不改原因 |
|---|---|
| `resources/plans/業務程式邏輯規劃/L0_共通.md` 到 `L5.md` | 原 L 層業務邏輯規格（非 SDD 規格），保留 |
| `resources/plans/業務程式邏輯規劃/業務邏輯規劃_終審報告_2026-05-24.md` | 歷史 review，保留 |
| `resources/plans/bdd規範.txt` | BDD 規範本身，保留 |
| `.claude/rules/bdd-tdd-workflow.md` | BDD+TDD dormant 規則，與 SDD 互補（SDD 是「實作前契約」、BDD/TDD 是「實作中流程」） |
| 其他 `.claude/rules/*.md` | 無關 |
| `myProgram/sales/` 其他 .py | 無關（spec 路徑引用只在 l4.py / timing.py） |

---

## 4. Out of scope（本輪不動）

- **不建 hook 強制 spec 存在**（user 沒要求；先靠規則 + 主 agent 自律；若漏寫率高再加 hook）
- **不引入 spec-kit / BMAD / superpowers 等重型工具**（依 research §6.3）
- **不改 sales-coder model / effort 預設**（仍 opus xhigh，無關 SDD 本身）
- **不動 worktree-workflow.md 規則**（SDD 流程內嵌 worktree workflow，不取代）
- **不動 [[dispatch-threshold-by-change-size]] memory**（spec 強制 ≠ subagent 強制；超級小改動 spec + 主 agent 自己 patch 仍可，subagent 仍由規模門檻決定）
- **不對既有 L0-L5 業務邏輯回填 SDD spec**（成本高、收益低；只對新改動適用）

---

## 5. 規範與參考

### 5.1 派發
- 本 meta-task 屬 workflow / rules / docs / docstring sweep 改動 — **主 agent 自行實作**（不派 sales-coder）
- 理由：sales-coder 範圍框死 myProgram/sales/ + worker code，本任務含 .claude/rules/ + CLAUDE.md + memory + sales-coder.md 自身等多類非 sales code 改動

### 5.2 TodoList 雙軌（demo 本流程）
- **主 agent TaskCreate（本輪示範雙軌的「主軌」）**：
  - 對應本 spec §3 各檔 + §3.4 階段
  - 每完成一檔標 completed
- **無 subagent**（本輪不派），故無 subagent 軌

### 5.3 相關 memory / 文檔
- `sdd-workflow` memory — 待本輪重寫
- [[wave-workflow-6-protections]] — 派 subagent 跨檔 refactor 6 招防護（適用未來 sales-coder 接 SDD spec）
- [[dispatch-threshold-by-change-size]] — subagent 派發規模門檻（spec 強制條款外的相容規則）
- [[worker-level-changes-dispatch-sales-coder]] — worker / wire-up 必派 sales-coder
- `resources/research/SDD_best_practices_2026-05-31.md` — 設計依據

---

## 6. 測試指令 + 預期結果

```bash
# 1. 全測試（確認 docstring 路徑改動不破壞既有測試）
python -m pytest tests/sales/ -v
# 預期：386 passed（與當前一致；本輪只改 docstring + 移檔位置，無行為變化）

# 2. Grep 確認所有 spec 引用都已更新
grep -rn "resources/plans/業務程式邏輯規劃/L4_v3" myProgram/ resources/ .claude/
# 預期：無命中（全部已更新為 resources/specs/L4_v3_dual_timer_spec.md）

grep -rn "resources/specs/L4_v3_dual_timer_spec.md" myProgram/ resources/ .claude/
# 預期：≥ 4 處命中（l4.py docstring / timing.py 註解 × 2 / projectStructure.md tree / 本 spec §3.2）
```

---

## 7. Commit 規範

**推薦拆分（3 commit）：**

**Commit 1 — File move**：
```
docs(specs): git mv L4_v3 spec to resources/specs/ flat structure

設立 resources/specs/ 為統一 SDD spec folder（flat 結構，不分 L 層）。
L4_v3_dual_timer_spec.md 為首個遷穻範本；新增 spec 一律走此 folder。

git add 範圍：（git mv 自動處理 add + delete）
```

**Commit 2 — Sweep references + new rule + CLAUDE.md**：
```
feat(SDD): formalize Spec-Driven Development workflow

- 新增 .claude/rules/sdd-workflow.md（完整流程 + template + trigger）
- 新增 resources/specs/sdd_workflow_formalization_2026-05-31_spec.md（meta-spec）
- CLAUDE.md 加「📐 SDD 流程」段 + pointer + 查閱表 2 行
- sales-coder.md system prompt 加「SDD 任務協議」段
- 改 l4.py + timing.py docstring 內 spec 路徑引用

依據：resources/research/SDD_best_practices_2026-05-31.md
2026-05-31 user 三題對齊：所有 myProgram/ code trigger / 雙軌 TaskCreate / L4_v3 遷穻

git add:
  .claude/CLAUDE.md
  .claude/rules/sdd-workflow.md
  .claude/agents/sales-coder.md
  resources/specs/sdd_workflow_formalization_2026-05-31_spec.md
  myProgram/sales/states/l4.py
  myProgram/sales/constants/timing.py
```

**Commit 3 — ProjectStructure update**：
```
docs(projectStructure): record SDD formalization 2026-05-31

- 樹：新增 resources/specs/ folder + 2 個 spec 檔；移除 plans/業務程式邏輯規劃/L4_v3 行
- 更新紀錄：append 2026-05-31 SDD formalization entry
- Header：bump 日期 + tests 數量

git add:
  resources/projectStructure/projectStructure.md
```

Memory 改動（`<memory>/sdd_workflow.md` 重寫 + `<memory>/MEMORY.md` pointer 更新）**不進 git commit**（memory 在使用者 ~/.claude/ 內，untracked）。

---

## 8. 流程鳥瞰

```
[已完成] 主 agent 對齊需求 + 3 題 AskUserQuestion → 寫此 meta-spec
   ↓
[此 spec 待 user 審查 approval]
   ↓
[approval 後] 主 agent commit spec doc（worktree 首 commit）
   ↓
[主 agent 自行實作（無 subagent）— demo 主軌 TaskCreate]
   ↓
   Task A: git mv L4_v3 spec
   Task B: 建 .claude/rules/sdd-workflow.md
   Task C: 改 CLAUDE.md
   Task D: 改 sales-coder.md
   Task E: 改 l4.py docstring
   Task F: 改 timing.py docstring
   Task G: 重寫 memory sdd-workflow + 改 MEMORY.md
   Task H: 跑 pytest 確認 386 仍綠
   Task I: 跑 grep 確認 spec 路徑全更新
   Task J: commit 2（feat sweep）
   ↓
[階段 3b] 更新 projectStructure.md → commit 3
   ↓
[階段 4 + 5] ExitWorktree keep → ff-merge → push → 手動 sync_pi.ps1 → cleanup
```
