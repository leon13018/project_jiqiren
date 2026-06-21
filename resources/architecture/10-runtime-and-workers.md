# 10 · 執行期與 Worker 層

> 入口層 `main.py` 怎麼把純邏輯接到硬體，以及四個背景 worker 的並行模型。以實際 code 為準（2026-06-21）。

---

## 1. `main.py` — 入口層 wire-up

`main.py` 是唯一允許持有「外部世界」的地方：終端 I/O、TTS、STT、動作、web。它**不持有業務 state**（cart / counters 全在 `SalesMachine` 內），只負責把 callback 接好、決定啟動模式、收尾 cleanup。

### 1.1 `TerminalSim` — callback 集

`TerminalSim` 是無內部 state 的 callback 容器，10 個 bound method 對應 10 個對外 callback，由 `callbacks()` 打包成 dict，展開餵 `logic.run(**callbacks)`：

| callback | 行為 | 備註 |
|---|---|---|
| `print_terminal(text)` | 受 `SALES_VOICE` gate，印導航 / 螢幕文字 | demo 預設隱藏（與 web 鏡像重複）|
| `show_hawk_help()` | 印叫賣模式操作提示 | 受 `SALES_VOICE` gate |
| `read_terminal_key(timeout=None)` | 從 `input_reader` 取商家鍵盤輸入；嚴格整段匹配 | 預設無限阻塞；hawk 主迴圈顯式傳 `timeout=0.1` polling |
| `read_customer_input(timeout)` | 取顧客輸入（語音 / 觸控），含 STT arm/disarm 編排 | 見 §1.2 |
| `speak(text)` | 非阻塞 enqueue TTS | lazy import `tts` |
| `speak_and_wait(text)` | 同步阻塞至播完 | wall-clock budget 子狀態用（3 處）|
| `do_action(name)` | 非阻塞 enqueue 動作 | lazy import `action` |
| `sleep(seconds)` | 阻塞等待（先 `tts.wait_idle`）| L5 禮貌間隔 |
| `tts_is_idle()` | 非阻塞查 TTS 是否閒置 | hawk 輪播間距判定 |
| `exit_program()` | `sys.exit(0)` | L1 連按 q 兩次退出 |

外加 `display`（web 鏡像，`--web` 才非 None）與 `start_hawk`（bool）由 `_run_wiring` 額外傳入。

### 1.2 STT 編排在 `read_customer_input` 裡

讀顧客輸入是整個入口層最精密的一段（`main.py:129`）。順序：

1. `stt.prearm()` 非阻塞預連線（首輪 540ms 握手藏進下面提示音播放）。
2. （`STT_EARLY_MIC=1`）`stt.arm(capture=False)` 提示音播放期間就開 arecord 串流暖機，但**不注入**（被 `_capturing` 閘擋）。
3. `tts.wait_idle()` 等提示音播完才開始倒數（避免顧客還在聽 prompt 就被扣秒）。
4. （`STT_MIC_OPEN_DELAY_MS>0`）等喇叭 ALSA 尾音排空。
5. `stt.arm()` 翻注入閘（capture=True；早麥則復用已開的 arecord）。
6. `_tick_countdown(timeout, "timeout", input_reader.read)` 倒數讀輸入（可被輸入打斷）。
7. `finally: stt.disarm()` —— try/finally 保證四條路徑（早麥開了 / 拿到輸入 / timeout / `q` 退出）都收麥。

### 1.3 Lazy import seam（Windows 紅線）

`TerminalSim` 每個碰硬體的 method 內部都是 **lazy import**（`from myProgram import tts` / `action` / `stt` / `input_reader` 寫在函式體，不在模組頂層）。理由：

- `tts.py` 頂層 `import edge_tts`、`action` daemon thread import vendor SDK、`stt` import websockets —— 這些在 Windows 裝不了。
- lazy import 讓 Windows pytest 可經 `from myProgram.main import _build_callbacks` 收到 callback 集而**不觸發**任何硬體依賴 import、不啟動 worker thread。
- Pi 端首次 `speak` / `do_action` / `read` 時才真正 import（fail-fast 留在該點）。

### 1.4 啟動分流 `_run_wiring`

