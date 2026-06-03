# Subagent / Agent Teams 派發協議

> **🎯 何時讀本檔**：要派 subagent / agent teams、判斷某改動該不該派（規模門檻）、或設定 / 派發 sales-coder。

## 派發時機

派發 = **派發前準備 + 派發後審查**，兩階段不可省。subagent 是隔離 context：**讀不到本對話歷史**（這輪的 discussion / 已對齊的設計決定 / 已讀的檔都看不到），但 general-purpose 與自訂 subagent（sales-coder）**啟動時仍會載入專案 CLAUDE.md + git status**（只有 built-in Explore / Plan 跳過）。→ 紅線它本就看得到；要主動餵的是**本對話特有的任務 context**（業務規格 / 設計決定 / reuse 點），不餵就產出偏離。

- **預設**：Plan mode 完成後派 subagent（單一任務）/ agent teams（複雜任務）執行；主 agent 留做規劃 / 審查 / 邊界判斷。
- **例外（主 agent 自寫）**：使用者明說「你自己改」、純文件 / memory 編輯、極小 typo / rename、bootstrap（見 [worktree.md](worktree.md) 例外 C）、及下方「超級小」改動。

## subagent_type 對應表

| 任務 | subagent_type |
|---|---|
| 編 `myProgram/sales/*.py` / `tests/sales/*.py` / `myProgram/{main,tts,action,input_reader}.py` | **`sales-coder`**（自訂，frontmatter 預載 karpathy + TDD + 本 skill 全文，強過 prompt 塞 summary） |
| 純研究 / 探索 / 文件查詢 | `claude-code-guide` / `Explore` / `Plan`（built-in，可 sonnet） |
| 其他寫 code（無對應 custom） | `general-purpose` + `model: "opus"`，prompt 塞「嚴格依規範、寧慢勿錯」 |

**預設模型 opus**：跨檔 refactor sonnet 踩坑率高、opus 穩。Agent 工具只接受 `sonnet`/`opus`/`haiku`（不能指定子版本）。`sales-coder` frontmatter 已內建 opus，派發不必再傳；研究 / Explore 類可手動指定 sonnet。

## 規模門檻（派 vs 主 agent 直接 patch）

| 規模 | 處理 |
|---|---|
| 中小以上 | **必派 sales-coder**，不論檔案類型 |
| **超級小** | 主 agent 直接 patch，但**必先** invoke `andrej-karpathy-skills:karpathy-guidelines` |

**「超級小」（須同時滿足）**：≤ 3 行（不含 docstring/comment）｜單一檔案｜純值替換 / typo / const 微調｜無新增 function/class/簽名變動｜無 cross-file propagation。

灰色地帶（const 多處 / 多檔同步 typo / docstring 大段重寫）→ **派 sales-coder**。規模判斷**向保守傾斜**，不確定就派。

## worker / wire-up 結構改動

動到 `myProgram/{tts,action,input_reader,main}.py` 的 **worker 級程式碼或 callback wire-up**，即使「規模小、surgical」也要 **EnterWorktree + 派 sales-coder**。

- **觸發**：新方法 / 新 attr / `_loop` 重排 / try-finally / lock scope / callback signature / wire-up。
- **不觸發**：純 const / 純字串 / 單行 typo / 純 docstring。
- 涉 race / sticky state / thread sync **一律派**（結構盲點非一眼 grep 得完）。

## 派發前必做（依序）

**Step 0 — EnterWorktree**：派發前主 agent 先進 worktree（除 bootstrap），subagent 繼承 cwd。見 [worktree.md](worktree.md)。

**Step 1 — 挑相關規則塞 prompt**（寧多不漏）：
- **不需塞**（frontmatter 預載）：karpathy / TDD / project-01-workflow 全文。
- **不需塞**（sales-coder / general-purpose 啟動原生載入專案 CLAUDE.md）：禁改廠商 SDK / 繁中 / 不用 `git add -A` / commit Co-Authored-By（紅線在 CLAUDE.md，自動載入；只有 Explore/Plan 跳過 CLAUDE.md，由 SubagentStart hook 補最小導航）。
- **仍需塞（任務特化）**：vendor API 細節 / 業務規格 / 已對齊的設計決定 / 既有 helper reuse 點 / git add 範圍 + commit message 範本。

