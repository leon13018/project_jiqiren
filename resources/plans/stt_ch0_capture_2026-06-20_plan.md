# STT 收音改取 ch0 處理聲道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven / executing-plans。Steps 用 checkbox 追蹤。

**Goal:** 收音從「6 聲道全降混」改成「只抽 ReSpeaker ch0（晶片處理過 ASR 聲道）」，修整體辨識極不準。

**Architecture:** `myProgram/stt.py` 收音層改動——`arecord -c 6`、`_ArecordSource.read()` 反交錯抽 ch0 回單聲道；其餘（連線/keyterm/語言/endpointing）不動。

**Tech Stack:** Python stdlib（`array` 反交錯）；buildless 測試走 `tests/stt/` 既有 fake。

## Global Constraints

- **繁體中文** 註解 / 字串 / commit。
- **設計**：`resources/specs/stt_ch0_capture_2026-06-20_spec.md`（含 A/B 實證）。
- **env 旋鈕**（模組常數，import 時讀一次）：`STT_CAPTURE_CHANNELS`(預設 6) / `STT_ASR_CHANNEL`(預設 0)。
- **不動**：keyterm / 語言碼 / endpointing / 連線 / arm-disarm / Deepgram URL（`channels=1` 不變）。
- **直通相容**：`channels==1` 時 `read` 行為與現狀完全一致（零開銷）。
- **紅線**：`array` 頂層 import OK；禁 websockets 頂層 import。**worktree**；不用 `git add -A`。

## 執行治理
`stt.py` 是 worker 檔 → 觸發 SDD → 派 sales-coder + 三段 reviewer，worktree 內。

---

## Task 1: `_ArecordSource` 反交錯抽 ch0 + 工廠收 6 聲道

**Files:**
- Modify: `myProgram/stt.py`（頂層 `import array`；`_PREROLL_MS` 附近加 2 env 常數；`_ArecordSource` 類；`_default_audio_factory`）
- Test: `tests/stt/test_worker.py`（改 1 測試 + 新增 3 測試）

**Interfaces:**
- Produces: `_ArecordSource(proc, channels=1, ch_index=0)`；`read(n)` 回「抽出第 ch_index 條的單聲道 bytes」（≤n，EOF 回 `b""`）。
- Consumes（既有）：`_send_loop` 呼叫 `audio.read(CHUNK_BYTES)`（介面不變，仍收單聲道 bytes）。

- [ ] **Step 1: 寫 failing 測試（反交錯 / 直通 / EOF + 工廠 -c 6）**

在 `tests/stt/test_worker.py` 適當處新增（檔頭若無 `import array, io` 補上）：
```python
import array, io


class _FakeProcStream:
    """包一段 bytes 當 arecord stdout（read 走 BytesIO；poll/terminate 供 close）。"""
    def __init__(self, data: bytes):
        self.stdout = io.BytesIO(data)
    def poll(self): return None
    def terminate(self): pass


def _interleave(frames):
    """frames: list[tuple[int,...]] → S16_LE 交錯 bytes。"""
    a = array.array("h")
    for f in frames:
        a.extend(f)
    return a.tobytes()


def test_arecord_source_extracts_ch0_from_6ch():
    import myProgram.stt as stt_mod
    data = _interleave([(100, 1, 2, 3, 4, 5),
                        (200, 6, 7, 8, 9, 10),
                        (300, 11, 12, 13, 14, 15)])
    src = stt_mod._ArecordSource(_FakeProcStream(data), channels=6, ch_index=0)
    out = src.read(6)  # 想要 3 個單聲道 sample = 6 bytes
    got = array.array("h"); got.frombytes(out)
    assert list(got) == [100, 200, 300]


def test_arecord_source_mono_passthrough():
    import myProgram.stt as stt_mod
    data = array.array("h", [10, 20, 30]).tobytes()
    src = stt_mod._ArecordSource(_FakeProcStream(data), channels=1, ch_index=0)
    assert src.read(6) == data  # 直通：channels=1 原樣回


def test_arecord_source_eof_returns_empty():
    import myProgram.stt as stt_mod
    src = stt_mod._ArecordSource(_FakeProcStream(b""), channels=6, ch_index=0)
    assert src.read(6) == b""
```

並把既有 `test_default_audio_factory_command`（現 ~200-201）的斷言 `-c 1` 改 `-c 6`：
```python
    assert captured["cmd"] == ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
                               "-c", "6", "-t", "raw"]
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py::test_arecord_source_extracts_ch0_from_6ch tests/stt/test_worker.py::test_default_audio_factory_command -v`
Expected: FAIL（現 `_ArecordSource` 不收 channels 參數；工廠出 `-c 1`）。

- [ ] **Step 3: 頂層 import + env 常數**

`myProgram/stt.py` 頂層 import 區（`import threading` 附近）加：
```python
import array
```
`_PREROLL_MS = ...`（現 ~62）之後加：
```python
# 收音聲道：ReSpeaker XVF-3000 原生 6 聲道，ch0 = 晶片處理過的 ASR 專用聲道（beamform＋AEC＋
# 除噪＋AGC）、ch1-4 生麥、ch5 喇叭回授。只抽 ch0 送 Deepgram——6 聲道降混會稀釋 ch0、相位互抵
# 糊掉辨識（2026-06-20 同源 A/B 實證）。channels=1 為直通退路。env import 時讀一次（同 endpointing）。
_CAPTURE_CHANNELS = int(os.environ.get("STT_CAPTURE_CHANNELS", "6"))
_ASR_CHANNEL = int(os.environ.get("STT_ASR_CHANNEL", "0"))
```

