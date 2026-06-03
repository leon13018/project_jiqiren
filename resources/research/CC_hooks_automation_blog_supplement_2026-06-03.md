# Claude Code Hooks & 自動化 — claude.com/blog 補充調研

> 日期：2026-06-03 ｜ 觸發：使用者要求再上 claude.com/blog 調研多份 hook / 自動化最佳實踐。
> 定位：**補充**，非取代 — hooks 機制／事件清單／exit code／Stop hook 深入已在 `CC_hooks_automation_best_practices_2026-06-03.md`（下稱「主筆記」）窮盡。本檔只記**主筆記沒涵蓋的新來源與新角度**，重疊處一律指回主筆記、不重述。
> 風格：信號密度優先，不抄預設行為。

## 0. 新發現來源（主筆記 S1–S7 之外）

| # | 標題 | URL | 對本檔貢獻 |
|---|---|---|---|
| B1 | How to configure hooks（blog） | claude.com/blog/how-to-configure-hooks | 主筆記列為 S3 但偏 schema；本檔補其「實作建議 / env 變數 / debug」段 |
| B2 | How Anthropic teams use Claude Code | claude.com/blog/how-anthropic-teams-use-claude-code | **全新** — 真實團隊自動化案例 |
| B3 | Best practices for Claude Opus 4.7 with Claude Code | claude.com/blog/best-practices-for-using-claude-opus-4-7-with-claude-code | **全新** — effort / auto mode / hook 通知 |
| B4 | How and when to use subagents | claude.com/blog/subagents-in-claude-code | **全新** — 委派門檻 + 「先對話、後自動化」 |
| B5 | Customize Claude Code with plugins | claude.com/blog/claude-code-plugins | 未深讀（自動化分發層，主筆記 §8.4 harness 順序已定位） |
| B6 | Advanced Patterns（PDF, resources.anthropic.com） | Subagents/MCP/Scaling | 未深讀，列備查 |

---

## 1. B1 — configure-hooks blog 的「上手」角度（補主筆記 S3）

主筆記 S3 抓滿了 schema / 決策 / 權限關係。blog 另有**實作落地建議**，主筆記較少著墨：

- **Start small**：第一個 hook 選**有立即可見輸出**的——官方點名 **PostToolUse formatter（Prettier/Black/gofmt）** 是最佳起點。
- **可用 env 變數**：`CLAUDE_PROJECT_DIR`、`CLAUDE_CODE_REMOTE`、`CLAUDE_ENV_FILE`（後者 SessionStart）。
  → **本專案對照**：我們 hook 已用絕對路徑 + `-NoProfile`；`CLAUDE_PROJECT_DIR` 可取代寫死路徑，未來新 hook 可採用以利可攜。
- **Debug**：每個 hook 收到 `transcript_path`（JSONL）→ `tail -f <path> | jq` 看歷史；自訂邏輯可包 logging script 補 transcript 看不到的決策。
- ⚠️ **與官方 doc 的數字出入（再次確認）**：此 blog 仍寫「**8 hook types**」「default timeout **60s**」。主筆記已判定 **官方 doc 為準**：事件實為 25+、command hook 預設 **600s**。blog 的 8/60 是**簡化／過時**，引用以主筆記 §2/§3 為準。

---

## 2. B2 — Anthropic 團隊真實自動化案例（全新）

主筆記偏「機制與本專案對照」，缺真實 pattern。B2 補足：

- **CLAUDE.md 當 "first stop"**：新人把整個 codebase 餵 Claude，靠 CLAUDE.md 認出相關檔、解釋 pipeline 依賴，**免人工建 catalog**。→ 印證本專案 lean&layered CLAUDE.md + code_map 方向。
- **Sub-agent 架構**：Growth 團隊用 2 個專職 subagent 處理 CSV → 找出爛廣告 + 生成變體，「分鐘級產出數百則」。
- **自主迴圈**：Product Design 讓 Claude「寫 feature → 跑測試 → 持續迭代」，人只給抽象問題 + 審結果（極端例：Claude 替自己寫 Vim keybinding，幾乎無人介入）。
- **GitHub Actions 整合**：PR 留言自動化，Claude 自動處理 formatting / test refactor。
- **核心心法**：最成功的團隊把 Claude 當 **thought partner 而非 code generator**，聚焦「能增益的人類 workflow」，而非純產碼。

