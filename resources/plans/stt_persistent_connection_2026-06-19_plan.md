# STT 整場共用一條 Deepgram 連線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `SttWorker` 從「每輪重連 Deepgram（580ms）」改成「整場共用一條持久連線 + KeepAlive」，第 2 輪起開麥只剩 arecord 冷啟動（~140ms）。

**Architecture:** 連線層（ws + receiver + keepalive thread）整場常駐、lazy 建線、死則下次 arm 重連；收音層（arecord + sender）每輪 arm/disarm。receiver 以 `_capturing` 閘門只在收音窗注入；所有 ws.send 經 `_send_lock` 序列化。

**Tech Stack:** Python 3.11（Pi runtime）；Windows pytest（`py -3.14 -m pytest tests/`）；websockets 同步 client（Pi-only，測試注入 FakeWs）；無新依賴。

## Global Constraints

- **繁體中文**：所有新增註解 / 字串 / commit message 繁中。
- **對話層零感知**：`arm()` / `disarm()` / `shutdown()` 對外 signature 不變 → `myProgram/main.py` **不動**。
- **行為不變**：每輪注入的顧客 utterance 與現狀相同（每輪只取第一個 speech_final）；缺 key / 連線失敗 → 停用走純鍵盤。
- **KeepAlive**：`{"type":"KeepAlive"}`，**text frame**，每 5s（< Deepgram 10s idle timeout）；**僅 `_capturing=False` 時送**。
- **併發**：所有 `ws.send` 經 `_send_lock`；`_ws` 死亡標記與狀態切換經 `_lock`。
- **不用 `git add -A` / `git add .`**：每 commit 明列檔名。
- **worktree**：全程在 `worktree-stt-persistent-conn` 內；上一 commit 是 spec doc（不要改）；每 commit 後 `git branch --contains HEAD` 驗落 `worktree-*`。
- **不碰** vendor/、drain、endpointing、既有辨識行為；不做 prearm / per-conversation（spec Out of scope）。

---

## Task 1: 擴充 FakeWs 測試 harness（Queue 化 + feed + control 捕捉）

**Files:**
- Modify: `tests/stt/conftest.py`（`FakeWs`）

**Interfaces:**
- Produces: `FakeWs(messages=())` recv() 阻塞至有訊息或 close()；`FakeWs.feed(message)` 動態加 server 訊息；`FakeWs.sent` 收所有 send（bytes 音框 + str control）；`close()` 令 recv() 拋出（模擬斷線 / 收線）。

- [ ] **Step 1: 改寫 FakeWs 為 Queue-based + feed**

把 `tests/stt/conftest.py` 的 `FakeWs` 改為（保留 `FakeWs(messages)` 建構相容、新增 `feed`）：
```python
import queue
# （頂部既有 import threading, time 保留；新增 import queue）


class FakeWs:
    """Queue 化：recv() 阻塞至有訊息或 close()；feed() 動態餵 server 訊息；
    sent 收所有 send（bytes 音框 + str control 如 KeepAlive/Finalize/CloseStream）。"""

    _SENTINEL = object()

    def __init__(self, messages=()):
        self._q = queue.Queue()
        for m in messages:
            self._q.put(m)
        self._closed = threading.Event()
        self.sent = []

    def send(self, data) -> None:
        if self._closed.is_set():
            raise RuntimeError("ws closed")
        self.sent.append(data)

    def feed(self, message) -> None:
        """動態加一筆 server 訊息（多輪 / 收音窗外測試用）。"""
        self._q.put(message)

    def recv(self):
        item = self._q.get()
        if item is FakeWs._SENTINEL:
            raise RuntimeError("ws closed")
        return item

    def close(self) -> None:
        self._closed.set()
        self._q.put(FakeWs._SENTINEL)
```

- [ ] **Step 2: 跑既有 stt 測試確認零回歸**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS（既有 SttWorker 不變，新 FakeWs 行為對既有測試等價——recv 依序回訊息、close 令 recv 拋出）。

- [ ] **Step 3: Commit**

```bash
git add tests/stt/conftest.py
git commit -m "test(stt): FakeWs 改 Queue-based + feed（持久連線多輪測試鋪路）"
git branch --contains HEAD
```

---

## Task 2: SttWorker 持久連線重構（連線層常駐 + 收音層每輪 + 閘門 + 重連）

