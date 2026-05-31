# Claude Code 在大型程式庫中的運作：最佳實踐與起步指南<br>（How Claude Code works in large codebases: Best practices and where to start）

> **本文件性質**：Anthropic 官方部落格文章的**轉述式結構化筆記**（非全文複製）。用於日後查閱該文所有重點、論述結構與清單。
> **版權聲明**：全文以筆者自己的話重新組織轉述，僅在關鍵術語與極短標誌性語句處做短引用；**無逐字全文複製**。出處見文末。

---

## 頂部 metadata

| 項目 | 內容 |
|---|---|
| 文章標題（原文） | *How Claude Code works in large codebases: Best practices and where to start* |
| 標題中譯 | Claude Code 在大型程式庫中的運作：最佳實踐與起步指南 |
| 來源 | Anthropic / Claude 官方部落格 |
| 原文 URL | https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start |
| 抓取日期 | 2026-06-01 |
| 致謝對象（原文） | Anthropic Applied AI 團隊：Alon Krifcher、Charmaine Lee、Chris Concannon、Harsh Patel、Henrique Savelli、Jason Schwartz、Jonah Dueck、Kirby Kohlmorgen；以及 Zoox 的 Amit Navindgi（提供回饋） |

**一句話 TL;DR**：在大型程式庫裡，決定 Claude Code 表現的不只是模型本身，而是圍繞模型搭建的「harness」（CLAUDE.md / hooks / skills / plugins / LSP / MCP / subagents）；關鍵是把 context 分層、讓 Claude 能精準找到對的脈絡，並在組織層面指派專責 owner 推動採用。

---

## 1. 前言（Introduction）

- Claude Code 已在實際生產環境運作，場景涵蓋：
  - 數百萬行的 monorepo（multi-million-line monorepos）
  - 累積數十年的老舊遺留系統（legacy systems）
  - 跨數十個 repository 的分散式架構
  - 擁有數千名開發者的大型組織
- 本文整理的是「在大規模採用中成功」所觀察到的模式（patterns）。
- 「大型程式庫」一詞涵蓋多種情境：數百萬行的 monorepo、累積數十年的遺留系統、散落在不同 repo 的數十個微服務，或以上組合。
- Claude Code 在某些語言上的表現「優於預期」，文章明確點名：C、C++、C#、Java、PHP。

---

## 2. Claude Code 如何在大型程式庫中導航（How Claude Code navigates large codebases）

### 2.1 導航方式（agentic search，非 RAG）

- Claude Code 的做法是：直接走訪檔案系統、讀檔、用 grep 找需要的內容、跨程式庫追蹤 reference。
- **完全在開發者本機運作**：不需要建立、維護或上傳任何程式庫索引（index）到伺服器。

### 2.2 與 RAG-based 工具的對比

- RAG（Retrieval-Augmented Generation）系統會把整個程式庫做 embedding，查詢時再取回相關片段（chunks）。
- 在大規模下，RAG 的 embedding pipeline **跟不上**活躍工程團隊的提交速度。
- 等到查詢當下，索引往往反映的是「過時」的程式庫狀態（可能是幾週、幾天、甚至幾小時前）。
- 取回的結果可能是已被改名的 function 或已刪除的 module，而系統不會告知這些內容其實已經失效。

### 2.3 Agentic search 的優勢

- 短引用：「沒有 embedding pipeline 或集中式索引需要在數千名工程師持續提交新 code 時去維護」。
- 每個開發者的 Claude 實例都從「當下活的程式庫」工作。
- 程式碼變更與 Claude 能存取到的內容之間「沒有落差（no lag）」。

### 2.4 關鍵取捨（tradeoff）

- 此做法在「Claude 有足夠的起始 context、知道該往哪裡找」時運作最好。
- 導航品質取決於程式庫的設定方式 —— 用 CLAUDE.md 與 skills 把 context 分層堆疊。
- 在十億行等級的程式庫裡做「模糊的 pattern 搜尋」，會撞到 context window 的上限。

---

## 3. Harness 跟模型一樣重要（The harness matters as much as the model）

### 3.1 核心迷思

- Claude Code 的能力**並非僅由所用模型決定**。
- 短引用：圍繞模型的生態系統 —— 即「the harness」—— 對 Claude Code 表現的決定性「比模型本身更大」。

### 3.2 五個擴充點（依建置/採用順序）

