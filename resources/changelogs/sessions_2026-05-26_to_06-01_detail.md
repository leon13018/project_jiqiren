# 開發詳錄：2026-05-26 ~ 06-01 各 session 里程碑（自 roadmap.md 搬遷）

> 2026-06-07 自 `resources/roadmap.md` 逐字搬遷（原「✅ 已完成里程碑」章）。內容為 session 級詳錄，比 changelog 主表更細。

## ✅ 已完成里程碑（不再是待辦）

### 2026-05-26 — P0-P8 multi-agent review-driven refactor 完成

派 4 個視角 subagent（結構/檔名 + 狀態機正確性 + NLU 健壯性 + 主 agent 橫切面）審查 myProgram/ 後產出 8 階段 Roadmap，全部完成 + 使用者實機驗證：
- **P0**：keyword 歧義急救（strict-match 短詞 + C-2 顧客錢包逆向錯誤修補）
- **P1**：Dead code 清理（do_action / _dialog_c2_auto_checkout）+ 廠商檔搬 `myProgram/vendor/`
- **P2**：L4 第 7 次催促 silent fix + dialog 抽 `_dialog_main_loop` helper（消 113 行 copy-paste）
- **P3**：checkout confirm UX 對齊（4-valued return + C-2 YES 直接 L4 + L2 timeout 顧客語氣）
- **P4**：keyword 覆蓋率補強（L3_STRICT 補「全部取消」/「iced tea」/「樂透」alias）
- **P5**：wire-up 健壯化（`normalize_input` IO 邊界 helper / `unmute_opencv` 對稱）
- **P6**：結構命名一致化（`myProgram.py` → `main.py` + states 改層編號制）
- **P7**：NLU 拆出 `product_parser.py`（intent 與商品實體分離）
- **P8**：`constants.py` 拆 subpackage（8 子模組 + backward compat re-export）

完整報告 + 6 視角原始輸出 + Roadmap：`resources/reviews/2026-05-26_myProgram_multi-agent-review.md`。

### 2026-05-26（同日）— P8 後 UX 補強迴圈

使用者實機測試 P0-P8 後即時踩出 5 條 UX 問題並修補：
- `696ae6a` L1 主選單嚴格匹配（多字元亂打「123/3434」不再誤進模式）
- `354c037` L4 客服模式移除 print_terminal dup（S1 chat-driven 視覺重複）
- `0016e23` L4「等待安撫」intent — 顧客「好/嗯/等等我/ok」溫和回應（**方案 A**：ack 重設 6s timer）
- `0236879` L4 從 A 反轉為**方案 B**：wall-clock 60s 全程預算（防 ack spam 無限拖延；見 [[l4-ack-wallclock-budget-design]]）
- `f970a81` L2/L3「想買無商品」intent — 顧客「有/要/想買」肯定詞無具體商品名 → 溫和引導，不 ++unclear/think

從 184 → 197 tests。所有 commits 已 push + Pi sync。

### 2026-05-26（同日）— Wave 0-10 review-driven 二輪修補完成

依 `resources/reviews/2026-05-26_myProgram_comprehensive_review.md`（4 視角 ~77 findings）的第 7 章 5 層執行：

- **Wave 0** 測試安全網：補 `test_logic.py`（6 個）+ `test_nlu_boundary.py`（23 個 xfail 預先紅燈）
- **Wave 1** dead code 清理（A5/A6/A8/C3）
- **Wave 2** 型別精化（Cart TypeAlias + classify_intent Literal）
- **Wave 3** NLU 集中修：23 個 xfail 全綠（HP-1/2/4 + B5/B16 + C12/C18 + D10）
- **Wave 4** cart 邊界防護（add_item assert + MAX_QTY_PER_ITEM=50）
- **Wave 5** L3/L4 即時 UX（HP-3 qty followup 困死 + HP-5 confirm 列總金額 + 文案改寫等 9 條）
- **Wave 6** 常數歸位 + 私名提升 + opencv_disable default 移除（A1/A7/A11/A14/D14；牽 15 檔，subagent 自動補 95 處 fixture）
- **Wave 7a** 文案 + 業務微調 6 條（C13 思考次數 3→4 + C22 dedup 改覆寫 + C17/C21/C23 等）
- **Wave 7b** L1 q confirm（C14 兩次 q 才退）+ show_hawk_help callback（B21）
- **Wave 10** INTENTIONAL 文件化 7 條（B13/B14/B18/B22/C7/D3/D9）

**Wave 7-10 v1（sonnet）踩 4 坑**（Gotcha M / 雙寫 main / pytest 失準 / 漏更新 test）→ 全 revert 用 `git revert`（無 force push）→ **v2 換 opus xhigh + 6 招防護重做零坑**。方法論記錄在 [[wave-workflow-6-protections]]。

從 197 → **233 tests**（Wave 0 +23 nlu_boundary，但都 xfail；Wave 0 +6 logic；Wave 4 +5 cart guards；Wave 7b +2 q→非q→q 不退出 = 197+6+5+2-23(xfail 轉綠)+...= 實測 233）。所有 commits 已 push + Pi sync 到 commit `b84f761`。

**review 第 7 章 5 層完成度**：第一 / 三 / 五層 + INTENTIONAL 文件化 全完成；**第二層（S3+ 必修）+ 第四層（大型重構）延後**（綁定 S3 開工 / demo 穩定後）。

### 2026-05-27 — Wave 4 hotfix 1-3 + dialog 客服 re-speak fix

Pi 實機驗證 Wave 0-10 後使用者踩出 4 個 runtime UX issue，當天連續修補：

- **Hotfix 1**（`f37d11a`）`_qty_follow_up_sub_loop` 加 caller-side cart cap 業務檢查 + speak retry — Pi 上輸入「34435454545454545」觸發 `cart.add_item` assertion crash（add_item 內 `assert qty <= MAX_QTY_PER_ITEM` 為 fail-fast，但 caller 沒先 cap → AssertionError 殺整個程式）。修法：caller 算 remaining = MAX_QTY_PER_ITEM - existing，cap qty 後加 + speak 通知 + 重問。+4 tests。
- **Hotfix 2**（`cd393b2`）`resolve_and_add_products` 同類 cart cap 業務檢查 — Hotfix 1 subagent 順手發現第二條路徑有同根因 risk（line 62 for loop 內也直呼 add_item）。修法：cap-to-remaining + speak 通知（one-shot 路徑不重問）。+5 tests。
- **Hotfix 3**（`50d8b67`）`myProgram/main.py` UnicodeDecodeError noisy debug — Pi 輸入「皆可」觸發 UnicodeDecodeError，原 except 印一行籠統訊息就吃掉。改 noisy 印 `codec` / `reason` / `start-end` / **raw bytes hex** + 友善 hint。EOFError 拆獨立 except。Pi locale 已確認全 UTF-8（疑似 IME / SSH transit / 異常 byte 序列），需 hex 才能定位根因。+4 tests。
- **客服 re-speak prompt fix**（`a2eee27`）L2/L3 dialog 3 處客服分支印電話後補 `speak(L2_ENTRY_PROMPT)` / `speak(L3_REASK)`（依 cart 狀態） — Pi 實機發現顧客講「客服」印電話後直接落到下個 read prompt，失去對話上下文。掃了 3 處同類路徑（主迴圈 + 2 個沉默期 helper dispatch_inner）一次修完。+2 tests。

