# Agent Skills 最佳實踐 — 官方文檔 + Claude blog/engineering 完整統整

> **本文件性質**：6 份官方來源（Claude API/Code 文檔 + Anthropic engineering blog + claude.com/blog）的**完整轉述式結構化筆記**，逐篇對應原文章節，保留所有規則、數字、清單、範例與術語；散文以繁中重組，不逐字全文複製。
> **版權聲明**：原文版權屬 Anthropic；本檔僅在關鍵術語 / 規則 / 極短標誌性語句處短引用。出處見文末。
> **抓取日期**：2026-06-03。
> **用途**：作為 `resources/specs/skill_reference_cleanup_2026-06-02_spec.md`（skill 精簡整改）的依據與深度討論材料。

## 索引

1. **Skill authoring best practices**（platform.claude.com docs）— 作者技巧最權威、最完整
2. **Equipping agents for the real world with Agent Skills**（engineering，2025-10-16）— skills 設計哲學
3. **Effective context engineering for AI agents**（engineering，2025-09-29）— context rot / right altitude / 長程技巧
4. **Seeing like an agent**（claude.com/blog）— 為 agent（非人）設計工具與文件
5. **Skills explained**（claude.com/blog，2025-11-13）— Skills vs prompts/Projects/subagents/MCP
6. **Improving skill-creator: test, measure, refine**（claude.com/blog）— eval-driven 測試與精修

---

## 1. Skill authoring best practices（官方 docs，最核心）

> URL：platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

### 1.1 核心原則

**(a) Concise is key（簡潔至上）**
- context window 是「公共財」，skill 與系統提示、對話史、其他 skill metadata、實際請求共享。
- 不是每個 token 都即時有成本：啟動只預載 metadata（name+description）；SKILL.md 在相關時才讀；附檔用到才讀。**但**：一旦 SKILL.md 載入，每個 token 都在跟對話史與其他 context 競爭。
- **預設假設：Claude 已經很聰明**。只加 Claude 還沒有的 context。每段自問：
  - 「Claude 真的需要這個解釋嗎？」
  - 「我能不能假設 Claude 已懂這個？」
  - 「這段值不值它的 token？」
- 範例對比：好的「Extract PDF text」約 50 token（直接給 pdfplumber code）；壞的約 150 token（解釋 PDF 是什麼、有哪些 library…）。簡潔版假設 Claude 已懂 PDF 與 library。

**(b) Set appropriate degrees of freedom（依任務脆弱度配自由度）**
- **高自由度**（純文字指示）：多解法皆有效、決策依情境、靠啟發式。例：code review 流程（分析結構→找 bug→建議→查慣例）。
- **中自由度**（虛擬碼 / 帶參數 script）：有偏好 pattern、容許變化、config 影響行為。例：`generate_report(data, format=..., include_charts=...)`。
- **低自由度**（精確 script / 少或無參數）：操作脆弱易錯、一致性關鍵、必須照特定順序。例：DB migration「就跑這條、別改別加 flag」。
- **類比**：把 Claude 當探路機器人——「兩側懸崖的窄橋」只有一條安全路 → 給精確護欄（低自由度）；「無障礙開闊地」多路皆通 → 給方向、信任它找路（高自由度）。

**(c) Test with all models you plan to use**
- skill 是模型的「加法」，效果取決於底層模型。對 Haiku（夠不夠引導？）/ Sonnet（清楚高效？）/ Opus（會不會過度解釋？）分別測。對 Opus 完美的可能對 Haiku 不夠細。

### 1.2 Skill 結構

**YAML frontmatter（必填兩欄）**：
- `name`：≤64 字元、僅小寫字母/數字/連字號、無 XML tag、不可含保留字 "anthropic"/"claude"。
- `description`：非空、≤1024 字元、無 XML tag、應寫「做什麼 + 何時用」。

