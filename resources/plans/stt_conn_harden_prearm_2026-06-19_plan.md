# STT 持久連線 hardening + prearm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉持久連線的 3 個併發 freeze-risk（壞訊息殺連線 / 建線持鎖凍結 / disarm Finalize 掛死），並加 prearm 首連線把 turn-1 的 540ms 握手藏進提示音播放。

**Architecture:** 全在 `stt.py` `SttWorker` + `main.py` `read_customer_input`。建線移出 `_lock`、以 `_connect_lock` 序列化（prearm 背景 vs arm 主線程）；`_receive_loop` 雙層 try 讓壞訊息不殺連線；disarm 用 `sender.is_alive()` 守 Finalize。

**Tech Stack:** Python 3.11（Pi runtime）；Windows pytest（`py -3.14 -m pytest`）；無新依賴。

## Global Constraints

- **繁體中文**：新增註解 / 字串 / commit 繁中。
- **對話層零感知**：`arm`/`disarm`/`shutdown` signature 不變；`prearm` 為純加速新增（缺 key / 純鍵盤模式 no-op）。
- **行為不變**：辨識、注入、連線復用/重連/401/失敗走鍵盤 全保留。
- **不用 `git add -A`**；明列檔名。
- **worktree**：全程在 `worktree-stt-harden-prearm`；上一 commit 是 spec/plan doc（不要改）；每 commit 後 `git branch --contains HEAD` 驗。
- **不碰** opener-split / prewarm / local 模型 / endpointing / drain / vendor。

---

## Task 1: A1 — `_receive_loop` 雙層 try（壞訊息不殺連線）

**Files:** Modify `myProgram/stt.py`（`_receive_loop` 203-228）；Test `tests/stt/test_worker.py`

- [ ] **Step 1: 寫 failing 測試**

`tests/stt/test_worker.py` 末尾加（檔頂已有 `_results` helper / `FakeWs` / `wait_until`）：
```python
def test_malformed_message_does_not_kill_connection():
    """單則壞訊息（非 JSON）→ receiver 略過該則、連線存活；隨後正常 speech_final 仍注入。"""
    calls = []
    ws = FakeWs()
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    ws.feed("這不是 JSON{{{")                          # 壞訊息：json.loads 會炸
    ws.feed(_results("正確", speech_final=True))        # 正常訊息
    assert wait_until(lambda: calls == ["正確"])        # 壞訊息被略過、loop 存活、正常訊息照注入
    assert worker._ws is not None                       # 連線未被壞訊息殺掉
    worker.shutdown()
```

- [ ] **Step 2: 跑見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py::test_malformed_message_does_not_kill_connection -q`
Expected: FAIL（現狀 json.loads 炸 → 外層 except → finally 標 `_ws=None` → `worker._ws is not None` 斷言失敗、且 "正確" 未注入）。

- [ ] **Step 3: 實作雙層 try**

把 `_receive_loop`（現 203-228）改為：
```python
    def _receive_loop(self, ws, conn_stop) -> None:
        """常駐：ws.recv → JSON → speech_final（**僅 _capturing 才注入**）。
        雙層 try：外層只包 ws.recv（連線層——recv 失敗=連線死→退出重連）；內層包單訊息
        處理（json/格式異常→印警示後 continue，**持久連線存活**）。退出時若非 shutdown
        觸發 → 印警示並標記 _ws 死亡（下次 arm 重連）。"""
        try:
            while not conn_stop.is_set():
                msg = ws.recv()
                try:
                    if isinstance(msg, bytes):
                        continue  # Deepgram Results 皆 text frame；防禦略過
                    data = json.loads(msg)
                    if data.get("type") != "Results" or not data.get("speech_final"):
                        continue
                    if not self._capturing:
                        continue  # 閘門：收音窗外（上一輪殘響 / Finalize 回覆）丟棄
                    alts = data.get("channel", {}).get("alternatives", [])
                    text = _normalize_transcript(alts[0].get("transcript", "")) if alts else ""
                    if text:
                        print(f"[語音辨識] {text}")
                        _timing(f"開麥後 {time.monotonic() - self._armed_at:.2f}s 出辨識結果")
                        self._sink(text)
                except Exception as e:
                    # 單訊息處理失敗（格式不合 / json 壞）→ 略過該則，持久連線存活
                    print(f"[語音辨識] ⚠️ 跳過異常訊息（{type(e).__name__}）")
        except Exception as e:
            if not conn_stop.is_set():
                print(f"[語音辨識] ⚠️ 串流中斷（{type(e).__name__}），下次開麥重連")
        finally:
            with self._lock:
                if self._ws is ws:
                    self._ws = None  # 標記死亡 → 下次 arm 重連
