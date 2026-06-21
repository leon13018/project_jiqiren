# Sales TTS / 計時倒數 / UX 過場設計

> **🎯 何時讀本檔**：要改 sales 的 TTS 等待 / wall-clock 計時倒數 / timeout / speak 文案 sweep / UX 過場。

## 目錄
- speak_and_wait 架構 / TtsWorker
- 全層 timeout 行為矩陣
- Countdown 終端打印設計
- TTS prompt 作為 UX pacing
- UX 優先於技術正確性

myProgram sales TTS pipeline（`tts.py` TtsWorker）、wall-clock 計時倒數打印、與 UX 過場的設計哲學。改 sales code（尤其 TTS 等待、timeout 計時、speak 文案 sweep）須對照本檔。

---

## speak_and_wait 架構 / TtsWorker

解 Pi demo UX bug「顧客還在聽 prompt 就被扣秒」。覆蓋全層每種狀態的 read / sleep 點（除 L1 商家 hawk polling 例外）。

**TtsWorker（`myProgram/tts.py`）race-free 原語**：`threading.Condition` + `_pending: int` counter（取代 v1 `_active: bool` polling，消除 R1 race）。`say()` 原子 `with cv: _pending += 1; _q.put(text)`；基底 `QueueWorker._loop` try/finally 包 `_process`，finally（`on_done`）`_pending -= 1`，==0 則 `cv.notify_all()`。

**對外 API**：`speak(text)`（非阻塞 enqueue）｜`wait_idle(max_wait=30.0)->bool`（阻塞至 `_pending=0` 或超時，timeout 印警示返 False 讓 caller continue 不死等）｜`speak_and_wait(text, max_wait=30.0)->bool`（say + wait_idle 連續，給 wall-clock budget caller）｜`shutdown()`。
- **max_wait=30s 由來**：Pi 實測 hawk slogan + L2 entry back-to-back ≈ 12-15s（synth + play + ALSA drain + edge_tts 網路），10s 不夠；30s 給 buffer 仍是「異常偵測防線」。

**兩個 caller pattern**：
- **Pattern 1 — wall-clock budget caller**：`speak_and_wait(prompt)` → `deadline = monotonic()+N`（從 TTS 播完起算）→ 迴圈 `read_customer_input(timeout=remaining)`（read 內 wait_idle 對 pending=0 即時 no-op return）。用於 `_cancel_confirm`（6s）、`_dialog_c2_second_stage`（6s）、`run_l4` entry budget。
- **Pattern 2 — 非 budget caller（自動 cover）**：`speak(prompt)` → `read_customer_input(timeout=N)`，`main.py` callback 開頭 `tts.wait_idle()`（全 12 個 read callsite + L5 sleep 自動受益，N 從 TTS 播完起算）。

**例外（故意不 cover）**：L1 商家 `read_terminal_key` 不加 wait_idle——hawk polling timeout=0.1s 與 max_wait=30s 衝突會卡死 hawk loop + OpenCV 失效；商家 speak 多是 status notification 非 prompt。有 regression test `test_read_terminal_key_does_not_call_wait_idle` 守住。

> **教訓：worker/wire-up 結構改動（race / try-finally / lock scope / 新 attr）派 sales-coder、別主 agent 直接 patch**——主 agent 直接 patch 曾踩 unbounded wait（synth 卡網路永久阻塞毀 budget）/ idle race（q.get 返回與旗號設定之間誤判 idle）/ budget 被 speak 時間吃掉等盲點，改派 sales-coder 嚴格 TDD 才收斂。

### 合成管線：快取 → prefetch → 合成（perf_w2/w5，2026-06-12）

`_process` 取得 mp3 的三層 fallback：**內容定址快取**（`sha1(VOICE|rate|text)` → `myProgram/tts_cache/<hash>.mp3`，命中零合成零網路）→ **prefetch 標記**（當前句播放等待期間預合成 queue 下一句入快取）→ 現場合成（worker 常駐 event loop；寫 `.tmp` 後 `os.replace` 原子入快取——快取永不含半寫檔）。

