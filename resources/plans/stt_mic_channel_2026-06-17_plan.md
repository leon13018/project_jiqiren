# STT 單一 raw 麥克風聲道 實作 plan

> **For agentic workers:** 走專案 SDD（sales-coder → Iron Law → 三段審）。
> Spec：`resources/specs/stt_mic_channel_2026-06-17_spec.md`（WHAT）。本檔 = HOW，TDD。
> 基線 = main `62e31c6`（`-c 1` mono 降混 + prewarm + 計時 log）。
> **單一增量**：音源 `-c 1` 降混 → `-c 6` 原生 + 抽 `STT_MIC_CHANNEL` 軌（預設 ch1 生麥）。其餘不動。

**Goal**：餵 Deepgram 單一乾淨 raw 麥克風軌（取代糊糊的 6 軌平均），讓「刮刮樂」不被聽成數字；聲道 env 可設定以掃出最佳麥。

**測試指令**：`python -m pytest tests/stt/`（最終加 `tests/sales/`）。本機 `python` 沒裝 pytest → 用 `py -m pytest`。

---

## Task 1：音源抽單一聲道 + 測試

**Files**：Modify `myProgram/stt.py`（加常數/`_extract_channel`/`_mic_channel`、改 `_ArecordSource`、改 `_default_audio_factory`）；Modify `tests/stt/test_worker.py`（更新 factory 測試 + 加抽軌/env 測試）

### Step 1：先寫 RED — 更新 + 新增 `tests/stt/test_worker.py` 測試

1a. **替換** `test_default_audio_factory_command` 整個函式為（`-c 1`→`-c 6` + 驗 channel + 清 STT_MIC_CHANNEL）：
```python
def test_default_audio_factory_command(monkeypatch):
    # 只驗指令構造 + 預設聲道，不真起 subprocess（Windows 無 arecord）
    import myProgram.stt as stt_mod
    captured = {}
    class FakeProc:
        stdout = None
        def poll(self): return None
        def terminate(self): pass
    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()
    monkeypatch.setattr(stt_mod.subprocess, "Popen", fake_popen)
    monkeypatch.delenv("STT_ARECORD_DEVICE", raising=False)
    monkeypatch.delenv("STT_MIC_CHANNEL", raising=False)
    src = stt_mod._default_audio_factory()
    assert captured["cmd"] == ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
                               "-c", "6", "-t", "raw"]
    assert captured["kwargs"]["stdin"] == stt_mod.subprocess.DEVNULL
    assert src._channel == 1                      # 預設抽 ch1（第一支生麥）

    monkeypatch.setenv("STT_ARECORD_DEVICE", "hw:CARD=ArrayUAC10")
    stt_mod._default_audio_factory()
    assert captured["cmd"][1:3] == ["-D", "hw:CARD=ArrayUAC10"]
```

1b. 在該函式之後**新增** 4 個測試：
```python
def test_extract_channel_picks_requested_channel():
    import struct
    from myProgram.stt import _extract_channel
    buf = (struct.pack("<6h", 10, 11, 12, 13, 14, 15)
           + struct.pack("<6h", 20, 21, 22, 23, 24, 25))
    assert struct.unpack("<2h", _extract_channel(buf, 0)) == (10, 20)
    assert struct.unpack("<2h", _extract_channel(buf, 1)) == (11, 21)
    assert struct.unpack("<2h", _extract_channel(buf, 4)) == (14, 24)


def test_extract_channel_drops_partial_frame():
    import struct
    from myProgram.stt import _extract_channel
    buf = struct.pack("<6h", 1, 2, 3, 4, 5, 6)
    assert _extract_channel(buf + b"\x09\x09", 1) == _extract_channel(buf, 1)


def test_mic_channel_env_parsing(monkeypatch):
    import myProgram.stt as stt_mod
    monkeypatch.delenv("STT_MIC_CHANNEL", raising=False)
    assert stt_mod._mic_channel() == 1            # 未設 → 預設 ch1
    monkeypatch.setenv("STT_MIC_CHANNEL", "3")
    assert stt_mod._mic_channel() == 3
    monkeypatch.setenv("STT_MIC_CHANNEL", "abc")  # 非法 → fallback
    assert stt_mod._mic_channel() == 1
    monkeypatch.setenv("STT_MIC_CHANNEL", "9")    # 越界（非 0..5）→ fallback
    assert stt_mod._mic_channel() == 1


def test_arecord_source_extracts_channel():
    import io, struct
    from myProgram.stt import _ArecordSource
    buf = b"".join(struct.pack("<6h", v, v + 1, v + 2, v + 3, v + 4, v + 5)
                   for v in (10, 20, 30))
    class _P:
        stdout = io.BytesIO(buf)
        def poll(self): return None
        def terminate(self): pass
    out = _ArecordSource(_P(), channel=1).read(6)  # 6 bytes mono = 3 樣本（內部讀 36 bytes）
    assert struct.unpack("<3h", out) == (11, 21, 31)
```

- [ ] **Step 2：跑見 FAIL**
Run：`py -m pytest tests/stt/test_worker.py -k "audio_factory or extract_channel or mic_channel or arecord_source" -v`
Expected：FAIL（`_extract_channel`/`_mic_channel` 不存在、`_ArecordSource` 不收 channel、factory 仍 `-c 1`）。

### Step 3：改 `myProgram/stt.py`