#### (1) CLAUDE.md 檔案優先（CLAUDE.md files come first）
- 是 Claude 在每個 session 開始時**自動讀取**的 context 檔。
- 根目錄的檔放「大方向 / 全局」；子目錄的檔放「局部慣例」。
- 短引用：讓它們「聚焦在普遍適用的內容」，才不會變成拖累效能的負擔。

#### (2) Hooks 讓設定能自我改善（Hooks make setup self-improving）
- Hooks 是在關鍵時刻執行的腳本（scripts that run at key moments）。
- **Stop hook**：可在 session 結束時回顧本次 session，趁 context 還新鮮時提議更新 CLAUDE.md。
- **Start hook**：可動態載入團隊專屬 context。
- 可用來「確定性地（deterministically）」強制執行規則（如 linting、formatting），產出一致結果。

#### (3) Skills 讓對的專業隨需可用（Skills keep the right expertise available on-demand）
- 在有數十種任務類型的大型程式庫裡，不是每個 session 都需要所有專業知識。
- 透過「progressive disclosure（漸進式揭露）」：只在任務需要時才載入特定 workflow 與領域知識。
- 範例：評估程式碼漏洞時載入 security review skill；需要更新文件時載入 document processing skill。
- Skills 可被 scope 到特定路徑（paths），只在程式庫的相關區段才啟用。

#### (4) Plugins 把有效做法散播出去（Plugins distribute what works）
- 痛點：好的設定常常「停留在小圈子（tribal）」，無法擴散。
- Plugin 把 skills、hooks、MCP 設定打包成「單一可安裝套件」。
- 新工程師能立刻取得與資深使用者相同的 context 與能力。
- Plugin 更新可透過受管理的 marketplace 發佈。

#### (5) Language Server Protocol（LSP）整合
- 短引用：給 Claude「和開發者在 IDE 裡相同的導航能力」。
- 多數大型程式庫的 IDE 已經在跑 LSP（即「go to definition」「find all references」背後的機制）。
- 提供 **symbol 等級的精確度**：追蹤 function 呼叫到定義、跨檔追 reference、區分不同語言中同名的 function。
- 若沒有 LSP，Claude 只能對文字做 pattern match，可能命中錯的 symbol。
- 對多語言程式庫，建議在 Claude Code 全面推行前，先做**全組織層級**的 LSP 部署。

### 3.3 額外能力

#### MCP servers 擴充一切（MCP servers extend everything）
- 把 Claude 連到原本無法觸及的內部工具、資料來源、API。
- 進階團隊會自建 MCP server，把「結構化搜尋」暴露成 Claude 可直接呼叫的工具。
- 可連接內部文件、ticketing 系統、analytics 平台。

#### Subagents 把「探索」與「編輯」分開（Subagents split exploration from editing）
- Subagent 是擁有自己 context window 的獨立 Claude 實例，接任務、做事、只把最終結果回傳給 parent。
- 典型用法：唯讀（read-only）subagent 先測繪某子系統、把發現寫進檔案；主 agent 再帶著完整全貌動手編輯。

### 3.4 元件總覽表（Component summary table，逐列轉述）

| 元件 | 是什麼 | 何時載入 | 最適合 | 常見誤用 |
|---|---|---|---|---|
| **CLAUDE.md** | Claude 自動讀取的 context 檔 | 每個 session | 專案特定慣例、程式庫知識 | 拿來放「可重用專業知識」（那應放在 skill） |
| **Hooks** | 在關鍵時刻執行的腳本 | 由事件觸發 | 自動化一致行為、捕捉 session 心得 | 把「該自動跑」的東西用 prompt 處理 |
| **Skills** | 針對特定任務類型打包的指令 | 隨需、相關時才載入 | 跨 session / 跨專案的可重用專業 | 把所有東西塞進 CLAUDE.md |
| **Plugins** | 打包的 skills / hooks / MCP 設定 | 設定後永遠可用 | 把可用設定散播至全組織 | 讓好設定停留在小圈子 |
| **LSP** | 透過語言伺服器提供即時 code intelligence | 設定後永遠可用 | typed 語言的 symbol 級導航與自動錯誤偵測 | 誤以為它會自動啟用 |
| **MCP servers** | 連接外部工具與資料 | 設定後永遠可用 | 讓 Claude 觸及原本構不到的內部工具 | 在基礎還沒到位前就先建 MCP |
| **Subagents** | 處理特定任務的獨立 Claude 實例 | 被呼叫時 | 分離探索與編輯、平行工作 | 在同一 session 內同時做探索與編輯 |

