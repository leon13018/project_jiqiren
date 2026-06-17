# STT 暖機 arecord（消除開麥裁切）實作 plan

> **For agentic workers:** 走專案 SDD（sales-coder → Iron Law → 三段審）。
> Spec：`resources/specs/stt_warm_arecord_2026-06-17_spec.md`（WHAT）。本檔 = HOW，TDD。
> 基線 = main `ead8a13`（v2 式 keepalive prewarm + `-c 1` 降混）。
> **單一增量**:prewarm 機制 keepalive-based → silence-based（arecord 提前暖機、去 keepalive）。**音源工廠不動**（`-c 1` 降混）。`main.py` 不動。

**Goal**:arecord 在 prewarm 就暖機錄音、暖機期送靜音、arm 即切真實 → 開麥零裁切,修「刮刮樂被切頭」。

**測試指令**:`py -m pytest tests/stt/`（最終加 `tests/sales/`）。本機 `python` 沒裝 pytest。

---

## Task 1：SttWorker keepalive→silence prewarm + 更新測試

**Files**：Modify `myProgram/stt.py`（`__init__`/`_open_ws`→`_start_session`/`prewarm`/`arm`/`_send_loop`/`disarm`、刪 `_keepalive_loop`）；Modify `tests/stt/test_worker.py`（更新 prewarm 測試 + 加 `_RepeatSource`）

### Step 1：先寫 RED — 更新 `tests/stt/test_worker.py`

1a. import 後（`_results` 函式附近）**新增** `_RepeatSource` helper：
```python
class _RepeatSource:
    """持續回傳同一 chunk（驗 mute/送真實的連續 sender 迴圈；FakeAudioSource 耗盡即 EOF 不適用）。"""
    def __init__(self, chunk):
        self._chunk = chunk
        self.closed = False
    def read(self, n):
        return b"" if self.closed else self._chunk
    def close(self):
        self.closed = True
```

1b. **替換** `test_prewarm_connects_keepalive_no_audio` 整個函式為（暖 arecord + 送靜音）：
```python
def test_prewarm_warms_arecord_sends_silence():
    ws = FakeWs([])
    src = _RepeatSource(b"\xAA\xBB")
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=lambda: src)
    worker.prewarm()
    assert worker.is_armed()                                  # session 已起（含 arecord 暖機）
    assert wait_until(lambda: len(ws.sent) > 0)               # sender 有在送
    assert b"\xAA\xBB" not in ws.sent                         # 真實聲（機器人）絕不送出
    assert all(m == b"\x00\x00" for m in ws.sent)             # 送的全是等長靜音
    worker.disarm()
```

1c. **替換** `test_arm_after_prewarm_sends_audio` 整個函式為（arm 解 mute 送真實）：
```python
def test_arm_unmutes_to_real_audio():
    ws = FakeWs([_results("我要紅茶兩杯。", speech_final=True)])
    calls = []
    src = _RepeatSource(b"\xAA\xBB")
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=lambda: src)
    worker.prewarm()                                          # mute（送靜音）
    worker.arm()                                              # 解 mute → 送真實
    assert wait_until(lambda: b"\xAA\xBB" in ws.sent)         # 真實音訊送出
    assert wait_until(lambda: calls == ["我要紅茶兩杯"])      # 顧客辨識注入
    worker.disarm()
```

1d. `test_prewarm_then_arm_reuses_connection`：**保留不動**（prewarm 起 session、arm 重用同 ws，仍成立）。`test_module_prewarm_delegates`：**保留不動**（prewarm 起 session、is_armed 仍成立）。

- [ ] **Step 2：跑見 FAIL**
Run：`py -m pytest tests/stt/test_worker.py -k "prewarm or unmute" -v`
Expected：FAIL（v2 prewarm 不起 arecord、送 KeepAlive 非靜音）。

### Step 3：改 `myProgram/stt.py`

3a. `__init__` **替換**（去 `keepalive_interval`、session dict 改）：
```python
    def __init__(self, sink, api_key=None, audio_factory=None, ws_factory=None):
        self._sink = sink
        self._api_key = api_key
        self._audio_factory = audio_factory or _default_audio_factory
        self._ws_factory = ws_factory or _default_ws_factory
        self._lock = threading.Lock()
        self._session = None      # dict|None: stop/ws/receiver/audio/sender/live
        self._disabled = False    # 缺 key / 401 → 本次執行停用（鍵盤照常）
```

