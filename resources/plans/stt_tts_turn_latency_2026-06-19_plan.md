# STT/TTS turn-boundary 即時化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 縮短顧客 turn boundary 的死時間（條件式 ALSA drain 省 ~0.3s/回合）並埋入可量測 / 可調的旋鈕（計時 log + endpointing env），行為預設不變。

**Architecture:** 三個獨立小元件，全落 `myProgram/stt.py` + `myProgram/tts.py`。endpointing 改 env 旋鈕（builder fn 可測）；計時 log 由 `STT_TTS_TIMING` env 閘門（預設靜默）；ALSA drain 改成只在 queue 還有下一句時才睡。

**Tech Stack:** Python 3.11（Pi runtime）；Windows pytest（`py -3.14 -m pytest tests/`）；無新依賴。

## Global Constraints

- **繁體中文**：所有新增註解 / 字串 / commit message 繁中。
- **行為預設不變**：`STT_TTS_TIMING` 與 `STT_ENDPOINTING_MS` 兩 env 未設時，全系統行為與現狀逐位元相同。文案 / 狀態轉換 / 計時秒數 / 連發句之間的 drain 一律不動。
- **endpointing 預設 300**（未設 env → URL 含 `endpointing=300`，與原硬編相同）；**不**預設改 200。
- **計時 log 不預設開**（`STT_TTS_TIMING` 未設 → 零新增輸出）。
- **不用 `git add -A` / `git add .`**：每個 commit 明列檔名。
- **worktree**：本 plan 全在 worktree `worktree-stt-tts-latency` 內實作；上一 commit 是 spec/plan doc（不要改）。每 commit 後 `git branch --contains <SHA>` 自驗落 `worktree-*`。
- **µs race 不加鎖**（元件 1）：YAGNI，機率可忽略。

---

## Task 1: stt.py — endpointing env 旋鈕（builder fn）

**Files:**
- Modify: `myProgram/stt.py:48-55`（`DEEPGRAM_URL` 區塊）
- Test: `tests/stt/test_keyterm.py`

**Interfaces:**
- Produces: `_build_deepgram_url(endpointing_ms: int) -> str`（組 URL，endpointing 由參數帶入）；`_ENDPOINTING_MS: int`（模組級，讀 env 預設 300）；`DEEPGRAM_URL: str`（= `_build_deepgram_url(_ENDPOINTING_MS)`，對外不變）。

- [ ] **Step 1: 寫 failing test**

在 `tests/stt/test_keyterm.py` 末尾加（並在頂部 import 補 `_build_deepgram_url`）：
```python
from myProgram.stt import DEEPGRAM_URL, KEYTERMS, _build_deepgram_url  # noqa: 既有 import 改這行


def test_endpointing_default_300_in_built_url():
    assert "endpointing=300" in _build_deepgram_url(300)


def test_endpointing_override_reflected_in_built_url():
    url = _build_deepgram_url(200)
    assert "endpointing=200" in url
    assert "endpointing=300" not in url


def test_built_url_still_carries_keyterms_and_base_params():
    url = _build_deepgram_url(250)
    assert "model=nova-3" in url and "language=zh-TW" in url
    assert "keyterm=" in url  # keyterm append 未被破壞
```

- [ ] **Step 2: 跑測試見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_keyterm.py -q`
Expected: FAIL（`ImportError: cannot import name '_build_deepgram_url'`）。

- [ ] **Step 3: 實作 builder fn**

把 `myProgram/stt.py` 的：
```python
# Deepgram 串流端點（統領設計 §2.5 既定參數；Pi 首測若 handshake 400 → 改試
# language=zh-Hant 並回寫 spec §2.3）。keyterm 在固定參數後 append（percent-encoded）。
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000"
    "&channels=1&interim_results=true&endpointing=300&smart_format=false"
    + "".join(f"&keyterm={quote(_kt)}" for _kt in KEYTERMS)
)
```
改為：
```python
# endpointing 毫秒：env 旋鈕（未設 = 300，與原硬編逐字元相同）。Pi 設
# STT_ENDPOINTING_MS=200 可 A/B「顧客講完 → speech_final」速度，不動碼。
_ENDPOINTING_MS = int(os.environ.get("STT_ENDPOINTING_MS", "300"))