**命名慣例**：建議 **gerund 動名詞形**（verb+ing）清楚描述能力。
- 好：`processing-pdfs`、`analyzing-spreadsheets`、`testing-code`、`writing-documentation`。
- 可接受：名詞片語 `pdf-processing`、動作式 `process-pdfs`。
- 避免：`helper`/`utils`/`tools`（模糊）、`documents`/`data`（過泛）、含保留字、collection 內不一致。

**寫有效的 description**：
- **一律第三人稱**（會被注入系統提示，視角不一致會害 discovery）。好：「Processes Excel files and generates reports」；避免：「I can help…」「You can use this…」。
- **具體 + 含關鍵詞**：寫「做什麼 + 何時用/觸發語境」。Claude 靠它從 100+ skills 中選對的。
- 範例：「Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.」
- 避免：「Helps with documents」「Processes data」「Does stuff with files」。

### 1.3 Progressive disclosure patterns

- SKILL.md 是 overview，像 onboarding 指南的目錄，指向細節材料。
- **實務指引**：SKILL.md body **<500 行**；逼近上限就拆檔。
- **Pattern 1：高層 guide + references**——SKILL.md 放 quick start，進階功能各自 `See [FORMS.md]` / `[REFERENCE.md]` / `[EXAMPLES.md]`，用到才載。
- **Pattern 2：domain 分檔**——多 domain 時按 domain 切（`reference/finance.md` / `sales.md` / `product.md`…），問 sales 就只讀 sales schema，不載 finance。SKILL.md 給導航 + 可用 `grep -i "revenue" reference/finance.md` 快查。
- **Pattern 3：條件式細節**——基本內容直接給，進階（tracked changes / OOXML）才 `See [REDLINING.md]`。

**⚠️ Avoid deeply nested references（避免深層巢狀引用）**：
- Claude 對「從被引用檔再引用的檔」可能**只部分讀**（用 `head -100` 預覽）→ 資訊不全。
- **規則：references 一律從 SKILL.md 一層深直連**。
- 壞：SKILL.md→advanced.md→details.md→真正資訊。好：SKILL.md 直接列 basic / advanced.md / reference.md / examples.md。

**Structure longer reference files with TOC**：
- **>100 行的 reference 開頭放目錄（Table of Contents）**，確保 Claude 即使部分讀也看得到全貌；之後可整檔讀或跳段。

### 1.4 Workflows 與 feedback loops

- 複雜操作拆成清楚的循序步驟；特別複雜的給「**可勾選 checklist**」讓 Claude 複製進回應逐項打勾（研究合成 / PDF 表單填寫兩例）。
- **Feedback loop**：常見模式「跑 validator → 修錯 → 重複」，大幅提升輸出品質（風格指南合規 / 文件編輯 validate→pack 兩例）。

### 1.5 Content guidelines

- **避免 time-sensitive 資訊**（會過時）：不要寫「2025 年 8 月前用舊 API、之後用新 API」。改用 **`## Old patterns`** 段 +（建議）`<details><summary>Legacy …（deprecated 2025-08）</summary>` 摺疊，留歷史脈絡不污染主內容。
- **一致術語**：一個詞用到底。好：永遠「API endpoint」「field」「extract」。壞：混用 endpoint/URL/route/path、field/box/element/control、extract/pull/get/retrieve。一致性幫 Claude 理解。

### 1.6 Common patterns

- **Template pattern**：給輸出格式範本，嚴格度依需求（嚴格「ALWAYS use this exact template」；彈性「sensible default, use judgment」）。
- **Examples pattern**：輸出品質靠看範例的場景，給 input/output 配對（如 commit message 三例）。**「Examples help Claude understand … more clearly than descriptions alone.」**
- **Conditional workflow pattern**：在決策點分流（「Creating new content? → … / Editing? → …」）。
- Tip：workflow 太大太多步 → 拆獨立檔，叫 Claude 依任務讀對應檔。

### 1.7 Evaluation and iteration（eval-driven）

