# STT Deepgram Pre-roll Warmup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 每輪開麥時先送 `STT_PREROLL_MS` 毫秒靜音暖 Deepgram 串流，讓顧客首字不落在「暖機窗」被吞。

**Architecture:** 在 `SttWorker._send_loop` 進真實收音 while 迴圈之前，若 `_PREROLL_MS > 0` 則 burst 送對應位元組數的零 PCM（以 `CHUNK_BYTES` 切片、走 `_send_lock`、可被 `send_stop` 中止）。預設 0 = 不送。純加性、不動連線/arm/disarm。

**Tech Stack:** Python、websockets 同步 client（生產）、pytest + `tests/stt/conftest.py` 的 `FakeWs`/`FakeAudioSource`/`wait_until`。

## Global Constraints
- 產出物（註解/docstring/字串/commit）一律**繁體中文**。
- **不改 vendor**（`ActionGroupControl.py`/`Board.py`）；本案不碰 vendor。
- `git add` **明列檔名**，禁 `-A`/`.`。
- **預設 `STT_PREROLL_MS=0` = 零行為改變**（既有測試須全綠）。
- arecord 音訊格式固定 16kHz / S16_LE / mono（pre-roll 位元組數計算依此）。

---

### Task 1: `_send_loop` pre-roll 靜音暖機

**Files:**
- Modify: `myProgram/stt.py`（常數置 `_ENDPOINTING_MS` 附近 ~line 58；`_send_loop` ~line 200-216）
- Test: `tests/stt/test_worker.py`（append 2 測試）

**Interfaces:**
- Consumes（既有）：模組常數 `CHUNK_BYTES = 3200`、`SttWorker._send_lock`、`_send_loop(self, ws, audio, send_stop)`、`os`（已 import）。
- Produces：模組常數 `_PREROLL_MS: int`（測試以 `monkeypatch.setattr(stt_mod, "_PREROLL_MS", N)` 撥動）。

- [ ] **Step 1: 寫 failing test A（pre-roll 暖機前綴）**

append 到 `tests/stt/test_worker.py` 末：
```python
def test_preroll_silence_warms_stream_before_audio(monkeypatch):
    """STT_PREROLL_MS>0：_send_loop 先送對應靜音框暖 Deepgram，再串真實音訊。
    200ms @ 16kHz/16-bit mono = 6400 bytes = 2 × CHUNK_BYTES(3200) 靜音框。"""
    monkeypatch.setattr(stt_mod, "_PREROLL_MS", 200, raising=False)
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02", b"\x03\x04"])
    worker.arm()
    silence = b"\x00" * stt_mod.CHUNK_BYTES
    assert wait_until(lambda: ws.sent == [silence, silence, b"\x01\x02", b"\x03\x04"])
    worker.shutdown()
```

- [ ] **Step 2: 跑 test A 見 FAIL**

Run: `py -m pytest tests/stt/test_worker.py::test_preroll_silence_warms_stream_before_audio -v`
Expected: FAIL — `ws.sent` 只有 `[b"\x01\x02", b"\x03\x04"]`（無靜音前綴），`wait_until` 逾時回 False → assert 失敗。

- [ ] **Step 3: 加模組常數 `_PREROLL_MS`**

在 `myProgram/stt.py` 的 `_ENDPOINTING_MS = ...`（~line 58）下方加：
```python
# pre-roll 暖機毫秒：每輪開麥先送這麼多 ms 靜音給 Deepgram 暖串流，顧客首字才不落在
# 暖機窗被吞（Pi 實證「等 1s 再講不掉字」= 暖機需求）。預設 0 = 不送、不改行為。
_PREROLL_MS = int(os.environ.get("STT_PREROLL_MS", "0"))
```

- [ ] **Step 4: 在 `_send_loop` while 前加 pre-roll**

把 `_send_loop`（~line 200-216）改為（**只在 `first = True` 之後、`while` 之前**插入 pre-roll 段，其餘不動）：
```python
    def _send_loop(self, ws, audio, send_stop) -> None:
        """audio.read → ws.send（經 _send_lock）；EOF（disarm terminate / 裝置故障）或
        send_stop 即止。首框到達印「開麥→第一個音框」計時。

        pre-roll：while 收音前先 burst 送 _PREROLL_MS 毫秒靜音暖 Deepgram 串流，讓顧客
        首字不落在暖機窗被吞（預設 0 = 不送）。送零非真實等待 → 不增 turn / 辨識延遲。"""
        first = True
        try:
            if _PREROLL_MS > 0:
                silence = b"\x00" * CHUNK_BYTES
                total = int(16000 * 2 * _PREROLL_MS / 1000)  # 16kHz × 2byte(S16_LE) × mono
                sent = 0
                while sent < total and not send_stop.is_set():
                    n = min(CHUNK_BYTES, total - sent)
                    with self._send_lock:
                        ws.send(silence[:n])
                    sent += n
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
```

- [ ] **Step 5: 跑 test A 見 PASS**

Run: `py -m pytest tests/stt/test_worker.py::test_preroll_silence_warms_stream_before_audio -v`
Expected: PASS（`ws.sent == [silence, silence, b"\x01\x02", b"\x03\x04"]`）。

- [ ] **Step 6: 寫 regression test B（預設 0 無前綴）**

append 到 `tests/stt/test_worker.py` 末：
```python
def test_no_preroll_when_default_zero(monkeypatch):
    """預設 0：不送任何靜音前綴，第一個送出的就是真實音框（不改行為）。"""
    monkeypatch.setattr(stt_mod, "_PREROLL_MS", 0, raising=False)
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02", b"\x03\x04"])
    worker.arm()
    assert wait_until(lambda: ws.sent == [b"\x01\x02", b"\x03\x04"])
    worker.shutdown()
```

- [ ] **Step 7: 跑 test B 見 PASS**

Run: `py -m pytest tests/stt/test_worker.py::test_no_preroll_when_default_zero -v`
Expected: PASS（無靜音前綴）。

- [ ] **Step 8: 跑全 stt suite 見全綠**

Run: `py -m pytest tests/stt/ -v`
Expected: 全 PASS（既有 + 2 新增）；既有 `test_sender_streams_audio_chunks` / `test_first_chunk_timing_logged_when_env_set` 仍綠（預設 0 無前綴）。

- [ ] **Step 9: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -F - <<'EOF'
feat(stt): add STT_PREROLL_MS to warm Deepgram stream before customer speech

Pi proved the first-char swallow is a per-turn Deepgram stream warmup window
(~1s): speaking immediately drops the soft onset (bing/hong), waiting 1s does
not. _send_loop now bursts STT_PREROLL_MS of silence PCM before the real
arecord audio so the customer's first word lands in an already-warm stream.
Burst (not a real wait) => no turn/result latency; pure zeros => no early mic,
no robot bleed, no AEC. Default 0 = no behavior change.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012DTTB5ygEsQjppQCyFznZC
EOF
```

---

## Self-Review（writing-plans 自掃）

1. **Spec coverage**：§2 行為（burst 靜音、CHUNK_BYTES 切片、send_stop gate、_send_lock、while 前、first 不受影響、預設 0）→ Step 3-4 全覆蓋；§3 改檔 → Task 1 兩檔；§6 測試 → Step 2/5/7/8。無 gap。
2. **Placeholder scan**：無 TBD/TODO；每碼步給完整碼。
3. **Type consistency**：`_PREROLL_MS`(int)、`CHUNK_BYTES`(3200)、`silence`(bytes)、`total/sent/n`(int) 全程一致；`stt_mod` = `import myProgram.stt as stt_mod`（test_worker.py 既有 line 8）。
