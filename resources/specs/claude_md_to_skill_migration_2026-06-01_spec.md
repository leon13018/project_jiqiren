# CLAUDE.md / rules / memory → 單一 Skill 遷移 — 設計 Spec

> **日期**：2026-06-01
> **類型**：meta 重構（`.claude/` + memory + 新 skill；非 `myProgram/` code，不觸發 SDD 三段迴圈）
> **產出脈絡**：使用者要求把 CLAUDE.md 的規範 / 工作流 + 主 agent 的 memory 清到「非常空」，全部整理進一個 skill，利用 skill 的 progressive disclosure 特性省常駐 context。參考官方 skill 架構文檔 `resources/research/CC-skills.md`。
> **建立方式**：最終用 `/skill-creator:skill-creator` 官方工具建 skill。
> **對齊紀錄**：2026-06-01 brainstorming 4 題對齊（顆粒度 / CLAUDE.md 殘留 / memory 清理 / path-scoped）+ roadmap/architecture 移 resources/。

---

## 1. 背景與動機

### 現況問題
- **CLAUDE.md 過大**：⛔禁止 + 🌏語言 + 8 大流程段 + 40 行查閱表 + 維護原則，全部**每 session 常駐**。
- **`.claude/rules/` 13 檔**：其中 **7 個 always-on**（無 `paths:`，跟 CLAUDE.md 同等常駐）：`subagent-dispatch-protocol` / `worktree-workflow` / `standard-workflow` / `sdd-workflow` / `incremental-rebuild` / `pi-side-trigger` / `projectstructure-trigger`。只有 4 個 path-scoped（progressive）。
- **memory 41 個檔**：MEMORY.md 索引（41 行）每 session 常駐。

### 核心洞見（依 `CC-skills.md` 官方文檔）
- Skill 的 **body 只在叫用時載入**，`description` 常駐（整體預算 ≈ context window 的 1%）。長參考資料在需要前幾乎零成本。
- SKILL.md 應 **< 500 行**，當「精簡路由」；細節拆 reference 支援檔，用到才 Read（file 層級 progressive disclosure）。
- Hooks = **確定性強制**，不依賴規則是否載入。
- CLAUDE.md 該 lean：只放「critical gotchas + pointers」；可重用專業知識應放 skill（官方明列的常見誤用：把 reusable expertise 塞 CLAUDE.md）。

### 目標
1. CLAUDE.md 縮到 **~40 行極簡核心**（只留「不能延遲載入」的：安全禁止 / 繁中 / skill 觸發表）。
2. 所有 workflow 協議 + 領域知識 → 收進**單一 skill** `project-01-workflow`（router SKILL.md + references + scripts + examples）。
3. memory 從 41 → **2 個**（`user_profile` + `user_step_by_step_pace`）。
4. `roadmap` / `project_architecture_vision` memory → 移 `resources/`。
5. 新增 2 個 hook，把「能確定性強制」的安全/繁中規範補上（因 CLAUDE.md 變薄、skill 觸發非確定性）。
6. 遷移後刪除 `.claude/rules/` 全部 + 38 個 memory 檔。

### 非目標（Out of scope）
- 不改任何 `myProgram/` code、不改 vendor SDK、不動 sales/ 測試。
- 不改變既有 workflow 的**內容語意**（只搬家 + 重組，不重新設計流程規則本身）。
- 不引入新 plugin / MCP。
- 不重寫既有 hooks 的 sync / pytest / vendor-block / git-add-block 邏輯（只「新增」2 個 + 更新 1 個 subagent-inject）。

---

## 2. 設計總覽

```
CLAUDE.md (極簡核心 ~40 行)              ← 保證載入：⛔安全 + 🌏繁中 + 📐skill 觸發表
  └─ 指向 ↓
.claude/skills/project-01-workflow/       ← description 常駐，body 用到才載
  SKILL.md                                ← 精簡路由 + 觸發表 (< 500 行)
  references/                             ← 12 個 workflow / 領域細節，Read on demand
  scripts/                                ← 可執行代碼（pycache 清理等）
  examples/                               ← reviewer prompt 範本
memory/ (2 個)                            ← user_profile + user_step_by_step_pace
resources/                                ← 接收 roadmap + architecture_vision
+ 新增 hook ×2 + 更新 subagent-inject ×1
```

