# project-01-workflow skill 全面精簡整改 — Spec

> **任務性質**：meta-task（整改 `.claude/skills/project-01-workflow/` 下的 `reference/` + `examples/` 文件），非 myProgram code。依 `reference/sdd.md` §不觸發條款，主 agent 自行實作、不派 sales-coder、不走三段 reviewer。本 spec 作為執行契約。
> **建立日期**：2026-06-02
> **依據**：4 個唯讀 Explore agent 的逐檔分析 + 主 agent 對已讀 5 檔（sdd / dispatch / standard-workflow + 2 examples）的跨檔比對 + 官方 *Skill authoring best practices* / *CC-skills* 文檔（見 §9）。

---

## 1. 背景與動機

`project-01-workflow` skill 的 reference/examples 共 14 檔、約 3519 行，長期累積出大量冗餘：

- 顆粒度錯置：dormant 的 `bdd-tdd.md` 寫了 412 行；核心設計表反而沒被保護。
- 同一概念跨 3-4 檔各寫一份完整版（drift 風險，本 session 已修過數次同類病）。
- 歷史敘事肥肉：逐 commit SHA 時間線 + 「2026-05-XX 我踩了什麼坑」長故事，技術結論被埋沒。

目標：**能刪的刪、能精簡的精簡，講重點、零冗餘重複，但不失重點細節**（核心設計決策 / 行為規約 / 操作步驟 / Gotcha 解法 100% 保留）。

---

## 2. 治理原則（governing principles）

整改套用以下尺規（借鏡官方 *Skill authoring best practices* + *Effective context engineering* + *Seeing like an agent*，見 §9）：

1. **簡潔測試（核心）**：假設「Claude 本來就很聰明」，每段自問「這段它需要嗎？能不能假設它已懂？這段值不值它的 token？」——通用知識（PDF 是什麼 / git 怎麼運作 / 名詞解釋）一律砍。**理據**：context rot——準確度隨 token 數上升而衰退，每個 token 都在耗 attention budget；reference 雖「不讀不耗 context」，但**一旦載入就吃 attention**，故砍噪訊＝提升訊號密度，不是純為了短。
2. **顆粒度 = right altitude / degrees of freedom**（官方框架，對應 user 的「該細的細、該粗的粗」）：在「過死（brittle 硬規則）」與「過虛（無具體訊號）」之間取 Goldilocks。
   - **高自由度**（純文字方向）：多解法皆可、依情境判斷 → 給方向就好，別寫死。
   - **中自由度**（虛擬碼 / 帶參數）：有偏好 pattern、容許變化。
   - **低自由度**（精確命令 / 不可改）：脆弱易錯、順序關鍵、一致性至上 → **必須精確、逐字保留**。
   - 對照：行為矩陣 / timeout 矩陣 / 操作命令 / Gotcha 解法 = 低自由度（必留細）；演化敘事 / 決策背景 = 可砍。
3. **歷史處理**：純 commit SHA 時間線 → 砍（進 git log）；**有決策價值的「為何不再這樣做」→ 收進摺疊 `<details><summary>舊做法</summary>` 區**（官方 "old patterns" 法，留脈絡不佔版面），非無腦刪。
4. **每檔自足、references 一層深、不互指**（官方反模式 + user 2026-06-03 定案）：
   - SKILL.md 是唯一 hub（SKILL.md → reference 一層深）；**reference 之間不做 load-bearing 互指**（避免 Claude 只 `head -100` 部分讀漏資訊）。
   - 跨檔重複**不靠指回解決**，改靠**概念歸屬**（見 §4）：判某概念屬哪檔的 `🎯` 範圍 → 屬本檔留**自足最小版**（夠在本檔完成操作、不必跳走）；不屬本檔**整段砍**（不留指標、不留複製）。
   - 容許「為自足而存在的最小重複」（如 worktree 階段 4 自列 4 行 git 命令），但**禁止整段重貼別檔完整內容**；深層 why/背景只留權威檔。最多一句非承載性「see also」。