**Files:**
- Modify: `myProgram/stt.py`（`SttWorker` 全面重構）
- Test: `tests/stt/test_worker.py`

**Interfaces:**
- Consumes（既有）：`_connect_with_retry`、`_timing`、`_normalize_transcript`、`_default_audio_factory`、`_default_ws_factory`、`CHUNK_BYTES`、`time`、`json`。
- Produces：`SttWorker._ensure_connected() -> bool`（lazy 建線 + 復用 + 起常駐 receiver；持 `_lock`）；`_ws`（持久連線或 None）；`_capturing` bool；`_send_lock`；`is_armed()` 回 `_capturing`。

- [ ] **Step 1: 寫 failing 測試（復用 / 閘門 / 重連）**

在 `tests/stt/test_worker.py` 末尾加（檔頂已 `from tests.stt.conftest import FakeAudioSource, FakeWs, wait_until` + `from myProgram.stt import SttWorker`；另確保有 `import time`、`import myProgram.stt as stt_mod`、本檔既有 `_results` helper）：
```python
def test_connection_reused_across_arm_disarm():
    """連兩輪 arm/disarm → ws_factory 只被呼叫 1 次（整場共用一條連線）。"""
    factory_calls = []
    ws = FakeWs()
    def factory(key):
        factory_calls.append(key)
        return ws
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.arm(); worker.disarm()
    worker.arm(); worker.disarm()
    assert factory_calls == ["test-key"]
    worker.shutdown()


def test_speech_final_not_injected_when_not_capturing():
    """收音窗外（disarm 後）到達的 speech_final 不注入；再 arm 才注入。"""
    calls = []
    ws = FakeWs()
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()                                   # capturing=False，連線/receiver 仍在
    ws.feed(_results("殘響", speech_final=True))       # 非收音窗
    time.sleep(0.1)                                   # 給 receiver 處理
    assert calls == []                                # 閘門擋住
    worker.arm()                                      # 收音窗
    ws.feed(_results("正確", speech_final=True))
    assert wait_until(lambda: calls == ["正確"])
    worker.shutdown()


def test_dead_connection_reconnects_on_next_arm():
    """連線死亡（ws.close）→ 標記 _ws None → 下次 arm 重連（ws_factory 再呼叫）。"""
    wss = []
    def factory(key):
        w = FakeWs()
        wss.append(w)
        return w
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.arm()
    assert wait_until(lambda: len(wss) == 1)
    wss[0].close()                                    # 模擬斷線 → receiver recv 拋出
    assert wait_until(lambda: worker._ws is None)     # 標記死亡
    worker.disarm()
    worker.arm()                                      # 重連
    assert wait_until(lambda: len(wss) == 2)
    worker.shutdown()
```