**Build evaluations FIRST（寫大量文件前先建 eval）**——確保 skill 解決真問題而非想像問題。
- **Evaluation-driven development 5 步**：
  1. **Identify gaps**：無 skill 跑代表性任務，記錄具體失敗 / 缺的 context。
  2. **Create evaluations**：建 3 個測這些 gap 的場景。
  3. **Establish baseline**：量無 skill 時的表現。
  4. **Write minimal instructions**：只寫剛好補 gap、通過 eval 的內容。
  5. **Iterate**：跑 eval、比 baseline、精修。
- **Eval 結構**（JSON 範例）：`skills`、`query`、`files`、`expected_behavior`（一串可判定的行為描述）。Eval 是「衡量 skill 有效性的真相來源」。

**Develop Skills iteratively with Claude（Claude A / Claude B）**：
- 用 Claude A 設計/精修 skill，用 Claude B（fresh instance 載入該 skill）在真任務測。
- 建立新 skill：無 skill 完成任務 → 找出可重用 pattern → 請 Claude A 建 skill → **Review for conciseness（請 Claude A 刪 Claude 已懂的解釋，如「移掉 win rate 是什麼的解釋」）** → 改善資訊架構（如「把 table schema 拆獨立 reference」）→ Claude B 測 → 依觀察回 Claude A 修。
- Tip：Claude 原生懂 skill 格式，不需特殊 system prompt 或「writing skills」skill。

**Observe how Claude navigates Skills（觀察導航）**——盯：
- 非預期探索路徑（讀檔順序出乎意料 → 結構不夠直覺）。
- 漏跟連結（沒 follow 到重要檔 → 連結要更明確/顯眼）。
- 過度依賴某段（一直讀同一檔 → 該內容也許該進 SKILL.md）。
- 從不讀的內容（某 bundled 檔沒被讀 → 也許多餘或訊號不足）。
- `name` + `description` 特別關鍵（決定觸發）。

**Gather team feedback**：分享給隊友、觀察使用、問「該觸發時有觸發嗎？指示清楚嗎？缺什麼？」。

### 1.8 Anti-patterns

- **避免 Windows 路徑**：一律正斜線 `scripts/helper.py`，反斜線在 Unix 出錯。
- **避免堆太多選項**：別「可用 pypdf 或 pdfplumber 或 PyMuPDF 或…」；給一個 default + 逃生口（「掃描檔需 OCR 才改用 pdf2image+pytesseract」）。

### 1.9 進階（含 code 的 skill）

- **Solve, don't punt**：script 要處理錯誤（FileNotFound/Permission 給 fallback），別丟給 Claude。
- **No voodoo constants**（Ousterhout's law）：常數要有註解理由（`REQUEST_TIMEOUT = 30 # …`），別 `TIMEOUT = 47 # Why 47?`。
- **Provide utility scripts**：即使 Claude 能寫，預製 script 更可靠、省 token、省時間、一致。**講清楚要「執行」還是「當 reference 讀」**。
- **Verifiable intermediate outputs（plan-validate-execute）**：複雜開放任務先產 plan（結構化）→ script validate → 才 execute。用於批次/破壞性/高風險操作。validate script 要 verbose（具體錯誤訊息列可用欄位）。
- **Package dependencies**：claude.ai 可裝 npm/PyPI；**Claude API 無網路、不能 runtime 裝**。SKILL.md 列所需套件並確認可用。

### 1.10 Runtime environment（影響寫法）

- metadata 啟動預載；檔案用 bash Read 按需讀；script 可執行而不載入全文（只 output 耗 token）；**大檔不讀就零 context 成本**。
- 路徑正斜線；檔名描述性（`form_validation_rules.md` 非 `doc2.md`）；按 domain/feature 組織；可大方 bundle 完整 API 文檔/範例/資料集（不讀不耗）；MCP 工具用全名 `ServerName:tool_name`；別假設套件已裝。

### 1.11 Checklist（精簡 skill 自驗，節錄 markdown-only 相關）

- description 具體含關鍵詞、含「做什麼+何時用」；SKILL.md <500 行；細節在獨立檔；**無 time-sensitive 資訊（或進 old patterns 段）**；**術語一致**；**範例具體非抽象**；**file references 一層深**；適當 progressive disclosure；workflow 步驟清楚。
- 測試：至少 3 個 eval；用 Haiku/Sonnet/Opus 測；真實情境測；納入團隊回饋。