- **前提**：rate 由 `len(text)` 決定、VOICE 固定 → 同文字永遠同音訊。**改 VOICE / rate 邏輯＝全快取自然失效**（key 變），須重跑 prewarm。
- **文案常數改動 SOP**：Pi 端 `python3.11 -m myProgram.tts_prewarm`（**勿與 demo 同時跑**，同句 .tmp 互踩）→ dev 端 scp 拉回 `git add myProgram/tts_cache` commit（Pi 無 GitHub 認證，不從 Pi push）。資產 tracked → demo 斷網可播全部固定句。
- 舊 `/tmp` 雙 buffer 已退役（內容定址檔名各句互異，無互踩面）；`_prefetched` 標記與 `_peek_next`（mutex 下偷看 `queue[0]`，單消費者安全）保留。

### 全層 timeout 行為矩陣
| 層 | 狀態 | Timeout | 從 speak 完算 | 機制 |
|---|---|---|---|---|
| L1 hawk | 商家 polling | 0.1s | ❌ 故意 | `read_terminal_key` 不 wait |
| L2 | DnC 主等待 / B-3 silence | 12s/6s | ✅ | read 內 wait_idle |
| L2/L3 | qty followup | 6s | ✅ | speak_and_wait + read wait |
| L3 | DyC 主等待 / B-4 silence | 12s/6s | ✅ | read 內 wait_idle |
| L3 | checkout confirm / unclear final | 12s/read | ✅ | read 內 wait_idle |
| L3 | C-2 三選一 | 6s | ✅ | speak_and_wait |
| L4 | entry budget / 主等待 / service | 見註/6s/24s | ✅ | speak_and_wait + read wait |
| L5 | THANK_DELAY | 3s sleep | ✅ | sleep 內 wait_idle |
| Cross-L | cancel_confirm | 6s | ✅ | speak_and_wait |

> 註：L4 entry budget = `L4_TOTAL_BUDGET` 36s（v3 雙計時器，見 [sales-dialog-design.md](sales-dialog-design.md) L4 段）；speak_and_wait 機制不受該值影響。

---

## Countdown 終端打印設計

`read_customer_input` / `sleep` 兩個 IO 邊界 callback 內每秒倒數打印（user debug 視覺時間感）。

> **預設隱藏**（2026-06-20）：兩種倒數行（`timeout = N` / `wait = N`）由 `main._SHOW_COUNTDOWN`（env `SALES_SHOW_COUNTDOWN`，預設 0）閘住，demo 終端乾淨；`SALES_SHOW_COUNTDOWN=1` 啟動才印。閘在 `_tick_countdown` 單一印行點、只抑制視覺、計時不受影響。

> **語音 echo 顯示 `SALES_VOICE`**（2026-06-21，反轉自原 `SALES_QUIET`）：**預設隱藏**終端正常機器人 echo（`[語音]`/`[動作]`/`[模擬提示]`）；`SALES_VOICE=1` 才顯示。保留導航（`print_terminal` 螢幕文字 / 選單 / `進入叫賣模式`）+ 錯誤 `⚠️`（恆顯示、不受旗標影響）。main/tts/action 各自讀 `SALES_VOICE`（沿用 STT_TTS_TIMING precedent，不新增跨模組 import），`if _VOICE:` 只包 print——**gate 外**的 `_worker.say/do`（語音/動作 dispatch）、控制流不受影響（隱藏下機器人仍說/動）。預設 0 = 隱藏（demo 走 web UI/觸控，終端 echo 與鏡像重複是雜訊）。countdown 與本旗標獨立。

| Callback | 格式 | 語意 | 中途打斷 |
|---|---|---|---|
| `read_customer_input` | `timeout = N` | 可被顧客輸入打斷的等待 | ✅ 拿到 input 立即 break |
| `sleep` | `wait = N` | 純阻塞（L5「致謝期間不接受輸入」） | ❌ 純 `time.sleep` 不可中斷 |

**實作 pattern（polling loop 對齊整秒邊界）**：
```python
deadline = time.monotonic() + N
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0: break
    ticks = math.ceil(remaining)
    print(f"timeout = {ticks}")            # 或 wait = {ticks}
    wait_to_next = remaining - (ticks - 1) # 對齊下一整秒邊界，避免浮點漂移「6 6 6」
    raw = input_reader.read(wait_to_next)  # 或 time.sleep
    if raw is not None: break              # 僅 read 有此 break；sleep 純等
```
- **語音播完才印第一個**：`tts.wait_idle()` 在 polling loop 前 → 顧客剛聽完 prompt 才開始倒數，不被 TTS 播放吃掉視覺（wait-then-count）。
- **範圍**：有倒數 = `read_customer_input`（所有顧客對話層）+ `sleep`（L5）；無倒數 = `read_terminal_key`（商家層，主選單無限阻塞 / hawk polling 印倒數會洗版）、`speak`/`do_action`（非 IO 等待）。
- **mock test 適配**：polling loop 內 `time.monotonic` 不前進會無限迴圈印 → `read` test 改 mock 首次回非-None 讓 loop 一次 break；`sleep` test 用 virtual clock（fake sleep advances mocked monotonic）。
- **How to apply**：等顧客回應 → `read_customer_input(timeout=N)` 倒數自動 cover；純等 → `sleep(N)`；**不要在 sales/ 業務邏輯內自己印倒數，改 IO 邊界（main.py）就全層 cover**。

