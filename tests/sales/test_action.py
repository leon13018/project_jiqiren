"""test_action.py — 測試 myProgram/action.py 的 SALES_VOICE echo gate。

action.py 頂層不 import vendor（lazy import 在 worker thread 內），故 Windows pytest
可 `from myProgram import action` 而不觸發 vendor ImportError。

隔離 gotcha（spec §測試）：do() 是「caller thread 立即 print → 再 _worker.do enqueue」。
測 print gate 必先把 module-level _worker.do monkeypatch 成 no-op，否則 daemon worker
thread 首次 dispatch 會 lazy import vendor（Windows ImportError）、其失敗印行污染 capsys、
測試 flaky。gate 只測 caller-thread 那行 print，不牽動 worker。
seam：monkeypatch myProgram.action._VOICE（對齊 tts._VOICE / main._VOICE pattern）。
"""

from myProgram import action as action_module


def test_action_echo_hidden_by_default(monkeypatch, capsys):
    """預設 _VOICE=False → do() 不印正常 `[動作] {name}` echo。"""
    monkeypatch.setattr(action_module, "_VOICE", False)
    monkeypatch.setattr(action_module._worker, "do", lambda name: None)
    action_module.do("bow")
    assert "[動作] bow" not in capsys.readouterr().out


def test_action_echo_shown_when_voice_on(monkeypatch, capsys):
    """_VOICE=True → do() 照印 `[動作] {name}`。"""
    monkeypatch.setattr(action_module, "_VOICE", True)
    monkeypatch.setattr(action_module._worker, "do", lambda name: None)
    action_module.do("wave")
    assert "[動作] wave" in capsys.readouterr().out