- 讀 `--hawk` / `SALES_KEYBOARD` → 啟動防呆（見 `00` §2）。
- `--web` 分流：主線程只建**輕量** stdlib 部件（`EventBus` / web 版 `display` / `input_reader`）→ 瞬間完成、menu 立即可互動；**笨重** import（`myProgram.web.server` 觸發 fastapi/uvicorn/pydantic，Pi 上要好幾秒）+ `server.start` 移到背景 `webui-boot` daemon thread，**不擋對話迴圈**。
- `display_cb` 在 `--web` 時恆 bus-backed：早期 menu emit（standby phase）走 `bus.publish`，loop 未綁時只存 `last_state`，瀏覽器連上經 `/api/state` 取 snapshot → 不丟失。
- web 啟動失敗 graceful（Pi 沒裝 fastapi / port 衝突）：背景 thread try/except 印明確繁中錯誤，**機器人照常運作**（不讓 web 殼開不了機害機器人開不了機）。

### 1.5 預熱與 cleanup

- **`_prewarm_workers`**（`main.py:280`）：startup 由背景 daemon thread 提前 import `tts` / `action` / `stt`，消除首次互動的 lazy import 頓挫。best-effort，失敗 swallow（lazy path 屆時自然 fail-fast）。
- **cleanup**（`main()` finally，`main.py:414`）：四個 worker 各自 `shutdown()`（lazy import + swallow ImportError），最後 **`os._exit(0)` 強退**。為什麼強退：`input_reader` daemon thread 阻塞在 `sys.stdin.buffer.readline()` 的 C-level kernel syscall，主線程 return 後 Python finalizer 會卡在 stdin lock（Linux `close(fd)` 不 wake 已阻塞在 `read(fd)` 的 thread）。worker shutdown 已跑完 → `os._exit(0)` 跳過 finalizer（atexit / module finalize / daemon join）對本專案無副作用（daemon 隨 process die 是設計目的）。

### 1.6 `_tick_countdown` 共用倒數

`read_customer_input`（可被輸入打斷）與 `sleep`（跑滿不可打斷）共用 `_tick_countdown(total, label, wait_tick)`：差異只在注入的 `wait_tick`——`input_reader.read` 可中斷回非 None / `time.sleep` 恆回 None。每秒對齊整秒邊界，`time` 用 module-global lookup（測試 patch 全域時鐘 seam）。倒數列印受 `SALES_SHOW_COUNTDOWN` 控制，**只抑制視覺列印，計時一秒不差**。

---

## 2. `queue_worker.py` — 消費者骨架

tts / action 兩個 consumer worker 共用骨架，收斂在此。

### `QueueWorker(ABC)`

```
__init__       建 self._q = queue.Queue() + 立即啟動 daemon thread 跑 _loop
_loop          on_thread_start() → while True: item=_q.get(); try _process(item) finally on_done(item)
submit(item)   self._q.put(item)
_process(item) @abstractmethod（子類實作真正工作）
on_thread_start()  hook，預設 pass（ActionWorker 用來 lazy import vendor）
on_done(item)      hook，預設 pass（TtsWorker 用來 dec _pending + notify）
drain()        drain_queue(self._q)
```

⚠️ **子類別自有欄位必須在 `super().__init__()` 之前設好**——基底 `__init__` 立即啟動 thread，thread 第一時間可能觸碰子類別欄位。

兩個刻意設計決定：

1. **基底無 except-all、無 on_error hook**：`_loop` 只有 try/finally。加 catch-all 會改變 TtsWorker「未知例外殺 thread」的現行行為（純重構零行為改變紅線）。
2. **`shutdown` 不入基底**：tts / action 收尾順序相反（tts：terminate proc → drain；action：drain → 守衛 stopAction），各自實作，只用 `self.drain()` / `drain_queue` 取代手寫清空迴圈。

`drain_queue(q)` 是模組級 helper（原 tts / action / input_reader 三份相同清空迴圈收斂於此）。`InputReader` 不繼承基底（producer 形狀與 consumer 相反），只 reuse `drain_queue`。

---

## 3. 四個 Worker

### 3.1 `tts.py` — 非阻塞 TTS（`TtsWorker(QueueWorker)`）

**職責**：文字轉語音並播放，caller 立即返回，背景 daemon FIFO 消費。

**公開 API**：`speak(text)`（非阻塞）/ `speak_and_wait(text, max_wait=30)`（阻塞至播完，回 bool）/ `wait_idle(max_wait=30)` / `is_idle()` / `shutdown()`。

**並行模型**：1 條常駐 daemon。同步原語三件：`_q`（FIFO）、`_cv`（Condition）+ `_pending`（int）計數三方同步、`_lock`（Lock）保護 `_proc`（當前 mpg123 process）。
- **`_pending` 計數修 R1 race**：`say` 持 `_cv` 原子 `_pending += 1` **再** `put`（順序關鍵）；`on_done` 持 `_cv` `_pending -= 1` 歸 0 時 `notify_all`；`wait_idle` 持 `_cv` wait。原 `_active` bool 有「`q.get()` 後但 flag 未設」的誤判 idle 窗，計數制根治。
- **`_lock` 範圍刻意短**：只包 `Popen` spawn 與 finally 清 None，**不**包 `_proc.wait()`（否則 shutdown 拿不到 lock 達 2–5s）。