### 可靠性緩解（因「單 skill router-Read」是模型決定、非確定性）
1. SKILL.md router 的**觸發語句寫明確**（「編 `myProgram/` code 前，先 Read `references/myprogram-*.md`」），降低漏載。
2. **`sales-coder` subagent frontmatter `skills:` 預載整個 skill** → subagent 啟動即全文注入。大部分 myProgram 編碼走 subagent，這條把該路徑轉成**確定性載入**。
3. 安全/繁中靠**新 hook 確定性兜底**，不依賴 skill 是否載入。

---

## 3. CLAUDE.md 殘留規格（目標 ~40 行）

只保留三類「不能延遲載入」：

| 區塊 | 內容 | 來源 |
|---|---|---|
| ⛔ 絕對禁止 | 4 項（① 不改 vendor ② Windows 不裝依賴 ③ 不 import vendor SDK ④ 不用 git add -A），各附 hook 強制標記 | 現 CLAUDE.md ⛔ 段精簡 |
| 🌏 輸出語言 | 「所有產出物中文一律繁體（成果在台灣展示）」一句 + 指向 `references/conventions.md` 看簡繁對照 | 現 🌏 段精簡 |
| 📐 Skill 觸發表 | 一段：列「何時載入 `project-01-workflow` skill」——改 `myProgram/{sales,main,tts,action,input_reader}.py` / 派 subagent / git 收尾（有 tracked 改動）/ SDD / worktree / Pi 端操作 / 結構維護 / 架構難收斂 debug。指明「相關任務開始前先載入該 skill」 | 新寫 |

**刪除**：8 大流程段（內容進 skill）、🌐 部署表（進 `references/pi-and-structure.md`）、40 行查閱表、維護原則段。

**保留**：開頭專案一句話描述、hook 自動化說明的精簡版（提醒 hook 存在）。

---

## 4. Skill 結構規格

### 4.1 Frontmatter（SKILL.md 頂部）

```yaml
---
name: project-01-workflow
description: Project_01 人形機器人銷售機器人專案的所有工作流程與領域知識。Use when 改動 myProgram/ code、派發 subagent、走 git 收尾 / worktree / SDD 流程、判斷 Pi 端操作或專案結構維護、或 debug 架構難收斂問題時。
---
```
- **不設 `paths:`**：本 skill 涵蓋面廣，靠 description 觸發 + CLAUDE.md 觸發表 + subagent 預載。
- **不設 `disable-model-invocation`**：要 Claude 自動載入。
- **不設 `user-invocable: false`**：保留 `/project-01-workflow` 手動叫用能力。
- 位置：`.claude/skills/project-01-workflow/`（專案 skill，commit 進 repo）。

### 4.2 SKILL.md 本體（精簡路由，< 500 行）

內容只有：
1. 專案一句話定位。
2. **觸發 → Read 哪個 reference 的路由表**（核心）。
3. 跨所有任務的「鐵則」極短摘要（如：tracked 改動走 worktree / push 後手動 sync / 派 subagent 不放水 / Iron Law 完成驗證），每條一行 + 指向對應 reference。
4. 不寫任何細節步驟（細節全在 references）。

路由表（示意）：

| 當我要… | Read |
|---|---|
| 改 `myProgram/` code（走 SDD） | `references/sdd.md` + `examples/` reviewer 範本 |
| 編 myProgram 前理解廠商 SDK / 動作 API | `references/myprogram-vendor.md` |
| 編 myProgram 多線程 / 路徑 | `references/myprogram-threading-paths.md` |
| 改 sales 對話狀態機 / 跨層流程設計 | `references/sales-dialog-design.md` |
| 改 sales TTS / 計時 / UX 過場設計 | `references/sales-tts-ux.md` |
| 派 subagent / 判斷派發規模 | `references/dispatch.md` |
| 進 worktree / 收尾 merge | `references/worktree.md` |
| git 收尾 5 步 / sync Pi | `references/standard-workflow.md` |
| 判斷 Pi 端操作 / 寫 pineedtodo / 更新 projectStructure | `references/pi-and-structure.md` |
| 架構多線程難收斂 | `references/incremental-rebuild.md` |
| 新增 sales 業務邏輯（BDD+TDD，dormant） | `references/bdd-tdd.md` |
| 繁簡對照 / 環境 quirk / 跨任務工作原則 | `references/conventions.md` |

### 4.3 references/（12 個檔，內容映射見 §6）