5. **meta 自述全砍**：「每個 section 對應一份 memory，忠實搬運」這類檔案自述、過度導讀。
6. **層 2 自述 + TOC**：每個 reference 開頭保留精簡 `🎯 何時讀本檔`（1-3 行；這是「兩層確認」的第 2 層——模型開檔即判要不要續讀；本身也要簡潔別變肥）；砍完仍 >100 行者開頭加「## 目錄」TOC（官方法，確保部分讀也看得到全貌）。examples 保留一句「何時用」。
7. **一致術語 / 具體範例必留 / 清單→範例 / 正斜線 / 不堆選項**：同義詞統一（一個詞用到底）；**教格式的具體範本**（commit message / pineedtodo / spec template）必留；**長 edge-case 清單 → 壓成幾個 canonical 範例**（官方「examples 勝過 laundry list」）；路徑一律 `/`；多解法只給一個 default + 逃生口。
8. **不新增檔案**：不拆 `bdd-tdd-full.md`、不建 `chinese-conventions.md`（拆檔增加導航複雜度又要動 SKILL 路由表；progressive disclosure 已讓檔案用到才載，原地砍即可）。
9. **繁簡對照表留在 `conventions.md`**：root CLAUDE.md 明寫「簡繁對照細節見 skill `reference/conventions.md`」，它是指定單一來源，不外移。

---

## 3. 逐檔整改目標（current → target；行數為本回合 `wc -l` 現值）

| 檔 | 現行 | 目標 | 主要動作 | 必留（不准砍） |
|---|---|---|---|---|
| `SKILL.md`（主入口） | 50 | ~45 | description 收緊（前置觸發關鍵字、去贅、第三人稱；**skill-creator 觸發優化輔助**）；兩層觸發說明/路由表必要微調；body 已精簡過 | 路由表、兩層觸發說明、巢狀 code_map 指標、跨任務鐵則 |
| `reference/bdd-tdd.md` | 412 | ~150 | dormant→重砍：刪重複觸發條件（18-31 或 42-51 擇一）、DEGRADED 三寫合一、Iron Law 指回 TDD skill、派發清單指回 dispatch.md、歷史 tests 累加數刪 | 重啟條件、4 階段鳥瞰、dispatcher pitfall 教訓 |
| `reference/sales-dialog-design.md` | 405 | ~260 | 砍 C-2 反轉 commit 軌跡（37-62）、改動規模（92-101）、L4 沿革 commit 欄、meta 自述（7）；keyword 段壓成表 | **C-2 三選一表、L4 預算虛擬碼+6×7 行為矩陣、cancel_confirm/service_confirm 完整規約** |
| `reference/sales-tts-ux.md` | 289 | ~190 | 砍 v1/v2/v3 演化敘述（65-79）、未來 4 情境預估（256-264，移 roadmap 或刪）、meta（7） | **speak_and_wait 架構、全層 timeout 矩陣、倒數 polling pattern、ack/UX 優先原則** |
| `reference/dispatch.md` | 423 | ~270 | 砍 sonnet 踩坑長敘事（wave 6 招歷史案例壓成教訓）；三段迴圈/Status 表指回 sdd.md；模型機制留本檔 | 規模門檻表、subagent_type 表、6 招防護要點、Gotcha M 處理（指回 worktree）|
| `reference/sdd.md` | 434 | ~320 | adversarial pose（239-257）濃縮+指回 examples；「為何 fresh-context」收斂為單一短版；Anti-patterns 壓縮 | 4 階段流程圖、Iron Law gate function、必跑指令對照表、Red Flags 表 |
| `reference/myprogram-threading-paths.md` | 238 | ~140 | S6 五輪修補（104-238）改「最終穩定設計 + 5 個要避免的 bug」列表；Fatal error/subagent 偏離敘述刪；地雷區壓成表 | 推薦架構表、Linux 路徑規範、最終穩定設計 |
| `reference/pi-and-structure.md` | 238 | ~185 | 砍專案背景介紹（119-120）、歷史紀錄 footnote；sync 規範指回 standard-workflow | trigger 清單、pineedtodo 規範、GLIBC/piwheels + git 對齊兩 gotcha、部署資訊表 |
| `reference/incremental-rebuild.md` | 182 | ~115 | 背景敘述（8-11）刪；單 queue（102-143）/sticky（145-177）從教學改規則清單 | 單 queue 洞察+how to apply 簡版、sticky 旗號規則（本檔為權威）|
| `reference/worktree.md` | 188 | ~125 | 階段 3a/3b/4 詳說指回權威檔；Gotcha M 歷史時間線壓成一句 | **5 階段命令、Gotcha M 解法表+cherry-pick、Windows lock fallback、subagent 視野表** |
| `reference/standard-workflow.md` | 208 | ~150 | pycache 兩 commit 案例壓成教訓；歷史 bug 段壓縮 | 5 步收尾、background sync 雙保險（本檔為 sync 權威）、觸發/不觸發判準 |
| `reference/conventions.md` | 128 | ~95 | 輸出語言段指回 CLAUDE.md（只留「派發時塞 prompt」）；bug 掃同類 why 壓簡；cp936 邏輯理順 | **繁簡對照表（root 指定單一來源）**、/goal 條件設計 |
| `examples/spec-reviewer-prompt.md` | 122 | ~90 | 砍「為何要 fresh-context」段（117-122，指回 sdd.md） | prompt 範本本體、3 大類檢查、回報格式 |
| `examples/code-quality-reviewer-prompt.md` | 139 | ~105 | 砍「為何要 fresh-context」段（124-130，指回 sdd.md） | prompt 範本本體、7 類審查、處理表 |

