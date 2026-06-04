# Scaffolding 盤點瘦身 — 實施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（本 plan 以主 agent 編排為主——派發 subagent、核可關、worktree——不適合 subagent-driven 整包外包）。Steps 用 checkbox（`- [ ]`）追蹤。

**Goal:** 依 `resources/specs/scaffolding_audit_slimming_2026-06-04_spec.md`，用 4 個唯讀 fresh-eyes subagent 盤點全專案 scaffolding，產出證據化報告，經使用者三級裁決後執行瘦身。

**Architecture:** 盤點波（4 並行 Explore subagent，唯讀）→ 主 agent 彙整複核 → 報告 commit → 核可關（AskUserQuestion 逐組）→ 執行波（worktree 5 階段，主 agent 親自編輯）→ 驗證收尾。

**Tech Stack:** Claude Code Agent tool（Explore）/ AskUserQuestion / git worktree / PowerShell（hook 手測）。

---

## 盤點對象清單（各 Task 引用，勿憑記憶）

- **CLAUDE.md ×8**：`CLAUDE.md`、`myProgram/CLAUDE.md`、`myProgram/sales/CLAUDE.md`、`myProgram/sales/states/CLAUDE.md`、`myProgram/sales/constants/CLAUDE.md`、`myProgram/vendor/CLAUDE.md`、`resources/CLAUDE.md`、`tests/CLAUDE.md`
- **code_map ×8**：`.claude/code_map.md`、`myProgram/.claude/code_map.md`、`myProgram/sales/.claude/code_map.md`、`myProgram/sales/constants/.claude/code_map.md`、`myProgram/sales/states/.claude/code_map.md`、`myProgram/vendor/.claude/code_map.md`、`tests/.claude/code_map.md`、`resources/.claude/code_map.md`
- **hooks ×10 + 設定**：`.claude/hooks/{block-git-add-bulk,block-vendor-edit,block-windows-install,check-traditional-chinese,session-start-context,state-clear-on-pytest,state-mark-sales-dirty,stop-check-sales-pytest,stop-sync-pi,subagent-inject-rules}.ps1` + `.claude/hooks/NOTES.md` + `.claude/settings.json` + `.claude/hooks/state/`（狀態檔）+ `*.log`
- **skill**：`.claude/skills/project-01-workflow/SKILL.md` + `reference/{bdd-tdd,conventions,dispatch,incremental-rebuild,myprogram-threading-paths,myprogram-vendor,pi-and-structure,sales-dialog-design,sales-tts-ux,sdd,standard-workflow,worktree}.md`
- **memory ×4 + 索引**：`C:\Users\LIN HONG\.claude\projects\C--Users-LIN-HONG-Desktop-Project-01\memory\{MEMORY,lean_doc_authoring,pi_ssh_repair_allowed,user_profile,user_step_by_step_pace}.md`

**共用 finding 格式**（spec §5，無證據不收）：
```
位置（檔:行）｜現況（原文引述）｜為何疑似 overhead｜證據（含 git 考證，若有）｜建議處置級（刪/降級/留觀察）｜誤刪風險
```

**共用豁免條款**（spec §2，寫進每個 subagent prompt）：vendor SDK 保護、`git add -A` 禁令、Windows 不裝依賴——不可逆損害防線，不得提議刪除。

---

### Task 1: 派發盤點波（4 並行唯讀 subagent）

**Files:** 無檔案改動（全程唯讀）。

- [ ] **Step 1: 確認起點乾淨**

Run: `git status --porcelain`
Expected: 空輸出（不乾淨 → 先停，向使用者確認來源）。

- [ ] **Step 2: 單一訊息並行派出 4 個 Agent（subagent_type: `Explore`，medium-thorough）**

四個 prompt 全文如下（佔位符 `{豁免條款}`、`{finding 格式}` 代入上方共用區全文）：

**Agent ①（hooks 機制）prompt：**
```
你是 fresh-eyes 審計員，盤點本專案 hook 機制是否有「為舊 model 限制而建、現已成 overhead」的項目。全程唯讀，禁止任何編輯。

先讀校準筆記：resources/research/CC_hooks_automation_best_practices_2026-06-03.md、resources/research/CC-hooks.md。
再讀盤點對象：.claude/settings.json、.claude/hooks/ 下全部 10 支 .ps1、NOTES.md、state/ 目錄內容、*.log 檔。

判準（機制尺）：hook 不吃 context、誤擋成本低 → 從寬保留；重點找：
(a) 死狀態檔 / 沒人讀的 log 堆積；(b) 多支 hook 重複邏輯；(c) 攔截的失敗模式現行 model 已不會犯（可用 git log --oneline --follow -- <檔> 與 NOTES.md 記載考證該 hook 當初為何而建）；(d) settings.json 註冊了但 script 不存在、或 script 存在但沒註冊。
{豁免條款}
輸出：每條 finding 用 {finding 格式}；另附「確認健康、無需動」清單一行帶過。無證據不收。
```

