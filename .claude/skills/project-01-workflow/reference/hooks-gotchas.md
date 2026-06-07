# PowerShell / hooks 踩坑全集

> 🎯 **何時讀本檔**：要寫 / 改**任何 .ps1**（hook、worker、skill script），或 debug hook 的編碼 / regex / stdin / 背景行程問題。系統現況與維護流程 → [hooks-system.md](hooks-system.md)。

## 目錄

- 編碼（#1-6：BOM / stdout / stdin / Select-String / Start-Job / marker）
- 背景行程 / CLI 呼叫（#7-12、21）
- Regex / matcher（#13-15：一寬一嚴 + 4 case 測試法）
- 事件行為（#16-20）
- 設計原則（fail-open / -NoProfile / 一次性提醒）

## 編碼（本機 code page = cp936 簡中，全部坑的根源）

1. **.ps1 必須 UTF-8 with BOM**——PS 5.1 讀無 BOM 檔用 ANSI 解碼 → 含中文必 parse error。兩個會產生無 BOM 檔的來源：**Claude Code 的 Write 工具**（寫完必補 BOM）、**pwsh 7 `Set-Content -Encoding UTF8`**（no-BOM，還會洗掉既有 BOM；要用 `utf8BOM`）。補 BOM：
   ```powershell
   [System.IO.File]::WriteAllText($p, (Get-Content $p -Raw -Encoding UTF8), (New-Object System.Text.UTF8Encoding $true))
   ```
2. **stdout 給 Claude 的 hook 開頭必設**：`[Console]::OutputEncoding = UTF8` + `$OutputEncoding = UTF8Encoding($false)`——否則繁中輸出被當 cp936 變亂碼（注入內容變廢、deny reason 不可讀）。1 是 input 編碼、2 是 output 編碼，**兩個都要**。
3. **讀 stdin 用 UTF-8 StreamReader**（`[Console]::OpenStandardInput()` + UTF8）——`[Console]::In` 受 console code page 影響，曾致 JSON 解析失敗、session_id 變 unknown。解析失敗記診斷 log（len + 前 80 字）。
4. **絕不可用 `Select-String -Path` 讀無 BOM UTF-8 檔**（cp936 誤解碼，全形匹配必失敗）——一律 `[System.IO.File]::ReadAllText(..., UTF8)`。
5. **Start-Job 子 host 要自設 OutputEncoding**（與主腳本各自獨立），否則子行程內 claude stdout 繁中亂碼。
6. **比對用 state 檔（如 SHA marker）用 no-BOM 寫入**——BOM 會混進比對值。

## 背景行程 / CLI 呼叫

7. **`Start-Process -ArgumentList` 不自動加引號**——路徑含空白（本機 `LIN HONG`）必須 `('"{0}"' -f $path)` 手動包，否則子行程無聲死亡、lock 不釋放。
8. **背景 job 呼 CLI 判成敗必帶回 `$LASTEXITCODE`**——`2>&1` 併流後錯誤文字也是非空輸出，「輸出非空＝成功」會把 auth / rate-limit / 無效 model 錯誤當成功。job 內 `[pscustomobject]@{ Out=...; Code=$LASTEXITCODE }` 一起回傳。
9. **`$ErrorActionPreference='Stop'` 會把 native command 的 stderr 雜訊當 terminating error**（git 進度訊息、OpenSSH post-quantum 警告都走 stderr）→ 跑 native command 段落 inline 改 `'Continue'`、以 `$LASTEXITCODE` 判成敗、finally 恢復。
10. **prompt 餵 `claude -p` 走 stdin**——免 3s stdin 偵測等待、免命令列長度上限、免引號轉義。
11. **計數鍵不可依賴 stdin 解析值**（解析失敗 fallback 成 unknown → 計數永不重置）——用本地可靠來源（如日期）。
12. **精確 slug 去重攔不住同義異名**——語意去重要把既有主題清單餵進模型 prompt，字串比對只做保底。
21. **PS-in-PS `-Command` 字串的內層 `\"` 轉義會被 native 命令列剝除**——`powershell -NoProfile -Command "... \"exit=$x\" ..."` 內層雙引號失效、內容變散 token（CommandNotFoundException）。修法：取值 / echo 移到**外層** shell 做；引號需求複雜時改 `-File` 帶參數或 here-string。（2026-06-07 codemap hook 驗證時實踩）

## Regex / matcher（一寬一嚴兩個經典）

13. **太寬誤抓**：`git add -A` 的 regex 掃整段 command 會誤擋「commit message 內含該字面」。根治：settings 該 hook entry 加 `"if": "Bash(git add *)"` gate——permission-rule 語法逐 subcommand 比對、引號內不解析 → 字面提及不 spawn、真 bulk add 照擋。
14. **太嚴漏抓**：`\bgit\s+push\b` 漏掉 `git -C "..." push`。修：`\bgit\b[^;&|\r\n]*?\bpush\s+origin\s+main\b`（容 git options、`[^;&|]` 擋跨 separator 誤匹配）。
15. **新 hook regex 必測 4 種 case**：simple form / `-C` form / `&&` chain / commit message 內含字面。

## 事件行為（官方語義，影響設計）

16. SessionStart 在 subagent 內是否 fire **官方未明說** → 防禦：查 stdin `agent_id`，存在即 silent exit。
17. `CLAUDE_PROJECT_DIR` 在 worktree 內指向 **worktree path**——要主 checkout 的東西（如 gitignored 的 sync_pi.ps1）需另行錨定。
18. SessionStart 每 session 都跑，**要快**（現行 ~200-400ms 可接受）；輸出要冪等（不寫死時間戳）。
19. **Gotcha M（subagent commit 落 main）**：hook 端僅記錄；完整處理鏈與防呆（`git branch --contains` 必驗）→ 權威在 [worktree.md](worktree.md)。
20. **背景 session 的 PostToolUse 非確定性**（有時不 fire，2026-05-27 實證）——這是 sync 改用 **Stop hook** 的原因（Stop 在所有 session 型態可靠 fire，2026-06-03 live + headless 雙實證）。新自動化避免依賴 PostToolUse 的必達性。

## 設計原則（從稽核與實戰沉澱）

- block hook 解析失敗 **fail-open**（`catch { exit 0 }`）——寧放過不誤殺。
- 每個 hook 都帶 `-NoProfile`（防 shell profile echo 污染 stdout JSON）。
- Stop 類提醒**一次性**（pending→reminded），避免無限 block deadlock。