**總計 ~3519 → ~2300 行（砍 ~35%）**，全砍在歷史/重複/meta；核心設計與操作細節 100% 保留。

> 行數為估計目標、非硬指標——以「砍完冗餘後自然剩多少」為準，不為湊數字犧牲細節。
>
> **§2.4 定案後修正**：上表「主要動作」欄凡寫「指回 X」者，一律改解讀為「砍到自足最小版 或 整段砍」（依概念歸屬 §4），**不做 load-bearing 互指**。

---

## 4. 概念歸屬對照（完整版主檔；其餘檔砍到自足最小版 or 整段砍）

> user 2026-06-03 定案：**每檔自足、不互指**（§2.4）。下表「主檔」放完整版；其餘檔依該概念是否屬自己 `🎯` 範圍，要嘛留**自足最小版**（夠在本檔操作、不跳走），要嘛**整段砍掉**（不留指標、不留複製）。

| 概念 | 完整版主檔 | 其餘檔處理 |
|---|---|---|
| git 收尾 5 步 + sync 雙保險 + pycache | `standard-workflow.md` | worktree.md 階段 4：自留 4 行 git 命令（自足最小版）；sync「為何 best-effort」深層 why **砍**。pi-and-structure.md：sync 深層說明**砍** |
| pineedtodo 規範 + code_map 更新判準 + Pi 部署 | `pi-and-structure.md` | worktree.md 3a/3b：只留「此階段做啥」一句操作摘要；判準細節**砍** |
| SDD 4 階段 + 三段 reviewer + 為何 fresh-context + Status 表 | `sdd.md` | dispatch.md「v3 升級」：砍重述、只留 dispatch 特有差異；2 examples 的「為何 fresh-context」整段**砍** |
| Gotcha M（commit 落 main 處理） | `worktree.md` | dispatch.md §派發後驗證：留觸發徵兆一句、完整解法**砍** |
| sticky 旗號 + 單 queue 設計 | `incremental-rebuild.md` | vendor / threading-paths：各留「本檔脈絡下一句結論」，完整推導**砍** |
| 派發模型 / 機制 / 6 招防護 | `dispatch.md` | sdd.md 三段迴圈：只列角色+模型一行，機制**砍** |
| 輸出語言（繁中）紅線 | root `CLAUDE.md` | conventions.md：只留「派發時塞 prompt」+ 繁簡表 |

**注意**：
- **不互指 load-bearing**：reference 之間不得用「見 X.md」當操作依賴（官方一層深反模式，避免部分讀漏資訊）；最多一句非承載性「see also」。
- 跨檔重複**靠砍/歸屬解決，不靠指標**：屬本檔→自足最小版；不屬→整段砍。判準＝該概念落在哪檔的 `🎯 何時讀` 範圍。
- 驗證見 §6（含「不追 2 跳就無法操作」反例檢查）。

---

## 5. 執行方式

採 cluster 分批，每批一個 commit、給 diff 審。**動刀前先跑 T0 baseline eval（§10）存 transcript**。建議順序：

