# Subagent / Agent Teams 派發協議

> **🎯 何時讀本檔**：要派 subagent / agent teams、判斷某改動該不該派（規模門檻）、或設定 / 派發 sales-coder。

## 目錄
- 派發時機與心態
- subagent_type 對應表 + 預設模型
- 規模門檻（派 vs 主 agent patch）
- worker / wire-up 結構改動規則
- 派發前必做 4 步
- 派發後審查 + branch 驗證
- Wave 6 招防護（跨檔 refactor）
- sales-coder 自訂 subagent + session restart

---

## 派發時機與心態

主對話 agent 是工程部「總負責人」，subagent 是執行任務的工程師團隊；我負責**有效管理 + 監督**（派發前準備 + 派發後審查，兩階段不可省）。

> **Why**：subagent 是全新 context window，預設讀不到 [CLAUDE.md](../../../../CLAUDE.md) 也讀不到本對話歷史。不主動餵規範 → 產出不合規（簡體 / 改廠商檔 / 相對或 `~` 或 Windows `\` 路徑）。預先準備一次到位是效率關鍵。

- **觸發（預設）**：Plan mode 完成後一律派 subagent（單一任務）/ agent teams（複雜任務）執行，**除非使用者明確要主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。
- **例外（主 agent 自己寫）**：使用者明說「你自己改」、純文件 / memory 編輯、極小 typo / rename、bootstrap 任務（見 [worktree.md](worktree.md) 例外 C）、及下方「超級小」改動。
- 不把使用者當品質檢查員——交付前自己把關完畢。

---

## subagent_type 對應表

| 任務類型 | subagent_type | 為何 |
|---|---|---|
| 編 `myProgram/sales/*.py` / `tests/sales/*.py` / `myProgram/{main,tts,action,input_reader}.py` 等寫 code | **`sales-coder`**（自訂，frontmatter 預載 karpathy + TDD + 本 skill 全文） | 啟動時官方機制注入 SKILL 全文，強過 prompt 內塞 reference summary |
| 純研究 / 探索 / 文件查詢 | `claude-code-guide` / `Explore` / `Plan`（built-in，可 sonnet） | 不寫 code，輕量省成本 |
| 其他寫 code（無對應 custom） | `general-purpose` + `model: "opus"` | fallback，prompt 內塞「嚴格依規範、寧可慢不要錯」 |

### 預設模型 opus
- `Agent({ model: "opus" })`。Agent 工具只接受 `sonnet`/`opus`/`haiku`，**不能指定子版本**（用 session 對應 Opus）。
- **`skills` 無法用 Agent 參數傳** → 要預載 skills 必須走 `.claude/agents/<name>.md` frontmatter（見文末）。
- **Why 預設 opus**：跨檔 refactor sonnet 踩坑率高、opus 穩；預設化省每次判斷複雜度。`sales-coder` frontmatter 已內建 `model: opus`，派發不必再傳。研究 / Explore 類仍可手動指定 sonnet。
- **Co-Authored-By**：用實際模型署名，預設 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；研究類用 sonnet 時為 `Claude Sonnet 4.6`。

---

## 規模門檻（派 vs 主 agent 直接 patch）

| 規模 | 處理 |
|---|---|
| 中小 / 中 / 中大 / 大 | **必派 sales-coder**，不論檔案類型（sales/ / main.py / docstring 多段重寫 / const+簽名變動 等） |
| **超級小** | 主 agent 直接 patch，但**必先** invoke `andrej-karpathy-skills:karpathy-guidelines` 再動手 |

**「超級小」定義（同時滿足才算）**：改動 ≤ 3 行（不含 docstring/comment）｜單一檔案｜純值替換 / typo / const 微調，無邏輯結構改動｜無新增 function/class/簽名變動｜無 cross-file propagation。

- 灰色地帶（const 多處 / 多檔同步 typo / docstring 大段重寫）→ **派 sales-coder**：多處 const + docstring 重寫已是 cross-line propagation，超門檻。規模主觀判斷**向保守傾斜**，不確定就派。

---

## worker / wire-up 結構改動規則

動到 `myProgram/{tts,action,input_reader,main}.py` 的 **worker 級程式碼或 callback wire-up**（不只 sales/），即使「規模小、surgical」也要 **EnterWorktree + 派 sales-coder**，不主 agent 直接 patch。

- **觸發**：結構性改動（新方法 / 新 attr / `_loop` 重排 / try-finally / lock scope / callback signature / wire-up）。
- **不觸發**：純 const / 純字串 / 單行 typo / 純 docstring（仍可直接 patch）。
- **Why**：worker thread 結構盲點（race / state machine / try-finally 邊界 / 新 attr 與既有 lock 互動）非主 agent 一眼 grep 得完，sales-coder 嚴格 TDD 更穩。涉 race / sticky state / thread sync **一律派**。

---

## 派發前必做（依序）

**Step 0 EnterWorktree**：派發前主 agent 先進 worktree（除 bootstrap 例外）；subagent 繼承 cwd 自動在隔離環境工作。見 [worktree.md](worktree.md)。

**Step 1 挑相關規則塞 prompt**（不全塞 CLAUDE.md，但寧多不漏）：
- **不需塞**（sales-coder frontmatter 預載）：karpathy-guidelines / test-driven-development / project-01-workflow 全文。
- **不需塞**（SubagentStart hook 注入）：廠商 SDK 禁改 / 繁中 / 不用 `git add -A` / commit Co-Authored-By。
- **仍需塞（任務特化）**：vendor API 細節 / 業務規格 / 已對齊的設計決定 / 既有 helper reuse 點 / git add 範圍 + commit message 範本。

**Step 2 確認 sales-coder 已生效**：寫 sales/ code 派 `Agent({subagent_type:"sales-coder", ...})`（frontmatter 已設 model+skills，不必再傳）。⚠️ **外部改 `.claude/agents/*.md` 需 session restart 才 reload**（見文末）。built-in subagent 不能改 frontmatter → 仍靠 hook 注入 + prompt 塞 karpathy。

**Step 3 要求嚴格遵守**：prompt 末要求 subagent 嚴格按前述規範、不自由發揮。

**Step 4 界定「不該做什麼」**（一律加，防越權收尾）：
```
## ⛔ 重要規範
- 不做 post-commit closeout（不 ExitWorktree / ff-merge / push / git worktree remove）— 主 agent 收尾。你只做：編輯 → commit → 回報。
- 不要 cd 到主 checkout 路徑（會引發 Gotcha M）— 維持在 worktree cwd；若 git 把 commit 落到 main 是已知偶發 Gotcha M，主 agent 會 workaround。
```
**Why**：subagent 常越權做完整收尾（ff-merge/push/cleanup），破壞主 agent 審查機會 + 殘留 worktree。

---

## 派發後審查 + branch 驗證

不可把產出原封交使用者，先審：
1. **逐項對照 CLAUDE.md**：中文全繁？沒改 `ActionGroupControl.py`/`Board.py`？路徑用 Linux 絕對路徑？沒 `git add -A`？（hook 已擋執行面；審查看 subagent 在 plan/說明內有無理解遵守）。
2. **依偏差程度**：小細節不符（少數簡體 / commit 寫法 / 檔名小錯）→ **自己直接修省往返**；大量偏差 / 核心理解錯（整檔簡體 / 改禁改檔 / 邏輯偏離）→ **退回重做**並列出偏差點。
3. **絕不把不合規產出交使用者**——我對最終交付負責。
4. **驗 commit branch（防 Gotcha M）**：subagent 回報 SHA 後跑 `git branch --contains <SHA>`，顯示 `main` 即誤落（已知偶發 bug）→ **完整解法見 [worktree.md](worktree.md) §Gotcha M**（ExitWorktree remove → 主 checkout 驗 → 需後續編輯則新 worktree + cherry-pick → push → branch -D）。

---

## Wave 6 招防護（跨檔 refactor）

派 subagent 做「跨檔簽名變動 + 既有 test 連動更新」的批次（Wave）時，**opus + 6 招**比單純拆細範圍更有效。

**6 招（prompt 內必含）**：
1. **先列再做**：開工前 grep 受影響檔/test，在 thinking 內列清單，return 必含此清單。
2. **每條改動完跑 pytest**：不累積到全改完才跑。
3. **commit 前自檢**：`git diff --stat` + `git status` + `python -m pytest tests/sales/ -v --tb=short`。
4. **pytest verbose 不省**：跑 `-v --tb=short`（非 `-q`），回報含尾 30 行（自報「N passed」可能不準）。
5. **規格衝突 test 必停**：改動使既有 test fail 且修法明顯（業務變更）→ 主動更新並列清單；修法不明顯 → 停下回報，不自作主張改 test。
6. **任何 fail/xpass/error 必停**：commit 前有 fail → 不 commit，停下回報。

**主 agent 端兩驗證**：(A) 主 checkout `git status` 應 clean（否則 subagent 雙寫了，見 worktree §Gotcha M）；(B) 主 agent 自跑 pytest，數字須對齊 subagent 自報。

**Wave 大小**：≤6 條低風險（純字串/數字/局部邏輯）= 一個 subagent；2 條結構動深（簽名 + 連動 ≥10 test）= 一個；≥8 條混合 = **拆 2 個序列做**。別「一條一 subagent」（多 subagent 改同檔會衝突、多 branch merge 更亂）；序列 2-3 個是甜蜜點。

---

## sales-coder 自訂 subagent + session restart

`.claude/agents/sales-coder.md` 透過 frontmatter `skills:` **啟動時預載 SKILL 完整內容**（非 reference summary）。官方確認（subagents.md）：`skills` 欄注入 full content；**Agent tool inline call 不支援 `skills` 參數**，故必須走 frontmatter 預定義路徑。

當前 frontmatter：`model: opus` + `skills: [andrej-karpathy-skills:karpathy-guidelines, test-driven-development, project-01-workflow]`。派發只傳 `subagent_type + description + prompt`（任務特化）。

**⚠️ Session restart 必要**（官方：直接改 disk 上 subagent 檔 → 需 restart 才 reload）：
- 用 Write 改 `.claude/agents/*.md` → 需 restart；`/clear` 不夠（只清對話）。
- 方法：CLI `/exit` 後重跑 `claude`；agent view 內 `Ctrl+X` stop + reattach（supervisor spawn fresh process 重讀 `.claude/agents/`）；Desktop/Web 點 New chat。
- 驗證：restart 後隨便派個任務給 `Agent({subagent_type:"sales-coder"})`，失敗回「unknown subagent_type」、成功代表 reload OK。
- **built-in subagent（Explore/Plan/general-purpose/claude-code-guide）不能改 frontmatter、不預載 skills**；需完整 SKILL 走 built-in → 主 agent 在 prompt 內 paste。

> 🪝 **SubagentStart hook**（2026-05-25 起）自動注入標準規範：研究類（claude-code-guide/Explore/Plan）注精簡版（繁中 + 文檔指標）；編碼類（general-purpose/sales-coder/其他自訂）注完整規範（⛔ 禁止項 + 強制規範 + 文檔指標）。完整 hook 文檔：`.claude/hooks/NOTES.md`。

---

## SDD 觸發時的派發增補

寫 `myProgram/` 任何 `.py` code 觸發 SDD（見 [sdd.md](sdd.md)）後，dispatch pattern 不變，只增補：
- 派 sales-coder prompt 必含 **spec/plan 兩檔路徑**（`resources/specs/<name>_<date>_spec.md` + `_plan.md`；mini spec 不拆）。
- sales-coder 回報**首行 4 狀態**（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）。
- 派發後走**三段 subagent 迴圈**（Iron Law 自驗 → spec-reviewer → code-quality-reviewer）——完整流程、模型選擇、Status 處理表全在 [sdd.md](sdd.md) §三段 subagent 迴圈，本檔不重述。

---

**相關 reference**：[worktree.md](worktree.md) / [standard-workflow.md](standard-workflow.md) / [sdd.md](sdd.md) / [pi-and-structure.md](pi-and-structure.md)