**Agent ②（恆載文字層）prompt：**
```
你是 fresh-eyes 審計員，盤點 CLAUDE.md 與 code_map 是否有「拿掉後現行 model 仍會做對」的冗餘。全程唯讀，禁止任何編輯。

先讀校準筆記：resources/research/CC_large_codebases_best_practices_2026-06-01.md、resources/research/large_codebases_official_guide_2026-06-02.md。
再讀盤點對象（16 檔）：{CLAUDE.md ×8 與 code_map ×8 清單代入}。

判準（訊號密度尺）：逐條問「移掉這行，model 還會做對嗎」。重點找：
(a) 跨層重複解釋（紅線/規則在 root 與子層都寫）；(b) 指向不存在檔案/路由的壞 pointer（用 Glob 驗證引用路徑存在）；(c) 對現行 model 多餘的操作叮嚀（教 model 它本來就會的事）；(d) 行數超標：root CLAUDE.md ≤~100 行、子層 ≤~60 行（用 Read 的行號確認總行數）；(e) code_map 與實際目錄不符（用 Glob 抽查）。
{豁免條款}——root 紅線區整段豁免，只可挑「重述紅線的子層段落」。
輸出：每條 finding 用 {finding 格式}；另附各檔行數總表。無證據不收。
```

**Agent ③（流程門檻）prompt：**
```
你是 fresh-eyes 審計員，盤點 project-01-workflow skill 的「流程門檻機制」是否對現行 model 過重。全程唯讀，禁止任何編輯。字句措辭剛被 denoise 過，不要挑字句，只審機制本身。

先讀校準筆記：resources/research/skills_best_practices_research_2026-06-03.md、resources/research/SDD_best_practices_2026-05-31.md。
再讀盤點對象：.claude/skills/project-01-workflow/SKILL.md + reference/ 全部 12 檔，聚焦這些機制：SDD 三段 reviewer、worktree 5 階段、dispatch 門檻（≤3 行才可自 patch）、Iron Law、pineedtodo 協議、code_map 巢狀維護、subagent commit branch 驗證。

判準（機制尺，吃時間/輪次 → 認真審）：逐個機制問「它防的失敗模式，現行 model 還會犯嗎？防護收益還值不值得流程成本？」可用 git log 考證機制何時為何而建（resources/specs/ 下歷史 spec 有記載動機，可引用）。
{豁免條款}
輸出：每條 finding 用 {finding 格式}，「機制」也算一個位置（標 SKILL.md 或 reference 檔:行）；明確區分「整個機制過重」vs「機制保留但某環節可簡化」。無證據不收。
```

**Agent ④（memory + 跨類重複）prompt：**
```
你是 fresh-eyes 審計員，做兩件事。全程唯讀，禁止任何編輯。

先讀校準筆記：resources/research/memory_official_guide_2026-06-02.md。
(1) 輕掃 memory（5 檔）：C:\Users\LIN HONG\.claude\projects\C--Users-LIN-HONG-Desktop-Project-01\memory\ 下 MEMORY.md、user_profile.md、user_step_by_step_pace.md、lean_doc_authoring.md、pi_ssh_repair_allowed.md——判準（訊號密度尺）：與 CLAUDE.md / skill 重複者、過時者列 finding。
(2) 跨類重複偵測：對照 root CLAUDE.md、.claude/skills/project-01-workflow/SKILL.md、reference/standard-workflow.md、reference/worktree.md、reference/dispatch.md、.claude/hooks/NOTES.md——找「同一規則出現 ≥3 處」的案例，標出每處位置與哪處該是權威版（root=紅線、skill=協議、NOTES=hook 行為）。
{豁免條款}
輸出：每條 finding 用 {finding 格式}。無證據不收。
```

- [ ] **Step 3: 收齊 4 份結果**

確認每份 finding 都符合強制格式；缺格式欄位的退回原 agent（用 SendMessage 續問）補齊。

---

### Task 2: 彙整複核 + 產出報告

**Files:**
- Create: `resources/reviews/scaffolding_audit_2026-06-04.md`

- [ ] **Step 1: 去重與衝突調和**

跨 agent 同一位置的 finding 合併；互相矛盾（如 ② 說刪、④ 說它是權威版）→ 主 agent 開原檔複核裁決，不直接採信任一方（spec §10）。

- [ ] **Step 2: 抽查證據**

每個 agent 至少抽 2 條 finding，開原檔核對「位置（檔:行）」與「現況引述」屬實。抽查不過 → 該 agent 全部 finding 逐條核對。

- [ ] **Step 3: 定三級初判並寫報告**

報告骨架（固定用此結構）：
```markdown
# Scaffolding 盤點報告 2026-06-04
> 來源：spec resources/specs/scaffolding_audit_slimming_2026-06-04_spec.md；4 subagent 盤點波結果彙整。
## A. 刪除組（高信心）
| # | 位置 | 現況 | 為何 overhead | 證據 | 誤刪風險 |
## B. 降級組（中信心：恆載 → 按需）
| # | 位置 | 現況 | 降到哪 | 證據 | 風險 |
## C. 留觀察組（低信心）
| # | 位置 | 疑點 | 回頭處理的觸發訊號 |
## D. 確認健康（無需動，一行一項）
## E. 使用者裁決紀錄（核可關後回填）
```