1. **SDD/reviewer cluster**（校準樣本）：`sdd.md` + `dispatch.md` + 2 examples — 跨檔去重最明確，先做給 user 校準精簡力度。
2. **process cluster**：`worktree.md` + `standard-workflow.md` + `pi-and-structure.md`（git 收尾/sync/pineedtodo 單一來源化）。
3. **threading cluster**：`myprogram-vendor.md` + `myprogram-threading-paths.md` + `incremental-rebuild.md`。
4. **sales cluster**：`sales-dialog-design.md` + `sales-tts-ux.md`。
5. **dormant/conventions cluster**：`bdd-tdd.md` + `conventions.md`。

> 每 cluster 改完 → 重跑該 cluster eval 場景 → grader + comparator 比對 baseline（§10）→ 退化補回 → 再 commit。cluster 1 做完先停給 user 確認力度，再用同一把尺續做 2-5。

---

## 6. 驗證（Iron Law：沒驗證不得宣告完成）

> 行為驗證主軸見 §10 EDD（skill-creator executor 實跑 + grader/comparator 判定）；以下為**靜態互補檢查**。

每 cluster 改完：

1. **必留項 checklist**：對照 §3「必留」欄逐項 grep / Read 確認仍在（尤其行為矩陣 / timeout 矩陣 / Gotcha 解法 / 繁簡表）。
2. **跨檔連結不斷裂**：grep 改檔內所有相對連結（`](*.md`）+ 指回目標段名存在。
3. **SKILL.md 路由表一致**：reference 檔名沒變（只改內容）→ 路由表不需動；若有檔被大幅改名/合併才更新（本 spec 不改檔名、不刪檔）。
4. **無新 stale 交叉引用**：grep 確認沒留下指向已刪段落的指標。
5. **自足 / 一層深 / TOC**：確認無 load-bearing 互指（reference 不靠「見 X.md」才能操作）、各檔對自己 `🎯` 範圍自足；砍完仍 >100 行的檔有「## 目錄」TOC（§2.6）。
6. **路徑 / 術語**：grep 無反斜線路徑（一律 `/`）；關鍵術語前後一致（§2.7）。

---

## 7. Out of scope（明示不動）

- **skill 目錄內**不改檔名、不刪整檔、不新增檔（§2.8）。**例外**：本輪於 `resources/evals/` 新增 EDD 持久套件（§10）——在 skill 目錄外，不受此限。
- **SKILL.md**（2026-06-03 納入精簡範圍）：只**微調 description（前置關鍵字、去贅、第三人稱）+ 兩層觸發/路由表必要指標**；**不重構 router 架構、不拆多 skill**（mega router 模式官方允許，見 §9）。
- **不動 myProgram/ 任何 code、不動 CLAUDE.md / code_map / hooks / agents**（本輪只碰 reference + examples）。
- **不動 `resources/` 其他檔**（除 §10 的 `resources/evals/`）。
- **skill-creator 只用其 eval 機器（executor/grader/comparator/benchmark）+ `run_loop.py`**；**不跑 `package_skill`、不產 `.skill`、不重建 skill 結構**。

---

## 8. Commit 規範

- 每 cluster 一 commit，message 英文 + 引用本 spec（`per skill_reference_cleanup_2026-06-02_spec.md §3`）+ 結尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- `git add` 明列改檔名，不用 `git add -A`。
- 各 cluster push 後手動 `& sync_pi.ps1`（idempotent；docs 不影響 Pi runtime）。

---

## 9. 依據的官方最佳實踐（本輪併入）

- **Skill authoring best practices**（platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices）— 本輪主要來源。採用：簡潔測試（假設 Claude 已聰明）、degrees of freedom 顆粒度框架、避免 time-sensitive→「old patterns」摺疊區、references 一層深、>100 行加 TOC、一致術語、具體範例、正斜線、不堆選項、給 default+逃生口。
- **CC-skills.md**（`resources/research/CC-skills.md`，官方 zh-TW skills 頁）— progressive disclosure、SKILL.md <500 行、「每行都是恆載 token 成本」、skill 內容生命週期（25k 預算）、description 前置關鍵字。
- *How Claude Code works in large codebases* / *Set up Claude Code in large codebase*（`resources/research/` 內既有筆記）— lean & layered、主題分層 vs 空間分層。
- **Effective context engineering for AI agents**（anthropic.com/engineering）— right altitude（Goldilocks：過死 brittle vs 過虛）、**context rot / attention budget**（token 越多準確度越降，每 token 都耗 attention）、curate examples > rule list、start minimal-add deliberately、just-in-time 檢索勝過預載。
- **Seeing like an agent**（claude.com/blog）— 大段文件造成 context rot → 文件要輕量分段、系統知識與任務指南分開；skill 檔當 discovery 機制。
- **Skills explained**（claude.com/blog）— skills=程序「how」/ memory=「what you know」/ subagent=隔離執行；granularity 依功能邊界非大小；官方無強制「一 skill 一能力」→ 本專案 mega router 合法。

