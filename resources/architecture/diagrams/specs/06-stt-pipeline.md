# 06 · STT 管線圖 — 主題 spec ＋ 實作計畫

> 報告系統圖 ⑥。**畫前已逐項回讀 `myProgram/stt.py` 全檔核對**（鐵則 1），事實附行號。風格＝淺色蠟筆（`report-design-system` 基準①②③ + `diagram-crayon.md`）。交付 `06-stt-pipeline.{html,png,svg}` 進 `diagrams/` 主層。

---

## 1. 這張要表達什麼（thesis）

**STT 是一條「每輪 arm→disarm 拋棄式串流 session」**：每輪開麥動態起兩條 daemon thread（收音層 SttSender + 連線層 SttReceiver）＋一條只活一輪（<12s）的 Deepgram websocket，把 ReSpeaker 6 聲道收音**反交錯抽出 ch0（處理過 ASR 聲道）**串給 Deepgram Nova-3，只在 `_capturing` 收音窗把 `speech_final` 注入共用 input queue；disarm 無條件收掉全部。**棄持久連線**以修「用久累積辨識 lag」。

- **Hero（珊瑚主角）＝ `ch0 抽取`（`_ArecordSource` 反交錯）**：本圖招牌決策。XVF-3000 原生只出 6 聲道（ch0 處理過 / ch1-4 生麥 / ch5 回授），降混會稀釋 ch0 並相位互抵糊掉辨識，故只抽 ch0（2026-06-20 同源 A/B 實證）。珊瑚只給這一張卡。
- **Signature 結構裝置＝「每輪一生 SESSION」cyan group frame**：把收音層 + 連線層 + 連線包進一個子框，框標「arm→disarm 一輪 <12s · 棄持久連線」，視覺說「整段每輪生滅」。
- **左側 main.py 編排 lane（blue，6 步真實序列）**：numbered 步驟在此**合理**（是真有序協議，非裝飾）。

來源副標：`per-round Deepgram Nova-3 streaming · arecord 6ch→ch0 · one websocket per turn`

---

## 2. 核對過的碼事實（`myProgram/stt.py`，逐項可回查）

### 2.1 模組級設定 / 常數
- `_ENDPOINTING_MS`＝env `STT_ENDPOINTING_MS` 預設 `300`（行 59；450 在背景音下害 speech_final 永不發→回歸 300）。
- `_PREROLL_MS`＝env `STT_PREROLL_MS` 預設 `0`（行 63；0＝不送靜音、不改行為）。
- `_CAPTURE_CHANNELS`＝env `STT_CAPTURE_CHANNELS` 預設 `6`（行 68）；`_ASR_CHANNEL`＝env 預設 `0`（行 69）。
- `CHUNK_BYTES`＝`3200`（行 85，100ms @ 16kHz 16-bit mono）。
- `KEYTERMS`≈29 詞（行 49-54：一瓶…十瓶 / 一張…十張 / 冰紅茶·紅茶·刮刮樂 / 結帳·取消·繼續·繼續選購·幾瓶·幾張）；Nova-3 contextual biasing，inference 內偏置零額外延遲。
- WS URL（行 76-81）：`wss://api.deepgram.com/v1/listen?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000&channels=1&interim_results=true&endpointing=300&smart_format=false` ＋ 逐詞 append `&keyterm=<percent-encoded>`。
- `_PUNCT`（行 30）去頭尾標點集；`_normalize_transcript`（行 33）`text.strip(_PUNCT)`，句中不動、全標點歸空字串。

### 2.2 收音層 — `_ArecordSource` / `_default_audio_factory`（行 353-414）
- arecord cmd：`arecord -q -f S16_LE -r 16000 -c <_CAPTURE_CHANNELS> -t raw`（行 407-408）→ stdout PIPE、`stdin=DEVNULL`、`stderr=DEVNULL`（行 412-413）。
- 裝置：env `STT_ARECORD_DEVICE`（如 `plughw:CARD=ArrayUAC10`）有設才 `-D` 插入（行 409-411），否則 ALSA 預設。
- `read(n)`（行 367-379）：`channels==1`→直通零反交錯；多聲道→讀滿 `(n//2)*frame_bytes`，截到整 frame（`array("h")` 切片 `samples[ch::channels]`）抽 ch0 回單聲道 bytes。`_frame_bytes = channels*2`（S16_LE）。
- `close()`（行 393）：`proc.poll() is None` 才 `terminate()`。

