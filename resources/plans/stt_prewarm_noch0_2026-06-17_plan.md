# STT prewarm（不加 ch0）實作 plan

> **For agentic workers:** 走專案 SDD（sales-coder 實作 → Iron Law → 三段審）。Steps 用 checkbox 追蹤。
> Spec：`resources/specs/stt_prewarm_noch0_2026-06-17_spec.md`（WHAT）。本檔 = HOW，TDD。
> 基線 = Phase 1（`734781e`：`-c 1` mono、arm 做全部、tuple session）。
> **單一增量**：在 Phase 1 上加 v2 式 prewarm（dict session + `_open_ws`/`prewarm`/`_keepalive_loop`、arm 兩段）。**音源工廠不動**（`-c 1`、無 ch0）。機制照 v2 `d8c8d77`。

**Goal**：prompt 播放期背景預連 Deepgram ws + KeepAlive 維持，播完 arm 才開麥送音訊 → 省 ws 握手延遲、辨識準確度不變。

**測試指令**：`python -m pytest tests/stt/`（最終加 `tests/sales/`）。Windows 全 fake；`python` 沒裝 pytest 時用 `py -m pytest`。

---

## Task 1：SttWorker Phase1→prewarm refactor + 加 prewarm 測試

**Files**：Modify `myProgram/stt.py`（`__init__`/`arm`/`disarm` + 新增 `_open_ws`/`prewarm`/`_keepalive_loop` + 模組層 `prewarm`）；Modify `tests/stt/test_worker.py`（加 4 測試）

### Step 1：先寫 RED — 在 `tests/stt/test_worker.py` 末尾加 4 個 prewarm 測試

```python
def test_prewarm_connects_keepalive_no_audio():
    ws = FakeWs([])
    audios = []
    def audio_factory():
        a = FakeAudioSource()
        audios.append(a)
        return a
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=audio_factory,
                       keepalive_interval=0.01)
    worker.prewarm()
    assert worker.is_armed()                          # session 已起（連線熱著）
    assert audios == []                               # 未開麥（arecord 沒被建）
    assert wait_until(lambda: len(ws.sent) > 0)       # 有送東西
    assert all(json.loads(m).get("type") == "KeepAlive" for m in ws.sent)  # 全是 KeepAlive、非音訊
    worker.disarm()


def test_arm_after_prewarm_sends_audio():
    ws = FakeWs([_results("我要紅茶兩杯。", speech_final=True)])
    calls = []
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws,
                       audio_factory=lambda: FakeAudioSource([b"\x01\x02"]),
                       keepalive_interval=0.01)
    worker.prewarm()                                  # 連線 + KeepAlive
    worker.arm()                                      # 停 KeepAlive → 開麥送真實
    assert wait_until(lambda: b"\x01\x02" in ws.sent)  # 真實音訊送出
    assert wait_until(lambda: calls == ["我要紅茶兩杯"])  # 顧客辨識注入
    worker.disarm()


def test_prewarm_then_arm_reuses_connection():
    factory_calls = []
    def ws_factory(key):
        factory_calls.append(key)
        return FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=ws_factory, audio_factory=FakeAudioSource,
                       keepalive_interval=0.01)
    worker.prewarm()
    worker.arm()                                      # 重用 prewarm 連線，不另開 ws
    assert factory_calls == ["test-key"]
    worker.disarm()


def test_module_prewarm_delegates(monkeypatch):
    import myProgram.stt as stt_mod
    monkeypatch.setattr(stt_mod, "_worker", None)
    monkeypatch.setattr(stt_mod, "_default_ws_factory", lambda key: FakeWs())
    monkeypatch.setattr(stt_mod, "_default_audio_factory", lambda: FakeAudioSource())
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    stt_mod.prewarm()
    assert stt_mod._worker.is_armed()
    stt_mod.disarm()
```

- [ ] **Step 2：跑見 FAIL**
Run：`py -m pytest tests/stt/test_worker.py -k "prewarm" -v`
Expected：FAIL（`SttWorker` 無 `prewarm`、`__init__` 無 `keepalive_interval`）。

### Step 3：refactor `myProgram/stt.py`

3a. `__init__` 改（加 `keepalive_interval`、session dict 註解）：
```python
    def __init__(self, sink, api_key=None, audio_factory=None, ws_factory=None,
                 keepalive_interval=5.0):
        self._sink = sink
        self._api_key = api_key
        self._audio_factory = audio_factory or _default_audio_factory
        self._ws_factory = ws_factory or _default_ws_factory
        self._keepalive_interval = keepalive_interval  # prewarm 期維持連線間隔（秒）
        self._lock = threading.Lock()
        self._session = None      # dict|None: stop/ws/receiver/keepalive/sending/audio/sender
        self._disabled = False    # 缺 key / 401 → 本次執行停用（鍵盤照常）
```

