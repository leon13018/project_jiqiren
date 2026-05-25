# Claude Code Hooks — 完整研究筆記（毫無保留版）

> 本檔記錄 hooks 系統的所有調研發現、設計決策、踩坑歷史、未實作但有用的功能。
> 後續討論 / 維護 / 擴展 hooks 都應該先看這檔。
>
> **最後更新：2026-05-25**（Stop + SessionStart hooks 上線）

---

## 0. 來歷 / 為何有這檔

使用者要求把可條件觸發 / 重複性 workflow 自動化掉，省 CLAUDE.md 內容 + 主 agent 記憶壓力。

**調研流程（3 輪）：**
1. **第 1 輪**（claude-code-guide subagent + 主 agent WebFetch）：盤點 hooks / slash command / loop / cron / skill 整體能力 → 列 inventory 評估能套到哪
2. **第 2 輪**（claude-code-guide + WebFetch + 第三輪驗證）：精準驗證 hook input/output schema、PowerShell 兼容性 → 寫 3 個 hooks（block-git-add-bulk / block-vendor-edit / auto-sync-pi）
3. **第 3 輪**（claude-code-guide + WebFetch + 第三輪驗證）：精準驗證 Stop / SessionStart 規格 → 寫 4 個新 scripts（state-mark / state-clear / stop-check / session-start-context）

**寧多勿少派 subagent + 親自 WebFetch cross-check** — 主 agent 訓練資料未必包含最新 Claude Code 規格，subagent 偶爾推測 / hallucinate，必須交叉驗證。

---

## 1. 當前已實作的 hooks 一覽

