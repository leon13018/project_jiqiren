# Claude Code Hooks & 自動化最佳實踐 — 調研筆記（毫無保留版）

> 日期：2026-06-03 ｜ 觸發：使用者要求調研 claude.com/blog 等 hooks/自動化最佳實踐文章，完整統整。
> 用途：(1) 寫 Stop-hook Pi-sync（見 `resources/specs/pi_sync_stop_hook_2026-06-03_spec.md`）的依據；(2) 補強 `.claude/hooks/NOTES.md` 的官方對照。
> 風格：官方規格逐條記錄 + **對本專案的對照**（→ 標記）。權威來源以官方 docs 為準，blog 為輔。

## 0. 來源清單

| # | 標題 | URL | 性質 |
|---|---|---|---|
| S1 | Automate actions with hooks（hooks-guide） | code.claude.com/docs/en/hooks-guide | **官方 docs，最權威** |
| S2 | Hooks reference | code.claude.com/docs/en/hooks | 官方 docs（完整 schema） |
| S3 | How to configure hooks（power user customization） | claude.com/blog/how-to-configure-hooks | 官方 blog |
| S4 | How Claude Code works in large codebases | claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start | 官方 blog（最佳實踐） |
| S5 | Introducing routines in Claude Code | claude.com/blog/introducing-routines-in-claude-code | 官方 blog（自動化） |
| S6 | A harness for every task: dynamic workflows | claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code | 官方 blog（編排） |
| S7 | Claude Code power user tips | support.claude.com/en/articles/14554000 | 官方 help center |

---

## 1. Hooks 是什麼 / 核心哲學

**定義**（S1）：Hooks 是在 Claude Code 生命週期特定時點自動執行的 user-defined shell 指令，提供對行為的**確定性控制**——確保某些動作**一定發生**，而非依賴 LLM「選擇」去跑。

**兩種價值定位**（S4，重要心法）：
1. **防禦性**（多數人只想到這層）：擋 Claude 做錯事。
2. **持續改進**（S4 強調「更有價值」）：
   > "Most teams think of hooks as scripts that prevent Claude from doing something wrong, but their more valuable use is continuous improvement."
   - 例：Stop hook 在 session 結束時、context 還新鮮時，反思本輪發生什麼、自動提議更新 CLAUDE.md。

**確定性 vs 依賴 LLM**（S4，與本專案直接相關）：
> "For automated checks like linting and formatting, hooks enforce the rules deterministically and produce more consistent results than relying on Claude to remember an instruction."

→ **本專案對照**：這正是我們把「Pi sync 從『agent 記得手動跑』改成 Stop hook 確定性觸發」的官方依據。把行為從 prompt/記憶層移到 hook 層 = 移除 context 負擔 + 消除「偶爾忘記」的可能。

**何時用 hook vs instruction vs prompt/agent hook**：
- 確定性、可重複 → `command` hook。
- 需要判斷 → `prompt` hook（單輪 LLM）或 `agent` hook（多輪 + 工具，可驗證實際狀態）。
- 純 context/慣例 → CLAUDE.md。

---

## 2. 完整 Hook 事件清單（官方 S1 表，2026-06）

> 官方文檔現列 **25+ 事件**（比本專案 NOTES §3 抓的當時版本更多）。完整：

