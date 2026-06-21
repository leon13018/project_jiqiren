"""test_machine.py — 測試 myProgram/sales/states/machine.py 的 State pattern。

對應 spec：resources/specs/oop_w5_2026-06-10_spec.md（§2-1/§2-2/§2-3）。
覆蓋（類別層，與 test_logic 同 mock seam = states 模組屬性）：
    1. Transition frozen（賦值 raise）+ enter_hawk 預設 False + 相等性
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
    State,
    L1State,
    DialogState,
    L4State,
    L5State,
    SalesMachine,
)


# ============================================================
# 共用 callback stub 工廠（與 test_logic 一致的 no-op）
# ============================================================

def _make_callbacks(**overrides):
    """建立預設全 no-op callback dict；可用 overrides 覆蓋個別 callback。"""
    defaults = dict(
        print_terminal=lambda *a, **k: None,
        read_terminal_key=lambda *a, **k: None,
        speak=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
        read_customer_input=lambda *a, **k: None,
        sleep=lambda *a, **k: None,
        tts_is_idle=lambda: True,
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
# Test 6：start_hawk 進場旗號（--hawk 入口；複用 enter_hawk_immediately）
# ============================================================

def test_start_hawk_true_first_l1_enters_hawk_immediately(monkeypatch):
    """SalesMachine(..., start_hawk=True)：首次進 L1 即 enter_hawk_immediately=True
    （跳主選單直接 hawk）。"""
    received = []

    def stub_run_l1(**kwargs):
        received.append(kwargs.get("enter_hawk_immediately"))
        return None  # 首輪即終止，只驗第一次進場旗號

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    machine = SalesMachine(callbacks=_make_callbacks(), cart=cart_module.new_cart(),
                           start_hawk=True)
    machine.run()

    assert received == [True], "start_hawk=True → 首次 run_l1 應收到 enter_hawk_immediately=True"


def test_start_hawk_default_false_shows_menu(monkeypatch):
    """SalesMachine 不傳 start_hawk（預設 False）：首次進 L1 enter_hawk_immediately=False
    （顯示主選單，既有行為）。"""
    received = []

    def stub_run_l1(**kwargs):
        received.append(kwargs.get("enter_hawk_immediately"))
        return None

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    machine = SalesMachine(callbacks=_make_callbacks(), cart=cart_module.new_cart())
    machine.run()

    assert received == [False], "預設 start_hawk=False → 首次 run_l1 應收到 enter_hawk_immediately=False"


# ============================================================
# Test 1：Transition frozen + 預設值 + 相等性
# ============================================================

def test_transition_enter_hawk_defaults_false():
    """Transition 不指定 enter_hawk 時預設 False。"""
    t = Transition("dialog")
    assert t.next_state == "dialog"
    assert t.enter_hawk is False


def test_transition_is_frozen():
    """Transition 為 frozen dataclass，賦值應 raise FrozenInstanceError。"""
    t = Transition("l4")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.next_state = "l5"


def test_transition_equality():
    """同 next_state + 同 enter_hawk 的 Transition 相等。"""
    assert Transition("l1", enter_hawk=True) == Transition("l1", True)
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
                        think_count, do_action, speak_and_wait=None,
                        display=None):
        cart["冰紅茶"] = 1  # L4 路徑不清 cart
        return ("L4", 0)

    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    machine = _make_machine()
    result = DialogState().run(machine)
    assert result == Transition("l4")


def test_dialogstate_enter_hawk_maps_to_l1_enter_hawk(monkeypatch):
    """DialogState：run_dialog stub 清 cart 回 ("L1_enter_hawk", 0)
    → Transition("l1", enter_hawk=True)。"""
    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart,
                        think_count, do_action, speak_and_wait=None,
                        display=None):
        cart.clear()
        return ("L1_enter_hawk", 0)

    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    machine = _make_machine()
    result = DialogState().run(machine)
    assert result == Transition("l1", enter_hawk=True)


def test_l4state_l5_maps_to_l5(monkeypatch):
    """L4State：run_l4 stub 回 ("L5", 0, 0) → Transition("l5")。"""
    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        return ("L5", 0, 0)  # L5 路徑不清 cart

    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    machine = _make_machine()
    result = L4State().run(machine)
    assert result == Transition("l5")


def test_l4state_non_scan_maps_to_l1_enter_hawk(monkeypatch):
    """L4State：run_l4 stub 清 cart 回 ("L1_enter_hawk", 0, 0)
    → Transition("l1", enter_hawk=True)。"""
    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        cart.clear()
        return ("L1_enter_hawk", 0, 0)

    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    machine = _make_machine()
    result = L4State().run(machine)
    assert result == Transition("l1", enter_hawk=True)


def test_l5state_always_maps_to_l1_enter_hawk_ignoring_return(monkeypatch):
    """L5State：run_l5 stub 清 cart 回非標準字串 ("L1", 0, 0)（回傳值被忽略）
    → 仍 Transition("l1", enter_hawk=True)。"""
    def stub_run_l5(*, cart, sleep, do_action):
        cart.clear()
        return ("L1", 0, 0)  # 非標準字串；應被忽略

    monkeypatch.setattr(states_module, "run_l5", stub_run_l5)
    machine = _make_machine()
    result = L5State().run(machine)
    assert result == Transition("l1", enter_hawk=True)


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


def test_machine_run_raises_on_unknown_entry_invariant():
    """machine.run() 進場時遇非法 entry_invariant（typo "Nonempty"）→ ValueError，
    fail-fast 而非靜默走錯誤 cart 檢查。raise 發生在 state.run 之前，不需 stub run_*。"""
    class BadState(State):
        entry_invariant = "Nonempty"  # 非法值（大寫 typo）
        entry_ctx = "進 Bad"

        def run(self, machine):  # 不該被呼到——進場 assert 先炸
            raise AssertionError("state.run 不應被呼叫")

    machine = _make_machine()
    machine._states["l1"] = BadState()

    with pytest.raises(ValueError, match="entry_invariant"):
        machine.run()


# ============================================================
# Test 5：machine 狀態進場 emit display（phase 轉移 + thankyou paid）
# ============================================================

def test_machine_emits_phase_on_state_entry(monkeypatch):
    """SalesMachine.run() 每進新層 emit phase 轉移 + 當前 cart 快照；
    進 l5 帶 paid = calc_total(cart)（清 cart 前算）。

    驅動一輪完整 cycle：l1（空）→ dialog（加 冰紅茶×2）→ l4 → l5（清 cart）
    → 回 l1（空）→ 終止。
    emit 在每層進場（invariant 檢查後、state.run 前）→ cart 快照為「進該層當下」狀態：
        standby  (l1, cart 空)
        ordering (dialog, cart 空 — dialog stub 進場後才加單)
        checkout (l4, cart={冰紅茶:2})
        thankyou (l5, cart={冰紅茶:2}, paid=54=2×27 — l5 清 cart 前算)
        standby  (回 l1, cart 已被 l5 清空)
    """
    calls = []

    l1_count = {"n": 0}

    def stub_run_l1(**kwargs):
        l1_count["n"] += 1
        return "L2" if l1_count["n"] == 1 else None  # 第二次進 l1 終止

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart,
                        think_count, do_action, speak_and_wait=None,
                        display=None):
        cart["冰紅茶"] = 2  # 顧客點兩瓶；L4 路徑不清 cart
        return ("L4", 0)

    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        return ("L5", 0, 0)  # 掃碼成功 → L5（不清 cart，L5 負責）

    def stub_run_l5(*, cart, sleep, do_action):
        cart.clear()  # L5 清 cart（正常行為）
        return ("L1", 0, 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    monkeypatch.setattr(states_module, "run_l5", stub_run_l5)

    cb = _make_callbacks(
        display=lambda phase, cart, paid=0: calls.append((phase, dict(cart), paid)),
    )
    SalesMachine(callbacks=cb, cart=cart_module.new_cart()).run()

    phases = [c[0] for c in calls]
    assert phases[:4] == ["standby", "ordering", "checkout", "thankyou"]
    assert calls[2][1] == {"冰紅茶": 2}, "進 l4 cart 快照應含 冰紅茶×2"
    assert calls[3] == ("thankyou", {"冰紅茶": 2}, 54), "進 l5 帶 paid=2×27=54（清 cart 前算）"


def test_machine_no_emit_when_display_absent(monkeypatch):
    """callbacks 無 display 鍵 → _emit 經 .get 取 None → 不 emit（既有 621 測試零行為改變）。

    run_l1 stub 第一輪即回 None 終止（只進一次 l1）；不傳 display callback，
    驗證 _emit 對缺 display 鍵 graceful（不 KeyError、不 raise）。
    """
    monkeypatch.setattr(states_module, "run_l1", lambda **kwargs: None)
    machine = _make_machine()              # _make_callbacks 無 display 鍵
    machine.run()                          # 不應 raise（.get("display") → None → 跳過 emit）


def test_machine_emit_unknown_state_no_raise_no_emit():
    """_emit 對未知 current（不在 _PHASE_BY_STATE）→ 跳過 emit、不 KeyError crash。

    反思 phase-map-unguarded-keyerror：current 非預期值（mock stub / 未來新狀態）
    經 .get 取 None → return 不呼叫 disp，不拖垮機器人主迴圈（web 顯示非關鍵）。
    """
    called = {"n": 0}
    machine = _make_machine(display=lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    machine._emit("unknown_state")         # 不應 raise
    assert called["n"] == 0, "未知 current → 不呼叫 display"