- [ ] **Step 4: Commit 報告**

```bash
git add resources/reviews/scaffolding_audit_2026-06-04.md
git commit -m "docs(review): scaffolding audit report (pre-approval)"
git push origin main
```
（commit message 結尾照例附 Co-Authored-By。）

---

### Task 3: 核可關（使用者裁決）

**Files:**
- Modify: `resources/reviews/scaffolding_audit_2026-06-04.md`（回填 §E）

- [ ] **Step 1: 呈現報告摘要 + 逐組 AskUserQuestion**

A/B/C 三組各一題，選項固定：「照單全收」「逐項挑（我會逐項再問）」「整組擱置」。選「逐項挑」→ 對該組逐項追問（每項：執行 / 擱置）。

- [ ] **Step 2: 回填裁決進報告 §E，commit**

```bash
git add resources/reviews/scaffolding_audit_2026-06-04.md
git commit -m "docs(review): record user disposition decisions"
git push origin main
```

- [ ] **Step 3: 守門檢查**

核可項為 0 → 跳過 Task 4，直接 Task 5（報告即成果）。未核可項一律不進執行清單。

---

### Task 4: 執行波（worktree 5 階段）

**Files:** 依核可清單（tracked 文件/設定，可能含 CLAUDE.md / code_map / skill refs / hooks / settings.json）；memory 檔不在 git，直接編輯。

- [ ] **Step 1: 讀協議權威**

Read：`.claude/skills/project-01-workflow/reference/worktree.md` + `reference/standard-workflow.md`（執行時重讀，不憑記憶）。

- [ ] **Step 2: EnterWorktree（name: `scaffolding-slimming`）**

- [ ] **Step 3: 按「高信心先動」逐項執行，每項三動作**

(a) Edit 該項（刪 = 移除該段；降級 = 從恆載檔剪下、貼進目標按需檔的對應節）；
(b) 立即驗證：文字類 → 重讀改動檔，確認殘留 pointer 仍指向存在的檔（Glob 驗證）；降級項 → 確認目標檔已收錄且該層 code_map / SKILL.md 路由表同步；
(c) hook/settings 類 → stdin 手測：
```powershell
'{"hook_event_name":"<事件名>","cwd":"."}' | pwsh -NoProfile -File .claude\hooks\<script>.ps1; $LASTEXITCODE
```
Expected: exit code 與該 hook NOTES.md 記載行為一致（block 類=deny JSON+0；旁路類=0）。

- [ ] **Step 4: 同類項集中 commit（在 worktree 內，分群提交）**

```bash
git add <明確檔名清單>
git commit -m "refactor(scaffolding): <群組描述> per audit item A-n"
```

- [ ] **Step 5: 全局複測**

(a) root CLAUDE.md 行數 ≤~100、被改子層 ≤~60（Read 行號確認）；
(b) `python -m pytest tests/sales/ -q` → Expected: 344 passed（保險絲：證明瘦身沒誤傷任何被測行為）；
(c) NOTES.md 與 hooks 實況一致（被改 hook 的記載同步更新）。

- [ ] **Step 6: worktree 收尾（依 worktree.md 階段 4–5：merge 回 main → push → 清 worktree）**

Pi sync 由 Stop hook 自動。

---

### Task 5: 收尾驗證 + 回報

- [ ] **Step 1: 留觀察清單落檔確認**

報告 §C 每項都有「觸發訊號」；缺的補上，與 Task 4 的執行結果一起最終 commit。

- [ ] **Step 2: 下一 turn 觀察 hook 活性**

SessionStart 快照正常注入、Stop hook 回報 `Pi synced to <sha>`（被改 hook 是否仍 fire 的實戰驗證）。

- [ ] **Step 3: 四件套回報**

(1) 改了什麼（刪 n 項/降級 n 項/留觀察 n 項）；(2) pineedtodo：無（純本機 scaffolding）；(3) Pi sync 狀態；(4) 後續行動：留觀察清單的觸發訊號。

---

## Self-Review 紀錄

- **Spec coverage**：§1→Task2/5 成功標準逐項對應；§2 範圍→Agent①②③④；§3 判準→各 prompt 內嵌；§4 三級→報告 A/B/C 組；§5 方法→Task1；§6→Task2；§7→Task3；§8→Task4；§9 驗證→Task4 Step3(b)(c)/Step5、Task5 Step2；§10 邊界→Task2 Step1（矛盾調和）、Task3 Step3（零核可）、證據錯誤退回=Task4 Step3(b) 驗證失敗時該項退回 §C。✅ 無缺口
- **Placeholder scan**：無 TBD/TODO；4 個 subagent prompt 全文在 plan 內；執行波依賴核可清單屬資料依賴非佔位。✅
- **一致性**：finding 格式、報告骨架、三級名稱（刪/降級/留觀察）全檔統一；hooks 數量修正為 10（ls 實測，spec 寫 9 為筆誤，以本 plan 為準）。✅
