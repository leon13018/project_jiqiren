"""test_tts_worker.py — 測試 myProgram/tts.py TtsWorker（v2 wait_idle 設計）。

2026-05-30 v2 重做 — 取代 reverted commit `8e3aa67` 的 `_active` bool + polling 設計。

關鍵設計改變：
    - 用 threading.Condition + _pending counter（取代 _active bool）
    - say() 原子 inc _pending + put queue（防 R1 race window）
    - worker finally 內 dec _pending + notify_all
    - wait_idle(max_wait=30.0) 阻塞至 _pending==0 或 timeout

注入策略：
    - 用 monkeypatch 替換 _synthesize / subprocess.Popen 避免實際呼叫網路 / mpg123
    - 直接建 TtsWorker 實例（不用 module-level singleton）方便每 test 獨立
"""

import os
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

from tests.stt.conftest import wait_until  # noqa: E402  跨模組 polling helper（既有）

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

    # cleanup：unblock worker + drain "X"（等 pending==0）才結束本 test。
    # 必須 drain：worker 是 daemon thread；若 "X" 還沒被消費就結束、monkeypatch 一 revert，
    # 殘留 worker 會在「後續 test 已把全域 tts_module._synthesize 換成自己的」之後才合成
    # "X" → 用到對方的 patch、污染對方的 synth_calls（曾使 test_prefetch_synthesizes_*
    # 在重載並發下偶見 ['X','A','B']）。wait_idle 保證 "X" 在本 test 的 _fake_synth_noop 下處理完。
    hang_event.set()
    assert worker.wait_idle(max_wait=5.0) is True, "worker 應在本 test 內把 'X' 處理完（防洩漏到後續 test）"


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


# ============================================================
# Test 7：default max_wait regression lock（2026-05-30 commit 7661f10）
# ============================================================


def test_wait_idle_default_max_wait_is_30_seconds():
    """v3 commit 7661f10：default max_wait 從 10s bump 30s。

    鎖死 default value — 下次改要同步更新此 test + docstring + inline comments。
    驗 3 處 default 一致：
      - TtsWorker.wait_idle method default
      - module-level wait_idle() 對外 API default
      - speak_and_wait() default
    """
    import inspect

    sig = inspect.signature(TtsWorker.wait_idle)
    assert sig.parameters["max_wait"].default == 30.0, (
        f"TtsWorker.wait_idle max_wait default should be 30.0, "
        f"got {sig.parameters['max_wait'].default}"
    )

    # 也檢查 module-level wait_idle 跟 speak_and_wait 的 default 一致
    sig_module = inspect.signature(tts_module.wait_idle)
    assert sig_module.parameters["max_wait"].default == 30.0, (
        f"module-level wait_idle max_wait default should be 30.0, "
        f"got {sig_module.parameters['max_wait'].default}"
    )

    sig_speak_wait = inspect.signature(tts_module.speak_and_wait)
    assert sig_speak_wait.parameters["max_wait"].default == 30.0, (
        f"speak_and_wait max_wait default should be 30.0, "
        f"got {sig_speak_wait.parameters['max_wait'].default}"
    )


# ============================================================
# is_idle：非阻塞瞬讀 _pending（hawk 輪播「上一句播完才起算間距」用）
# ============================================================


def test_is_idle_true_when_no_pending(monkeypatch):
    """新建 worker、_pending=0 時 is_idle() 立即返回 True。"""
    _make_fast_fakes(monkeypatch)
    worker = TtsWorker()

    assert worker.is_idle() is True, "pending=0 應回 True"