```

- [ ] **Step 4: 跑見 PASS**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS（新測 + 既有續綠）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "fix(stt): _receive_loop 雙層 try — 壞訊息略過不殺持久連線（反思 receive-loop-outer-try）"
git branch --contains HEAD
```

---

## Task 2: A2 — 建線移出 `_lock` + `_connect_lock` + arm 重構

**Files:** Modify `myProgram/stt.py`（`__init__` / `_ensure_connected` 121-144 / `arm` 146-168）；Test `tests/stt/test_worker.py`（既有連線測試為回歸網）

**Interfaces:** Produces `_connect_lock`；`_ensure_connected` 鎖外建線；`arm` 建線不持 `_lock`。

- [ ] **Step 1: 加 `_connect_lock` 欄位**

`__init__`（現 102 `self._send_lock = ...` 之後）加：
```python
        self._connect_lock = threading.Lock()  # 序列化建線（prearm 背景 vs arm 主線程），不與 _lock 同時持有
```

- [ ] **Step 2: 重構 `_ensure_connected`（鎖外建線）**

把 `_ensure_connected`（現 121-144）改為：
```python
    def _ensure_connected(self) -> bool:
        """確保持久連線存在：已連則復用（True）。未連則**鎖外**建線（阻塞網路 IO 不持
        _lock，避免凍結 disarm/shutdown）+ 鎖內寫狀態 + 起常駐 receiver/keepalive（含
        「開麥連線」計時）。連線失敗回 False。_connect_lock 序列化 prearm/arm 並發建線。"""
        with self._lock:
            if self._ws is not None:
                return True
        with self._connect_lock:
            with self._lock:
                if self._ws is not None:
                    return True  # 等鎖期間 prearm/另一 arm 已建好 → 復用
            # 鎖外建線（_lock 已釋放）——阻塞 IO 不凍結 disarm/shutdown
            _connect_t0 = time.monotonic()
            ws = self._connect_with_retry()
            if ws is None:
                return False
            _timing(f"開麥連線 {(time.monotonic() - _connect_t0) * 1000:.0f}ms")
            conn_stop = threading.Event()
            receiver = threading.Thread(
                target=self._receive_loop, args=(ws, conn_stop),
                name="SttReceiver", daemon=True)
            keepalive = threading.Thread(
                target=self._keepalive_loop, args=(ws, conn_stop),
                name="SttKeepAlive", daemon=True)
            with self._lock:
                self._ws = ws
                self._conn_stop = conn_stop
                self._receiver = receiver
                self._keepalive = keepalive
            receiver.start()
            keepalive.start()
            return True
```

- [ ] **Step 3: 重構 `arm`（建線移出 `_lock`）**

把 `arm`（現 146-168）改為：
```python
    def arm(self) -> None:
        """冪等開麥：已 capturing / 已停用 no-op；缺 key 印一次警告後停用。
        建線在鎖外（不持 _lock，避免凍結 disarm/shutdown）；首輪建線、之後只 spawn
        arecord + sender（若 prearm 已建線則直接復用）。"""
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
                return  # 防禦：理論上單 caller 不發生
            audio = self._audio_factory()
            send_stop = threading.Event()
            sender = threading.Thread(
                target=self._send_loop, args=(self._ws, audio, send_stop),
                name="SttSender", daemon=True)
            self._audio = audio
            self._send_stop = send_stop
            self._sender = sender
            self._armed_at = time.monotonic()
            self._capturing = True
            sender.start()
```

- [ ] **Step 4: 跑既有連線測試（回歸網）見 PASS**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS（`test_connection_reused_across_arm_disarm` / `test_dead_connection_reconnects_on_next_arm` / `test_connect_retry_once_then_success` / `test_connect_fail_twice_gives_up_but_not_disabled` / `test_401_disables_permanently` / `test_speech_final_*` / 計時測 全綠——arm 重構後行為等價）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/stt.py
git commit -m "fix(stt): 建線移出 _lock + _connect_lock 序列化（反思 arm-lock-blocking-io；為 prearm 鋪路）"
git branch --contains HEAD
```

---

## Task 3: A3 — disarm join 逾時跳過 Finalize

**Files:** Modify `myProgram/stt.py`（`disarm` 256-264）；Test `tests/stt/test_worker.py`

- [ ] **Step 1: 寫 failing 測試**

`tests/stt/test_worker.py` 末尾加：
```python
def test_disarm_skips_finalize_when_sender_stuck():
    """sender 卡死（join 逾時仍 alive）→ disarm 不送 Finalize、不掛死、~1s 內返回。"""
    release = threading.Event()

    class _BlockingAudio:
        def __init__(self):
            self.closed = False
        def read(self, n):
            release.wait(timeout=5.0)   # 卡住模擬 sender 不收（真實情境為卡在 ws.send）
            return b""
        def close(self):
            self.closed = True

    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=_BlockingAudio)
    worker.arm()
    assert wait_until(lambda: worker._capturing)
    start = time.monotonic()
    worker.disarm()                                  # sender 卡在 read → join(1.0) 逾時
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"disarm 不應掛死，實際 {elapsed:.2f}s"
    assert not _control_sent(ws, "Finalize"), "sender 卡死時不應送 Finalize"
    release.set()                                    # cleanup：放行 sender
    worker.shutdown()