---

## 4. 三種成功部署的配置模式（Three configuration patterns from successful deployments）

### 模式 1：讓程式庫在規模下仍可導航（Making the codebase navigable at scale）

**核心原則**
- 短引用：Claude 在大型程式庫中能幫上忙的程度，「受限於它能找到對的 context 的能力」。
- 每個 session 塞太多 context 會拖垮效能；塞太少則讓 Claude 盲目摸索。

**具體做法（6 項）**

1. **保持 CLAUDE.md 精簡且分層（lean and layered）**
   - context 隨 Claude 在程式庫中移動而「additively（疊加式）」載入。
   - 根目錄檔只放大方向；子目錄檔放局部慣例。
   - 根檔只該包含「指標（pointers）+ 關鍵地雷（critical gotchas）」，其餘都是雜訊。

2. **在子目錄初始化，而非 repo 根目錄**
   - Claude scope 到相關區段時運作最好。
   - 這在 monorepo 中反直覺（工具常假設從 root 操作）。
   - Claude 會自動沿目錄樹向上走，載入沿途找到的每個 CLAUDE.md，所以 root 層 context 不會丟失。

3. **把 test / lint 指令 scope 到各子目錄**
   - Claude 只改了一個 service 卻跑整套測試 → 會 timeout、把 context 浪費在無關輸出上。
   - 在子目錄層級的 CLAUDE.md 指定「只適用該區段」的指令。
   - 對「各自有 test/build 指令的 service-oriented 程式庫」效果好。
   - 對「跨目錄深度相依的編譯語言 monorepo」較難達成。

4. **用 `.ignore` 類檔案排除生成檔、build 產物、第三方 code**
   - 把 `permissions.deny` 規則 commit 進 `.claude/settings.json`。
   - 排除規則納入版控 → 每位開發者都得到相同的雜訊削減，無需手動設定。
   - 開發 code generator 的人可在本機 override 排除規則，不影響團隊。

5. **當目錄結構本身講不清楚時，建立 codebase map**
   - 在 repo 根目錄放一個輕量 markdown 檔，列出每個 top-level 資料夾 + 一行描述。
   - 給 Claude 一份「目錄（table of contents）」可先掃，再決定要開哪些檔。
   - 若有「數百個」top-level 資料夾：用分層做法 —— 根檔只描述最高層結構，子目錄 CLAUDE.md 提供下一層細節。
   - 較單純的情況：用 `@`-mention 直接點名 Claude 該參考的特定檔案/目錄。

6. **跑 LSP server，讓 Claude 以 symbol 而非 string 搜尋**
   - 短引用：在大型程式庫對常見 function 名「grep 會回傳數千筆 match」。
   - Claude 會耗盡 context 去逐一開檔判斷哪筆重要。
   - LSP 只回傳「指向同一 symbol」的 reference，過濾在 Claude 讀任何東西之前就完成。
   - 需求：為該語言安裝 code intelligence plugin + 對應的 language server binary。

**注意事項（caveat）**
- 階層式 CLAUDE.md 做法在某些 edge case 會失效，例如：有數十萬資料夾 / 數百萬檔案的程式庫、跑在「非 git」版控上的遺留系統。
- 文章表示後續系列文章會處理這些挑戰。

### 模式 2：隨模型智慧演進，主動維護 CLAUDE.md（Actively maintaining CLAUDE.md files as model intelligence evolves）

**核心洞察**
- 短引用：為「現在的模型」寫的指令，可能會「對未來的模型造成反效果」。
- 為了引導 Claude 繞過某些它過去不擅長的 pattern 而寫的 CLAUDE.md，在下一代模型上可能變成多餘甚至綁手綁腳。

**具體例子**
- 一條叫 Claude「把每次 refactor 都拆成單檔變更」的 CLAUDE.md 規則：對舊模型有幫助，卻會阻止新模型發揮它已能勝任的「跨檔協調編輯」。
- 為了補償特定模型限制而建的 skills / hooks，一旦該限制不存在，就變成額外負擔（overhead）。
- 例：某個攔截檔案寫入、強制在 Perforce 程式庫執行 `p4 edit` 的 hook —— 在 Claude Code 加入原生 Perforce 模式後就變得多餘。