3b. 在 `is_armed` 之後、`arm` 之前**新增** `_open_ws`：
```python
    def _open_ws(self) -> bool:
        """caller 持 self._lock。連 ws + 起 receiver + keepalive（不開麥、不送音訊）。
        缺 key → 停用；連線失敗 → 放棄。回傳 session 是否就緒；已有 session 直接 True。"""
        if self._disabled:
            return False
        if self._session is not None:
            return True
        if not self._api_key:
            print("[語音辨識] ⚠️ 未設定 DEEPGRAM_API_KEY，STT 停用（鍵盤輸入照常）")
            self._disabled = True
            return False
        ws = self._connect_with_retry()
        if ws is None:
            return False  # 本輪放棄（已印原因）
        stop = threading.Event()
        sending = threading.Event()  # set 後 keepalive 停（音訊接手維持連線）
        receiver = threading.Thread(
            target=self._receive_loop, args=(ws, stop),
            name="SttReceiver", daemon=True)
        keepalive = threading.Thread(
            target=self._keepalive_loop, args=(ws, stop, sending),
            name="SttKeepAlive", daemon=True)
        self._session = {"stop": stop, "ws": ws, "receiver": receiver,
                         "keepalive": keepalive, "sending": sending,
                         "audio": None, "sender": None}
        receiver.start()
        keepalive.start()
        return True

    def prewarm(self) -> None:
        """預熱：連 ws + 起 receiver/keepalive，不開麥不送音訊（機器人聲不進 Deepgram）。冪等。"""
        with self._lock:
            self._open_ws()
```

3c. `arm` 整個方法**替換**為兩段版（確保連線 → 開麥）：
```python
    def arm(self) -> None:
        """開始送顧客音訊：確保連線（未 prewarm 則即連）→ 停 keepalive + 開 arecord/sender。冪等。"""
        with self._lock:
            if self._disabled:
                return
            if not self._open_ws():
                return  # 缺 key / 連線失敗（已印原因）
            s = self._session
            if s["sender"] is not None:
                return  # 已 armed → no-op
            s["sending"].set()  # 通知 keepalive 停送（音訊接手維持連線）
            audio = self._audio_factory()
            sender = threading.Thread(
                target=self._send_loop, args=(s["ws"], audio, s["stop"]),
                name="SttSender", daemon=True)
            s["audio"] = audio
            s["sender"] = sender
            sender.start()
```

3d. 在 `_connect_with_retry` 之後、`_send_loop` 之前**新增** `_keepalive_loop`：
```python
    def _keepalive_loop(self, ws, stop, sending) -> None:
        """prewarm 期週期送 KeepAlive（text frame）維持 Deepgram 連線；arm 後 sending
        set → 停送（音訊接手維持）。stop（disarm）或 ws 關即止。"""
        try:
            while not stop.wait(self._keepalive_interval):
                if not sending.is_set():
                    ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception:
            pass  # ws 已關（disarm / 斷線）→ 靜默結束
```

3e. `_send_loop` / `_receive_loop` **不動**。

3f. `disarm` 整個方法**替換**為 dict 版（join 三 thread）：
```python
    def disarm(self) -> None:
        """冪等收麥：stop → 殺音源(若有) + 關 ws → join receiver/keepalive/sender(各若非 None)。"""
        with self._lock:
            if self._session is None:
                return
            s = self._session
            self._session = None
            s["stop"].set()
            if s["audio"] is not None:
                s["audio"].close()
            try:
                s["ws"].close()
            except Exception:
                pass  # 已斷線的 ws close 可能 raise——cleanup 路徑安全吞掉
        for th in (s["receiver"], s["keepalive"], s["sender"]):
            if th is not None:
                th.join(timeout=1.0)
```

3g. 模組層：在 `def arm()` **之前**新增 `def prewarm()`：
```python
def prewarm() -> None:
    """對外 API：預熱連線（read_customer_input 進場、疊在 TTS 播放上呼叫）。"""
    _get_worker().prewarm()
```
（`_default_audio_factory`/`_ArecordSource`/`_default_ws_factory`/`_get_worker`/`arm`/`disarm`/`shutdown` 不動——音源維持 `-c 1`、無 ch0。）

- [ ] **Step 4：跑見 PASS（含既有不破）**
Run：`py -m pytest tests/stt/ -v`
Expected：全 passed。特別確認既有 `test_arm_idempotent_single_session`（arm 兩次只連一次 ws）、`test_disarm_closes_audio_and_allows_rearm`（re-arm 起全新 session）、`test_no_key_disables_and_warns_once`（缺 key 印一次、not armed）、`test_sender_streams_audio_chunks`（arm 直呼送真實 chunks）皆綠。