- [ ] **Step 2: 跑測試見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -q`
Expected: FAIL（`_ensure_connected` / `_ws` / `_capturing` 尚未存在；`test_connection_reused...` 會因每輪重連而 `factory_calls` 長度 2）。

- [ ] **Step 3: 重寫 SttWorker（連線層常駐 + 收音層每輪）**

把 `myProgram/stt.py` 整個 `SttWorker` class（`class SttWorker:` 到 `shutdown` 結束、`_is_auth_error` 之前）替換為：
```python
class SttWorker:
    """Deepgram 串流 worker：整場共用一條持久連線（連線層常駐），每輪只開關 arecord（收音層）。

    Thread model：
        - 連線層（整場常駐）：_ws（持久連線）+ SttReceiver（ws.recv→閘門→sink）
          + SttKeepAlive（idle 時送 KeepAlive 撐住）。lazy 於首次 arm 建線，死則下次
          arm 重連，shutdown 收掉。
        - 收音層（每輪 arm/disarm）：arecord（_audio）+ SttSender（audio.read→ws.send）。
        - _capturing 閘門：receiver 只在收音窗注入，擋上一輪殘響 / Finalize 回覆漏入下一輪。
        - _send_lock 序列化所有 ws.send（音框 / keepalive / finalize / close）——websockets
          sync client 並發 send 非 thread-safe。

    注入 seams（Windows pytest 全 fake）：sink / audio_factory / ws_factory（同前）。
    """

    def __init__(self, sink, api_key=None, audio_factory=None, ws_factory=None):
        self._sink = sink
        self._api_key = api_key
        self._audio_factory = audio_factory or _default_audio_factory
        self._ws_factory = ws_factory or _default_ws_factory
        self._lock = threading.Lock()        # 保護連線層狀態 + capturing 切換
        self._send_lock = threading.Lock()   # 序列化所有 ws.send
        # 連線層（整場常駐）
        self._ws = None                      # 持久連線，或 None（未連 / 已死）
        self._conn_stop = None               # Event：停 receiver + keepalive（shutdown）
        self._receiver = None
        self._keepalive = None
        # 收音層（每輪）
        self._audio = None
        self._sender = None
        self._send_stop = None
        # 其他
        self._capturing = False
        self._armed_at = 0.0                 # arm 時記 monotonic（計時 log 用）
        self._disabled = False               # 缺 key / 401 → 本次執行停用（鍵盤照常）

    def is_armed(self) -> bool:
        with self._lock:
            return self._capturing

    def _ensure_connected(self) -> bool:
        """確保持久連線存在：已連則復用（True）；未連則建線 + 起常駐 receiver/keepalive
        （含「開麥連線」計時）。連線失敗回 False。呼叫者（arm）持 _lock。"""
        if self._ws is not None:
            return True
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
        self._ws = ws
        self._conn_stop = conn_stop
        self._receiver = receiver
        self._keepalive = keepalive
        receiver.start()
        keepalive.start()
        return True

    def arm(self) -> None:
        """冪等開麥：已 capturing / 已停用 no-op；缺 key 印一次警告後停用。
        首輪建線（580ms），之後只 spawn arecord + sender（~140ms）。"""
        with self._lock:
            if self._disabled or self._capturing:
                return
            if not self._api_key:
                print("[語音辨識] ⚠️ 未設定 DEEPGRAM_API_KEY，STT 停用（鍵盤輸入照常）")
                self._disabled = True
                return
            if not self._ensure_connected():
                return  # 連線失敗（已印原因）；本輪走鍵盤
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

    def _connect_with_retry(self):
        """建線；非 401 失敗重試 1 次；401 → 永久停用（本次執行）。"""
        for attempt in (1, 2):
            try:
                return self._ws_factory(self._api_key)
            except Exception as e:
                if _is_auth_error(e):
                    print("[語音辨識] ⚠️ API key 無效（HTTP 401），本次執行停用 STT")
                    self._disabled = True
                    return None
                if attempt == 1:
                    continue
                print(f"[語音辨識] ⚠️ 連線失敗（{type(e).__name__}: {e!r}），本輪改用鍵盤")
                return None

    def _send_loop(self, ws, audio, send_stop) -> None:
        """audio.read → ws.send（經 _send_lock）；EOF（disarm terminate / 裝置故障）或
        send_stop 即止。首框到達印「開麥→第一個音框」計時。"""
        first = True
        try:
            while not send_stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                if first:
                    # arm 記的 _armed_at 到第一個音框 ≈ arecord 冷啟動 + 首框填充
                    _timing(f"開麥→第一個音框 {time.monotonic() - self._armed_at:.2f}s（arecord 冷啟動＋首框填充）")
                    first = False
                with self._send_lock:
                    ws.send(chunk)
        except Exception:
            pass  # ws 已關 / 死 → 靜默結束；receiver 負責標記死亡

    def _receive_loop(self, ws, conn_stop) -> None:
        """常駐：ws.recv → JSON → speech_final（**僅 _capturing 才注入**）。退出時若非
        shutdown 觸發 → 印警示並標記 _ws 死亡（下次 arm 重連）。"""
        try:
            while not conn_stop.is_set():
                msg = ws.recv()
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
            if not conn_stop.is_set():
                print(f"[語音辨識] ⚠️ 串流中斷（{type(e).__name__}），下次開麥重連")
        finally:
            with self._lock:
                if self._ws is ws:
                    self._ws = None  # 標記死亡 → 下次 arm 重連

    def _keepalive_loop(self, ws, conn_stop) -> None:
        """常駐：idle（_capturing=False）時每 _KEEPALIVE_INTERVAL 秒送 KeepAlive 撐住
        連線（Deepgram 10s 無音訊/keepalive 即關 NET-0001）。conn_stop 設或 send 失敗即止。"""
        while not conn_stop.wait(_KEEPALIVE_INTERVAL):
            if self._capturing:
                continue  # 收音中音訊自然撐住，不送
            try:
                with self._send_lock:
                    ws.send(_KEEPALIVE_MSG)
            except Exception:
                break  # ws 死 → 退出；receiver 標記 _ws=None

    def disarm(self) -> None:
        """冪等收麥：停收音層（sender + arecord）+ 送 Finalize 沖尾巴；**連線不關**
        （keepalive 撐住，下輪直接開麥）。"""
        with self._lock:
            if not self._capturing:
                return
            self._capturing = False
            audio = self._audio
            send_stop = self._send_stop
            sender = self._sender
            ws = self._ws
            self._audio = None
            self._send_stop = None
            self._sender = None
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        if ws is not None:
            try:
                with self._send_lock:
                    ws.send(_FINALIZE_MSG)  # 沖 pending 音訊，乾淨收尾
            except Exception:
                pass

    def shutdown(self) -> None:
        """程式退出：收收音層 + 送 CloseStream + 關連線 + 收常駐 thread。"""
        self.disarm()
        with self._lock:
            ws = self._ws
            conn_stop = self._conn_stop
            receiver = self._receiver
            keepalive = self._keepalive
            self._ws = None
            self._conn_stop = None
            self._receiver = None
            self._keepalive = None
        if conn_stop is not None:
            conn_stop.set()
        if ws is not None:
            try:
                with self._send_lock:
                    ws.send(_CLOSE_MSG)
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                pass
        for th in (receiver, keepalive):
            if th is not None:
                th.join(timeout=1.0)
