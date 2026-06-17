# STT 互動延遲診斷計時 instrumentation plan

> Spec:`resources/specs/stt_timing_debug_2026-06-17_spec.md`(WHAT)。本檔 = HOW。
> **純診斷,additive,env-gated**(`STT_DEBUG_TIMING` 未設→零輸出零行為改變)。無新測試(無行為可斷言);既有 625 須仍綠。
> 測試指令:`py -m pytest tests/stt/ tests/sales/`(本機 `python` 沒裝 pytest)。

---

## Task 1:main.py + tts.py 加 env-gated `[計時]` log

**Files**:Modify `myProgram/main.py`(加 `import os` + `read_customer_input` 3 處計時);Modify `myProgram/tts.py`(`_process` 1 處計時)

### Step 1:main.py 加 `import os`

把(line 22-24):
```python
import math
import sys
import time
```
替換為:
```python
import math
import os
import sys
import time
```

### Step 2:main.py `read_customer_input` 加 3 處計時

把現有這段(prewarm + wait_idle):
```python
        from myProgram import stt
        # STT prewarm（v2 式來源端閘）：進場先在 prompt 播放期背景預連 Deepgram ws +
        # KeepAlive 維持、**不開麥不送音訊**（機器人聲不進辨識）→ wait_idle 播完後 arm
        # 才開麥，省掉 ws 握手延遲、且無自我回授。
        stt.prewarm()
        from myProgram import tts
        tts.wait_idle()
        from myProgram import input_reader
```
替換為(加 `_dbg` + prewarm/wait_idle 兩計時):
```python
        from myProgram import stt
        # STT prewarm（v2 式來源端閘）：進場先在 prompt 播放期背景預連 Deepgram ws +
        # KeepAlive 維持、**不開麥不送音訊**（機器人聲不進辨識）→ wait_idle 播完後 arm
        # 才開麥，省掉 ws 握手延遲、且無自我回授。
        # STT_DEBUG_TIMING=1 → 印 [計時] log 定位互動延遲卡段（預設關，demo 乾淨）。
        _dbg = os.environ.get("STT_DEBUG_TIMING")
        _t = time.monotonic()
        stt.prewarm()
        if _dbg:
            print(f"[計時] prewarm {time.monotonic() - _t:.2f}s（ws 連線）")
        from myProgram import tts
        _t = time.monotonic()
        tts.wait_idle()
        if _dbg:
            print(f"[計時] wait_idle {time.monotonic() - _t:.2f}s（TTS 合成+播放+drain）")
        from myProgram import input_reader
```

把現有這段(arm + try/finally):
```python
        # TTS 播完才 arm 開麥（連線已於 prewarm 預熱，省握手；arm 冪等、缺 key 自動停用走純鍵盤）。
        # finally 保證三條路徑（拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        stt.arm()
        try:
            if timeout is None or timeout <= 0:
                raw = input_reader.read(timeout)
            else:
                raw = _tick_countdown(timeout, "timeout", input_reader.read)
        finally:
            stt.disarm()
```
替換為(arm 後記時間 + try/finally 後印 arm→輸入):
```python
        # TTS 播完才 arm 開麥（連線已於 prewarm 預熱，省握手；arm 冪等、缺 key 自動停用走純鍵盤）。
        # finally 保證三條路徑（拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        stt.arm()
        _t = time.monotonic()
        try:
            if timeout is None or timeout <= 0:
                raw = input_reader.read(timeout)
            else:
                raw = _tick_countdown(timeout, "timeout", input_reader.read)
        finally:
            stt.disarm()
        if _dbg:
            print(f"[計時] arm→輸入 {time.monotonic() - _t:.2f}s（你開口+Deepgram 辨識）")
```

### Step 3:tts.py `_process` 加總耗時 + 快取/合成標記計時

3a. 在 `_process` 方法**最開頭**(docstring 之後、`cache_path = _cache_path_for(text)` 之前)插入:
```python
        _dbg = os.environ.get("STT_DEBUG_TIMING")
        _t0 = time.monotonic()
        _synthed = False
```

3b. 在合成分支(現有 `else:` 區塊內,`tmp_path = cache_path + ".tmp"` 之前)標記合成:
把:
```python
        else:
            # 防禦：FIFO 單消費者下 prefetch 內容必等於下一句，mismatch 理論不可達；
            # 若出現（未來改動引入）丟棄重合成即可，行為仍正確
            self._prefetched = None
            tmp_path = cache_path + ".tmp"
```
替換為:
```python
        else:
            # 防禦：FIFO 單消費者下 prefetch 內容必等於下一句，mismatch 理論不可達；
            # 若出現（未來改動引入）丟棄重合成即可，行為仍正確
            self._prefetched = None
            _synthed = True
            tmp_path = cache_path + ".tmp"
```

3c. 在成功播放路徑的 `finally` 區塊之後、`time.sleep(ALSA_DRAIN_SEC)` 之前印計時:
把:
```python
        finally:
            with self._lock:
                self._proc = None

        # 播放成功（returncode==0）：drain ALSA
```
替換為:
```python
        finally:
            with self._lock:
                self._proc = None

        if _dbg:
            print(f"[計時] TTS {text[:8]!r}: {'合成' if _synthed else '快取'} 共 {time.monotonic() - _t0:.2f}s")
        # 播放成功（returncode==0）：drain ALSA
```

- [ ] **Step 4:跑全回歸（旗號未設 → 行為不變）**
Run:`py -m pytest tests/stt/ tests/sales/`
Expected:**625 passed**（instrumentation env-gated,測試未設旗號 → 零行為差異）。

- [ ] **Step 5:commit**
```bash
git add myProgram/tts.py myProgram/main.py
git commit -m "feat(stt): env-gated [計時] 診斷 log（定位互動延遲卡段）"
git branch --contains $(git rev-parse HEAD)   # 自驗落 worktree-stt-timing-debug
```

---

## 完成檢查（主 agent Iron Law）
- `py -m pytest tests/stt/ tests/sales/` → `625 passed`。
- `git branch --contains <SHA>` → `worktree-stt-timing-debug`。
- grep `STT_DEBUG_TIMING`:main.py ≥1、tts.py ≥1;`[計時]` 出現 4 處（prewarm/wait_idle/arm→輸入/TTS）。
- 確認所有 print 都在 `if _dbg:`（或等效）守衛下——未設旗號零輸出。