1. `sdd.md`
2. `worktree.md`
3. `dispatch.md`
4. `standard-workflow.md`
5. `pi-and-structure.md`
6. `incremental-rebuild.md`
7. `bdd-tdd.md`
8. `myprogram-vendor.md`
9. `myprogram-threading-paths.md`（含 S6 非阻塞 input 架構）
10. `sales-dialog-design.md`（對話狀態機 / 跨層流程設計）
11. `sales-tts-ux.md`（TTS / 計時 / UX 過場設計）
12. `conventions.md`

### 4.4 examples/

- `spec-reviewer-prompt.md` ← `.claude/rules/sdd-prompts/spec-reviewer.md`
- `code-quality-reviewer-prompt.md` ← `.claude/rules/sdd-prompts/code-quality-reviewer.md`

### 4.5 scripts/

- `clean-pi-pycache.ps1` ← `python_pycache_stale_on_pull` memory 內的 SSH 清 pycache 指令（若該邏輯已在既有 hook 內，scripts/ 只放「手動補跑」版本，並在 reference 註明 hook 已自動做）。
- （可選）`verify-branch.ps1` ← Gotcha M 的 `git branch --contains <SHA>` 驗證封裝。
- 用 `${CLAUDE_SKILL_DIR}/scripts/...` 引用。
- **`sync_pi.ps1` 不複製**（gitignored 在 repo 根）；reference 只寫「跑 `& sync_pi.ps1`」。

---

## 5. Memory 殘留 + resources/ 接收

### 留 memory（2 個）
| 檔 | 理由 |
|---|---|
| `user_profile.md` | 使用者背景，跨 session 事實，memory 系統本職 |
| `user_step_by_step_pace.md` | 使用者工作節奏 feedback，memory 系統本職 |

### 移 resources/
| 檔 | 去向 | 理由 |
|---|---|---|
| `roadmap.md` | `resources/roadmap.md` | 專案進度狀態（living），非 workflow 非 user 事實 |
| `project_architecture_vision.md` | `resources/architecture/architecture_vision.md` | 架構願景，resources/architecture 已存在 |

### MEMORY.md 索引
縮到只剩 2 行（user_profile + user_step_by_step_pace）。

---

## 6. 完整遷移映射表

### 6.1 Rules（13 → 0，全刪）

| Rule 檔 | 去向 |
|---|---|
| `sdd-workflow.md` | references/sdd.md |
| `worktree-workflow.md` | references/worktree.md |
| `subagent-dispatch-protocol.md` | references/dispatch.md |
| `standard-workflow.md` | references/standard-workflow.md |
| `pi-side-trigger.md` | references/pi-and-structure.md |
| `projectstructure-trigger.md` | references/pi-and-structure.md |
| `incremental-rebuild.md` | references/incremental-rebuild.md |
| `bdd-tdd-workflow.md` | references/bdd-tdd.md |
| `vendor-sdk-api.md` | references/myprogram-vendor.md |
| `threading-conventions.md` | references/myprogram-threading-paths.md |
| `path-conventions.md` | references/myprogram-threading-paths.md |
| `sdd-prompts/spec-reviewer.md` | examples/spec-reviewer-prompt.md |
| `sdd-prompts/code-quality-reviewer.md` | examples/code-quality-reviewer-prompt.md |

### 6.2 Memory（40 → 2 留 / 2 移 resources / 36 進 skill）

