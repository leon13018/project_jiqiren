"""test_terminal_sim.py — 測試 myProgram/main.py 的 TerminalSim 類別 + _build_callbacks facade。

W6 重構：main.py 的 closure callback → TerminalSim 類別的 bound methods，
`_build_callbacks()` 變 facade（`return TerminalSim().callbacks()`）。

凍結面驗證（spec §2-5）：
    - callbacks() 回傳 dict 的 10 鍵與現行完全一致（餵 logic.run(**callbacks)）
    - 值為 bound methods，且全 bound 到同一 TerminalSim 實例
"""

from myProgram.main import TerminalSim, _build_callbacks


# 10 鍵（spec §2-5 — 餵 logic.run(**callbacks) 的對外契約）
# （2026-06-20 移除整套偵測模擬層後 14 → 10：去掉 4 個偵測相關 callback）
EXPECTED_KEYS = {
    "print_terminal",
    "read_terminal_key",
    "speak",
    "speak_and_wait",
    "do_action",
    "read_customer_input",
    "sleep",
    "tts_is_idle",
    "exit_program",
    "show_hawk_help",
}


def test_build_callbacks_returns_exact_10_keys():
    """_build_callbacks facade 回傳鍵集 == 10 鍵（凍結 — logic.run 對外契約）。"""
    callbacks = _build_callbacks()
    assert set(callbacks.keys()) == EXPECTED_KEYS, (
        f"鍵集不符；多/少：{set(callbacks.keys()) ^ EXPECTED_KEYS}"
    )


def test_terminal_sim_callbacks_returns_exact_10_keys():
    """TerminalSim().callbacks() 直接呼叫也回 10 鍵。"""
    callbacks = TerminalSim().callbacks()
    assert set(callbacks.keys()) == EXPECTED_KEYS


def test_callbacks_are_bound_methods_of_same_instance():
    """callbacks 值全為 bound methods，且 bound 到同一 TerminalSim 實例。"""
    sim = TerminalSim()
    callbacks = sim.callbacks()
    for key, cb in callbacks.items():
        assert hasattr(cb, "__self__"), f"{key} 應為 bound method（有 __self__）"
        assert cb.__self__ is sim, f"{key} 應 bound 到同一 TerminalSim 實例"