| 檔名 | 事件 | matcher | 用途 | 風險 |
|---|---|---|---|---|
| `block-git-add-bulk.ps1` | PreToolUse | Bash | 擋 `git add -A` / `--all` / `.` | 低（命中精準）|
| `block-vendor-edit.ps1` | PreToolUse | Edit\|Write | 擋廠商 SDK 檔（ActionGroupControl/Board.py）| 低 |
| `auto-sync-pi.ps1` | PostToolUse (async, 120s) | Bash | `git push origin main` 後自動跑 sync_pi.ps1 | 中（log 偶寫 ERROR 但功能正常，見 §6）|
| `state-mark-sales-dirty.ps1` | PostToolUse | Edit\|Write | 編 sales/* 時寫 flag | 低 |
| `state-clear-on-pytest.ps1` | PostToolUse | Bash | pytest 跑過清 flag | 低 |
| `stop-check-sales-pytest.ps1` | Stop | (無 matcher) | 結束 turn 前若 flag pending → block 一次 | 中（block 體驗略生硬）|
| `session-start-context.ps1` | SessionStart | (無 matcher, 全 source) | 注入 branch/status/test count 到 Claude context | 低 |
| `subagent-inject-rules.ps1` | SubagentStart | (無 matcher) | 自動注入標準規範到 subagent context，依 agent_type 分流（編碼類完整 / 研究類精簡）| 低 |

**對應 settings.json 結構：**
```
PreToolUse:
  Bash → block-git-add-bulk
  Edit|Write → block-vendor-edit
PostToolUse:
  Bash → [auto-sync-pi (async), state-clear-on-pytest]
  Edit|Write → state-mark-sales-dirty
Stop:
  → stop-check-sales-pytest
SessionStart:
  → session-start-context
SubagentStart:
  → subagent-inject-rules
```

---

## 2. 三方協作架構（flag file pattern）

**問題：** Stop hook 輸入 JSON 沒有本輪 tool 歷史（官方確認，無 `tool_history` / `tools_used` field），無法直接判斷「本輪有沒有編 sales/*」。

**解法：** flag file 三方協作。

```
                  [Edit sales/*]
                        ↓
            state-mark-sales-dirty.ps1
                        ↓
            sales-dirty.flag = pending
                        |
                        ↓
       ╔════════ 三條路徑 ════════╗
       ║                          ║
   [pytest 跑]                [Stop 觸發]
       ↓                          ↓
state-clear-on-pytest    stop-check-sales-pytest
       ↓                          ↓
   flag 刪除               flag=pending → block + 改 reminded
                          flag=reminded → silent
                          flag 不存在   → silent
```

**關鍵設計決策：**
- **block 只一次**（pending → reminded 轉換）：避免無限循環（若 Claude 真的不能/不想跑 pytest，e.g. 純 docstring 修改）
- **下次編 sales/* 自動 reset 回 pending**：再編就再次提醒（合理）
- **任何 pytest 跑（PASS or FAIL）都清 flag**：Claude 自行從 pytest output 判斷後續

---

## 3. 官方 hook 事件完整清單（30+ 個）

從 docs.claude.com / code.claude.com 抓取（2026-05-25）：

### Per-session events（一次性）
- `SessionStart` ⭐ **已用**
- `SessionEnd`
- `Setup`

### Per-turn events
- `UserPromptSubmit`
- `UserPromptExpansion`
- `Stop` ⭐ **已用**
- `StopFailure`
- `TeammateIdle`

### Agentic loop events
- `PreToolUse` ⭐ **已用**
- `PermissionRequest`
- `PermissionDenied`
- `PostToolUse` ⭐ **已用**
- `PostToolUseFailure`
- `PostToolBatch`
- `Elicitation`
- `ElicitationResult`

### Async events
- `Notification`
- `SubagentStart` ⭐ **可用未用** — 派 subagent 時 fire，可 additionalContext
- `SubagentStop` ⭐ **可用未用** — subagent 結束 fire（Stop 在 subagent 內自動轉成這個）
- `TaskCreated`
- `TaskCompleted`
- `ConfigChange`
- `CwdChanged`
- `FileChanged` ⭐ **可用未用** — 配 `watchPaths` 用，外部檔變動觸發
- `WorktreeCreate`
- `WorktreeRemove`
- `PreCompact`
- `PostCompact`
- `InstructionsLoaded`

---

## 4. Hook 配置 JSON schema 速查

### settings.json 結構
```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "<regex or source>",
        "hooks": [
          {
            "type": "command|http|mcp_tool|prompt|agent",
            "command": "powershell" | "bash" | "./script.sh",
            "args": ["-File", "..."],
            "timeout": 600,
            "async": false,
            "shell": "bash" | "powershell",
            "if": "Bash(rm *)",
            "statusMessage": "Running...",
            "once": false
          }
        ]
      }
    ]
  }
}
```

### 設定檔優先序
1. `~/.claude/settings.json`（user global）
2. `.claude/settings.json`（project，commit 上去）— ⭐ **本專案用這個**
3. `.claude/settings.local.json`（local，gitignored）

後者覆蓋前者。

### Stdin JSON Common Fields
```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/.jsonl",
  "cwd": "/working/dir",
  "permission_mode": "default|plan|acceptEdits|bypassPermissions|...",
  "hook_event_name": "PreToolUse|PostToolUse|Stop|SessionStart|...",
  "effort": { "level": "low|medium|high|xhigh|max" },
  "agent_id": "...",      // subagent context only
  "agent_type": "..."     // subagent or --agent flag
}
```

### Tool-specific input fields

**Bash：**
```json
"tool_input": {
  "command": "npm test",
  "description": "Run tests",
  "timeout": 120000,
  "run_in_background": false
}
```

**Edit：**
```json
"tool_input": {
  "file_path": "/abs/path",
  "old_string": "...",
  "new_string": "...",
  "replace_all": false
}
```

**Write：**
```json
"tool_input": {
  "file_path": "/abs/path",
  "content": "..."
}
```

---

## 5. Exit code / Output 控制速查

### Exit codes
| Code | 行為 |
|---|---|
| **0** | Success；stdout 看事件決定（SessionStart 自動進 context，其他多進 debug log）|
| **2** | **Blocking error**；忽略 stdout，stderr 給 Claude；事件依本身行為決定 block 什麼 |
| **其他** | Non-blocking error；transcript 顯示 hook error notice |

### 哪些事件能 block（exit 2 有效）
- `PreToolUse` — block tool call
- `UserPromptSubmit` — reject prompt
- `Stop` — prevent stop, continue conversation
- `WorktreeCreate` — abort worktree creation（**任何**非零都 abort，不只 exit 2）
- 其他多數事件：exit 2 = stderr to user only

### JSON output 決策 patterns

**Pattern 1：Top-level `decision`**（用於：UserPromptSubmit / PostToolUse / Stop / SubagentStop / ConfigChange / PreCompact 等）
```json
{ "decision": "block", "reason": "..." }
```

**Pattern 2：`hookSpecificOutput` 給 PreToolUse**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask|defer",
    "permissionDecisionReason": "..."
  }
}
```

**Pattern 3：`additionalContext` 注入 Claude context**（用於：SessionStart / Setup / SubagentStart / UserPromptSubmit / PreToolUse / PostToolUse）
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Current branch: feat/auth-refactor\n...",
    "initialUserMessage": "...",   // SessionStart only
    "watchPaths": ["/abs/path"]    // SessionStart only — 設 FileChanged 監看路徑
  }
}
```

**通用欄位**（所有 hook 都能用）：
```json
{
  "continue": true,           // false = Claude 完全停止
  "stopReason": "...",        // continue=false 時顯給 user
  "suppressOutput": false,    // true = 隱藏 stdout 在 transcript
  "systemMessage": "...",     // warning 給 user
  "terminalSequence": "..."   // 終端 escape sequence（通知/標題/嗶）
}
```

---

## 6. 已知 gotchas / 踩坑 / cosmetic bug

### A. PowerShell 5.1 編碼問題 ⚠️ 必記
**症狀：** `.ps1` 含中文字串 → `ParseError: The string is missing the terminator`
**原因：** Windows PowerShell 5.1（舊版，預設）讀無 BOM 的 UTF-8 檔時用 ANSI（cp950/cp936）→ mojibake → parse error
**解法：** 所有 `.ps1` 必須加 **UTF-8 BOM**（`\xEF\xBB\xBF` 前綴）
**驗證：** `head -c 5 file.ps1 | xxd` 看頭 3 byte 是不是 `efbbbf`
**自動加 BOM 一行指令：**
```powershell
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($path, (Get-Content $path -Raw -Encoding UTF8), $utf8Bom)
```

### B. `$ErrorActionPreference = 'Stop'` + git stderr 互動 cosmetic bug
**症狀：** auto-sync-pi.ps1 log 偶寫「ERROR: From https://github.com/...」但 sync 實際成功
**原因：** PS 5.1 把 native cmd（git）的 stderr 當 NativeCommandError，配合 `ErrorActionPreference = 'Stop'` → try/catch 抓到，誤判 error
**狀態：** 還沒修；功能無影響；TODO 改 `'Continue'` 包裹 git 呼叫

### C. SessionStart 在 subagent 內是否 fire — 官方未明說
**官方原文：** `subagent behavior is not addressed in the SessionStart documentation`
**防禦策略：** session-start-context.ps1 內檢查 stdin JSON 的 `agent_id` field，存在則 silent exit（subagent 不該被注入 main session context）
**好處：** 不論官方未來怎麼處理，我的 hook 都安全

### D. Stop hook 在 subagent 內**不會** fire
**官方原文：** `For subagents, Stop hooks are automatically converted to SubagentStop`
**意思：** 我們派 Agent({...}) 時，subagent 結束 fire 的是 SubagentStop，不是 Stop → stop-check-sales-pytest.ps1 不會被誤觸發

### E. CLAUDE_PROJECT_DIR env var 在 worktree 內是 worktree path
**症狀：** auto-sync-pi.ps1 在 worktree 內跑時，`${CLAUDE_PROJECT_DIR}` 指向 worktree，但 sync_pi.ps1 是 gitignored 不在 worktree
**解法：** hardcoded 用 main checkout 路徑 `C:/Users/LIN HONG/Desktop/Project_01`，fallback CLAUDE_PROJECT_DIR

### F. PostToolUse hook 在 tool 失敗時是否 fire
**官方：** PostToolUseFailure 是另一個事件 → PostToolUse 只在 tool **成功**時 fire
**意思：** `git push origin main` 若失敗，sync_pi 不會被誤觸發 ✓

### G. Stop hook 無法直接看本輪 tool 歷史
**官方確認：** Stop hook input JSON 只含 common fields，無 `tool_input` / `tool_name` / `tools_used`
**唯一管道：** 自己 parse `transcript_path` 的 `.jsonl`（複雜、未驗證 schema 穩定性）
**我們的設計：** 走 flag file 三方協作（更穩定、無依賴 transcript schema）

### H. SessionStart hook 跑得快很重要
**官方原文：** `SessionStart runs on every session, so keep these hooks fast`
**我們的 session-start-context.ps1 估時：** ~200-400ms（git 兩三個指令 + Select-String 數 test funcs）— 可接受

### I. matcher 不支援的 events
**官方原文：** `Stop, UserPromptSubmit, PostToolBatch, TeammateIdle, TaskCreated, TaskCompleted, WorktreeCreate, WorktreeRemove, CwdChanged don't support matchers`
**意思：** 這些 events 的 hook entry 不能寫 `"matcher": "..."`，永遠 fire
**我們 Stop hook 配置就沒寫 matcher** ✓

### J. Hook stdout 編碼問題 ⚠️ 必記（與 A 配對）
**症狀：** `/compact` 後 SessionStart 注入的 system-reminder 顯示亂碼（如 `## ������B���գ�`）；Claude 看到的注入內容變廢；deny reason 亂碼導致使用者不知為何被擋。
**原因：** PowerShell 5.1 預設 `[Console]::OutputEncoding` 與 `$OutputEncoding` 為**系統 ANSI code page**（本機 = cp936/GBK，PRC 區域；台灣機器才是 Big5/cp950），但 Claude Code 讀 hook stdout 預期 UTF-8 → 中文被當 cp936 解碼成亂碼。
**解法：** 所有會 `Write-Output` 中文到 Claude 的 hook 開頭加：
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
```
**範圍：** 5 個 hook 需修（session-start-context / subagent-inject-rules / stop-check-sales-pytest / block-vendor-edit / block-git-add-bulk）。State/log-only hooks（auto-sync-pi / state-mark / state-clear）不需修，輸出不到 Claude。
**驗證：** 手動 pipe stdin JSON 給 hook → 看 stdout 是不是乾淨繁中
**Gotcha A vs J 區別：** A 是 .ps1 **input**（讀 source code）編碼問題（用 BOM 解決）；J 是 .ps1 **output**（寫 stdout）編碼問題（用 OutputEncoding override 解決）。兩個都得處理。

### K. block-git-add-bulk regex 太寬，誤擋含 `git add -A` / `git add .` 字面的 commit message
**症狀：** commit message 內文寫了「擋 `git add -A` / `git add .`」這類字串時，本 hook 把整個 Bash command 字串（含 commit -m "...") 掃到，誤判為要跑 `git add -A` 並 deny。
**原因：** regex `\bgit\s+add\s+(-A\b|--all\b|\.(?:\s|$))` 沒限定「行首」或「在 shell separator `&&` `;` `|` 之後」，掃整段 command 字串就會中招。
**踩到時間：** 2026-05-25 寫 commit「hooks: force UTF-8 stdout encoding ... 5 hooks (... bulk-add deny reason)」第一次 commit body 內含字面 `'git add -A'` / `'git add .'` 被擋。
**workaround：** commit message 內文避開字面 `git add -A` / `git add .`，改用「bulk-add」「bulk」「-A 旗標」描述。
**TODO：** 收緊 regex 加 lookbehind 限定 shell separator / 行首。沒急做（commit message 寫法 workaround 簡單）。

---

## 7. Cross-check 結果（subagent 推測 vs 官方）

| 項目 | claude-code-guide subagent | 主 agent WebFetch | 真實答案（官方）|
|---|---|---|---|
| reason 字數限制 | 「最佳實踐 <200 字」 | 未提 | **無限制** — subagent 推測錯 |
| SessionStart 在 subagent fire | 「不 fire」 | 「未明確記載」 | **官方未說** — subagent 推測，**防禦寫法為準** |
| SubagentStop 替代 Stop | 「自動轉換」 | 未提 | **真**（官方明確）|
| `if` field 存在 | ✅ | ✅ | 真（用於 permission rule syntax）|
| `async: true` 存在 | ✅ | ✅ | 真 |
| `shell: "powershell"` 存在 | ✅ | ✅ | 真 |
| FileChanged event 存在 | ✅ | ✅ | 真 |
| `claudefa.st` 是官方 source | ✅ 引用 | ❌ 質疑 | **第三方 blog，不是官方** — subagent 引錯 source |

**結論：** subagent 大方向對，細節偶有推測 / 引錯 source；**必須 cross-check**。

---

## 8. 未實作但有用的官方功能（future ideas）

### ~~A. `SubagentStart` hook~~ ✅ **已實作（2026-05-25 同日）**
原 future idea，**現已上線：** `subagent-inject-rules.ps1`
- 依 agent_type 分流：編碼類（general-purpose）注入完整規範；研究類（claude-code-guide / Explore / Plan / statusline-setup）注入精簡版
- 取代 subagent-dispatch-protocol 步驟 2-3 的手動塞規則 boilerplate
- 主 agent 派發 prompt 只需寫 task description + 任務特化規則

### B. `watchPaths` + `FileChanged` event
- SessionStart hook 可 return `watchPaths: ["abs/path/..."]`
- 該路徑檔案變動 → `FileChanged` event fire（async）
- **用途：** 外部編輯器（VSCode）改檔時也能觸發 hook
- **TODO 評估：** Claude 已有自己的 file edit hooks，這個值得做嗎？

### C. `PreCompact` hook
- compaction 前 fire，可注入 context 保留關鍵資訊
- **用途：** 自動補一條「目前正在做 X 任務，cart-dirty flag 狀態 Y」幫助 compact 後不忘
- **TODO 評估：** 中等價值，看 compact 後是否真的會忘要事

### D. `initialUserMessage` (SessionStart only)
- SessionStart 可指定首個 user message（headless mode `-p` 內生效）
- **用途：** CI / 自動化情境

### E. `CLAUDE_ENV_FILE` 在 SessionStart hook 內
- SessionStart hook 可寫到 `$env:CLAUDE_ENV_FILE`，內容會被持久化到 Bash subprocess
- **用途：** session 開始時設環境變數（如 `NODE_ENV=production`）給所有 Bash tool 看
- **TODO 評估：** 目前用不到

### F. `Notification` hook
- 各種系統通知（如 permission 等待）時 fire
- **用途：** 改成 push notification 給手機（agentPushNotifEnabled 配合）

### G. `MCP tool` 類型的 hook
- hook type 可以是 `mcp_tool` — 呼叫 MCP server 的 tool 而不是 shell command
- **用途：** 未來如果接了 Linear / Slack / Github MCP，hook 可以直接更新 issue / 發訊息

### H. `prompt` / `agent` 類型的 hook
- hook type 可以是 `prompt`（給 fast model 跑 prompt）或 `agent`（給 subagent 處理）
- **用途：** complex 判斷邏輯（如「這個 git commit message 寫得清楚嗎？」）

### I. `decision: "ask"` 給 PreToolUse
- 不是 block 也不是 allow，是強制走 permission flow 問 user
- **用途：** 「破壞性操作（rm -rf / git reset --hard）」自動轉成需 user 確認

### J. `terminalSequence` 通用欄位
- hook output JSON 可塞 terminal escape sequence
- **用途：** 失敗時亮紅燈、完成時 bell、改視窗標題

---

## 9. 確認不可行的事項清單（不要再想了）

- ❌ Stop hook 不能 read 本輪用了哪些 tool（官方確認）
- ❌ Stop hook 不能用 `additionalContext`（官方 decision pattern table 確認）
- ❌ SessionStart hook 不能 block（官方確認 "No blocking or decision control"）
- ❌ Subagent dispatch 時 `Stop` event 不 fire（替代為 SubagentStop）
- ❌ Hook 不能修改其他 tool 的 output（只能 control 自己的決策）
- ❌ Hook 不能呼叫 Claude tool（如 AskUserQuestion / Read 等）— 只能跑 shell / HTTP / MCP

---

## 10. 維護指南

### 改 hook script 時
1. 一定 EnterWorktree（hook 屬 .claude/，tracked）
2. 寫 PS 一定加 BOM 否則 PS 5.1 會 mojibake error
3. 本地測試：`'{...stdin json...}' | & powershell -NoProfile -File path/to/script.ps1`
4. 改完 settings.json 也要重啟 Claude Code session 才會 reload（**未驗證**，可能 ConfigChange event 自動 reload）

### 加新 hook event 時
1. 看 §3 確認 event 真實存在（別瞎掰）
2. 看 §5 確認該 event 的 decision pattern
3. 看 §6 看有沒已知 gotcha 撞到
4. 寫完 test 邊界 case
5. 更新本檔（§1 一覽表 / §6 新 gotcha）

### Debug hook 沒觸發時
1. 看 stderr — Claude transcript 會顯示 hook error notice
2. 看 hook script 內手動 log 到檔案（無官方 hook log view）
3. 確認 settings.json 路徑（`.claude/settings.json` 是 project，不要寫到 user global）

---

## 11. 參考來源

- **官方文檔（authoritative）：** https://code.claude.com/docs/en/hooks
- **WebFetch records（保留 3 輪 query log）：** 略
- **claude-code-guide subagent 報告（保留 3 輪 raw output）：** 略（agent IDs: a825e4f9, a8c1bdc3, a6fb500a — temp files）
- **本檔 commit history：** `git log -- .claude/hooks/NOTES.md`

---

**Maintainer note：** 本檔是 hooks 系統的 single source of truth，所有 hook 設計 / 變動 / 移除前都應該先查這檔再動手。若官方文檔升級或新 events 出現，請更新 §3 / §5。