---

## 2. Equipping agents for the real world with Agent Skills（engineering，2025-10-16）

> 作者：Barry Zhang, Keith Lazuka, Mahesh Murag。

- **定義**：Skill = 含 instructions/scripts/resources 的目錄，agent 動態 discover + load，把通用 agent 變專家。類比「給新人的 onboarding 指南」。動機：要更 composable / scalable / portable 的方式給 agent 領域專長。
- **結構**：目錄 + SKILL.md（YAML frontmatter 必含 name/description）。
- **三層 progressive disclosure**：
  1. 啟動：name+description 預載系統提示（判斷相關性，不載全文）。
  2. 任務觸發：讀 SKILL.md body 進 context。
  3. 巢狀 references：複雜時 bundle 附檔，特定情境才讀（PDF skill 的 `reference.md` / `forms.md`，填表才讀 forms.md）。
  - 因 agent 有 filesystem + code execution，不必把整個 skill 載入 context → **skill 複雜度實質無上限**。
- **Skills + code execution**：可 bundle 可執行 code 當工具。理由：某些操作（如排序）用傳統 code 比 token 生成更省更可靠（determinism）。code 可同時當「可執行工具」與「文件」；**要講清楚執行 vs 當 reference 讀**。
- **開放標準**（2025-12-18 更新）：Agent Skills 發布為跨平台開放標準。
- **4 條開發/評估指引**：
  1. **Start with Evaluation**：跑代表性任務找 gap，增量補。
  2. **Structure for Scale**：SKILL.md 太大就拆檔；互斥/少同用的 context 分檔省 token；code 雙用途要講清楚。
  3. **Think from Claude's Perspective**：觀察真實使用、非預期軌跡、過度依賴；重視 name/description；Claude 出軌時請它自省哪裡失敗。
  4. **Iterate with Claude**：做任務時請 Claude 把成功做法 + 常見錯誤 capture 成可重用 context/code。
- **安全**：只裝可信來源；不可信來源徹底 audit（讀所有 bundled 檔、留意 code 依賴、bundled 資源、連外網的指示）。
- **支援平台**：Claude.ai / Claude Code / Agent SDK / Developer Platform。長期願景：agent 自主建/改/評 skill。
- **與 MCP 關係**：互補——Skills 教「複雜 workflow（含外部工具）」。

---

## 3. Effective context engineering for AI agents（engineering，2025-09-29）

> 作者：Anthropic Applied AI team。

- **context engineering 定義**：在 LLM 限制下「優化那些 token 的效用」。context = 採樣時餵入的所有 token（系統指示、工具、外部資料、訊息史、MCP）。心態：「thinking in context」——考慮 LLM 可見的整體狀態會產生什麼行為。
- **vs prompt engineering**：prompt engineering 偏一次性寫好指令；context engineering 是跨多輪「策展與維護最佳 token 集」的循環迭代。
- **為何重要**：
  - **Context rot**：token 數上升 → 回憶準確度下降（所有模型皆有，程度不一）。
  - **Attention budget**：context 是有限資源、邊際遞減；每個新 token 都耗 attention。transformer n² 注意力關係，越長越稀釋；位置編碼外推有「token 位置理解的退化」。表現是漸層非斷崖。
- **Anatomy of effective context**：
  - 指導原則：找「**最小的高訊號 token 集**，最大化期望結果機率」。
  - **System prompts — right altitude**：兩個失敗模式——過度具體（脆弱 if-else 硬規則、維護負擔）/ 過度模糊（無具體訊號、假設共享 context）。Goldilocks：具體到能引導、又彈性到給強啟發。結構：用 XML tag / Markdown header 分節（`<background_information>`/`<instructions>`/`## Tool guidance`…）；「minimal ≠ 一定短」；先用最強模型 + 最小 prompt 測，依失敗模式增補。
  - **Tool design**：token-efficient、鼓勵高效行為、自足且容錯、用途明確不重疊。**失敗模式：臃腫工具集、決策點模糊**（人都分不清該用哪個，agent 也分不清）。
  - **Examples / few-shot**：策展多樣、canonical 的範例，**勝過塞 edge-case 清單**。「examples 是勝過千言的『圖片』」。