def _build_deepgram_url(endpointing_ms: int) -> str:
    """組 Deepgram 串流 URL；endpointing 由參數帶入，其餘參數固定。keyterm 在固定
    參數後 append（percent-encoded）。統領設計 §2.5 既定參數；Pi 首測若 handshake
    400 → 改試 language=zh-Hant 並回寫 spec §2.3。"""
    return (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000"
        f"&channels=1&interim_results=true&endpointing={endpointing_ms}&smart_format=false"
        + "".join(f"&keyterm={quote(_kt)}" for _kt in KEYTERMS)
    )


DEEPGRAM_URL = _build_deepgram_url(_ENDPOINTING_MS)
```

- [ ] **Step 4: 跑測試見 PASS**

Run: `py -3.14 -m pytest tests/stt/test_keyterm.py -q`
Expected: PASS（含既有 `test_base_params_preserved` 的 `endpointing=300` 斷言——未設 env 預設 300）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/stt.py tests/stt/test_keyterm.py
git commit -m "feat(stt): endpointing 改 STT_ENDPOINTING_MS env 旋鈕（預設 300，Pi 可 A/B 200）"
git branch --contains HEAD
```

---

## Task 2: stt.py — 選用式計時 log（env-gated）

**Files:**
- Modify: `myProgram/stt.py`（頂部 `import time`；`_timing` helper；`SttWorker.__init__` / `arm` / `_receive_loop`）
- Test: `tests/stt/test_worker.py`

**Interfaces:**
- Produces: `_timing(msg: str) -> None`（`STT_TTS_TIMING` 設了才 `print(f"[計時] {msg}")`）；`SttWorker._armed_at: float`（arm 時記 monotonic）。

- [ ] **Step 1: 寫 failing test**

在 `tests/stt/test_worker.py` 末尾加：
```python
def test_timing_log_emitted_on_speech_final_when_env_set(monkeypatch, capsys):
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    worker, ws, calls = _make_worker([
        _results("好", speech_final=True),
    ])
    worker.arm()
    assert wait_until(lambda: calls == ["好"])
    worker.disarm()
    out = capsys.readouterr().out
    assert "[計時]" in out and "開麥後" in out


def test_timing_log_silent_when_env_unset(monkeypatch, capsys):
    monkeypatch.delenv("STT_TTS_TIMING", raising=False)
    worker, ws, calls = _make_worker([
        _results("好", speech_final=True),
    ])
    worker.arm()
    assert wait_until(lambda: calls == ["好"])
    worker.disarm()
    assert "[計時]" not in capsys.readouterr().out
```

- [ ] **Step 2: 跑測試見 FAIL**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -q`
Expected: FAIL（`test_timing_log_emitted...` 因無 `[計時]` 輸出而 AssertionError）。

- [ ] **Step 3: 實作**

(a) `myProgram/stt.py` 頂部 import 段加 `import time`（與既有 `import os` 等並列）。

(b) 在 `_normalize_transcript` 之後（module-level）加 helper：
```python
def _timing(msg: str) -> None:
    """STT_TTS_TIMING 設了才印計時行（量測用，預設靜默；可隨時移除）。"""
    if os.environ.get("STT_TTS_TIMING"):
        print(f"[計時] {msg}")
```

(c) `SttWorker.__init__` 末尾加一行（避免 _receive_loop 先讀到未設的 attr）：
```python
        self._armed_at = 0.0      # arm 時記 monotonic（計時 log 用）
```

(d) `arm()` 內 `self._session = (...)` 那行之前（仍持 `_lock`、threads 尚未 start）加：
```python
            self._armed_at = time.monotonic()
