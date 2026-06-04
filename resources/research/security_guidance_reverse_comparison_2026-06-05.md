# security-guidance plugin 逆向比對筆記（vs 手搓反思 Stop hook）

> 日期：2026-06-05 ｜ 來源：`github.com/anthropics/claude-plugins-official` `plugins/security-guidance` **v2.0.3**（sparse clone 原始碼逐檔分析，未安裝）
> 比對對象：本專案手搓 `stop-reflect.ps1` + `reflect-worker.ps1`（spec → `resources/specs/reflective_stop_hook_2026-06-04_spec.md`）
> 方法：4 個並行 agent 分工摘要 15 檔（~400KB Python）→ 關鍵常數逐項 Select-String 抽查證實 → 本筆記綜合。行號引用以 v2.0.3 為準。

## 1. 官方架構總覽

- **單一入口**：`security_reminder_hook.py` 吃全部事件（UserPromptSubmit / PostToolUse / Stop），由 stdin JSON 的 `hook_event_name` 路由（srh.py:2177-2245）；非每事件一檔。
- **三層**：① pattern 正則警示（25 條規則，免 LLM）② Stop 時 LLM diff review ③ git commit/push 時 agentic review（Agent SDK，Read/Grep/Glob 跨檔追資料流）。
- **v2 的關鍵機制 = `asyncRewake`**（hooks.json）：hook 在背景跑 LLM，**exit 2 + `rewakeMessage` 把發現「敲醒」主 agent 修**——不是被動提示，是主動喚回。配套欄位 `rewakeSummary`（通知一行摘要）。
- **launcher**：`sg-python.sh` 三輪探測 python（3.13→3.10 精確版 → 裸 python3 → 任意 3.x），`PYTHONUTF8=1` 強制 UTF-8（他們也踩 cp1252 編碼坑，#2056/#2099）。
- **SessionStart**：`ensure_agent_sdk.py` 自建 venv 裝 Agent SDK（哨兵檔 O_EXCL 防並發、5 分鐘殭屍容限——與我們 lock 設計同構）。

## 2. 維度對照表