- [ ] **Step 4: 改 `_ArecordSource` 反交錯**

把現 `_ArecordSource`（現 ~346-364）整類替換為：
```python
class _ArecordSource:
    """arecord subprocess 包裝：收多聲道 → 反交錯抽單一聲道（ReSpeaker ch0 = 處理過 ASR 聲道）。

    XVF-3000 原生只出 6 聲道（ch0 處理過 / ch1-4 生麥 / ch5 回授）；降混會稀釋 ch0 並相位互抵
    → 收 6 聲道、只取 ch0 送 Deepgram（2026-06-20 同源 A/B：ch0 近完美、降混糊掉）。
    channels=1 為直通（向後相容 / env 退路）。stdin=DEVNULL 對齊 tts.py mpg123 守則。
    """

    def __init__(self, proc: "subprocess.Popen", channels: int = 1, ch_index: int = 0) -> None:
        self._proc = proc
        self._channels = channels
        self._ch = ch_index
        self._frame_bytes = channels * 2   # S16_LE = 2 bytes/sample

    def read(self, n: int) -> bytes:
        if self._channels == 1:
            return self._proc.stdout.read(n)   # 直通：零反交錯開銷
        # 多聲道：讀滿 n//2 個 frame（frame 對齊）→ array 切片抽第 _ch 條 → 回單聲道 bytes
        raw = self._readexact((n // 2) * self._frame_bytes)
        if not raw:
            return b""
        samples = array.array("h")
        samples.frombytes(raw)
        return array.array("h", samples[self._ch::self._channels]).tobytes()

    def _readexact(self, want: int) -> bytes:
        """讀滿 want bytes（pipe 可能短讀）；EOF 提早回（呼叫端視為結束）。"""
        chunks = []
        got = 0
        while got < want:
            c = self._proc.stdout.read(want - got)
            if not c:
                break
            chunks.append(c)
            got += len(c)
        return b"".join(chunks)

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass
```

- [ ] **Step 5: 改 `_default_audio_factory`**

把現 `_default_audio_factory`（現 ~367-379）的 cmd 與回傳改為：
```python
def _default_audio_factory():
    """production 音源：arecord 16kHz/S16_LE/<_CAPTURE_CHANNELS> 聲道 raw → stdout pipe；
    _ArecordSource 反交錯抽 ch0（XVF-3000 處理過 ASR 聲道）。

    裝置選擇：環境變數 STT_ARECORD_DEVICE（如 "plughw:CARD=ArrayUAC10"）；未設用 ALSA 預設。
    """
    cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
           "-c", str(_CAPTURE_CHANNELS), "-t", "raw"]
    device = os.environ.get("STT_ARECORD_DEVICE")
    if device:
        cmd[1:1] = ["-D", device]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return _ArecordSource(proc, channels=_CAPTURE_CHANNELS, ch_index=_ASR_CHANNEL)
```

- [ ] **Step 6: 跑新測試 + STT 全量確認 PASS**

Run: `py -3.14 -m pytest tests/stt/ -v --tb=short`
Expected: 全 passed（含新 3 測試 + 改的工廠測試；既有 worker/keyterm/normalize/inject/wireup 不破）。

- [ ] **Step 7: 跑全量回歸**

Run: `py -3.14 -m pytest tests/ -q`
Expected: 全 passed、0 failed。

- [ ] **Step 8: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "fix(stt): 收音改抽 ReSpeaker ch0 處理聲道（修 6 聲道降混致整體辨識崩潰）"
```

---

## Pi by-ear 驗收（收尾後）

Pi `python3.11 -m myProgram --web`（`STT_ARECORD_DEVICE` 維持現有 `plughw:CARD=ArrayUAC10`，配 `-c 6` 直通）：
- 重講「我要三瓶冰紅茶和五張刮刮樂，然後結賬」「三瓶」「五張」等 → 辨識應近完美（對比修前糊成一團）。
- 真機 TTS 播放後接話：ch0 含 AEC，應比修前更不受機器人自身語音干擾。
- 若 RMS 偏低想試別條：`STT_ASR_CHANNEL` / `STT_CAPTURE_CHANNELS` env 可 A/B，不動碼。

> 口頭提醒使用者順手清 `.bashrc` 內重複的 3 行 `export STT_ARECORD_DEVICE`（保留一行 `plughw:CARD=ArrayUAC10` 即可）——非本 spec code 範圍。

---

## Self-Review

**1. Spec coverage：** §2.2 env 常數→Step 3 ✓；§2.3 反交錯 read/_readexact→Step 4 ✓；§2.4 工廠 -c/回傳→Step 5 ✓；§6 測試（反交錯/直通/EOF/工廠 -c 6/device 注入）→Step 1 ✓；不動 keyterm/語言/連線→Files 僅 stt.py 收音層 + 該測試 ✓。
**2. Placeholder scan：** 每 step 確切 code + 指令 + 預期；pytest 啟動器差異（py -3.14）已註明，非 placeholder。
**3. Type consistency：** `_ArecordSource(proc, channels, ch_index)` 簽名（Step 4 定義 ↔ Step 5 工廠呼叫 ↔ Step 1 測試建構）一致；`_CAPTURE_CHANNELS`/`_ASR_CHANNEL`（Step 3 定義 ↔ Step 5 使用）一致；`read(n)` 回單聲道 bytes 契約（Step 4 ↔ 既有 `_send_loop` 消費）不變。