| Memory 檔 | 去向 |
|---|---|
| `user_profile.md` | **留 memory** |
| `user_step_by_step_pace.md` | **留 memory** |
| `roadmap.md` | resources/roadmap.md |
| `project_architecture_vision.md` | resources/architecture/architecture_vision.md |
| `sdd_workflow.md` | references/sdd.md |
| `worktree_workflow.md` | references/worktree.md |
| `gotcha_m_post_commit_workflow.md` | references/worktree.md |
| `subagent_dispatch.md` | references/dispatch.md |
| `dispatch_threshold_by_change_size.md` | references/dispatch.md |
| `worker_level_changes_dispatch_sales_coder.md` | references/dispatch.md |
| `sales_coder_subagent.md` | references/dispatch.md |
| `wave_workflow_6_protections.md` | references/dispatch.md |
| `standard_workflow.md` | references/standard-workflow.md |
| `background_session_hook_skip.md` | references/standard-workflow.md |
| `python_pycache_stale_on_pull.md` | references/standard-workflow.md + scripts/clean-pi-pycache.ps1 |
| `workflow_constraints.md` | references/standard-workflow.md |
| `pineedtodo_spec.md` | references/pi-and-structure.md |
| `project_deployment.md` | references/pi-and-structure.md |
| `pi_glibc_piwheels_trap.md` | references/pi-and-structure.md |
| `git_sync_verify_before_debug.md` | references/pi-and-structure.md |
| `incremental_rebuild_pattern.md` | references/incremental-rebuild.md |
| `single_queue_preference.md` | references/incremental-rebuild.md |
| `vendor_stop_action_sticky.md` | references/incremental-rebuild.md（+ myprogram-vendor cross-ref） |
| `bdd_tdd_workflow.md` | references/bdd-tdd.md |
| `vendor_files.md` | references/myprogram-vendor.md |
| `vendor_runaction_silent_fail.md` | references/myprogram-vendor.md |
| `s6_non_blocking_input.md` | references/myprogram-threading-paths.md（S6 worker 架構） |
| `c2_three_way_design.md` | references/sales-dialog-design.md |
| `l4_ack_wallclock_budget_design.md` | references/sales-dialog-design.md |
| `cancel_confirm_cross_l.md` | references/sales-dialog-design.md |
| `service_confirm_unified.md` | references/sales-dialog-design.md |
| `confirm_default_must_be_conservative.md` | references/sales-dialog-design.md |
| `speak_and_wait_architecture.md` | references/sales-tts-ux.md |
| `countdown_print_design.md` | references/sales-tts-ux.md |
| `tts_prompt_as_ux_pacing.md` | references/sales-tts-ux.md |
| `ux_over_technical_correctness.md` | references/sales-tts-ux.md |
| `goal_condition_design.md` | references/conventions.md |
| `fix_one_path_sweep_related.md` | references/conventions.md |
| `output_language.md` | CLAUDE.md 核心保留規則 + 簡繁對照細節 → references/conventions.md |
| `user_environment.md` | references/conventions.md（cp936 / 簡繁環境 quirk） |

> ⚠️ 此表 §6.2 是本 spec 最需 user 過目的部分——歸屬有判斷空間（尤其 feedback 性質的 `fix_one_path_sweep` / `confirm_default` / `ux_over_technical` 你若想留 memory，請於審查時指出）。

---

## 7. 新增 / 更新 Hooks

### 7.1 新增 `block-windows-install.ps1`（PreToolUse）
- 攔 Bash/PowerShell tool 內 `pip install` / `pip3 install` / `npm install` / `npm i ` / `apt install` / `apt-get install` 等關鍵字。
- 命中 → block + 訊息「⛔ Windows 本機不裝依賴（CLAUDE.md ⛔#2）；執行環境是 Pi」。
- 確定性兜底 ⛔#2（原本只靠規則文字）。

### 7.2 新增 `check-traditional-chinese.ps1`（Stop 或 PostToolUse）
- 掃本輪 git diff（或本輪寫入檔）有無常見**簡體字**。
- **純警示（絕不 block / 絕不擋任何流程）**：命中只列 file + 簡體字提醒改繁體，exit code 永遠不阻斷。（user 2026-06-01 明確：純警示就好）
- 只掃**檔案產出**（無法掃對話回覆，但檔案產出正是規範重點）。
- 簡體偵測：用簡繁差異字集 / 常見簡體 unicode 範圍（細節實作時定）。

### 7.3 更新 `subagent-inject-rules.ps1`
- 現在注入 rule 摘要 → 改注入「請載入 `project-01-workflow` skill（或已預載）」+ 保留 ⛔ 禁止項 / 繁中極短提醒（這些確定性最重要）。
- 避免 rules 已刪後注入失效的指標。

### 7.4 既有 hooks（不動）
`block-vendor-edit` / `block-git-add-bulk` / `stop-check-sales-pytest` / `session-start-context` / `auto-sync-pi` 維持。

---

## 8. Subagent / Agent 更新

### 8.1 `.claude/agents/sales-coder.md`
- frontmatter `skills:` **加入 `project-01-workflow`**（與既有 karpathy-guidelines / test-driven-development 並列）→ 啟動即全文預載整個 skill。
- 系統 prompt 內原本引用 `.claude/rules/...` 路徑的地方 → 改引用 skill references 路徑。
- ⚠️ 改 subagent 檔需 session restart 或 `/agents` 才生效。

### 8.2 其他 built-in subagent
- 不支援 frontmatter 預載；靠 SubagentStart hook（§7.3）注入 skill 指標 + 主 agent 派發 prompt 內塞必要 reference 路徑。

---

## 9. 刪除清單（遷移完成、驗證後執行）

