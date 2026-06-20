# STT 早麥 `STT_EARLY_MIC` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans。Steps 用 checkbox（`- [ ]`）。

**Goal:** `STT_EARLY_MIC=1` 時，提示音播放期間就開 arecord 串流暖 Deepgram（`_capturing=False` 不注入），提示音播完才翻注入閘，讓顧客馬上講的首字不被吞。

**Architecture:** `arm()` 加 `capture` 參數把「開收音層」與「進注入窗」解耦；收音層「未開才開」使早麥的第二次 `arm()` 只翻 `_capturing`、不重開 arecord。`disarm()` 清理閘改判 `_audio` 開否（涵蓋早麥開了卻沒 capture）。`main.py` 以 `_EARLY_MIC` 旗標在 `wait_idle` 前後兩段式 arm。

**Tech Stack:** Python、websockets 同步 client（生產）、pytest + `tests/stt/conftest.py`（`FakeWs`/`FakeAudioSource`/`wait_until`）+ `tests/sales/test_main_read_callbacks.py`（fake tts/stt 注入）。

## Global Constraints
- 產出物（註解/docstring/字串/commit）一律**繁體中文**。
- **不改 vendor**；本案不碰 vendor。
- `git add` 明列檔名，禁 `-A`/`.`。
- **預設關（`STT_EARLY_MIC` 未設 / `capture=True`）= 零行為改變**；既有 arm/disarm 冪等 + prearm 佈線測試不得回歸。

---

### Task 1: `stt.py` — `arm(capture=...)` 解耦 + `disarm` 清理閘修正

**Files:**
- Modify: `myProgram/stt.py`（`arm` ~line 148-175；`disarm` ~line 294-314）
- Test: `tests/stt/test_worker.py`（append 2 測試）

**Interfaces:**
- Produces：`SttWorker.arm(self, capture: bool = True)`；`disarm` 行為（早麥開了未 capture 也收）。
- Consumes（既有）：`self._lock`/`self._audio`/`self._send_stop`/`self._sender`/`self._capturing`/`self._audio_factory`/`self._ensure_connected`/`self._close_connection`/`self._armed_at`/`self._send_loop`。

- [ ] **Step 1: 寫 failing test A（capture=False 串流不注入、capture=True 翻注入）**

append 到 `tests/stt/test_worker.py` 末：
```python
def test_arm_capture_false_streams_without_injecting():
    """arm(capture=False)：開收音層串流（音流出去）但 _capturing=False → speech_final
    不注入；隨後 arm()（capture=True）翻 _capturing → 注入。"""
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02"])
    worker.arm(capture=False)                       # 早麥：串流暖機、不注入
    assert wait_until(lambda: ws.sent == [b"\x01\x02"])   # 音流出去（收音層已開）
    assert not worker.is_armed()                    # _capturing 仍 False
    ws.feed(_results("機器人提示", speech_final=True))    # 早麥窗 → 閘擋住
    time.sleep(0.1)
    assert calls == []
    worker.arm()                                    # capture=True → 翻注入
    assert worker.is_armed()
    ws.feed(_results("顧客紅茶", speech_final=True))
    assert wait_until(lambda: calls == ["顧客紅茶"])
    worker.shutdown()
```

- [ ] **Step 2: 跑 test A 見 FAIL**

Run: `py -m pytest tests/stt/test_worker.py::test_arm_capture_false_streams_without_injecting -v`
Expected: FAIL — `arm()` 尚不接受 `capture` kwarg → `TypeError: arm() got an unexpected keyword argument 'capture'`。

- [ ] **Step 3: 改 `arm` 加 `capture` 參數 + 「未開才開」**