- **Context retrieval / agentic search**：
  - agent 定義：「LLM 在迴圈裡自主用工具」。
  - **just-in-time vs 預載**：保留輕量識別子（檔路徑、查詢、連結），runtime 才動態載入；mirror 人類認知（用檔案系統/書籤而非死記）。
  - Claude Code 例：寫 query、存結果、用 `head`/`tail` 分析大檔不全載；用 metadata（資料夾層級/命名/timestamp）當訊號；progressive disclosure 逐層組裝理解。
  - 取捨：runtime 探索比預算慢、需「opinionated 的工程」避免浪費 context。**hybrid**：Claude Code 把 CLAUDE.md 直接載入 + 用 `glob`/`grep` just-in-time。原則「**Do the simplest thing that works**」。
- **長程任務（數十分鐘~數小時）三技巧**：
  1. **Compaction**：近上限時摘要對話、重啟新 context。Claude Code 保留架構決策/未解 bug/實作細節，丟冗餘 tool output；續接時帶壓縮 context + 最近 5 個存取過的檔。調校：先最大化 recall 再提 precision。最安全的輕量 compaction＝清舊 tool result。
  2. **Structured note-taking（agentic memory）**：定期寫 note 持久到 context 外（to-do list、NOTES.md）；Pokémon 例跨數千步維持 tally/地圖/成就。Developer Platform 有 memory tool（beta）。
  3. **Sub-agent architectures**：主 agent 高層規劃，sub-agent 乾淨 context 做專注深工，各自探索數萬 token、只回 1000-2000 token 摘要。複雜研究任務明顯優於單 agent。
  - 選法：compaction（需大量來回的對話流）/ note-taking（有明確里程碑的迭代開發）/ multi-agent（可平行探索的複雜研究分析）。
- **演進**：模型越強，重點從「完美 prompt」轉向「策展什麼資訊進入有限 attention budget」；但「把 context 當珍貴有限資源」永遠核心。

---

## 4. Seeing like an agent（claude.com/blog）

- **核心框架**：為 agent 設計工具要「站在 agent 視角」。類比：解數學題的人需配合能力的工具（紙/計算機/電腦）。
- **加工具的門檻很高**：「多一個工具＝多一個要思考的選項」，增加認知負擔。靠實驗、讀 output、迭代——「You learn to see like an agent」。
- **案例 1 AskUserQuestion**：失敗嘗試（塞 ExitPlanTool 參數造成資訊衝突 / 改 markdown 格式 Claude 維持不住結構）→ 解法是專用工具觸發 modal UI、阻塞 agent loop、保證結構化選項。原則「**再好的工具，Claude 不懂怎麼呼叫也沒用**」。
- **案例 2 Todos→Tasks**：每 5 turn 的 system reminder 反效果（Claude 當成約束非引導）；隨能力提升 todo list 變限制 → 換成支援 inter-agent 協調/依賴的 Task。洞見「**模型能力提升後，曾經需要的工具可能反而綁手；常重訪『需要哪些工具』的假設**」。
- **Progressive disclosure：RAG → search → skills**：
  - 初版 vector DB 預索引 + RAG 取片段 → 脆弱、context 是「被給」非「被發現」。
  - 改 grep 讓 Claude 自己搜 → 演進成 Agent Skills 的**遞迴檔案發現**：skill 檔引用其他檔、Claude 遞迴讀、**自己 build context**。「從不太能 build context → 能跨數層檔案 nested search 找到精確 context」。
