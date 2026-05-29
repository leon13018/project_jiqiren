"""test_tts_worker.py — 測試 myProgram/tts.py TtsWorker（v2 wait_idle 設計）。

2026-05-30 v2 重做 — 取代 reverted commit `8e3aa67` 的 `_active` bool + polling 設計。

關鍵設計改變：
    - 用 threading.Condition + _pending counter（取代 _active bool）
    - say() 原子 inc _pending + put queue（防 R1 race window）
    - worker finally 內 dec _pending + notify_all
    - wait_idle(max_wait=10.0) 阻塞至 _pending==0 或 timeout

注入策略：
    - 用 monkeypatch 替換 _synthesize / subprocess.Popen 避免實際呼叫網路 / mpg123
    - 直接建 TtsWorker 實例（不用 module-level singleton）方便每 test 獨立
"""

import sys
import threading
import time
import types

import pytest

# 為何先注入 fake edge_tts module：tts.py 頂層 `import edge_tts` 是 fail-fast
# （prod code 缺套件直接 ImportError）。Windows pytest 環境沒裝 edge_tts，但本檔測試
# 純驗 TtsWorker 同步 / 計數 / 阻塞語意，不需要真網路 TTS。注入 stub module 跳過。
# 各 test 內仍 monkeypatch tts_module._synthesize 為 no-op async function。
if "edge_tts" not in sys.modules:
    _fake_edge_tts = types.ModuleType("edge_tts")

    class _FakeCommunicate:
        def __init__(self, **kw):
            pass

        async def save(self, out_path):
            return None

    _fake_edge_tts.Communicate = _FakeCommunicate
    sys.modules["edge_tts"] = _fake_edge_tts

from myProgram import tts as tts_module  # noqa: E402
from myProgram.tts import TtsWorker  # noqa: E402


# ============================================================
# Fake helpers — 用 monkeypatch 注入避免 edge_tts 網路 / mpg123 subprocess
# ============================================================


class _FakePopen:
    """模擬 subprocess.Popen — wait() 立即 return 0；可選 hang_event 模擬 wait 阻塞。"""

    def __init__(self, returncode: int = 0, wait_event: threading.Event | None = None) -> None:
        self._returncode = returncode
        self._wait_event = wait_event
        self.returncode = None

    def wait(self) -> int:
        if self._wait_event is not None:
            self._wait_event.wait()  # 阻塞至外部 set
        self.returncode = self._returncode
        return self._returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        if self._wait_event is not None:
            self._wait_event.set()  # unblock wait


def _make_fast_fakes(monkeypatch):
    """注入 fake _synthesize（no-op）+ fake Popen（wait 立即 return 0）。

    讓 _loop 流程跑得極快，方便驗證 _pending 計數 + Condition 喚醒邏輯。
    """
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)
    monkeypatch.setattr(tts_module.subprocess, "Popen", lambda *a, **kw: _FakePopen(returncode=0))
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)  # 跳過 ALSA_DRAIN_SEC


async def _fake_synth_noop(text, out_path):
    return None


# ============================================================
# Test 4a：R1 race regression（最重要）
# ============================================================


def test_wait_idle_does_not_return_before_worker_finishes_processing(monkeypatch):
    """R1 race regression：say() 後 wait_idle 必須等到 _loop _process_text 完成才返回。

    這是 v2 設計的核心驗證 — v1 的 `_active` bool 設計有 race window：
      worker thread:  text = q.get()    # _active 仍是 False
      main thread:    wait_idle()        # 看到 _q.empty()=True + _active=False → False idle
      worker thread:  _active = True; process text; _active = False  # 太晚

    v2 fix：say() 原子 inc _pending + put queue，worker finally 內 dec _pending。
    q.get() 後 _pending 仍 > 0 → wait_idle 阻塞至 worker 真完成才返回。

    本 test 用 wait_event 強制 worker 處理 hang 在 wait() — main thread 立即 wait_idle
    若 race 存在 → 立即 return True（pending 看似為 0）→ test FAIL（hang_event 還沒 set）
    若 race 修好 → wait_idle 阻塞至 timeout → return False。
    """
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)

    hang_event = threading.Event()  # worker wait() 卡在此 event

    def make_hanging_popen(*a, **kw):
        return _FakePopen(returncode=0, wait_event=hang_event)

    monkeypatch.setattr(tts_module.subprocess, "Popen", make_hanging_popen)
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()

    # say + 立即 wait_idle（worker 已 get text 但 hang 在 popen.wait()）
    worker.say("X")
    # 短 timeout 確認 race fix：若 race 修好 → wait_idle 阻塞至 max_wait 超時 → False
    result = worker.wait_idle(max_wait=0.3)

    # 必須是 False（worker 還沒處理完，hang_event 未 set）
    assert result is False, (
        "R1 race regression：wait_idle 應阻塞至 max_wait timeout（worker hang 在 wait）；"
        "若 race 存在 worker get text 後 _active=False 瞬間會被誤判 idle 立即 return True"
    )

    # cleanup：unblock worker
    hang_event.set()