def test_is_idle_false_while_processing_and_returns_immediately(monkeypatch):
    """say + worker hang 在 popen.wait（處理中）→ is_idle() 回 False，且立即返回不阻塞。

    用 R1 regression 的 hang seam：say 後 worker get text 但卡在 popen.wait()，
    _pending 仍 > 0。is_idle 必須非阻塞瞬讀回 False（不像 wait_idle 會等到
    max_wait timeout）——立即性用 elapsed < 0.1s 斷言。
    """
    monkeypatch.setattr(tts_module, "_synthesize", _fake_synth_noop)

    hang_event = threading.Event()  # worker wait() 卡在此 event

    def make_hanging_popen(*a, **kw):
        return _FakePopen(returncode=0, wait_event=hang_event)

    monkeypatch.setattr(tts_module.subprocess, "Popen", make_hanging_popen)
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("X")
    # 等 worker 真的 inc _pending（say 已原子 inc，但保險等到 worker 卡進 wait）
    assert wait_until(lambda: worker._pending > 0), "worker 應有 pending 處理中"

    start = time.monotonic()
    result = worker.is_idle()
    elapsed = time.monotonic() - start

    assert result is False, "處理中（_pending > 0）is_idle 應回 False"
    assert elapsed < 0.1, (
        f"is_idle 應非阻塞立即返回（< 100ms），實際 {elapsed:.3f}s — "
        f"不可像 wait_idle 阻塞等 max_wait"
    )

    # cleanup：unblock worker + drain "X"（等 pending==0）才結束本 test。
    # 必須 drain：worker 是 daemon thread；若 "X" 還沒被消費就結束、monkeypatch 一 revert，
    # 殘留 worker 會在「後續 test 已把全域 tts_module._synthesize 換成自己的」之後才合成
    # "X" → 用到對方的 patch、污染對方的 synth_calls（曾使 test_prefetch_synthesizes_*
    # 在重載並發下偶見 ['X','A','B']）。wait_idle 保證 "X" 在本 test 的 _fake_synth_noop 下處理完。
    hang_event.set()
    assert worker.wait_idle(max_wait=5.0) is True, "worker 應在本 test 內把 'X' 處理完（防洩漏到後續 test）"


def test_module_level_is_idle_delegates_to_worker():
    """module-level is_idle() 委派 _worker.is_idle()（對外 API）。"""
    assert tts_module.is_idle() == tts_module._worker.is_idle()


# ============================================================
# perf_w2 F-4：1-deep prefetch（雙 buffer）
# ============================================================


def test_prefetch_synthesizes_next_during_playback(monkeypatch):
    """連發兩句：第一句播放期間（gated Popen 未釋放前）第二句應已被 prefetch 合成；
    全程結束後每句恰 synth 一次（prefetch 命中不重合成）。

    a_may_proceed 卡住 A 的 synth 直到 B 已入 queue——確保 prefetch peek 必看得到 B
    （消除 say 與 worker 消費之間的時序 race，測試確定性）。
    """
    synth_calls: list = []
    a_may_proceed = threading.Event()
    b_synthed = threading.Event()

    async def recording_synth(text, out_path):
        if text == "A":
            # 同步 Event 刻意阻塞整個 loop thread：gate 住 A 直到 B 入 queue（非 async bug）
            a_may_proceed.wait()
        synth_calls.append(text)
        if text == "B":
            b_synthed.set()

    release_play = threading.Event()
    monkeypatch.setattr(tts_module, "_synthesize", recording_synth)
    monkeypatch.setattr(
        tts_module.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(returncode=0, wait_event=release_play),
    )
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("A")
    worker.say("B")
    a_may_proceed.set()

    # A 播放被 gate 住（release_play 未 set）期間，B 應已被 prefetch 合成
    assert b_synthed.wait(timeout=2.0), (
        "B 應在 A 播放期間（release_play 未 set 前）被 prefetch 合成"
    )
    release_play.set()
    assert worker.wait_idle(max_wait=5.0) is True
    assert synth_calls == ["A", "B"], (
        f"每句恰合成一次（B 走 prefetch 命中、不重合成），實際 {synth_calls}"
    )