- **Claude Code guide subagent 模式**：把 Claude Code 自身文檔塞系統提示會造成 context rot、干擾主職（寫 code）→ 改用 subagent 在隔離 context 載文檔、照抽取指示、只回相關答案，保持主 agent context 乾淨。原則「**不加工具也能加功能——靠委派**」。
- **對「寫給 agent 讀的 reference 文件」的 takeaway**：
  1. 假設 agent 會**增量搜尋**而非一次吸收全文 → 為發現而設計結構。
  2. 階層式檔案組織支援遞迴發現（breadth-first 再 depth）。
  3. 大段文件載入主 context 造成 overhead → 專門查詢委派 subagent。
  4. 按需載入時給明確抽取指引（抽什麼、丟什麼）。
  5. 工具有效性非定局，隨模型能力重訪假設。
- 結語：工具設計「既是科學也是藝術」，取決於模型/目標/環境，需持續實驗 + agent-centered 思考。

---

## 5. Skills explained（claude.com/blog，2025-11-13）

- **Skills 定義**：含 instructions/scripts/resources 的資料夾，相關時動態載入；像「專門訓練手冊」提供領域專長免重複解釋。
- **三層 progressive disclosure（給了具體數字）**：metadata 先載（**~100 token**）標示相關性；full instructions 需要時載（**<5k token**）；bundled 檔/script 用到才載。
- **何時用 Skills**：組織 workflow（品牌規範/合規/模板）、領域專長（Excel/PDF/資料分析）、個人偏好（筆記法/coding pattern）。
- **五大 building block 對照**：
  - **vs Prompts**：prompt 短暫/對話式/反應式、單次；skill 跨對話持久/主動套用/含 code。重複貼同一 prompt → 升級成 skill。
  - **vs Projects**：Project 是自含工作區（獨立 chat 史 + 200K context + 上傳文件 + 自訂指示），提供「**你需要知道什麼（what you know）**」靜態背景；skill 提供「**怎麼做（how）**」動態專長、相關才啟動、progressive disclosure 更省 context。
  - **vs Subagents**：subagent 獨立 context/自訂系統提示/特定工具權限、隔離執行回傳結果；skill 是可攜專長、跨 agent/對話重用。**「若多個 agent/對話需要同一專長 → 建 skill，而非把知識寫進個別 subagent」**。最佳組合：subagent 用 skill 當專長。
  - **vs MCP**：MCP 是連外部系統/資料/工具的連通層（access）；skill 教「拿到資料/工具後做什麼」（usage）。互補：MCP 連 DB、skill 教 query 優化/過濾/報表慣例。
- **granularity**：依**功能邊界**非大小；**官方無「一 skill 一能力」硬規定**。
- **authoring 指引**：確保是持久可重用的專長（非一次性）；含程序知識 + 可執行範例；reference 為「高效發現」而組織；考慮跨 project/agent 可攜。
- **組織最佳實踐**：重複的 prompt → 轉 skill；靜態 context（Projects）與動態能力（Skills）分開；領域專長/程序知識用 skill。

---

## 6. Improving skill-creator: test, measure, refine（claude.com/blog）

- **目的**：讓非工程師也能驗證 skill 是否有效、抓 regression、改 description，靠測試/benchmark/迭代，免寫 code。
- **兩類 skill**：
  - **Capability Uplift**：讓 Claude 做 base model 做不到/不穩的事（如文件生成技巧）。隱憂：模型變強後可能變多餘 → eval 可偵測「過時」（base model 不靠 skill 也通過 eval 時）。
  - **Encoded Preference**：把 Claude 既有能力按團隊 workflow 排序（如 NDA review、週報）。隱憂：耐久度取決於對真實 workflow 的忠實度。
