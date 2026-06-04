# Agent 記憶與自我記憶管理（淨增量研究筆記）

> **本檔性質**：聚焦「Claude API memory tool（beta）／ context editing ／ compaction ／ Managed Agents memory ／ context engineering」的官方規格與最佳實踐統整。
> **與既有筆記的關係**：Claude Code「自動記憶（auto-memory）＋ CLAUDE.md」載入機制、`MEMORY.md` 200 行 / 25KB 規則、`~/.claude/projects/<project>/memory/` 位置、`/memory` 指令、`autoMemoryEnabled` 等已在
> **`memory_official_guide_2026-06-02.md`** 完整涵蓋——本檔**不重寫**，重疊處標「→ 見 memory_official_guide」。本檔寫的是該檔**沒有**的東西：**API 層的 memory tool / 伺服端 compaction / context editing / Managed Agents memory / context engineering 文章**。
> **版權**：所有出處屬 Anthropic；本檔為轉述式結構化筆記，識別字串（beta header、tool type、參數名、數字）為功能性事實照實複製，散文以繁中重組。出處見文末來源表。

---

## 目錄

1. [來源清單表](#1-來源清單表)
2. [全景：三層記憶 / 上下文機制如何分工](#2-全景三層記憶--上下文機制如何分工)
3. [Claude API Memory Tool（beta `memory_20250818`）](#3-claude-api-memory-toolbeta-memory_20250818)
4. [Context Editing（beta `context-management-2025-06-27`）](#4-context-editingbeta-context-management-2025-06-27)
5. [Compaction（beta `compact-2026-01-12`，伺服端摘要）](#5-compactionbeta-compact-2026-01-12伺服端摘要)
6. [Managed Agents Memory（memory stores，beta `managed-agents-2026-04-01`）](#6-managed-agents-memorymemory-storesbeta-managed-agents-2026-04-01)
7. [Context Engineering：attention budget 與 just-in-time retrieval](#7-context-engineeringattention-budget-與-just-in-time-retrieval)
8. [長時程 agent harness 的記憶模式（progress file / 假設中斷）](#8-長時程-agent-harness-的記憶模式progress-file--假設中斷)
9. [Claude Code 端：PreCompact / PostCompact / SessionStart(compact) hooks](#9-claude-code-端precompact--postcompact--sessionstartcompact-hooks)
10. [agent 自我管理記憶的最佳實踐（該記 / 不該記 / 防腐 / 索引）](#10-agent-自我管理記憶的最佳實踐該記--不該記--防腐--索引)
11. [多 session / 多 agent 共享記憶的官方模式](#11-多-session--多-agent-共享記憶的官方模式)
12. [與 Claude Code auto-memory 的差異對照](#12-與-claude-code-auto-memory-的差異對照)
13. [本專案（Project_01）可借鏡的點](#13-本專案project_01可借鏡的點)
14. [來源表（完整 URL + 抓取日期）](#14-來源表完整-url--抓取日期)

---

## 1. 來源清單表

| # | 文件 | 類型 | URL |
|---|---|---|---|
| S1 | Memory tool | API 文檔 | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool |
| S2 | Context editing | API 文檔 | https://platform.claude.com/docs/en/build-with-claude/context-editing |
| S3 | Compaction | API 文檔 | https://platform.claude.com/docs/en/build-with-claude/compaction |
| S4 | Using agent memory（Managed Agents） | API 文檔 | https://platform.claude.com/docs/en/managed-agents/memory |
| S5 | Effective context engineering for AI agents | 工程部落格 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| S6 | Effective harnesses for long-running agents | 工程部落格 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| S7 | Managing context on the Claude Developer Platform | 部落格 | https://claude.com/blog/context-management |
| S8 | Memory & context management（cookbook，Sonnet 4.6） | Cookbook | https://platform.claude.com/cookbook/tool-use-memory-cookbook ／ https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/memory_cookbook.ipynb |
| S9 | Hooks reference（PreCompact / PostCompact / SessionStart） | Claude Code 文檔 | https://code.claude.com/docs/en/hooks |

抓取日期：全部 2026-06-04（WebFetch）。Compaction 與 Managed Agents memory 為較新的 beta，規格可能持續演進，引用以上述抓取日為準。

---

## 2. 全景：三層記憶 / 上下文機制如何分工

官方把「長時程 agent 的上下文/記憶」拆成**互補的多層**，不是單一機制：

| 層 | 機制 | 在哪 | 作用 | 出處 |
|---|---|---|---|---|
| **短期：清掉雜訊** | **Context editing**（`clear_tool_uses` / `clear_thinking`） | 伺服端，送進模型前套用 | 在對話成長時**選擇性清除**舊 tool result / thinking block，騰出 attention budget | S2 |
| **短期：壓縮全局** | **Compaction** | 伺服端 | 逼近 context window 上限時，**整段對話摘要**成一個 `compaction` block，之後的請求丟掉摘要前的訊息 | S3 |
| **長期：持久化** | **Memory tool**（`/memories` 檔案） | 用戶端（你的基礎設施） | 把學到的東西寫成檔案，**跨 session / 跨 compaction 邊界存活** | S1 |

S1 明說 memory tool 是「just-in-time context retrieval 的關鍵原語：不是一次把所有相關資訊載入，而是 agent 把學到的存進記憶、按需取回」。

S1 也明確點出三者的**搭配關係**：
- **memory tool + context editing**：context editing 清用戶端的特定 tool result，memory 把重要資訊存到 context window 之外。
- **memory tool + compaction**：「compaction 讓 active context 維持可控、不需用戶端記帳；memory 則在 compaction 邊界之間持久化重要資訊，使摘要中不致遺失任何關鍵內容」（S1 原文轉述）。
- 對長時程 agentic workflow，**官方建議兩者都用**。

---

## 3. Claude API Memory Tool（beta `memory_20250818`）

> **這是 Claude Code auto-memory 之外的另一套東西**：API 層、**用戶端執行（client-side）**、由你自己決定儲存後端。Claude Code auto-memory 是 CLI 內建、機器本地、自動寫的（→ 見 memory_official_guide §2）。

### 3.1 基本規格（S1）
- **啟用方式**：在 `tools` 陣列加入 `{"type": "memory_20250818", "name": "memory"}`。
- **用戶端工具**：memory tool **operates client-side**——Claude 發出 tool call，**你的應用在本地執行**實際檔案操作，你完全掌控存哪、怎麼存（檔案 / 資料庫 / 雲端 / 加密檔皆可）。
- **SDK helper**：Python 可 subclass `BetaAbstractMemoryTool`；TypeScript 用 `betaMemoryTool`。官方範例：
  - Python：`examples/memory/basic.py`（anthropic-sdk-python）
  - TypeScript：`examples/tools-helpers-memory.ts`（anthropic-sdk-typescript）
- **記憶目錄**：所有操作應限制在 **`/memories`** 目錄。
- **ZDR**：此功能符合 Zero Data Retention 資格。
- **支援模型**（S8 cookbook 列）：Claude Opus 4.1 / Opus 4 / Sonnet 4.6 / Sonnet 4 / Haiku 4.5（並以 Sonnet 4.6 為示範主力）。

### 3.2 運作流程（S1）
啟用後，Claude **在開始任務前自動先 `view /memories`**，讀相關檔，再開始工作。系統提示會自動注入這段 memory protocol（原文片段）：

```text
IMPORTANT: ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE.
MEMORY PROTOCOL:
1. Use the `view` command of your `memory` tool to check for earlier progress.
2. ... (work on the task) ...
     - As you make progress, record status / progress / thoughts etc in your memory.
ASSUME INTERRUPTION: Your context window might be reset at any moment, so you risk
losing any progress that is not recorded in your memory directory.
```

> 注意末句「**ASSUME INTERRUPTION**（假設隨時被中斷）」——這是整套長時程記憶設計的核心心智模型，與 §8 harness 文章一致。

### 3.3 七個 command（用戶端需自行實作，S1）

| command | 參數 | 行為 / 回傳重點 |
|---|---|---|
| `view` | `path`、選填 `view_range:[start,end]` | 目錄→列出最多 2 層、人類可讀大小、排除隱藏檔與 `node_modules`、tab 分隔；檔案→帶 6 字寬右對齊行號（1-indexed、tab 分隔）；超過 999,999 行回錯誤 |
| `create` | `path`、`file_text` | 成功回 `"File created successfully at: {path}"`；已存在回 `"Error: File {path} already exists"` |
| `str_replace` | `path`、`old_str`、`new_str` | 找不到 / 多筆相符都回錯誤（多筆要求 `old_str` 唯一） |
| `insert` | `path`、`insert_line`、`insert_text` | 行號需在 `[0, n_lines]` |
| `delete` | `path` | 目錄遞迴刪除 |
| `rename` | `old_path`、`new_path` | 目的地已存在則報錯，**不覆寫** |

> 文檔註：「這些是 Claude 最熟悉的建議行為，你可以依需求修改實作、回傳自訂字串。」

### 3.4 安全（S1，重要）
- **路徑穿越（path traversal）**：`<Warning>` 等級——「你的實作 **MUST** 驗證所有路徑以防目錄穿越攻擊」。建議：
  - 驗證所有 path 以 `/memories` 開頭；
  - 解析成 canonical form 並確認仍在記憶目錄內（Python 用 `pathlib.Path.resolve()` + `relative_to()`）；
  - 拒絕含 `../`、`..\\`、URL-encoded（`%2e%2e%2f`）等序列。
- **敏感資訊**：Claude「通常會拒絕把敏感資訊寫進記憶檔」，但仍建議自行做更嚴格的剝除驗證。
- **檔案大小**：建議追蹤大小、限制單次讀取最大字元數、讓 Claude 分頁讀。
- **記憶過期**：建議定期清掉長期未存取的記憶檔。

### 3.5 Prompting 指引（S1）
- 若觀察到 Claude 製造雜亂記憶檔，可加：「always try to keep its content up-to-date, coherent and organized. You can rename or delete files that are no longer relevant. Do not create new files unless necessary.」
- 可限定主題：「Only write down information relevant to \<topic\> in your memory system.」

### 3.6 官方「多 session 軟體開發」記憶模式（S1）
針對跨多 session 的長專案，**記憶檔要刻意 bootstrap，而非邊做邊隨手寫**：
1. **Initializer session**：第一個 session 在實質工作前先建好記憶 artifact——progress log（做了什麼 / 下一步）、feature checklist（工作範圍）、startup / init script 的參照。
2. **後續 session**：開場先讀這些 artifact，幾秒內恢復完整專案狀態，不必重新探索 codebase。
3. **Session 結束前**：更新 progress log（完成了什麼 / 還剩什麼）。
- **關鍵原則**：一次只做一個 feature；只有**端到端驗證**通過才標記完成（不是寫完 code 就標完成），以保持 progress log 可信、防止 scope creep 跨 session 累積。（詳案例見 S6，本檔 §8）

---

## 4. Context Editing（beta `context-management-2025-06-27`）

> 用途：**主動策展 Claude 看到的東西**。S2 原文：「context 是有限資源、邊際報酬遞減，無關內容會降低模型專注度」。文檔同時提示「對多數情境，**伺服端 compaction 才是主要策略**；context editing 適合需要更細粒度控制的場景」。

### 4.1 兩個伺服端策略（S2）

**(a) Tool result clearing — `clear_tool_uses_20250919`**
- 對話超過門檻時，**按時間順序清除最舊的 tool result**，並以 placeholder 文字取代讓 Claude 知道被移除了。
- 預設只清 tool result；設 `clear_tool_inputs: true` 連 tool call 參數一起清。
- 設定選項（S2 表）：

  | 選項 | 預設 | 說明 |
  |---|---|---|
  | `trigger` | 100,000 input tokens | 超過此值開始清除；可用 `input_tokens` 或 `tool_uses` 計 |
  | `keep` | 3 tool uses | 清除後保留最近幾組 tool use/result（移除最舊的） |
  | `clear_at_least` | 無 | 每次至少清這麼多 token；達不到就不套用（用來判斷是否值得打破 prompt cache） |
  | `exclude_tools` | 無 | 永不清除的工具名清單 |
  | `clear_tool_inputs` | `false` | 是否連 tool call 參數一起清 |

**(b) Thinking block clearing — `clear_thinking_20251015`**
- 管理 extended thinking 的 `thinking` block。設定選項 `keep`：`{type:"thinking_turns", value:N}`（N>0，保留最近 N 個帶 thinking 的 assistant turn）或 `"all"`。
- **預設因模型而異**（S2 表）：
  - Opus 4.5+ / Sonnet 4.6+：保留**所有** prior thinking。
  - 更早的 Opus/Sonnet、以及所有 Haiku（至 Haiku 4.5）：只保留**最後一個** turn 的 thinking。
  - 跨多模型層執行時，建議**明確設 `keep`** 而非依賴 per-model 預設。

### 4.2 組合與快取（S2）
- **組合兩策略時，`clear_thinking_20251015` 必須排在 `edits` 陣列第一個**。
- **與 prompt caching 的互動**：
  - tool result clearing 清除時會**使快取前綴失效**→ 用 `clear_at_least` 確保每次清足夠 token，讓打破快取划算。
  - thinking 被**保留**時 prompt cache 維持（有 cache hit）；被**清除**時在清除點失效。
- **重要**：context editing 在**伺服端套用**，你的用戶端維持完整未修改的對話歷史，**不需同步**用戶端狀態。
- 回應的 `context_management.applied_edits` 會回報清了幾個 tool use / thinking turn、省了多少 input token。token counting endpoint 也支援預覽清除後 token 數。

### 4.3 用戶端 compaction（SDK）
S2 還列了第三種：**client-side compaction**，在 Python/TypeScript/Ruby SDK 的 `tool_runner` 可用，產生摘要取代完整對話歷史——但**官方明說伺服端 compaction（§5）通常更優先**。

---

## 5. Compaction（beta `compact-2026-01-12`，伺服端摘要）

> **這是「逼近 context window 上限時整段對話摘要」的伺服端機制**，與 Claude Code CLI 的 `/compact` 是不同層的東西（CLI 那套見 memory_official_guide §4.4）。

### 5.1 規格（S3）
- **beta header**：`anthropic-beta: compact-2026-01-12`，所有請求都要帶。
- **觸發流程**：偵測 input token 超過 `trigger`→生成摘要→建立 `compaction` block→以摘要續寫。**後續請求 API 自動丟掉 `compaction` block 之前的所有訊息**，從摘要往後接。
- 回傳時你**必須把 `compaction` block 帶回**以維持連續性。

### 5.2 設定參數（S3 表）

| 參數 | 預設 | 說明 |
|---|---|---|
| `type` | （必填） | 必為 `"compact_20260112"` |
| `trigger.value` | 150,000 | token 門檻，**最小 50,000** |
| `pause_after_compaction` | `false` | 摘要後是否暫停（回 `stop_reason:"compaction"`，讓你插入內容再續） |
| `instructions` | `null` | 自訂摘要 prompt——**會完全取代**預設 prompt，不是補充 |

- 預設摘要 prompt（S3 原文）重點：「為 transcript 寫摘要，目的是提供連續性，讓未來 context 中（原始歷史不可得、被此摘要取代）能繼續推進任務；寫下狀態、下一步、學到的事，並用 `<summary></summary>` 包起來。」
- **支援模型**（S3）：`claude-mythos-preview`、Opus 4.8 / 4.7 / 4.6、Sonnet 4.6。

### 5.3 已知坑（S3，與 memory tool 直接相關）
- **定義了 tools 時 compaction 可能失敗**：模型在摘要步驟可能去呼叫工具而非寫摘要，導致 `compaction` block 的 `content` 為 `null`。
- **解法**：在 `instructions` 明確禁止工具使用，例如「Do not call any tools while writing this summary; respond with text only.」
- 計費：compaction 多一次 sampling iteration，反映在 `usage.iterations`；**頂層 `input_tokens`/`output_tokens` 不含 compaction iteration**，要把 `iterations` 全部加總。
- prompt caching：在 `compaction` block 與 system prompt 上各設 `cache_control` breakpoint，compaction 只會讓摘要那段快取失效、不動 system prompt。

---

## 6. Managed Agents Memory（memory stores，beta `managed-agents-2026-04-01`）

> **這是「多 session / 多 agent 共享記憶」最完整的官方模式**——對應任務問題 5。與 memory tool（用戶端檔案）不同，**memory store 是 Anthropic 託管、workspace 範圍的文件集合**。

### 6.1 核心概念（S4）
- Managed Agents 每個 session **預設全新 context**，session 結束後狀態消失；memory store 讓 agent 跨 session 帶資訊（user preferences、專案慣例、過往錯誤、領域脈絡）。
- **memory store** = workspace 範圍的文字文件集合，附加到 session 時**掛載成 session sandbox 內的目錄**（`/mnt/memory/` 下），agent 用一般檔案工具讀寫；系統提示自動加上每個掛載點的描述告訴 agent 去哪找。需啟用 agent toolset。
- 每個 **memory** 由 path 定址，可透過 API/Console 直接讀寫（調校、匯入、匯出）。
- **每次變更建立一個不可變 memory version（`memver_...`）**→ 完整稽核軌跡 + point-in-time 還原。

### 6.2 容量上限（S4，數字照實）
- 單一 memory 上限 **100 kB（約 25k tokens）**。
- 單一 store 上限 **2,000 memories**。建議「many small focused files，而非少數大檔」。
- 單一 session 最多附加 **8 個 memory stores**。

### 6.3 API 操作（S4）
- store：`create`（name + description，description 會傳給 agent 告知存了什麼）/ `retrieve` / `update` / `list`（預設排除 archived，`include_archived:true` 含）/ `archive`（單向、變唯讀、不可附加到新 session）/ `delete`。
- memory：`create`（不覆寫）/ `retrieve` / `update`（可改 content / path（=rename）；支援 `content_sha256` **樂觀並行控制 precondition**，hash 不符就重讀重試）/ `list`（可 `path_prefix` + `depth` 像目錄瀏覽）/ `delete`。
- memory version：`list` / `retrieve` / **`redact`**（清掉歷史版本內容但保留稽核軌跡，用於移除外洩 secret / PII / 使用者刪除請求；current head 不能 redact，要先寫新版或刪除）。版本**保留 30 天**（近期版本永遠留），可透過 API 匯出延長保存。

### 6.4 附加到 session（S4）
- 在 `session.create` 的 `resources[]` 加 `{type:"memory_store", memory_store_id, access, instructions}`。**只能在 session 建立時附加，running session 不能加 / 移除**。
- `access` 預設 `read_write`，亦支援 `read_only`；**在檔案系統層強制**（read_only 掛載拒絕寫入）。
- `instructions`（≤4096 字元）給該 store 的 session 專屬用法指引。

### 6.5 ⭐ 多 session / 多 agent 共享模式（S4，對應任務問題 5）
- **shared reference material**：一個 **read-only** store 附加到很多 session（標準 / 慣例 / 領域知識），與各 session 自己的 read-write store 分開。
- **對應產品結構**：一個 store / 每位終端使用者、每團隊、或每專案，同時共用同一份 agent 設定。
- **不同生命週期**：某 store 可比任何單一 session 活得久，或單獨排程封存。
- 寫入會**持久化回 store，並在共享它的 session 之間保持同步**。

### 6.6 安全（S4，prompt injection 直球警告）
- `<Warning>`：memory store 預設 `read_write`。若 agent 處理**不可信輸入**（使用者 prompt、抓來的網頁、第三方工具輸出），**成功的 prompt injection 可能把惡意內容寫進 store，後續 session 把它當可信記憶讀回**。→ 參考資料 / 共享查詢 / agent 不需修改的 store，**一律用 `read_only`**。

### 6.7 容量管理最佳實踐（S4）
- store 達 2,000 上限時，**新 memory 寫入會失敗**（含 agent 對未映射 path 的檔案寫入），既有 memory 仍可讀可改。
- 建議：用**聚焦的小型 store**（每使用者一個、共享領域知識一個、專案脈絡一個）；填滿前**精簡或修剪**（`memories.delete`，或跑 **dreaming session** 把碎片整併到新輸出 store）；必要時附加新 store 並把舊的設 `read_only`；只給真正要寫的 session `read_write`。

---

## 7. Context Engineering：attention budget 與 just-in-time retrieval

來源 S5「Effective context engineering for AI agents」（對應任務問題 4）。

### 7.1 attention budget 與 context rot（S5）
- 核心命題：「隨著模型更強，挑戰不只是寫完美 prompt，而是**謹慎策展每一步進入模型有限 attention budget 的資訊**」；「good context engineering = 找出**最小、最高訊號密度的 token 集合**，最大化期望結果的可能性」。
- **context rot**：「context window 的 token 數增加時，模型從中**準確回憶資訊的能力下降**」。根源是 transformer 架構約束——n 個 token 需 n² pairwise relationship，注意力被攤薄。
- 推論：system prompt、tools、examples、message history、runtime data 全部**競爭同一有限資源**。

### 7.2 just-in-time vs 預載（S5，本專案 skill 機制的理論依據）
- 趨勢從**預先載入（upfront / pre-load）** 轉向 **just-in-time（即時）**：agent「維持輕量識別碼（檔案路徑、stored query、web link），用這些參照在 runtime 用工具動態載入資料進 context」。
- 類比人類認知：「不背整個資料集，而是用檔案系統、收件匣、書籤等外部組織與索引系統，**按需取回**」。
- **Skills 模式**正是這個的具體實現：每個 tool/capability 用簡短 YAML frontmatter 描述，模型先有高層概覽，需要時才用 `read_file` 把完整文件**即時拉進 context**。
- **hybrid（混合）**：上限先取關鍵資料、再由 agent 自行決定要不要進一步探索——兼顧速度與彈性。

### 7.3 長時程任務三技術（S5）
- **Compaction**：逼近上限時摘要對話歷史，蒸餾「最關鍵細節」、丟冗餘輸出，以最小性能損失續行。
- **Structured Note-Taking（結構化筆記 / 外部記憶）**：agent 用檔案維持持久外部記憶，「跨數十次 tool call 追蹤進度、維持否則會丟失的關鍵脈絡與依賴」。
- **Sub-Agent 架構**：專化 agent 處理聚焦任務、主 agent 綜合精簡摘要，達到「關注點分離」、把詳細探索隔離。

> 三者剛好對應 §5 compaction、§3 memory tool、本專案既有的 subagent/teams 派發機制。

---

## 8. 長時程 agent harness 的記憶模式（progress file / 假設中斷）

來源 S6「Effective harnesses for long-running agents」（S1 與 S5 都指向它做案例）。

- **兩階段架構**：(1) Initializer session（第一個 context window，建立基礎環境）；(2) 後續 Coding session（用結構化 artifact 漸進推進）。
- **Progress file（`claude-progress.txt`）**：session 之間的橋。關鍵洞見：「找到讓 agent 用全新 context window 開始時**快速理解工作狀態**的方法」——靠這份 log 搭配 git history。
- **Feature checklist（JSON）**：定義所有需求，每條含 `category` / `description` / `steps` / `passes:false`。用「**It is unacceptable to remove or edit tests**…」這類強措辭防止模型亂改；**JSON 格式比 Markdown 更能抵抗模型不當修改**。
- **Git-based recovery**：模型用 git 還原壞掉的變更、回到可運作狀態；描述性 commit 形成天然 checkpoint。
- **Assume Interruption（假設中斷）開場標準流程**：`pwd` 確認工作目錄→讀 git log 與 progress file→挑最高優先未完成 feature→跑 `init.sh` 啟動 dev server→跑基本端到端測試**再**動新工作。
- **一次一個 feature**：「只做一個 feature——這個漸進法是關鍵」，防止 agent 一個 session 想做完整個 app。
- **End-of-session**：以描述性訊息 commit 到 git，並把進度摘要寫進 progress file。

---

## 9. Claude Code 端：PreCompact / PostCompact / SessionStart(compact) hooks

來源 S9（官方 hooks reference）。對應任務問題 3——這是 CLI 端用 hook 在 compaction 邊界保存記憶的官方介面。

### 9.1 PreCompact（S9）
- **何時觸發**：context compaction **發生前**。matcher 區分：`manual`（使用者 `/compact`）/ `auto`（Claude Code 自動）。
- **輸入欄位**：`session_id`、`transcript_path`（JSONL 完整 transcript 路徑）、`cwd`、`hook_event_name:"PreCompact"`、`trigger`（`"manual"`/`"auto"`）。
- **可阻擋 compaction**：頂層 `decision:"block"` + `reason`（顯示給使用者）。省略 `decision` 則放行。
- → 典型用途：在壓縮前讀 `transcript_path` 把完整對話備份到外部（如 SQLite / 檔案）。

### 9.2 PostCompact（S9）
- **何時觸發**：compaction **完成後**。同樣支援 `manual` / `auto` matcher。
- 輸入欄位同 PreCompact（`hook_event_name:"PostCompact"`）。
- **無阻擋能力**：exit code 2 與任何非零碼只把 stderr 顯示給使用者；用於壓縮後的 side effect（logging / cleanup / 重新注入結構化脈絡）。

### 9.3 SessionStart 的 `compact` matcher（S9）
- session 在 compaction 後恢復時，**SessionStart hook 以特殊 matcher `compact` 觸發**，輸入帶 `source:"compact"`。
- 用途：壓縮後刷新脈絡。官方範例——一個載入近期 git commit 的 hook 可重跑提供最新資訊：

  ```json
  { "hooks": { "SessionStart": [ {
      "matcher": "compact",
      "hooks": [ { "type": "command", "command": "git log --oneline -10" } ]
  } ] } }
  ```

> 三者合起來＝「PreCompact 抓全量 → compaction → PostCompact / SessionStart(compact) 重新注入精選脈絡」的無損記憶管線。（社群實作如 mikeadolan 的 SQLite brain 採此模式；屬非官方範例，僅作概念佐證。）

---

## 10. agent 自我管理記憶的最佳實踐（該記 / 不該記 / 防腐 / 索引）

綜合 S8（cookbook）、S1、S4、memory_official_guide。

### 10.1 該記 vs 不該記（S8）
- **該記**：任務相關的**模式（pattern）**而非對話歷史；學到的架構模式（如併發 bug 修法）；團隊特定的 code quality 知識；領域 insight / 技巧。
- **不該記**：敏感資訊（密碼 / API key / PII）；**完整對話歷史**；不分青紅皂白全記；讓記憶無界成長。

### 10.2 組織與防腐（stale memory）
- **清晰目錄結構 + 描述性檔名**；**定期 review 並清理**（S8）。
- **索引模式**：→ 見 memory_official_guide §2.3——`MEMORY.md` 是「簡潔索引」、只它載入每個 session（前 200 行 / 25KB），詳細筆記移到主題檔按需讀。S8 對 API memory tool 的對應建議：「先用單一 `/memories/patterns.md` 起步」。
- **防腐手段**：rename / delete 不再相關的檔（S1 prompting）；定期清長期未存取檔（S1 安全段）；Managed Agents 用 **dreaming session** 把碎片整併、舊 store 設 read_only 或封存（S4）。
- **「只有端到端驗證通過才標完成」**（S1/S6）是防止 progress log 腐化的關鍵紀律。

### 10.3 記憶投毒 / prompt injection（S8、S4，跨來源一致的高優先警告）
- **記憶檔會被讀回 Claude 的 context，因此是 prompt injection 載體**。
- 緩解（S8）：(1) 寫入前內容消毒、過濾危險模式；(2) per-user/per-project **隔離 scope**；(3) 記錄並掃描所有 memory 操作；(4) prompt 指示 Claude **忽略記憶中的指令**。
- Managed Agents 對應招（S4）：不可信輸入路徑上的 store 一律 `read_only`。

### 10.4 兩層記憶心智模型（S8）
- **短期**＝對話 context + thinking → 自動清掉省空間（context editing）。
- **長期**＝`/memories` 裡存的模式 → 跨 session 持久。
- cookbook 比喻：「給 Claude 一本筆記本，像人類一樣記下、回頭翻」。

### 10.5 生產參數建議（S8）
- context editing trigger：**生產用 30–40k tokens**（demo 用 5k 以便頻繁觸發觀察）。
- thinking budget：每 turn 約 1,024 tokens（啟用 `clear_thinking` 時）。
- 組合 strategy 時 `clear_thinking` 必須排第一。

---

## 11. 多 session / 多 agent 共享記憶的官方模式

對應任務問題 5，分三條官方路徑：

1. **Managed Agents memory stores（最正式，S4）**：workspace 範圍、可被多 session 附加、寫入跨 session 同步、read-only 共享參考 + per-user/team/project 的 read-write store、單向 archive、不可變版本稽核。詳 §6。
2. **API memory tool（S1）**：記憶後端由你掌控，因此「共享」靠你把多個 client session 指向**同一儲存後端**（檔案系統 / DB）來達成；官方建議 **per-project 隔離防交叉污染**（S8）。
3. **Claude Code auto-memory（→ 見 memory_official_guide §2.2）**：`<project>` 路徑源自 git repo，**同一 repo 的所有 worktree 與子目錄共享同一記憶目錄**；但**機器本地、不跨機器/雲端**。CLAUDE.md 跨機器共享靠版控；個人指令跨 worktree 共享靠從 `~/.claude/` import（→ 見 memory_official_guide §1.5）。

> 小結：要**跨機器 / 多 agent 雲端共享** → Managed Agents memory stores 或自管 memory tool 後端；**單機 / 同 repo 多 worktree** → Claude Code auto-memory 已自動共享。

---

## 12. 與 Claude Code auto-memory 的差異對照

| 維度 | Claude Code auto-memory | API memory tool（`memory_20250818`） | Managed Agents memory store |
|---|---|---|---|
| 層級 | CLI 內建 | 你的 API 應用 | Managed Agents 平台 |
| 誰執行檔案操作 | CLI（機器本地） | **你的用戶端** | Anthropic 託管 sandbox 掛載 |
| 儲存位置 | `~/.claude/projects/<project>/memory/`（→ 見 memory_official_guide §2.2） | 你決定（檔案/DB/雲端/加密） | workspace 範圍 memory store |
| 自動寫入？ | **是**（Claude 自己判斷要不要存） | 由模型在對話中用 tool 寫 | 由 agent 用檔案工具寫 |
| 載入觸發 | session 開始自動載 `MEMORY.md` 前 200 行/25KB | 模型「task 前先 view /memories」 | 掛載成目錄 + 系統提示加掛載描述 |
| 跨機器共享 | 否（機器本地） | 看你的後端 | 是（平台託管） |
| 版本稽核 | 無（純 markdown 檔，可手動 git） | 看你的後端 | **內建不可變 version + redact** |
| 啟用旗標 | `autoMemoryEnabled` / `CLAUDE_CODE_DISABLE_AUTO_MEMORY`（v2.1.59+） | tools 加 `memory_20250818` | session `resources[]` 加 `memory_store` |

> 三者**不互斥**：Claude Code 用戶在 CLI 用 auto-memory；自建 API agent 用 memory tool + context editing + compaction；雲端託管多租戶 agent 用 memory stores。

---

## 13. 本專案（Project_01）可借鏡的點

僅列「概念上可借鏡」，非建議立刻改動（依使用者 step-by-step pace，不預做設計推測）：

- **just-in-time retrieval 理論已是本專案 skill 機制的官方背書**（S5 §7.2）：`project-01-workflow` skill 的「用到才載 reference」、`code_map.md` 逐層下沉索引，正是 attention budget + JIT 的實踐。本檔可作為該設計的理論引用來源。
- **「假設中斷 + progress file」模式**（§3.6、§8）與本專案既有的 `pineedtodo`（Pi 待辦）/ SDD 流程同源——若未來要做長時程 agent 自走，可對齊 initializer/progress/feature-checklist 三件套。
- **SessionStart(compact) / PreCompact hook**（§9）與本專案既有 SessionStart 快照、Stop pytest 守等 hook 同一機制層；若擔心 `/compact` 後脈絡流失，PreCompact 備份 transcript 是官方介面（本檔僅記錄，未改 settings）。
- **記憶投毒警告**（§10.3）對「規則匹配點餐機器人」這種會吃**使用者輸入**的系統值得留意：若未來把對話寫入任何記憶/日誌再讀回，需做輸入消毒。

---

## 14. 來源表（完整 URL + 抓取日期）

| # | 標題 | URL | 抓取日 | 版權 |
|---|---|---|---|---|
| S1 | Memory tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool | 2026-06-04 | Anthropic |
| S2 | Context editing | https://platform.claude.com/docs/en/build-with-claude/context-editing | 2026-06-04 | Anthropic |
| S3 | Compaction | https://platform.claude.com/docs/en/build-with-claude/compaction | 2026-06-04 | Anthropic |
| S4 | Using agent memory（Managed Agents） | https://platform.claude.com/docs/en/managed-agents/memory | 2026-06-04 | Anthropic |
| S5 | Effective context engineering for AI agents | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2026-06-04 | Anthropic |
| S6 | Effective harnesses for long-running agents | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | 2026-06-04 | Anthropic |
| S7 | Managing context on the Claude Developer Platform | https://claude.com/blog/context-management | 2026-06-04 | Anthropic |
| S8 | Memory & context management cookbook（Sonnet 4.6） | https://platform.claude.com/cookbook/tool-use-memory-cookbook ／ https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/memory_cookbook.ipynb | 2026-06-04 | Anthropic |
| S9 | Hooks reference | https://code.claude.com/docs/en/hooks | 2026-06-04 | Anthropic |

> 數字事實（84% / 39% / 29% / 100-turn、100kB / 2000 / 8 stores、150k/50k token、200行/25KB 等）皆引自上述官方頁面；無法在官方來源證實的數字未寫入本檔。社群部落格（如 PreCompact SQLite 實作）僅在 §9 末作概念佐證、明確標示為非官方。