```

(e) `_receive_loop` 注入處（`if text:` 區塊）：
```python
                if text:
                    print(f"[語音辨識] {text}")
                    _timing(f"開麥後 {time.monotonic() - self._armed_at:.2f}s 出辨識結果")
                    self._sink(text)
```

- [ ] **Step 4: 跑測試見 PASS**

Run: `py -3.14 -m pytest tests/stt/test_worker.py -q`
Expected: PASS（新增兩 test + 既有全綠）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/stt.py tests/stt/test_worker.py
git commit -m "feat(stt): STT_TTS_TIMING 計時 log（開麥→辨識結果 delta，env 閘門預設靜默）"
git branch --contains HEAD
```

---

## Task 3: tts.py — 條件式 ALSA drain（真正的提速）

**Files:**
- Modify: `myProgram/tts.py:319-327`（`_process` 結尾 drain）
- Test: `tests/sales/test_tts_worker.py`

**Interfaces:**
- Consumes（既有）：`self._peek_next()`（偷看 queue 下一筆，None = 即將 idle）、`ALSA_DRAIN_SEC`、`tts_module.time.sleep`。
- 行為：播放成功後，僅 `_peek_next() is not None`（還有下一句要播同一播放裝置）才 `time.sleep(ALSA_DRAIN_SEC)`；idle → 跳過。

- [ ] **Step 1: 寫 failing test**

在 `tests/sales/test_tts_worker.py` 末尾加：
```python
def test_drain_skipped_when_going_idle(monkeypatch):
    """單句播完、queue 空（即將 idle）→ 不 drain（省 turn boundary ~0.3s）。"""
    sleeps = []
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)
    monkeypatch.setattr(tts_module.subprocess, "Popen", lambda *a, **kw: _FakePopen(returncode=0))
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: sleeps.append(s))

    worker = TtsWorker()
    worker.say("只有一句")
    assert worker.wait_idle(max_wait=5.0)
    assert tts_module.ALSA_DRAIN_SEC not in sleeps, "idle 時不應 drain"


def test_drain_kept_when_next_utterance_queued(monkeypatch):
    """第一句播放期間第二句已排隊 → 第一句播完應 drain（防截尾，行為不變）。"""
    sleeps = []
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)
    hang = threading.Event()  # 第一句 wait() 卡住，給時間 queue 第二句

    popens = []
    def make_popen(*a, **kw):
        # 第一個 Popen hang 在 wait；其後立即 return
        p = _FakePopen(returncode=0, wait_event=hang if not popens else None)
        popens.append(p)
        return p
    monkeypatch.setattr(tts_module.subprocess, "Popen", make_popen)
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: sleeps.append(s))

    worker = TtsWorker()
    worker.say("第一句")
    assert wait_until(lambda: len(popens) == 1)   # 第一句已進 wait()
    worker.say("第二句")                          # 排隊（第一句 _peek_next 將見到它）
    hang.set()                                    # 放行第一句 wait()
    assert worker.wait_idle(max_wait=5.0)
    assert tts_module.ALSA_DRAIN_SEC in sleeps, "有下一句時應 drain（防截尾）"
```

> 註：`wait_until` 需從測試既有 import 取得；若 `test_tts_worker.py` 尚未 import，於檔頂加
> `from tests.stt.conftest import wait_until`（既有跨模組 polling helper）或就地寫一個
> 簡單 polling（`for _ in range(500): if cond(): break; time.sleep(0.005)`）。實作者擇一，
> 與既有風格一致即可。

- [ ] **Step 2: 跑測試見 FAIL**

Run: `py -3.14 -m pytest tests/sales/test_tts_worker.py -q`
Expected: FAIL（`test_drain_skipped_when_going_idle`——現狀無條件 drain，`ALSA_DRAIN_SEC in sleeps`）。

- [ ] **Step 3: 實作條件式 drain**