把 `myProgram/stt.py` 的 `arm` 整個方法換成：
```python
    def arm(self, capture: bool = True) -> None:
        """開麥。capture=True（預設）：開收音層（若未開）+ 進注入窗（_capturing=True）——
        既有單呼叫行為完全不變。capture=False：只開收音層串流（音流進 Deepgram 暖機），
        _capturing 仍 False、不注入 —— 供「早麥」於提示音播放期間先開麥暖串流；隨後
        arm()（capture=True）翻 _capturing 開始注入，**不重開 arecord**（復用早麥已開的收音層）。
        建線在鎖外（不持 _lock，避免凍結 disarm/shutdown）。"""
        with self._lock:
            if self._disabled or self._capturing:
                return
            if not self._api_key:
                print("[語音辨識] ⚠️ 未設定 DEEPGRAM_API_KEY，STT 停用（鍵盤輸入照常）")
                self._disabled = True
                return
        # 連線在鎖外（_ensure_connected 內自持 _connect_lock；失敗已印原因）
        if not self._ensure_connected():
            return  # 本輪走鍵盤
        with self._lock:
            if self._capturing:
                return  # 防禦：等鎖期間已進注入窗
            if self._audio is None:
                # 收音層未開才開（首次 arm，或早麥 arm(capture=False)）
                audio = self._audio_factory()
                send_stop = threading.Event()
                sender = threading.Thread(
                    target=self._send_loop, args=(self._ws, audio, send_stop),
                    name="SttSender", daemon=True)
                self._audio = audio
                self._send_stop = send_stop
                self._sender = sender
                self._armed_at = time.monotonic()
                sender.start()
            if capture:
                self._capturing = True
```

- [ ] **Step 4: 跑 test A 見 PASS**

Run: `py -m pytest tests/stt/test_worker.py::test_arm_capture_false_streams_without_injecting -v`
Expected: PASS。

- [ ] **Step 5: 寫 failing test B（capture=True 後不重開 arecord）**

append 到 `tests/stt/test_worker.py` 末：
```python
def test_arm_capture_true_after_false_does_not_reopen_audio():
    """早麥 arm(capture=False) 已開 arecord；隨後 arm() 不重開（audio_factory 仍 1 次）、
    只翻 _capturing。"""
    audios = []
    def audio_factory():
        a = FakeAudioSource()
        audios.append(a)
        return a
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: FakeWs(), audio_factory=audio_factory)
    worker.arm(capture=False)
    assert wait_until(lambda: len(audios) == 1)
    worker.arm()                                    # 不重開 arecord
    assert len(audios) == 1 and worker.is_armed()
    worker.shutdown()
```

- [ ] **Step 6: 跑 test B 見 PASS**

Run: `py -m pytest tests/stt/test_worker.py::test_arm_capture_true_after_false_does_not_reopen_audio -v`
Expected: PASS（`arm` 已有「未開才開」邏輯）。

- [ ] **Step 7: 改 `disarm` 清理閘 `if capturing` → `if self._audio is not None`**

把 `myProgram/stt.py` 的 `disarm` 整個方法換成：
```python
    def disarm(self) -> None:
        """冪等收麥：收音層開著就收（停 sender + arecord）→ 無條件收線。
        清理閘判 `_audio` 是否開著（非 `_capturing`）—— 早麥可能開了 arecord 卻因 q/例外
        未進注入窗（_capturing 從未 True），仍須收掉收音層、不洩漏。
        不送 Finalize（靠 endpointing 自然 finalize）。"""
        with self._lock:
            self._capturing = False
            audio = self._audio
            send_stop = self._send_stop
            sender = self._sender
            self._audio = None
            self._send_stop = None
            self._sender = None
        if audio is not None:
            send_stop.set()
            audio.close()
            sender.join(timeout=1.0)
            # 不送 Finalize：逐輪 mid-stream Finalize 會破壞 Deepgram 對後續 utterance 的
            # finalization（症狀：speech_final 空白、辨識整輪漏掉；Pi 2026-06-19 診斷鐵證）。
        self._close_connection()  # 無條件收線（含 prearm 已連但未 arm）
```

- [ ] **Step 8: 跑全 stt suite 見全綠**

Run: `py -m pytest tests/stt/ -v`
Expected: 全 PASS（既有 + 2 新增）；既有 `test_disarm_closes_audio_and_allows_rearm` / `test_arm_idempotent_single_session` / `test_disarm_skips_finalize_when_sender_stuck` 仍綠（capture=True 預設＝舊行為，`_audio is not None` 與舊 `capturing` 等價）。

