# STT warm-arecord Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 麥克風在 `prearm`（念提示音時）就開著暖機、sender 先丟棄機器人音，`arm` 翻送出模式 → 根治開頭 ~40ms 冷啟動裁頭。

**Architecture:** 收音層（arecord + sender）從 `arm` 搬到 `prearm`；`_send_loop` 以 `_capturing` 切 discard/send；連續讀 pipe 不爆。`main.py` 不動。

**Tech Stack:** Python 3.11；Windows pytest（`py -3.14 -m pytest`）；無新依賴。

## Global Constraints
- **繁體中文**註解/commit。
- `arm`/`disarm`/`shutdown`/`prearm` signature 不變 → `main.py` 不動。
- 念提示音期（capturing=False）錄到的機器人音**丟棄不送**（無自我回授）。
- 連續讀 arecord → pipe 不爆（修舊 warm「收不到音」）。
- 不用 `git add -A`；worktree `worktree-stt-warm-arecord`；每 commit `git branch --contains HEAD` 驗。
- 不碰 endpointing / 對話文案 / receiver / 連線層 / 辨識 robustness。

---

## Task 1: SttWorker 收音層搬到 prearm + sender discard/send 模式

**Files:** Modify `myProgram/stt.py`（`prearm` / `arm` / `_send_loop` / `disarm` + 新 `_warm_capture`）；Test `tests/stt/test_worker.py`（既有回歸網）

- [ ] **Step 1: 新增 `_warm_capture()`（在 `arm` 之後、`prearm` 之前或附近）**
```python
    def _warm_capture(self) -> None:
        """冪等開麥暖機：_audio 為 None 才開 arecord + 起 sender（discard/send 由
        _capturing 控制）。單一 caller thread（主線程 prearm/arm），_audio 等於 _lock 內寫。"""
        with self._lock:
            if self._audio is not None:
                return
            audio = self._audio_factory()
            send_stop = threading.Event()
            sender = threading.Thread(
                target=self._send_loop, args=(audio, send_stop),
                name="SttSender", daemon=True)
            self._audio = audio
            self._send_stop = send_stop
            self._sender = sender
        sender.start()
```

- [ ] **Step 2: 改 `prearm()`（warm + connect）**

把現 `prearm`（185-191）改為：
```python
    def prearm(self) -> None:
        """非阻塞預開麥 + 預連線：念提示音時就開 arecord 暖機（sender discard 模式讀+丟，
        麥克風保持熱、pipe 排空）+ 背景建線。arm 後 sender 翻送出 → 無冷啟動裁頭。
        快查任一成立即返：已停用 / 收音中 / 缺 key。"""
        if self._disabled or self._capturing or not self._api_key:
            return
        self._warm_capture()                       # 開麥暖機（capturing=False → 丟棄）
        if self._ws is None:
            threading.Thread(target=self._ensure_connected, name="SttPrearm", daemon=True).start()
```

- [ ] **Step 3: 改 `arm()`（不再自開 arecord/sender；capturing 先 True 再 warm）**

把現 `arm`（156-183）的 `with self._lock:` spawn 段（170-183）改為：
```python
        # 連線在鎖外（_ensure_connected 內自持 _connect_lock；失敗已印原因）
        if not self._ensure_connected():
            return  # 本輪走鍵盤
        with self._lock:
            if self._capturing:
                return  # 防禦：理論上單 caller 不發生
            self._armed_at = time.monotonic()
            self._capturing = True                 # sender 翻送出（先設，再 warm → 無漏首框 race）
        self._warm_capture()                       # 冪等：prearm 已暖則 no-op；否則現開（capturing 已 True → 直接送）
```
（即：移除原本在 `_lock` 內 `audio = self._audio_factory()` … `sender.start()` 那段，改為設 capturing 後呼叫 `_warm_capture`。`arm` docstring 同步：「prearm 已暖則翻送出；否則現開」。）

- [ ] **Step 4: 改 `_send_loop`（去 `ws` 參、discard/send 模式）**

把現 `_send_loop(self, ws, audio, send_stop)`（208-224）改為：
```python
    def _send_loop(self, audio, send_stop) -> None:
        """讀 arecord：capturing=False（暖機/收音窗外）讀+丟（保持 pipe 排空、麥克風熱）；
        capturing=True 送 self._ws（經 _send_lock）。暖機讓 arm 後首框即時送、無冷啟動裁頭。
        EOF（disarm terminate / 裝置故障）或 send_stop 即止。"""
        first_sent = True
        try:
            while not send_stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                if not self._capturing:
                    continue  # 丟棄模式：讀+丟（機器人提示音不送 Deepgram，無自我回授）
                ws = self._ws
                if ws is None:
                    continue  # capturing 但連線未就緒（罕見）→ 丟
                if first_sent:
                    _timing(f"arm→首框送出 {time.monotonic() - self._armed_at:.2f}s（麥克風已暖，應趨近 0）")
                    first_sent = False
                with self._send_lock:
                    ws.send(chunk)
        except Exception:
            pass  # ws 已關 / 死 → 靜默結束；receiver 負責標記死亡
```

- [ ] **Step 5: 改 `disarm()` 判定（`_audio is None`，涵蓋暖機未 arm）**

