"""test_machine.py — 測試 myProgram/sales/states/machine.py 的 State pattern。

對應 spec：resources/specs/oop_w5_2026-06-10_spec.md（§2-1/§2-2/§2-3）。
覆蓋（類別層，與 test_logic 同 mock seam = states 模組屬性）：
    1. Transition frozen（賦值 raise）+ via_subroutine_a 預設 False + 相等性
    2. 各 State 轉移映射（stub 對應 states.run_*）
    3. L5State 忽略回傳值（stub 回非標準字串仍 Transition("l1", True)）
    4. L1State consume-reset 旗號（run 後 stub 收到 True 且 machine 旗號變 False）
    5. machine 進場 invariant ctx 字串（cart 非空進 "l1" → AssertionError）

設計：callback 全 stub（inline lambda + dict 收集），禁用 mock library；
      用 monkeypatch.setattr 替換 myProgram.sales.states 的各 run_? 函式（與 test_logic 同 seam）。
"""

import dataclasses

import pytest
import myProgram.sales.states as states_module
import myProgram.sales.cart as cart_module
from myProgram.sales.states.machine import (
    Transition,
    L1State,
    DialogState,
    L4State,
    L5State,
    SalesMachine,
)


# ============================================================
# 共用 callback stub 工廠（與 test_logic 一致的 13 個 no-op）
# ============================================================

def _make_callbacks(**overrides):
    """建立預設全 no-op callback dict；可用 overrides 覆蓋個別 callback。"""
    defaults = dict(
        print_terminal=lambda *a, **k: None,
        read_terminal_key=lambda *a, **k: None,
        opencv_dwell_seconds=lambda *a, **k: None,
        opencv_disable=lambda *a, **k: None,
        opencv_enable=lambda *a, **k: None,
        mute_opencv=lambda *a, **k: None,
        speak=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
        read_customer_input=lambda *a, **k: None,
        sleep=lambda *a, **k: None,
        schedule=lambda *a, **k: None,
        exit_program=lambda *a, **k: None,
        show_hawk_help=lambda *a, **k: None,
        speak_and_wait=lambda *a, **k: None,
    )
    defaults.update(overrides)
    return defaults


def _make_machine(cart=None, **cb_overrides):
    """建一個 SalesMachine（cart 預設新建空車）。"""
    if cart is None:
        cart = cart_module.new_cart()
    return SalesMachine(callbacks=_make_callbacks(**cb_overrides), cart=cart)


# ============================================================
# Test 1：Transition frozen + 預設值 + 相等性
# ============================================================

def test_transition_via_subroutine_a_defaults_false():
    """Transition 不指定 via_subroutine_a 時預設 False。"""
    t = Transition("dialog")
    assert t.next_state == "dialog"
    assert t.via_subroutine_a is False


def test_transition_is_frozen():
    """Transition 為 frozen dataclass，賦值應 raise FrozenInstanceError。"""
    t = Transition("l4")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.next_state = "l5"


def test_transition_equality():
    """同 next_state + 同 via_subroutine_a 的 Transition 相等。"""
    assert Transition("l1", via_subroutine_a=True) == Transition("l1", True)
    assert Transition("dialog") != Transition("l4")


# ============================================================
# Test 2：各 State 轉移映射
# ============================================================

def test_l1state_l2_maps_to_dialog(monkeypatch):
    """L1State：run_l1 stub 回 "L2" → Transition("dialog")。"""
    monkeypatch.setattr(states_module, "run_l1", lambda **kwargs: "L2")
    machine = _make_machine()
    result = L1State().run(machine)
    assert result == Transition("dialog")


def test_l1state_none_terminates(monkeypatch):
    """L1State：run_l1 stub 回 None → None（程式終止）。"""
    monkeypatch.setattr(states_module, "run_l1", lambda **kwargs: None)
    machine = _make_machine()
    result = L1State().run(machine)
    assert result is None


def test_dialogstate_l4_maps_to_l4(monkeypatch):
    """DialogState：run_dialog stub 回 ("L4", 0) → Transition("l4")。"""
    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart,
                        think_count, opencv_disable, do_action, speak_and_wait=None):
        cart["冰紅茶"] = 1  # L4 路徑不清 cart
        return ("L4", 0)

    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    machine = _make_machine()
    result = DialogState().run(machine)
    assert result == Transition("l4")


