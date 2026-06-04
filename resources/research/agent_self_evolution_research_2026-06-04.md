# Agent 自進化（Self-Evolution）— 官方文檔 + Anthropic blog/engineering/cookbook 完整研究

> **本文件性質**：以 Anthropic 官方來源（platform.claude.com docs / cookbook、anthropic.com/engineering、claude.com/blog、anthropics/skills GitHub）為主的**轉述式結構化筆記**。功能性事實（數字、規則、API 欄位、指令）照實記錄並附出處；散文以繁體中文重組，僅在關鍵術語與標誌性語句處短引用。
> **版權**：原文版權屬 Anthropic；本檔非逐字全文複製。
> **抓取日期**：2026-06-04。
> **主題**：Agent 改進自己的 harness——自寫/自改 skill、eval-driven development、self-correcting feedback loops、從錯誤學習固化進 CLAUDE.md/skill/memory 的閉環。
> **淨增量原則**：與下列既有筆記重疊處標出處、不重述；本檔只寫新發現。
>   - `skills_best_practices_research_2026-06-03.md`（skills 撰寫最佳實踐，含 §1.7 eval-driven、§6 skill-creator）
>   - `CC-skills.md`（Claude Code skills 官方文檔）
>   - `CC_large_codebases_best_practices_2026-06-01.md` §8 ＝該檔模式 2「主動維護 CLAUDE.md / 為舊 model 建的 scaffolding 綁住新 model / 3-6 個月 review」

---

## 目錄