把 `myProgram/tts.py` `_process` 結尾：
```python
        # 播放成功（returncode==0）：drain ALSA
        # 給 ALSA buffer 完成尾巴音訊播放的時間，避免下一個 speak() 立刻啟動
        # 新 mpg123 沖掉舊 buffer（症狀：「付款成功」尾巴被截）。失敗 path
        # 不到這裡因 mpg123 沒真播完 = 無 buffer 殘留 = 不需 drain。
        time.sleep(ALSA_DRAIN_SEC)
```
改為：
```python
        # 播放成功（returncode==0）：僅在 queue 還有下一句要播時 drain ALSA。
        # drain 防的是「下一個 mpg123 開同一播放裝置沖掉舊 buffer 截尾」；worker 即將
        # idle（_peek_next 為 None）→ 無下一個 mpg123 → 跳過 drain，省 turn boundary
        # ~0.3s（playback→listen 轉場；喇叭=板載、麥=USB 不同裝置，arecord 開 capture
        # 不會沖播放 buffer，尾巴自然播完）。連發句之間照舊 drain（防截尾，行為不變）。
        # 失敗 path 不到這裡因 mpg123 沒真播完 = 無 buffer 殘留 = 不需 drain。
        if self._peek_next() is not None:
            time.sleep(ALSA_DRAIN_SEC)
```

- [ ] **Step 4: 跑測試見 PASS**

Run: `py -3.14 -m pytest tests/sales/test_tts_worker.py -q`
Expected: PASS（新增兩 test + 既有全綠——既有 test 多以 no-op sleep 注入，不受影響）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/tts.py tests/sales/test_tts_worker.py
git commit -m "perf(tts): 條件式 ALSA drain — idle 時跳過 0.3s 尾巴 sleep（省 turn boundary）"
git branch --contains HEAD
```

---

## Task 4: tts.py — 選用式計時 log（env-gated）

**Files:**
- Modify: `myProgram/tts.py`（`_timing` helper；`_process` 內計時點）
- Test: `tests/sales/test_tts_worker.py`

**Interfaces:**
- Produces: `_timing(msg: str) -> None`（`STT_TTS_TIMING` 設了才 `print(f"[計時] {msg}")`）。
- `_process` 成功 path 末尾印一行：來源（cache 命中 / prefetch / 現場合成）＋ play 時長 ＋ drain on/off（＋ 現場合成時的 synth 時長）。

- [ ] **Step 1: 寫 failing test**

在 `tests/sales/test_tts_worker.py` 末尾加：
```python
def test_tts_timing_log_emitted_when_env_set(monkeypatch, capsys):
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    _make_fast_fakes(monkeypatch)
    worker = TtsWorker()
    worker.say("計時測試句")
    assert worker.wait_idle(max_wait=5.0)
    out = capsys.readouterr().out
    assert "[計時]" in out and "play=" in out


def test_tts_timing_log_silent_when_env_unset(monkeypatch, capsys):
    monkeypatch.delenv("STT_TTS_TIMING", raising=False)
    _make_fast_fakes(monkeypatch)
    worker = TtsWorker()
    worker.say("計時測試句")
    assert worker.wait_idle(max_wait=5.0)
    assert "[計時]" not in capsys.readouterr().out
```

- [ ] **Step 2: 跑測試見 FAIL**

Run: `py -3.14 -m pytest tests/sales/test_tts_worker.py -q`
Expected: FAIL（`test_tts_timing_log_emitted...` 無 `[計時]` 輸出）。

- [ ] **Step 3: 實作**

(a) 在 `myProgram/tts.py` `_print_failure` 之後（module-level）加 helper：
```python
def _timing(msg: str) -> None:
    """STT_TTS_TIMING 設了才印計時行（量測用，預設靜默；可隨時移除）。
    與 stt.py 同名 helper 各自內聯——兩模組無共享依賴，2 行不抽 util（YAGNI）。"""
    if os.environ.get("STT_TTS_TIMING"):
        print(f"[語音][計時] {msg}")
