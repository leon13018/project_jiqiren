"""read_customer_input 的 STT arm/disarm 佈線測試。

stub 手法：main.py 的 callback 內 `from myProgram import tts/stt/input_reader`
是 lazy import——以 sys.modules 預植 stub 模組攔截（tts 在 Windows 真 import 會
炸 edge_tts，必須 stub；若 tests/sales 已有現成 stub pattern 優先沿用）。
"""
import sys
import types

import pytest

from myProgram.main import TerminalSim, _S1State


@pytest.fixture
def wired(monkeypatch):
    calls = []
    fake_tts = types.SimpleNamespace(
        wait_idle=lambda max_wait=30.0: calls.append("wait_idle") or True)
    fake_stt = types.SimpleNamespace(
        prewarm=lambda: calls.append("prewarm"),
        arm=lambda: calls.append("arm"),
        disarm=lambda: calls.append("disarm"))
    monkeypatch.setitem(sys.modules, "myProgram.tts", fake_tts)
    monkeypatch.setitem(sys.modules, "myProgram.stt", fake_stt)
    import myProgram
    monkeypatch.setattr(myProgram, "tts", fake_tts, raising=False)
    monkeypatch.setattr(myProgram, "stt", fake_stt, raising=False)
    sim = TerminalSim(_S1State())
    return sim, calls, monkeypatch


def _stub_input(monkeypatch, calls, value):
    import time as _time

    def _read(timeout):
        # 模擬真實等待節奏：value=None（timeout 案例）時若立即返回會 busy-spin
        # 倒數迴圈灌爆 calls；小睡讓 deadline 自然消耗。
        _time.sleep(min(timeout or 0.05, 0.05))
        calls.append("read")
        return value

    fake_input = types.SimpleNamespace(read=_read)
    monkeypatch.setitem(sys.modules, "myProgram.input_reader", fake_input)
    import myProgram
    monkeypatch.setattr(myProgram, "input_reader", fake_input, raising=False)


def test_arm_after_wait_idle_and_disarm_on_input(wired):
    sim, calls, monkeypatch = wired
    _stub_input(monkeypatch, calls, "好")
    assert sim.read_customer_input(timeout=5) == "好"
    assert (calls.index("prewarm") < calls.index("wait_idle")
            < calls.index("arm") < calls.index("read"))
    assert calls[-1] == "disarm"


def test_disarm_on_timeout(wired):
    sim, calls, monkeypatch = wired
    _stub_input(monkeypatch, calls, None)   # read 恆 None → 倒數耗盡 timeout
    assert sim.read_customer_input(timeout=0.2) is None
    assert "arm" in calls and calls[-1] == "disarm"