```
（`_control_sent` helper 已於既有 Task 3 控制訊息測定義；`threading` 已 import。）

- [ ] **Step 2: 跑見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py::test_disarm_skips_finalize_when_sender_stuck -q`
Expected: FAIL（現狀 join 逾時後仍送 Finalize → `_control_sent(ws, "Finalize")` 為 True → 斷言失敗）。

- [ ] **Step 3: 實作守衛**

把 `disarm` 結尾（現 256-264）：
```python
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        if ws is not None:
            try:
                with self._send_lock:
                    ws.send(_FINALIZE_MSG)  # 沖 pending 音訊，乾淨收尾
            except Exception:
                pass
```
改為：
```python
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        # 僅 sender 已收（未卡在 ws.send 持 _send_lock）才送 Finalize；join 逾時仍 alive
        # → 跳過，避免搶 _send_lock 掛死 disarm（連線此時多半已異常，送不送意義不大）。
        if ws is not None and not sender.is_alive():
            try:
                with self._send_lock:
                    ws.send(_FINALIZE_MSG)  # 沖 pending 音訊，乾淨收尾
            except Exception:
                pass
```

- [ ] **Step 4: 跑見 PASS**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS（新測 + `test_finalize_sent_on_disarm`（正常 sender 已收→仍送）續綠）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "fix(stt): disarm join 逾時跳過 Finalize 防掛死（反思 disarm-finalize-blocked）"
git branch --contains HEAD
```

---

## Task 4: B — prearm 首連線（stt.py method + module + main.py wire）

**Files:** Modify `myProgram/stt.py`（新增 `prearm` method + module `prearm()`）、`myProgram/main.py`（`read_customer_input`）；Test `tests/stt/test_worker.py`、`tests/sales/test_main_read_callbacks.py`

- [ ] **Step 1: 寫 failing 測試（stt prearm）**

`tests/stt/test_worker.py` 末尾加：
```python
def test_prearm_connects_in_background():
    """未連時 prearm 背景建線；隨後 arm 復用同一連線（ws_factory 仍 1 次）。"""
    factory_calls = []
    ws = FakeWs()
    def factory(key):
        factory_calls.append(key)
        return ws
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.prearm()
    assert wait_until(lambda: worker._ws is not None)   # 背景已建線
    worker.arm()                                        # 復用
    worker.disarm()
    assert factory_calls == ["test-key"]                # 只連一次
    worker.shutdown()


def test_prearm_noop_when_already_connected():
    factory_calls = []
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: factory_calls.append(key) or ws,
                       audio_factory=FakeAudioSource)
    worker.arm()                                        # 已連
    worker.prearm()                                     # no-op
    worker.disarm()
    assert factory_calls == ["test-key"]
    worker.shutdown()


def test_prearm_noop_without_key():
    factory_calls = []
    worker = SttWorker(sink=lambda t: None, api_key=None,
                       ws_factory=lambda key: factory_calls.append(key),
                       audio_factory=FakeAudioSource)
    worker.prearm()
    time.sleep(0.1)
    assert factory_calls == []                          # 缺 key → 不建線
```

- [ ] **Step 2: 跑見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -k prearm -q`
Expected: FAIL（`AttributeError: 'SttWorker' object has no attribute 'prearm'`）。

- [ ] **Step 3: 實作 `prearm`（stt.py）**

在 `arm` 之後加 method：
```python
    def prearm(self) -> None:
        """非阻塞預連線：起 daemon thread 跑 _ensure_connected，讓首輪 540ms 握手藏進
        提示音播放。快查任一成立即返（不起 thread）：已停用 / 收音中 / 缺 key / 已連。
        _connect_lock 保證與 arm 不重複建線（後到者復用）。"""
        if self._disabled or self._capturing or not self._api_key or self._ws is not None:
            return
        threading.Thread(target=self._ensure_connected, name="SttPrearm", daemon=True).start()
```
並在 module-level `def arm():` 之後加：
```python
def prearm() -> None:
    """對外 API：非阻塞預連線（read_customer_input 於 wait_idle 前呼叫，藏首輪握手）。"""
    _get_worker().prearm()
```

