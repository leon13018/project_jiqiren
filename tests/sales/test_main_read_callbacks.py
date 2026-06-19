"""test_main_read_callbacks.py — 測試 myProgram/main.py 的 read_*_input/read_*_key callback。

2026-05-30 v3：read_customer_input 內部加 `tts.wait_idle()` 前置 — 顧客的「全部層
和每種狀態」timeout 從 TTS 播完才開始倒數，不被 prompt 播放時間吃掉。

對應背景：
    - v1 (8e3aa67) 同設計被 revert，因 3 個 bug（P0 unbounded wait / P1 race /
      M2 wall-clock budget silent semantic change）
    - v2 (c418004) 修了 P0/P1（max_wait=10s + Condition+_pending counter）+
      給 wall-clock budget caller `speak_and_wait` 顯式控制 deadline
    - v3 (本檔)：v1 設計現在安全，重新引入

涵蓋三條測試：
    1. read_customer_input：wait_idle 必須在 input_reader.read 之前被 call
       （顧客層全 read 點自動 cover TTS 等待）
    2. read_terminal_key：wait_idle 不該被 call（regression 防護 — L1 hawk 主迴圈
       polling cadence 0.1s，加 wait_idle 會被 max_wait=30s 卡死）
    3. sleep：wait_idle 必須在 time.sleep 之前被 call（L5 THANK_DELAY=3s 規格
       promise「顧客 3 秒離開時間」從 speak 完才起算；只等 TTS 不等 do_action）

測試策略 — Fake tts module + 雙重注入（Windows 無 edge_tts + cross-test cache）：
    1. myProgram.tts 頂層 `import edge_tts` 是 fail-fast；Windows pytest 無此套件，
       直接 monkeypatch.setattr("myProgram.tts.wait_idle", ...) 會觸發 import
       myProgram.tts → ImportError。
    2. main.py callback 內 `from myProgram import tts` 的 Python 語義（CPython
       IMPORT_FROM）：先看 myProgram package 上有沒 tts attribute，沒有才走
       sys.modules + import 流程。
    3. 兩種 pytest 跨檔順序：
       - 本檔單跑（或本檔先跑）：myProgram 上沒 tts attr 也不在 sys.modules
         → setitem 注入到 sys.modules 讓 import 路徑可解析；setattr raising=False
         新增 attr 防 IMPORT_FROM 取 sys.modules 前被舊 attr 攔截。
       - test_tts_worker.py 先跑：真模組進 sys.modules + bind 到 myProgram.tts
         attr → 必須同時蓋 attr 才有效。

    解：用 helper `_install_fake_tts` 同時 setitem(sys.modules) + setattr(myProgram)
    cover 兩種情境；monkeypatch 結束兩者都自動還原。
"""

import sys
import types

import myProgram
from myProgram.main import _build_callbacks, _S1State


def _make_fake_tts_module(wait_idle_calls):
    """建一個 fake myProgram.tts module，wait_idle 記錄 call。"""
    fake = types.ModuleType("myProgram.tts")

    def wait_idle(*args, **kwargs):
        wait_idle_calls.append("wait_idle")
        return True

    fake.wait_idle = wait_idle
    return fake


def _install_fake_tts(monkeypatch, fake):
    """同時注入 fake 到 sys.modules + myProgram package attr。

    cover 兩種 pytest 跨檔順序：
      - 真 myProgram.tts 已被 test_tts_worker.py import → 需蓋 attr
      - 從未 import 過 → setattr raising=False 直接新增 attr
    monkeypatch teardown 兩者都自動還原。
    """
    monkeypatch.setitem(sys.modules, "myProgram.tts", fake)
    monkeypatch.setattr(myProgram, "tts", fake, raising=False)