3a. 在 `_is_auth_error` 函式**之後**、`class _ArecordSource` **之前**插入常數 + 兩個 helper：
```python
_CHANNELS = 6  # ReSpeaker 原生 6 聲道韌體：ch0=處理後（AEC/波束）/ ch1-4=生麥克風 / ch5=播放參考
_DEFAULT_MIC_CHANNEL = 1  # 預設抽 ch1（第一支生麥）；ch0 處理後實測降準確度、ch5 為播放參考


def _extract_channel(buf: bytes, channel: int, channels: int = _CHANNELS) -> bytes:
    """交錯多聲道 S16 buffer → 取指定 channel（每幀第 channel 個 16-bit 樣本）。不完整尾幀丟棄。"""
    frame = channels * 2
    usable = len(buf) - (len(buf) % frame)
    start = channel * 2
    return b"".join(buf[i + start:i + start + 2] for i in range(0, usable, frame))


def _mic_channel() -> int:
    """讀 STT_MIC_CHANNEL env（預設 1=第一支生麥）；未設 / 非法 / 越界(非 0..5) → fallback 預設。

    實測用：使用者一個 session 設一值掃 ch1→4 找「刮刮樂」最清楚的軌，定案後改 _DEFAULT_MIC_CHANNEL。
    """
    raw = os.environ.get("STT_MIC_CHANNEL")
    if raw is None:
        return _DEFAULT_MIC_CHANNEL
    try:
        ch = int(raw)
    except ValueError:
        return _DEFAULT_MIC_CHANNEL
    return ch if 0 <= ch < _CHANNELS else _DEFAULT_MIC_CHANNEL
```

3b. **替換** `_ArecordSource` 的 docstring + `__init__` + `read`（close 不動）：

把：
```python
class _ArecordSource:
    """arecord subprocess 包裝：read 走 stdout pipe，close 走 terminate。

    stdin=DEVNULL 對齊 tts.py mpg123 守則（不偷主程式 stdin）；terminate 容錯
    OSError（子程序剛好自然結束——對齊 tts.shutdown 同情境處理）。
    """

    def __init__(self, proc: "subprocess.Popen") -> None:
        self._proc = proc

    def read(self, n: int) -> bytes:
        return self._proc.stdout.read(n)
```
替換為：
```python
class _ArecordSource:
    """arecord subprocess 包裝：read 讀 6ch 交錯 stdout、抽單一聲道→mono，close 走 terminate。

    stdin=DEVNULL 對齊 tts.py mpg123 守則（不偷主程式 stdin）；terminate 容錯
    OSError（子程序剛好自然結束——對齊 tts.shutdown 同情境處理）。
    """

    def __init__(self, proc: "subprocess.Popen", channel: int = _DEFAULT_MIC_CHANNEL) -> None:
        self._proc = proc
        self._channel = channel

    def read(self, n: int) -> bytes:
        # 讀 n*6 bytes（6ch 交錯）→ 抽第 _channel 軌（生麥）→ 回 n bytes mono
        return _extract_channel(self._proc.stdout.read(n * _CHANNELS), self._channel)
```

3c. **替換** `_default_audio_factory`（`-c 1`→`-c 6` + 傳 channel）：

把：
```python
def _default_audio_factory():
    """production 音源：arecord 16kHz/S16_LE/mono raw → stdout pipe。

    裝置選擇：環境變數 STT_ARECORD_DEVICE（如 "plughw:1,0"）；未設用 ALSA 預設
    （Pi 端把 ReSpeaker 設為預設 capture 或設此變數——pineedtodo 會列）。
    """
    cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"]
    device = os.environ.get("STT_ARECORD_DEVICE")
    if device:
        cmd[1:1] = ["-D", device]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    return _ArecordSource(proc)
```
替換為：
```python
def _default_audio_factory():
    """production 音源：arecord 16kHz/S16_LE 原生 6ch raw → 抽 STT_MIC_CHANNEL 軌 → mono。

    裝置選擇：環境變數 STT_ARECORD_DEVICE（原生 6ch 須 "hw:CARD=ArrayUAC10"）；聲道
    由 STT_MIC_CHANNEL 決定（預設 ch1 生麥；Pi 端掃 ch1-4 找最清楚的——pineedtodo 會列）。
    """
    cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", str(_CHANNELS), "-t", "raw"]
    device = os.environ.get("STT_ARECORD_DEVICE")
    if device:
        cmd[1:1] = ["-D", device]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    return _ArecordSource(proc, _mic_channel())
```

- [ ] **Step 4：跑見 PASS（含既有不破）**
Run：`py -m pytest tests/stt/ -v`
Expected：全 passed。特別確認既有 `test_sender_streams_audio_chunks`（FakeAudioSource 注入、不經 `_ArecordSource` → 不受影響）、prewarm 4 測試、`test_module_api_lazy_singleton` 皆綠。

- [ ] **Step 5：全回歸**
Run：`py -m pytest tests/stt/ tests/sales/`
Expected：sales 592 + stt 全綠。

- [ ] **Step 6：commit**
```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "feat(stt): 改抽單一 raw 麥克風聲道（-c 6 + STT_MIC_CHANNEL，取代 -c 1 降混）"
git branch --contains $(git rev-parse HEAD)   # 自驗落 worktree-stt-mic-channel
```

---

## 完成檢查（主 agent Iron Law）
- `py -m pytest tests/stt/ tests/sales/` → `N passed`（sales 592 + stt 約 629）。
- `git branch --contains <SHA>` → `worktree-stt-mic-channel`。
- grep stt.py：`"-c", "6"` = 1（factory）；`"-c", "1"` = 0（降混已移除）；`_extract_channel`/`_mic_channel`/`STT_MIC_CHANNEL` 各 ≥1。
- `main.py` 無改動（`git diff --stat` 不含 main.py）。