- [ ] **Step 4: 跑見 PASS（stt prearm）**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS。

- [ ] **Step 5: 寫 failing 測試（main wire）**

`tests/sales/test_main_read_callbacks.py` 加（檔頂已 `import sys`/`types`/`myProgram`）：
```python
def _make_fake_stt_module(call_order):
    fake = types.ModuleType("myProgram.stt")
    fake.prearm = lambda: call_order.append("prearm")
    fake.arm = lambda: call_order.append("arm")
    fake.disarm = lambda: call_order.append("disarm")
    return fake


def _install_fake_stt(monkeypatch, fake):
    monkeypatch.setitem(sys.modules, "myProgram.stt", fake)
    monkeypatch.setattr(myProgram, "stt", fake, raising=False)


def test_read_customer_input_calls_prearm_before_wait_idle(monkeypatch):
    """prearm 必須在 wait_idle 之前 call（才能 overlap 提示音播放藏首輪握手）。"""
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)
    assert call_order.index("prearm") < call_order.index("wait_idle") < call_order.index("read")
    assert "arm" in call_order and "disarm" in call_order
```

- [ ] **Step 6: 跑見 FAIL**

Run: `py -3.14 -m pytest tests/sales/test_main_read_callbacks.py::test_read_customer_input_calls_prearm_before_wait_idle -q`
Expected: FAIL（現狀 read_customer_input 未呼叫 prearm → `call_order.index("prearm")` ValueError）。

- [ ] **Step 7: 實作 main.py wire**

`myProgram/main.py` `read_customer_input` 內，把現有：
```python
        from myProgram import tts
        tts.wait_idle()
```
改為（import stt 上移 + prearm 前置；原本 `arm()` 之前的 `from myProgram import stt` 移除避免重複）：
```python
        from myProgram import stt
        stt.prearm()   # 非阻塞預連線：首輪 540ms 握手藏進下面 wait_idle 的提示音播放
        from myProgram import tts
        tts.wait_idle()
```
並把原本 `stt.arm()` 之前的 `from myProgram import stt`（現 ~153 行）那一行刪掉（已於上方 import）。`stt.arm()` / `stt.disarm()` 呼叫不動。

- [ ] **Step 8: 跑見 PASS（main wire + 全 stt/sales）**

Run: `py -3.14 -m pytest tests/sales/test_main_read_callbacks.py tests/stt/ -q`
Expected: PASS（既有 `test_read_customer_input_calls_wait_idle_before_input_read` 順序仍 wait_idle→read，新 prearm 測通過）。

- [ ] **Step 9: Commit**

```bash
git add myProgram/stt.py myProgram/main.py tests/stt/test_worker.py tests/sales/test_main_read_callbacks.py
git commit -m "feat(stt): prearm 首連線 — wait_idle 前背景建線藏 turn-1 540ms 握手"
git branch --contains HEAD
```

---

## 收尾驗證（主 agent）

- **Iron Law**：`py -3.14 -m pytest tests/ -q` 全綠（baseline 666 + 新增 ~7 test）。
- **三段 reviewer**：spec-reviewer → code-quality-reviewer（併發重構，重點審 `_connect_lock`/`_lock` 不交叉死鎖、prearm/arm 並發建線復用、雙層 try、disarm is_alive 守衛）。
- **docs**：更新 `proposals.md` 3 條 pending → adopted + 落實 SHA；pineedtodo 加 prearm/壞訊息/卡死 Pi 驗證點；roadmap 註記。
- **worktree closeout**：merge --ff-only → push → 清。

---

## Self-Review

**1. Spec coverage：** A1→Task 1 ✓；A2→Task 2 ✓；A3→Task 3 ✓；B（prearm + main wire）→Task 4 ✓；3 反思各對應一 Task ✓；行為不變式→各 Task 既有測試回歸網 + Global Constraints ✓。
**2. Placeholder scan：** 無 TBD；prod 與 test code 完整（含改前/改後）。
**3. Type consistency：** `_connect_lock`（Lock）、`_ensure_connected()->bool`、`prearm()->None`（method + module）、`_BlockingAudio`（read/close）、`_control_sent(ws,name)`（既有）、`_make_fake_stt_module`/`_install_fake_stt`（鏡像既有 tts 版）全程一致。