3b. **替換** `_open_ws` 整個方法為 `_start_session`（+arecord+sender、依 live_initial 定旗號）：
```python
    def _start_session(self, live_initial: bool) -> bool:
        """caller 持 self._lock。連 ws + 起 receiver + arecord + sender（暖機就收音）。
        起 sender 前依 live_initial 定 live 旗號（避免 mute 期誤送真實聲，race-safe）：
        False → sender 進 mute（送等長靜音）；True → 直接送真實音訊。
        缺 key / 連線失敗 → 停用 / 放棄。回傳就緒與否；已有 session 直接 True。"""
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
        live = threading.Event()  # False=mute(送靜音), True=送真實音訊
        if live_initial:
            live.set()
        audio = self._audio_factory()
        receiver = threading.Thread(
            target=self._receive_loop, args=(ws, stop),
            name="SttReceiver", daemon=True)
        sender = threading.Thread(
            target=self._send_loop, args=(ws, audio, stop, live),
            name="SttSender", daemon=True)
        self._session = {"stop": stop, "ws": ws, "receiver": receiver,
                         "audio": audio, "sender": sender, "live": live}
        receiver.start()
        sender.start()
        return True
```

3c. **替換** `prewarm`：
```python
    def prewarm(self) -> None:
        """預熱：連 ws + 起 arecord 暖機錄音，但 sender 進 mute（送靜音、機器人聲不進
        Deepgram）。arecord 提前暖好 → arm 後零開麥裁切。冪等。"""
        with self._lock:
            self._start_session(live_initial=False)
```

3d. **替換** `arm`：
```python
    def arm(self) -> None:
        """解 mute：sender 改送真實顧客音訊（arecord 已於 prewarm 暖好、零啟動裁切）。
        未經 prewarm 直接 arm 則即起即送（向後相容）。冪等。"""
        with self._lock:
            if self._session is None:
                self._start_session(live_initial=True)
            else:
                self._session["live"].set()
```

3e. **刪除** `_keepalive_loop` 整個方法。

3f. **替換** `_send_loop`（加 `live` 參數 + 靜音分支）：
```python
    def _send_loop(self, ws, audio, stop, live) -> None:
        """audio.read → ws.send。mute（live 未 set）期送等長靜音（保連線、不送真實聲）；
        live 後送真實音訊。EOF / stop 即止。"""
        try:
            while not stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                ws.send(chunk if live.is_set() else b"\x00" * len(chunk))
        except Exception:
            pass  # ws 已關（disarm / 斷線）→ 靜默結束；對外回報由 receiver 負責
```

3g. **替換** `disarm`（dict 版、join receiver/sender，去 keepalive）：
```python
    def disarm(self) -> None:
        """冪等收麥：stop → 殺音源 + 關 ws → join receiver/sender。

        join(timeout=1) 讓 session 結束具確定性（測試 / re-arm 安全）；threads 為
        daemon，極端卡住也不擋程式退出（對齊 S6 教訓：不嘗試強解 blocking IO）。
        """
        with self._lock:
            if self._session is None:
                return
            s = self._session
            self._session = None
            s["stop"].set()
            s["audio"].close()
            try:
                s["ws"].close()
            except Exception:
                pass  # 已斷線的 ws close 可能 raise——cleanup 路徑安全吞掉
        for th in (s["receiver"], s["sender"]):
            th.join(timeout=1.0)
```

（`_receive_loop` / `_connect_with_retry` / `_ArecordSource` / `_default_audio_factory`（`-c 1` 降混）/ 模組 `prewarm`/`arm`/`disarm`/`shutdown` **不動**。）

- [ ] **Step 4：跑見 PASS（含既有不破）**
Run：`py -m pytest tests/stt/ -v`
Expected：全 passed。特別確認 `test_sender_streams_audio_chunks`（arm 直呼 → live_initial=True → 送真實、無靜音前綴）、`test_arm_idempotent_single_session`、`test_disarm_closes_audio_and_allows_rearm`、`test_no_key_disables_and_warns_once`、`test_default_audio_factory_command`（仍 `-c 1`）皆綠。

- [ ] **Step 5：全回歸**
Run：`py -m pytest tests/stt/ tests/sales/`
Expected：sales 592 + stt 全綠。

- [ ] **Step 6：commit**
```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "feat(stt): 暖機 arecord 送靜音、arm 即切真實（消開麥裁切；保留 -c 1 降混）"
git branch --contains $(git rev-parse HEAD)   # 自驗落 worktree-stt-warm-arecord
```

---

## 完成檢查（主 agent Iron Law）
- `py -m pytest tests/stt/ tests/sales/` → `N passed`（sales 592 + stt ≈625）。
- `git branch --contains <SHA>` → `worktree-stt-warm-arecord`。
- grep stt.py：`_keepalive` / `keepalive_interval` = 0（v2 殘留清除）;`live.set` / `live_initial` ≥1（v3 機制在）;`"-c", "1"` = 1（降混音源未動）。
- grep stt.py `_extract_channel` / `_CHANNELS` = 0（確認沒誤引入抽軌）。
- `main.py` 無改動（`git diff --stat` 不含 main.py）。