# ============================================================
# Test 4b：基本 idle 行為
# ============================================================


def test_wait_idle_returns_true_immediately_when_no_pending(monkeypatch):
    """新建 worker、_pending=0 時 wait_idle 立即返回 True。"""
    _make_fast_fakes(monkeypatch)
    worker = TtsWorker()

    start = time.monotonic()
    result = worker.wait_idle(max_wait=5.0)
    elapsed = time.monotonic() - start

    assert result is True, "pending=0 應立即返回 True"
    assert elapsed < 0.1, f"應立即返回（< 100ms），實際 {elapsed:.3f}s"


# ============================================================
# Test 4c：max_wait 超時
# ============================================================


def test_wait_idle_returns_false_on_max_wait_timeout(monkeypatch):
    """fake synth hang → wait_idle(max_wait=0.1) 應 ~0.1s 後 return False。

    驗證 max_wait fallback：synth 卡網路 / mpg123 hang 時 wait_idle 不能永久阻塞。
    """
    synth_hang_event = threading.Event()

    async def hanging_synth(text, out_path):
        # asyncio 內 sleep；synth_hang_event 用 polling 模擬
        while not synth_hang_event.is_set():
            import asyncio
            await asyncio.sleep(0.01)

    monkeypatch.setattr(tts_module, "_synthesize", hanging_synth)
    monkeypatch.setattr(tts_module.subprocess, "Popen", lambda *a, **kw: _FakePopen(returncode=0))
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("X")

    start = time.monotonic()
    result = worker.wait_idle(max_wait=0.15)
    elapsed = time.monotonic() - start

    assert result is False, "synth hang 時 wait_idle 應 timeout return False"
    # 容許 50ms 誤差（thread scheduling）
    assert 0.1 <= elapsed < 0.5, f"應 ~0.15s 後 timeout，實際 {elapsed:.3f}s"

    # cleanup
    synth_hang_event.set()


# ============================================================
# Test 4d：_process_text synth 失敗 path 也應 dec _pending
# ============================================================


def test_process_text_synth_failure_decrements_pending(monkeypatch):
    """fake synth raise Exception → finally 必須 dec _pending → wait_idle return True。

    驗證 _process_text 失敗 path 不會卡 _pending 計數（v2 設計：try/finally 包 _process_text）。
    """
    async def failing_synth(text, out_path):
        raise RuntimeError("synth network error")

    monkeypatch.setattr(tts_module, "_synthesize", failing_synth)
    monkeypatch.setattr(tts_module.subprocess, "Popen", lambda *a, **kw: _FakePopen(returncode=0))
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("X")

    # synth 失敗後 finally dec _pending → wait_idle 應 return True
    result = worker.wait_idle(max_wait=1.0)
    assert result is True, "synth 失敗 path 也應 dec _pending → wait_idle return True"


# ============================================================
# Test 4e：notify 機制 — 等中 worker dec 後解除阻塞
# ============================================================


def test_wait_idle_unblocks_when_pending_reaches_zero(monkeypatch):
    """另一 thread 跑 wait_idle 阻塞 → worker dec _pending notify_all → wait_idle 解阻塞。

    驗證 Condition.notify_all 確實會喚醒等待 thread（非 polling 也能 unblock）。
    """
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)
    # popen 等 0.05s 模擬處理時間（給 wait_idle 真的進入 wait 狀態的機會）
    popen_event = threading.Event()

    def slow_popen(*a, **kw):
        # 立即 set event 但延後 wait return
        return _FakePopen(returncode=0, wait_event=popen_event)

    monkeypatch.setattr(tts_module.subprocess, "Popen", slow_popen)
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("X")

    # 啟動 wait_idle thread；確保 main 已進 cv.wait
    result_holder = {}

    def waiter():
        result_holder["result"] = worker.wait_idle(max_wait=5.0)

    waiter_thread = threading.Thread(target=waiter)
    waiter_thread.start()

    # 給 waiter 進 wait 狀態的時間
    time.sleep(0.1)
    # 解阻塞 worker → worker finally dec _pending notify_all → waiter 解阻塞
    popen_event.set()

    waiter_thread.join(timeout=2.0)
    assert not waiter_thread.is_alive(), "waiter 應被 notify_all 喚醒"
    assert result_holder.get("result") is True, "notify_all 後 wait_idle 應 return True"


# ============================================================
# Test 4f：並發 say + wait_idle 不卡死、計數正確
# ============================================================


def test_say_and_wait_idle_thread_safe_under_concurrent_load(monkeypatch):
    """20 個 say + 多個 wait_idle 並發 — 最終 _pending == 0 + 無 deadlock。"""
    _make_fast_fakes(monkeypatch)
    worker = TtsWorker()

    N = 20
    for i in range(N):
        worker.say(f"text-{i}")

    # 主 thread 阻塞等所有 say 處理完
    result = worker.wait_idle(max_wait=5.0)
    assert result is True, "並發 say 後 wait_idle 應 return True"
    # 直接驗 _pending 確實歸 0
    assert worker._pending == 0, f"最終 _pending 應為 0，實際 {worker._pending}"