```

(b) `_process` 階段 1 三層 fallback 各標 `source`，並量 synth 時長：
- prefetch 命中分支：`source = "prefetch"`
- 內容定址快取命中分支：`source = "cache"`
- 現場合成分支：`source = "synth"`，且把
  ```python
                self._loop_obj.run_until_complete(_synthesize(text, tmp_path))
  ```
  包成計時：
  ```python
                _synth_t0 = time.monotonic()
                self._loop_obj.run_until_complete(_synthesize(text, tmp_path))
                _synth_ms = (time.monotonic() - _synth_t0) * 1000
  ```
  （prefetch / cache 分支設 `_synth_ms = 0.0`，在分支前先 `_synth_ms = 0.0` 預設值）

(c) 階段 2 量 play 時長：在 `returncode = self._proc.wait()` 前後夾 monotonic：
```python
            _play_t0 = time.monotonic()
            returncode = self._proc.wait()
            _play_ms = (time.monotonic() - _play_t0) * 1000
```

(d) drain 區塊改成記錄 `drained` 並在成功 path 末尾印計時行：
```python
        drained = self._peek_next() is not None
        if drained:
            time.sleep(ALSA_DRAIN_SEC)
        _timing(f"{text!r} 來源={source} play={_play_ms:.0f}ms"
                + (f" synth={_synth_ms:.0f}ms" if source == "synth" else "")
                + f" drain={'on' if drained else 'off'}")
```

> 註：Task 3 已把 drain 改條件式；本 Task 在其上加 `drained` 變數 + 計時行。實作者直接
> 在 Task 3 結果上演進（drain 邏輯不變，只多記一個 bool 供 log）。`source` / `_synth_ms` /
> `_play_ms` 皆 _process 區域變數，不新增 instance 狀態、不新增鎖。

- [ ] **Step 4: 跑測試見 PASS**

Run: `py -3.14 -m pytest tests/sales/test_tts_worker.py -q`
Expected: PASS（新增兩 test + 既有全綠）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/tts.py tests/sales/test_tts_worker.py
git commit -m "feat(tts): STT_TTS_TIMING 計時 log（來源/play/synth/drain，env 閘門預設靜默）"
git branch --contains HEAD
```

---

## 收尾驗證（主 agent，非 sales-coder）

- **Iron Law**：`py -3.14 -m pytest tests/ -q` 全綠（baseline 649 + 新增 8 test）。
- **三段 reviewer**：spec-reviewer → code-quality-reviewer（worker 檔改動，照跑）。
- **docs（resources/，主 agent 收尾）**：`raspberry_pi_setup.md` 加兩 env 變數說明；新增 `pineedtodo` 記 Pi 驗證點（drain 自我回授實測 / endpointing A/B / 計時 log 跑一輪）。
- **worktree closeout**：merge --ff-only → push → 清 worktree。

---

## Self-Review

**1. Spec coverage：**
- spec 元件 1（條件式 drain）→ Task 3 ✓；元件 2（計時 log）→ Task 2（stt）+ Task 4（tts）✓；元件 3（endpointing env）→ Task 1 ✓。
- spec「行為預設不變」→ Global Constraints + 各 Task default 300 / env 未設靜默 ✓。
- spec「測試 Windows 全可跑」→ 各 Task pytest 指令 ✓；spec「Iron Law baseline 649」→ 收尾段 ✓。
- spec「風險 / Pi 驗證點 pineedtodo」→ 收尾段 ✓。

**2. Placeholder scan：** 無 TBD/TODO；prod 與 test code 均完整給出（含改前/改後）。

**3. Type consistency：** `_build_deepgram_url(int)->str`、`_timing(str)->None`、`_armed_at: float`、`drained: bool`、`source: str`、`_synth_ms`/`_play_ms: float` 全程一致；`_timing` 在 stt 印 `[計時]`、tts 印 `[語音][計時]`（前綴差異刻意——對齊各模組既有 log 前綴 `[語音辨識]` / `[語音]`，測試只斷言 `[計時]` 子字串故兩者皆過）。