| 維度 | 官方 security-guidance | 手搓 stop-reflect | 評 |
|---|---|---|---|
| 目的 | 找安全漏洞→敲醒 agent 修 code | 找學習點→提議進 proposals.md 人定奪 | 目的不同，機制同構 |
| 背景化 | `asyncRewake`（harness 原生：背景跑→exit 2 喚回） | Start-Process detached worker + 下輪一行提示 | 官方走 harness 特性；我們手搓等價物 |
| 遞迴守衛 | stdin 的 `stop_hook_active` 欄位（srh.py:1843，harness 在 asyncRewake Stop 進行中全程置 true） | 自設 `CLAUDE_REFLECT_CHILD` env var | 兩者皆有效；官方用 harness 原生欄位 |
| 迴圈上限 | `MAX_STOP_HOOK_FIRINGS=3`/rewake 迴圈，TTL **120s** 自動過期（diffstate.py:29） | 每日保險絲 100 | 官方限「單迴圈連發」、我們限「日總量」——互補概念 |
| 變動基準 | UserPromptSubmit 時 `git stash create` 快照 SHA（含未提交；不含 untracked→另存 mtime 快照過濾舊檔）；`merge-base --is-ancestor` 偵測線性推進決定 diff base | HEAD ≠ last-reflected marker ＋ `git status` 非空 | stash-create 基準涵蓋面更精確；我們的 marker 法簡單夠用 |
| 素材 cap | 30 檔（**風險 token 排序取前 30**，>10×=300 檔才真 bail；srh.py:1999）；80KB/檔、400KB 總（review_api.py:27-28）；排除 node_modules/.min.js/.lock/generated | 30 檔 / 400 行截斷 | 官方「優先化而非硬截」是亮點 |
| 模型 | **opus-4-7**（賭精確度——偽陽性才是解除安裝主因；llm.py:121-125）、thinking 10000、max_tokens 16000、429/5xx 指數退避×3、5xx 自動降 sonnet | haiku、單發、120s timeout、無 retry | 成本姿態不同：他們產品級、我們夠用就好 |
| 呼叫途徑 | 1P 直 HTTP API → OAuth fallback（sticky）→ 3P 走 Agent SDK | `claude -p` stdin 餵 prompt | 我們綁 CLI 最簡；官方要跨供應商 |
| 防過度反思 | prompt 強制「具體攻擊路徑」+ **明列 NOT-flag 清單**（llm.py:978-997）+ severity 過濾掉 low + agentic 第二階段**自我反駁**（預設=存活，有具體證據才殺） | prompt 嚴格門檻四條件 + NONE | 同哲學；NOT-flag 反例清單與自我反駁是可學的強化 |
| 去重 | key=`(filePath, category)`（vulnerableCode 會漂移故不用）；previous_findings TTL 3600s；**已報未修者故意不去重**（再提醒）；late dedup 防並發 race | slug 清單餵 prompt 語意去重 | key 設計值得記：選「穩定欄位」當 key |
| 失敗處理 | **fail-open + restore**：API 失敗→回復 state（baseline/touched_paths），下輪重審不漏（srh.py:2085-2087） | log 後靜默結束；marker 已在派發時前移→**該輪素材永久跳過** | ⚠️ 我們的真差距，見 §4-1 |
| 編碼 | `PYTHONUTF8=1`；subprocess 全面禁 `text=True`，utf-8+`errors=replace`；**`git -c core.quotePath=false`** 讓中文檔名輸出原始 UTF-8（gitutil.py:29-39） | BOM ps1 + StreamReader stdin + job 內 OutputEncoding | 同坑同解；quotePath 我們沒處理，見 §4-2 |
| state | `~/.claude/security/` 集中、fcntl 鎖、30 天 GC、session key 淨化限 128 字、CCR 遠端 session id 優先 | `.claude/hooks/state/reflect/`、lock 檔、7 天 prune | 同構 |
| log | 1MB 自動輪轉、目錄 0700（_base.py:53-71） | reflect.log 無上限 | 見 §4-3 |
| 遙測 | 每次呼叫記 token/cost（內建定價表）、23 類 bootstrap 失敗碼 | log 一行摘要 | 產品級需求，我們不需要 |
| 擴充 | 使用者可放 `claude-security-guidance.md`（8KB cap）+ 自訂 pattern YAML（50 條、ReDoS 靜態檢查） | 無 | 我們的「擴充」= 直接改 prompt，夠用 |

## 3. 手搓版已與官方一致的設計（驗證通過）

1. **做事/評判分離 + fresh context**：官方 Stop review 也是另開模型呼叫看 diff，無 sunk cost。
2. **不 block、背景跑、turn 零延遲**：官方全三層皆背景化；我們 detached worker 同效。
3. **嚴格門檻 prompt 防「為報而報」**：官方 NOT-flag 清單 ≈ 我們的四條件+NONE。
4. **lock + 殭屍容限**：官方哨兵檔 O_EXCL + 300s 容限 ≈ 我們 lock + 10 分鐘容限。
5. **硬上限多層化**：官方 3-fire/20-per-hour/30-files ≈ 我們 daily-100/30 檔/400 行/3 條提議。
6. **UTF-8 編碼全鏈路明示**：雙方都被 Windows code page 咬過、解法同向（強制 UTF-8 + 容錯 decode）。
7. **state 集中 + 過期清理**：同構。

## 4. 候選採納清單（按值得程度排序）