def test_dialogstate_subroutine_a_maps_to_l1_via_sub(monkeypatch):
    """DialogState：run_dialog stub 清 cart 回 ("L1_via_subroutine_a", 0)
    → Transition("l1", via_subroutine_a=True)。"""
    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart,
                        think_count, opencv_disable, do_action, speak_and_wait=None):
        cart.clear()
        return ("L1_via_subroutine_a", 0)

    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    machine = _make_machine()
    result = DialogState().run(machine)
    assert result == Transition("l1", via_subroutine_a=True)


def test_l4state_l5_maps_to_l5(monkeypatch):
    """L4State：run_l4 stub 回 ("L5", 0, 0) → Transition("l5")。"""
    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    opencv_disable, do_action, speak_and_wait=None):
        return ("L5", 0, 0)  # L5 路徑不清 cart

    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    machine = _make_machine()
    result = L4State().run(machine)
    assert result == Transition("l5")


def test_l4state_non_scan_maps_to_l1_via_sub(monkeypatch):
    """L4State：run_l4 stub 清 cart 回 ("L1_via_subroutine_a", 0, 0)
    → Transition("l1", via_subroutine_a=True)。"""
    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    opencv_disable, do_action, speak_and_wait=None):
        cart.clear()
        return ("L1_via_subroutine_a", 0, 0)

    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    machine = _make_machine()
    result = L4State().run(machine)
    assert result == Transition("l1", via_subroutine_a=True)


def test_l5state_always_maps_to_l1_via_sub_ignoring_return(monkeypatch):
    """L5State：run_l5 stub 清 cart 回非標準字串 ("L1", 0, 0)（回傳值被忽略）
    → 仍 Transition("l1", via_subroutine_a=True)。"""
    def stub_run_l5(*, speak, cart, sleep, do_action):
        cart.clear()
        return ("L1", 0, 0)  # 非標準字串；應被忽略

    monkeypatch.setattr(states_module, "run_l5", stub_run_l5)
    machine = _make_machine()
    result = L5State().run(machine)
    assert result == Transition("l1", via_subroutine_a=True)


# ============================================================
# Test 3：L1State consume-reset 旗號
# ============================================================

def test_l1state_consumes_and_resets_enter_hawk_flag(monkeypatch):
    """machine.enter_hawk_immediately=True → run_l1 stub 收到 True，
    且呼叫後 machine 旗號立即 reset 為 False（consume-after-use）。"""
    received = {}

    def stub_run_l1(**kwargs):
        received["enter_hawk_immediately"] = kwargs.get("enter_hawk_immediately")
        return "L2"

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    machine = _make_machine()
    machine.enter_hawk_immediately = True

    L1State().run(machine)

    assert received["enter_hawk_immediately"] is True, "run_l1 應收到 True"
    assert machine.enter_hawk_immediately is False, "呼叫後旗號應立即 reset 為 False"


# ============================================================
# Test 4：machine 進場 invariant ctx 字串
# ============================================================

def test_machine_run_asserts_cart_empty_entering_l1(monkeypatch):
    """machine.run() 進 "l1" 前 cart 非空 → AssertionError，
    訊息 match "Cart invariant 違反" 且含「進 L1」。"""
    # run_l1 不該被呼到（進場 assert 先炸）；給 stub 防意外
    monkeypatch.setattr(states_module, "run_l1", lambda **kwargs: None)

    cart = cart_module.new_cart()
    cart["冰紅茶"] = 1  # 進 L1 前刻意非空 → 違反 invariant
    machine = _make_machine(cart=cart)

    with pytest.raises(AssertionError, match="Cart invariant 違反"):
        machine.run()


def test_machine_run_l1_entry_ctx_mentions_進l1(monkeypatch):
    """進 L1 invariant 違反訊息應含 ctx 「進 L1」。"""
    monkeypatch.setattr(states_module, "run_l1", lambda **kwargs: None)
    cart = cart_module.new_cart()
    cart["冰紅茶"] = 1
    machine = _make_machine(cart=cart)

    with pytest.raises(AssertionError, match="進 L1"):
        machine.run()