**從 233 → 248 tests**（+4 hotfix1 +5 hotfix2 +4 hotfix3 +2 re-speak = +15 = 248）。所有 commits 已 push + Pi sync 到 commit `a2eee27`。Hotfix 1+3 用 opus xhigh subagent + 6 招防護零踩坑（見 [[wave-workflow-6-protections]]）；hotfix 2 同；re-speak fix 主 agent 直寫（範圍 3 處 surgical）。

### 2026-05-27（同日）— S2 同步 TTS + S4 非阻塞 worker + 9 條 UX 補強迴圈

接續 Wave 4 hotfix 之後，跑完整 S2 → S4 incremental-rebuild + 系列 Pi 實機 demo 踩坑修補（**14 commits**）。**248 → 245 tests**（L5 mute 移除 -1 + stdin reconfigure UnicodeDecodeError test 移除 -2）。

**Incremental rebuild 進展**（commits）：
- **S2 同步 TTS 落地**（`3afc9ac`）— `myProgram/tts.py` 新建：`edge_tts.Communicate(...).save("/tmp/last_tts.mp3")` + `subprocess.run(["mpg123", "-q", path])` 同步阻塞至播完；import edge_tts fail-fast；runtime 失敗 noisy print + return；`main.py` speak callback 改 call `tts.speak`（lazy import 防 Windows pytest 觸發 ModuleNotFoundError）。pineedtodo `2026-05-27_S2_tts_verify.md` 寫 Pi 端驗證步驟。
- **S3 跳過**（incremental-rebuild rule「S3 後可暫停 S4-S7」反向應用：S3/S4 互不依賴可亂序）。
- **S4 非阻塞 TTS worker**（`179e55b`，opus xhigh + 6 招）— `class TtsWorker` daemon thread + `queue.Queue` FIFO + `threading.Lock` 保護 `_proc` + `shutdown()` lock-protected terminate；`speak()` 非阻塞（caller print + put queue 立即 return）；`main()` finally `tts.shutdown()`。**設計關鍵**：Lock 只包 `_proc` 賦值/讀/terminate 三短瞬間**不**包 wait（否則 shutdown defeat）；預設 FIFO 不中斷（中斷是 S7）。**解使用者三個訴求**：q 立刻響應 / exit 時最後音檔立刻停 / 為 S6 真 opencv 偵測鋪路。

**UX 補強迴圈 9 條**（連續修補 Pi 實機踩到的）：
- `5f30dc6` ALSA buffer drain 0.3s（mpg123 退出 ALSA buffer 殘留被下個 mpg123 沖掉，「付款成功」尾巴被截）
- `4672f1b` **L5 移除冗餘 `mute_opencv(THANK_DELAY)`** — 會被緊隨 subroutine_a `mute_opencv(OPENCV_MUTE)` 覆寫，純規格冗餘（248→247，刪 1 個 test）
- `b50b954` 4 條 TTS 文案口語化（移除括號內「終端輸入 1=X」雜訊）
- `a9c26ff` **`sys.stdin.reconfigure(encoding='utf-8', errors='replace')`** — Pi 端 stdin TextIOWrapper buffer 殘留 partial UTF-8 byte 害 input() raise UnicodeDecodeError（「刮」leading byte 0xe5 被當「期待 continuation byte」報誤）；移除 2 個 UnicodeDecodeError test（247→245）
- `c0cb5b7` cart cap 4 條 speak f-string 改自然口語
- `1876cc6` 'c' 鍵 mute 期間嚴格行為 + `sleep` callback 改 `time.sleep` 真等待（L5 thanks 3s 禮貌間隔）
- `f7dab09` **mpg123 `stdin=subprocess.DEVNULL`** — 防 mpg123 偷讀父程序 stdin 攔截 user dialog input（Pi 實機踩到「L4 entry 期間打字 → mpg123 收到 q → 印「Stopped.」+ quit 中斷 dialog flow」）
- `48b9d03` L1 q-confirm 改 nested while 不重印 banner
- `f61a497` **L4 客服 + final-confirm 繼續後 re-speak entry prompt**（對齊 L2/L3 dialog 客服 re-speak fix `a2eee27` pattern）

**Hook 配套**（清 Pi pycache 解 stale .pyc bug）：
- `600a4cc` + `034846d` — `auto-sync-pi.ps1` 加 SSH 清 Pi `__pycache__`（Pi `git pull` 拉到 latest source 但 Python 仍 import cached .pyc → user 看到 demo「沒」走 unclear 但實際 NLU 已修補）；**獨立 try/catch**（sync_pi.ps1 內 git stderr progress msg 被 PowerShell 當 ErrorRecord 拋出，會跳過後續清理）。詳細根因 + 修補：[[python-pycache-stale-on-pull]]。

**新增 memory 三條**：
- [[tts-prompt-as-ux-pacing]] — 對話 ack speak 不是冗餘是 loading-bar 等價 UX pacing
- [[ux-over-technical-correctness]] — 主原則：先試技術優化 → 不能 → 用心理學掩蓋極限；最終目的是「使用者當下體驗好」
- [[python-pycache-stale-on-pull]] — Pi `git pull` 後 Python pyc 殘留問題 + hook 解法

**S2/S4 session 結束狀態**（commit `028ac3f`）：
- main HEAD f61a497 → 028ac3f（含 docs sync）
- pytest sales/ **245 passed**
- TTS pipeline 完整（fail-fast import / noisy runtime / ALSA drain / stdin DEVNULL / worker thread / shutdown cleanup）
- L1-L5 dialog UX 細節已修補（'c' 鍵 mute / sleep real / L4 re-speak / L1 q-confirm 不重印 banner / 4 條 cart cap 文案 / 4 條 confirm 文案）
- Hook 系統：sync_pi + clear pycache 獨立 try/catch
- **下一步：使用者繼續修 S2**（user 明示）— 可能是 S2 / S4 範圍內的對話 UX / TTS 文案 / dialog flow 後續細節

### 2026-05-27（同日）— S3 同步動作 callback 接入（incremental-rebuild 第 3 步，跳回補做）

接續 S2/S4 session 後使用者宣告「S2 修的差不多了」，討論並對齊 S3 mapping 後派 opus xhigh subagent + 6 招防護實作。

**設計對齊（與使用者 AskUserQuestion 對齊三回合確認）：**
- 範圍最小切片 — 只做 `Act.runAction` 同步阻塞；不碰 Board 頭部舵機 / 不做場景組合 / 不呼叫 stopAction / 不加 cancel Event
- 動作觸發點 5 個（不只 L4+L5，使用者要求 5 層全加，新增自訂 L2.d6a / L3.d6a 配合）
- L1 hawk 只 entry 跑一次（servo 過熱防護；後續輪播留 S5 worker）

**動作 mapping：**
| 層 | 動作 | 對應 .d6a |
|---|---|---|
| L1 hawk entry | `wave_hand` | 廠商原生 |
| L2 dialog entry（cart 空） | `L2` | 使用者自訂 |
| L3 dialog entry（cart 非空） | `L3` | 使用者自訂 |
| L4 鏈路 A（主 dispatcher + 客服模式 2 處） | `bow` | 廠商原生 |
| L5 entry | `wave_hand` | 廠商原生 |

