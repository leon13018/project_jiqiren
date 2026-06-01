# Subagent / Agent Teams 派發協議

我（主對話 agent）是工程部「總負責人」，subagent / agent teams 是底下執行任務的工程師團隊。我負責**有效管理 + 監督**，必須完整執行派發前準備 + 派發後審查兩個階段，不可省略。

> **Why**：subagent / agent team 是全新 context window，預設讀不到 [CLAUDE.md](../../../CLAUDE.md) 也讀不到本對話的歷史。如果不主動把規範餵給他們，他們會做出不合規範的產出（典型錯誤：寫簡體中文、改到廠商檔、用相對路徑、用 `~` 路徑、用 Windows `\` 路徑等等）。最後我還是得要求他們修或自己修，造成大量往返浪費。**預先準備好可以一次到位，是效率關鍵。**

---

## 派發時機與心態

### 觸發時機（預設行為）

**Plan mode 完成後 → 一律派 subagent（單一任務）/ agent teams（複雜任務）執行**，**除非使用者明確要求主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。

**Why**：使用者 2026-05-22 確認此分工 — 主 agent（Opus）留做規劃 / 審查 / 邊界判斷，編輯任務交給 subagent。原本預設「更便宜的 Sonnet」，**2026-05-28 改為 Opus**（[wave 6 招防護](#wave-6-招防護跨檔-refactor)證實 sonnet 在跨檔任務踩坑率太高，opus xhigh 零坑），預設模型升級換取穩定性。Opus 主 agent 的火力仍用在抓 bug、設計決策、跨檔重構這類需要全局視野的工作。

**例外（主 agent 自己寫）**：使用者明確說「你自己改」、純文件 / memory 編輯、極小範圍 typo / rename、bootstrap 任務（見 [worktree.md](worktree.md) 例外 C）。另見下方「規模門檻」對「超級小」改動的精確定義。

### 心態原則

- 我是工程部總負責人，subagent 是團隊工程師。我負責**有效管理 + 監督**。
- 派發任務要清楚、要把背景與規範交代完整。
- 進度跟進、產出審查、品質把關是我的職責。
- 不把使用者當品質檢查員 — 交給使用者之前就要把關完畢。

---

## subagent_type 對應表（依任務類型選）

| 任務類型 | subagent_type | 為何 |
|---|---|---|
| 編 `myProgram/sales/*.py` / `tests/sales/*.py` / `myProgram/{main,tts,action,input_reader}.py` 等寫 code 任務 | **`sales-coder`**（自訂，frontmatter 預載 karpathy + TDD SKILL 完整內容） | 啟動時官方機制注入 SKILL 全文 vs prompt 內塞 reference summary 的薄弱對比 — 2026-05-28 由 user 提示研究後採用 |
| 純研究 / 探索 / 文件查詢 | `claude-code-guide` / `Explore` / `Plan`（built-in，sonnet） | 不寫 code，輕量化省成本 |
| 其他寫 code（暫無 custom subagent 對應） | `general-purpose` + `model: "opus"` | fallback，需在 prompt 內塞「extended thinking + xhigh effort 仔細思考、嚴格依規範執行、寧可慢、不要錯」字串 |

### 預設模型 opus xhigh

`Agent({ model: "opus" })`。Agent 工具只接受 `sonnet` / `opus` / `haiku` 這三個 tier 字串，**不能指定子版本**，會用 session 對應的 Opus 版本。

**沒有 `effort` / `thinking` / context-window 參數可以傳。** xhigh effort 必須在 prompt 內明確寫：「請以 extended thinking + xhigh effort 仔細思考、嚴格依規範執行、寧可慢、不要錯」。

**為何模型預設 opus xhigh**：[wave 6 招防護](#wave-6-招防護跨檔-refactor)實測 sonnet v1 Wave 7-10 連續踩 4 坑（Gotcha M / 雙寫 main / pytest 失準 / 漏更新 test）vs opus xhigh v2 零坑，既然 opus xhigh 是「跨檔 refactor 安全選項」乾脆預設化，省得每次判斷任務複雜度。**`sales-coder` frontmatter 已內建 `model: opus`（不寫 `effort` 欄位 → 繼承 session 預設，opus 4.8 = `high`），主 agent 派發不必再傳。** **例外**：純研究 / Explore 類 subagent 仍可手動指定 sonnet（成本考量）。

**Co-Authored-By trailer**：subagent commit 訊息用實際模型署名，預設 Opus → `Co-Authored-By: Claude Opus <noreply@anthropic.com>`，跟主 agent 的 Co-Authored-By 一致；研究類例外用 sonnet 時則為 `Claude Sonnet 4.6`。

### 為何不用 inline `Agent({skills: [...]})`

官方文檔（[subagents.md](https://code.claude.com/docs/en/subagents.md)）證實 Agent tool inline parameters **不接受 `skills` / `effort` / `thinking`**；必須走 `.claude/agents/<name>.md` frontmatter 預定義路徑。CLI `--agents` JSON flag 支援 skills 但屬 startup 級設定，session 內派發不適用。

從 system prompt 內 Agent tool schema：

```json
{
  "properties": {
    "description": ..., "isolation": ..., "model": ...,
    "prompt": ..., "run_in_background": ..., "subagent_type": ...
  }
}
```

**沒 `skills` 參數。** 所以必須走 `.claude/agents/<name>.md` frontmatter 預定義路徑。CLI `--agents` JSON flag 支援 skills（subagents.md line 225）但屬 startup 級設定，主對話內派發不適用。

---

## 規模門檻（派發 vs 主 agent 直接 patch）

派發門檻按**改動規模**決定，不只看「是否 worker-level」（規模門檻是更廣的規則，worker-level 為其特例）：

| 規模 | 處理方式 |
|---|---|
| 中小 / 中 / 中大 / 大 | **必派 sales-coder**，不論檔案類型（sales/ / main.py / tts.py / docstring 多段重寫 / const + 函數簽名變動 等都算）|
| **超級小** | 主 agent 直接 patch，但**必先** invoke `andrej-karpathy-skills:karpathy-guidelines` SKILL 載入規範再動手 |

**「超級小」定義（同時滿足才算）**：

- 改動 ≤ 3 行（excluding docstring / comment）
- 單一檔案
- 純值替換 / typo fix / const 數字微調，無邏輯結構改動
- 無新增 function / class / 簽名變動
- 無 cross-file propagation

**Why**：2026-05-30 commit `7661f10`（`wait_idle` `max_wait` 10s → 30s，3 處 const + docstring 更新）我判斷「const 調整 = 超級小」直接 patch。User 事後明確 feedback：「中小 / 中 / 中大 / 大都派 sales-coder，超級小才主 agent + karpathy-guidelines」。3 處 const + docstring 多段已超出「超級小」門檻（雖然 logic 一致但已是 cross-line propagation + docstring rationale 重寫）。我自己改沒踩雷但偏離規範。**規模主觀判斷向保守傾斜** — 不確定就派發。

**How to apply**：

- 任何 sales/ / myProgram/* 改動先評估：「行數 + 結構複雜度」屬哪一級
- 灰色地帶（如 const tweak 多處 / 多檔同步 typo / docstring 大段重寫）→ 派 sales-coder
- 確認「超級小」要動手前 — **強制** `Skill(skill="andrej-karpathy-skills:karpathy-guidelines")` 先載入規範
- karpathy 規範重點：surgical / verifiable / no over-engineering / no premature abstraction / 看到不對立刻修不放
- 歷史「超級小」實例（可繼續主 agent patch）：單字 typo 修一個字、單一 const 數字微調（如 `33e5fc2` 把「錯誤」從 NO substring 移到 strict_short 是 1 處改）、單行 import 刪除
- 歷史「不該超級小」實例：`7661f10`（3 處 const + 多行 docstring 重寫）、`a7d225e`（雖只 2 行但跨多 const + 改 punctuation + 加字 + 移除空格 = 多 dimension）、`55e029a`（const + import 移除 + 多行 docstring 更新）

---

## Worker / wire-up 結構改動規則

動到 `myProgram/{tts,action,input_reader,main}.py` 的 **worker 級程式碼或 callback wire-up**（不只 `myProgram/sales/`），即使我判斷「規模小、surgical」，**也要 EnterWorktree + 派 sales-coder**，不要直接主 agent Edit + commit。

**Why**：2026-05-30 commit `8e3aa67`（`tts.py` 加 `wait_idle()` + `_active` flag + `_loop` 抽 `_process_text` + try/finally 重構 + `main.py` callback wire-up）我判斷規模可控直接 patch。User 事後明確 feedback「下次這種大改動，要呼叫 sales-coder 比較好」。雖然 pytest 296 PASS 沒踩雷，但 worker thread 結構改動的盲點風險（race / state machine / try-finally 邊界 / 新 attr 跟既有 lock 互動）並非主 agent 一眼就能 grep 完，sales-coder 嚴格 TDD + 多角度檢查更穩。

**How to apply**：

- **觸發條件**：本輪 commit 涉及 `myProgram/{tts,action,input_reader,main}.py` 的**結構性改動**（新方法 / 新 attr / `_loop` 邏輯重排 / try-finally / lock scope / callback signature / wire-up 串接）→ 派 sales-coder
- **不觸發**：純 const 數字 / 純字串 const 改動 / 單行 typo fix / 純 docstring（仍可直接 patch）
- 配合 sales-coder 描述：「亦適用 `myProgram/main.py` callback wire-up / `myProgram/{tts,action,input_reader}.py` worker 級程式碼」— 不只 sales/ 業務邏輯
- 風險判斷：若改動涉及 race window / sticky state / try-finally / thread sync，**一律**派發。我直覺「小」≠ 客觀小

---

## 派發前必做（依序執行）

### Step 0：EnterWorktree

派發前主 agent 先進 worktree（除非是 bootstrap 例外）。subagent 繼承 cwd 自動在隔離環境內工作。完整流程見 [worktree.md](worktree.md)。

### Step 1：挑選相關的規則塞進 prompt

判斷當前任務可能踩到哪些規則，**不要全塞 CLAUDE.md，但寧可多塞不要漏。**

**已大幅精簡 — 標準規範由 frontmatter `skills:` 預載 + SubagentStart hook 補注入**：

- **不需自己塞（sales-coder 用 frontmatter 預載 SKILL 全文）**：karpathy-guidelines / test-driven-development — `.claude/agents/sales-coder.md` 的 `skills:` 欄位啟動時自動注入完整 SKILL.md
- **不需自己塞（SubagentStart hook 注入 reference）**：廠商 SDK 禁改 / 繁中 / 不用 `git add -A` / commit Co-Authored-By
- **仍需自己塞（任務特化）**：vendor-files API 細節 / 業務規格 / 設計決定（已 AskUserQuestion 對齊的 ambiguity）/ 既有 helper reuse 點 / git add 範圍 + commit message 範本
- 規則：subagent 是全新 context window；frontmatter + hook 只涵蓋「universal rules」，path-scoped + 任務特化規則仍需手動

常見規則對應（判斷當前任務「至少要塞」哪些）：

| 任務類型 | 至少要塞的規則 |
|---|---|
| 寫 / 改 Python 程式碼 | 路徑規範（Linux 絕對路徑）、檔案禁改清單（廠商兩檔）、廠商 SDK API、繁中規範（註解 / 字串）、git 收尾 |
| 寫文件 / markdown | 繁中規範、檔案結構查 `code_map` |
| 改設定 / 部署 | 部署資訊、git 收尾循環、`.gitignore` 規則 |
| 程式碼審查 / 重構 | 全套規範（禁令、路徑、繁中、廠商檔）|
| Pi 端設定 / 依賴 | Pi 端操作觸發條件（見 [pi-and-structure.md](pi-and-structure.md)）；**subagent 不寫操作說明書**，只在回報中列出 Pi 端需求；主 agent 在 worktree 階段 3a 統整寫成 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（append-only）並提醒使用者回報安裝狀況 → 收到回報後主 agent 更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單） |

### Step 2：載入 `karpathy-guidelines` Skill（2026-05-28 改 frontmatter 預載）

**新做法（推薦）**：寫 sales/ code 任務派 `sales-coder` subagent（`.claude/agents/sales-coder.md`），frontmatter `skills:` 欄位啟動時自動預載 SKILL **完整內容**（不是 reference summary）。**Why**：官方文檔 confirm `skills:` 預載 full content（[subagents.md#preload-skills-into-subagents](https://code.claude.com/docs/en/subagents.md)）；之前 SubagentStart hook 只注入一句 reference + Agent tool inline call **不支援** `skills` 參數，導致 karpathy SKILL 從未真正完整載入 subagent context。

**派發改成**：

```python
Agent({
  subagent_type: "sales-coder",  # frontmatter: model opus（無 effort → 繼承 session 預設 high）, skills: [karpathy, TDD, project-01-workflow]
  description: "...",
  prompt: "...任務描述 + 業務規格 + 既有 helper reuse 點 + git add 範圍 + commit message 範本..."
})
```

不必再傳 `model: "opus"`（frontmatter 已設）、不必再 paste karpathy SKILL 內容（已預載）；effort 用 session 預設（opus 4.8 = high），毋需 prompt 內塞 xhigh（要更高 effort 才手動要求）。

**舊做法（仍適用 fallback）**：built-in subagent（`general-purpose` / `Explore` / `Plan` / `claude-code-guide`）**不能改 frontmatter** — 派發時仍要 prompt 內塞一句 karpathy reference + manual 傳 `model: "opus"`。SubagentStart hook 自動注入 summary 補足。

**⚠️ Session restart 必要**：disk file 寫入後需 session restart 才 reload。`/clear` 不夠。CLI：`/exit` + `claude` 重跑；agent view 內：`Ctrl+X` stop + reattach。完整機制見下方「sales-coder 自訂 subagent」段。

### Step 3：明確要求嚴格遵守

派發 prompt 末尾要求 subagent **嚴格按照前述所有規範執行**，不要自由發揮。

### Step 4：明確界定「不該做什麼」（2026-05-26 補：post-commit closeout 邊界）

**現象**：Sonnet subagent 經常會越權做完整 worktree 5 階段收尾（ExitWorktree / `git merge --ff-only` / `git push` / `git worktree remove`），把主 agent 的職責也吞了。雖然結果通常正確，但這破壞主 agent 派發後審查的機會（一旦 push 出去就難回頭）+ Gotcha M 觸發時自行 workaround 可能造成 worktree 殘留。

**現象實例（2026-05-26 P0-P8 session）**：P3 subagent 自行做完 ff-merge / push / cleanup（但 worktree 殘留沒清，主 agent 補手動 cleanup）；P6 subagent 為避 Gotcha M 直接 cd 到主 checkout 工作。

**How to apply（派發 prompt 一律加）**：

```
## ⛔ 重要規範
- **不要做 post-commit closeout**（不要 ExitWorktree / 不 ff-merge / 不 push /
  不 git worktree remove）— 主 agent 自己收尾。你只做：編輯 → commit → 回報。
- **不要 cd 到主 checkout 路徑**（會引發 Gotcha M）— 維持在 worktree cwd 內
  工作；若 git 把 commit 落到 main 那是已知偶發 Gotcha M，主 agent 會 workaround
```

P4-P8 加入此規範後 5 個 subagent 全部守規，零越權。

---

## 派發後審查 + branch 驗證

不可直接把 subagent 的產出原封不動交給使用者。必須先審查：

### 1. 逐項對照 CLAUDE.md 規範檢查

- 中文是否全繁體？
- 有沒有改到 `ActionGroupControl.py` / `Board.py`？（hook 已擋；但 subagent 可能在無 hook 環境寫 plan 文字提到）
- 路徑有沒有用 Linux 絕對路徑？
- git 操作有沒有用 `git add -A`？（hook 已擋）

> 2026-05-25 自動化：標準規範（廠商檔 / `git add -A` / 繁中 / karpathy / commit Co-Authored-By）已由 SubagentStart hook 自動注入到 subagent context；PreToolUse hook 自動擋廠商檔編 + `git add -A`。審查時這些項目主要看「subagent 有沒理解 + 在 plan / explanation 內遵守」，動手執行的部分 hook 已守住。

### 2. 依偏差程度決定處理方式

- **小細節不符**（少數註解寫簡體、commit message 寫法不對、檔名小錯）→ **我自己直接修，省往返**。
- **大量偏差 / 核心理解錯誤**（整個檔案用簡體、修改了禁改檔、邏輯偏離需求）→ **退回 subagent 要求重做**，並把偏差點明確列出。

### 3. 絕不直接把不符合規範的產出交給使用者

我對最終交付負責。

### 4. 驗證 commit branch（2026-05-26 加，防 Gotcha M）

subagent 回報 commit SHA 後跑 `git branch --contains <SHA>` 確認落在 `worktree-*` branch；若顯示 `main` 表示 commit 跑錯 branch（已知偶發 bug），完整處理鏈：

| 步驟 | 動作 |
|---|---|
| 1 | `ExitWorktree(action="remove")` — 切回主 checkout（worktree branch 無新 commit，安全 remove） |
| 2 | 在主 checkout 跑 pytest / 審查新檔（main HEAD 已是 subagent commit） |
| 3a | **不需後續編輯** → 直接 `git push origin main` + hook 自動 sync，結束 |
| 3b | **需要主 agent 後續編輯**（code_map / pineedtodo 等）→ 進新 worktree + 編輯 + commit + ExitWorktree(keep) → **`git cherry-pick <SHA>`**（不能 ff-merge — 必失敗 diverging，因新 worktree 從舊 base 分出）→ push → `git worktree remove` + `git branch -D worktree-*`（用 `-D` 大寫因 branch 未被 ff-merged） |

**歷史案例**：2026-05-26 Wave 0：subagent commit `d60798e` 落 main → projectStructure 更新 commit `2976566` 在新 worktree branch → ff-merge fail diverging → cherry-pick 成 main `bd77ded`。**完整文檔**：[worktree.md](worktree.md) §Gotcha M（含 diverge 陷阱徵兆速查 + 完整解法）。

---

## Wave 6 招防護（跨檔 refactor）

派 subagent 做含「跨檔簽名變動 + 既有 test 連動更新」的 Wave 時，**模型升級到 opus + xhigh effort + 6 招防護**比單純拆細範圍更有效。2026-05-26 Wave 7-10 兩次實測對比（sonnet 踩 4 坑 vs opus xhigh 零坑）驗證。

**Why**：第一次 Wave 7-10 用 sonnet subagent 連續踩 4 個坑（Gotcha M / 雙寫 main checkout / pytest 自報「231 passed」實際漏 fail / 漏更新 `test_l2_duplicate_product_accumulates`），revert 後第二次改用 opus xhigh + 6 招防護，3 個 wave 連跑零坑、pytest 233 passed 一次到位。

### 1. 模型用 opus（搭配 prompt 內要求 extended thinking + xhigh effort）

Agent tool 的 `model` 參數選 `"opus"`；prompt 內寫「請以 extended thinking + xhigh effort 仔細思考」「寧可慢、不要錯」。對範圍大或結構動較深的任務（如改函式簽名 + 連動 ≥10 個 test），opus 大幅優於 sonnet。

### 2. 6 招防護（prompt 內必含）

**招 1：先列再做** — prompt 要求 subagent 開工前先 grep 受影響檔 / test，**在 thinking 內列出來再下手**。

- 範例：「grep `key == "q"` + `q` 相關 test，列出所有受影響檔 + test 數量」
- 落實：subagent return 必含「Step A 列的清單」

**招 2：每條改動完跑 pytest** — 不要等全部改完才跑，每條獨立的改動結束後跑一次。任一改動破其他 test 立即發現。

**招 3：commit-前自檢** — commit 前必跑：

```bash
git diff --stat
git status
python -m pytest tests/sales/ -v --tb=short
```

**招 4：pytest verbose 不省** — 跑 `python -m pytest -v --tb=short`（**不是** `-q`），回報含最後 30 行。subagent 自報「231 passed」可能不準 — verbose 看 case 名才能驗證對齊。

**招 5：規格衝突 test 必停回報** — 若改動使既有 test fail 但**修法明顯需要更新 test**（如業務行為變更）→ 主動更新並列清單。**若修法不明顯** → 停下回報，不要自作主張改 test。

**招 6：任何 fail / xpass / error 必停** — commit 前若 pytest 有任何 fail → **不要 commit**，停下回報。

### 3. 主 agent 端驗證（兩招最關鍵）

subagent commit 後**主 agent 必跑**：

**驗證 A：主 checkout 雙寫檢查**

```bash
cd "C:/Users/LIN HONG/Desktop/Project_01"
git status
```

應該 `nothing to commit, working tree clean`。若主 checkout 有未提交變動 → 表 subagent 雙寫了，要處理（見 [worktree.md](worktree.md) §Gotcha M）。

**驗證 B：主 agent 自跑 pytest**

不信任 subagent 自報。在 worktree 內自跑：

```bash
cd "C:/Users/LIN HONG/Desktop/Project_01/.claude/worktrees/<name>"
python -m pytest tests/sales/ --tb=no -q
```

應數字對齊 subagent 報的。任何不一致 → 主 agent 介入。

### 4. Wave 大小拆分原則

opus xhigh 也別讓單個 subagent 一次做 ≥8 條改動的跨檔重構。**經驗值**：

- **≤ 6 條低風險改動**（純字串 / 純數字 / 局部邏輯）= 一個 subagent OK
- **2 條結構動較深**（簽名變動 + 連動 ≥10 個 test）= 一個 subagent OK
- **≥ 8 條混合**（含結構動）= 拆兩個 subagent 序列做

2026-05-26 實測：Wave 7 原本 8 條一次（v1 sonnet）踩坑；拆成 7a（6 條低風險）+ 7b（2 條結構動）（v2 opus xhigh）零坑。

### 5. 不要過度拆

「一條一 subagent」也不對 — 8 條改動派 8 個 subagent 平行做 worktree 會檔案衝突（多個 subagent 改同樣的 `nlu.py` / `l1.py` 等），8 個 branch merge 比 2 個還複雜。**序列做拆 2-3 個 subagent 是甜蜜點**。

### 歷史案例

- **2026-05-26 v1（sonnet）踩坑紀錄**：
  - Wave 7a commit `5e76c68` 落 main（Gotcha M）+ 漏更新 `test_l2_duplicate_product_accumulates`
  - Wave 7b commit `c37a80e` 雙寫 main checkout 13 檔
  - 主 agent 後續修補：`dc58b4d` regression / cherry-pick / 第二輪 worktree diverge
- **2026-05-26 v2（opus xhigh + 6 招）**：
  - 全 revert v1 commits 回 Wave 6（用 `git revert` 不用 force push，Pi 端 `git pull` 自動同步）
  - 重做 Wave 7a → 7b → 10 連續三輪零坑，最終 pytest 233 passed

---

## sales-coder 自訂 subagent 說明

**2026-05-28 加：`.claude/agents/sales-coder.md` 自訂 subagent** 透過 frontmatter `skills:` 欄位**啟動時預載 SKILL 完整內容**（不是 reference summary）。**Why**：user 提示研究後發現先前主要派 subagent 的 `karpathy-guidelines` 從未真正完整載入 — SubagentStart hook 只注入一句 reference + Agent tool inline call **不支援** `skills` 參數。**How to apply**：寫 sales/ code 任務派 `Agent({subagent_type: "sales-coder", ...})` 取代既有 `general-purpose + model: opus + prompt 內塞 effort 字串`。

### 官方文檔 confirmation（`/en/subagents`）

**subagents.md line 274**（Supported frontmatter fields 表格）：

> `skills` | Skills to **preload into the subagent's context at startup**. **The full skill content is injected, not just the description.** Subagents can still invoke unlisted project, user, and plugin skills through the Skill tool

**Preload skills 段（line 426-444）**：

> "The full content of each listed skill is injected into the subagent's context at **startup**. This field controls which skills are preloaded, not which skills the subagent can access"

**限制（line 444）**：

> "You cannot preload skills that set `disable-model-invocation: true`. If a listed skill is missing or disabled, Claude Code skips it and **logs a warning to the debug log**."

**Plugin namespace 語法（skills.md line 110）**：

> "Plugin skills use a `plugin-name:skill-name` namespace"

→ `andrej-karpathy-skills:karpathy-guidelines` 是合法 frontmatter `skills:` list 內語法。

### 當前 sales-coder.md frontmatter

```yaml
---
name: sales-coder
description: 派發給 sales-coder 來實作或修改 myProgram/sales/ 業務邏輯 + 對應 tests/sales/ 測試。亦適用 myProgram/main.py callback wire-up / myProgram/{tts,action,input_reader}.py worker 級程式碼。Karpathy guidelines + TDD skill 會在 subagent 啟動時自動預載完整內容，主 agent 不必再在 prompt 內塞 reference。
model: opus
skills:
  - andrej-karpathy-skills:karpathy-guidelines
  - test-driven-development
  - project-01-workflow
---
```

**主 agent 派發只傳**：

```python
Agent({
  subagent_type: "sales-coder",
  description: "...",
  prompt: "...任務描述 + 業務規格 + 既有 helper reuse 點 + git add 範圍 + commit message 範本..."
})
```

不必再塞 `model: "opus"`、不必再 paste karpathy SKILL 內容 — frontmatter 已預設；effort 用 session 預設（opus 4.8 = high），毋需 prompt 塞 xhigh。

### ⚠️ Session restart 必要性

**官方文檔（subagents.md line 242）**：

> "Subagents are loaded at session start. If you add or edit a subagent file directly on disk, **restart your session** to load it. Subagents created through the `/agents` interface take effect immediately without a restart."

**對 Claude Code CLI 的具體含義**：

- 用 Write tool 寫 disk file → 需要 restart session 才生效
- `/clear` slash command **不重 read** subagent files（只清 conversation context）
- 「Restart」方法：
  - **CLI**：`/exit` 後重跑 `claude`
  - **agent view 內**：`Ctrl+X` stop 該 background session + 重 attach → supervisor spawn **fresh process** → re-read `.claude/agents/`
  - 或外部 shell：`claude stop <id>` + `claude attach <id>`（或 `claude respawn <id>`）
  - **Desktop / Web**：點「New chat」
- **驗證方法**：restart 後 user 隨便派個任務（如「印 hello」）給 `Agent({subagent_type: "sales-coder"})`，失敗會回「unknown subagent_type」，成功代表 reload OK。

### Built-in subagents 不適用此機制

文檔（subagents.md line 785-787）：

> "Preloaded skills: full content of any skill named in the agent's skills field. **Built-in agents don't preload skills.** Explore and Plan are the only subagents that omit CLAUDE.md and git status."

Built-in subagent（`Explore` / `Plan` / `general-purpose` / `claude-code-guide` / `statusline-setup`）**不能改 frontmatter**，仍只能靠 SubagentStart hook reference 注入。若需完整 SKILL 走 built-in subagent → 必須主 agent 在 prompt 內 paste 全文。

### 為何 Agent tool inline call 不支援 skills

見上方「為何不用 inline `Agent({skills: [...]})`」段的 Agent tool schema — 沒 `skills` 參數，所以必須走 `.claude/agents/<name>.md` frontmatter 預定義路徑。

---

## 自動化補充

- 📦 **`sales-coder` 自訂 subagent**（2026-05-28 起）`.claude/agents/sales-coder.md` 透過 frontmatter `skills:` 預載 karpathy-guidelines + test-driven-development **SKILL 完整內容**（非 reference summary）。**外部直接編輯 / 新增** subagent 檔需**重啟 session** 才生效；只有**在 `/agents` 互動介面內建立 / 編輯**的 agent 才立即生效（官方文檔：「edit a subagent file directly on disk → restart your session to load it」；`/agents` 的即時生效**不涵蓋**外部改檔——別誤以為開 `/agents` 就能 reload 已外部改的檔）。built-in subagent（Explore / Plan / general-purpose / claude-code-guide / statusline-setup）不支援 frontmatter 預載。
- 🪝 **SubagentStart hook**（2026-05-25 起）自動注入標準規範。Subagent 看到的 context window 開頭會有「SubagentStart 標準規範注入」段，包含 ⛔ 禁止項 / 強制規範 / 文檔指標。
- 🪝 **agent_type 分流**：研究類（claude-code-guide / Explore / Plan）注入精簡版（只含繁中 + 文檔指標）；編碼類（general-purpose / sales-coder / 其他自訂 agent）注入完整規範。
- 🔗 **完整 hook 文檔**：`.claude/hooks/NOTES.md`

---

## SDD v3 升級（2026-05-31）— 派發行為新增層

寫 `myProgram/` 任何 `.py` code 觸發 SDD（見 [sdd.md](sdd.md)）後，dispatch pattern **不變**但增加：

### Prompt 內容新增（sales-coder 派發 prompt 必含）

- **Spec/Plan 兩檔路徑**：`resources/specs/<name>_<date>_spec.md` + `<name>_<date>_plan.md`（v3 起兩檔；mini spec 不拆）
- sales-coder frontmatter 已預載 SDD 任務協議段（spec first / TaskCreate / Definition of done / 偏離標明 / Status 4 選 1 / self-review 4 類），prompt 不必再塞這些通用規範
- 任務特化規則（commit msg 範本 / git add 範圍）仍要 prompt 內塞

### Subagent 回報強制 4 狀態

- sales-coder 回報**首行**必選 1：**DONE** / **DONE_WITH_CONCERNS** / **BLOCKED** / **NEEDS_CONTEXT**
- 主 agent 依 status 處理：BLOCKED / NEEDS_CONTEXT → 提供 context 重派；DONE → 進三段審查

### 派發後 v3 三段 subagent 迴圈（取代「主 agent 一次審查」）

1. **主 agent Iron Law 自驗** — 跑 pytest + `git branch --contains` verify（evidence before claims）
2. **派 spec-reviewer**（fresh `general-purpose` + sonnet）— prompt template 見 `examples/` 內 spec-reviewer 範本；查 spec compliance（missing / extra / misinterpreted）；✅ → 進第 3 段 / ❌ → 派 sales-coder fix → 重審
3. **派 code-quality-reviewer**（fresh `general-purpose` + opus xhigh）— prompt template 見 `examples/` 內 code-quality-reviewer 範本；查 code quality（karpathy 違反 / 命名 / 檔案組織等，分 Critical / Important / Minor）；✅ / ⚠️ 主 agent 判決 / ❌ 派 sales-coder fix → 重審

### 何時跳過三段審查

- **Mini spec**（≤ 3 行 code 改動）：主 agent 自己 patch + Iron Law verify，不派任何 subagent
- **非 myProgram/ code 改動**（rules / agents / memory 編輯）：主 agent 自實作，不派 subagent

詳見 [sdd.md](sdd.md) §三段 subagent 迴圈詳解。

---

**相關 reference**：[worktree.md](worktree.md) / [standard-workflow.md](standard-workflow.md) / [sdd.md](sdd.md) / [pi-and-structure.md](pi-and-structure.md) ｜ karpathy 準則用 Skill 工具 invoke `andrej-karpathy-skills:karpathy-guidelines`