def test_prefetch_failure_falls_back_to_inline_synth(monkeypatch):
    """prefetch 失敗（B 首呼 raise）→ B 輪到自己的 _process 內重試成功；計數不卡。"""
    b_calls = {"n": 0}
    a_may_proceed = threading.Event()

    async def flaky_synth(text, out_path):
        if text == "A":
            # 同步 Event 刻意阻塞整個 loop thread：gate 住 A 直到 B 入 queue（非 async bug）
            a_may_proceed.wait()
        if text == "B":
            b_calls["n"] += 1
            if b_calls["n"] == 1:
                raise RuntimeError("prefetch 網路抖動")

    release_play = threading.Event()
    release_play.set()  # 播放不卡（重點在 synth 呼叫次數，非重疊時序）
    monkeypatch.setattr(tts_module, "_synthesize", flaky_synth)
    monkeypatch.setattr(
        tts_module.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(returncode=0, wait_event=release_play),
    )
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("A")
    worker.say("B")
    a_may_proceed.set()

    assert worker.wait_idle(max_wait=5.0) is True, "prefetch 失敗不得卡住 pipeline"
    assert b_calls["n"] == 2, (
        f"B 應 prefetch 失敗一次＋inline 重試一次，實際 {b_calls['n']} 次"
    )


def test_distinct_texts_synthesize_to_distinct_paths(monkeypatch):
    """相鄰兩次 synth 的 out_path 必不同（內容定址：異文字必異檔——防播放中的檔被覆寫）。
    此性質與 prefetch 是否命中無關，對任何時序皆成立（確定性斷言）。"""
    paths: list = []

    async def recording_synth(text, out_path):
        paths.append(out_path)

    monkeypatch.setattr(tts_module, "_synthesize", recording_synth)
    monkeypatch.setattr(
        tts_module.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(returncode=0),
    )
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    for t in ("A", "B", "C"):
        worker.say(t)

    assert worker.wait_idle(max_wait=5.0) is True
    assert len(paths) == 3, f"每句恰合成一次，實際 {paths}"
    for i in range(len(paths) - 1):
        assert paths[i] != paths[i + 1], f"相鄰 synth 不得同檔：{paths}"


# ============================================================
# perf_w5：內容定址快取
# ============================================================