**實作（commit `888ac76`）：**
- 新增 `myProgram/sales/constants/actions.py`（5 個 ACTION_* 常數）+ `constants/__init__.py` re-export
- `main.py` 加 `do_action` callback（lazy vendor import 對齊 speak pattern；fail-fast Pi-only）
- `logic.py` 簽名加 `do_action` 並傳遞給 4 個 state callsite（l1 / dialog / l4 / l5）
- 5 個 state files 簽名擴 + 觸發點插入：`l1.py _run_l1_hawk` / `l2_l3_dialog.py run_dialog` / `l4.py _l4_dispatch_response + _l4_service_mode 兩處` / `l5.py run_l5`

**架構選項 C 維持：** sales/ 嚴格不 `from myProgram.vendor` import；動作名字串從 `myProgram.sales.constants.actions` 取。grep 驗證 0 命中 vendor import。

**Tests 245 → 252：** fixture sweep 131 callsite（test_states.py + test_logic.py）加 `do_action=lambda *a, **k: None`；+7 新測（5 個觸發點各 1 + L4 客服路徑 + L1 hawk subsequent rounds NOT-called invariant）。subagent programmatic 一次 inject 131 fixture（不是 131 個 Edit call）+ idempotency check + 完整 pytest 雙保險。

**Gotcha M 不踩：** subagent 自驗 `git branch --contains 888ac76` 顯示 `worktree-s3-sync-action`（不含 main）。主 agent 也在 worktree 內跑 pytest 雙保險 252 passed。

**S3 session 結束狀態：**
- worktree HEAD `888ac76`（subagent code commit）+ 收尾 commit（pineedtodo + projectStructure docs）
- pytest sales/ **252 passed**
- 5 個觸發點 grep 驗證到位（l1.py:243 / l2_l3_dialog.py:104 / l4.py:366+425 / l5.py:50）
- pineedtodo `2026-05-27_S3_action_verify.md` 列 Pi 端 4 步驟驗證流程（L2.d6a/L3.d6a 確認 / 個別動作 smoke / 全 flow 5 觸發點 / 連續 2 輪交易看 sticky flag）

### 2026-05-27/28 同 session — S3 後續 fixes（Pi demo 驅動）

**Pi demo 第一輪實測**：5 觸發點 console output 只 4 個印出 — L3 沒印 `[動作] L3`。根因：L3 動作只 trigger 在 `run_dialog` function entry，但 L2 加單成功後 dialog 直接 `speak(L2_C_ADDED)+speak(L3_ENTRY_PROMPT)` 沒重新進 entry。

**Fix 1（commit `750ab32`，主 agent 直寫）：** 在 cart empty→non-empty transition 兩處（`_dialog_dispatch_inner_l2` + `_dialog_main_loop` was_empty 分支）插 `do_action(ACTION_L3)`；`do_action` propagate 過 4 個 helper 簽名（L2 side）。+3 tests。Pi demo 第二輪 5 觸發點全到位。

**Pi demo 第二輪後**：使用者要求進 L4 等掃碼前加引導動作（point_screen 指螢幕）。

**Fix 2（commit `c893de0`，主 agent 直寫）：** 新增 `ACTION_L3_CHECKOUT_GO = "point_screen"`，在兩處 `speak(L3_C1_CHECKOUT_GO)` 後插 `do_action(ACTION_L3_CHECKOUT_GO)`（`_dialog_dispatch_inner_l3` + `_dialog_main_loop` 結帳路徑）。順手補 Fix 1 漏的 L3-side helper propagation（`_dialog_think_silence_l3` / `_dialog_dispatch_inner_l3` 簽名 + main_loop call silence_l3 處傳遞）— 既有 tests 沒 cover 該 path 所以沒 fail 浮上，但 Pi 跑 silence 期內結帳會 NameError crash。+2 tests。

### 2026-05-27/28 同 session — Hook bug 雙層 fix（commit `aae2338` + `30ef910`）

**Pi 沒 sync 觸發 debug**：S3 push 後 Pi HEAD 仍是上輪 commit。

**Layer 2（hook script）：** `auto-sync-pi.ps1` 改 inline `$ErrorActionPreference='Continue'` 跑 native command，改 `$LASTEXITCODE` 判斷。修補 OpenSSH 新版量子安全警告（post-quantum kex）被 PowerShell `2>&1` 包成 NativeCommandError 中斷 try block 的問題。

**Layer 1（規則層）：** 實證 Claude Code background job session 內 PostToolUse hook **行為非 deterministic 不可依賴** — 同 session 內 5 次 push 中 2 次沒觸發、3 次觸發。規則加「Background session 雙保險：永遠手動跑 `& sync_pi.ps1`」段（standard-workflow / worktree-workflow / NOTES.md Gotcha N / CLAUDE.md 警示 / 新 memory `background-session-hook-skip`）。

**新 memory 兩條（user-level）：** `background-session-hook-skip` / `vendor-runaction-silent-fail`（Pi demo 沒動作排查 4 步 checklist）。

### S3 階段最終狀態（2026-05-28，commit `c893de0`）

- main HEAD `c893de0` / Pi HEAD `c893de0`
- pytest sales/ **257 passed**（245 → +12 S3 tests）
- 6 個動作觸發點全到位 + Pi demo 驗證通過（5 觸發點 + L3→L4 transition point_screen）：
  - L1 hawk entry → wave_hand
  - L2 dialog entry (cart 空) → L2
  - L2→L3 transition (cart 變非空) → L3
  - L3→L4 transition (checkout confirm yes) → **point_screen**（新加）
  - L4 鏈路 A (掃碼成功) → bow
  - L5 entry → wave_hand
- L3 dialog mode 內後續加單**不**重跑動作（servo 過熱避；符合「每層只 entry 一次」精神）

### 2026-05-28 — Session B：subagent policy + S5 + UX 微調（合成 voice + TTS rate 三段式）

接續 S3 完成後使用者開新 session 推進。**6 commits 從 `63839e6 → 6341a16`**：

**A. Subagent dispatch default 從 sonnet 改 opus**（commit `63839e6`，主 agent 自寫）
使用者主動要求：派發 subagent / agent teams 預設模型升級 opus + prompt 內塞 xhigh effort。Why：[[wave-workflow-6-protections]] 已驗證 sonnet v1 跨檔任務踩 4 坑 vs opus xhigh v2 零坑，既然 opus xhigh 是「跨檔 refactor 安全選項」乾脆預設化省判斷成本。更新 3 個 `.claude/` 檔（CLAUDE.md / subagent-dispatch-protocol.md / bdd-tdd-workflow.md）+ 3 個 memory（MEMORY.md index / subagent_dispatch.md / worktree_workflow.md Co-Authored-By 範例）。Co-Authored-By trailer 預設 `Claude Opus 4.7`，研究類 / Explore 子 agent 可手動降回 sonnet。本 session 即首個 dogfood：派 5 個 subagent 全 opus，零踩坑（含 1 個研究類 web search 也用 opus 對齊 policy）。

