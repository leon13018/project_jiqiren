# memory 健檢 + 整併迴圈 — Spec（2026-06-06）

## 目標

為 auto-memory 目錄（`~/.claude/projects/<專案slug>/memory/`）建立手動觸發的維護迴圈：**確定性健檢（script）→ agent 整併判斷 → 對話內人定奪 → 帳本記錄**。解決「記憶腐化無人察覺」問題（system prompt 自身警告：recalled memory 指名的檔案/flag 可能已不存在）。

理論依據：`resources/research/agent_memory_management_research_2026-06-04.md` §10.2（防腐）、§6.7（整併）。官方 marketplace 零覆蓋（`claude-md-management` 只管 CLAUDE.md，不碰 auto-memory）——已查證不重複造輪。

## 設計決策（brainstorm 定案）

| 決策點 | 定案 |
|---|---|
| 主標的 | 健檢 + 整併完整迴圈 |
| 觸發 | 手動（使用者喊「memory 健檢」才跑）；零背景成本 |
| 承載 | PS 健檢 script + skill reference 流程（主 agent inline 執行整併判斷）；不用 workflow——僅 6 個小檔，碼化判準的 fan-out-able 不成立，且 workflow 腳本無法讀檔 |
| 提議落點 | 對話內人定奪 + **獨立帳本檔**記錄（不混 proposals.md） |

## 元件

### 1. `​.claude/skills/project-01-workflow/scripts/memory-health.ps1`（新）

確定性健檢，**只報告、絕不改檔**（沿用反思 hook「絕不自動寫入」原則）。

| # | 檢查 | 等級 |
|---|---|---|
| 1 | MEMORY.md 存在；≤200 行 / ≤25KB（超過=error，達 80%=warn——超出部分 session 載不到） | ❌/⚠️ |
| 2 | 索引→檔：MEMORY.md 每條 `[Title](file.md)` 指向的檔存在 | ❌ |
| 3 | 檔→索引：memory 目錄每個 .md（除 MEMORY.md）在索引有對應行 | ❌ |
| 4 | frontmatter：有 `name:` / `description:` / `metadata.type ∈ {user, feedback, project, reference}`；name 與檔名一致（`-`/`_` 視為等價——實測現有檔 name 用 kebab、檔名用底線） | ❌（name/檔名不一致僅 ⚠️） |
| 5 | `[[wiki-link]]` 可解析到既有記憶 name 或檔名 | ⚠️（規格允許先掛後補） |
| 6 | 記憶內文反引號包住的 repo 檔案引用仍存在（啟發式：有常見副檔名、排除 URL/含空白/萬用字元/`<`佔位符/`@`/`:` 主機與絕對路徑；純檔名 repo 內遞迴找）。防呆不防騙，誤報可接受 | ⚠️ |

- 介面：`-MemoryDir <path>` 參數覆寫；預設由 cwd 推導 slug（非英數→`-`，已實測吻合 `C--Users-LIN-HONG-Desktop-Project-01`）。**worktree 內 cwd 推導會錯**——測試與 worktree 內執行一律顯式給 `-MemoryDir`。
- 輸出：繁中人類可讀報告；exit 0=全綠 / 1=僅警告 / 2=有錯誤。
- UTF-8 with BOM（專案 .ps1 慣例）。

### 2. `​.claude/skills/project-01-workflow/reference/memory-management.md`（新）

🎯 標頭 + 六步流程：跑 script → 機械修復（呈報後直接修）→ 讀帳本疫苗（rejected 不重提）→ 整併四問 → 對話內人定奪（Why+diff 格式，借官方 `/revise-claude-md` 呈現法）→ 記帳。

整併四問（對每條記憶）：
1. **還真嗎**——指名的檔案/行為/flag 要實際驗證，不憑記憶宣稱
2. **該升層嗎**——選層判準 hook > root CLAUDE.md > skill reference > NOTES > memory；memory 該只剩「使用者個人特質/授權/節奏」這類無處可歸的事實
3. **重複/可合併嗎**
4. **該刪嗎**——已失效或已被其他層覆蓋

邊界：升層落實後原 memory 條目刪除或改 pointer（不留雙權威）；記憶不得含敏感資訊。

### 3. SKILL.md 路由表加一行

`| memory 健檢 / 記憶整併 / 記憶維護 | memory-management.md |`

### 4. `resources/reflections/memory_ledger.md`（新帳本）

格式沿 proposals.md 慣例：`## 日期 slug｜類型(升層/合併/刪除/修正)` + status + 落實行；rejected 留作疫苗。**reflections/ 整目錄已 gitignored** → 免 commit、免改 .gitignore。與 proposals.md 分檔理由：來源不同（手動健檢 vs 反思 hook）、生命週期不同。

## 驗收

1. **基線**：script 對現有 6 檔跑出報告（預期全綠或抓到真問題；name/檔名 `-`/`_` 等價後不得誤報）
2. **壞型注入**：temp fixture（`-MemoryDir` 指過去）注入孤兒檔、死索引連結、壞 frontmatter、缺 type、死路徑引用、死 wiki-link、超門檻 MEMORY.md → 各自被抓到、error/warn 分級正確、exit code 正確
3. **e2e**：對真實 memory 跑完整整併迴圈一輪，產出真提議 → 使用者定奪 → 帳本落地

## 流程約束

- script + reference + SKILL.md 在 `.claude/` → **worktree 5 階段**；帳本在 `resources/`（gitignored）→ 直接建
- 寫碼前 invoke karpathy-guidelines（每輪實作）
- script 對真實 memory 目錄只做讀取操作，開發期即可安全實測