1. `.claude/rules/` 全 13 檔（含 `sdd-prompts/` 子資料夾）→ 內容已進 skill。
2. 38 個 memory 檔（除 `user_profile` / `user_step_by_step_pace` / `MEMORY.md`）。
3. CLAUDE.md 內遷出的段落。

> 刪除是**最後一步**，確認 skill + references 內容完整、CLAUDE.md 觸發表正確、新 hook 上線後才刪。保留 git history 可回溯。

---

## 10. 執行計畫（兩階段）

### Phase 1 — 用 skill-creator 建 skill 骨架 + 灌入內容
1. `/skill-creator:skill-creator` 建立 `project-01-workflow` skill 骨架（SKILL.md frontmatter + 目錄）。
2. 寫 SKILL.md router（§4.2 路由表 + 鐵則摘要）。
3. 逐一建 11 個 references（§6 映射，**搬運 + 重組**既有 rule/memory 內容，繁中，保留原語意 + cross-ref `[[ ]]` 改為相對路徑連結）。
4. 建 examples/（2 個 reviewer 範本）+ scripts/（pycache 清理等）。
5. 用 skill-creator 的 eval/description 優化功能調 description 觸發準確度（可選）。

### Phase 2 — 遷移收尾（主 agent 自做，非 myProgram code 不派 subagent）
6. CLAUDE.md 瘦身到 §3 極簡核心。
7. 新增 2 個 hook（§7.1 / §7.2）+ 更新 subagent-inject（§7.3）+ 註冊到 settings.json。
8. 更新 `sales-coder.md` frontmatter + 系統 prompt 路徑（§8.1）。
9. memory：移 roadmap / architecture_vision 到 resources/；縮 MEMORY.md；刪 38 memory 檔。
10. 刪 `.claude/rules/`（§9）。
11. 更新 `projectStructure.md`（大量結構變動：新 skill 目錄樹 + rules/ 移除 + memory 變動 + 更新紀錄）。
12. git 收尾：worktree ff-merge + push + sync + cleanup。

> Phase 1 與 Phase 2 之間可暫停讓 user 檢視 skill 內容。

---

## 11. 驗證 / 風險 / 回滾

### 驗證
- 新 session 重啟後，`/doctor` 看 skill description 是否在預算內、是否正常列出。
- 問「What skills are available?」確認 `project-01-workflow` 出現。
- 觸發測試：說「我要改 myProgram 的 L4」→ Claude 應自動載入 skill 並 Read 對應 reference。
- 派 `sales-coder` subagent → 確認 skill 全文預載（看 subagent context 開頭）。
- 新 hook：跑 `pip install x`（沙箱）應被 block；寫含簡體字的檔應觸發警示。
- pytest 仍 344 綠（本變更不碰 sales/ code，純 meta）。

### 風險
| 風險 | 緩解 |
|---|---|
| skill 該觸發沒觸發（myProgram 知識漏載） | router 觸發語句明確 + sales-coder 預載 + 安全靠 hook 兜底 |
| description 超 1536 字元預算被截斷 | 精簡 description；必要時調 `skillListingBudgetFraction` |
| 刪 rules/memory 後發現內容漏搬 | git history 可回溯；刪除排最後 + 先驗證 |
| 繁中 hook 誤報（正常繁中被當簡體） | 用精準簡體字集；警示非 block，不擋流程 |
| 改 sales-coder frontmatter 不生效 | session restart / `/agents` |

### 回滾
- 全程在 worktree + git history；任何階段可 `git revert` 或從 worktree branch 還原。
- 刪除步驟（Phase 2 step 9-10）獨立 commit，便於單獨 revert。

---

## 12. User 審查決議（2026-06-01 已定）
1. **§6.2 memory 歸屬**——feedback 性質檔全部**進 skill**（不留 memory）。memory 最終只留 `user_profile` + `user_step_by_step_pace`。✅
2. **§4.3 references 切法**——拆細：`myprogram-sales-design` 拆成 `sales-dialog-design.md`（對話狀態機 / 跨層流程）+ `sales-tts-ux.md`（TTS / 計時 / UX）；`s6_non_blocking_input` 歸 `myprogram-threading-paths.md`、`goal_condition_design` 歸 `conventions.md`。references 共 **12 個**。✅
3. **skill 命名**——`project-01-workflow`。✅
4. **§7.2 繁中 hook**——做，但**純警示、絕不擋任何流程**。✅
5. **執行分兩階段**——Phase 1（skill-creator 建 skill）做完暫停讓 user 檢視內容，再進 Phase 2。✅