---

## TTS prompt 作為 UX pacing

**Rule**：看到「短 ack speak + 緊接實質 speak」（例：`speak("好的，為您結帳") → 計算 → speak("您的總金額是 918 元")`），**預設不要把第一句當冗餘移除**。短 ack 是過場 UX，跟 loading 進度條 / skeleton screen / typing indicator 同類。

**Why**：曾把 `L3_C1_CHECKOUT_GO="好的，為您結帳"` 列為冗餘推薦移除，user 拒絕並解釋：大廠在需計算時間的程式跑過場效果（loading 進度條）減緩用戶焦慮，看似冗餘但比卡頓提升體驗。**技術冗餘 ≠ UX 冗餘**（ack 提早填補 silence = 顧客知道機器人在處理 = 焦慮↓）。

**判斷 ack 還是真冗餘**：(1) 第一句帶實質新資訊嗎？沒帶（只 ack）→ pacing 候選；(2) 後句需計算/IO 時間嗎？是 → ack 填補 silence 有價值；(3) user 明確抱怨這條 ack 嗎？沒 → 假設有意設計。
**反例（真冗餘可移除）**：兩 speak 完全同字面（copy-paste bug）/ speak 後立刻 return 沒進新層 / 同句 dispatcher 內印兩次。
**派 subagent sweep TTS 文案**：prompt 必明示「ack / transition speak 是 UX pacing，禁止當冗餘移除」。

---

## UX 優先於技術正確性

**Rule（順序）**：(1) 先看技術能否縮短負面感知瞬間（卡頓/延遲/沉默/突兀）→ 能就優化；(2) 不能 → 用心理學手段掩蓋（過場 ack / progress bar / skeleton / typing indicator / 友善口語）；(3) 始終以「使用者當下體驗好」為最終目的，不以「技術背後完美正確」為標準。「看似冗餘但提升體驗」屬第 2 條合法應用，不該因技術潔癖移除。

**Why**：user 教育——「認清技術極限，運算時間避免不了 → 用心理學掩蓋不足；客戶不在乎背後怎麼實現，只要當下體驗好就是好。」把 ack speak 當冗餘**不是視角錯，是順序錯**（應先 UX 後技術）。

**判斷 checklist**：有負面感知瞬間？→ 技術能根除？能就優化、不能 → 有低成本心理學手段？有就採用（即使看似冗餘）；該手段帶來新負面（重複/誤導/太長）？是 → 重設計。

**已知 instance**：L3→L4 transition TTS 5.6s → ack「好的，為您結帳」｜加單後 reask → ack「好的，已加入購物車」｜L4→L5 致謝串接 → ack「付款成功」+ ALSA drain。
**未來 instance（預警）**：S3 `runAction` 2-5s → ack「好的，請稍等」+「好了」｜S6 STT ~1-2s → typing indicator / ack「我聽到了，讓我想想」｜HTML 載 cart → skeleton｜NLU unclear「思考」→ 短 speak「嗯，我聽聽看」+ reask｜系統 exception → 友善「不好意思系統怪怪的，請再說一次」。

**Counter-examples（不應用此哲學）**：真重複 / dead code（同字面 copy-paste）→ 移除；技術其實能縮短卻純靠過場拖時間 → 先優化；ack 跟下句同資訊 → 合併；過場太長拖過實際處理 → 反成負面。
**派 subagent 寫 user-facing 邏輯**：prompt 必明示「預設保留 ack/transition/pacing；禁以『技術冗餘/簡化/dead code 清理』移除 ack speak / loading 提示；不確定標『待 UX 評估』回報，不擅自簡化」。sweep TTS 文案的 subagent 額外塞此哲學全文。
