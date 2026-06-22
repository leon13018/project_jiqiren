# 07 · TTS 管線圖 — 主題 spec ＋ 實作計畫

> 報告系統圖 ⑦。**畫前已逐項回讀 `myProgram/tts.py` / `tts_prewarm.py` / `queue_worker.py` 全檔核對**（鐵則 1），事實附行號。風格＝淺色蠟筆（`report-design-system` 基準①②③ + `diagram-crayon.md`）。交付 `07-tts-pipeline.{html,png,svg}` 進 `diagrams/` 主層。

---

## 1. 這張要表達什麼（thesis）

**TTS 是一條「queue → 三層取得 mp3 → mpg123 播放」的非阻塞管線，靠內容定址快取讓雲端 TTS 斷網可播、靠 1-deep prefetch 把句間靜默壓到趨近 0**。caller `speak` 立即返回；常駐 daemon `_process` 每輪取一句 → 三層 fallback 取得 mp3（① prefetch 標記 → ② 內容定址快取命中 → ③ 現場 edge-tts 合成）→ `mpg123` 播放，**播放阻塞期間預合成下一句進快取**。

- **Hero（珊瑚主角）＝ `內容定址快取`（命中/未命中分支）**：本圖招牌。key＝SHA1(`VOICE|rate|text`)，任一合成參數變即自然失效；命中＝零合成零網路（斷網可播）、未命中＝走雲端 synth 再原子入快取。珊瑚只給這一張卡（命中/未命中由此分流）。
- **Signature 結構裝置＝珊瑚 `1-deep prefetch` 弧**：一條珊瑚弧從「播放等待」回繞到「快取」，表「播放阻塞期間合成下一句」——靜態圖裡唯一的「重疊/回流」語意，串起本圖的時間性。
- **三層 fallback numbered ①②③ 在此合理**（是真有序 fallback，非裝飾）。

來源副標：`queue → 3-layer mp3 fetch (content-addressed cache) → mpg123 · 1-deep prefetch hides synth latency`

---

## 2. 核對過的碼事實（逐項可回查）

### 2.1 `tts.py` 模組級常數
- `_VOICE`＝env `SALES_VOICE` 預設 `0`（行 58；echo print gate，demo 隱藏）。
- `VOICE`＝`"zh-TW-HsiaoChenNeural"`（行 60，台灣女聲）。
- `_CACHE_DIR`＝package-anchored `<模組目錄>/tts_cache`（行 64，**非 cwd**；Pi 隨 git pull 取得預熱資產；執行期自我增長）。
- `ALSA_DRAIN_SEC`＝`0.3`（行 70；Pi 經驗值，短句尾巴 ~200ms + 安全餘裕 ~100ms）。
- 語速三段（行 80-84）：`RATE_SHORT`＝`+3%`（<14 字）/ `RATE_MEDIUM`＝`+6%`（14-22）/ `RATE_LONG`＝`+12%`（≥23）；`MEDIUM_THRESHOLD`＝14、`LONG_THRESHOLD`＝23。edge-tts rate 格式 `[+-]\d+%`；Azure 有效 -50%~+100%；`len(text)` 中文每字 1 code point、含標點。

### 2.2 `tts.py` helper
- `_pick_rate(text)`（行 87）：≥23 長 / ≥14 中 / else 短。
- `_cache_path_for(text)`（行 96）：內容定址。key＝`f"{VOICE}|{_pick_rate(text)}|{text}"`.encode → `os.path.join(_CACHE_DIR, sha1(key).hexdigest()+".mp3")`。同文字（同 VOICE+rate）永遠同檔名。
- `_store_into_cache(tmp,cache)`（行 102）：`os.replace` 原子搬移（防中斷殘留半寫檔）；tmp 缺失 no-op（測試 seam）。
- `_synthesize(text,out)`（行 109）：`await edge_tts.Communicate(text=text, voice=VOICE, rate=_pick_rate(text)).save(out)`（async，覆寫）。

