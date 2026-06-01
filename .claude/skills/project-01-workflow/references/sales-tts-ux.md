# Sales TTS / 計時倒數 / UX 過場設計

myProgram sales TTS pipeline（`tts.py` TtsWorker）、wall-clock 計時倒數打印、與 UX 過場 / 心理學掩蓋的領域設計哲學。日後改 sales code（尤其 TTS 等待、timeout 計時、speak 文案 sweep）須對照本檔。

> 每個 section 對應一份原始 memory，忠實搬運其全部設計細節 + Why + 歷史演進。

---

## speak_and_wait 架構 / TtsWorker 設計（speak-and-wait-architecture）

**2026-05-30 落地的 timeout 架構**：解 Pi demo UX bug「顧客還在聽 prompt 就被扣秒」。最終覆蓋全層每種狀態的 read / sleep 點（除 L1 商家 hawk polling 例外）。

### TtsWorker 設計（`myProgram/tts.py`）

**Race-free 同步原語：**
- `threading.Condition` + `_pending: int` counter（取代 v1 `_active: bool` polling，消除 R1 race window）
- `say()`：原子 `with cv: _pending += 1; _q.put(text)`
- `_loop()`：try/finally 包 `_process_text(text)`，finally 內 `_pending -= 1`，==0 則 `cv.notify_all()`

**對外 API：**
- `speak(text)` — 既有，非阻塞 enqueue
- `wait_idle(max_wait=30.0) -> bool` — 阻塞至 `_pending=0` 或超時；timeout 印警示返 False 讓 caller continue（不死等）
- `speak_and_wait(text, max_wait=30.0) -> bool` — `say()` + `wait_idle()` 連續，給 wall-clock budget caller 用
- `shutdown()` — 既有，cleanup

**max_wait=30s 由來**：Pi 實測 hawk slogan + L2 entry back-to-back ≈ 12-15s（synth + play + ALSA drain + edge_tts 網路 round-trip），10s 不夠。30s 給 ~15-18s buffer，仍是「異常偵測防線」（synth 真卡網路 / mpg123 stuck 才會 trip）。

### 兩條 callback API + 兩個 caller pattern

**Pattern 1：Wall-clock budget caller — 用 `speak_and_wait` 顯式控制 deadline**

```python
speak_and_wait(prompt)           # 阻塞至 TTS 播完，pending=0
deadline = monotonic() + N       # 從 TTS 播完起算 budget
while True:
    remaining = deadline - monotonic()
    if remaining <= 0: ...
    response = read_customer_input(timeout=remaining)  # read 內 wait_idle 對 pending=0 即時 return（no-op）
```

3 個 wall-clock budget caller（commit `c418004`）：
- `_cancel_confirm.py` 6s budget
- `_dialog_c2_second_stage` 6s budget
- `run_l4` entry 60s budget

**Pattern 2：非 budget caller — 自動 cover（main.py callback 內 wait_idle）**

```python
speak(prompt)                          # 非阻塞 enqueue
response = read_customer_input(timeout=N)  # callback 內先 wait_idle 才 read，N 從 TTS 播完起算
```

`main.py read_customer_input` callback 開頭 `tts.wait_idle()`（commit `075309a` v3）— 全 12 個 `read_customer_input` callsite 自動受益。
`main.py sleep` callback 開頭 `tts.wait_idle()`（commit `c07cfc3`）— L5 THANK_DELAY=3s 從 TTS 完才起算。

### 例外（故意不 cover）

**L1 商家層 `read_terminal_key`** — `main.py` callback 內**不**加 wait_idle：
- Hawk polling timeout=0.1s + max_wait=30s 衝突 → 整個 hawk loop 卡 30s + OpenCV 偵測失效
- 商家 speak 多是 status notification（「已開啟偵測」）不是 prompt
- 有 regression test `test_read_terminal_key_does_not_call_wait_idle` 守住

### v1 → v2 → v3 演化（重要教訓）

**v1（commit `8e3aa67`, reverted）：** 主 agent 直接 patch `read_customer_input` 加 wait_idle，踩 3 個 bug：
- P0 unbounded wait → synth 卡網路永久阻塞，毀 L4 wall-clock budget 訴求
- P1 R1 race window → `q.get()` 返回 → `_active=True` 之間 wait_idle 誤判 idle
- M2 wall-clock budget silent semantic change → 6s budget 被 speak 時間吃掉

