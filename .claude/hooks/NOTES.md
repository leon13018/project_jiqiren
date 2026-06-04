# Claude Code Hooks — 完整研究筆記（毫無保留版）

> 本檔記錄 hooks 系統的所有調研發現、設計決策、踩坑歷史、未實作但有用的功能。
> 後續討論 / 維護 / 擴展 hooks 都應該先看這檔。
>
> **最後更新：2026-06-02**（§10.6 官方陷阱稽核；前次 2026-05-25 Stop + SessionStart hooks 上線）

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
| `block-git-add-bulk.ps1` | PreToolUse | Bash（+`if:"Bash(git add *)"` gate）| 擋 `git add -A` / `--all` / `.` | 低（命中精準）|
| `block-windows-install.ps1` | PreToolUse | Bash\|PowerShell | 擋本機 `pip` / `npm` / `apt` install（pytest 例外）| 低 |
| `block-vendor-edit.ps1` | PreToolUse | Edit\|Write | 擋廠商 SDK 檔（ActionGroupControl/Board.py）| 低 |
| `state-mark-sales-dirty.ps1` | PostToolUse | Edit\|Write | 編 sales/* 時寫 flag | 低 |
| `state-clear-on-pytest.ps1` | PostToolUse | Bash | pytest 跑過清 flag | 低 |
| `check-traditional-chinese.ps1` | PostToolUse | Edit\|Write | 掃剛寫入檔的常見簡體字 → 純警示（不擋）| 低 |
| `stop-check-sales-pytest.ps1` | Stop | (無 matcher) | 結束 turn 前若 flag pending → block 一次 | 中（block 體驗略生硬）|
| `stop-sync-pi.ps1` | Stop | (無 matcher) | 每 turn 結束比對 origin/main vs marker，落後則 sync Pi + 清 pycache，成功寫 marker | 中（同步阻塞 turn end ~3s，僅落後時）|
| `session-start-context.ps1` | SessionStart | (無 matcher, 全 source) | 注入 branch/status/test count 到 Claude context | 低 |
| `subagent-inject-rules.ps1` | SubagentStart | (無 matcher) | 只對 Explore/Plan（唯一跳過 CLAUDE.md 的 agent）注入「繁中 + 文檔指標」最小導航；其餘 agent 原生載入 CLAUDE.md 故直接放行 | 低 |

**對應 settings.json 結構：**
```
PreToolUse:
  Bash → block-git-add-bulk        (帶 if:"Bash(git add *)" gate，gotcha K 根治)
  Bash|PowerShell → block-windows-install
  Edit|Write → block-vendor-edit
PostToolUse:
  Bash → [state-clear-on-pytest]
  Edit|Write → [state-mark-sales-dirty, check-traditional-chinese]
Stop:
  → [stop-check-sales-pytest, stop-sync-pi]
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

### 同架構的第二個 flag：`last-synced-commit.marker`（stop-sync-pi）

`stop-sync-pi.ps1` 用同屬 `state/` 的 `last-synced-commit.marker` 存「上次成功 sync 到 Pi 的 `origin/main` SHA」。每 turn 結束：`git rev-parse origin/main` vs marker，相同→零 SSH 早退；落後→跑 `sync_pi.ps1` + 清 pycache，**成功才把 marker 更新成新 SHA**。失敗不更新 → 下個 turn 自動重試（自我修正）。與 sales-dirty 同為「state/ flag 檔協作」家族，但更簡單（單向 marker、無 pending/reminded 狀態機、永不 block）。marker 用 no-BOM UTF-8 寫入（`WriteAllText`+`UTF8Encoding $false`），避免 SHA 比對受 BOM 干擾。

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

**⚠️ 2026-06-01 補充 — 兩個會「產生無 BOM .ps1」的常見來源（都會重新觸發本 gotcha）：**
1. **Claude Code 的 Write 工具寫 .ps1 = 無 BOM**。用 Write 新建任何含中文的 hook / script 後，**必須**接著用上面的「自動加 BOM 一行指令」補 BOM，否則 PS 5.1 hook 一執行就 parse error（症狀同上：`block-windows-install.ps1:35 字符:40` 之類，且錯誤訊息本身亂碼）。
2. **pwsh 7 `Set-Content -Encoding UTF8` = 無 BOM（會洗掉既有 BOM！）**。pwsh 7 的 `UTF8` 是 no-BOM，`Set-Content`/`Out-File -Encoding UTF8` 重寫一個原本有 BOM 的 .ps1 會把 BOM 拿掉 → 原本好好的 hook 壞掉。要保留 BOM 改用 `-Encoding utf8BOM`，或統一用上面的 `WriteAllText` + `UTF8Encoding $true`。**歷史**：2026-06-01 references→reference 改名時用 `Set-Content -Encoding UTF8` 洗掉 `subagent-inject-rules.ps1` 的 BOM（回歸），同批新建的 `block-windows-install` / `check-traditional-chinese` / `clean-pi-pycache` 本來就無 BOM，一併補回（commit `a1c3753`）。
**經驗法則**：動完任何 .ps1（新建或重寫）後，跑 `head -c 3 file.ps1 | od -An -tx1` 確認頭 3 byte 是 `ef bb bf`；不是就補。

### B. `$ErrorActionPreference = 'Stop'` + native command stderr 互動 ⚠️ 已修
**症狀：** auto-sync-pi.ps1 log 寫「sync_pi.ps1 ERROR: ...」並中斷 try block。實測踩到兩種 stderr 雜訊：
1. `git pull` 印 "From https://github.com/..." 進度訊息進 stderr（原有 finding）
2. **OpenSSH 新版量子安全警告**（2026-05-27 新踩）：`** WARNING: connection is not using a post-quantum key exchange algorithm. ** This session may be vulnerable to "store now, decrypt later" attacks.` — Pi 的 OpenSSH 沒支援 post-quantum kex 時 client 端 unconditional 印
**原因：** PS 5.1 在 `2>&1` 時把 native command stderr 包成 `NativeCommandError` ErrorRecord 進 pipeline；`ErrorActionPreference = 'Stop'` 把它當 terminating error → 跳到 catch → 後續流程（含 pycache 清理）被跳過。
**修法：** 2026-05-27 commit — `auto-sync-pi.ps1` 兩個 try block 內 inline `$ErrorActionPreference = 'Continue'` 跑 native command，改用 `$LASTEXITCODE` 判斷成功失敗（native command 才有的可靠指標）；`finally` 恢復原 EAP。
**驗證：** 修後手動 invoke hook，log 應寫「sync_pi.ps1 completed exit=0」+「Pi __pycache__ cleared exit=0」而非 ERROR。

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

### K. block-git-add-bulk regex 太寬，誤擋含 `git add -A` / `git add .` 字面的 commit message ⚠️ 已修
**症狀：** commit message 內文寫了「擋 `git add -A` / `git add .`」這類字串時，本 hook 把整個 Bash command 字串（含 commit -m "...") 掃到，誤判為要跑 `git add -A` 並 deny。
**原因：** regex `\bgit\s+add\s+(-A\b|--all\b|\.(?:\s|$))` 沒限定「行首」或「在 shell separator `&&` `;` `|` 之後」，掃整段 command 字串就會中招。
**踩到時間：** 2026-05-25 寫 commit「hooks: force UTF-8 stdout encoding ... 5 hooks (... bulk-add deny reason)」第一次 commit body 內含字面 `'git add -A'` / `'git add .'` 被擋。
**修法（2026-06-03，commit `1f8c4f3`）：** 不收緊 regex，改在 settings.json 給本 hook entry 加 `"if": "Bash(git add *)"` gate。官方確認 `if` 用 permission-rule 語法**逐 subcommand 比對**（分隔符 `&& || ; |` 等，**引號內不解析**）→ `git commit -m "...含字面 git add -A..."` 被當單一 `git commit` 子命令，不 match → hook 根本不 spawn → 誤擋根治；真正的 `git add -A`/`--all`/`.` 仍 match → 照常 deny（守門不失效）。附帶省去每次 Bash 呼叫的 spawn。script 內 regex 維持不變（當 spawn 後的實際判斷）。
**驗證（官方根據）：** 派 claude-code-guide 查 code.claude.com/docs/en/hooks + permissions：`if` 不命中→「never run」（不可能誤 deny）；`Bash(git add *)` match `git add -A`/`--all`/`.`/`file.py`；複合指令逐 subcommand 切、引號內不當獨立命令。
**已知殘留邊界（不修）：** `git -C "..." add -A` 可能不 match `Bash(git add *)`（git 與 add 間夾 `-C`，文檔未明）——但**現有 regex `\bgit\s+add` 對此型本來就漏抓**（同 gotcha L 的 -C 缺口），故 `if` gate 不引入新回歸，屬同等既有缺口。實務上幾乎不會用 `git -C ... add -A`，踩到再說。
**workaround（已不需要，存查）：** 修前靠「commit message 內文避開字面 `git add -A` / `git add .`，改用 bulk-add / -A 旗標描述」。`if` gate 上線後不再受限。

### L. auto-sync-pi regex 太嚴，`git -C ... push origin main` 不命中 ⚠️ 已修
**症狀：** push 後 Pi 沒 sync 到最新 commit。log 內看不到對應 push 的 `Triggered by:` 行（hook 根本沒跑）。
**原因：** 舊 regex `\bgit\s+push\s+origin\s+main\b` 要求 `git` 後面**直接接** `push`。worktree 工作流程下我習慣用 `git -C "C:/..." push origin main`，`-C ...` 卡在 git 跟 push 中間 → regex miss。
**踩到時間：** 2026-05-25 兩個 hook 修補 commit（c47ba98 / d0fce32）push 後 Pi 停在 9948962，使用者去 Pi 上發現後才察覺。
**修法：** 改 regex 為 `\bgit\b[^;&|\r\n]*?\bpush\s+origin\s+main\b` — 允許 git 與 push 之間有 git options，但用 `[^;&|\r\n]` 阻止跨 shell separator 誤匹配。
**驗證的 case：**
- ✅ `git push origin main`
- ✅ `git -C "..." push origin main`
- ✅ `git merge xxx --ff-only && git push origin main`
- ✅ `git merge xxx --ff-only && git -C "..." push origin main`
- ❌ `git push origin master`（main 後有字接 → \b 擋）
- ❌ `git status; some other thing push origin main`（跨 `;` 不匹配）
**Gotcha K vs L 對比：** K 是 regex **太寬**（誤抓）；L 是 regex **太嚴**（漏抓）。寫 hook 的 regex 要在「精準命中目標」與「不掃到字面字串」之間平衡。建議未來新 hook 寫 regex 時，主動測 4 種 case：simple form / -C form / `&&` chain / commit message 內含字面。

### M. Subagent 偶發 commit 跑到 main branch 而非 worktree branch ⚠️ 待 reproduce
**症狀：** 主 agent EnterWorktree 後派 subagent 寫 code + commit；subagent 回報 commit SHA，但實際 worktree branch HEAD 沒動，commit 跑到主 checkout 的 main branch（reflog 顯示 `refs/heads/main@{0}: commit` + `main-worktree/HEAD@{0}: commit`，worktree-* branch 仍在派發前的 HEAD）。
**踩到時間：** 2026-05-26 commit `288a851`（confirm-no-clear-cart 任務，sonnet subagent）。
**已驗證不是 cwd 繼承問題：** 同日後續派 haiku diagnostic subagent 在 worktree 內跑 `pwd / git rev-parse --show-toplevel / git rev-parse --git-dir / git branch --show-current` → 全部正確（worktree path + `.git/worktrees/<name>` + `worktree-<name>` branch）。表示 Agent 工具的 cwd 繼承機制本身 OK。
**hypotheses（未證實，下次踩到要 reproduce）：**
1. subagent Edit/Write 用「相對路徑」時，內部 expand 成主 checkout 絕對路徑（不是 cwd）→ 改主 checkout 的檔 → git status 在主 checkout 有變 → 後續 git add/commit 命中主 checkout
2. subagent 自己跑 `cd` 出 worktree（特定 prompt 觸發）
3. Claude Code internal race / bug
**workaround / 防呆：**
- **派發後必驗：** subagent 回報 commit SHA 後，跑 `git branch --contains <SHA>` 確認落在 worktree-* branch（已加入 `subagent-dispatch-protocol.md` 派發後必做段）
- **若 commit 跑到 main：** 直接在主 checkout `git push origin main`，跳過 worktree ff-merge（worktree branch 沒 commit 可 merge）；cleanup 流程不變（worktree branch 跟主 checkout 同 commit ancestor，可安全刪）
- **下次 reproduce 時：** 派發 prompt 第一步要求 subagent 回報 `pwd && git branch --show-current && git rev-parse --git-dir`，跟預期值比對；若不符即停手回報主 agent

### N. Background job session 內 PostToolUse hook 非 deterministic ⚠️ Claude Code 端行為
> **✅ 2026-06-03 已繞過**：sync 改用 **Stop hook（`stop-sync-pi.ps1`）** 觸發——官方確認 Stop 在所有 session 類型（含 headless/background）可靠 fire（非同步 PostToolUse 的非確定性是該事件特有，Stop 不受影響）。`auto-sync-pi.ps1` 已移除。本 gotcha 保留作歷史 + 設計決策背景（見 `resources/specs/pi_sync_stop_hook_2026-06-03_spec.md` / `resources/research/CC_hooks_automation_best_practices_2026-06-03.md`）。
> **實證（2026-06-03）**：(1) live session — push 後 turn 結束 stop-sync 自動觸發、marker 推進、Pi 同步（log 11:58:32）。(2) **headless `claude -p` session** — session 結束時 stop-sync 同樣可靠觸發並完成 sync（log 12:07:38，`Updating 14f65c6..8fa861b Fast-forward`）。對照本 gotcha 對 PostToolUse 的「非確定性」觀察：**Stop hook 在非互動 session 是可靠的**，與官方說法一致。
**症狀：** Claude Code background job 模式（`$CLAUDE_JOB_DIR` env var 存在 / system context 含「Background Session」段）內，PostToolUse hook **觸發行為非 deterministic — 有時跑有時不跑，原因未明，視為不可依賴**。具體影響：`git push origin main` 後 auto-sync-pi.ps1 可能沒被 Claude Code 觸發 → Pi 沒同步 → user demo 跑舊版 code。
**踩到時間：** 2026-05-27 S3 同步動作落地 push commit `16a90bd` 後，使用者 Pi 上 `git log -1` 看到 HEAD 仍是 `028ac3f`（前一輪 commit）。檢查 `auto-sync-pi.log` 發現該 push 沒進 log（最後 entry 是上一輪 live session 結束 push）。手動 invoke hook script 跑得起來 → 確認 hook script 本身沒壞。
**Finding refine（同日後續觀察）：** 原以為「完全不觸發」，但同一個 background session 內後續 push 行為不一致：
- `16a90bd` (S3 落地)：沒觸發
- `aae2338` (hook fix)：沒觸發
- `f084aba` (CLAUDE.md docs)：**觸發了**（log 23:21:48 entry）

→ 結論：**非 deterministic 而非絕對不觸發**。規律未明（command 結構 / timing race / async hook + 120s timeout 互動？均為 hypothesis）。
**性質：** Claude Code background mode 設計 / bug — 未在官方文檔明確記載。**hook 端無法修**（hook script 本身沒問題）。
**Workaround**（規則層補強）：
- 主 agent 在每次 push 後 **永遠 explicit 跑** `& sync_pi.ps1`（PowerShell tool）— 不要試圖判斷 hook 這次有沒有跑
- hook 偶有自動跑 → 手動跑變 idempotent no-op（git pull → Already up to date），浪費 ~3s SSH latency 可接受
- 規則檔已加註：`standard-workflow.md` 步驟 5 / `worktree-workflow.md` 階段 4「Background session 雙保險」段
**判斷標準：** 看 system context — 有「# Background Session」段 + 提到 `$CLAUDE_JOB_DIR` 路徑 → background；否則 live。
**未來如要 root cause 釐清：** 系統性 reproduce — 每次 push 後同步看 hook log，搜集 N 次樣本看跑 / 沒跑的差異變因。本輪 demo 推進優先，紀錄到此停。

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
- **只對 Explore / Plan 注入**「繁中 + 文檔指標」最小導航；其餘 agent（general-purpose / claude-code-guide / statusline-setup / 自訂 sales-coder）**直接放行不注入**。
- **設計依據（官方 sub-agents.md，2026-06-03 派 claude-code-guide 查證）**：只有 built-in Explore / Plan 啟動時跳過 CLAUDE.md + git status；「Every other built-in and custom subagent loads both」。故唯有 Explore/Plan 看不到專案規範與導航，需 hook 補；其餘 agent 原生載入 CLAUDE.md（紅線 + skill 路由本就在），再注入＝重複佔 attention。且 Explore/Plan 為唯讀研究 agent（主對話帶 CLAUDE.md context 解讀其結果），連紅線都不必傳，只補它們看不到的「繁中產出 + 文檔入口」。
- **演進**：原設計（2026-05-25）依「編碼類完整 / 研究類精簡」分流、且預設 subagent 讀不到 CLAUDE.md；2026-06-03 查證該前提有誤（只有 Explore/Plan 跳過）後改為現行「只補 Explore/Plan」，刪掉對 CLAUDE.md-loading agent 的全部冗餘注入（含原「完整版」紅線段）。
- 主 agent 派發 prompt 只需寫 task description + 任務特化規則。

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
4. 改完 settings.json：官方文檔（hooks-guide）確認 file watcher **通常幾秒內自動 reload**，沒生效再重啟 session 保險。（前述「未驗證」懸念已由 2026-06-03 best-practices 調研解答，見 `resources/research/CC_hooks_automation_best_practices_2026-06-03.md` §4）

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

## 10.6 官方陷阱稽核（2026-06-02）

派 claude-code-guide subagent 重抓官方文檔（`code.claude.com/docs/en/hooks`）整理出 17 條 hooks 陷阱，
對照本專案全部 10 個 hook 腳本逐一比對。**結論：一條都沒踩到，且多條為主動防禦。** 無需修改。

### 逐條對照

| # | 官方陷阱 | 本專案狀態 | 判定 |
|---|---|---|---|
| 1 | `exit 1` 擋不住動作 | 3 個 block hook 都用 JSON `permissionDecision:deny` + `exit 0`（官方兩種合法擋法之一），不依賴 exit 1 | ✅ |
| 2 | JSON 與 `exit 2` 混用（JSON 被忽略） | 從未混用；要嘛 JSON+exit 0，要嘛純 exit 0 | ✅ |
| 3 | shell profile 的 echo 污染 JSON stdout | **每個 hook 都帶 `-NoProfile`** | ✅ 主動防禦 |
| 4 | 超時阻塞 session | `auto-sync-pi` 有 `timeout:120`+`async`；其餘皆快指令（默認 600s 充足） | ✅ |
| 5 | 輸出超 10,000 字元被改存檔 | 最大的 `subagent-inject-rules` 也遠低於 1 萬字 | ✅ |
| 6 | matcher 精確 vs 正則混淆 | `Bash` / `Bash\|PowerShell` / `Edit\|Write` 皆合法「字母+`\|`」精確 alternation，無需正則 | ✅ |
| 7 | Windows exec form 跑 `.cmd`（如 npm）失敗 | 用 `command:"powershell"`（真 .exe，非 .cmd），exec form 正確 | ✅ |
| 8 | PreToolUse vs PermissionRequest 決策格式不同 | 只用 PreToolUse，格式 `permissionDecision:deny` 正確 | ✅ |
| 9 | `async:true` 靜默失敗、模型不被通知 | `auto-sync-pi` 刻意 fire-and-forget（CLAUDE.md 明定手動 `& sync_pi.ps1` 為準） | ✅ 已知取捨 |
| 10 | HTTP hook 默認不阻止操作 | 未使用 HTTP hook | — N/A |
| 11 | SessionStart 非冪等（`$(date)` resume 後過期） | 每次重算 git 狀態、無寫死時間戳進輸出；另有 `agent_id` guard 防污染 subagent | ✅ 主動防禦 |
| 12 | MCP tool hook 連線檢查報未連接 | 未使用 MCP hook | — N/A |
| 13 | 不支援 matcher 的事件寫了會被靜默忽略 | Stop / SessionStart / SubagentStart **正確地未寫 matcher** | ✅ |
| 14 | 無法存取 `/dev/tty` / 互動輸入 | 無互動輸入 | ✅ |
| 15 | `allowManagedHooksOnly` 擋掉非 managed hooks | 個人專案，N/A | — |
| 16 | `additionalContext` 用命令句觸發注入防禦 | 注入的是專案規則（禁止…/繁中…），屬正當用途，非「忽略先前指令」型 | ✅ |
| 17 | matcher/if/disableAll 等導致 hook 不觸發 | 無異常 | ✅ |

### 超出文檔要求的主動防禦（本專案特有）

- **UTF-8 OutputEncoding 修正**：每個輸出繁中的 hook 都修了 PowerShell 5.1 預設 cp936/GBK（本機 code page = 簡中），
  否則繁中 deny reason / 注入內容會 mojibake。此為文檔未提、但本機環境必須做的步驟。
- **Stop hook `pending → reminded` 一次性提醒**：避開「Stop hook 無限 block 造成 deadlock」鄰近陷阱。
- **block hook 解析失敗 fail-open**（`catch { exit 0 }`）：寧可放過不誤殺，符合 PreToolUse 最佳實踐。

### 兩個無害小觀察（非問題、刻意不改）

1. `state-mark-sales-dirty` / `state-clear-on-pytest` 未設 UTF-8 OutputEncoding —— 但兩者只寫 flag 檔、不對 stdout 印任何東西，
   無 mojibake 風險，純風格不一致。
2. `state-clear-on-pytest` 用 `\b(pytest|py\.test)\b` 比對指令字串 —— 理論上某指令僅「提到」pytest 卻沒真跑（如 `echo pytest`）
   會誤清 flag；屬刻意的寬鬆設計（docstring 有註明），實務幾乎不觸發。

> **觸發來源**：使用者讀 `resources/research/CC_large_codebases_best_practices_2026-06-01.md`（官方大型程式庫最佳實踐筆記）
> 提到「常見誤用」後，要求對照官方 hooks 文檔做防禦性稽核。

---

## 11. 參考來源

- **官方文檔（authoritative）：** https://code.claude.com/docs/en/hooks
- **WebFetch records（保留 3 輪 query log）：** 略
- **claude-code-guide subagent 報告（保留 3 輪 raw output）：** 略（agent IDs: a825e4f9, a8c1bdc3, a6fb500a — temp files）
- **本檔 commit history：** `git log -- .claude/hooks/NOTES.md`

---

## 12. stop-reflect（反思型 Stop hook，手搓版）

- 事件：Stop（與 stop-check / stop-sync 並行，互不依賴）。exit 0 always、永不 block。
- 觸發：T1 = 本 turn 有 git 變動（status 非空或 HEAD ≠ last-reflected marker）→ 素材 = diff（cap 400 行）；
  T2 = 連續 20 輪無反思 → 素材 = transcript 尾段（30 條 / 8KB cap）。
- 引擎：Start-Process 拋背景 `reflect-worker.ps1` → `claude -p`（Haiku、fresh context、prompt 經 stdin 餵入、禁工具指示）→
  提議 append `resources/reflections/proposals.md`（gitignored）；**只提議、絕不自動寫入規範檔**。
- 防迴圈：`CLAUDE_REFLECT_CHILD=1` 旗標（stop-reflect + stop-sync + stop-check 三支開頭早退）+
  worker cwd 移出專案（專案 hooks 不載入，雙保險）｜每日呼叫保險絲 100（`daily-calls_<yyyyMMdd>.txt`，
  按日重置、7 天自清；正常用不到，防自動化長跑暴走）｜**語意去重**（既有 slug 清單餵進
  prompt，事後字串比對保底）｜lock 防並發（10 分鐘殭屍自清）。
- 未讀提示：proposals pending 數增加時，下一次 Stop 輸出 systemMessage + additionalContext（實測結果：<驗證後回填：支援/被忽略>）；
  人工清理 proposals 使 pending 回落 → 計數自動 sync-down（否則下一條新提議的提示會被吞）。
- state：`.claude/hooks/state/reflect/`；log：`.claude/hooks/reflect.log`（皆 gitignored）。
- 關閉方式：settings.json 移除該 Stop 群組；或暫時把 `stop-reflect.ps1` 頂部 `$DAILY_CAP` 設 0。
- **實作踩坑（手搓記錄，未來寫 hook 必讀）**：
  1. PS1 含繁中必須 **UTF-8 with BOM**——PS 5.1 對無 BOM 檔以 cp936 解析，多位元組序列會吞掉引號造成 parse error。
  2. Start-Job 子 host 要自設 `[Console]::OutputEncoding=UTF8`，否則 claude stdout 繁中變亂碼（與主腳本各自獨立）。
  3. **絕不可用 `Select-String -Path` 讀無 BOM UTF-8 檔**（cp936 誤解碼，全形字元匹配必失敗）——一律 `[System.IO.File]::ReadAllText(..., UTF8)`。
  4. 精確 slug 去重攔不住「同義異名」——必須把既有主題清單餵進評審 prompt 做語意去重。
  5. prompt 走 stdin 餵 `claude -p`：免 3s stdin 偵測等待、免 Windows 命令列長度上限、免引號轉義。
  6. `Start-Process -ArgumentList` **不自動加引號**——本機路徑含空白（`LIN HONG`），每個路徑參數必須 `('"{0}"' -f $path)` 手動包，否則子行程無聲死亡、lock 不釋放。
  7. **hook 讀 stdin 用 UTF-8 StreamReader**（`[Console]::OpenStandardInput()` + UTF8，自動去 BOM）——`[Console]::In` 受 console code page（cp936）影響，live 環境曾因此 JSON 解析失敗、session_id 變 unknown；解析失敗時記診斷 log（len + 前 80 字）以便確診。
  8. **計數鍵不可依賴 stdin 解析出的值**——解析失敗會默默 fallback（如 unknown）導致計數語意全變（永不重置）；計數鍵用本地可靠來源（日期）。
- spec / plan：`resources/specs|plans/reflective_stop_hook_2026-06-04_*.md`。

---

**Maintainer note：** 本檔是 hooks 系統的 single source of truth，所有 hook 設計 / 變動 / 移除前都應該先查這檔再動手。若官方文檔升級或新 events 出現，請更新 §3 / §5。