- **Improving skill-creator: test, measure, refine**（claude.com/blog）+ **skill-creator skill 本體**（全域安裝）— EDD 回歸偵測 / capability obsolescence / benchmark（pass-rate/time/token）/ A/B 盲判 / description 觸發優化。

> **2026-06-03 更新**：先前把 evaluation-driven / 多模型測試 / Claude-A-B 列為「僅新建 skill 適用、本輪不納入」——此判斷已**推翻**。精簡＝回歸測試，eval 同樣適用且更能證明「沒砍掉重點細節」。已落為 §10。

---

## 10. EDD（Evaluation-Driven Development）驗證層

> 2026-06-03 brainstorming 定案。**用 skill-creator 機器全程**跑回歸（improve 模式＝舊版 vs 新版）；eval 存成**持久套件**供未來模型升級重跑。skill-creator 內部已研究（SKILL.md + grader/comparator/analyzer + run_loop.py），確認適配（見 §10.5）。

### 10.1 用 skill-creator 機器跑回歸（角色對映）

我們自備：**5 場景（§10.3）+ 每場景的 transcript-可判定 assertions**；其餘交給 skill-creator：
- **executor subagent**：全新乾淨 context 跑場景任務、存 transcript + 輸出。
- **grader subagent**：對 transcript+輸出逐條判 assertion pass/fail，**並自動批爛 assertion**（防 false confidence）。
- **comparator subagent**：**盲判**舊版 vs 新版輸出（不知哪版是哪版），出 winner + rubric——落實「砍的人不當判官」。
- **analyzer + aggregate_benchmark**：聚合 pass-rate / time / token（mean±stddev + delta）+ 跨 run 模式（非辨別性 assertion、高變異 flaky 等）。
- fresh-context executor/grader 即官方「觀察導航」。

### 10.2 時序（baseline 動刀前抓；不用 snapshot）

```
T0  baseline：精簡前，5 場景各跑 executor → 存 transcript+輸出（resources/evals/baseline/）
T1..T5 每 cluster：精簡 → 重跑「踩到該 cluster」場景 → grader + comparator 比對 baseline → 退化補回 → commit
T_end：① run_loop.py 跑 SKILL.md description 觸發優化 ② 全 5 場景最終 A/B 盲判 ③ benchmark token/time 前後對比
```

- **為何不用 skill-creator 的 snapshot-baseline**：它假設「以路徑顯式叫 skill」；本 skill 是 **auto-load project skill**，snapshot 會與 live 雙載撞車。故 baseline 改走「動刀前時序」存 transcript，最穩。
- **多模型**（官方 test-with-all-models）：場景 1（reviewer/sdd）另用 **sonnet** 跑一次（spec-reviewer 實際用 sonnet），確認精簡後 sonnet 也讀得懂；其餘用 session 模型。

### 10.3 持久 eval 套件 `resources/evals/`

- `resources/evals/evals.json`（skill-creator schema：`prompt` + `expected_output` + `expectations[]`）+ `baseline/`（T0 transcript+輸出）。
- **assertion 設計 caveat（最難處）**：要寫**可從 transcript 判定的流程 assertion**，例：「transcript 顯示讀了 `reference/sdd.md`」「最終 plan 含三段 reviewer + Iron Law 步驟」「未開第 2 個 reference 即完成」。爛 assertion（只查表面）會給假信心 → grader 會自動挑出來批，當安全網。
- 5 場景（每 cluster 一、刻意踩該 cluster 要砍的必留細節）：