**資料流（三層 mp3 取得 fallback）**：① prefetch 標記命中 → ② 內容定址快取命中（`os.path.exists`，零合成零網路，**斷網可播**）→ ③ 現場合成（常駐 event loop `run_until_complete(_synthesize)` → `_store_into_cache` 原子 `os.replace`）。播放用 `subprocess.Popen(["mpg123","-q",mp3], stdin=DEVNULL)`，**播放阻塞期間 prefetch 下一句**（`_peek_next` → 合成進 cache → 設 `_prefetched`，句間靜默趨近 0）。

**設計決策 / gotcha**：
- **內容定址快取**：key = SHA1(`f"{VOICE}|{rate}|{text}"`)，任一合成參數變即自然失效；快取目錄 package-anchored（非 cwd）；執行期自我增長（動態句首播後永久免合成）。
- `_pick_rate`：依字數選語速（短 +3% / 中 +6% / 長 +12%）。
- `stdin=DEVNULL`：mpg123 預設讀父 stdin 偷 control char（q/s/p）會吃掉 user 輸入或誤觸 quit。
- **常駐 event loop**（`on_thread_start` 內 `new_event_loop`）取代每句 `asyncio.run`；不在 shutdown close loop（daemon 與 loop 同壽命，`os._exit` 強退）。
- **print 在 caller thread**（不在 `_loop`）→ 保 SSH log 時序與 dialog flow 一致。
- **ALSA drain**：drain 時僅當還有下一句才 `sleep(0.3)`，防下個 mpg123 沖掉 ALSA buffer 截尾；即將 idle 則跳過省 0.3s。

### 3.2 `stt.py` — Deepgram Nova-3 串流 STT（`SttWorker`）

**職責**：第四個 worker（producer 形狀）；arecord 收音 → 每輪 Deepgram websocket 串流 → `speech_final` transcript 去頭尾標點 → 注入 `input_reader` 共用 queue。

**公開 API**（全委派 lazy singleton `_get_worker()`）：`prearm()` / `arm(capture=True)` / `disarm()` / `shutdown()`。

**⚠️ 重要事實**：現行 code 是「**每輪新連線**」——`disarm` 無條件收線（CloseStream + 關 ws + 收 receiver），下一輪 `prearm`/`arm` 重連。連線只活一輪（<12s）。**刻意棄持久連線**以修「用久累積辨識 lag」（早期註解仍提「持久連線」概念，以 code 為準）。

**並行模型**：無常駐 thread，每輪動態起：連線層（`_ws` 每輪新連線 + `SttReceiver` thread）+ 收音層（`_audio` arecord + `SttSender` thread）。三把鎖（`_lock` 連線狀態 / `_send_lock` 序列化所有 `ws.send` / `_connect_lock` 序列化建線）+ 停止 Event（`_conn_stop` / `_send_stop`）+ `_capturing` 閘門（receiver 只在收音窗注入，擋上一輪殘響）。
- `_ensure_connected` **鎖外建線**（阻塞網路 IO 不持 `_lock`，避免凍結 disarm/shutdown）；double-checked locking。
- `_send_lock` 必要：websockets sync client 並發 send 非 thread-safe。

**資料流**：`arecord -q -f S16_LE -r 16000 -c 6 -t raw` → `_ArecordSource.read` 反交錯抽 ch0（6 聲道 → ch0 = 處理過 ASR 聲道）→ `_send_loop` 經 `_send_lock` `ws.send`（100ms chunk）。WS URL：`model=nova-3&language=zh-TW&...&endpointing=300&smart_format=false` + 約 29 詞 KEYTERMS（contextual biasing）。收：Results → `speech_final` → `_normalize_transcript` → `sink(text)`（= `input_reader.inject`）。

**設計決策 / gotcha**：
- **ch0 抽取定版**（XVF-3000 6 聲道，降混會稀釋 + 相位互抵，2026-06-20 A/B 實證）。
- **不送 Finalize**（靠 endpointing 自然 finalize；逐輪 mid-stream Finalize 會破壞後續 utterance）。
- **首字暖機**：`prearm` 把首輪握手藏進提示音播放；`arm(capture=False)` 早麥只開收音層暖串流不注入。
- 頂層禁 import websockets（收在 `_default_ws_factory` lazy）；401 永久停用本次執行（鍵盤照常）。

### 3.3 `action.py` — 非阻塞動作（`ActionWorker(QueueWorker)`）