**維護節奏**
- 預期每 **3 至 6 個月**做一次有意義的配置審查。
- 另外，每當「重大模型版本發佈後效能停滯（plateau）」時也要審查。

### 模式 3：指派 Claude Code 管理與採用的 ownership（Assigning ownership for management and adoption）

**組織層的重要性**
- 光有技術配置不足以驅動採用；成功的組織也投資在「組織層（organizational layer）」。

**成功 rollout 的共通特徵**
- 散播最快的組織，是在「廣泛開放存取之前」就先投資基礎建設。
- 一個小團隊（有時只有一個人）先把工具串接好，讓 Claude 在開發者第一次接觸時就貼合其 workflow。
- 例 1：兩三位工程師打造了一套 plugin suite 與 MCP，第一天就能用。
- 例 2：整個負責 AI coding 工具的團隊，在 rollout 前就把基礎建設準備好。
- 兩例的共通點：開發者的「第一次體驗」是有生產力的，而非令人挫折的 —— 採用就此擴散。

**團隊歸屬**
- 做這件事的團隊通常隸屬 developer experience / developer productivity。
- 他們本就負責新工程師 onboarding、開發者工具。
- 新興角色：**agent manager**（PM 與工程師的混合職能），專責管理 Claude Code 生態。

**最小可行組織結構**
- 至少要有一個具 **DRI（Directly Responsible Individual，直接負責人）** 身份的人。
- 對 Claude Code 配置有 ownership。
- 有權拍板：settings、permissions 政策、plugin marketplace、CLAUDE.md 慣例。
- 有責任讓上述保持最新。

**避免碎片化（fragmentation）**
- 由下而上（bottoms-up）的採用能激發熱情，但缺乏集中化就會碎片化。
- 需要個人或團隊去「組裝並倡議」對的 Claude Code 慣例，例如：標準化的 CLAUDE.md 階層、精選的 skills 與 plugins 集合。
- 沒有這份工作，知識會停留在小圈子，採用會停滯。

**治理考量（大型組織 / 受監管產業，governance）**
- 早期就會冒出的問題：
  - 誰控制哪些 skills / plugins 可用？
  - 如何防止數千名工程師各自重造同一個輪子？
  - 如何確保 AI 生成的 code 走和人類 code 一樣的 review 流程？
- 建議做法：先從「一組已核可的 skills + 必要的 code review 流程 + 有限的初期存取權」開始，隨信心建立再擴張。

**跨職能工作小組（cross-functional working groups）**
- 最順的部署會早早建立這類小組：把 engineering、information security、governance 代表聚在一起。
- 一起定義需求、一起建構 rollout roadmap。

---

## 5. 把這些模式套用到你的組織（Applying these patterns to your organization）

**設計前提（design assumption）**
- Claude Code 是圍繞「傳統軟體工程環境」設計：
  - 工程師是程式庫的主要貢獻者
  - repo 使用 Git
  - code 遵循標準目錄結構
- 多數大型程式庫符合此模式。

**需要額外配置的非傳統情境**
- 含大型 binary 資產的遊戲引擎（game engines）
- 非常規的版控環境
- 由「非工程師」貢獻 code 的程式庫
- 以上都需要額外的配置工作。

**實作支援**
- Anthropic 的 Applied AI 團隊會直接與工程團隊合作，把這些模式轉譯成各組織的具體需求。
- 適用於「需要針對特定程式庫 / 工具 / 組織做判斷」的複雜情境。

---

## 6. 起步檢查清單（Getting Started Checklist）

- 原文此處呈現為一個視覺元素（圖示），描繪「分階段 rollout（phased rollout）」的做法。
- WebFetch 抓取時此區塊只取到標題，未取到逐條文字（圖片內容未被轉成文字）。**（誠實標註：此節為唯一不完整處，見文末「抓取完整性說明」。）**
- 依全文論述可歸納出隱含的起步順序（筆者整理，非原文逐字）：
  1. 先把 CLAUDE.md 分層做好（root pointers + 子目錄局部慣例）。
  2. 加 hooks（Stop / Start）讓設定能自我改善、強制一致性。
  3. 為多語言程式庫部署 LSP。
  4. 用 skills 做 progressive disclosure。
  5. 用 plugins 把上述打包散播。
  6. 視需要接 MCP servers。
  7. 指派 DRI / agent manager，建立 governance 與跨職能工作小組，採分階段、有限存取的 rollout。

---

## 7. 關鍵術語與事實性參照（命令 / 檔名 / 設定）