def test_cache_hit_skips_synth_and_plays_cached_file(monkeypatch, tmp_path):
    """快取命中：synth 零呼叫，mpg123 直接播快取檔（固定句零合成零網路的根基）。"""
    monkeypatch.setattr(tts_module, "_CACHE_DIR", str(tmp_path))
    synth_calls: list = []

    async def recording_synth(text, out_path):
        synth_calls.append(text)

    popen_cmds: list = []

    def recording_popen(cmd, **kw):
        popen_cmds.append(cmd)
        return _FakePopen(returncode=0)

    monkeypatch.setattr(tts_module, "_synthesize", recording_synth)
    monkeypatch.setattr(tts_module.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    cached = tts_module._cache_path_for("固定句")
    with open(cached, "wb") as f:
        f.write(b"fake-mp3")

    worker = TtsWorker()
    worker.say("固定句")
    assert worker.wait_idle(max_wait=5.0) is True
    # 斷言以「本句」為錨——前一測試殘留的 daemon worker 可能在 monkeypatch 生效後
    # 才呼叫到本 test 的 fake（污染清單開頭），故不用 [0] 索引、不斷言全空
    assert "固定句" not in synth_calls, f"快取命中不得合成本句，實際 {synth_calls}"
    assert any(cmd[2] == cached for cmd in popen_cmds), (
        f"mpg123 應播快取檔 {cached}，實際 {popen_cmds}"
    )


def test_cache_miss_stores_result_and_reuses_on_second_say(monkeypatch, tmp_path):
    """快取 miss：合成結果原子入快取；同句第二次 say 不再合成（執行期自我增長）。"""
    monkeypatch.setattr(tts_module, "_CACHE_DIR", str(tmp_path))
    synth_calls: list = []

    async def writing_synth(text, out_path):
        # 本測試自備會寫檔的 fake——驗證 tmp → cache 原子搬移鏈
        synth_calls.append(text)
        with open(out_path, "wb") as f:
            f.write(b"fake-mp3")

    monkeypatch.setattr(tts_module, "_synthesize", writing_synth)
    monkeypatch.setattr(
        tts_module.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(returncode=0),
    )
    monkeypatch.setattr(tts_module.time, "sleep", lambda s: None)

    worker = TtsWorker()
    worker.say("動態句")
    assert worker.wait_idle(max_wait=5.0) is True
    cache_path = tts_module._cache_path_for("動態句")
    assert os.path.exists(cache_path), "合成結果應已原子搬移入快取"
    assert not os.path.exists(cache_path + ".tmp"), "tmp 檔應已被 os.replace 消耗"

    worker.say("動態句")
    assert worker.wait_idle(max_wait=5.0) is True
    assert synth_calls == ["動態句"], f"第二次應走快取不再合成，實際 {synth_calls}"


def test_prewarm_texts_cover_fixed_and_variants():
    """預熱清單：含已知固定句與商品變體、全部非模板（無 '{'）、無重複。"""
    from myProgram.tts_prewarm import _prewarm_texts
    from myProgram.sales.constants import L4_A_PAY_SUCCESS_FAREWELL, QTY_PROMPT_TEMPLATE

    texts = _prewarm_texts()
    assert texts, "預熱清單不得為空"
    assert all("{" not in t for t in texts), "模板必須先插值才進預熱清單"
    assert L4_A_PAY_SUCCESS_FAREWELL in texts
    assert QTY_PROMPT_TEMPLATE.format(product="冰紅茶", unit="瓶") in texts
    assert len(texts) == len(set(texts)), "清單不得重複"


# ============================================================
# 條件式 ALSA drain（turn boundary 提速）
# ============================================================


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


# ============================================================
# 選用式計時 log（STT_TTS_TIMING env-gated）
# ============================================================


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


# ============================================================
# SALES_QUIET：藏正常 [語音] echo、保留 ⚠️ 失敗行
# ============================================================
# 隔離 gotcha（spec §測試）：speak() 是「caller thread 立即 print → 再 _worker.say
# enqueue」。測 print gate 必先把 module-level _worker.say monkeypatch 成 no-op，
# 否則 daemon worker thread 真去合成 / 播放，async 失敗印行（[語音] ⚠️）會污染
# capsys、測試 flaky。gate 只測 caller-thread 那行 print，不牽動 worker。


def test_speak_echo_hidden_when_quiet(monkeypatch, capsys):
    """SALES_QUIET（_QUIET=True）→ speak() 不印正常 `[語音] {text}` echo。"""
    monkeypatch.setattr(tts_module, "_QUIET", True)
    monkeypatch.setattr(tts_module._worker, "say", lambda text: None)
    tts_module.speak("安靜句")
    assert "[語音] 安靜句" not in capsys.readouterr().out


def test_speak_echo_shown_when_not_quiet(monkeypatch, capsys):
    """預設 _QUIET=False → speak() 照印 `[語音] {text}`（行為不變）。"""
    monkeypatch.setattr(tts_module, "_QUIET", False)
    monkeypatch.setattr(tts_module._worker, "say", lambda text: None)
    tts_module.speak("正常句")
    assert "[語音] 正常句" in capsys.readouterr().out


def test_failure_line_not_gated_by_quiet(monkeypatch, capsys):
    """_QUIET=True 也不該藏失敗行：直接呼 _print_failure 仍印 `[語音] ⚠️`（錯誤保留）。"""
    monkeypatch.setattr(tts_module, "_QUIET", True)
    tts_module._print_failure("play", ["text = 'x'"])
    out = capsys.readouterr().out
    assert "[語音] ⚠️ TTS 失敗" in out