- [ ] **Step 9: Commit（Task 1）**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -F - <<'EOF'
feat(stt): decouple arm capture from audio-open for early-mic

arm(capture=False) opens the capture layer (audio streams to Deepgram for
warmup) without entering the injection window (_capturing stays False); a
later arm(capture=True) flips _capturing and reuses the already-open arecord
(no re-open). disarm() now tears down the capture layer when _audio is open
rather than gating on _capturing, so an early-mic open that never captured
(q/exception before the second arm) is not leaked. capture=True default is
unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012DTTB5ygEsQjppQCyFznZC
EOF
```

---

### Task 2: `main.py` — `_EARLY_MIC` 旗標 + `read_customer_input` 兩段式 arm

**Files:**
- Modify: `myProgram/main.py`（常數 ~line 33 區；`read_customer_input` body ~line 148-171）
- Test: `tests/sales/test_main_read_callbacks.py`（更新 `_make_fake_stt_module` + append 2 測試）

**Interfaces:**
- Consumes：Task 1 的 `stt.arm(capture=False)`。
- Produces：`myProgram.main._EARLY_MIC: bool`（測試以 `monkeypatch.setattr("myProgram.main._EARLY_MIC", ...)` 撥動）。

- [ ] **Step 1: 更新 `_make_fake_stt_module`（arm 接 capture，向後相容）**

把 `tests/sales/test_main_read_callbacks.py` 的 `_make_fake_stt_module` 換成：
```python
def _make_fake_stt_module(call_order):
    fake = types.ModuleType("myProgram.stt")
    fake.prearm = lambda: call_order.append("prearm")
    fake.arm = lambda capture=True: call_order.append("arm" if capture else "arm_early")
    fake.disarm = lambda: call_order.append("disarm")
    return fake
```
（既有測試呼叫 `stt.arm()` → capture=True → 仍 append `"arm"`，向後相容。）

- [ ] **Step 2: 跑既有 main read 測試見仍 PASS（回歸守衛）**

Run: `py -m pytest tests/sales/test_main_read_callbacks.py -v`
Expected: 既有全 PASS（fake 改 arm 簽名不破壞既有 `stt.arm()` 無參呼叫）。

- [ ] **Step 3: 寫 failing test（早麥序列）**

append 到 `tests/sales/test_main_read_callbacks.py` 末：
```python
def test_early_mic_arms_capture_false_before_wait_idle(monkeypatch):
    """STT_EARLY_MIC=1：arm(capture=False) 在 wait_idle 前（提示音播放期間開麥暖機），
    arm(capture=True) 在 wait_idle 後（翻注入閘）。"""
    monkeypatch.setattr("myProgram.main._EARLY_MIC", True)
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)
    assert call_order.index("arm_early") < call_order.index("wait_idle") < call_order.index("arm")
    assert call_order.index("arm") < call_order.index("read")
    assert "disarm" in call_order