| 事件 | 何時 fire | 支援 matcher | 能 block(exit2) |
|---|---|---|---|
| `SessionStart` | session 開始/resume | source（startup/resume/clear/compact） | ❌（顯 stderr 續跑） |
| `Setup` | `--init-only` / `-p --init`/`--maintenance` | init/maintenance | ❌ |
| `UserPromptSubmit` | 送出 prompt 前 | ❌ | ✅（reject prompt） |
| `UserPromptExpansion` | command 展開成 prompt 前 | command 名 | ✅（block 展開） |
| `PreToolUse` | tool 執行前 | tool 名 | ✅（block tool） |
| `PermissionRequest` | 權限對話出現時 | tool 名 | （decision.behavior）⚠️ `-p` 模式不 fire |
| `PermissionDenied` | auto 分類器 deny 後 | tool 名 | `{retry:true}` 可叫 model 重試 |
| `PostToolUse` | tool **成功**後 | tool 名 | （decision:block） |
| `PostToolUseFailure` | tool **失敗**後 | tool 名 | |
| `PostToolBatch` | 一批並行 tool 全 resolve 後 | ❌ | |
| `Notification` | Claude 發通知時 | 通知類型 | ❌ |
| `MessageDisplay` | 顯示 assistant 訊息時 | ❌ | |
| `SubagentStart` | subagent 生成時 | agent_type | |
| `SubagentStop` | subagent 結束時 | agent_type | （decision:block） |
| `TaskCreated` | TaskCreate 建立 task 時 | ❌ | |
| `TaskCompleted` | task 標記完成時 | ❌ | |
| `Stop` | **Claude 回應結束時** | ❌ | ✅（prevent stop / continue） |
| `StopFailure` | turn 因 API error 結束 | error 類型 | output/exit 被忽略 |
| `TeammateIdle` | agent team teammate 將 idle | ❌ | |
| `InstructionsLoaded` | CLAUDE.md / `.claude/rules/*.md` 載入時 | load 原因 | |
| `ConfigChange` | 設定檔 session 中被改 | 設定來源 | ✅（exit2 / decision:block） |
| `CwdChanged` | 工作目錄變（如 `cd`） | ❌ | |
| `FileChanged` | 監看檔變動 | **檔名清單**（`\|` 分隔字面，非 regex） | |
| `WorktreeCreate` | 建 worktree 時（取代預設 git 行為） | | 任何非零都 abort |
| `WorktreeRemove` | 移除 worktree 時 | | |
| `PreCompact` | compaction 前 | manual/auto | |
| `PostCompact` | compaction 後 | manual/auto | |
| `Elicitation` | MCP server 請求 user input | MCP server 名 | |
| `ElicitationResult` | user 回應 MCP elicitation 後 | MCP server 名 | |
| `SessionEnd` | session 終止 | clear/resume/logout/… | |