```

並在模組頂部常數區（`CHUNK_BYTES = 3200` 之後）加：
```python
_KEEPALIVE_INTERVAL: float = 5.0  # 秒；< Deepgram 10s idle timeout（NET-0001）。測試可 monkeypatch 縮短
_KEEPALIVE_MSG = json.dumps({"type": "KeepAlive"})
_FINALIZE_MSG = json.dumps({"type": "Finalize"})
_CLOSE_MSG = json.dumps({"type": "CloseStream"})
```

> 註：本 Task 已含 `_keepalive_loop` / `_FINALIZE_MSG` / `_CLOSE_MSG` 的程式碼（與 Task 3 同檔一次到位較省事），但**對應測試**留 Task 3 補（本 Task 只先綠化復用 / 閘門 / 重連三測 + 既有測試）。

- [ ] **Step 4: 更新既有測試（行為改變的合法調整）**

`tests/stt/test_worker.py` 兩處：
1. `test_disarm_closes_audio_and_allows_rearm`：原 `assert worker.is_armed() and len(wss) == 2 and len(audios) == 2` → 改為
   ```python
       assert worker.is_armed() and len(wss) == 1 and len(audios) == 2   # ws 復用、arecord 每輪重開
   ```
   並把該 test 結尾的 `worker.disarm()` 改為 `worker.shutdown()`（disarm 不再關連線，需 shutdown 收常駐 thread）。
2. 其餘呼叫 `worker.disarm()` 作為**收尾 cleanup** 的既有 test（`test_speech_final_injected_normalized` / `test_interim_empty_and_nonresults_not_injected` / `test_sender_streams_audio_chunks` / `test_arm_idempotent_single_session` / `test_connect_retry_once_then_success` / `test_stream_interruption_warns` / 既有計時三測）→ 結尾 `worker.disarm()` 改 `worker.shutdown()`（確保常駐 receiver/keepalive 收掉，避免 daemon thread 跨 test 殘留）。**斷言不動**（除上述 #1）。

> `test_stream_interruption_warns`：斷言 `"串流中斷" in out` 維持綠（新訊息「串流中斷（…），下次開麥重連」仍含該子字串）。`test_arm_idempotent_single_session`（arm→arm 無 disarm）factory 仍 1 次（第二 arm capturing=True no-op）。

- [ ] **Step 5: 跑測試見 PASS**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS（新三測 + 既有全綠）。

- [ ] **Step 6: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "feat(stt): 持久連線重構 — 整場共用一條 ws + 每輪只開麥（連線復用/閘門/重連）"
git branch --contains HEAD
```

---

## Task 3: KeepAlive / Finalize / CloseStream 控制訊息測試

**Files:**
- Test: `tests/stt/test_worker.py`（純補測；Task 2 已實作三控制訊息）

**Interfaces:**
- Consumes（Task 2 已產出）：`_keepalive_loop`、`_KEEPALIVE_INTERVAL`、disarm 的 `_FINALIZE_MSG`、shutdown 的 `_CLOSE_MSG`、`FakeWs.sent`（含 str control）。