**職責**：動作名推背景 FIFO 消費，caller 立即返回；`Act.runAction` 在 worker thread 阻塞執行 → 動作與語音真正並行。

**公開 API**：`do(name)`（非阻塞）/ `shutdown()`。

**並行模型**：1 條常駐 daemon。**只有 `_q`，無 lock / cv / event**（與 tts 不同：vendor SDK 無 subprocess 可殺，中斷靠 vendor 內部旗號）。單 queue 單消費者 → `runAction` 無並發。

**設計決策 / gotcha**：
- **vendor lazy import 在 `on_thread_start`**（worker thread 內）：頂層不 import → Windows 可 import action 模組；但該 daemon thread 進 `on_thread_start` 會 import vendor → Windows 上 thread ImportError 死掉，主流程不受影響。
- **sticky 旗號守衛**：`stopAction()` 設 `stop_action=True` 是 sticky，只在 `runAction` 內部 loop 消耗 reset；空轉時呼叫會污染下次 runAction → `shutdown` 守衛 `if Act.runningAction:` 才 stop。
- `name` 從 `sales.constants.actions` 取常數，對應 `/home/pi/TonyPi/ActionGroups/<name>.d6a`；`.d6a` 不存在是 vendor silent print 不 raise。

### 3.4 `input_reader.py` — 非阻塞 stdin reader（`InputReader`，producer）

**職責**：背景 daemon thread 持續 `readline` push 進 queue，主線程 `read(timeout)` 取；同時是 STT / web 命令的 sink（共用同一 queue）。

**公開 API**（委派 singleton）：`read(timeout) -> str|None` / `inject(text)` / `shutdown()`。

**並行模型**：producer 形狀（1 條 reader daemon + 主線程 consumer），**不繼承 `QueueWorker`**，只 reuse `drain_queue`。只有 `_q`（thread-safe queue），**刻意不用 Lock**（queue 內建 thread-safe）。三個 producer 共用同一 queue：stdin reader（鍵盤）、`inject`（STT / web）、EOF sentinel。

**設計決策 / gotcha**：
- **bytes-level decode 根治 multibyte bug class**：`sys.stdin.buffer.readline()` 拿 bytes 自己 `decode("utf-8", errors="replace")`，繞過 TextIOWrapper buffer（解過 0xe5「invalid continuation byte」）。
- **drain-on-enter latest-wins**：`read` 進場先 `get_nowait` 清殘留只留最新一筆——避免 hawk spam 殘留漏入對話，同時不殺剛打完未消費的合法輸入。
- **shutdown 不關 stdin**（只清 queue）：曾 `sys.stdin.close()` 在 Pi 上 deadlock；daemon 隨 `os._exit(0)` 一起 die。
- `SALES_KEYBOARD=0` 時不起 reader 迴圈，但 `inject`/`read`/`shutdown` 仍照常（web / 語音驅動）。eager singleton（與 stt lazy 對比）。

### 3.5 `tts_prewarm.py` — 一次性預熱腳本（非 worker）

把固定文案一次合成進 tts 內容定址快取，commit 進 git 後 demo 斷網也能播全部固定語音。`python3.11 -m myProgram.tts_prewarm`。枚舉清單：自動掃 `l1_text`~`l5_text`+`shared` 公開 str 常數（排除含 `{` 模板）+ 手列 `HAWK_SLOGANS` + 每商品 qty prompt 插值。借用 tts 內部 helper（共用同一內容定址檔名 → 預熱資產 = runtime 快取命中）。⚠️ **勿與 demo 同時跑**（同句 `.tmp` 路徑相同，並發合成互踩寫壞檔）。

---

## 4. 跨 worker 共通模式

- **三胞胎 API 對稱**：`speak`/`do` 非阻塞 + `shutdown` cleanup；print 一律在 caller thread 保 SSH log 時序。
- **全體 `daemon=True`**：`os._exit(0)` 強退時自動 die；但 daemon die 不自動清 subprocess / sticky 旗號 → 仍需顯式 shutdown（tts terminate mpg123、action 守衛 stopAction、stt 收 arecord+ws、input 清 queue）。
- **單 queue 單消費者鐵則**：避免旗號分流 race，`input_reader` 把鍵盤 + STT + web 命令收斂到同一 queue，下游 `read` 對三來源語意一致。
- **對外動作由 `main.py` callback 注入**：worker 不知道 `sales/` 存在；`stt` 的 sink 反向注入回 `input_reader`。

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-06-21 | 初版：main.py 編排 + QueueWorker 骨架 + 四 worker 並行模型 + 預熱 / cleanup。|