### 2.3 並行模型 — 每輪 arm/disarm（**重要事實**）
- **無常駐 thread**；每輪動態起：連線層（`_ws` 每輪新連線 + `SttReceiver` thread）＋ 收音層（`_audio` arecord + `SttSender` thread）。連線只活一輪（<12s，無 keepalive），**刻意棄持久連線**修累積 lag（行 91-97 docstring）。
- 三把鎖：`_lock`（連線狀態 + `_capturing` 切換）/ `_send_lock`（序列化所有 `ws.send`——websockets sync client 並發 send 非 thread-safe）/ `_connect_lock`（序列化建線：prearm 背景 vs arm 主線程，不與 `_lock` 同持）（行 110-112）。
- 停止 Event：`_conn_stop`（停 receiver）/ `_send_stop`（停 sender）。
- `_capturing` 閘門：receiver 只在收音窗注入，擋上一輪殘響 / Finalize 回覆漏入下一輪（行 98、270-272）。

### 2.4 生命週期方法
- `prearm()`（行 193-199）：非阻塞預連線，起 daemon thread `SttPrearm` 跑 `_ensure_connected`，藏首輪握手進提示音播放。快查任一成立即返（已停用 / 收音中 / 缺 key / 已連）。
- `arm(capture=True)`（行 159-191）：capture=True 開收音層（若未開）+ 進注入窗（`_capturing=True`）；capture=False 只開收音層串流暖機、不注入（早麥）；隨後 arm() 翻閘**不重開 arecord**。建線在鎖外。缺 key→印警示停用（鍵盤照常）。
- `_ensure_connected()`（行 131-157）：已連復用；未連**鎖外建線**（阻塞網路 IO 不持 `_lock`，避免凍結 disarm/shutdown）+ 鎖內寫狀態 + 起 receiver。double-checked locking（`_connect_lock`）。
- `_connect_with_retry()`（行 201-214）：非 401 失敗重試 1 次；401→永久停用本次執行（鍵盤照常）。
- `_send_loop()`（行 216-244）：`audio.read`→`ws.send`（經 `_send_lock`）；pre-roll 先 burst `_PREROLL_MS` 靜音（預設 0）；EOF / send_stop 即止。
- `_receive_loop()`（行 246-293）：`ws.recv`→JSON→`type=="Results"`→`speech_final`（**僅 `_capturing` 才注入**）；空白 speech_final 退用本句最後非空 interim（`_last_nonempty`）；雙層 try（外層包 recv＝連線死則退出重連；內層包單訊息＝格式壞印警示 continue、連線存活）；退出時若非 disarm/shutdown→標記 `_ws=None`（下次 arm 重連）。注入＝`self._sink(text)`。
- `disarm()`（行 322-341）：冪等。`_capturing=False`、收音層開著就收（停 sender + 關 arecord）→ **無條件收線**（`_close_connection`）。**不送 Finalize**（靠 endpointing 自然 finalize；逐輪 mid-stream Finalize 破壞 Deepgram 後續 utterance＝speech_final 空白漏字，2026-06-19 鐵證，行 339）。
- `_close_connection()`（行 295-320）：送 `CloseStream` + 關 ws + 收 receiver，冪等。
- `shutdown()`（行 343-345）＝disarm。
- 對外 API（lazy singleton `_get_worker`，行 429-457）：`arm(capture=True)` / `prearm()` / `disarm()` / `shutdown()`，sink＝`input_reader.inject`。import 零副作用、首次 arm 才建。

### 2.5 main.py 編排（doc 10 §1.2，`read_customer_input` @ main.py:129）
1. `stt.prearm()` 非阻塞預連線（首輪 540ms 握手藏進下面提示音）。
2. （`STT_EARLY_MIC=1`）`stt.arm(capture=False)` 提示音播放期間就開 arecord 暖串流、**不注入**。
3. `tts.wait_idle()` 等提示音播完才倒數（不扣顧客秒）。
4. （`STT_MIC_OPEN_DELAY_MS>0`）等喇叭 ALSA 尾音排空。
5. `stt.arm()` 翻注入閘（早麥則復用已開 arecord）。
6. `_tick_countdown(timeout,"timeout",input_reader.read)` 倒數讀輸入（可被打斷）。
7. `finally: stt.disarm()`——四路徑都收麥。

### 2.6 資料流（一句話）
`arecord 6ch` → `_ArecordSource` 反交錯抽 **ch0** → `_send_loop`（100ms chunk 經 `_send_lock`）→ `ws.send` → **Deepgram Nova-3 WS** → `Results`/`speech_final` → `_normalize_transcript` 去頭尾標點 → `_capturing` 閘 → `sink`＝`input_reader.inject` → **共用 input queue**（與鍵盤同一 queue、producer 端零分流）。