**B. S5 非阻塞動作 worker 落地**（commit `9add5e5` + `b15513f`，opus xhigh subagent + 主 agent docs）
incremental-rebuild 第 5 步：新增 `myProgram/action.py`（154 行）完全鏡像 `tts.py` 的 `TtsWorker` 結構 — `class ActionWorker` daemon thread + `queue.Queue` FIFO + `do(name)` enqueue 立即返回 + `shutdown()` 清 queue + 守衛 stopAction；`main.py` `do_action` callback 從 `Act.runAction(name)` 同步阻塞改 `action.do(name)` enqueue；`main()` finally 加 `action.shutdown()` 對稱 `tts.shutdown`。**4 處刻意差異**：(1) 無 `self._proc` / `self._lock`（vendor 不是 subprocess，中斷靠 vendor `stop_action` 旗號）；(2) 無 ALSA drain；(3) 失敗單階段 catch Exception；(4) shutdown 守衛 `if Act.runningAction: Act.stopAction()` 避免 sticky 旗號污染下次 runAction（[[vendor-stop-action-sticky]]）。**Pi demo 驗證 4 劇本通過**：並行起、FIFO 順序、shutdown 不留尾巴、連續組。從此動作 + 語音兩個 worker 各自硬體通道真正並行。

**C. L2→L3 transition 兩條 speak 合成單一 utterance**（commit `7077b18`，opus xhigh subagent）
Pi demo 後使用者反饋 L2 加單成功後「[語音] 好的，已加入購物車」+「[語音] 請問還有額外需要購買的嗎？」中間斷一下。根因：S4 TTS worker 兩條 enqueue 之間有 synth round-trip + ALSA drain 0.3s 停頓。合成 `L2_TO_L3_TRANSITION = "好的，已加入購物車，請問還有額外需要購買的嗎？"`（逗號連貫）放 `constants/l3_text.py`；`l2_l3_dialog.py` 兩處 transition（line 247-248 + 595-596）改單條 `speak(L2_TO_L3_TRANSITION)`；保留原 `L2_C_ADDED` / `L3_ENTRY_PROMPT` 常數（其他 path 仍獨立使用 L3_ENTRY_PROMPT）。**Tests 257 不變**（assert 改文案）。Pi 實測流暢度符合預期。

**D. edge-tts 語速調整網路調研**（純研究，opus xhigh subagent + WebSearch / WebFetch）
派 subagent 查 edge-tts rate API。關鍵發現：
- `Communicate(text, voice, *, rate="+0%", volume="+0%", pitch="+0Hz")` keyword-only
- Client regex `^[+-]\d+%$`：**必帶正負號 + 只能整數**（`"50%"` / `"+50.5%"` 都 ValueError）
- Azure 服務端有效範圍 -50% ~ +100%（0.5x ~ 2x）超出截斷
- `zh-TW-HsiaoChenNeural` 跟所有 Neural voice 共用同條 prosody 管線，無 voice-specific bug
- 業界沒有「便利店」場景直接推薦值；subagent 推論 `-5% ~ -10%` 起點（放慢），但使用者選**加快**方向

**E. TTS rate 三段式落地 + 長句微調**（commits `66192de` + `6341a16`，主 agent 自寫）
使用者選「加快」方向 — 短句 +3% / 中句 +6% / 長句 +9%（先試）→ Pi 實測後長句仍偏慢 → 長句調 +12%。`tts.py` 加 5 個 module-level knob：`RATE_SHORT="+3%"` / `RATE_MEDIUM="+6%"` / `RATE_LONG="+12%"` / `MEDIUM_THRESHOLD=14` / `LONG_THRESHOLD=23` + `_pick_rate(text)` helper（`len(text)` 算字數含標點）。`_synthesize` 改 `Communicate(..., rate=_pick_rate(text))`。涵蓋分布：~10 條短（如 L4_A_PAY_SUCCESS 4 字）/ ~12 條中（如 L2_ENTRY_PROMPT 14 字）/ ~12 條長（如 L4_D_FINAL_PROMPT 37 字）。Pi 實測長句體感符合預期。

**F. 「3300」誤觸排查 — 非 bug 結案**
Pi demo 觀察到「紅茶5個 刮刮樂300張」輸入後語音回「您剛才要的 3300 張超過上限」。Windows 本機跑 `parse_products` 證實邏輯返 `[(冰紅茶, 5), (刮刮樂, 300)]` 正確 → 不是 product_parser bug。使用者反思：TTS 播音期間誤觸鍵盤 `3`，stdin buffer 殘留，下次 `input()` 收進去拼到「刮刮樂」與「300」之間變「3300張」，regex `\d+` 命中 3300。**stdin 與主線程 input() 的固有 race**，演示時手指注意可避免。未來 S6（非阻塞 input + 單 queue）/ STT 取代鍵盤即根治；目前不修。

### Session B 結束狀態（2026-05-28，commit `6341a16`）

- main HEAD `6341a16` / Pi HEAD `6341a16`
- pytest sales/ **257 passed**（不變，本 session 改動不涉 sales/ 業務邏輯 / test 邏輯）
- **incremental-rebuild 進度**：S1 ✅ S2 ✅ S3 ✅ S4 ✅ **S5 ✅** / S6 ⬜ / S7 ⬜
- TTS 三段式 rate 落地 + 長句 +12% / `myProgram/action.py` 非阻塞動作 worker 落地
- subagent dispatch default 升級 opus + xhigh，本 session 5 subagents 零踩坑驗證

### 2026-05-28 — Session C：S6 非阻塞 input（**5 個 commit 修補**）+ c2 三選一 + sales-coder subagent

接續 Session B 後使用者開新 session 推進 S6 + 連帶 UX 修補。**主 HEAD `6341a16` → `3f82638`**，共 11 個 commits（含一個 revert）。

#### A. S6 非阻塞 input + 單 reader thread + bytes-level stdin 根治（incremental-rebuild 第 6 步）

**主 commit `c3563b3`**（opus xhigh subagent）：新增 `myProgram/input_reader.py`（200 行）— `class InputReader` daemon thread + `queue.Queue` + `sys.stdin.buffer.readline()` bytes-level decode `errors="replace"`，module-level singleton `_reader`，對外 API `read(timeout)` / `shutdown()` 鏡像 `tts._worker` / `action._worker` pattern。`main.py` `read_terminal_key(timeout=0.1)` / `read_customer_input(timeout)` 內部從 `input()` 阻塞改 `input_reader.read(timeout)` 真 timeout。**移除** `sys.stdin.reconfigure(...)` hack（bytes-level decode 繞過 TextIOWrapper buffer 邏輯）。Subagent 自行偏離 plan 改 drain 為 **latest-wins** 語義（保留 user 剛打的最新一筆，避免「全清」race window 殺合法輸入）— 主 agent 審查接受。

**Pi demo 暴露 4 個 bug，連續修補（5 個 commits）：**

| commit | 修什麼 | 教訓 |
|---|---|---|
| `3625d56` | L1 busy loop — read_terminal_key default 從 `timeout=0.1` 改 `None` | polling cadence 是 caller-specific，default 不能設 polling |
| `25e8bb9` | (失敗嘗試) `sys.stdin.close()` 抑制 Fatal Python error 訊息 | 訊息壓掉但**底層 hang 沒解** |
| `d1fa68a` | hawk q-confirm — polling 空 read 不該 `_reset_q_confirm()` | 阻塞→polling 改造時所有 state machine 都要 audit「假設無輸入不會被觸發」 |
| `880936e` | `main()` finally 加 `os._exit(0)` 強退跳過 finalizer | daemon thread + C-level blocking syscall = interpreter shutdown 不乾淨 |
| `9931605` | **移除** `sys.stdin.close()` — 才讓 `os._exit` 真跑到 | Linux kernel `close(fd)` 不 unblock in-syscall read；`sys.stdin.close()` acquire BufferedReader lock 跟 daemon thread 持有的 lock 衝突 deadlock |

