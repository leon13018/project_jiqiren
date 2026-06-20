"""read_customer_input 的 STT arm/disarm 佈線 + main.py `--web` 佈線測試。

stub 手法：main.py 的 callback 內 `from myProgram import tts/stt/input_reader`
是 lazy import——以 sys.modules 預植 stub 模組攔截（tts 在 Windows 真 import 會
炸 edge_tts，必須 stub；若 tests/sales 已有現成 stub pattern 優先沿用）。

`--web` 佈線測試（`_run_wiring`）同理用 lazy import seam：web server 殼 import
uvicorn（Windows 裝不了）→ 以 sys.modules 預植 stub `myProgram.web.server`；
bus / display 純 stdlib 可真 import。logic.run 一律 monkeypatch 攔 kwargs（不真跑
狀態機）。
"""
import sys
import threading
import time
import types

import pytest

import myProgram.main as main_module
from myProgram.main import TerminalSim
from myProgram.sales import logic


@pytest.fixture
def wired(monkeypatch):
    calls = []
    fake_tts = types.SimpleNamespace(
        wait_idle=lambda max_wait=30.0: calls.append("wait_idle") or True)
    fake_stt = types.SimpleNamespace(
        prearm=lambda: calls.append("prearm"),
        arm=lambda: calls.append("arm"),
        disarm=lambda: calls.append("disarm"))
    monkeypatch.setitem(sys.modules, "myProgram.tts", fake_tts)
    monkeypatch.setitem(sys.modules, "myProgram.stt", fake_stt)
    import myProgram
    monkeypatch.setattr(myProgram, "tts", fake_tts, raising=False)
    monkeypatch.setattr(myProgram, "stt", fake_stt, raising=False)
    sim = TerminalSim()
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
    assert calls.index("wait_idle") < calls.index("arm") < calls.index("read")
    assert calls[-1] == "disarm"


def test_disarm_on_timeout(wired):
    sim, calls, monkeypatch = wired
    _stub_input(monkeypatch, calls, None)   # read 恆 None → 倒數耗盡 timeout
    assert sim.read_customer_input(timeout=0.2) is None
    assert "arm" in calls and calls[-1] == "disarm"


# === main.py `--web` 佈線（_run_wiring）===============================

def _capture_logic_run(monkeypatch):
    """攔 logic.run 的 kwargs（不真跑狀態機），回傳 captured dict。"""
    captured = {}
    monkeypatch.setattr(logic, "run", lambda **kw: captured.update(kw))
    return captured


def test_terminal_mode_injects_callable_display_and_no_web_import(monkeypatch):
    """無 `--web`：display 為 callable（no-op），且不 import web server。"""
    monkeypatch.setattr(sys, "argv", ["myprogram"])
    captured = _capture_logic_run(monkeypatch)
    # 乾淨狀態：確保斷言「未 import web server」前 sys.modules 無殘留
    monkeypatch.delitem(sys.modules, "myProgram.web.server", raising=False)

    main_module._run_wiring()

    assert callable(captured["display"])
    assert "myProgram.web.server" not in sys.modules


def test_web_mode_starts_server_on_port_8137_with_web_display(monkeypatch):
    """`--web`：呼叫 server.start(port=8137)，且注入 web 版 display（經 bus.publish）。"""
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    captured = _capture_logic_run(monkeypatch)

    started = {}

    def fake_start(bus, on_input, port=8137):
        started["bus"] = bus
        started["port"] = port
        return object(), object()   # (server, thread)

    fake_server = types.SimpleNamespace(
        start=fake_start,
        stop=lambda srv: started.__setitem__("stopped", True),
    )
    # server.py import uvicorn（Windows 裝不了）→ 必須 stub；bus/display 純 stdlib 真 import
    monkeypatch.setitem(sys.modules, "myProgram.web.server", fake_server)

    main_module._run_wiring()

    assert started["port"] == 8137
    # web 版 display：呼叫後狀態進 bus（last_state 反映出來），與 no-op lambda 區別
    captured["display"]("ordering", {"冰紅茶": 2})
    assert started["bus"].last_state()["cart"] == {"冰紅茶": 2}
    assert started.get("stopped") is True   # finally 收掉 server


def test_web_mode_wires_on_input_to_input_reader_inject(monkeypatch):
    """`--web`：server.start 收到 on_input = input_reader.inject（觸控上行注入 seam）。"""
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    captured = _capture_logic_run(monkeypatch)

    injected = []
    fake_input = types.SimpleNamespace(inject=lambda t: injected.append(t))
    monkeypatch.setitem(sys.modules, "myProgram.input_reader", fake_input)
    import myProgram
    monkeypatch.setattr(myProgram, "input_reader", fake_input, raising=False)

    started = {}

    def fake_start(bus, on_input, port=8137):
        started["on_input"] = on_input
        started["port"] = port
        return object(), object()

    fake_server = types.SimpleNamespace(start=fake_start, stop=lambda srv: None)
    monkeypatch.setitem(sys.modules, "myProgram.web.server", fake_server)

    main_module._run_wiring()

    assert started["port"] == 8137
    started["on_input"]("c")          # 等同呼叫 input_reader.inject("c")
    assert injected == ["c"]