| # | cluster | 任務 | 踩到的必留細節 |
|---|---|---|---|
| 1 | SDD/reviewer | 派 sales-coder 改 L4 budget timeout、走三段 reviewer | sdd 4 階段 / Iron Law / examples rubric |
| 2 | process | tracked 檔收尾，commit 誤落 main（Gotcha M）怎麼救 | worktree 5 階段 / Gotcha M 解法 / sync 雙保險 |
| 3 | threading | 新增讀 STT 的 worker thread，避開 stale .pyc / 單 queue / sticky | 單 queue 洞察 / sticky 規則 / pycache |
| 4 | sales | L3「沒有了」進結帳 confirm，設計 cancel_confirm 行為 | C-2 三選一表 / cancel_confirm 規約 / timeout 矩陣 |
| 5 | dormant/conv | 新增一條 sales 業務邏輯重啟 BDD+TDD + 繁簡產出 | bdd 重啟條件 / 繁簡表 |

- **未來用途**：模型升級重跑＝regression detection；若某場景 base model 不靠 skill 也過＝capability obsolescence 訊號（該段可再瘦身/退役）。

### 10.4 description 觸發優化（run_loop.py）

- T_end 跑 `python -m scripts.run_loop --eval-set <trigger.json> --skill-path <project-01-workflow> --model <session 模型 id> --max-iterations 5`。
- trigger eval：**20 條**（8-10 should-trigger / 8-10 near-miss should-not）、具體擬真（含檔路徑/情境/口語）；60/40 train/test、best-by-test（防 overfit）。
- skill-creator 觸發觀察：Claude 只對「自己難一鍵搞定的」任務才諮詢 skill → trigger 查詢要夠實質（多步專案任務），別用「讀個檔」這種一步小事。
- 產出 `best_description` → 更新 SKILL.md frontmatter，給 user 看 before/after + 分數。

### 10.5 skill-creator 適配結論 + 邊界

- **適配良好**：improve 模式 baseline＝舊版 vs 新版＝我們的「精簡回歸」；grader 吃 transcript 能判流程 assertion；run_loop 描述優化即插即用。
- **不用的部分**：`package_skill` / 產 `.skill`（改 in-repo project skill、不打包分發）；viewer 的檔案產物渲染（我們「產出」是 plan/transcript，倚重 transcript assertions）。
- **流程 skill 本質**：「對不對」無法全自動 pass/fail，最終仍有一層人工判讀；comparator 盲判 + grader 降偏誤、非消滅判讀。

---

## 11. Round 2（2026-06-03）：去噪 + 全 scope 再優化

> Round 1（§1-§10，commit `038a835` 止）已砍 ~60%。Round 2 由 user 2026-06-03 指示：對**整個 skill**（SKILL.md + examples 2 檔 + reference 12 檔，共 15 檔）再做一次完整優化，重點加一條**去噪 mandate**。沿用 §2 其餘原則、§5 cluster 分批、§6 靜態檢查、§8 commit 規範、§10 EDD 機器；以下為 round-2 **delta**。

### 11.1 新增：去噪政策（推翻 §2.3 的 `<details>` 折疊法）

**原則**：skill 內只放「與 workflow 直接相關、能指導未來動作」的內容。**歷史 / 日誌 / 演化敘事 / SHA 時間線 / 「我哪天踩了什麼坑」的故事＝噪音，移出 skill**，以降低恆載 attention、提升模型專注力。