**無 matcher 支援的事件**（寫了會被忽略，永遠 fire）：`UserPromptSubmit`, `PostToolBatch`, `Stop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `WorktreeCreate`, `WorktreeRemove`, `CwdChanged`, `MessageDisplay`。
→ **本專案對照**：我們的 Stop / SessionStart(全source) 正確未寫 matcher；新 stop-sync 同樣不寫。

---

## 3. Handler 類型（5 種，S1）

| type | 行為 | 預設 timeout |
|---|---|---|
| `command` | 跑 shell 指令（最常用） | **10 分鐘**（UserPromptSubmit 降 30s、MessageDisplay 降 10s） |
| `http` | POST event JSON 到 URL，回應 body 用同 JSON 格式控制 | 10 分鐘 |
| `mcp_tool` | 呼叫已連線 MCP server 的 tool | 10 分鐘 |
| `prompt` | 單輪 LLM 判斷（預設 Haiku，可 `model` 指定） | 30s |
| `agent` | 多輪 subagent + 工具驗證（**experimental**） | 60s，最多 50 tool turns |

**⚠️ 與本專案 NOTES 的 timeout 出入**：S3 blog 寫「60-second default timeout」，但官方 S1 doc 明寫 command hook 預設 **10 分鐘（600s）**。**官方 doc 為準** → NOTES §10.6 #4 寫的「默認 600s」是對的，blog 的 60s 過時/錯誤。
→ **本專案對照**：新 stop-sync 是 command hook，SSH sync ~3-10s 遠低於 600s，**不需設 timeout、不需 async**。

**prompt/agent Stop hook 範例**（S1，未來可參考）：
```json
{ "hooks": { "Stop": [ { "hooks": [
  { "type": "agent", "prompt": "Verify that all unit tests pass...", "timeout": 120 }
] } ] } }
```
→ **本專案對照**：現有 `stop-check-sales-pytest`（command + flag pattern）理論上可改寫成 agent hook（自己跑 pytest 判斷），但 flag pattern 更輕、無 LLM 成本，維持現狀。

---

## 4. 設定位置與優先序（S1）

| 位置 | 範圍 | 可分享 |
|---|---|---|
| `~/.claude/settings.json` | 所有專案 | 否（本機） |
| `.claude/settings.json` | 單一專案 | ✅ commit |
| `.claude/settings.local.json` | 單一專案 | 否（gitignored） |
| Managed policy settings | 組織級 | admin |
| Plugin `hooks/hooks.json` | plugin 啟用時 | ✅ |
| Skill/agent frontmatter | 該 skill/agent active 時 | ✅ |

- `disableAllHooks: true` 全關。
- `/hooks` menu **唯讀**，只能編 JSON 或叫 Claude 改。
- **熱重載**：直接編 settings 檔，file watcher 通常自動 pick up（幾秒內）；沒生效就重啟 session。
  → **本專案對照**：解答 NOTES §10「改 settings.json 是否需重啟（未驗證）」——**通常自動 reload，保險起見重啟**。

→ **本專案對照**：我們用 `.claude/settings.json`（project，commit），正確。

---

## 5. 輸入 / 輸出 / 決策

### 5.1 Input（stdin JSON）
共同欄位：`session_id`, `cwd`, `hook_event_name`, `transcript_path`, `permission_mode`。Tool 事件加 `tool_name` / `tool_input`。各事件加各自欄位（如 SessionStart 的 `source`，UserPromptSubmit 的 `prompt`）。

### 5.2 Exit codes（S1）
- **0**：無異議，動作正常進行。對 PreToolUse **不等於 approve**（仍走正常 permission flow）。對 `UserPromptSubmit`/`UserPromptExpansion`/`SessionStart`，**stdout 會注入 Claude context**。
- **2**：block。stderr 給 Claude 當 feedback。部分事件不能 block（SessionStart/Setup/Notification 等 → 顯 stderr 給 user 後續跑）。
- **其他**：動作續跑，transcript 顯 `<hook> hook error` + 第一行 stderr，完整進 debug log。

### 5.3 Structured JSON output（exit 0 + stdout JSON）
**⚠️ 不要混用**：exit 2 時 Claude Code **忽略 JSON**。要嘛 exit2+stderr，要嘛 exit0+JSON。
- PreToolUse：`hookSpecificOutput.permissionDecision` = `allow`/`deny`/`ask`/`defer`(僅 `-p`)。
- PostToolUse / Stop / SubagentStop：top-level `decision: "block"` + `reason`。
- PermissionRequest：`hookSpecificOutput.decision.behavior`。
- 通用：`continue`(false 全停), `stopReason`, `suppressOutput`, `systemMessage`, `additionalContext`(注入 context，限特定事件)。

**權限關係（重要）**：hook `allow` **不能** override settings 的 deny rule（deny 永遠優先）；hook 能收緊不能放寬。PreToolUse `deny` 在 `bypassPermissions` / `--dangerously-skip-permissions` 下**仍生效**（policy enforcement 不可繞）。

→ **本專案對照**：3 個 block hook 用 `permissionDecision:deny`+exit0（合法），未混用 exit2——正確（NOTES §10.6 #1/#2 已稽核）。

### 5.4 多 hook 同事件合併（S1，本專案沒用到但要知道）
- 同事件所有 matching hook **並行跑**，每個跑完才合併；相同指令自動去重。
- **一個 hook 的 deny 不會阻止 sibling hook 的 side effect**——別依賴某 hook deny 來抑制另一 hook。
- PreToolUse 合併取**最嚴**：deny > ask > allow。`additionalContext` 全部保留串接。
- 多個 PreToolUse 回 `updatedInput` 改同一 tool 參數 → **最後完成的贏，順序非確定**，避免多 hook 改同 input。

---

## 6. Matcher / `if` 進階過濾

- **Matcher** group 級，只比 tool 名：`Bash`、`Edit|Write`（pipe alternation）、`*`/空（全部）、`mcp__github__.*`（regex）。**大小寫敏感**（`bash`≠`Bash`）。
- **`if` 欄位**（v2.1.85+，僅 tool 事件）：用 **permission rule 語法**比 tool 名 + 參數，hook process 只在命中才 spawn：`"if": "Bash(git *)"`、`"Edit(*.ts)"`。複合指令 `npm test && git push` 會逐 subcommand 評估。
  → **本專案對照**：被移除的 auto-sync 是用 regex 自己比對 `git push origin main`；若未來要寫 Bash 過濾 hook，`if: "Bash(git push *)"` 比手寫 regex 乾淨（可免去 NOTES gotcha K/L 的 regex 寬嚴調校）。但**新 stop-sync 是 Stop 事件、不支援 `if`**，用不到。

### 6.1 官方直接背書「Stop hook 掃工作樹」模式（S1，**對本專案最關鍵的一條**）
> "Claude can also create or modify files by running shell commands through the Bash tool. If your hook must see every file change... add a **`Stop` hook that scans the working tree once per turn**. For per-call coverage instead, also match `Bash` and have your script list modified and untracked files with `git status --porcelain`."

→ **本專案對照**：這正是方案 A 的核心思路的**官方認證版本**。要可靠捕捉「任何方式造成的狀態變化（含透過 Bash git push）」，官方建議就是「Stop hook 每 turn 掃一次」。我們的 stop-sync 比對 `origin/main` 即是這個 pattern 的 sync 應用。**設計方向獲官方背書。**

---

## 7. Stop hook 深入（與本專案 stop-sync 直接相關）

1. **Fire 時機**（S1）："Stop hooks fire whenever Claude finishes responding, **not only at task completion**. They do not fire on user interrupts. API errors fire StopFailure instead."
   → **本專案對照**：每 turn 結束都 fire（利於自我修正）；但 **user 中斷（Ctrl-C）與 API error 不 fire** → 那個 turn 的 sync 會延到下個正常結束的 turn（自我修正吸收）。應補進 spec 邊界 case。

2. **可靠性跨 session 類型**（S2，已於 spec 階段確認）：Stop 在 headless/background 都可靠 fire（"When Claude finishes responding"）。非同步 PostToolUse 的非確定性（NOTES gotcha N）是該事件特有，Stop 不受影響。

3. **8 次 block cap + `stop_hook_active`**（S1，重要安全機制）：
   > "Claude Code overrides a Stop hook after it blocks **8 times in a row** without progress."
   - 會 block 的 Stop hook 要 parse input 的 `stop_hook_active`，true 就早退避免 deadlock；要更多輪用 `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`。
   → **本專案對照**：
     - **stop-sync**：用 exit0 無 decision（sync 是 side effect，從不 block）→ **完全不受 8-cap 影響**。應在 spec 註明「為何不 block」。
     - **既有 stop-check-sales-pytest**：用 `pending→reminded` 一次性 block，最多 block 1 次 → 遠低於 8，安全（NOTES §2 已設計）。可考慮額外讀 `stop_hook_active` 當第二道防線（非必要）。

4. **Prompt/agent 型 Stop hook**：`ok:false` → reason 餵回 Claude 繼續做。（本專案 command + flag 已足夠。）

---

## 8. 最佳實踐（S4 / S7）

### 8.1 確定性 enforcement > 依賴記憶
linting/formatting/sync 這類可重複行為，用 hook 比寫進 CLAUDE.md 靠 Claude 記得更一致。→ 本專案 sync 改 hook 的依據。

### 8.2 持續改進型 hook
Stop hook 反思 session、提議 CLAUDE.md 更新（context 還新鮮時）。
→ **本專案未來 idea**：可加一個「Stop 時若本輪有踩到新 gotcha → 提醒寫進 NOTES.md」的反思 hook（低優先，記著）。

### 8.3 Lean & layered CLAUDE.md（S4，本專案已實踐）
> "root file for the big picture, subdirectory files for local conventions. The root file should be pointers and critical gotchas only; everything else drifts into noise."
→ **本專案對照**：我們的 root CLAUDE.md（紅線+指標）+ 子層 code_map + skill reference 正是此架構，且每 3-6 個月該 review（S4：為舊 model 寫的限制會綁住新 model，例：「每次 refactor 拆成單檔」對舊 model 有用、對新 model 反而綁手）。

### 8.4 完整 harness 建構順序（S4）
1. CLAUDE.md（context 地基）→ 2. **Hooks**（自動化+改進）→ 3. Skills（on-demand 專長）→ 4. Plugins（分發）→ 5. LSP（符號級導航）→ 6. MCP（外部工具）。
每層建在前層上，過早投資後段是浪費。
→ **本專案對照**：我們在 1-3 層（CLAUDE.md + hooks + skill）已扎實，符合順序。

### 8.5 Scoping（S4）
per-subdirectory 跑 test/lint（非全套）；`.claudeignore` + `permissions.deny`；在子目錄而非 repo root 起 session（避免 timeout/context 浪費）。

### 8.6 Power-user 雜項（S7）
- 「Claude 做錯 → 立刻寫進 CLAUDE.md，結尾加『Update your CLAUDE.md so you don't make that mistake again』」。
- `settings.json` check 進 git 共享團隊設定。
- 重複 workflow → skill（`.claude/skills/<name>/SKILL.md`）。command 內嵌 Bash 預算 `git status` 省 model 呼叫。
- **驗證是第一鐵則**："If Claude can close the feedback loop on its own, it will iterate until the output is right"。→ 本專案 Iron Law（沒跑驗證不宣告完成）同源。
- plan mode（Shift+Tab）先規劃；「一個 Claude 寫 plan，另一個當 staff engineer review」。
- `/effort max` 給硬 debug。

### 8.7 安全（S1/S3）
- 直接編 hook 設定檔需在 `/hooks` review 才生效（防靜默注入惡意碼）。
- 驗證/淨化 stdin；shell 變數加引號 `"$VAR"`；script 用絕對路徑；別處理 `.env`/憑證；hook 以你的 user 權限跑＝等同直接 shell access。

---

## 9. 自動化（hook 之外，S5/S6/S7）

### 9.1 Routines（S5）— 排程/事件型雲端自動化
- 定義："A routine is a Claude Code automation you configure once — prompt, repo, connectors — and run on a schedule, from an API call, or in response to an event."
- 跑在 Claude Code web 基礎設施 → **免管 cron、免本機開機**。
- 三觸發：**Scheduled**（每晚 2am 拉 Linear top bug → 修 → 開 draft PR）／**API**（HTTP POST，接 alerting/deploy hook）／**Webhook**（GitHub，每個符合 filter 的 PR 開 session）。
- 用例：backlog triage、doc drift 掃描、deploy 後 smoke test、alert triage、跨語言 SDK port。
- 限制：需 Claude Code on web（Pro/Max/Team/Enterprise）；每日上限 Pro 5 / Max 15 / Team-Ent 25 routines。
→ **本專案對照**：Pi sync 是**本機 → Pi** 的即時同步，不適合雲端 routine（routine 跑在 Anthropic 雲，碰不到你的 Pi/本機）。Routine 的價值在未來「定時 PR/triage」類，非本案。對照本專案的 `/loop`（本機 recurring，≤3 天）與 `/schedule`（雲端 cron）認知一致。

### 9.2 Dynamic Workflows（S6）— 自寫多 agent harness
- Claude 即時寫 JS harness 編排 subagent（隔離 context window），確定性控制流、可中斷續跑。
- 對抗三失敗模式：agentic laziness（半成宣告完成）、self-preferential bias、goal drift。
- 模式：classify-and-act / fan-out-and-synthesize / adversarial verification / generate-and-filter / tournament / loop-until-done。
- 何時用：migration/refactor、deep research、驗證 workflow、大規模排序。**何時不用**：比預設 harness 耗 token，一般 coding 不值得（"does it really need more compute?"）。
→ **本專案對照**：sync hook 是單一確定性動作，不需 workflow。Workflow 適用本專案的「大型 refactor / 多檔掃描」類任務（已知，非本案）。

### 9.3 其他自動化原語（S7）
`/loop <interval> <cmd>`（本機 recurring，≤3 天）｜`/schedule`（雲端 cron，關機也跑）｜`/batch`（fan out worktree agents 做 migration）｜subagent `isolation: worktree` 並行。

---

## 10. Debug / 踩坑（S1，對照本專案 NOTES）

| 官方 gotcha | 說明 | 本專案狀態 |
|---|---|---|
| **JSON 被 shell profile echo 污染** | shell-form hook 跑 `sh -c`/Git Bash 可能 source profile，無條件 echo 會污染 JSON stdout → parse 失敗。修：profile 內 echo 包 `if [[ $- == *i* ]]` | ✅ 我們每個 hook `-NoProfile`，免疫（NOTES §10.6 #3） |
| **Hook 不 fire** | `/hooks` 確認；matcher 大小寫；事件選對；`-p` 模式 PermissionRequest 不 fire 改 PreToolUse | ✅ |
| **Hook error in output** | 非零 exit；用 `echo '{...}' \| ./hook.sh; echo $?` 手測；絕對路徑/`${CLAUDE_PROJECT_DIR}`；`jq` 沒裝；script 沒 +x | → 我們本地手測法一致（NOTES §10） |
| **exec form 免 shell quoting** | 加 `"args": []` 直接 spawn script，免 shell 解析 | → 我們 PS 用 `args:["-File",...]` |
| **`/hooks` 沒顯示** | file watcher 漏 → 重啟；JSON 不能有 trailing comma/註解；位置對不對 | |
| **Stop hook 撞 8-block cap** | 見 §7.3 | ✅ stop-sync 不 block；stop-check 最多 1 次 |
| **timeout** | command 預設 10 分鐘 | ✅ sync ~3-10s 充足 |

**官方參考實作**：bash command validator example — github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py

**Debug 技巧**：`Ctrl+O` transcript 看每個 hook 一行摘要；`claude --debug-file /tmp/claude.log` + `tail -f` 看完整（含 matched/exit/stdout/stderr）；mid-session `/debug` 開。

---

## 11. 對 Pi-sync spec 的具體影響（→ §12 spec 檢視用）

**驗證設計正確的發現**：
- Stop hook「每 turn 掃工作樹」是**官方明文推薦**的可靠捕捉模式（§6.1）→ 方案 A 方向正確。
- exit0 無 decision → 不受 8-block cap（§7.3）。
- `-NoProfile` 免疫 JSON 污染（§10）。
- command hook 預設 600s timeout，sync 同步跑無虞，不需 async（§3）。

**可補強 spec 的點**（非結構性，硬化）：
1. 邊界 case 補：Stop 不 fire 於 **user 中斷 / API error(StopFailure)** → 該 turn sync 延後，自我修正吸收（§7.1）。
2. spec §2 明記「為何用 exit0 無 decision 而非 block」＝避免 8-block cap、sync 是 side effect（§7.3）。
3. 驗證計畫補：`/hooks` 確認 stop-sync 註冊；改完 settings 重啟 session 保險（§4）。
4. timeout：確認不設 `timeout`、不設 `async`（同步才能可靠寫 marker）（§3）。

**未來 idea（記著，非本案）**：
- 反思型 Stop hook 提議 NOTES/CLAUDE.md 更新（§8.2）。
- 若日後新增 Bash 過濾 hook，用 `if: "Bash(...)"` 取代手寫 regex（§6，免 gotcha K/L 調校）。
