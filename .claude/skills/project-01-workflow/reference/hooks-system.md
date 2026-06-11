# Hooks 系統現況與維護

> 🎯 **何時讀本檔**：要新增 / 修改 / 移除 / debug 任何 hook，查某 hook 的行為與設計理由，或改 `settings.json` 的 hooks 段。寫 .ps1 的踩坑 → [hooks-gotchas.md](hooks-gotchas.md)。

## 目錄

- 已實作 hooks 一覽
- Flag file 協作架構（state/ 家族）
- stop-reflect（反思引擎）
- Exit / 輸出控制速查
- 確認不可行（不要再想）
- 維護指南
- 未實作但可用

## 已實作 hooks 一覽

| 檔名 | 事件 | matcher | 用途 |
|---|---|---|---|
| `block-git-add-bulk.ps1` | PreToolUse | Bash + `if:"Bash(git add *)"` gate | 擋 `git add -A` / `--all` / `.` |
| `block-windows-install.ps1` | PreToolUse | Bash\|PowerShell | 擋本機 `pip` / `npm` / `apt` install（pytest 例外） |
| `block-vendor-edit.ps1` | PreToolUse | Edit\|Write | 擋廠商 SDK 檔（ActionGroupControl/Board.py） |
| `state-mark-sales-dirty.ps1` | PostToolUse | Edit\|Write | 編 sales/* 時寫 flag |
| `state-clear-on-pytest.ps1` | PostToolUse | Bash\|PowerShell | pytest 跑過清 flag（兩 shell 工具都要掛——只掛 Bash 曾致 PowerShell 跑 pytest 後 Stop 誤報） |
| `check-traditional-chinese.ps1` | PostToolUse | Edit\|Write | 掃剛寫入檔的常見簡體字 → 純警示 |
| `stop-check-sales-pytest.ps1` | Stop | — | flag pending → block 一次（pending→reminded，不無限擋） |
| `stop-sync-pi.ps1` | Stop | — | origin/main 比 marker 落後 → sync Pi + 清 pycache，成功才前移 marker |
| `stop-check-codemap.ps1` | Stop | — | 結構變動（git 快照 diff）/ 死引用（codemap-health 重用）未反映到 code_map → block 一次（spec：codemap_guard_stop_hook_2026-06-07_spec.md） |
| `stop-reflect.ps1` | Stop | — | 背景反思（見下節） |
| `session-start-context.ps1` | SessionStart | — | 注入 branch / status / test 數快照；model 換代偵測 → 提醒重訪 `resources/watchlist.md` |
| `subagent-inject-rules.ps1` | SubagentStart | — | 只對 Explore/Plan（唯一跳過 CLAUDE.md 的 agent）注入「繁中＋文檔指標」；其餘 agent 原生載 CLAUDE.md，直接放行 |

註冊在 `.claude/settings.json`（project 層）；改 settings 後 file watcher 通常幾秒內自動 reload。

## Flag file 協作架構（state/ 家族）

Stop hook 輸入 JSON **沒有本輪 tool 歷史**（官方確認）→ 跨 hook 溝通走 `.claude/hooks/state/` flag 檔：

- **sales-dirty 三方**：編 sales/* → mark 寫 `pending`；pytest 跑過（PASS 或 FAIL）→ clear 刪 flag；Stop 時 `pending` → block 一次並改 `reminded`（防無限循環）、再編自動 reset 回 pending。
- **sync marker（單向，永不 block）**：`last-synced-commit.marker` 存上次成功 sync 的 origin/main SHA；落後才 SSH、成功才前移、失敗下輪自動重試。**no-BOM UTF-8 寫入**（BOM 會干擾 SHA 比對）。
- **model marker**：`last-model.txt`，SessionStart 比對換代（`model` 為 SessionStart 獨有輸入欄位，官方文檔確認；防禦式：欄位存在才比對）。
- **codemap 守門（state/codemap/）**：`last-snapshot.txt` 檔案清單基線（過關才前移）＋ `reminded.txt` 已提醒集合（當前 ⊆ 它即放行，包含比對非 hash）＋ `acked-deadrefs.txt` 已提醒死引用（同批只擋一次）。皆 no-BOM UTF-8。

## stop-reflect（反思引擎）

- 觸發：T1 = 本 turn 有 git 變動 → 素材 = diff（cap 400 行、`-c core.quotePath=false` 保中文檔名）；T2 = 連續 20 輪無反思 → transcript 尾段（30 條 / 8KB cap）。
- 引擎：Start-Process 背景拋 `reflect-worker.ps1` → `claude -p`（**Sonnet**——2026-06-07 自 Haiku 升級，實證誤報率 2/5；fresh context、prompt 經 stdin 餵入、禁工具）→ 提議 append `resources/reflections/proposals.md`（gitignored）。**只提議、絕不自動寫入規範檔。**
- marker **成功後**才前移（失敗 / 逾時不前移 → 下輪重審同素材）。
- 逾時防連環（2026-06-11 修）：`claude -p` timeout 300s（原 120s 統計 19% 逾時，叢發於主 session 重度用量時段）；**逾時後 lock 保留並 touch = 10 分鐘冷卻**——`Stop-Job` 殺不掉孤兒 claude 行程，立即釋放 lock 會讓下輪再 spawn 與孤兒並發 → 連環逾時。
- 防迴圈：`CLAUDE_REFLECT_CHILD=1` 旗標（三支 Stop hook 開頭早退）+ worker cwd 移出專案｜每日保險絲 100 呼叫｜語意去重（既有 slug 清單餵 prompt + 字串比對保底）｜lock 防並發（10 分鐘殭屍自清，兼作逾時冷卻）。
- 未讀提示：pending 數增加 → 下次 Stop 輸出**純 systemMessage**（Stop 無 hookSpecificOutput，見不可行清單）。
- state：`state/reflect/`；log：`reflect.log`（>1MB 輪轉 `.1`，stop-sync-pi.log 同）。關閉：settings 移除或 `$DAILY_CAP` 設 0。
- spec：`resources/specs/reflective_stop_hook_2026-06-04_spec.md`、`reflect_hardening_2026-06-05_spec.md`。

## Exit / 輸出控制速查（非官方全表，只留本專案用到的）

- exit 0 = success（stdout：SessionStart 自動進 context，其他多進 debug log）；exit 2 = blocking error（stderr 給 Claude）；其他非零 = non-blocking notice。
- 能 block 的事件：PreToolUse（`permissionDecision:deny` + exit 0，本專案三支 block hook 用法）、UserPromptSubmit、Stop（`decision:block`+reason）。
- 注入 context：`hookSpecificOutput.additionalContext`（SessionStart / SubagentStart / PreToolUse / PostToolUse…）。
- 通用欄位：`systemMessage`（給 user 的警示）、`continue:false`、`suppressOutput`。

## 確認不可行（不要再想）

- ❌ Stop hook 讀不到本輪 tool 歷史（官方確認）→ 走 flag file。
- ❌ **Stop 沒有 hookSpecificOutput union member**——帶 additionalContext 整包被 schema 拒收（連 systemMessage 一起吞，live 實測 2026-06-05）；要餵 model 只能 `decision:block`（與永不 block 原則衝突，不採）。
- ❌ SessionStart 不能 block。
- ❌ Subagent 內 Stop 不 fire（自動轉 SubagentStop）→ stop-* 三支不會被 subagent 誤觸發。
- ❌ PostToolUse 只在 tool 成功時 fire（失敗是 PostToolUseFailure）。
- ❌ Hook 不能呼叫 Claude 工具（AskUserQuestion / Read 等）——只能 shell / HTTP / MCP。
- ❌ Stop / SessionStart / SubagentStart 等事件不支援 matcher（寫了被靜默忽略）。

## 維護指南

1. 改 hook 必 EnterWorktree（`.claude/` tracked）；.ps1 必 UTF-8 BOM（→ [hooks-gotchas.md](hooks-gotchas.md)）。
2. 本地測試：`'{...stdin json...}' | powershell -NoProfile -File <script>.ps1`（用 5.1 對齊運行時）。
3. **hook 與其 worker 改參數介面必須原子合併**——worktree e2e 必跨版本（新 hook 配舊 worker → 無聲死亡），派發鏈驗證只能 merge 後在真實 turn 做。
4. 新增 hook：先查官方事件存在（https://code.claude.com/docs/en/hooks）→ 確認 decision pattern → 對 [hooks-gotchas.md](hooks-gotchas.md) 掃一遍 → 測邊界 → 更新本檔一覽表。
5. Debug 沒觸發：看 transcript hook error notice → 看 script 自寫 log → 確認 settings.json 在 project 層。

## 未實作但可用（要做時查官方細節）

`PreCompact`（壓縮前注入保留脈絡）｜`FileChanged`+`watchPaths`（外部編輯器改檔觸發）｜`prompt`/`agent` 型 hook（複雜判斷給模型）｜`decision:"ask"`（破壞性操作轉人工確認）｜`Notification` → 手機推播｜`CLAUDE_ENV_FILE`（SessionStart 設 Bash 環境變數）。