1. [來源清單表](#1-來源清單表)
2. [核心命題：harness 是「對模型能力的假設集合」](#2-核心命題harness-是對模型能力的假設集合)
3. [skill-creator 的 agent 自驅 eval/improve 機制（最完整實作）](#3-skill-creator-的-agent-自驅-evalimprove-機制最完整實作)
4. [官方 eval 體系：demystifying evals for AI agents](#4-官方-eval-體系demystifying-evals-for-ai-agents)
5. [self-correcting loop：generator/grader 分離（GAN 式）](#5-self-correcting-loopgeneratorgrader-分離gan-式)
   - 5.1 harness-design 的 evaluator 分離
   - 5.2 Outcomes：agent 對著 rubric 自我修正（managed agents）
6. [Dreaming：從過往 session 萃取教訓、固化進 memory（不改權重）](#6-dreaming從過往-session-萃取教訓固化進-memory不改權重)
7. [agent 改進自己的 tools：writing-tools-for-agents 的自我改進循環](#7-agent-改進自己的-toolswriting-tools-for-agents-的自我改進循環)
8. [安全演進：prompt/skill 版本化 + rollback + 回歸偵測](#8-安全演進promptskill-版本化--rollback--回歸偵測)
9. [固化到哪一層：CLAUDE.md vs skill vs hook vs memory 的決策](#9-固化到哪一層claudemd-vs-skill-vs-hook-vs-memory-的決策)
10. [真實案例與成效](#10-真實案例與成效)
11. [對 Project_01 的可操作啟示](#11-對-project_01-的可操作啟示)
12. [出處](#12-出處)

---

## 1. 來源清單表

| # | 標題 | 類型 | URL | 與本主題關聯 |
|---|---|---|---|---|
| S1 | skill-creator `SKILL.md`（anthropics/skills） | 官方開源 skill | github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | agent 自驅 eval/improve 的**實作層**（指令、檔結構、train/test split） |
| S2 | Demystifying evals for AI agents | engineering | anthropic.com/engineering/demystifying-evals-for-ai-agents | eval 體系權威：regression vs capability、pass@k/pass^k、LLM-as-judge、Swiss Cheese |
| S3 | Harness design for long-running application development | engineering | anthropic.com/engineering/harness-design-long-running-apps | 「harness＝對模型能力的假設」+ generator/evaluator 分離 + 移除元件 |
| S4 | Writing effective tools for AI agents—using AI agents | engineering | anthropic.com/engineering/writing-tools-for-agents | agent 分析 transcript → 重構自己的 tools 的自我改進循環 |
| S5 | New in Claude Managed Agents: dreaming, outcomes, multiagent | claude.com/blog | claude.com/blog/new-in-claude-managed-agents | dreaming + outcomes 兩大官方自進化機制總覽 + Harvey 6x |
| S6 | Dreams（Managed Agents docs） | platform docs | platform.claude.com/docs/en/managed-agents/dreams | dreaming 的 API 級精確機制、不改權重、可審查 |
| S7 | Outcomes: agents that verify their own work（cookbook） | cookbook | platform.claude.com/cookbook/managed-agents-cma-verify-with-outcome-grader | self-correct loop 的**逐 pass 實例** + rubric 設計 |
| S8 | Managed Agents tutorial: prompt versioning and rollback（cookbook） | cookbook | platform.claude.com/cookbook/managed-agents-cma-prompt-versioning-and-rollback | 安全演進：版本化 + 回歸偵測 + 即時 rollback |
| S9 | How Warp builds self-improving agents on Claude | webinar 頁 | anthropic.com/webinars/how-warp-builds-self-improving-agents-on-claude | 真實案例：agent「研究團隊如何糾正它 → 改寫自己的 skill」 |
| S10 | Improving skill-creator: test, measure, refine | claude.com/blog | claude.com/blog/improving-skill-creator-... | **已在既有筆記 §6**，本檔只補實作細節（見 §3） |

> **補充輔證（非官方，僅交叉印證數字，不作為主張依據）**：VentureBeat / SD Times / 9to5Mac 對 dreaming/outcomes 的報導；Harvey customer story（claude.com/customers/harvey）。所有官方數字皆以 S5–S8 為準。

---

## 2. 核心命題：harness 是「對模型能力的假設集合」

> 來源 S3（harness-design-long-running-apps）。**這是整個「自進化」主題的理論支點**，比既有 `CC_large_codebases §8`「為舊 model 建的 scaffolding 綁住新 model」更進一步、更可操作。

**標誌性論點（短引用）**：
> 「**every component in a harness encodes an assumption about what the model can't do on its own, and those assumptions are worth stress testing**」
>（harness 的每個元件都編碼了一個「模型自己做不到什麼」的假設，這些假設值得拿來壓力測試。）

**可操作的推論**：
- CLAUDE.md 的每條規則、每個 hook、每個 skill = 一條對模型弱點的賭注。模型變強 → 賭注可能過時甚至反效果（與既有筆記 §8 一致，標為重疊）。
- **淨增量做法**：S3 給了「移除元件」的具體實踐——他們**為 Opus 4.6 移除了 sprint decomposition（衝刺拆解）元件**，但保留 planner 與 evaluator，示範「harness 複雜度應隨模型能力調整，而非固定不變」。
- 對「自我評估」的關鍵限制（S3 短引用）：
  > 「agents tend to respond by confidently praising the work—even when, to a human observer, the quality is obviously mediocre」
  >（agent 傾向自信地稱讚自己的產出——即使在人看來品質明顯平庸。）
  - 對主觀任務（設計品質）尤其嚴重，因為缺乏客觀正確性指標。
  - **解法**：把「做事的 agent」與「評判的 agent」**分離**（"Separating the agent doing the work from the agent judging it proves to be a strong lever"）。調校一個外部 evaluator 去「skeptical（多疑）」，比讓 generator 自我批判更可行。→ 這直接導出 §5 的 generator/grader 分離模式。

---

## 3. skill-creator 的 agent 自驅 eval/improve 機制（最完整實作）

> 來源 S1（skill-creator SKILL.md）。**既有筆記 §6 已涵蓋「概念層」（capability uplift vs encoded preference、benchmark mode、A/B comparator、description 優化）。本節只補既有筆記沒有的「實作層」**：精確的檔結構、指令、train/test split、grading schema、停止條件。

### 3.1 EDD 主循環（agent 自己跑的步驟）

skill-creator 把 §1.7「evaluation-driven development」變成一條 agent 可自動執行的流水線，主循環短引用：「**Repeat until you're satisfied**」。步驟：
1. 草擬/編輯 skill；
2. **同一 turn 內**同時 spawn「with-skill」與「baseline」兩組 subagent run（關鍵：不可先跑 with-skill 再回來補 baseline）；
3. 使用者對輸出做質性評估（feedback）；
4. 跑量化 benchmark；
5. 依 feedback 改 skill；
6. 把所有 test case 重跑進新的 iteration 目錄；
7. 重複。

### 3.2 檔結構（agent 寫出的工作區）

```
<skill-name>-workspace/
├── iteration-1/
│   ├── eval-0/
│   │   ├── with_skill/outputs/
│   │   ├── without_skill/outputs/   # 新 skill 用「無 skill」當 baseline
│   │   │  (改進既有 skill 時改為 old_skill/outputs/  # 舊版快照當 baseline)
│   │   ├── eval_metadata.json
│   │   ├── timing.json
│   │   └── grading.json
│   ├── benchmark.json / benchmark.md
│   └── feedback.json
├── iteration-2/ ...
└── skill-snapshot/
```

### 3.3 eval / grading schema（精確欄位，viewer 依賴）

- `evals/evals.json`：`skill_name` + `evals[]{id, prompt, expected_output, files}`。
- **初期只寫 prompt、不寫 assertion**（"Don't write assertions yet"）——assertion 在 run 進行中才補。
- `timing.json`：`total_tokens` / `duration_ms` / `total_duration_seconds`。**關鍵警告**：這是「唯一一次」能抓 timing 的機會，資料只在 task notification 出現、不持久化，必須逐筆即時處理。
- `grading.json`：`expectations[]` **必須**用欄位 `text` / `passed` / `evidence`（**不可**用 `name`/`met`/`details` 等變體——viewer 硬依賴這三個欄位名）。
- assertion 原則：「objectively verifiable and have descriptive names」；主觀面向（寫作風格、設計品質）改走質性評估，**別硬塞 assertion**。

### 3.4 benchmark 聚合與 description 優化（精確指令）

```bash
# 聚合 benchmark（pass_rate / time mean±stddev / tokens mean±stddev / 與 baseline 的 delta）
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>

# description 觸發優化迴圈
python -m scripts.run_loop \
  --eval-set <trigger-eval.json> --skill-path <skill> \
  --model <model-id> --max-iterations 5 --verbose
```

- **run_loop 的回歸防護機制（淨增量重點）**：
  - **把 eval set 切 60% train / 40% held-out test**；
  - 每個 description 在 train+test 都重評，**每個 query 跑 3 次取可靠的觸發率**；
  - 迭代至多 5 次，最終回傳的 `best_description` **以 test 分數選取（非 train），以避免 overfitting**。
  - 這是官方對「skill 改動沒退化」的標準答案之一：**train/held-out 切分 + 以 held-out 選優**。

### 3.5 改 skill 的「為什麼」原則（agent 自我修正的指導語）

S1 對 improve 階段的指導語，正是「從錯誤學習固化」的精華：
- **泛化而非過擬**：「we're trying to create skills that can be used a million times...Rather than put in fiddly overfitty changes」——卡關時換隱喻、換工作 pattern，而非塞特例補丁。
- **讀 transcript 而非只看終輸出**：若 skill 害模型浪費時間做無生產力的事，就砍掉那段。
- **解釋 why、警惕 ALL-CAPS**：「If you find yourself writing ALWAYS or NEVER in all caps, or using super rigid structures, that's a yellow flag.」（與本專案 memory「lean doc authoring」相容，標重疊。）
- **偵測重複勞動 → 固化成 bundled script**：若 3 個 test case 的 subagent 都各自寫了類似的 `create_docx.py`，就是「該把該 script bundle 進 skill」的強訊號。
- 停止條件：使用者滿意 / feedback 全空 / 不再有實質進展。

---

## 4. 官方 eval 體系：demystifying evals for AI agents

> 來源 S2。**全新內容，既有筆記未涵蓋**。這是 Anthropic 對「如何建 agent 行為回歸測試」最系統的官方論述，正面回答調研問題 3。

### 4.1 術語（官方定義）

| 術語 | 定義 |
|---|---|
| **Task** | 一個帶明確輸入與成功標準的測試 |
| **Trial** | 對某 task 的單次嘗試（因模型有變異，需多次 trial） |
| **Grader** | 對 agent 表現某面向打分的邏輯 |
| **Transcript/Trace** | 一次 trial 的完整紀錄（輸出、tool call、推理、中間結果） |
| **Outcome** | trial 結束時環境的最終狀態 |
| **Evaluation harness** | 跑 task、記錄步驟、彙總結果的基礎設施 |

### 4.2 兩類 eval（自進化的核心對立）

- **Regression evals**：「Does the agent still handle all the tasks it used to?」**應接近 100% pass rate**；分數下滑＝有東西壞了（防退化）。
- **Capability evals**：「What can this agent do well?」**刻意從低 pass rate 起步**，瞄準 agent 不擅長的任務。
- **graduation 機制**：capability eval 一旦 pass rate 高了，可「畢業」轉成 regression suite。→ 這就是「能力固化」的量化儀式。

### 4.3 變異數分析（驗證固化是否穩定）

- **pass@k**：k 次嘗試至少一次成功的機率。
- **pass^k**：k 次**全部**成功的機率。例：每次 75%、3 次 → (0.75)³ ≈ 42%。「對使用者每次都期待可靠的面向客戶 agent，這個指標才重要。」
- 含意：固化一個行為若只看 pass@1 會高估穩定度；面向終端使用者要看 pass^k。

### 4.4 LLM-as-judge（model-based grader）正確用法

- 適合開放式任務；用 rubric 計分、自然語言 assertion、pairwise 比較、multi-judge 共識。
- **必須與人類 grader 校準**（非確定性）；給模型「逃生口」（可回 "Unknown"）以防幻覺。
- rubric 要「clear, structured」；**每個維度用獨立的 LLM-as-judge 分開評，不要一個 judge 評所有維度**。

### 4.5 驗證「行為改動沒退化」的官方手法

1. **Isolation**：每個 trial 從乾淨環境起；共享狀態會造成「相關性失敗（correlated failures）」與虛假灌水（如 agent 偷看上一 trial 的 git 歷史）。
2. **讀 transcript**：「你不讀許多 trial 的 transcript 與 grade，就不會知道 grader 好不好用」；分數停滯時「讀 transcript 是驗證 eval 是否量到真正重要東西的方法」。
3. **多種 grader 並用**：code-based（快、客觀）＋ model-based（彈性）＋ human（黃金標準）。
4. **雙向問題集**：同時測「該發生時有發生」與「不該發生時沒發生」，否則造成「one-sided optimization」。

### 4.6 八步建置路線 + 反模式

- 起步：「**20-50 個源自真實失敗的簡單 task 就是很好的開始**」；把開發時的手動檢查、使用者回報的失敗轉成 test case。
- task 要「兩位領域專家會獨立得到相同 pass/fail 判定」且「照指示做就能過」。
- grader「grade what the agent produced, not the path it took」（評產出，別評路徑）；多元件任務給 partial credit。
- 監控 **capability eval 飽和**：100% 的 eval 只追回歸、對改進無訊號。
- **反模式**：過嚴路徑式 grading（罰掉設計者沒預期的有效解法）、模糊規格、grading bug（例：期待 96.124991… 卻罰 96.12）、共享狀態。
- **Swiss Cheese Model**：「no single evaluation layer catches every issue」——自動 eval + 生產監控 + A/B + transcript review + 人類研究多層疊加，一層漏的另一層接。

---

## 5. self-correcting loop：generator/grader 分離（GAN 式）

### 5.1 harness-design 的 evaluator 分離（S3）

- 架構是 **GAN 啟發**的回饋：evaluator 給出具體可行動的批評並把失敗 route 回 generator。
- 前端設計案例：evaluator 用 **Playwright** 操作實際頁面、截圖、研究後再對四項標準（design quality / originality / craft / functionality）打分。
- 全端 coding 案例：evaluator 抓到具體 bug（如「Tool only places tiles at drag start/end points instead of filling the region」）並 route 回 generator。
- 核心：把 evaluator 調成「多疑」比讓 generator 自評更可行（見 §2）。

### 5.2 Outcomes：agent 對著 rubric 自我修正（S5, S7）

> Managed Agents 的 production 級 self-correct loop，是 §5.1 概念的產品化。**全新內容**。

**機制**：你寫一份 **rubric**，session 多一個「**唯一工作就是檢查**」的 grader agent，在**獨立 context window** 評產出（看不到 writer 的推理鏈），不滿意就 pinpoint 該改什麼、writer 再來一 pass，直到 satisfied 或撞 `max_iterations`。

**為何分離（短引用）**：
> 「A writer that knows the criteria is still grading its own work. It will say it passed whenever it believes it did... The grader has no choice but to do those checks.」

**結果狀態**：`satisfied` / `needs_revision` / `max_iterations_reached` / `failed` / `interrupted`。

**rubric 設計原則（可直接借用）**：每條標準可勾選、要 grader「掙得 satisfied」（須附具體證據）、描述目標而非步驟、預判抄捷徑（如「不可用 mirror/repost/搜尋摘要佐證，須 fetch 引用 URL 本身」）、規定回饋格式（記分板＋bullet）、明說該忽略什麼以免在風格細節上空轉。

**逐 pass 實例（citation 驗證任務）**：
- Pass 0：5/7 覆蓋，grader 指出「demand charges 只定性描述、沒給 $/kW 數字」「引用第三方新聞而非 SEC filing」。
- Pass 1：6/7，grader 進一步分辨「引用的是 8-K EX-99.1（earnings press release exhibit），rubric 明確排除新聞稿，不是 10-K/10-Q」——**「這是任務本身會錯過的區分」**。
- Pass 2：writer 找到真正的 10-K → `satisfied`（7/7、6/6 citation 全 LIVE 且引文逐字相符）。
- 該例：3 passes、12m 56s、31 次 tool call。

**production 治理建議**：rubric 用 Files API 上傳一次、以 `rubric:{type:file,file_id:...}` 跨 session 重用，「像 code 一樣可版本化、可審查」。

**官方成效**：內部測試 task success **全面 +10 個百分點**（Word 文件 +8.4%、PowerPoint +10.1%），**且未改模型**（S5）。

---

## 6. Dreaming：從過往 session 萃取教訓、固化進 memory（不改權重）

> 來源 S5（blog）+ S6（docs，API 級）。**全新內容、且是本主題最重要的官方機制**——直接回答調研問題 2「錯誤 → 歸因 → 固化進哪一層 → 怎麼驗證」中「固化進 memory 層」的官方產品答案。

### 6.1 是什麼

- **dreaming = 一個「排程的反思過程」**：回顧 agent 的過往 session 與 memory store、跨它們萃取 pattern、整理（curate）memory，使 agent 隨時間自我改進。Research Preview（2026 年 5 月 Code with Claude 發表）。
- 兩階段記憶觀（S5 短引用）：「**Memory lets each agent capture what it learns _as it works_. Dreaming refines that memory _between sessions_**」——memory 是工作中即時捕捉、dreaming 是 session 之間精煉並跨 agent 拉出共享學習。
- **surface 三類 pattern**（單一 session 看不到的）：
  1. recurring mistakes（反覆犯的錯）；
  2. workflows that agents converge on（多個 agent 各自獨立收斂到的工作流）；
  3. preferences shared across a team（跨團隊共享偏好）。

### 6.2 API 級機制（S6，精確）

- 一個 **dream** 是非同步 job，輸入＝1 個既有 **memory store** ＋ **1 到 100 個 session транscript**，輸出＝**另一個新的 memory store**（與輸入分離）。
- **輸入 store 永不被修改**（"The input store is never modified"）→ 可審查輸出、不滿意就丟（delete/archive）。**這是「可觀察、可審計」的關鍵設計**。
- 可在 create 時給 `instructions`（≤4096 字元）導引，例：「Focus on coding-style preferences; ignore one-off debugging notes.」
- dream 做的事：去重合併、用最新值取代過時/被推翻的條目、surface 新洞見。
- 生命週期：`pending`→`running`→`completed`/`failed`/`canceled`；running 時 `session_id` 指向執行 pipeline 的 session，**可串流其 events 即時觀察它在讀什麼、寫什麼**（archived 不刪，transcript 留存）。
- 限制：每 dream ≤100 session、支援 `claude-opus-4-8 / 4-7 / sonnet-4-6`、按標準 token 計費（成本約隨 session 數與長度線性）。
- **不改模型權重**：dreaming 寫的是 plain-text note 與結構化 playbook，未來 session 引用——整個過程人類可觀察、可審計（S5 報導與 S6 機制一致）。

### 6.3 與本專案 memory 機制的對照

- 本專案的 `MEMORY.md` + auto-memory 是「人工/規則維護的持久 context」；dreaming 是「**讓 Claude 自己跨 session 精煉 memory**」的自動化版本。**概念可借鏡，但 dreaming 是 Managed Agents API 功能，非 Claude Code 本機功能**——本專案目前無法直接用，但其「輸入不可變、輸出可丟棄、可審計」的設計哲學可手動模仿（見 §11）。

---

## 7. agent 改進自己的 tools：writing-tools-for-agents 的自我改進循環

> 來源 S4。**全新內容**。標題副題即「**using AI agents**」——讓 agent 改進它自己依賴的 tool。

**自我改進循環（短引用）**：「**You can even let agents analyze your results and improve your tools for you.**」

**循環步驟**：
1. 建 prototype（本地 MCP server 測）；
2. 用簡單 agentic loop（LLM call 與 tool call 交替）跑 eval，eval task 要「grounded in real world uses」、可能需數十次 tool call（例：客服情境「Customer Sarah Chen 剛送出取消請求，準備留客方案…」）；
3. 收集 metric：accuracy、runtime、token 消耗、tool error；
4. **「Simply concatenate the transcripts from your evaluation agents and paste them into Claude Code」** → Claude 同時分析數十個 tool 的失敗 pattern，找出「contradictory tool descriptions」到「inefficient tool implementations」並重構，同時確保 self-consistency；
5. 迭代。
- verifier 從「exact string comparison」到「enlist Claude to judge」皆可，但**避免過嚴 verifier 誤殺正確回應**。
- 成效：用 held-out test set 量到「even beyond what we achieved with 'expert' tool implementations」（連專家手寫的 tool 之上還能再榨出改進）。

---

## 8. 安全演進：prompt/skill 版本化 + rollback + 回歸偵測

> 來源 S8（cookbook）。**全新內容**。正面回答調研問題 2 最後一段「怎麼驗證固化有效」與問題 4「review 節奏」的工程化機制。

**機制**：Managed Agents 的 prompt 以**伺服器端不可變版本**保存；每次 `agents.update` 產生新 version（同一 agent ID），session 用版本 ID 選版。

**Create → Evaluate → Ship → Detect → Rollback 工作流**：
1. create v1（自動 `version:1`）；
2. score v1（把全部 test ticket 跑過 pin 到 v1 的 session）；
3. ship v2（`agents.update` → 版本自動遞增）；
4. score v2（對**同一 test set** 評 v2 以偵測回歸）；
5. 若偵測到回歸 → caller 直接 revert 回 `version:1`（**即時、免部署**）。

**治理要點**：
- production caller **永遠 pin 明確版本號**（不要裸 agent ID）；新版在「promote」前對 production 不可見。
- 「你仍 review/approve prompt 改動，但你 approve 的是 config 裡的版本號，而非 code diff」——把 pinned 版本號當變更管制閘門，走正常 code review。
- 支援 canary（一小部分流量導到新版邊監控邊全推）。

**對自進化的意義**：這是「**讓 agent 改自己的 prompt/skill，但人保留變更管制 + 一鍵回退**」的官方安全範式，直接對應 §2「移除/修改 harness 元件」的風險控管。

---

## 9. 固化到哪一層：CLAUDE.md vs skill vs hook vs memory 的決策

> 綜合 S2/S3/S5/S6 + 既有筆記。回答調研問題 2 的「固化進哪一層」。下表為**本研究綜合整理**（標明非單一原文逐字）。

| 學到的東西 | 固化到哪層 | 官方依據 | 怎麼驗證固化有效 |
|---|---|---|---|
| 一條反覆需要的硬規則、必須**確定性**強制（lint/format/禁某操作） | **hook** | 既有 large-codebases §3.2「hooks 確定性強制」 | 該操作再也不發生（hook block 計數） |
| 跨 session/跨 agent 可重用的**程序專長**（workflow、領域 schema） | **skill**（+ bundle script） | S1「重複勞動→bundle script」；Skills explained「多 agent 需同一專長→建 skill」 | skill-creator EDD：train/held-out + pass_rate delta（§3.4） |
| **專案特定**慣例、critical gotchas、導航指標 | **CLAUDE.md**（root 放紅線、子層放局部） | large-codebases §4 模式1 | regression eval 接近 100%（§4.2） |
| 跨 session 累積的**偏好/經驗/反覆犯錯** | **memory**（人工或 dreaming 精煉） | S5/S6 dreaming | 比較精煉前後 memory；輸出可丟棄、可審計（§6.2） |
| 一個任務當下「夠不夠好」的**品質閘** | **rubric/outcome grader**（runtime self-correct） | S7 Outcomes | grader 在獨立 context 對 rubric 判 satisfied（§5.2） |

**錯誤 → 歸因 → 固化的官方閉環順序**（綜合）：
1. 把失敗轉成 eval task（S2「20-50 個源自真實失敗的 task」）；
2. 讀 transcript 歸因（S1/S2「讀 transcript 而非只看終輸出」）；
3. 選層固化（上表）；
4. 用 held-out eval / regression suite 驗證沒退化（S2 §4.2、S1 §3.4）；
5. 能力穩定後 capability eval「畢業」成 regression suite（S2 §4.2）；
6. 隨模型升級重訪、必要時移除過時 scaffolding（S3 §2、既有 §8）。

---

## 10. 真實案例與成效

| 案例 | 機制 | 官方成效（精確） | 出處 |
|---|---|---|---|
| **Harvey**（法律 AI） | Managed Agents + dreaming（session 間記住 filetype workaround、tool-specific pattern） | 「**Completion rates went up ~6x in their tests**」 | S5 |
| **Anthropic 內部**（文件生成） | Outcomes（grader 對 rubric self-correct，未改模型） | task success 全面 **+10pp**；Word **+8.4%**、PowerPoint **+10.1%** | S5 |
| **Anthropic 內部**（tool 開發） | agent 分析 eval transcript 重構自己的 tools | held-out test set 上「**even beyond...'expert' tool implementations**」（未給絕對數字） | S4 |
| **Warp**（終端 agent） | agent「研究團隊如何糾正它 → 改寫自己的 skill」；「skills as the substrate」；PR review agent 隨時間精煉自己的審查標準 | webinar 頁**未列具體 metric**（錄影當時未上線） | S9 |

> **誠實標註**：Warp 案例僅有定性描述，無官方數字，故不寫成效數字。Harvey 6x 與 Outcomes +10pp 為官方 blog（S5）明列。

---

## 11. 對 Project_01 的可操作啟示

> 本專案＝Raspberry Pi 規則匹配點餐/收款模擬，單人期末專題、Claude Code 本機開發。下列為**可立即手動模仿的低成本版本**（dreaming/Outcomes/Managed Agents 是 API 功能，本機 Claude Code 無法直接用，但模式可借）。

1. **harness 假設清單化（S3）**：把現有 hooks / skill reference / CLAUDE.md 紅線各自視為「對模型弱點的一條賭注」，每 3-6 個月（或換 model 後）逐條問「移掉會不會出錯」（與既有 §8、CLAUDE.md 維護原則一致），並**敢於移除**過時 scaffolding。
2. **skill 改動走 EDD 回歸（S1 §3.4）**：改 `project-01-workflow` skill 前，用 fresh subagent（Claude B）跑 3+ 代表性任務當 baseline，改後重跑比 pass/觸發/找對檔；大改時用 60/40 train/held-out 心智模型、以 held-out 結果定案，避免過擬到單一案例。
3. **錯誤→eval task（S2）**：把 debug 多線程收斂、Pi sync 失敗等真實踩雷各寫成 1 條 eval task（描述 + 期望行為），累積成 regression 清單；修好後該 task 進「regression suite」防退化。
4. **generator/grader 分離（S3/S5.2）**：對「skill 精簡有沒有砍掉重點」「commit message 合不合繁中規範」這類判斷，派**獨立 subagent 當 grader**（看輸出、不看撰寫推理）對著一份簡短 rubric 判，而非讓同一 agent 自評。
5. **memory 精煉模仿 dreaming（S6）**：定期請 Claude 讀近期 session 摘要 → 產出「新版 memory 草稿」放到**獨立檔**供人審後再合併（模仿 dreaming「輸入不可變、輸出可丟棄、可審計」），不要讓它就地覆寫 `MEMORY.md`。
6. **改動可回退（S8）**：skill/CLAUDE.md 大改前先 commit 快照（本專案已用 git），等同 prompt versioning 的窮人版 rollback。

---

## 12. 出處

| # | URL | 抓取日期 |
|---|---|---|
| S1 | https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md | 2026-06-04 |
| S2 | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | 2026-06-04 |
| S3 | https://www.anthropic.com/engineering/harness-design-long-running-apps | 2026-06-04 |
| S4 | https://www.anthropic.com/engineering/writing-tools-for-agents | 2026-06-04 |
| S5 | https://claude.com/blog/new-in-claude-managed-agents | 2026-06-04 |
| S6 | https://platform.claude.com/docs/en/managed-agents/dreams | 2026-06-04 |
| S7 | https://platform.claude.com/cookbook/managed-agents-cma-verify-with-outcome-grader | 2026-06-04 |
| S8 | https://platform.claude.com/cookbook/managed-agents-cma-prompt-versioning-and-rollback | 2026-06-04 |
| S9 | https://www.anthropic.com/webinars/how-warp-builds-self-improving-agents-on-claude | 2026-06-04 |
| S10 | https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills | 既有筆記 §6（本檔僅補實作細節） |

> **版權**：以上皆 Anthropic 官方內容之轉述式摘要筆記，非逐字全文複製；功能性事實（數字/規則/API 欄位/指令）照實記錄，散文以繁中重組。輔證性第三方報導僅用於交叉印證官方數字，未作為獨立主張依據。抓取日期 2026-06-04。
</content>
</invoke>