### 2.3 `QueueWorker` 基底（`queue_worker.py`）
- `__init__`（行 45）：`self._q = queue.Queue()` + 立即啟動 daemon thread 跑 `_loop`。
- `_loop`（行 54）：`on_thread_start()` → `while True: item=_q.get(); try _process(item) finally on_done(item)`。
- `submit(item)`（行 49）：`_q.put`（TtsWorker **刻意不經此**——say 需在 `_cv` 臨界區原子 inc `_pending` + put，避免 R1 race）。
- abstract `_process`；hook `on_thread_start`（pass；ActionWorker lazy import vendor）/ `on_done`（pass；TtsWorker dec+notify）。`drain()`／模組 `drain_queue(q)`。
- 兩設計決定：基底**無 except-all / 無 on_error**（未知例外殺 thread＝現狀，純重構零行為改變紅線）；`shutdown` 不入基底（tts/action 收尾順序相反）。

### 2.4 `TtsWorker(QueueWorker)`（`tts.py`）
- `thread_name="TtsWorker"`（行 152）。
- 欄位**先設、`super().__init__()` 後呼叫**（行 154-173；基底立即啟 thread，thread 第一時間 on_done 觸碰 `_cv`/`_pending`）：`_proc`(None) / `_lock`(保護 _proc) / `_cv`(Condition) / `_pending`(int=0，queued+processing 數) / `_prefetched`(tuple[str,str]|None，僅 worker thread 觸碰、不需鎖)。
- `on_thread_start()`（行 175-185）：worker thread 常駐 event loop（`asyncio.new_event_loop`+`set_event_loop`，取代每句 `asyncio.run`）；**不在 shutdown close**（daemon 與 loop 同壽命、`os._exit` 強退）；`os.makedirs(_CACHE_DIR, exist_ok=True)`。
- `_peek_next()`（行 187）：`with self._q.mutex: queue[0]`（本 thread 唯一消費者，偷看不取出）。
- `say(text)`（行 193-205）：非阻塞 producer。`with self._cv: self._pending += 1; self._q.put(text)`——**先 inc 後 put（順序關鍵，修 R1 race）**。FIFO 不中斷。
- `on_done(text)`（行 207）：`with self._cv: self._pending -= 1; if 0: notify_all`。
- `_process(text)`（行 218-355）single-iteration body：
  - **階段 1 取得 mp3（三層 fallback）**：
    - ① `self._prefetched is not None and _prefetched[0]==text` → `source="prefetch"`、`mp3_path=_prefetched[1]`、清 `_prefetched`（行 232）。
    - ② `os.path.exists(cache_path)` → `source="cache"`、`mp3_path=cache_path`——**零合成零網路、斷網可播**（行 236）。
    - ③ else `source="synth"`：`tmp=cache_path+".tmp"` → `self._loop_obj.run_until_complete(_synthesize(text,tmp))`（edge-tts 雲端）→ `_store_into_cache(tmp,cache)` 原子 os.replace → `mp3_path=cache_path`；synth 失敗 noisy print + `return`（行 241-261）。
  - **階段 2 播放**：`with self._lock: self._proc = subprocess.Popen(["mpg123","-q",mp3_path], stdin=subprocess.DEVNULL)`（短臨界區，不包 wait）。
  - **階段 2.5 prefetch（signature）**：`nxt=_peek_next()` → 若已在快取設 `_prefetched`，否則 `run_until_complete(_synthesize(nxt,...))`→store→set `_prefetched`（失敗靜默）（行 285-302）。
  - 等播完：`returncode = self._proc.wait()`（**不持 lock**——shutdown 可 terminate；SIGTERM 回 -15）。`returncode!=0` → raise `CalledProcessError` → noisy print continue（行 305-316）。
  - `finally: with self._lock: self._proc=None`（行 340-342）。
  - **階段 3 drain**：成功且 `_peek_next() is not None` 才 `time.sleep(ALSA_DRAIN_SEC)`（行 350-352）；即將 idle 跳過省 0.3s。