1. **失敗 restore（值得做，小改）**：worker 呼叫 claude 失敗時不該讓素材永久跳過。現狀 marker 在派發時前移，claude 掛了該輪 diff 就丟了。改法：worker 成功後才前移 marker（marker 寫入從 stop-reflect 移到 worker 成功路徑），或失敗時回寫舊值。官方對應：`restore_unreviewed_stop_state()`。
2. **`git -c core.quotePath=false`（值得做，一行）**：本專案有中文檔名（resources/ 下），預設 git 會輸出 `"\346\211\213..."` 八進位轉義，餵給評審模型等於亂碼。在 stop-reflect 收集素材的 git diff 指令加此 flag。
3. **reflect.log 輪轉（值得做，幾行）**：官方 1MB 輪轉到 `.1`。我們 log 無上限，長期跑會膨脹。
4. **`stop_hook_active` 第二道守衛（看情況）**：stdin 本來就帶這欄位，加一行判斷零成本；但我們 env var 守衛已覆蓋同場景，屬冗餘保險。
5. **asyncRewake（先觀察，潛在大升級）**：若本機 CC 版本支援（hooks.json 語法 `asyncRewake: true` + `rewakeMessage`），可把「被動一行提示」升級成「反思完成主動敲醒 agent 看提議」。**但**：我們的設計哲學是人定奪、不打擾，敲醒反而違反「不吵」原則——若採納應只用於高價值提議（如紅線級）。需先驗證欄位支援度再議。
6. **風險排序代替硬截斷（不急）**：素材超 30 檔時按風險 token 排序取前 30 而非位置截斷。我們的 turn 級 diff 很少超 30 檔，觸發率低。

## 5. 明確不採納（記理由防回鍋）

- **Agent SDK + venv bootstrap**：為跨供應商與 agentic 多回合而生；我們 `claude -p` 單發已覆蓋需求，引入 SDK = 重量級依賴。
- **opus + thinking 10000**：他們賭精確度因為誤報導致解除安裝；我們的提議有人工把關，haiku 誤報成本≈0。
- **dual-OR 雙模型合議 / agentic-fallback 競速**：2× 成本換 recall，產品級需求。
- **遙測/定價表/23 類失敗碼**：單人專案 log 一行足矣。
- **pattern 層 + 擴充 YAML**：紅線已有 PreToolUse 確定性 block（spec §8 既有結論，原始碼看完後維持）。

## 6. 聰明細節拾遺（無關採納，純學習）

- **stash create 當快照**：`git stash create` 產生「HEAD+工作樹」匿名 commit SHA 而不動工作樹——比 status+diff 組合更原子。
- **untracked 用 mtime 快照過濾**：解「舊 untracked 檔每輪重複被審」——我們的 proposals.md gitignore 決策（避免工作樹常駐 dirty）是同一問題的另一解。
- **「已報未修」故意不去重**：去重只防雜訊，不防怠惰——同 key 再現=修復不完整，照報。
- **metrics 第一行單行輸出**：CC 只掃 stdout 第一個 `{` 行，all-in-one json.dumps 防 rewakeSummary 被丟。
- **`-c core.hooksPath=/dev/null` + `core.fsmonitor=false`**：hook 裡呼 git 時隔離使用者 git hooks，防套娃與劫持。
- **ReDoS 靜態檢查**收使用者正則：嵌套量詞 `(a+)*`、wildcard 群組、前綴重疊——收任何使用者輸入的 pattern 前先驗。
- **provenance 標籤**：注入文本帶 `[from security-guidance@... plugin]`，讓模型分得清「這不是使用者說的」。

## 7. 來源檔案速查（job tmp 內 sparse clone，會隨 job 清掉；要重看再 clone）

| 檔 | 大小 | 職責 |
|---|---|---|
| `hooks/security_reminder_hook.py` | 114KB | 主入口：事件路由、觸發判斷、限流、輸出 |
| `hooks/llm.py` | 117KB | 模型呼叫：API/SDK 路由、retry、review prompt、解析 |
| `hooks/gitutil.py` | 36KB | git 素材：diff、優先排序、編碼防護 |
| `hooks/diffstate.py` | 21KB | baseline 狀態機、TTL、restore |
| `hooks/_base.py` / `session_state.py` | 16KB | log 輪轉、state 鎖、GC |
| `hooks/patterns.py` / `extensibility.py` / `review_api.py` | 57KB | pattern 層、使用者擴充、agentic API |
| `hooks/ensure_agent_sdk.py` / `sg-python.sh` | 29KB | bootstrap：python 探測、venv、降級 |