- [ ] **Step 5：commit（code 第一段——stt.py + test_worker.py）**
> 與 Task 2 合併為單一 code commit 亦可；若分開，先別 commit，等 Task 2 完一起 commit（見 Task 2 Step 4）。

---

## Task 2：main.py 佈線 prewarm + wireup 測試

**Files**：Modify `myProgram/main.py`（`read_customer_input`）；Modify `tests/stt/test_main_wireup.py`（fixture + ordering 斷言）

### Step 1：先寫 RED — 改 `tests/stt/test_main_wireup.py`

1a. `wired` fixture 的 `fake_stt` 加 `prewarm` stub（否則 main 呼叫會 AttributeError）：
```python
    fake_stt = types.SimpleNamespace(
        prewarm=lambda: calls.append("prewarm"),
        arm=lambda: calls.append("arm"),
        disarm=lambda: calls.append("disarm"))
```

1b. `test_arm_after_wait_idle_and_disarm_on_input` 的 ordering 斷言加 prewarm（prewarm 須在 wait_idle 之前）：
```python
def test_arm_after_wait_idle_and_disarm_on_input(wired):
    sim, calls, monkeypatch = wired
    _stub_input(monkeypatch, calls, "好")
    assert sim.read_customer_input(timeout=5) == "好"
    assert (calls.index("prewarm") < calls.index("wait_idle")
            < calls.index("arm") < calls.index("read"))
    assert calls[-1] == "disarm"
```

- [ ] **Step 2：跑見 FAIL**
Run：`py -m pytest tests/stt/test_main_wireup.py -v`
Expected：FAIL（main 未呼叫 `prewarm`／無 `prewarm` import → AttributeError 或 ordering 斷言 `ValueError: 'prewarm' is not in list`）。

### Step 3：改 `myProgram/main.py` `read_customer_input`

把現有開頭（lazy import tts + wait_idle）這段：
```python
        # 等 TTS 播完才開始倒數（max_wait=30s 防 synth/mpg123 hang 永久阻塞）。
        # Lazy import 對齊既有 speak callback pattern（Windows pytest 不觸發 edge_tts import）。
        from myProgram import tts
        tts.wait_idle()
        from myProgram import input_reader
```
**替換**為（wait_idle 前先 prewarm）：
```python
        # 等 TTS 播完才開始倒數（max_wait=30s 防 synth/mpg123 hang 永久阻塞）。
        # Lazy import 對齊既有 speak callback pattern（Windows pytest 不觸發 edge_tts import）。
        from myProgram import stt
        # STT prewarm（v2 式來源端閘）：進場先在 prompt 播放期背景預連 Deepgram ws +
        # KeepAlive 維持、**不開麥不送音訊**（機器人聲不進辨識）→ wait_idle 播完後 arm
        # 才開麥，省掉 ws 握手延遲、且無自我回授。
        stt.prewarm()
        from myProgram import tts
        tts.wait_idle()
        from myProgram import input_reader
```

並把後面原本的 stt import + 註解這段：
```python
        from myProgram import stt
        # STT Phase 1：TTS 播完才開麥（arm 冪等；缺 key 自動停用走純鍵盤）。
        # finally 保證三條路徑（拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        stt.arm()
```
**替換**為（stt 已於上方 import，去重複 import；arm 註解更新）：
```python
        # TTS 播完才 arm 開麥（連線已於 prewarm 預熱，省握手；arm 冪等、缺 key 自動停用走純鍵盤）。
        # finally 保證三條路徑（拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        stt.arm()
```

- [ ] **Step 4：跑見 PASS + 全回歸**
Run：`py -m pytest tests/stt/ tests/sales/`
Expected：sales 592 + stt 全綠（621 基線 + 4 新 prewarm 測試）。

- [ ] **Step 5：commit（單一 code commit）**
```bash
git add myProgram/stt.py myProgram/main.py tests/stt/test_worker.py tests/stt/test_main_wireup.py
git commit -m "feat(stt): v2 式 prewarm 預熱連線（保留 -c 1 mono、不加 ch0）"
git branch --contains $(git rev-parse HEAD)   # 自驗落 worktree-stt-prewarm-noch0
```

---

## 完成檢查（主 agent Iron Law）
- `py -m pytest tests/stt/ tests/sales/` → `N passed`（sales 592 + stt 625 左右）。
- `git branch --contains <SHA>` → `worktree-stt-prewarm-noch0`。
- grep `_extract_ch0` / `_CHANNELS` / `-c", "6` 在 stt.py = 0（確認**沒有**意外引入 ch0）。
- grep `KeepAlive` 在 stt.py = 1（prewarm 機制在）；`stt.prewarm()` 在 main.py = 1 且在 `wait_idle` 之前。