- `_lock` 範圍刻意短：只包 Popen spawn + finally 清 None，**不包 `_proc.wait()`**（否則 shutdown 拿不到 lock 2-5s）。
- `wait_idle(max_wait=30.0)`（行 357）：阻塞至 `_pending=0` 或超時，回 True（drained）/ False（timeout）。30s 從 10s bump（hawk slogan+L2 entry back-to-back ~12-15s）。
- `is_idle()`（行 388）：非阻塞 `_pending==0`（L1 hawk polling 用）。
- `shutdown()`（行 399）：`with self._lock:` terminate 當前 mpg123（SIGTERM）+ `self.drain()` 清 queue。
- 對外 API：`speak(text)`（行 430，非阻塞；`print` 在 **caller thread**、`_VOICE` gate echo）/ `speak_and_wait(text,max_wait=30)`（行 445，say+wait_idle，wall-clock budget）/ `wait_idle` / `is_idle` / `shutdown`。模組 singleton `_worker = TtsWorker()`（行 427，import 即啟 daemon）。
- `stdin=DEVNULL`：mpg123 預設讀父 stdin 偷 control char（q/s/p/+/-）會吃掉 user 輸入或誤觸 quit（行 264-273）。

### 2.5 `tts_prewarm.py`（一次性 bootstrap，**非 worker**）
- `python3.11 -m myProgram.tts_prewarm`（Pi，需網路）→ `tts_cache/<hash>.mp3` commit 進 git → demo 斷網也能播全部固定語音。
- ⚠️ **勿與 demo 同時跑**（同句 `.tmp` 路徑相同，並發合成互踩寫壞檔）。
- 枚舉（行 41-65）：自動掃 `l1_text~l5_text`+`shared` 公開 str 常數（排除含 `{` 模板）＋手列 `HAWK_SLOGANS`＋每商品 qty prompt/clarify/at-cap 插值；去重保序。
- `main()`（行 68）：makedirs；逐句若快取存在 skip，否則 `asyncio.run(_synthesize)` → `_store_into_cache`；計 new/skip/fail。
- 借 tts 內部 helper（`_CACHE_DIR`/`_cache_path_for`/`_store_into_cache`/`_synthesize`）→ **共用同一內容定址檔名 = runtime 快取命中**。

### 2.6 資料流（一句話）
`speak(text)` → `say`（持 `_cv` 原子 inc `_pending` + put）→ **FIFO `_q`** → daemon `_process` 取一句 → **三層取 mp3：① prefetch → ② 內容定址快取命中 → ③ edge-tts 雲端 synth + 原子入快取** → `mpg123 -q`(stdin=DEVNULL) 播放 → ALSA → 喇叭；**播放阻塞期間 prefetch 下一句進快取**；成功且還有下一句才 `sleep(0.3)` drain。

---

## 3. 版面計畫（左→右管線，畫布 1960×1280；座標為起手建議，implementer 可微調避免死空白）

- **標題**：`FIG.07　TTS 管線`，副標見 §1。
- **legend（左上）色彩語意**（6 列）：
  - blue＝caller / 主線程（speak/say）
  - green＝常駐 daemon（TtsWorker _process）
  - purple＝FIFO queue · 同步原語（_cv+_pending）
  - cyan＝內容定址快取層（cache dir / store）
  - orange＝一次性（tts_prewarm bootstrap）
  - gray＝子程序 mpg123 · 雲端 edge-tts（chip）
  - （珊瑚不入 legend：★ 主角 內容定址快取）
- **A · caller（blue，左欄）**：
  - `speak(text)` card：對外 API · 非阻塞入 queue · `print` 在 caller thread（保 SSH log 時序）· _VOICE gate echo
  - → `say(text)`：producer · 持 `_cv` **先 inc `_pending` 後 put**（R1 race fix）