def test_read_customer_input_calls_wait_idle_before_input_read(monkeypatch):
    """v3：顧客層 read 前先 wait_idle 等 TTS 播完才開始倒數。

    驗證 wait_idle 必須在 input_reader.read 之前被 call（順序對；
    對 wall-clock budget caller speak_and_wait 後 pending=0 是 immediate
    no-op，對非 budget caller 自動 cover TTS 等待）。

    2026-05-30 加：read_customer_input 進入 polling loop（每秒印 `timeout = N`），
    為避免測試陷入無限迴圈（mock 的 input_reader.read 不真實 sleep，monotonic
    不前進），讓 mock 第一次 read 即回傳 "x"（非 None）讓 loop break，再驗
    wait_idle → read 順序。
    """
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    monkeypatch.setattr(
        "myProgram.input_reader.read",
        lambda timeout: call_order.append("read") or "x",
    )

    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)

    assert call_order == ["wait_idle", "read"], (
        f"順序應 wait_idle → read，實際：{call_order}"
    )


def _make_fake_stt_module(call_order):
    fake = types.ModuleType("myProgram.stt")
    fake.prearm = lambda: call_order.append("prearm")
    fake.arm = lambda: call_order.append("arm")
    fake.disarm = lambda: call_order.append("disarm")
    return fake


def _install_fake_stt(monkeypatch, fake):
    monkeypatch.setitem(sys.modules, "myProgram.stt", fake)
    monkeypatch.setattr(myProgram, "stt", fake, raising=False)


def test_read_customer_input_calls_prearm_before_wait_idle(monkeypatch):
    """prearm 必須在 wait_idle 之前 call（才能 overlap 提示音播放藏首輪握手）。"""
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)
    assert call_order.index("prearm") < call_order.index("wait_idle") < call_order.index("read")
    assert "arm" in call_order and "disarm" in call_order


def test_read_customer_input_mic_open_delay_sleeps_between_wait_idle_and_arm(monkeypatch):
    """STT_MIC_OPEN_DELAY_MS 旋鈕生效：開麥延遲落在 wait_idle 與 arm 之間。

    旋鈕 > 0 時，read_customer_input 在 tts.wait_idle()（等喇叭播完）之後、
    stt.arm()（開 arecord）之前 sleep 該秒數，讓喇叭 ALSA 尾音排空，避免
    arecord 把機器人尾音收進去黏吞顧客軟起音首字。

    斷言鎖定「開麥延遲那次 sleep」：fake input_reader.read 第一次即回 "x" 讓
    _tick_countdown 立即 break、不進倒數 sleep，故 mic-open delay 是唯一一次
    time.sleep。驗 sleep 以 0.3 被呼叫，且呼叫序為 wait_idle → sleep → arm。
    """
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    monkeypatch.setattr("myProgram.main._MIC_OPEN_DELAY_SEC", 0.3)

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        call_order.append("sleep")

    monkeypatch.setattr("myProgram.main.time.sleep", fake_sleep)

    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)

    assert sleep_calls == [0.3], (
        f"開麥延遲應以 0.3 呼叫一次 time.sleep，實際：{sleep_calls}"
    )
    assert (
        call_order.index("wait_idle")
        < call_order.index("sleep")
        < call_order.index("arm")
    ), f"序列應 wait_idle → sleep → arm，實際：{call_order}"


def test_read_customer_input_default_no_mic_open_delay(monkeypatch):
    """預設 0：開麥前不插入延遲 sleep，wait_idle 後直接 arm（不改行為）。"""
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    _install_fake_stt(monkeypatch, _make_fake_stt_module(call_order))
    monkeypatch.setattr("myProgram.input_reader.read",
                        lambda timeout: call_order.append("read") or "x")
    monkeypatch.setattr("myProgram.main._MIC_OPEN_DELAY_SEC", 0.0)

    def fake_sleep(seconds):
        call_order.append("sleep")

    monkeypatch.setattr("myProgram.main.time.sleep", fake_sleep)

    callbacks = _build_callbacks(_S1State())
    callbacks["read_customer_input"](timeout=6)

    assert "sleep" not in call_order, (
        f"預設 0 不應插入開麥延遲 sleep，實際：{call_order}"
    )
    assert call_order.index("wait_idle") < call_order.index("arm"), (
        f"wait_idle 後應直接 arm，實際：{call_order}"
    )