> **本專案對照**：B2 的雲端 / GitHub Actions 自動化碰不到本機 Pi（同主筆記 §9.1 對 routine 的判斷）。可借鑒的是「自主迴圈 + 審結果」與「CLAUDE.md 當入口」——本專案已用 SDD reviewer + 巢狀 code_map 達到同效。

---

## 3. B3 — Opus 4.7 best practices（全新；偏 workflow 配置）

- **hook 型通知**：「叫 Claude 在任務完成時播音效，它能自建 hook-based notification」——長任務 hands-off 監看。→ 本專案未用，記為低優先 idea（Pi sync 完成可選配音效提示，非必要）。
- **effort 預設 `xhigh`**（介於 high 與 max 的新階）：平衡推理深度與 token，硬 debug 才升 `max`。
- **adaptive thinking**：不支援固定 thinking budget，模型自決何時深想。
- **任務結構**：首回合就給齊 intent / 約束 / 驗收標準 / 檔案位置（別擠牙膏式逐步揭露）；**減少 user turn** 降 reasoning overhead。
- **工具使用**：4.7 用工具更節制 → 若要它積極搜檔／讀檔，**明講何時與為何**用工具；不會無故 spawn subagent。

> 註：本專案模型為 Opus 4.8，effort 階層細節以當前 `/effort` 實況為準；B3 的「首回合給齊脈絡 + 明確驗收標準」與本專案 SDD spec/Iron Law 同源。

---

## 4. B4 — subagents：委派門檻 + 自動化升級路徑（全新）

**何時派**：研究需讀數十檔 ｜ 多個獨立任務並行 ｜ 要無偏見 fresh review ｜ commit 前獨立驗證（防 overfit 測試 / 漏 edge case）｜ pipeline 階段（design→implement→test）。

**何時不派**：有順序依賴的工作 ｜ 同檔並行編輯 ｜ 小快任務 ｜ 多 agent 需互相協調。

**context 隔離**：subagent 各自 context window，不背對話歷史 → 省 token、回應不被拖慢；可給不同權限（研究 agent read-only、實作 agent 可編輯）。

**自動化升級路徑（5 階）**：對話請求 → `.claude/agents/` 自訂 specialist → CLAUDE.md 訂委派政策 → skill 包多步 workflow → **hook 在特定生命週期點自動觸發 subagent**。

> **核心原則：「Start conversational, automate later」** — 先自然請求，pattern 浮現再建自動化。
> **本專案對照**：完全印證現行做法 — sales-coder 是 `.claude/agents/` specialist、dispatch.md 是委派政策、SubagentStart hook 注入規範。「何時不派（同檔並行、小任務）」對應本專案「≤3 行純值替換主 agent 自 patch」門檻。

---

## 5. 對本專案的淨增益（去重後）

1. **新 hook 一律用 `CLAUDE_PROJECT_DIR`** 取代寫死路徑（B1，可攜性）。
2. 真實案例（B2/B4）**印證**本專案 lean CLAUDE.md + subagent + hook 觸發架構方向正確，無結構性調整需求。
3. 低優先 idea（記著，非本案）：
   - Pi sync / 長任務完成的 **hook-based 音效通知**（B3）。
   - 反思型 Stop hook 提議 NOTES/CLAUDE.md 更新（主筆記 §8.2 已記）。
4. **數字權威性再確認**：事件數 25+、command timeout 600s 以官方 doc 為準；blog 的 8 types / 60s 不採用（B1）。

> 機制細節、Stop hook 8-block cap、exit code、Pi-sync spec 影響 → 一律回主筆記 `CC_hooks_automation_best_practices_2026-06-03.md`。