**檔名與設定**
- `CLAUDE.md`
- `.claude/settings.json`
- `.ignore` 類檔案（用於排除）
- `permissions.deny` 規則
- `@`-mention（在 prompt 中點名檔案/目錄）

**概念縮寫**
- RAG（Retrieval-Augmented Generation）
- Agentic search
- Progressive disclosure（漸進式揭露）
- LSP（Language Server Protocol）
- MCP（Model Context Protocol）
- DRI（Directly Responsible Individual）
- Stop hooks / Start hooks
- agent manager（新興角色）

**具體例子提及**
- Perforce 的 `p4 edit`（後被原生 Perforce 模式取代）
- 表現「優於預期」的語言：C、C++、C#、Java、PHP

---

## 8. 對 Project_01 的潛在啟發（筆者加值分析）

> 對應本專案現況：Raspberry Pi 上的 Python 銷售機器人，已有 SDD / worktree / subagent dispatch / sales-coder 等流程。

1. **CLAUDE.md 分層 vs. 本專案「三層架構」高度吻合**：文章主張「root 只放 pointers + critical gotchas，細節下放」，正是本專案 CLAUDE.md（大標題 + pointer）→ `.claude/rules/<topic>.md` → memory 的設計。可繼續審視 root CLAUDE.md 是否還殘留「該下放到 rules/memory」的細節，降低每 session 的 context 負擔。

2. **「主動維護 CLAUDE.md 隨模型演進」直接適用**：本專案多條規則是為補償特定模型行為而生（如 sonnet v1 踩坑 → 改 opus xhigh、dispatch threshold、Gotcha M 防護）。建議建立每 3-6 個月（或重大模型升級後）的「規則退役審查」習慣 —— 檢查哪些 hook / rule 已因模型變強而變成 overhead（呼應文章的 Perforce hook 例子）。

3. **path-scoped skills / rules 即 progressive disclosure**：本專案已有 `paths:` frontmatter 的 path-scoped rules（vendor-sdk-api / path-conventions / threading-conventions / bdd-tdd-workflow）。文章正名了這個做法，可考慮把更多「只在特定檔才需要」的知識改成 path-scoped，進一步省 context。

4. **subagent 分離「探索 / 編輯」可強化 SDD 三段迴圈**：文章的「唯讀 subagent 先測繪、主 agent 帶全貌再編輯」與本專案 SDD v3 的 implementer → spec-reviewer → code-quality-reviewer 同源。可考慮在 spec 撰寫前，增派一個唯讀「探索 subagent」先測繪受影響子系統，餵給 spec —— 尤其是動到 main.py wire-up 這類跨檔任務。

5. **LSP 在本專案 ROI 偏低但非零**：本專案是單一 Python 程式庫、規模不大，文章的 LSP 建議主要針對多語言巨型 monorepo。但未來若導入 HTML+TS 前端（架構願景三層），跨語言 symbol 導航的價值會浮現，屆時可評估 LSP plugin。

6. **「指派 DRI / 避免碎片化」對個人專案的縮影版**：本專案是單人開發，DRI 即使用者本人。文章的啟發是「設定要集中、要有人維護保新」—— 對應本專案應持續維護 `projectStructure.md`、memory 索引、`.claude/hooks/NOTES.md`，避免規則散落失同步（這正是本專案 hook 強制執法 + 三層維護原則在做的事）。

---

## 抓取完整性說明（誠實聲明）

- 主體章節（前言、導航/agentic search、harness 五擴充點、元件總覽表、三大配置模式、套用到組織、術語）皆完整抓取並轉述，無遺漏。
- **唯一不完整處**：第 6 節「Getting Started Checklist」在原文為圖示型視覺元素，WebFetch 只取得標題、未取得圖內逐條文字。已於該節明確標註，並補上「依全文論述歸納的隱含起步順序」（標明為筆者整理、非原文逐字）。
- 補充以一次 WebSearch 交叉確認文章主旨與既有理解一致，未發現主體內容缺漏。

---

## 出處

- **來源**：Anthropic / Claude 官方部落格
- **原文標題**：How Claude Code works in large codebases: Best practices and where to start
- **URL**：https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start
- **抓取日期**：2026-06-01
- **版權聲明**：本文件為轉述式摘要筆記，**非逐字全文複製**；僅在關鍵術語與極短標誌性語句處使用引號做短引用。原文版權屬 Anthropic。