def test_web_mode_missing_deps_falls_back_to_noop_display(monkeypatch, capsys):
    """`--web` 但 web import 失敗（Pi 沒裝 fastapi/uvicorn）→ 印錯誤 + 退回 no-op 繼續跑。"""
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    captured = _capture_logic_run(monkeypatch)
    # sys.modules[...] = None 讓 `from myProgram.web import server` raise ImportError
    monkeypatch.setitem(sys.modules, "myProgram.web.server", None)

    main_module._run_wiring()   # 不得 raise（graceful）

    assert callable(captured["display"])
    # 退回 no-op：呼叫不爆且無副作用
    captured["display"]("ordering", {"冰紅茶": 2})
    out = capsys.readouterr().out
    assert "webui" in out.lower()   # 印了明確的 web 失敗訊息


def test_prewarm_workers_swallows_import_error(monkeypatch):
    """_prewarm_workers best-effort：某 worker import 拋錯被吞、不 propagate。

    背景預熱純加速；某模組 import 失敗（缺套件 / 環境問題）不該炸主流程——
    lazy import path 屆時自然 fail-fast。monkeypatch importlib.import_module 對
    任一 name 拋錯 → _prewarm_workers() 不得 raise。
    """
    import importlib

    def boom(name, *a, **k):
        raise RuntimeError(f"預熱 import 故意失敗：{name}")

    monkeypatch.setattr(importlib, "import_module", boom)

    # 不得 raise（best-effort 吞錯）
    main_module._prewarm_workers()


def test_prewarm_workers_imports_each_worker(monkeypatch):
    """_prewarm_workers 對 tts / action / stt 各跑一次 import_module（暖三個 worker）。"""
    import importlib

    imported = []
    monkeypatch.setattr(importlib, "import_module",
                        lambda name, *a, **k: imported.append(name))

    main_module._prewarm_workers()

    assert imported == ["myProgram.tts", "myProgram.action", "myProgram.stt"]


def test_web_mode_logic_run_not_blocked_by_slow_server_start(monkeypatch):
    """`--web` 非阻塞契約：logic.run 立即跑，不等笨重的 server.start 完成。

    根因修復核心——笨重 web import + server.start 移到背景 daemon thread，
    menu（logic.run）立即可互動。本測試讓 server.start 卡 0.5s（模擬 Pi 上
    fastapi/uvicorn 笨重 import + 啟動），驗 logic.run 在 server.start 仍進行中
    就已被呼叫（即 start 在背景 thread、非主執行緒阻塞 logic.run 之前）。
    """
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])

    events = []
    start_running = threading.Event()
    start_done = threading.Event()

    def slow_start(bus, on_input, port=8137):
        start_running.set()
        time.sleep(0.5)          # 模擬笨重啟動
        start_done.set()
        events.append("start_done")
        return object(), object()

    def fake_logic_run(**kw):
        # logic.run 被呼叫時 server.start 應已啟動（thread spawn）但尚未完成
        start_running.wait(timeout=2)
        events.append(f"logic_run start_done={start_done.is_set()}")

    fake_server = types.SimpleNamespace(start=slow_start, stop=lambda srv: None)
    monkeypatch.setitem(sys.modules, "myProgram.web.server", fake_server)
    monkeypatch.setattr(logic, "run", fake_logic_run)

    main_module._run_wiring()

    # logic.run 在 server.start 尚未完成時即被呼叫（非阻塞契約）
    assert events[0] == "logic_run start_done=False", (
        f"logic.run 應在 server.start 進行中即被呼叫，實際事件序：{events}"
    )
    # finally 仍等 boot thread 完成、收掉 server（不漏 stop）
    assert "start_done" in events


def test_web_mode_server_start_raises_falls_back_to_noop_display(monkeypatch, capsys):
    """`--web` 但 server.start() raise（如 port 衝突 OSError）→ 不 raise + 退回 no-op 繼續跑。

    反思 web-startup-non-import-error-crash：graceful 原只包 ImportError，server 啟動
    失敗的 OSError 等會傳出 crash 機器人。bus/display 真 import、只 stub server.start raise。
    """
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    captured = _capture_logic_run(monkeypatch)

    def fake_start(bus, on_input, port=8137):
        raise OSError("port 8137 已被佔用")

    fake_server = types.SimpleNamespace(
        start=fake_start,
        stop=lambda srv: None,   # 不應被呼叫（start 失敗 → web_srv 留 None）
    )
    monkeypatch.setitem(sys.modules, "myProgram.web.server", fake_server)

    main_module._run_wiring()   # 不得 raise（graceful 涵蓋 OSError）

    assert callable(captured["display"])
    # 退回 no-op：呼叫不爆且無副作用
    captured["display"]("ordering", {"冰紅茶": 2})
    out = capsys.readouterr().out
    assert "webui" in out.lower()   # 印了明確的 web 啟動失敗訊息