**v2（commit `c418004`，派 sales-coder）：** 修 P0（max_wait）+ P1（Condition+_pending）+ 給 budget caller `speak_and_wait` 顯式控制 deadline（解 M2）

**v2.1（commit `bd95796`）：** qty followup 4 個 prompt-then-read callsite propagate `speak_and_wait`

**v3（commit `075309a` + `c07cfc3`）：** v1 設計重新引入到 read / sleep callback，現在安全因 P0/P1/M2 已解

**v3.1（commit `7661f10` + `1abb673`）：** Pi demo 觸發 max_wait 10s 不夠 → bump 30s + cleanup stale comments + 加 default value verification test

### 全層 timeout 行為矩陣

| 層 | 狀態 | Timeout | 從 speak 完才算？ | 機制 |
|---|---|---|---|---|
| L1 hawk | 商家 polling | 0.1s | ❌ 故意 | `read_terminal_key` 不 wait |
| L2 | DnC 主等待 / B-3 silence | 12s/6s | ✅ | read 內 wait_idle (v3) |
| L2/L3 | qty followup | 6s | ✅ | speak_and_wait + read wait |
| L3 | DyC 主等待 / B-4 silence | 12s/6s | ✅ | read 內 wait_idle (v3) |
| L3 | checkout confirm / unclear final | 12s/read | ✅ | read 內 wait_idle (v3) |
| L3 | C-2 三選一 | 6s | ✅ | speak_and_wait (`c418004`) |
| L4 | entry budget / 主等待 / final / service | 60s/6s/etc | ✅ | speak_and_wait + read wait |
| L5 | THANK_DELAY | 3s sleep | ✅ | sleep 內 wait_idle (`c07cfc3`) |
| Cross-L | cancel_confirm | 6s | ✅ | speak_and_wait |