---

## 3. 版面計畫（左→右管線，畫布 1960×1280；座標為起手建議，implementer 可微調避免死空白）

- **標題**：`FIG.06　STT 管線`，副標見 §1。
- **legend（左上，~60,150）色彩語意 · thread 生命週期**（5-6 列）：
  - blue＝主線程編排（read_customer_input）
  - cyan＝每輪一生 session thread（Sender/Receiver）
  - purple＝注入點 · 共用 input queue
  - orange＝一次性（SttPrearm）
  - gray＝子程序 arecord · 雲端 Deepgram（chip）
  - （珊瑚不入 legend：★ 主角 ch0 抽取，比照①慣例）
- **A · main.py 編排 lane（blue，左欄縱列 6 步）**：§2.5 的 prearm→arm(capture=False)→wait_idle→arm()→countdown read→finally disarm，每步小卡或一列、向下串箭頭。標「per-round 編排」。
- **B · 「每輪一生 SESSION」cyan group frame（中上，包 C+D+ 連線）**，框標 `STT SESSION · arm→disarm 一輪 <12s · 棄持久連線`。
- **C · 收音層（frame 內上半，左→右）**：
  - `arecord` chip（gray）：`-q -f S16_LE -r16000 -c6 -t raw` · stdin=DEVNULL · 6ch XVF-3000
  - → **ch0 抽取 HERO（珊瑚）**：`_ArecordSource.read` · 反交錯 `samples[0::6]` · 降混稀釋+相位互抵（2026-06-20 A/B）
  - → `SttSender`（cyan card）：`_send_loop` producer · 100ms chunk(3200B) 經 _send_lock · pre-roll 靜音暖機(預設 0)
  - → `ws.send` → Deepgram
- **D · 雲端（frame 右 / 跨出皆可）**：`Deepgram Nova-3 WS` chip/card（gray）：`model=nova-3 language=zh-TW 16kHz · endpointing=300 smart_format=false · +29 詞 KEYTERMS biasing`
- **E · 連線層（frame 內下半，右→左回收）**：
  - `SttReceiver`（cyan card）：`_receive_loop` consumer · `ws.recv→Results` · `speech_final`（空白退用最後非空 interim）
  - → `_normalize_transcript`（去頭尾標點，句中不動）
  - → `_capturing` 閘（僅收音窗注入，擋上輪殘響 / Finalize 漏入下輪）
  - → `sink = input_reader.inject`
- **F · 輸出（purple，右下）**：`input queue` — 與鍵盤共用單一 queue（producer 端零分流）。inject 線可走細珊瑚或墨色 flow（珊瑚 hero 已給 ch0，避免雙主角；inject 線用墨色 flow 即可）。
- **G · 一次性（orange，側欄）**：`SttPrearm` — 背景 daemon 跑 `_ensure_connected` · 藏首輪 ~540ms 握手 · 401 永久停用（鍵盤照常）。
- **note（左下「所以呢 · STT 三鐵則」）**：
  1. **每輪新連線**：disarm 無條件收線（CloseStream+關 ws+收 receiver），下輪 prearm/arm 重連——連線只活一輪（<12s）修「用久累積辨識 lag」。
  2. **不送 Finalize**：靠 endpointing(300ms) 自然 finalize；逐輪 mid-stream Finalize 破壞 Deepgram 後續 utterance（speech_final 空白漏字，2026-06-19 鐵證）。
  3. **ch0 抽取定版** + 頂層禁 import websockets（lazy 收在 `_default_ws_factory`）；`_capturing` 閘擋跨輪洩漏；三鎖序列化建線 / send。

---

## 4. 邊（edges）
- 主管線（墨色 `.flow` + `#ah` 箭頭頭）：A 各步縱向下串；arecord→ch0→Sender→（ws.send）→Deepgram→Receiver→normalize→gate→inject→queue。線走 lane 正中、零交叉、不擦卡；標籤（音框 / ws.send / ws.recv / inject）落卡間空白、halo 描白。
- prearm 虛線 `.async`（7 5 dash）連到連線層（背景預連，非主資料流）。
- **不畫 process 外框**；珊瑚只給 ch0 hero 卡。

## 5. 鐵則自查（交付前）
逐項回比 `myProgram/stt.py`：狀態 / 轉移 / 計時（endpointing 300 / chunk 3200B / 連線 <12s）/ 欄位（_capturing/_send_lock/_conn_stop）/ 聲道（6ch→ch0）全部來自實際碼，無捏造。QA-C 必讀 `stt.py` 核對。