處理三分法（取代 round-1 的「折進 `<details>`」）：
1. **蒸餾成關鍵陷阱 → 留 skill**：該歷史若濃縮成「一句可執行規則 / 一個要避開的坑」對未來有指導價值 → 只留那一句規則（去掉 commit SHA、日期、第幾輪、誰派誰）。
2. **已記在別處 → 直接刪**：演化全貌多數已在 `resources/changelog.md`（里程碑日誌）/ git log。skill 內重述＝冗餘 → 刪，不留指標。
3. **沒別處記 + 有未來值 → 外移 resources/**：如通用工具 lore（已辦：`/goal` → `resources/research/claude-code-goal-command-notes.md`）。外移後 skill 內**不留 breadcrumb**（避免把剛清掉的噪音又指回來）。

**判準**：一段內容自問「拿掉它，Claude 規劃/執行 workflow 會出錯嗎？」——不會＝噪音，按上三法處理。**保留的陷阱要少而精**（few key traps），不是把歷史換句話全留。

### 11.2 scope 與 round-1 差異

- **SKILL.md / examples 全文納入**（round-1 §7 對 SKILL.md 只「微調 description」；round 2 連同路由表/兩層觸發/鐵則/維護段一起去噪精煉，但仍**不重構 router 架構、不拆多 skill**）。
- 其餘 12 reference 全部再過一遍（多數 round-1 已精簡，round 2 主要砍殘留歷史敘事 + 再壓冗語）。

### 11.3 EDD baseline 與時序（round 2）

- **baseline = 既有 `resources/evals/iteration-1/` transcript**：那批是針對「當前檔（round-1 結果）」跑的，等同 round-2 的「before」，**免重跑 T0**。round-2 產出存 `resources/evals/iteration-2/`。
- comparator 盲判 **iteration-1（before）vs iteration-2（after）**；同 §10 用不同 fresh-context navigator + 多模型（scenario 1 另跑 sonnet）。
- 5 場景 / assertions **不變**（§10.3）——它們測的是「導航精準度 + 必留細節在不在」，正好驗證「去噪沒誤砍 load-bearing 陷阱」。去噪移除的是非承載敘事，本就不該被任何 assertion 依賴；若某 assertion 因移除而 fail＝該內容其實 load-bearing，補回。
- 每 cluster：改 → 跑該 cluster 場景 navigator → comparator → 退化補回 → commit + sync。cluster 1 做完停給 user 校準去噪力度，再續 2-5 + SKILL.md。

### 11.4 round-2 out of scope（追加）

- 仍不動 myProgram/ code、CLAUDE.md、code_map、hooks、agents（§7 不變）。
- 不新增 reference/examples 檔、不改檔名、不刪整檔（§2.8 不變）；去噪的「外移」目的地一律在 skill 目錄**外**（resources/）。
- 不重跑 round-1 已完成的 baseline（§11.3）。

### 11.5 round-2 完成記錄（2026-06-03，commit `038a835`→`b864797`）

**✅ 完成**。前置 + 6 個 commit：`/goal` 外移（`b3d963f`）+ 5 cluster + SKILL.md（`e17f6a6` / `82e9277` / `f260e49` / `d798eca` / `12b7281` / `b864797`）。

**Benchmark（15 檔字元數）**：108248 → 104839，**−3409（−3.1%）**。最大降幅 conventions（/goal 外移 −1563）/ standard-workflow（−448）/ sales-tts-ux（−427）/ sdd（−396）/ dispatch（−355）；唯一增加 sales-dialog-design（**+410**，L4 v3 準確性重寫）；vendor ±0（已純淨）。round-1 已 −60%，round-2 為殘留行內去噪（邊際遞減符合預期）。

**移除的噪音類型**：commit SHA 戳記、日期戳（2026-05-XX）、版本號（v3）、「借鏡 superpowers X」歸屬語、episode 實測數據、redundant 教訓行、演化敘事（v1/v2/v3）、遷移歷史。全部規則 / 表 / Gotcha 解法 / Iron Law / 行為矩陣 / canonical 範例 / 繁簡表逐字保留。

**準確性修正**：sales-dialog-design 的 L4 段從 stale v2（30s 單 budget）重寫為 v3 準確版（36s 雙計時器 + QR 12s 循環 + 暫停補償 + 客服 yes reset）——此段橫跨 round-1+2 EDD 每次都被 navigator 標 stale，現已消除並重跑驗證。

**EDD（iteration-1 baseline vs iteration-2，transcript 存 `resources/evals/iteration-2/`）**：5 場景重跑 navigator + 盲判 comparator，**零退化**；cluster 1 盲判選 round-2 版、cluster 4 盲判選 round-2 版（更自足）；cluster 2/3/5 內容等價（盲判差異均為 navigator 答題變異或「保有日期 anchor」——後者正是刻意移除的噪音）。description 走選項 B 手動精煉（觸發關鍵字全保留）。

**已知殘留（scope 外，follow-up 候選）**：(1) `tests/sales/test_states.py` 註解仍寫 30s/12s 舊值（test code 非 skill）；(2) 數個 reference 的 pre-existing 內容縫隙（「L3 reject 短詞=結帳意圖」未進 sales-dialog-design / STT 自我回授坑未明列 / L4 budget 整除不變量未標明）——屬「補內容」非去噪，未在本輪動。