def test_read_terminal_key_does_not_call_wait_idle(monkeypatch):
    """v3 regression：商家層 hawk polling 不應被 wait_idle 卡。

    L1 hawk 主迴圈以 timeout=0.1s polling 跟 OpenCV 並行；若加 wait_idle，
    其 max_wait=30s 會把 hawk polling cadence 完全卡死（規格 hawk 12s 內
    TTS 大半都卡）。商家層 speak 多是 status notification（「已開啟偵測」），
    不需要顧客式「等播完再倒數」語意。
    """
    wait_idle_calls = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(wait_idle_calls))
    monkeypatch.setattr(
        "myProgram.input_reader.read",
        lambda timeout: None,
    )

    callbacks = _build_callbacks(_S1State())
    callbacks["read_terminal_key"](timeout=0.1)

    assert wait_idle_calls == [], (
        f"read_terminal_key 不應 call wait_idle（會卡 hawk polling），實際 called: {wait_idle_calls}"
    )


def test_sleep_calls_wait_idle_before_actual_sleep(monkeypatch):
    """v3：sleep 前先 wait_idle 等 TTS 播完才開始倒數。

    L5 THANK_DELAY=3s 規格 promise「顧客 3 秒離開時間」現在從 speak 完才起算
    （之前 S4 後 speak 非阻塞 + 立即 time.sleep → 顧客 effective 離開時間 ~1s）。

    L5 序列（sales/states/l5.py；2026-06-15 結帳收尾語音合併後 L5 不再 speak，
    致謝語音已併入 L4 鏈路 A 的 L4_A_PAY_SUCCESS_FAREWELL 單句）：
        do_action(ACTION_L5_FAREWELL)  # 非阻塞（S5 worker enqueue，return immediately）
        clear_cart                     # instant
        sleep(THANK_DELAY)             # ← 之前立即 time.sleep(3)，TTS 還在播

    sleep 仍先 wait_idle 等 TTS（此處指 L4 已 enqueue 的合併致謝句）播完才倒數
    — 顧客看到揮手動作 + 聽完語音 + 有 3s 走人（do_action 不卡倒數）。

    2026-05-30 加：sleep 進入 polling loop（每秒印 `wait = N`）對齊 read_customer_input
    countdown pattern；為避免測試陷入無限迴圈（mock 的 time.sleep 不真實前進
    monotonic clock），用虛擬時鐘 advance — 每次 time.sleep(s) 把 monotonic 推 s 秒，
    讓 loop 自然耗盡 deadline。順序仍驗 wait_idle → 第一次 sleep。
    """
    call_order = []
    _install_fake_tts(monkeypatch, _make_fake_tts_module(call_order))
    # 虛擬時鐘：time.sleep(s) 推進 monotonic s 秒（避免 polling loop 無限迴圈）
    clock = [0.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    def fake_sleep(seconds):
        call_order.append(f"sleep({seconds})")
        clock[0] += seconds

    monkeypatch.setattr("time.sleep", fake_sleep)

    callbacks = _build_callbacks(_S1State())
    callbacks["sleep"](3)

    # wait_idle 必須先於任何 sleep；後續 3 次 sleep(1.0) 是 polling loop
    # 對齊整秒邊界（remaining=3.0 → 1.0；2.0 → 1.0；1.0 → 1.0）
    assert call_order[0] == "wait_idle", (
        f"wait_idle 應排第一，實際：{call_order}"
    )
    assert call_order[1].startswith("sleep("), (
        f"wait_idle 後應接 sleep（polling loop），實際：{call_order}"
    )