```

- [ ] **Step 4: 跑見 FAIL**

Run: `py -m pytest tests/sales/test_main_read_callbacks.py::test_early_mic_arms_capture_false_before_wait_idle -v`
Expected: FAIL — `myProgram.main` 無 `_EARLY_MIC`（`monkeypatch.setattr` AttributeError），或無 `arm_early`（未早麥）。

- [ ] **Step 5: 加 `_EARLY_MIC` 常數**

在 `myProgram/main.py` 的 `_MIC_OPEN_DELAY_SEC = ...` 下方加：
```python
# 早麥（env 旗標）：STT_EARLY_MIC=1 時，read_customer_input 在提示音播放期間（wait_idle
# 前）就 arm(capture=False) 開 arecord 串流暖機，wait_idle 後才 arm() 翻注入閘。提示音的
# 辨識被 _capturing 閘擋、不進訂單。預設 0 = 不早麥、不改行為。
_EARLY_MIC = bool(int(os.environ.get("STT_EARLY_MIC", "0")))
```

- [ ] **Step 6: 重排 `read_customer_input`（早麥 + try 涵蓋 disarm）**

把 `read_customer_input` 的 body（from `from myProgram import stt` 到 `stt.disarm()` 的 finally，即 line 150-171）換成：
```python
        from myProgram import stt
        stt.prearm()   # 非阻塞預連線：首輪 540ms 握手藏進下面 wait_idle 的提示音播放
        from myProgram import tts
        from myProgram import input_reader

        # STT Phase 1：提示音播完才翻注入閘；STT_EARLY_MIC=1 時提前在播放期間就開麥串流
        # 暖機（arm(capture=False)，提示音辨識被 _capturing 閘擋、不進訂單）。
        # try/finally 保證四條路徑（早麥開了 / 拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        try:
            if _EARLY_MIC:
                stt.arm(capture=False)   # 早麥：提示音播放期間開 arecord 串流暖機（不注入）
            tts.wait_idle()
            if _MIC_OPEN_DELAY_SEC > 0:
                time.sleep(_MIC_OPEN_DELAY_SEC)
            stt.arm()                    # capture=True：翻注入閘（早麥則復用已開 arecord）
            if timeout is None or timeout <= 0:
                raw = input_reader.read(timeout)
            else:
                raw = _tick_countdown(timeout, "timeout", input_reader.read)
        finally:
            stt.disarm()
```
（非早麥路徑呼叫序 prearm → wait_idle → arm → disarm 與行為不變。）

- [ ] **Step 7: 跑早麥 test 見 PASS**

Run: `py -m pytest tests/sales/test_main_read_callbacks.py::test_early_mic_arms_capture_false_before_wait_idle -v`
Expected: PASS。

- [ ] **Step 8: 寫 regression test（預設無早麥）**

append 到 `tests/sales/test_main_read_callbacks.py` 末：
```python
def test_default_no_early_mic_single_arm(monkeypatch):
    """預設（_EARLY_MIC=False）：無 arm_early，wait_idle 後才 arm（不改行為）。"""
    monkeypatch.setattr("myProgram.main._EARLY_MIC", False)
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)
    assert "arm_early" not in call_order
    assert call_order.index("wait_idle") < call_order.index("arm") < call_order.index("read")
```

- [ ] **Step 9: 跑全 suite 見全綠**

Run: `py -m pytest tests/stt/ tests/sales/ -q`
Expected: 全 PASS（Task 1 + Task 2 + 4 新增）；既有 `test_read_customer_input_calls_prearm_before_wait_idle` 等不回歸。

- [ ] **Step 10: Commit（Task 2）**

```bash
git add myProgram/main.py tests/sales/test_main_read_callbacks.py
git commit -F - <<'EOF'
feat(stt): wire STT_EARLY_MIC two-phase arm in read_customer_input

When STT_EARLY_MIC=1, read_customer_input arm(capture=False) before wait_idle
(open mic + stream during prompt playback for real-audio warmup) then arm()
after wait_idle to flip the injection gate. The prompt's own transcripts are
blocked by _capturing so they never enter the order. wait_idle/arm move inside
a try whose finally disarms, covering the early-opened mic on every exit path.
Default off = unchanged behavior.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012DTTB5ygEsQjppQCyFznZC
EOF
```

---

## Self-Review（writing-plans 自掃）

1. **Spec coverage**：§2 `arm(capture)` 規約 → Task1 Step3；「未開才開」→ Step3 `if self._audio is None`；disarm 修正 → Step7；§3 main 常數 + 重排 → Task2 Step5/6；注入閘（既有不改）→ 靠 `_receive_loop` 現狀（測 A 驗）；§6 測試 → 兩 Task 的 pytest 步。無 gap。
2. **Placeholder scan**：無 TBD/TODO；每碼步給完整方法/測試碼。
3. **Type consistency**：`arm(self, capture: bool = True)`、`_EARLY_MIC: bool`、`_audio`/`_send_stop`/`_sender`（既有欄位名）、`audios`/`calls`/`call_order`（test）全程一致；`stt_mod`（test_worker.py line 8 既有）；`_make_fake_stt_module` 改後 `arm` 簽名 `capture=True` 與既有無參呼叫相容。