- [ ] **Step 1: 寫 failing 測試（keepalive / finalize / closestream）**

在 `tests/stt/test_worker.py` 末尾加：
```python
def _control_sent(ws, name):
    return any(isinstance(s, str) and name in s for s in ws.sent)


def test_keepalive_sent_when_idle(monkeypatch):
    """disarm 後（capturing=False）keepalive thread 送 KeepAlive 撐住連線。"""
    monkeypatch.setattr(stt_mod, "_KEEPALIVE_INTERVAL", 0.02)
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()
    assert wait_until(lambda: _control_sent(ws, "KeepAlive"))
    worker.shutdown()


def test_finalize_sent_on_disarm():
    """disarm 送 Finalize 沖尾巴。"""
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()
    assert _control_sent(ws, "Finalize")
    worker.shutdown()


def test_closestream_sent_on_shutdown():
    """shutdown 送 CloseStream 優雅關閉。"""
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.shutdown()
    assert _control_sent(ws, "CloseStream")
```

- [ ] **Step 2: 跑測試見 PASS（Task 2 已實作 → 直接綠）**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -q`
Expected: PASS。
> 註：因控制訊息已於 Task 2 實作，本 Task 是「補測釘住行為」，三測直接綠（非經典 RED→GREEN）。若任一 FAIL = Task 2 實作有缺，回 Task 2 修。

- [ ] **Step 3: Commit**

```bash
git add tests/stt/test_worker.py
git commit -m "test(stt): KeepAlive/Finalize/CloseStream 控制訊息行為釘樁"
git branch --contains HEAD
```

---

## 收尾驗證（主 agent，非 sales-coder）

- **Iron Law**：`py -3.14 -m pytest tests/ -q` 全綠（baseline 660 + 新增 6 test = 666）。
- **三段 reviewer**：spec-reviewer → code-quality-reviewer（worker 併發重構，務必跑；重點審 thread 安全 / 閘門 / 重連 / send 序列化 / daemon cleanup）。
- **docs（resources/，主 agent 收尾）**：更新 `pineedtodo/2026-06-19_stt_tts_turn_latency_verify.md`（或新開單）記 Pi 驗證點：①「開麥連線」只第一輪印 ②「五張」開頭不再裁 ③長對話/回 hawk 連線未死 ④手動斷網下輪重連不卡。roadmap 現況註記。
- **worktree closeout**：merge --ff-only → push → 清 worktree。

---

## Self-Review

**1. Spec coverage：**
- spec §2 連線層常駐（ws+receiver+keepalive lazy 建線）→ Task 2 `_ensure_connected` + `_receive_loop` + `_keepalive_loop` ✓；收音層每輪 → arm/disarm 的 audio/sender ✓。
- spec §2 `_capturing` 閘門 → `_receive_loop` `if not self._capturing: continue` + Task 2 gating 測 ✓；`_send_lock` 序列化 → 所有 send 包鎖 ✓。
- spec §2 重連 → `_ensure_connected` 復用判斷 + `_receive_loop` finally 標記 + Task 2 重連測 ✓。
- spec §2 keepalive 5s / capturing 跳過 → `_keepalive_loop` + `_KEEPALIVE_INTERVAL` + Task 3 測 ✓；Finalize/CloseStream → disarm/shutdown + Task 3 測 ✓。
- spec §3「main.py 不動」→ 介面不變，plan 無 main.py task ✓；既有測試語意更新 → Task 2 Step 4 ✓。
- spec §6 測試清單（復用/keepalive/閘門/Finalize/重連/shutdown）→ Task 2+3 全覆蓋 ✓。

**2. Placeholder scan：** 無 TBD/TODO；完整新 class code 與 test code 均給出（含既有 test 改前/改後）。

**3. Type consistency：** `_ensure_connected()->bool`、`is_armed()->bool(_capturing)`、`_send_loop(ws, audio, send_stop)`、`_receive_loop(ws, conn_stop)`、`_keepalive_loop(ws, conn_stop)`、`_KEEPALIVE_INTERVAL: float`、控制常數 `_KEEPALIVE_MSG/_FINALIZE_MSG/_CLOSE_MSG` 全程一致；`FakeWs.feed`/`sent`/`close` 與 Task 1 定義一致；`_control_sent(ws, name)` helper 於 Task 3 定義後使用。