**Step 2 — 確認 sales-coder 生效**：`Agent({subagent_type:"sales-coder", ...})`（frontmatter 已設 model+skills）。built-in subagent（如 general-purpose）不能改 frontmatter 預載 skill → 紅線靠原生載入的 CLAUDE.md，karpathy / 任務特化規則靠 prompt 塞。

**Step 3 — 要求嚴格遵守**：prompt 末要求 subagent 嚴格按規範、不自由發揮。

**Step 4 — 界定「不該做什麼」**（一律加，防越權收尾）：
```
## ⛔ 重要規範
- 不做 post-commit closeout（不 ExitWorktree / ff-merge / push / git worktree remove）— 主 agent 收尾。你只做：編輯 → commit → 回報。
- 不要 cd 到主 checkout 路徑（會引發 commit 誤落 main）— 維持在 worktree cwd。
```

## 派發後審查 + branch 驗證

不可把產出原封交使用者，先審：
1. **逐項對照 CLAUDE.md**：中文全繁？沒改 `ActionGroupControl.py`/`Board.py`？路徑用 Linux 絕對路徑？沒 `git add -A`？（hook 已擋執行面；審查看 plan/說明有無理解遵守）。
2. **依偏差程度**：小細節不符 → **自己直接修**省往返；大量偏差 / 核心理解錯 → **退回重做**並列偏差點。
3. **絕不把不合規產出交使用者**——主 agent 對最終交付負責。
4. **驗 commit branch**：subagent 回報 SHA 後跑 `git branch --contains <SHA>`，顯示 `main` 即誤落（Gotcha M）→ 解法見 [worktree.md](worktree.md)。

## Wave 6 招防護（跨檔 refactor）

派 subagent 做「跨檔簽名變動 + 既有 test 連動更新」的批次（Wave）時，**opus + 6 招**比單純拆細範圍更有效。**6 招（prompt 內必含）**：

1. **先列再做**：開工前 grep 受影響檔/test，thinking 內列清單，return 必含。
2. **每條改動完跑 pytest**：不累積到全改完才跑。
3. **commit 前自檢**：`git diff --stat` + `git status` + `python -m pytest tests/sales/ -v --tb=short`。
4. **pytest verbose 不省**：`-v --tb=short`（非 `-q`），回報含尾 30 行。
5. **規格衝突 test 必停**：修法明顯（業務變更）→ 主動更新並列清單；不明顯 → 停下回報，不自作主張改 test。
6. **任何 fail/xpass/error 必停**：commit 前有 fail → 不 commit，停下回報。

**主 agent 端兩驗證**：(A) 主 checkout `git status` 應 clean（否則 subagent 雙寫）；(B) 自跑 pytest，數字須對齊 subagent 自報。

**Wave 大小**：≤6 條低風險 = 一個 subagent；2 條結構動深（簽名 + 連動 ≥10 test）= 一個；≥8 條混合 = **拆 2 個序列做**。別「一條一 subagent」；序列 2-3 個是甜蜜點。

## sales-coder 自訂 subagent

`.claude/agents/sales-coder.md` 透過 frontmatter **啟動時預載 SKILL 完整內容**（非 summary）；Agent tool inline call 不支援 `skills` 參數，故必走 frontmatter。當前：`model: opus` + `skills: [andrej-karpathy-skills:karpathy-guidelines, test-driven-development, project-01-workflow]`。派發只傳 `subagent_type + description + prompt`。

**⚠️ 改了 `.claude/agents/*.md` 需 session restart 才 reload**（`/clear` 不夠）：CLI `/exit` 重跑 `claude`，或 agent view `Ctrl+X` stop + reattach。驗證：restart 後派個任務，回「unknown subagent_type」= 沒 reload。

## SDD 觸發時的派發增補

寫 `myProgram/` 任何 `.py` 觸發 SDD（見 [sdd.md](sdd.md)）後，dispatch pattern 不變，只增補：
- prompt 必含 **spec/plan 兩檔路徑**（`resources/specs/<name>_<date>_spec.md` + `_plan.md`；mini spec 不拆）。
- sales-coder 回報**首行 4 狀態**（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）。
- 派發後走**三段 subagent 迴圈**（完整流程、模型、Status 處理表見 [sdd.md](sdd.md)）。