把現 `disarm` 開頭（`with self._lock:` / `if not self._capturing: return`，約 277-279）改為：
```python
    def disarm(self) -> None:
        """冪等收麥：停收音層（sender + arecord）；**連線不關**（keepalive 撐住，下輪直接
        開麥）。判定用 _audio（涵蓋 prearm 暖機但未 arm 也要收 sender）。"""
        with self._lock:
            if self._audio is None:
                return
            self._capturing = False
            audio = self._audio
            send_stop = self._send_stop
            sender = self._sender
            self._audio = None
            self._send_stop = None
            self._sender = None
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
```
（其餘 disarm 後續行（不送 Finalize 註解）保留。）

- [ ] **Step 6: 跑既有測試對齊**

Run: `py -3.14 -m pytest tests/stt/ -q`
Expected: PASS。重點既有測試行為：
- `test_sender_streams_audio_chunks`：arm 直呼 → capturing 先 True、`_warm_capture` 開 sender → 首框即送（無丟棄）→ `ws.sent == chunks`。
- `test_disarm_closes_audio_and_allows_rearm`：arm 開 audios[0]、disarm close、re-arm 開 audios[1]；`len(wss)==1 and len(audios)==2`、`is_armed` 對。
- `test_prearm_connects_in_background` / `_noop_*`：prearm 現也 `_warm_capture`（FakeAudioSource 無 chunk → sender EOF 即退，無害）；ws 斷言不變；結尾 `shutdown` 收。
- `test_speech_final_*` / `test_connection_*` / 控制訊息 / 計時：續綠。
若有斷言因結構調整而紅 → 對齊（非弱化；行為等價）。

- [ ] **Step 7: Commit**
```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "feat(stt): warm-arecord — 收音層搬 prearm + sender discard/send 模式（修開頭裁頭）"
git branch --contains HEAD
```

---

## Task 2: warm 行為新測（discard→send / 暖機未 arm 收尾）

**Files:** Test `tests/stt/test_worker.py`

- [ ] **Step 1: 寫測試**

在 `tests/stt/test_worker.py` 末尾加（檔頂補 `import queue` 若無）：
```python
class _BlockingAudio:
    """read 阻塞至 feed 或 close（模擬連續 arecord，不會立即 EOF）。"""
    def __init__(self):
        self._q = queue.Queue()
        self.closed = False
    def feed(self, chunk):
        self._q.put(chunk)
    def read(self, n):
        item = self._q.get()
        return b"" if item is None else item
    def close(self):
        self.closed = True
        self._q.put(None)


def test_warm_capture_discards_then_sends_after_arm():
    """prearm 暖機期（capturing=False）讀到的音丟棄不送；arm 後（capturing=True）才送。"""
    audio = _BlockingAudio()
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=lambda: audio)
    worker.prearm()
    assert wait_until(lambda: worker._audio is audio and worker._ws is not None)
    audio.feed(b"\x01\x02")                       # 暖機期 → 丟棄
    import time as _t; _t.sleep(0.1)
    assert ws.sent == [], "暖機期音訊不應送出"
    worker.arm()                                  # capturing=True
    audio.feed(b"\x03\x04")                       # → 送出
    assert wait_until(lambda: b"\x03\x04" in ws.sent)
    assert b"\x01\x02" not in ws.sent             # 暖機期那框始終沒送
    worker.shutdown()


def test_prearm_warmed_sender_stopped_by_disarm():
    """prearm 暖機但未 arm → disarm 仍收掉 sender（_audio is None 判定）。"""
    audio = _BlockingAudio()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: FakeWs(), audio_factory=lambda: audio)
    worker.prearm()
    assert wait_until(lambda: worker._sender is not None and worker._sender.is_alive())
    worker.disarm()                               # 未 arm（capturing=False），_audio 非 None → 仍收
    assert worker._audio is None and audio.closed
    assert wait_until(lambda: not worker._sender.is_alive())
    worker.shutdown()
```

- [ ] **Step 2: 跑見 PASS**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -k "warm or prearm" -q`
Expected: PASS（Task 1 已實作 → 直接綠）。若紅 = Task 1 實作有缺，回 Task 1 修。

- [ ] **Step 3: 全套 + Commit**
```bash
py -3.14 -m pytest tests/ -q   # 預期 675 + 2
git add tests/stt/test_worker.py
git commit -m "test(stt): warm-arecord discard→send + 暖機未 arm 收尾測"
git branch --contains HEAD
```

---

## 收尾驗證（主 agent）
- **Iron Law**：`py -3.14 -m pytest tests/ -q` 全綠（baseline 675 + 2）。
- **三段 reviewer**：spec-reviewer → code-quality-reviewer（動 working 收音層 + 併發，務必跑；重點 discard/send 翻轉時序、`_audio` 判定、無漏首框、prearm/arm/disarm/sender 跨執行緒）。
- **docs**：pineedtodo Pi 驗證點（arm→首框送出趨近 0 / 搶快不裁頭 / 無自我回授 / 全流程）；roadmap 註記。
- **worktree closeout**：merge --ff-only → push → 清。

---

## Self-Review
**1. Spec coverage：** `_warm_capture`→Task1 S1；prearm→S2；arm→S3；_send_loop discard/send→S4；disarm `_audio` 判定→S5；既有回歸→S6；warm 新測→Task2 ✓。
**2. Placeholder scan：** 無 TBD；prod 與 test code 完整（含改前指引/改後完整碼）。
**3. Type consistency：** `_warm_capture()->None`、`_send_loop(audio, send_stop)`（去 ws 參）、`_BlockingAudio.read/feed/close`、`disarm` `_audio is None` 判定、`arm` capturing-先-True 全程一致；`prearm`/`arm` 皆呼叫 `_warm_capture`（冪等）。