- **Evaluation 框架**：「定義測試 prompt（+檔案）、描述『好』長怎樣，skill-creator 告訴你 skill 撐不撐得住」。兩大用途：(1) **Regression detection**（對新模型跑 eval，先抓品質變化）；(2) **Capability obsolescence**（base model 不靠 skill 也過 → 技巧已內化）。
- **Benchmark mode**：標準化評估追蹤 **eval pass rate / elapsed time / token usage**；模型更新後或迭代精修時跑；結果使用者自有（本地/dashboard/CI）。
- **Multi-agent evaluation**：獨立 agent 平行跑 eval，各自乾淨 context + 隔離 token/timing，消除交叉污染。**A/B 用 comparator agent** 盲判兩版本或 skill vs baseline，判斷改動是否真的更好。
- **Skill trigger 優化**：description 精準度隨 skill 增多越關鍵——過廣→false trigger；過窄→不觸發。skill-creator 對照 sample prompt 分析 description、建議減少 false +/− 的修改。實證：6 個公開文件生成 skill 中 5 個經 description 優化後改善。
- **PDF 例**：非填充式表單（無定義欄位的座標放字）失敗 → eval 隔離失敗 → 修法錨定到抽取的文字座標。展示「eval 隔離具體失敗→針對性修」。
- **未來方向**：「也許一段 what 的自然語言描述就夠，模型補完 how」——eval 把期望結果當 spec，朝「skill 由目標而非實作指示定義」演進。

---

## 7. 綜合萃取：對本專案 skill 精簡整改的啟示

> 對應 `skill_reference_cleanup_2026-06-02_spec.md`。

| 官方原則 | 來源 | 對應 spec |
|---|---|---|
| Concise / 「Claude 已聰明」/ context rot / attention budget | §1.1, §3 | §2.1 簡潔測試（已納入） |
| Degrees of freedom / right altitude | §1.1, §3 | §2.2 顆粒度（已納入） |
| time-sensitive → `<details>` old patterns | §1.5 | §2.3 歷史處理（已納入） |
| references 一層深、避免深巢狀 | §1.3, §4 | §2.4 每檔自足、不互指（已納入） |
| >100 行加 TOC + per-file 自述 | §1.3 | §2.6 層 2 自述 + TOC（已納入） |
| 一致術語 / examples > rule list / 正斜線 / 不堆選項 | §1.5, §1.8, §3 | §2.7（已納入） |
| 無「一 skill 一能力」硬規定、router 合法 | §5 | §7 不拆 mega skill（已納入） |
| **Eval-driven：先建 eval、量 baseline、回歸偵測** | §1.7, §2, §6 | **尚未納入 → 建議新增「§10 Eval 驗證」** |
| **Claude A/B 迭代 + 觀察導航** | §1.7, §2 | **尚未納入 → 建議併入 §6 驗證** |
| **description 觸發優化（false +/−）** | §6 | 部分（§3 SKILL.md description 收緊）→ 可加觸發測試 |
| benchmark：pass rate / time / token | §6 | 可選：精簡前後量 token 對比 |

**最關鍵的兩個尚未納入點**（深度討論用）：
1. **Eval-driven 回歸驗證**：官方視 eval 為「skill 有效性的真相來源」。對「精簡」任務 = 回歸測試：精簡前用 fresh subagent（Claude B）跑代表性任務測 baseline，精簡後重跑確認無退化（觸發/找對檔/自足/不做錯）。直接根治「會不會砍掉重點細節」的疑慮。
2. **觀察導航 + A/B**：精簡後觀察 Claude B 是否經 SKILL.md 路由 + `🎯` 找到對檔、有無漏跟/過度依賴；必要時 comparator 盲判精簡版 vs 原版。

---

## 出處

1. Skill authoring best practices — platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices（亦 docs.claude.com 同頁）
2. Equipping agents for the real world with Agent Skills — anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills（2025-10-16）
3. Effective context engineering for AI agents — anthropic.com/engineering/effective-context-engineering-for-ai-agents（2025-09-29）
4. Seeing like an agent — claude.com/blog/seeing-like-an-agent
5. Skills explained — claude.com/blog/skills-explained（2025-11-13）
6. Improving skill-creator: test, measure, and refine Agent Skills — claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills

> **版權**：以上皆 Anthropic 官方內容之轉述式摘要筆記，非逐字全文複製；功能性事實（數字/規則/設定）照實記錄，散文以繁中重組。抓取日期 2026-06-03。
