# STT 開麥冷啟動量測 — Mini SDD spec

**日期：** 2026-06-19
**類型：** 量測埋點（worker `myProgram/stt.py`，env-gated，零行為改變）

## Why
使用者 Pi 實測回報「語音播完沒辦法馬上說話、要等一下才錄得到」。根因推論為 arecord 開麥冷啟動（既有「開麥裁切」），但目前 `STT_TTS_TIMING` 只量「開麥→辨識結果」（含顧客講話時間，無法隔離）。本埋點把 turn 開頭的空檔拆成**連線**與**裝置冷啟動**兩段，定量回答「是連線延遲還是裝置」，再決定要不要做較大的 warm-during-prompt 改造。全程 `STT_TTS_TIMING` 閘門，未設零輸出。

## 改動 1：arm() 量 ws 連線時長
- **檔**：`myProgram/stt.py`，`arm()` 內 `ws = self._connect_with_retry()` 區段（現 ~112-115 行）
- **改前**：
```python
            ws = self._connect_with_retry()
            if ws is None:
                return  # 本輪放棄（已印原因）；下次 arm 再試或已永久停用
            audio = self._audio_factory()
```
- **改後**：
```python
            _connect_t0 = time.monotonic()
            ws = self._connect_with_retry()
            if ws is None:
                return  # 本輪放棄（已印原因）；下次 arm 再試或已永久停用
            _timing(f"開麥連線 {(time.monotonic() - _connect_t0) * 1000:.0f}ms")
            audio = self._audio_factory()
```

## 改動 2：_send_loop 量第一個音框到達時間（裝置冷啟動）
- **檔**：`myProgram/stt.py`，`_send_loop`（現 ~143-152 行）
- **改前**：
```python
    def _send_loop(self, ws, audio, stop) -> None:
        """audio.read → ws.send；EOF（disarm terminate / 裝置故障）或 stop 即止。"""
        try:
            while not stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                ws.send(chunk)
        except Exception:
            pass  # ws 已關（disarm / 斷線）→ 靜默結束；對外回報由 receiver 負責
```
- **改後**：
```python
    def _send_loop(self, ws, audio, stop) -> None:
        """audio.read → ws.send；EOF（disarm terminate / 裝置故障）或 stop 即止。"""
        first = True
        try:
            while not stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                if first:
                    # 從 arm 記的 _armed_at 到第一個音框到達 ≈ arecord 冷啟動 + 首框
                    # （CHUNK_BYTES=100ms）填充。隔離出「裝置開麥延遲」這段死時間。
                    _timing(f"開麥→第一個音框 {time.monotonic() - self._armed_at:.2f}s（arecord 冷啟動＋首框填充）")
                    first = False
                ws.send(chunk)
        except Exception:
            pass  # ws 已關（disarm / 斷線）→ 靜默結束；對外回報由 receiver 負責
```

## 語意
- 兩行皆走既有 `_timing`（`STT_TTS_TIMING` 閘門）+ 既有 `_armed_at`、`time`、`CHUNK_BYTES`，零新依賴、零新狀態（`first` / `_connect_t0` 皆區域）。
- `_armed_at`（line 123）在 ws 連線**之後**設 → 改動 2 的量測**不含連線**（連線另由改動 1 量），兩段互斥可加總 = turn 開頭總空檔。

## 行為不變式
- `STT_TTS_TIMING` 未設 → 零新增輸出，與現狀逐位元相同。
- 不動 arm/disarm session 生命週期、不動 send/recv 邏輯、不動 endpointing。

## 驗證
- `py -3.14 -m pytest tests/stt/ -q`：
  - 新增 `test_connect_timing_logged_when_env_set`（env 設 → capsys 含「開麥連線」）。
  - 新增 `test_first_chunk_timing_logged_when_env_set`（env 設 + chunks → capsys 含「開麥→第一個音框」）。
  - 既有全綠。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 658）。
- Pi：`STT_TTS_TIMING=1 python3.11 -m myProgram` 跑一輪 → 看每輪的「開麥連線 Xms」+「開麥→第一個音框 Y.Ys」，回報數字。

## Out of scope
- 不做 warm-during-prompt 改造（待本量測數據決定）。
- 不動 drain / endpointing / 其他既有行為。