**完整教訓**見新 memory [[s6-non-blocking-input]]。**S6 退出 path 在 `9931605` 真正穩定**：第二個 q 後立即返回 shell prompt，無 Fatal error、無 hang。

**Tests 257 → 264**（+8 input_reader / -4 test_main_decode_error.py（reconfigure hack 沒了該 test 目標消失）/ +sweep `FakeKeyboardInput.read` 簽名加 timeout=None）。S6 主功能 + 退出 path 修補階段最終 264 PASS。

**Pi 端待驗證 3 條（user 沒完整跑完）**：
- L4 60s 真預算（進 L4 後完全不打字應 60s forced exit）
- 多 byte 根治「刮刮樂冰紅茶」連續輸入兩次無 UnicodeDecodeError
- hawk 期間按 q 立即退出（user 看過部分 trigger 但沒完整驗）

#### B. Cap retry sub-loop 三輪嘗試 + 全 revert

Pi demo 後 user 發現 `_qty_follow_up_sub_loop` 在「顧客超量被 cap 拒絕後 timeout」場景默默加 1 違反 expectation（[[confirm-default-must-be-conservative]]）。三輪嘗試 + 全 revert：

| commit | 設計 | user feedback |
|---|---|---|
| `595b66c` | cap retry timeout → cancel 此商品 + speak「好的，這次先不加 X」 | 「不要跳回 L2」 |
| `7173b50` | cap retry timeout → 重 speak 同 prompt + continue（infinite reprompt 直到答對 / 主動 reject）| 「不要 6s timeout 重 speak」 |
| `17d51b8` | cap retry 期間 read(timeout=None) 無限阻塞，完全無 timeout 行為 | （試完仍不滿） |
| `48c5312` | **Revert 三個 cap_retry attempts squash 為單一 revert commit**，回到 9931605 state | user ask revert 到「S6 退出剛修好」狀態 |

**結論**：cap retry「user 答錯後該怎麼辦」設計空間複雜，user expectation 沒對齊清楚；本 session 不處理，待後續迭代。既有 cap retry timeout default 加 1 行為仍是現況。

#### C. L3 C-2 第二段：二元 yes/no → 三選一（繼續/結帳/取消）

**commit `a1612d5`**（主 agent 自寫，原本派 subagent 但 subagent 暫停回報 scope conflict — 9 個既有 c2 tests 受新設計影響 + 設計矛盾 UX 問題）：

Pi demo 揭示 c2 二元 yes/no UX bug：顧客「不要」歧義（「不要結帳、繼續逛」vs「不要整單」）被當「拒絕整單」清 cart。重構三選一明確意圖：

- **CANCEL keyword**（取消 / 取消吧 / 幫我取消...）→ `_dialog_exit_a`：清 cart + speak L3_REJECT_THANKS + 退 L1
- **CONTINUE keyword**（繼續 / 繼續選購 / 選購商品...）→ `_dialog_main_loop`：不清 cart 重入
- **CHECKOUT keyword**（結 / 結賬 / 直接結賬...）→ `_c2_checkout_via_confirm`：經 `_dialog_checkout_confirm` 確認明細 → L4
- **6s timeout（silent）**→ `_c2_direct_checkout`：**直接 L4 跳過 confirm**（user 字面 promise「6 秒內未答將進行結賬」）
- 亂答 → 既有 silent 倒數（第一次提示「請說『繼續』、『結賬』或『取消』」）

「結」單字 strict-short 防 substring 誤命中「結束 / 結婚 / 結局」。新增 3 個 KEYWORDS_C2_* + 各自 STRICT_SHORT；新增 `C2_DECISION_TIMEOUT = 6`；改 `L3_C2_WARNING_TEMPLATE` 文案；重寫 `_dialog_c2_second_stage`；4 既有 c2 tests 改寫 + 1 新 strict-short「結」test。**Tests 264 → 265。**

完整設計記錄見新 memory [[c2-three-way-design]]。**Pi 端待驗證**：四條路徑（繼續 / 結帳 / 取消 / 6s timeout）。

#### D. sales-coder 自訂 subagent — frontmatter skills 預載 SKILL 完整內容

**commit `3f82638`**（主 agent 自寫，user 提示 + 派 claude-code-guide subagent 查文檔 + WebFetch 親自驗證）：

User 質疑「之前派 subagent 時有給看完整 karpathy-guidelines SKILL 嗎？」→ 調研發現**沒有**：之前 prompt 內只塞一句 reference + SubagentStart hook 也只注入 summary + Agent tool inline call 不支援 `skills` 參數。

新增 `.claude/agents/sales-coder.md` frontmatter 預載 SKILL 完整內容：
```yaml
---
name: sales-coder
model: opus
effort: xhigh
skills:
  - andrej-karpathy-skills:karpathy-guidelines
  - test-driven-development
---
```