> 註：上表 L4 entry budget 標 60s 為本架構落地當時（2026-05-30 早）的值；L4 budget 後續二次重構簡化為 30s 單一 budget，見 [sales-dialog-design.md L4 budget section](sales-dialog-design.md#l4-30s-wall-clock-budget-設計l4-ack-wallclock-budget-design)。speak_and_wait 機制本身不受該值變動影響。

### 13 個 function signature 加 `speak_and_wait=None` kwarg

Cross-L cancel_confirm + speak_and_wait 都需要 propagate callback。default `None` fallback to `speak` 保持既有 test 向後相容。受影響 chain：
`logic.run` → `run_dialog` / `run_l4` → 內部所有 inner state helper（13 個）

### 未來 trigger（band-aid 上限）

- Pi demo 再次出現 `wait_idle 超過 max_wait` warning → 不是繼續 bump 30s，而是查 root cause：FIFO 累積還是 edge_tts 異常
- UX 上「顧客出現後仍要聽完 hawk 廣告才聽 L2 prompt」→ S7-mini interrupt（OpenCV 偵測時 drain queue + terminate mpg123）

### 相關（同檔群內）

- [tts-prompt-as-ux-pacing](#tts-prompt-作為-ux-pacingtts-prompt-as-ux-pacing) — 短 ack speak 是 loading-bar UX 不是冗餘
- [ux-over-technical-correctness](#ux-優先於技術正確性ux-over-technical-correctness) — 用心理學掩蓋技術極限

跨檔關聯：[worker-level-changes-dispatch-sales-coder / dispatch-threshold](sdd.md)（worker / wire-up 結構改動派 sales-coder；v1 直接 patch 失敗 → user feedback）；[c2-three-way-design](sales-dialog-design.md#c-2-三選一設計c2-three-way-design)（C-2 silent timeout 從直接 L4 改合流 confirm path，本架構同期落地）；[cancel-confirm-cross-l](sales-dialog-design.md#跨層-cancel_confirm-子狀態cancel-confirm-cross-l)（跨層 cancel intent 子狀態，用 speak_and_wait）；[s6 非阻塞 input](myprogram-threading-paths.md)（input_reader.read 底層 polling 機制）。

---

## Countdown 終端打印設計（countdown-print-design）

**架構（2026-05-30 commits `84a8aae` + `fab8966`）：** `read_customer_input` / `sleep` 兩個 IO 邊界 callback 內加每秒倒數打印，user debug 視覺時間感。

### 設計區分語意

| Callback | 格式 | 語意 | 中途打斷 |
|---|---|---|---|
| `read_customer_input` | `timeout = N` | 可被顧客輸入打斷的等待 | ✅ 拿到 input 立即 break |
| `sleep` | `wait = N` | 純阻塞等待（規格 L5「致謝期間不接受顧客輸入」） | ❌ 純 `time.sleep` 不可中斷 |

**設計沿革**：先做 `read_customer_input` 倒數，user 問 `sleep` 是否也要 — 確認後加 `sleep` 倒數但**格式區分**（user 字面：「就改成 wait =」），避免語意混淆。

### 實作 pattern（polling loop 對齊整秒邊界）

```python
deadline = time.monotonic() + N
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        break
    ticks = math.ceil(remaining)
    print(f"timeout = {ticks}")  # 或 wait = {ticks}
    wait_to_next = remaining - (ticks - 1)  # 對齊下一個整秒邊界
    raw = input_reader.read(wait_to_next)  # 或 time.sleep
    if raw is not None: break  # 僅 read 有此 break；sleep 純等
```

**整秒邊界邏輯**：`remaining=6.0` → `ticks=6, wait=1.0`；`remaining=5.3` → `ticks=6, wait=0.3` 對齊整秒；下一輪 `remaining≈5.0` → `ticks=5, wait=1.0`。避免浮點漂移「6 6 6」。

### 語音播完才印第一個

**關鍵對齊**：`tts.wait_idle()` 在 polling loop 前，確保「語音播完瞬間印第一個 ceil(timeout)」 — 顧客剛聽完 prompt 才開始倒數，不被 TTS 播放時間吃掉視覺。

詳見 [speak-and-wait 架構](#speak_and_wait-架構--ttsworker-設計speak-and-wait-architecture) wait-then-count pattern。

### Mock test 適配

既有 main.py callback test 用 mock `input_reader.read` 回 `None` + mock `time.sleep` 不真實 sleep → polling loop 內 `time.monotonic` 不前進會無限迴圈印。處理：

- `read_customer_input` test：改 mock 首次回非-None 讓 loop 一次 break（保留 wait_idle → read 順序 assertion）
- `sleep` test：用 virtual clock pattern（fake `time.sleep` advances mocked `time.monotonic`）讓 polling loop 自然 terminate

這是 polling loop 重寫帶來的 surgical 必要 mock 調整，commits `84a8aae` + `fab8966` 內處理。

### 範圍與例外

**有倒數**：
- `read_customer_input(timeout=N)`（L2/L3/L4 / qty followup / cancel_confirm / service_confirm 等所有顧客對話層）
- `sleep(seconds=N)`（L5 THANK_DELAY=3s）

**無倒數**：
- `read_terminal_key(timeout=None/0.1)`（商家層 — 主選單無限阻塞無 UX 需求；hawk 100ms polling cadence 印倒數會洗版）
- `tts.speak` / `do_action` etc.（不是 IO 邊界等待，純動作）

### How to apply

- 新增「等顧客回應」邊界 → 用 `read_customer_input(timeout=N)`，倒數自動 cover
- 新增「純等」邊界 → 用 `sleep(N)` callback，wait 倒數自動 cover
- 不要在 sales/ 業務邏輯內自己印倒數 — 改 IO 邊界（main.py）就全層 cover
- 測 main.py callback 時注意 polling loop mock 適配

### 相關

- [speak-and-wait 架構](#speak_and_wait-架構--ttsworker-設計speak-and-wait-architecture) — TTS 播完才開始倒數的整體架構（read/sleep 都 cover）
- [ux-over-technical-correctness](#ux-優先於技術正確性ux-over-technical-correctness) — 終端打印是「show progress」UX，跟「TTS speak ack 是 loading-bar pacing」一致心法
- 跨檔：[s6 非阻塞 input](myprogram-threading-paths.md) — input_reader.read 的底層 polling 機制

---

## TTS prompt 作為 UX pacing（tts-prompt-as-ux-pacing）

**Rule:** 看到對話流程中「短 ack speak + 緊接著實質 speak」的 pattern（例：`speak("好的，為您結帳") → 計算 → speak("您的總金額是 918 元")`），**預設不要把第一句當冗餘移除**。短 ack 是過場 UX 設計，跟大廠 loading 進度條 / skeleton screen / typing indicator 是同一類 pattern。

**Why:** 2026-05-27 S2 TTS 接入後，使用者反映 L3 confirm yes → L4 entry 之間「卡幾秒」。主 agent 第一輪分析把 `L3_C1_CHECKOUT_GO = "好的，為您結帳"` 列為「冗餘 speak」推薦移除，使用者明確拒絕並解釋：

> 「您知道我為何說'好的，為您結帳'那句話不錯，因為很多大廠的演算法，在跑一些需要計算時間的程式時，為了不要讓用戶有卡頓感，會去做一些過場效果，看似冗餘，但實際上和卡頓相比反而會提升用戶體驗，比如說 loading 時會有進度條，減緩用戶焦慮，各種產品用戶人因設計體驗心理學。」

主 agent 反思：技術視角看「兩個 speak 串接 = 雙倍 TTS 時長 = 卡」，但 UX 視角看「ack speak 提早出來填補 silence = 顧客知道機器人在處理 = 焦慮↓」。**技術冗餘 ≠ UX 冗餘**。

**How to apply:**

| 訊號 | 判定 |
|---|---|
| 對話中「ack 短句」+「實質長句」串接（如「好的，為您 X」+「您的 Y 是 Z」）| **保留**（UX pacing 設計） |
| 兩個 speak 完全同訊息 / 純廢話覆蓋 | 才考慮移除 |
| user 抱怨「卡」 | 先查 **真正冗餘**（重複、dead callback、不必要 sleep / mute_opencv），不要立刻刪 ack speak |
| 真根治阻塞 TTS 累加 | 走 S4 非阻塞 TTS worker + queue，**不是**刪 ack speak |
| 派 subagent sweep TTS 文案 | prompt 內必須明示「ack / transition speak 是 UX pacing，禁止當冗餘移除」 |

**判斷 ack 還是真冗餘的 checklist：**
1. 第一句是否帶實質新資訊？— 沒帶（只是 ack）→ pacing 候選
2. 後面緊接的 speak 是否需要計算 / IO 時間？— 是 → ack 提早出來填補 silence 有價值
3. user 是否明確抱怨這條 ack？— 沒明確抱怨 → 假設它是有意設計

**反例（不是 pacing 是真冗餘）：**
- 兩個 speak 完全同字面（debug copy-paste）
- speak 後立刻 return 沒進新層（純 trailing 廢話）
- 同一句在 dispatcher 內被印兩次（同訊息 dup，不是 ack + 實質）

**相關：**
- [ux-over-technical-correctness](#ux-優先於技術正確性ux-over-technical-correctness) — 本 section 是此主原則在 TTS 層的具體 instance；判斷邏輯（先試技術優化、不能 → 用心理學掩蓋、最終目的是體驗）見主原則
- [speak-and-wait 架構](#speak_and_wait-架構--ttsworker-設計speak-and-wait-architecture) — S4 非阻塞 TTS worker 才是「多 speak 串接卡」的根本解（roadmap 候選）

---

## UX 優先於技術正確性（ux-over-technical-correctness）

**Rule:** 做任何 user-facing 設計判斷時，順序是：

1. **先看技術能否縮短負面感知瞬間**（卡頓 / 延遲 / 沉默 / 訊息突兀）— 能 → 優化
2. **不能縮短時 → 用心理學手段掩蓋**（過場 ack / progress bar / skeleton screen / typing indicator / 友善口語訊息）
3. **始終以「使用者當下體驗好」為最終目的**，不以「技術背後完美正確」為標準

「看似冗餘但實際提升體驗」的設計**屬於第 2 條的合法應用**，不該因技術潔癖被移除。

**Why:** 2026-05-27 使用者在 L3 confirm yes → L4 entry「卡 5.6s」討論中明確教育主 agent：

> 「技術直覺是好的，但是認清技術極限，其實最根本是因為我們技術上避免不了運算時間，所以有心理學的方式掩蓋技術上的不足。而且要始終明白我們做這些的最終目的是要『讓客戶有更好的體驗』，客戶根本不在乎您背後事實是如何實現的，只要當下體驗好，對客戶來說就是好。」

主 agent 第一輪把 `L3_C1_CHECKOUT_GO = "好的，為您結帳"` 列為「冗餘 speak」 — 技術視角看「兩 speak 串接 = 雙倍 TTS 時長」是對的，但 UX 視角看「ack 提早出來填補 silence = 顧客知道機器人在處理 = 焦慮↓」更重要。**這不是哪個視角錯，是順序錯**（先 UX 後技術，不是反過來）。

**How to apply:**

### 判斷 user-facing 設計時的 checklist

| 問題 | 動作 |
|---|---|
| 1. 此設計有沒有「使用者會感受到負面體驗」的瞬間？（卡頓 / 沉默 / 突兀 / 技術錯誤訊息）| 有 → 進 2 |
| 2. 技術上能不能根除該瞬間？| 能 → 優化技術；不能 → 進 3 |
| 3. 有沒有低成本心理學手段可掩蓋？| 有 → **採用（即使看似冗餘）**；無 → 接受並標記 |
| 4. 該手段是否帶來新負面（如資訊重複、誤導、太長）？| 是 → 重設計；否 → 採用 |

### 已知 instance（隨 demo 進展持續累積）

| 情境 | 技術極限 | 心理學手段 | 對照 section |
|---|---|---|---|
| L3→L4 transition TTS 5.6s | edge_tts + mpg123 同步阻塞 | ack speak「好的，為您結帳」過場 | [tts-prompt-as-ux-pacing](#tts-prompt-作為-ux-pacingtts-prompt-as-ux-pacing) |
| 加單後等下一輪 reask | TTS 阻塞 | ack speak「好的，已加入購物車」+ 下一輪 prompt | [tts-prompt-as-ux-pacing](#tts-prompt-作為-ux-pacingtts-prompt-as-ux-pacing) |
| L4 結帳 → L5 致謝 TTS 串接 | TTS 阻塞 + ALSA buffer race | ack speak「付款成功」 + ALSA drain | (現存設計，不動) |

### 未來會遇到的 instance（事先預警）

| 情境 | 技術極限 | 預估手段 |
|---|---|---|
| S3 `Act.runAction()` 動作執行 2-5s | 廠商 SDK 同步 blocking | speak ack「好的，請稍等」+ 動作完成 speak「好了」 |
| S6 STT 語音識別 ~1-2s | 雲端 ASR 延遲 | typing indicator / ack speak「我聽到了，讓我想想」 |
| HTML 前端載入 cart 內容 | HTTP request + render | skeleton screen / progressive disclosure |
| 機器人「思考」狀態（NLU unclear）| 規則匹配本身不慢，但顧客感知「為何沒回應」| 短 speak「嗯，我聽聽看」+ 然後 reask |
| 系統錯誤 / exception | exception trace 醜陋 | 友善口語訊息「不好意思系統怪怪的，請再說一次」 |

### Counter-examples（什麼時候**不**應用此哲學）

- **真重複 / dead code**：兩個 speak 完全同字面 / 同訊息 / 純 copy-paste bug → 仍要移除（這是技術 bug 不是 pacing）
- **掩蓋逃避優化**：技術上其實能縮短卻不縮、純靠過場拖時間 → 仍要先優化（如 ALSA drain 0.3s 可以縮 0.2s 同時不影響截斷）
- **資訊冗餘**：ack speak 跟下一句完全同資訊（如「您要結帳了」+「您即將結帳」）→ 合併
- **過長過場**：ack 太長拖過實際處理時間 → 反而成負面（loading bar 跑完了還沒好）

### 派 subagent 寫 user-facing 邏輯時

**prompt 內必須明示：**
- 「對話 / UI / 動作流程中含使用者感知瞬間（speak / wait / IO），預設保留 ack / transition / pacing 設計」
- 「禁止以『技術冗餘 / 簡化 / dead code 清理』為名移除 ack speak / loading 提示 / typing indicator 等」
- 「真不確定 → 標『待 UX 評估』回報主 agent，不要擅自簡化」

**派 sweep TTS 文案的 subagent** → 額外塞此哲學全文。

**相關：**
- [tts-prompt-as-ux-pacing](#tts-prompt-作為-ux-pacingtts-prompt-as-ux-pacing) — 本原則在 TTS / dialog 層的具體 instance
- 跨檔：[confirm-default-must-be-conservative](sales-dialog-design.md#confirm-亂答--timeout-default-必須保守confirm-default-must-be-conservative) — 同樣是「UX 心理學優先於技術對稱性」的應用（confirm 子狀態 default 必須 conservative）
- 使用者背景：資工 4A，但 demo 對象是普通顧客，必須以「對 demo 對象友善」為設計優先（見 user-profile）

---

**相關 reference**：[sales-dialog-design.md](sales-dialog-design.md)（對話狀態機 / 跨層流程）/ [myprogram-threading-paths.md](myprogram-threading-paths.md)（多線程 / S6 input）/ [sdd.md](sdd.md)（改 sales code 走 SDD 流程）/ [CLAUDE.md](../../../CLAUDE.md)
