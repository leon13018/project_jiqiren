# Harness Engineering 總綱<br>（Context Engineering · Building Effective Agents · Tool Design · Feedback Loop · 各層職責）

> **本檔性質**：Anthropic / Claude 官方工程部落格四篇基石長文 + Agent Skills 工程文的**轉述式結構化筆記**。
> 以繁中重組轉述，僅在 load-bearing 處做短引用（"…"）；無逐字全文複製。版權屬 Anthropic。
> **與既有筆記的關係**：本檔只寫**淨增量**——「harness 建構順序（CLAUDE.md→hooks→skills→plugins→LSP→MCP）」「元件總覽表」「monorepo 分層 / worktree / settings 機制」已分別由
> `CC_large_codebases_best_practices_2026-06-01.md` 與 `large_codebases_official_guide_2026-06-02.md` 涵蓋；重疊處只標出處、不重述。
> 本檔補的是那兩篇**沒講的底層工程原理**：context engineering 的「為什麼」、agent 架構模式、tool 設計準則、feedback loop 設計、以及各層職責分配的官方論述。

---

## 目錄

1. [來源清單](#1-來源清單)
2. [Context Engineering（情境工程）](#2-context-engineering情境工程)
   - 2.1 [從 prompt engineering 到 context engineering](#21-從-prompt-engineering-到-context-engineering)
   - 2.2 [Attention budget 與 context rot](#22-attention-budget-與-context-rot)
   - 2.3 [System prompt 的「高度（altitude）」](#23-system-prompt-的高度altitude)
   - 2.4 [工具與範例（few-shot）的精簡原則](#24-工具與範例few-shot的精簡原則)
   - 2.5 [Just-in-time retrieval 與 hybrid 策略](#25-just-in-time-retrieval-與-hybrid-策略)
   - 2.6 [長任務三策略：compaction / note-taking / sub-agents](#26-長任務三策略compaction--note-taking--sub-agents)
3. [Building Effective Agents（建構有效的 agent）](#3-building-effective-agents建構有效的-agent)
   - 3.1 [workflow vs agent 的定義界線](#31-workflow-vs-agent-的定義界線)
   - 3.2 [最簡原則：何時該用 agent](#32-最簡原則何時該用-agent)
   - 3.3 [building block：augmented LLM](#33-building-blockaugmented-llm)
   - 3.4 [五個 composable workflow 模式](#34-五個-composable-workflow-模式)
   - 3.5 [autonomous agent](#35-autonomous-agent)
   - 3.6 [三個實作原則 + ACI](#36-三個實作原則--aci)
4. [Writing Tools for Agents（給 agent 用的工具設計）](#4-writing-tools-for-agents給-agent-用的工具設計)
5. [Feedback Loop（回饋迴路）設計](#5-feedback-loop回饋迴路設計)
6. [各層職責分配（system prompt / CLAUDE.md / hooks / skills / tools / memory）](#6-各層職責分配)
7. [最重要的發現](#7-最重要的發現)

---

## 1. 來源清單

| # | 原文標題 | 來源 | URL | 抓取日 |
|---|---|---|---|---|
| A | Effective context engineering for AI agents | Anthropic Engineering | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2026-06-04 |
| B | Building Effective AI Agents | Anthropic Research | https://www.anthropic.com/research/building-effective-agents | 2026-06-04 |
| C | Writing effective tools for AI agents—using AI agents | Anthropic Engineering | https://www.anthropic.com/engineering/writing-tools-for-agents | 2026-06-04 |
| D | Building agents with the Claude Agent SDK | Anthropic（已 308 轉址至 claude.com/blog） | https://claude.com/blog/building-agents-with-the-claude-agent-sdk | 2026-06-04 |
| E | Equipping agents for the real world with Agent Skills | Anthropic Engineering | https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | 2026-06-04 |

> 抓取方式：WebSearch 定位 + WebFetch 全文轉述。D 篇原 `anthropic.com/engineering` 路徑 308 永久轉址至 `claude.com/blog`。
> E 篇本檔僅取 WebSearch 摘要（progressive disclosure 三層）交叉佐證 §6，未做全文 fetch。

---

## 2. Context Engineering（情境工程）

> 出處：A 篇。**這是兩份既有筆記完全沒展開的底層論述。**

### 2.1 從 prompt engineering 到 context engineering

- **Prompt engineering**：聚焦「為離散任務寫好、組織好 LLM 指令」——怎麼寫一個好的 system prompt。
- **Context engineering**：是它的演進，指「在 LLM 推論期間，策展並維護那組最佳 token（資訊）的策略，包含所有可能落進 context 的、prompt 以外的資訊」。
- 關鍵差別：prompt 是**寫一次**的靜態工藝；context engineering 是 agent **跨多輪運作時**的迭代工藝——short quote：「在那個不斷演化的可能資訊宇宙中，策展什麼該進入有限 context window 的藝術與科學」。
- 一句話：模型越強，挑戰就不再是「寫出完美 prompt」，而是「每一步都謹慎策展什麼資訊進入模型有限的 attention budget」。

### 2.2 Attention budget 與 context rot

- LLM 有有限的 **"attention budget"**，類比人類的工作記憶。
- **Context rot（情境腐化）**：研究指出，隨 token 數增加，模型準確回想資訊的能力**下降**。
- 機制根因：transformer 架構對 n 個 token 需要 **"n² pairwise relationships"**；context 越長，模型捕捉這些關係的能力「被拉得越薄（stretched thin）」。
- 表現形式：是 **"a performance gradient rather than a hard cliff"**（漸進衰退而非斷崖）——長 context 下模型仍能用，但「資訊檢索與長程推理的精度下降」。
- 核心心法：context 必須當成 **"a finite resource with diminishing marginal returns"**（有邊際遞減的有限資源）。
- 由此推出 context engineering 的目標：**找出最小的高訊號 token 集合，最大化期望結果的機率**。每個多餘的字、每個冗餘的工具描述、每筆過時資料都在主動劣化 agent 表現。

> 與既有筆記呼應：`large_codebases_official_guide` §1 講的「預設值塞滿 context 浪費 token 拖垮表現」是此原理的工程後果；本節是它的**理論根據**。

### 2.3 System prompt 的「高度（altitude）」

- System prompt 要落在兩種失敗模式之間的 **"Goldilocks zone"**：
  - **過低（太硬）**：「hardcoding complex, brittle logic」——脆弱、維護成本高、稍變環境就壞。
  - **過高（太空泛）**：「vague, high-level guidance that fails to give the LLM concrete signals」——給不出具體訊號。
- 最佳「高度」：**"specific enough to guide behavior effectively, yet flexible enough to provide the model with strong heuristics"**（夠具體能有效引導行為，又夠彈性給模型強啟發式）。
- 結構建議：用 **XML tagging 或 Markdown headers** 切分區塊；目標是「完整勾勒期望行為的最小資訊集」。

> **直接對應 Project_01**：本專案 CLAUDE.md 維護原則「每行自問移掉會不會讓 Claude 出錯」「root ≤~100 行」正是這條「最小資訊集 + 對的高度」的落地。

### 2.4 工具與範例（few-shot）的精簡原則

- **工具**要「self-contained、robust to error、對用途極度清楚」。常見壞味道：**"bloated tool sets"**——功能太雜、或讓 agent 在「該用哪個工具」上模糊。
- 黃金判準（極重要）：**"If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better."**（人類工程師都說不清該用哪個工具，就別指望 AI 做得更好。）→ 策展「minimal viable set of tools」。
- **Few-shot 範例**：仍是 best practice，但別「把一長串 edge case 硬塞進 prompt 想窮舉每條規則」。應策展「一組多樣、典範性的範例，有效刻畫期望行為」。short quote：對 LLM 而言「examples are the 'pictures' worth a thousand words」。

### 2.5 Just-in-time retrieval 與 hybrid 策略

- **Pre-retrieval（前置全載）**：先把所有相關資料處理好塞進 prompt。
- **Just-in-time（即時載入）**：只維護 **"lightweight identifiers (file paths, stored queries, web links, etc.)"**，runtime 時用工具動態載入。
- 類比人類認知：我們不背整個語料庫，而是用「檔案系統、收件匣、書籤等外部組織與索引系統」按需取回。**Metadata 本身就是訊號**——「檔案大小暗示複雜度；命名慣例暗示用途；時間戳可當相關性的代理」。
- 取捨：runtime 探索「比取回預算好的資料慢」，且需要「opinionated and thoughtful engineering」。
- **Hybrid 策略（推薦）**：先前載一部分資料求速度，再讓 agent「自行斟酌進一步自主探索」。
- **Claude Code 即範例**：開場把 CLAUDE.md 丟進 context（前載），再用 **glob / grep** 做 just-in-time 取回——「有效繞過陳舊索引的問題」。

> 與既有筆記呼應：`CC_large_codebases` §2「agentic search 非 RAG、no lag」是此原理對「導航」面向的應用；本節給的是**更上位的 retrieval 設計哲學**（前載 vs 即時 vs 混合），不限於程式碼搜尋。

### 2.6 長任務三策略：compaction / note-taking / sub-agents

長程任務（long-horizon）會撞 context 上限，A 篇給三個並存策略：

1. **Compaction（壓縮）**：context 接近上限時，把對話摘要後以壓縮版重啟。「以高保真方式蒸餾 context window 內容，讓 agent 以最小效能損失繼續」。關鍵難點＝「選什麼留、什麼丟」——壓縮太狠會丟掉「微妙但關鍵的 context」。
2. **Structured note-taking / Memory（結構化筆記 / 記憶）**：agent 定期把筆記寫到 context window **外部**、之後再取回。「讓 agent 跨複雜任務追蹤進度，維持否則會遺失的關鍵 context 與依賴」。Pokémon 範例：agent 自建地圖、追蹤目標、維持策略筆記——「達成把全部資訊只放在 context 裡所不可能的長程策略」。
3. **Sub-agent architectures（子代理架構）**：專責 sub-agent 用乾淨 context 處理聚焦任務，主 agent 協調。每個 subagent「可能探索得很廣、用掉數萬 token，但只回傳一份濃縮蒸餾的摘要（常 1,000–2,000 token）」，達成「clear separation of concerns」。

> 與既有筆記呼應：`CC_large_codebases` §3.3「subagent 分離探索與編輯」是策略 3 的具體形態。本節補上 compaction 與 note-taking 兩個既有筆記**未涵蓋**的策略，並點明三者是**互補並存**而非擇一。

---

## 3. Building Effective Agents（建構有效的 agent）

> 出處：B 篇。既有兩份筆記完全沒涵蓋此篇。

### 3.1 workflow vs agent 的定義界線

- **Agentic system** 是上位詞，涵蓋兩類：
  - **Workflows**：「LLM 與工具透過**預定義的程式碼路徑**被編排」的系統（決定性、固定邏輯）。
  - **Agents**：「LLM **動態自我導引**其流程與工具使用、保有控制權」的系統（自主、自己決定下一步）。
- 核心差別 = **決定性 vs 自主性**。

### 3.2 最簡原則：何時該用 agent

- 奠基指導：**"find the simplest solution possible, and only increase complexity when needed."**
- 很多應用**根本不需要 agentic 系統**。「用 retrieval 與 in-context 範例優化單一 LLM 呼叫，通常就夠了」。
- 取捨：「Agentic 系統常以延遲與成本換取更好的任務表現」——要審慎權衡。
- 選擇：workflow 適合「well-defined tasks」；agent 適合「需要規模化的彈性與模型驅動決策」時。

### 3.3 building block：augmented LLM

- 基礎元件 = LLM 增強三能力：**retrieval、tools、memory**。
- 兩個實作優先項：「為你的具體用例量身打造這些能力」+「確保它們提供**易用、文檔完備的介面**給 LLM」。
- MCP（Model Context Protocol）是整合外部工具的一種標準介面實作。

### 3.4 五個 composable workflow 模式

| 模式 | 定義 | 何時用 | 範例 |
|---|---|---|---|
| **Prompt chaining（提示鏈）** | 把任務拆成**循序**步驟，每個 LLM 呼叫處理前一個的輸出；可在中間步加「gate」程式檢查 | 任務能「乾淨地拆成固定子任務」；以延遲換準確度 | 先寫行銷文案再翻譯；先擬大綱再寫文件 |
| **Routing（路由）** | 把輸入**分類**後導向專門的下游任務 | 有「明顯該分開處理的類別」且「分類能做得準」時 | 客服分流；簡單問題給便宜快模型、難題給強模型 |
| **Parallelization（平行化）** | 多個 LLM 同時跑、輸出以程式聚合。兩變體：**Sectioning**（拆獨立子任務並行）、**Voting**（同任務跑多次取多元輸出） | 子任務可並行求速度，或需多視角 / 多次嘗試提高信心 | sectioning：guardrail 篩查與回應生成並行；voting：多個 reviewer 找漏洞 |
| **Orchestrator-workers（協調者-工人）** | 中央 LLM **動態**拆任務、派給 worker LLM、再綜合結果 | 「無法預測需要哪些子任務」的複雜任務 | 跨多檔的 coding agent；多來源研究任務 |
| **Evaluator-optimizer（評估者-優化者）** | 一個 LLM 產生回應，另一個在**迴圈**中評估給回饋 | 有「明確評估準則」且「迭代精修有可衡量價值」時 | 文學翻譯精修；需多輪蒐集資訊的複雜搜尋 |

- **orchestrator-workers vs parallelization 的關鍵差異**：拓樸相似，但前者「子任務**不預先定義**，由 orchestrator 依輸入決定」，後者子任務固定。

> 對 Project_01 的對照：本專案的 subagent 分派（Explore/Plan）與 `project-01-workflow` 的多線程 debug 收斂屬 orchestrator-workers + evaluator-optimizer 的混用形態。

### 3.5 autonomous agent

- 起點：「來自人類使用者的命令或互動討論」。任務釐清後 agent「自主規劃與運作，必要時回來找人類要資訊或判斷」。
- 關鍵要求：每一步都要從環境取得 **"ground truth"**（如工具呼叫結果、code 執行結果）來評估進度——**這正是 §5 feedback loop 的基礎**。
- 必須設 **"stopping conditions"**（如最大迭代數）以保持控制。
- 何時用：「開放式問題、難以或不可能預測所需步數、無法 hardcode 固定路徑」時。代價＝「更高成本、錯誤複利累積」，需「在 sandbox 環境大量測試」。
- 範例：SWE-bench coding；computer-use agent。

### 3.6 三個實作原則 + ACI

1. **Simplicity（簡單）**：維持乾淨設計、不加非必要複雜度。
2. **Transparency（透明）**：明確展示 agent 的規劃步驟以利可解讀。
3. **Tool design / ACI（工具設計）**：透過「徹底的工具文檔與測試」精雕 **agent-computer interface（ACI）**。
- 框架警告：「框架能讓你快速起步，但走向生產時別猶豫去減少抽象層、用基礎元件來建」。
- 工具的 prompt engineering（B 篇先聲，C 篇展開）：
  - 給模型「足夠 token 去『思考』，以免把自己寫進死角」。
  - 「格式貼近模型在網路文本中自然見過的樣子」。
  - 「別有格式 overhead（如要求精準計數）」。
  - 像投資 HCI 一樣投資 ACI。SWE-bench 實例：團隊「花在優化工具上的時間比優化整體 prompt 還多」，發現「要求絕對路徑」可避免因切目錄產生的工具錯誤。

---

## 4. Writing Tools for Agents（給 agent 用的工具設計）

> 出處：C 篇。回答調研問題 3。

- **工具 ≠ 傳統 API**：工具是 **"a contract between deterministic systems and non-deterministic agents"**（決定性系統與非決定性 agent 之間的契約）。傳統 API 預期可預測的呼叫模式；agent 會「hallucinate 或根本不懂怎麼用」，需要根本不同的設計思維。
- **建構與評估三階段**：
  1. **Prototype**：用 Claude Code / 本地 MCP server 快速做出來，用真實用例手動測（`claude mcp add`）。
  2. **Evaluate**：產生需多次工具呼叫的真實評估任務，用直接 API 呼叫跑 agentic loop；收集**準確度以外**的指標——runtime、token 消耗、錯誤率、工具呼叫模式。
  3. **Optimize**：讓 Claude 分析評估 transcript 找摩擦點、系統性重構工具。
- **準則 1：選對工具（不是越多越好）**——**"More tools don't always lead to better outcomes."** 要**整併**功能、對齊高影響 workflow，而非鏡射每個 raw API endpoint：
  - `list_users` + `list_events` + `create_event` → 一個 `schedule_event`。
  - `read_logs` → `search_logs`（只回相關行）。
  - `get_customer_by_id` + `list_transactions` + `list_notes` → `get_customer_context`。
- **準則 2：namespace 工具**——用前綴依**服務**與**資源**分組（`asana_search`、`jira_search`），在可能上百個工具裡釐清邊界、減少混淆。
- **準則 3：回傳有意義的 context**——優先高訊號資訊；避免低階技術識別碼（`uuid`、`mime_type`），改回 `name`、`image_url`、`file_type`。short quote：「把任意英數 UUID 解析成更語意化的語言…顯著提升 Claude 的精度」。
- **準則 4：token 效率**——實作「pagination、range selection、filtering、和／或 truncation，搭配合理的預設參數值」。用**有指引性的錯誤訊息**把 agent 推向高效策略（給「具體可行動的改進」而非難解的錯誤碼）；截斷時鼓勵「多次小而精準的搜尋，而非一次寬泛搜尋」。
  - 提供 **response_format 控制**（enum 參數）：讓 agent 依下游需要選 `"concise"`（範例 72 token）或 `"detailed"`（206 token）。
- **準則 5：prompt-engineer 工具描述**——當成「對團隊新成員 / junior developer 寫 docstring」：讓隱含 context 顯性化、參數命名無歧義（`user_id` 優於 `user`）。short quote：「small refinements to tool descriptions can yield dramatic improvements」。

> 與既有筆記呼應：`CC_large_codebases` 元件表把 MCP 列為「在基礎到位前別先建」的常見誤用；本節補的是**一旦要建工具時的具體設計準則**——既有筆記完全沒展開。

---

## 5. Feedback Loop（回饋迴路）設計

> 出處：D 篇（+ B 篇 §3.5 的 ground-truth 要求）。回答調研問題 4。

- **核心迴圈**：**gather context → take action → verify work → repeat**（蒐集 context → 採取行動 → 驗證成果 → 重複）。
- 為何重要（極關鍵）：**"Agents that can check and improve their own output are fundamentally more reliable—they catch mistakes before they compound, self-correct when they drift, and get better as they iterate."**（能自查自改的 agent 本質上更可靠：在錯誤複利前抓到、漂移時自我修正、隨迭代變好。）→ 驗證**閉合回饋迴路**，把 agent 從「一次性表演者」變成「迭代改善者」。

### 三種驗證取向

| 取向 | 是什麼 | 何時最好 | 強健度 |
|---|---|---|---|
| **Rules-based feedback / Linting（規則式）** | **"The best form of feedback is providing clearly defined rules for an output, then explaining which rules failed and why."** 明確規則 + 哪條失敗 + 為什麼 | 資料驗證、型別檢查、email 格式驗證——有客觀對錯 | **最可靠**（the most reliable） |
| **Visual feedback（視覺）** | 對 UI 任務截圖 / 渲染，讓 agent 評估佈局、樣式、層級、響應式 | UI / HTML 輸出（如截圖生成的 email 回傳給模型驗證） | 中 |
| **LLM-as-judge（模型評審）** | 「讓另一個語言模型依**模糊規則**評審 agent 輸出」 | 模糊準則（如評估 email 語氣） | **較弱**——「generally not a very robust method, and can have heavy latency tradeoffs」，僅當效能收益值回成本時用 |

### 好 verifier 的判準

- 核心：**"The key is giving Claude concrete ways to evaluate its work."**（給 Claude 具體的方式評估自己的工作。）
- 好 verifier 的特徵：
  - 提供**具體、詳細的失敗解釋**（詳盡 lint 輸出 > 含糊錯誤訊息）。
  - 提供**多層回饋**（TypeScript > JavaScript，多一層型別檢查就多一層回饋）。
  - **匹配任務領域**（UI 用視覺、資料驗證用規則式）。
- 底層原則：verifier 必須**透明且可行動**，讓 agent 明確知道哪裡錯、怎麼改。

### 各 phase 機制（D 篇補充）

- **Gather context**：agentic search（`grep`/`tail`，「資料夾與檔案結構本身成為一種 context engineering」，建議起點）> semantic search/RAG（較不透明難維護，「先用 agentic search，只有需要更快結果才加 semantic」）；subagents（並行 + context 隔離，「只回相關摘錄而非整串 email」）；compaction（接近上限時自動摘要先前訊息）。
- **Take action** 四機制：**Tools**（在 context 最顯眼、是 Claude 首選動作）、**Bash & Scripts**（通用彈性）、**Code generation**（「code is precise, composable, and infinitely reusable」，是 agent 理想輸出）、**MCP**（標準化外部整合、自動處理 auth）。

> 與 Project_01 對照：本專案 Stop hook 跑 pytest 守、SubagentStart 注入規範，正是「rules-based feedback」的 harness 化——把 verifier 從 advisory（CLAUDE.md）升級成 deterministic（hook）。

---

## 6. 各層職責分配

> 回答調研問題 5。綜合 A/B/C/D/E 篇 + 既有兩份筆記的元件表。**原則：可重用專業 → skill；該自動發生 → hook；專案恆載慣例 → CLAUDE.md；外部整合 → MCP/tool；跨 session 狀態 → memory。**

| 層 | 載入時機 | 該放什麼（官方論述） | 不該放什麼 | 主要出處 |
|---|---|---|---|---|
| **System prompt** | 永遠 | 對的「高度」：強啟發式 + 期望行為的最小集；XML/MD 分區 | hardcoded 脆弱邏輯；空泛無訊號的話 | A §2.3 |
| **CLAUDE.md** | 每個 session 自動（分層疊加） | 專案特定慣例、程式庫知識、critical gotchas、指標 | 「可重用專業知識」（那屬 skill）；窮舉 edge case | 既有筆記元件表；A §2.4 |
| **Hooks** | 事件觸發 | **該確定性自動發生**的事：lint/format/test、強制規則、Stop 時提議更新 CLAUDE.md、SessionStart 注入 context | 「該自動跑的東西卻用 prompt 處理」 | 既有筆記；A 篇隱含 |
| **Skills** | 隨需、相關時 | 跨 session/專案的**可重用程序知識**；progressive disclosure 三層（metadata 探索 → SKILL.md body 啟動 → 拆檔執行） | 「把所有東西塞進 CLAUDE.md」 | E 篇 + 既有筆記 |
| **Tools（含 MCP）** | 設定後可用 / 被呼叫時 | agent 最頻繁的動作；整併過的高影響 workflow；namespace 清楚；回高訊號 context；token 效率 | bloated 工具集；鏡射 raw API endpoint；低階 UUID | C 篇全篇 |
| **Memory** | 跨 session 持久 | context window 外的筆記、進度、依賴、長程狀態 | 一次性可重算的資訊 | A §2.6 策略 2 |
| **Subagents** | 被呼叫時 | 分離探索與編輯；用乾淨 context 深探、只回 1–2k token 摘要 | 同一 session 內同時探索與編輯 | A §2.6 策略 3；既有筆記 |

**核心判別法則（綜合）**：
- **Skill vs CLAUDE.md**：可跨專案重用、且只在特定任務需要 → skill（progressive disclosure 省 context）；專案恆載、到處適用 → CLAUDE.md。E 篇 progressive disclosure 三層正是「skill 為何能省 context 而 CLAUDE.md 不能」的機制解釋——skill 開場只載 name+description 進 system prompt，判定相關才讀 body，再大才拆檔。
- **Hook vs CLAUDE.md**：CLAUDE.md 是 **advisory（勸阻）**、靠模型自律；hook 是 **deterministic（強制）**、靠 harness 執行。要「保證發生」就用 hook。（Project_01 CLAUDE.md 已明言「hook 才是強制執行、CLAUDE.md 是 advisory，故 root 紅線寫精簡即可」——與官方論述一致。）
- **Tool/MCP vs 直接讀檔**：組織已有 code search/RAG index → 暴露成 MCP 工具查詢，而非讓 Claude 直接讀檔（既有筆記 §7）；但「在基礎還沒到位前別先建 MCP」。

---

## 7. 最重要的發現

1. **「Context 是有邊際遞減的有限資源」是整個 harness 工程的第一性原理。** Context rot 源於 transformer 的 n² 關係隨長度被「拉薄」，呈漸進衰退而非斷崖（A §2.2）。本專案既有筆記講的所有「精簡、分層、scope、deny 規則」都是這條原理的工程後果——本檔補上了**為什麼**，使「lean & layered」從風格偏好升級為有理論依據的硬約束。

2. **「能自己關閉回饋迴路的 agent 才能迭代到對」有官方完整展開，且 verifier 有明確品質階梯。** D 篇定義 gather→act→verify→repeat 迴圈，並排出三種驗證的強健度序：**規則式（最可靠）> 視覺 > LLM-as-judge（最弱、有延遲代價）**。好 verifier ＝具體失敗解釋 + 多層回饋 + 匹配領域。這直接背書 Project_01 用 Stop hook 跑 pytest（規則式、最強）而非靠模型自評的設計。

3. **「人類工程師都說不清該用哪個工具，就別指望 AI 做得更好」是工具與層職責設計的單一判準。** 跨 A 篇（minimal viable tools）、B 篇（ACI / 絕對路徑 poka-yoke）、C 篇（整併 endpoint、namespace、高訊號回傳、token 效率）一致：**工具設計應投入得像 HCI 一樣多**，且「more tools don't always lead to better outcomes」。配合 §6 的層職責表，給出了「什麼放哪層」可操作的官方法則（可重用→skill、該自動→hook、外部整合→tool/MCP、恆載慣例→CLAUDE.md、跨 session 狀態→memory）。

---

> **抓取完整性**：A/B/C/D 四篇經 WebFetch 全文轉述，主體章節完整。E 篇僅取 WebSearch 摘要佐證 §6 的 progressive disclosure 三層，未做全文 fetch（如需 E 篇完整三級揭露細節，可後續補抓）。所有數字（n²、1,000–2,000 token、72/206 token）均來自原文，無自行推估。