- **B · queue / 同步（purple）**：`FIFO _q`（單 queue 單消費者）＋ `_cv + _pending` chip（Condition+int 三方同步：say / on_done / wait_idle）。
- **C · TtsWorker daemon `_process`（green，中央主體）內含三層 fallback（珊瑚 hero 在 ②）**：
  - ① `prefetch 命中`（cyan/green 小卡）：`_prefetched[0]==text` → mp3（瞬時，上輪預取）
  - ② **內容定址快取 HERO（珊瑚）**：`os.path.exists(cache_path)` 命中 → 零合成零網路、斷網可播 · key=SHA1(`VOICE|rate|text`)
  - ③ `未命中 synth`：`run_until_complete(_synthesize)` → edge-tts（雲端，rate 三段 +3/+6/+12%）→ `_store_into_cache` 原子 os.replace → cache
- **D · 播放（green→gray）**：`mpg123 -q`（Popen，stdin=DEVNULL · returncode≠0→CalledProcessError noisy continue）→ `ALSA` → 喇叭 chip。
- **E · 1-deep prefetch 弧（珊瑚 signature）**：一條珊瑚 `.hawk` 弧從「播放等待 / mpg123」回繞到「內容定址快取」，標 `階段2.5 · 播放阻塞期間預合成下一句`。`_peek_next`→synth→cache→set `_prefetched`。
- **F · ALSA drain（小註）**：成功且還有下一句才 `sleep(0.3s)`；即將 idle 跳過省 0.3s（行為註腳，可掛 D 旁小 chip 或入 note）。
- **G · 常駐 event loop（小註/chip）**：`on_thread_start` `new_event_loop`+`set_event_loop`（取代每句 asyncio.run）；不在 shutdown close（daemon 與 loop 同壽命，os._exit）。
- **H · 一次性（orange，側欄）**：`tts_prewarm` — 枚舉固定文案（l1~l5_text+shared+HAWK_SLOGANS+商品 qty 插值）→ asyncio.run synth → seed cache · git commit → 斷網可播 · 共用同一內容定址檔名＝runtime 快取命中 · ⚠️ 勿與 demo 並跑。一條虛線 `.async` 指向內容定址快取（預先 seed）。
- **note（左下「所以呢 · TTS 三鐵則」）**：
  1. **內容定址快取**：key＝SHA1(`VOICE|rate|text`)，任一合成參數變即自然失效；package-anchored（非 cwd）；執行期自我增長（動態句首播後永久免合成、斷網可播）。
  2. **1-deep prefetch**：播放阻塞期間合成下一句進快取，句間靜默從一次 synth round-trip 降到趨近 0（單 thread 重疊、零新鎖、各句快取檔名互異）。
  3. **常駐 event loop** 取代每句 asyncio.run；`print` 在 caller thread 保 SSH log 時序；ALSA drain 僅在還有下一句時 sleep 0.3s（防 mpg123 沖 ALSA buffer 截尾）。

---

## 4. 邊（edges）
- 主管線（墨色 `.flow` + `#ah`）：speak→say→queue→_process（三層）→mpg123→ALSA→喇叭。線走 lane 正中、零交叉、不擦卡；標籤（put / 取一句 / mp3 / 播放）落卡間空白、halo 描白。
- **1-deep prefetch 珊瑚 `.hawk` 弧 + `#ah-hawk`**（signature）：播放等待→內容定址快取（回流預取下一句）。
- `tts_prewarm` 虛線 `.async`（7 5 dash）→ 內容定址快取（預先 seed，非 runtime 主流）。
- **不畫 process 外框**；珊瑚只給內容定址快取 hero 卡 + prefetch 弧（同色家族＝快取主題）。

## 5. 鐵則自查（交付前）
逐項回比三檔原始碼：三層 fallback 順序 / 計時（drain 0.3s / rate +3·+6·+12% / 字數閾值 14·23 / wait_idle 30s）/ key 構成（SHA1 VOICE|rate|text）/ 欄位（_pending/_cv/_proc/_prefetched）全部來自實際碼，無捏造。**勿把「持久 prefetch」畫成多深**——只 1-deep（`_prefetched` 單一 tuple）。QA-C 必讀 `tts.py`/`tts_prewarm.py`/`queue_worker.py` 核對。