官方文檔（[subagents.md#preload-skills-into-subagents](https://code.claude.com/docs/en/subagents.md)）證實「The full skill content is injected at startup」。CLAUDE.md + subagent-dispatch-protocol.md + projectStructure.md 同步更新。

**⚠️ 需要 session restart 才生效**（disk file 寫入 disk → 官方文檔字面「restart your session」）。`/clear` 不 reload subagent files。CLI restart 方式：`/exit` + `claude` 重跑；或 agent view 內 `Ctrl+X` stop + reattach（supervisor spawn fresh process）。

完整機制記錄見新 memory [[sales-coder-subagent]]。

### Session C 結束狀態（2026-05-28，commit `3f82638`）

- main HEAD `3f82638` / Pi HEAD `3f82638`
- pytest sales/ **265 passed**（257 → +8 input_reader / -4 decode_error / +sweep timeout=None / +1 c2 strict-short / 三輪 cap_retry revert 淨變 0 = 265）
- **incremental-rebuild 進度**：S1 ✅ S2 ✅ S3 ✅ S4 ✅ S5 ✅ **S6 ✅**（5 commits 修補完成）/ S7 ⬜
- L3 C-2 三選一落地（[[c2-three-way-design]]）
- `.claude/agents/sales-coder.md` subagent 落地（[[sales-coder-subagent]]）但**需要 session restart 才生效**
- **3 條 Pi 已全部驗證通過**（2026-05-29 user 回報）：S6 四路徑 / c2 四路徑 / sales-coder restart 後 dispatch
- **cap retry redesign 開放**（三輪 revert 後 user 沒重做，現況 timeout default 加 1，未來再迭代）

### 2026-05-28 — Session D：3 個 commits 嘗試後 user 全 revert（修法不滿意）

Session C 完成後嘗試 3 個延伸 commit（`06e90b0` Session C snapshot doc / `048ddc2` c2 timeout transition cue fix / `e7d6bfd` hooks docs Gotcha N 擴 live session），**user 看後覺得修法不好（不是有 bug 要留，是品質不滿意）**，commit `a6e33cc` 全 revert 回 `3f82638` 狀態。

→ **main code 內容仍是 Session C end-state（3f82638）**，但 git history 留 revert 痕跡。

### 2026-05-29 — Hook + CLAUDE.md tidy（commit `3c89b0f`）

純文件 / hook 修補，**未動 sales/ 業務邏輯**：
- `subagent-inject-rules.ps1` 廠商 SDK 路徑同步 `myProgram/vendor/*`（與 P1 落差補上）
- CLAUDE.md 拿掉具體測試數（245/257）改指向 SessionStart hook 快照
- CLAUDE.md + standard-workflow.md + worktree-workflow.md 統一「push 後永遠手動跑 sync_pi.ps1」單一規則（原本三處方向 / 程度不一）
- `sync_pi.ps1`（gitignored）繁中註解 + inline EAP=Continue 修 log ssh stderr 雜訊

### 2026-05-29/30 — 大規模 S6 細節 iteration 完成（21 commits，265 → 308 tests）

跨兩日 session 完整覆蓋 4 大主題 + 2 條 feedback rule。**main HEAD `3c89b0f` → `1abb673`**：

#### A. L3 C-2 silent timeout 合流 confirm flow（4 commits）

- `87a44bb` L3 C-2 silent timeout 補 ack speak（L3_C1_CHECKOUT_GO）+ point_screen
- `3a94fa8` **silent timeout 改合流 `_c2_checkout_via_confirm`**（刪除 `_c2_direct_checkout` dead code）— 顧客 silent 也經 confirm 確認明細，跟 CHECKOUT keyword path UX 完全一致；31 個 test fixture sweep
- `c7c8ddb` `L3_CHECKOUT_CONFIRM_TEMPLATE` 刪「（請說"對"或者"不對"）」尾巴 + YES/NO keyword 擴充 user 列表
- `33e5fc2` 「錯誤」從 NO substring 移到 strict_short（避「沒有錯誤」誤命中 false positive）

詳見 [[c2-three-way-design]] 反轉段。

#### B. Cross-L cancel intent + 6s confirm 子狀態（2 commits）

- `1679239` 新 `_cancel_confirm.py` helper + 5 個 explicit gate（main_loop / L2 inner / L3 inner / checkout_confirm / L4 dispatch）+ NLU 擴充
- `83e77bc` 補 3 個 inner state gate（unclear_final / l4_final / l4_service）

8 個 explicit gate cover 全層「拒絕」NLU 路徑；qty_followup 例外（user 接受 fall-through）；C-2 三選一 CANCEL keyword 保留快速 path。詳見 [[cancel-confirm-cross-l]]。

#### C. qty_followup 全面 UX 重構（4 commits）

- `db1504b` silent timeout 從「自動加 1」改「skip 該商品」
- `b19f878` 4 個 skip 分支（reject / 結帳-as-skip / attempts cap / timeout）統一 speak「商品 X 已幫您取消」
- `78f30d5` **return type refactor** `tuple[bool, str | None]`/`tuple[bool, list[str]]` — sub_loop 不直接 speak，caller 把 cancel notice 跟 reask 拼成單一 speak
- `7478e15` multi-product N>=2 用 count 格式「有 X 項商品已幫您取消」

詳見 commit messages。

#### D. **「TTS 播完才開始 timeout 倒數」架構**（核心架構工作，9 commits）

- `8e3aa67` v1 直接 patch read_customer_input 加 wait_idle — **3 P0/P1 bugs**：unbounded wait / R1 race / silent semantic change
- `46e9a67` v1 全 revert（user 拍板「重新規劃」）
- `c418004` **v2** 派 sales-coder：`speak_and_wait` callback + `threading.Condition + _pending` race-free + `max_wait=10s` bounded
- `bd95796` v2.1 qty followup 4 個 prompt-then-read callsite propagate `speak_and_wait`
- `075309a` **v3** read_customer_input 內 wait_idle（自動 cover 12 read 點）+ `read_terminal_key` 不 cover（hawk polling）
- `c07cfc3` sleep callback 內 wait_idle（L5 THANK_DELAY=3s 從 TTS 完才起算）
- `7661f10` Pi demo 觸發 max_wait 10s 不夠 → bump 30s（hawk + L2 entry back-to-back ~12-15s）
- `1abb673` cleanup stale `10s` references（main.py:127 inline comment + test docstrings）+ `test_wait_idle_default_max_wait_is_30_seconds`（鎖死 default）
- `487c175` projectStructure.md 同步紀錄

**3 個新測試檔**：`test_cancel_confirm.py` / `test_tts_worker.py` / `test_main_read_callbacks.py`

13 個 function signature 加 `speak_and_wait=None` kwarg propagate；全層 read/sleep 點除 L1 hawk polling 外都「等 TTS 播完才開始倒數」。詳見 [[speak-and-wait-architecture]]。

#### E. 兩條文案微調（2 commits）

- `a7d225e` `L3_C2_WARNING_TEMPLATE` 標點 + 加「將」+ 去空格（user reword）
- `55e029a` `DIALOG_VAGUE_BUY_REASK` 刪價格列表尾巴（user 反饋過冗）

#### F. 兩條新 feedback rule（user 直接告知，落地 memory）

- [[worker-level-changes-dispatch-sales-coder]] — 動到 `myProgram/{tts,action,input_reader,main}.py` worker / wire-up 結構性改動一律派 sales-coder（v1 `8e3aa67` user feedback）
- [[dispatch-threshold-by-change-size]] — 中小/中/中大/大改動全派 sales-coder；只有「超級小」(≤3 行單檔純值替換) 才主 agent 直接 patch，且必先 invoke `karpathy-guidelines` SKILL（`7661f10` user feedback）

### Session 結束狀態（2026-05-30，commit `1abb673`）

- main HEAD `1abb673` / Pi HEAD `1abb673`
- pytest sales/ **308 passed**（265 + 43 新測 — 含 9 cancel_confirm helper / 6 tts_worker / 3 main read callbacks / 各 path regression）
- **incremental-rebuild 進度**：S1-S6 ✅ S7 ⬜
- 「speak 完才 timeout」架構全層覆蓋（除 L1 hawk polling 設計例外）
- Cross-L cancel intent 8 gate 落地（qty_followup 例外 user 接受）
- L3 C-2 silent timeout 合流 confirm（dead code 清乾淨）
- qty_followup 4 skip path UX 一致 + multi-product count 格式

### 2026-05-30/31 — Pi demo 驅動：客服統一 + L4 大重構 + NLU 多輪擴展 + UX 對齊（18 commits，308 → 378 tests）

接續上輪 S6 細節 iteration，跨兩日 session **18 個 commit**（`4776cb1` → `f9fc54d`）連續修補 Pi demo 暴露的對話層 UX / NLU / flow 問題。**未動 incremental-rebuild S 軸**（S6 已完成 → S7 仍待決），全部是「對話層深度迭代」。

#### A. L4 大重構：60s 多計數器 → 30s 單一 budget（commits `0090786` + `bcc2920`）

L4 從原本「60s + loop_count 4 階段語氣 + unclear_count + final confirmation + 獨立 service timeout」大幅簡化為**單一 30s wall-clock budget + 12s 重提示 + 亂答不重置 budget**。淨減 569 行 prod code（去掉過度設計）。

User 字面：「就單純 budget 計時，沒結賬的話，每 12 秒會重複提示一次，如果亂輸入不會重置 budget，只會印提示給用戶系統無法判斷」。詳見 [[l4-ack-wallclock-budget-design]] v2 段。

`bcc2920` 補修主 loop 客服繼續路徑漏掉的 re-speak entry + reset budget（v2 漏修，user Pi demo「鏈路不知道跑去哪邊了」反饋）。

#### B. 客服統一機制：抽 `_service_confirm` helper（commits `2141e7e` + `92fedb6` + `46c0b52` + `5c9fb1e`）

新建 `myProgram/sales/states/_service_confirm.py` helper（跟 `_cancel_confirm.py` 對稱）+ 4 個 `KEYWORDS_L4_C_CONFIRM_*` 集 + `L4_C_CONFIRM_PROMPT_TEMPLATE`「請問是否繼續交易？{seconds}秒後將自動取消交易。」。

**對齊範圍** — 6 個客服進入點都用 helper：
- L4 `_l4_service_mode`（`allow_scan=True` 給終端 "s" fast path）
- L2 / L3 main loop 客服分支
- L2 / L3 dispatch_inner 客服分支
- qty followup `_qty_follow_up_sub_loop` 客服分支

**Timeout**：12s（第一次） → 24s（user 反饋打電話聯絡客服需更充裕時間，commit `5c9fb1e`）。詳見 [[service-confirm-unified]]。

#### C. Countdown 終端打印：read/sleep 區分語意（commits `84a8aae` + `fab8966`）

`read_customer_input` 每秒印「`timeout = N`」（可被顧客輸入打斷）；`sleep` 每秒印「`wait = N`」（純阻塞）。User debug 視覺時間感，對齊 [[speak-and-wait-architecture]]「TTS 播完才開始倒數」。詳見 [[countdown-print-design]]。

#### D. NLU 多輪擴展（commits `db1871e` + `83b2e24` + `c118384`）

Pi demo 連續暴露 NLU gap 多輪修補：
- C-2 三選一 keyword family 大幅擴（CONTINUE +24 / CANCEL +10）— [[c2-three-way-design]] 2026-05-30 段
- L3 reject 加「不需要」/「沒有額外」cover「不需要 / 我不需要 / 不需要了 / 沒有額外需要購買的」
- `KEYWORDS_CONFIRM_YES` 加「對哦/對呢/對啊」（「對 + 語助詞」sweep）

#### E. Flow 修正 + UX 合成 voice（commits `5dc249f` + `4776cb1` + `b1d1614` + `973ebd2`）

- `_dialog_checkout_confirm` cancel_confirm YES 改新 sentinel `"cancel_to_l1"` 直退 L1（避免兩輪 YES 才退的 bug）
- 3 個合成 voice 常數：`L3_C2_CONTINUE_ACK` / `L2_CANCEL_DECLINED_RESUME` / `L3_CANCEL_DECLINED_RESUME`（cancel/CONTINUE 後保留上下文）

#### F. 其他

- `68b77ec` 新增 `QTY_FOLLOWUP_TIMEOUT: int = 12` 專屬常數（從 `WAIT_NO_RESPONSE=6s` 改 12s，給顧客回答數量更寬鬆時間）
- `168ef65` + `f9fc54d` sweep stale 「12s」comments → 24s（純 docstring/comment 對齊）

### Session 結束狀態（2026-05-31，commit `f9fc54d`）

- main HEAD `f9fc54d` / Pi HEAD `f9fc54d`
- pytest sales/ **378 passed**（308 + 70 = 含 12 service_confirm helper / 各擴展 keyword parametrize / L4 重構 tests / 各 NLU 擴展 invariant test 等）
- **incremental-rebuild 進度**：S1-S6 ✅ S7 ⬜
- 客服統一機制落地（[[service-confirm-unified]]）；L4 大幅簡化（[[l4-ack-wallclock-budget-design]] v2）
- Countdown 終端打印落地（[[countdown-print-design]]）
- 多輪 NLU 擴展 + flow 修正 + UX 合成 voice 對齊

### 2026-05-31 cont. — L4 v3 + SDD 流程正式化 + v3 借鏡 superpowers（14 commits，378 → 386 tests）

接續 `f9fc54d` 後 user 同日 session，**未動 incremental-rebuild S 軸**（S7 仍待決），全部是「流程級基礎建設」+ 「L4 重設計」。main HEAD `5710826` → `5c2deb1`，**4 個 work item**：

#### A. L4 v3 雙計時器重設計（commits `f6c2079` / `b78d541` / `1375db0` / `f8dc222`，首個 SDD 應用）

User Pi demo transcript 觀察 v2 (30s 單 budget) UX 不對齊 — ack speak 後 read timeout 視覺重置令顧客困惑。對齊 5 ambiguity（循環秒數 / QR 刷新動作 / ack speak 保留與否 / 子狀態暫停 / 客服 reset）→ 寫 spec 8 段（`L4_v3_dual_timer_spec.md`）→ 派 sales-coder → 主迴圈重寫雙獨立 wall-clock 計時器（總 budget 36s + QR 刷新循環 12s，36=12×3）+ 子鏈路 ack 不影響任何計時器 + cancel_confirm 6s / service 24s 子狀態 pause-compensate + 客服 yes reset 兩計時器。`L4_TOTAL_BUDGET 30→36`、`L4_PROMPT_INTERVAL → L4_QR_REFRESH_INTERVAL`（語意翻轉）、`_l4_dispatch_response` 簽名擴展 `→ (result, pause_duration)` + `"reset"` sentinel。Tests 378 → 386（+8 對應 spec §3.3）。`[DEGRADED-TDD-PARTIAL-L4-v3]` — 主迴圈跨層耦合重構難逐 scenario RED，spec §3.3 9 條清單預先列出當 regression 安全網。詳見 `resources/specs/L4_v3_dual_timer_spec.md`。

#### B. SDD 最佳實踐多源調研報告（commit `d7eb8c1`）

User 要求派 3 個 opus xhigh subagent 並行調研 SDD：(A) Anthropic / Claude 官方（claude-code-guide opus）/ (B) Superpowers + GitHub Spec Kit + 社群插件（claude-code-guide opus）/ (C) Karpathy / Sean Grove / Simon Willison 等思想家（general-purpose opus）。主 agent 整合單一報告 `resources/research/SDD_best_practices_2026-05-31.md`（新建 folder，9 段 ~5000 字）— TL;DR 10 條 + 整體圖景（名詞學 / 時間線 / 三大流派 lightweight-middleweight-heavyweight）+ 跨來源共識 9 條 + 4 條主要分歧 + 工具光譜表 + 7 條 anti-patterns + 對 Project_01 4 段具體建議 + 三大來源詳細報告 + 完整 URL 清單。**結論**：Project_01 現行架構與 Anthropic `cwc-long-running-agents` planner/generator/evaluator + Superpowers 主流社群 pattern 高度同構，**不需引入** spec-kit / BMAD / Kiro 重型工具。

#### C. SDD 流程正式化 v2（commits `edb08e5` / `c586173` / `fa8e43f`）

User 提出 SDD 作為「實作前完整契約」工作流（與 BDD/TDD 並列）→ 三題對齊（L4_v3 spec 遷穻 / 所有 myProgram/ trigger / 雙軌 TaskCreate）→ 寫 meta-spec `sdd_workflow_formalization_2026-05-31_spec.md` → 走 SDD 流程自身實作。**改動**：(1) git mv L4_v3_dual_timer_spec.md → `resources/specs/`（首個遷穻）；(2) 新 `resources/specs/` flat folder + meta-spec（首個跑新規範）；(3) 新 `.claude/rules/sdd-workflow.md`（觸發條件 / 兩 template / Spec 位置命名 / 4 階段 / 雙軌 TaskCreate / sales-coder prompt 範本 / 與其他規則關係 / Anti-patterns）；(4) CLAUDE.md 加 📐 SDD 段 + 4 行查閱表；(5) `.claude/agents/sales-coder.md` 加 SDD 任務協議段；(6) sweep spec path references 5 檔 8 處；(7) memory `sdd-workflow` 完整重寫。**觸發條件強制**：所有 `myProgram/{sales,main,tts,action,input_reader}.py` 改動，不分規模（≥3 行完整 spec / ≤3 行 mini 5 行）。

#### D. SDD v3 升級借鏡 superpowers v5.1.0（commits `b33435c` / `707c1fe` / `5c2deb1`）

User 安裝 `superpowers@claude-plugins-official` 後要求 reverse-engineer → 主 agent 讀 11 個 core skill / prompt template 檔 → 對齊 3 題（Phase A 6 全引入 / Phase B 3 全引入 / 寫 spec 走現行 SDD）→ 寫 meta-spec → 走 SDD 流程實作。**9 個整合點**：

**Phase A (rule/memory 5 項)：**
- A1 Iron Law 主 agent 完成宣告驗證（"NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE" + Gate function + 必跑指令對照表）
- A2 Red Flags 12 條反模式表（看到 STOP 你正在合理化）
- A3 Adversarial 審查 pose（不信 sales-coder 回報，獨立 verify）
- A4 Status 強制 4 選 1（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）取代自由回報
- A5 Implementer self-review 4 類（Completeness / Quality / Discipline / Testing）handoff 前自查

**Phase B (spec 自身 3 項)：**
- B1 Spec self-review 4 點 sweep（placeholder / consistency / scope / ambiguity）user approval 前主 agent 自查
- B2 Step-by-step plan template（2-5min/step + 完整 test/impl code + commit msg）
- B3 spec/plan 兩份 doc 分離（`<name>_spec.md` WHAT + `<name>_plan.md` HOW）

**Phase C (三段 subagent 迴圈 1 項)：**
- C1 implementer (sales-coder) → spec-reviewer (general-purpose sonnet) → code-quality-reviewer (general-purpose opus xhigh)；**scale adaptation**：每 spec 派 3 agents（非 superpowers 每 task）；reviewer prompt templates 集中 `.claude/rules/sdd-prompts/{spec-reviewer.md, code-quality-reviewer.md}`

**改動**：(1) `.claude/rules/sdd-workflow.md` 全面 v3 改寫（+278 行）；(2) 新 sdd-prompts/ folder + 2 reviewer templates；(3) sales-coder.md 加 4 狀態 + self-review 段；(4) CLAUDE.md refine 📐 SDD 段含 v3 + 查閱表 1 新行；(5) memory `sdd-workflow` v3 重寫。Tests 386 仍綠（純流程改動）。**不引入** Phase C 5 項（2-3 approaches / 嚴格 1 問訊息 / 模型分層細節 / Finishing 4-way menu / Visual companion）規模不匹配。

### Session 結束狀態（2026-05-31 cont.，commit `5c2deb1`）

- main HEAD `5c2deb1` / Pi HEAD `5c2deb1`（Pi sync CAS race cosmetic，hook 先成功）
- pytest sales/ **386 passed**（378 + 8 L4 v3）
- **incremental-rebuild 進度**：S1-S6 ✅ S7 ⬜（未推進，本 session 流程級）
- **SDD 流程 v3 完整落地**：spec/plan 兩檔 / 三段 subagent 迴圈 / Iron Law / Red Flags / 4 狀態 / self-review 4 類 / spec self-review 4 點 / 步驟級 plan
- **新基礎建設**：`resources/specs/`（3 spec docs）/ `resources/research/`（1 調研報告）/ `.claude/rules/sdd-prompts/`（2 reviewer templates）
- **下個 session user 規劃**：(1) CLAUDE.md 流程繼續優化（user 明示）(2) 之後修改主程式代碼

### 2026-06-01 — CLAUDE.md / rules / memory → 單一 skill 遷移 + hook BOM 修復

把專案規範體系從「CLAUDE.md（大）+ 13 rules + 41 memory」重整為「CLAUDE.md 極簡核心 + 單一 progressive-disclosure skill」，依官方 skill 架構（`resources/research/CC-skills.md`）+ brainstorm 設計 spec（`resources/specs/claude_md_to_skill_migration_2026-06-01_spec.md`）。

**Phase 1 — 建 skill**（commits `7f6ef9f` / `9c7f59c`）：brainstorm 對齊 4 決策（單 skill router 顆粒度 / CLAUDE.md 留極簡核心 + 新 hook 補強 / memory 只留 2 / myProgram 知識當 router-Read reference）→ 用 skill-creator 建骨架 → 派 8 個 opus subagent 平行把 13 rules + 36 memory **忠實搬運重組**成 `.claude/skills/project-01-workflow/`（router `SKILL.md` + 12 reference + 2 examples + 1 script；繁中、保留全細節、現況校正過期內容如 sync 規則 / Opus 版本 / L4 budget）。

**Phase 2 — 瘦身收尾**（commits `dfd9666` / `7c603df` / `704177a`）：CLAUDE.md ~230 → ~64 行極簡核心（⛔安全 + 🌏繁中 + 📐skill 觸發表）；新增 2 hook（`block-windows-install` PreToolUse 執法 ⛔#2 + `check-traditional-chinese` PostToolUse 純警示）+ 更新 `subagent-inject-rules` 指向 skill + `sales-coder` frontmatter 預載 `project-01-workflow`；刪 `.claude/rules/` 13 檔；`roadmap` + `architecture_vision` 遷入 `resources/`；38 memory 刪除只剩 `user_profile` + `user_step_by_step_pace`；`references/` → `reference/` 單數改名。

**後續修復**：`CC-skills.md` 納入 git（`98520bf`）；**hook BOM bug 修復**（`a1c3753`）— PS 5.1（`powershell.exe`）讀無 BOM .ps1 用系統 cp936 解碼 → 中文字串 parse error（`block-windows-install` 一執行就 crash；起因：Write 工具寫無 BOM + 我用 pwsh `Set-Content -Encoding UTF8` 誤洗掉 `subagent-inject` 的 BOM）；4 個 .ps1 補回 UTF-8 BOM，全 11 hook 實測 PS 5.1 解析+執行正常；教訓寫進 `NOTES.md` Gotcha A（`e0b9102`）。本機 `.pytest_cache` / `__pycache__` 一併清理（gitignored，無影響）。

**狀態**：sales/ pytest 不受影響（純 meta 重構，未動 `myProgram/` code）；main HEAD `e0b9102` / Pi HEAD `e0b9102` 對齊。

**下一步（user 明示）**：先繼續優化 `project-01-workflow` skill + CLAUDE.md（流程級 meta 優化），之後才修改主程式 code。
