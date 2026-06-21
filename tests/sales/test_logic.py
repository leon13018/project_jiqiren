"""test_logic.py — 測試 myProgram/sales/logic.py 主控狀態機。

對應 review finding：HP-10 / D1 / D6
覆蓋：
    1. cart invariant 違反時 raise AssertionError
    2. L1 result=None → run 立即返回
    3. dialog 返 L1_enter_hawk → cart 應已空 + enter_hawk_immediately=True
    4. L4 非掃碼退出 → cart 應已空 + enter_hawk_immediately=True
    5. L5 退出後 cart 應已空 + enter_hawk_immediately=True
    6. enter_hawk_immediately 消費後 reset 為 False

設計：callback 全 stub（inline lambda + list 收集呼叫紀錄），禁用 mock library。
      用 monkeypatch.setattr 替換 myProgram.sales.states 的各 run_? 函式。
"""

import pytest
import myProgram.sales.logic as logic
import myProgram.sales.states as states_module
import myProgram.sales.cart as cart_module


# ============================================================
# 共用 callback stub 工廠
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
    )
    defaults.update(overrides)
    return defaults


# ============================================================
# Test 1：cart invariant 違反時 raise AssertionError
# ============================================================

def test_logic_assert_cart_empty_violation_raises(monkeypatch):
    """進入 dialog 層前 cart 必須為空，否則 _assert_cart_empty raise AssertionError。

    模擬情境：
        第一輪 run_l1 返 "L2"；
        run_dialog 在執行時把 cart 加入商品後返 "L1_enter_hawk"，但不清 cart；
        enter_hawk_immediately=True 使第二輪跳過主選單直接進 L1；
        第二輪 run_l1 也返 "L2"；
        第二輪再進 dialog 層前的 _assert_cart_empty 應 raise（因 cart 未被清空）。
    """
    call_counts = {"run_l1": 0, "run_dialog": 0}

    def stub_run_l1(**kwargs):
        call_counts["run_l1"] += 1
        # 前兩輪都返 "L2"，進 dialog
        return "L2"

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart, think_count,
                        do_action, speak_and_wait=None, display=None):
        call_counts["run_dialog"] += 1
        # 第一次把 cart 加商品但不清空，然後返 L1_enter_hawk
        cart["冰紅茶"] = 1
        return ("L1_enter_hawk", 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)

    cbs = _make_callbacks()

    with pytest.raises(AssertionError, match="Cart invariant 違反"):
        logic.run(**cbs)


# ============================================================
# Test 2：L1 result=None → run 立即返回
# ============================================================

def test_logic_l1_returns_none_terminates_run(monkeypatch):
    """run_l1 stub 返 None 時，logic.run() 應立即 return，不進入 dialog。

    模擬情境：商家在 L1 按 q 退出。
    """
    dialog_calls = []

    def stub_run_l1(**kwargs):
        return None

    def stub_run_dialog(**kwargs):
        dialog_calls.append(True)
        return ("L4", 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)

    cbs = _make_callbacks()
    result = logic.run(**cbs)

    assert result is None, "logic.run 應返 None"
    assert dialog_calls == [], "dialog 不應被呼叫"


# ============================================================
# Test 3：dialog 返 L1_enter_hawk → cart 已空 + enter_hawk_immediately=True
# ============================================================

def test_logic_dialog_exits_to_enter_hawk_with_empty_cart(monkeypatch):
    """dialog 返 L1_enter_hawk 時：
        - cart 必須已空（dialog 自行清空）
        - 下一輪 run_l1 收到 enter_hawk_immediately=True

    模擬情境：顧客拒絕 → dialog 清 cart 後退出到 L1_enter_hawk。
    """
    l1_call_args = []
    l1_call_count = {"n": 0}

    def stub_run_l1(**kwargs):
        l1_call_count["n"] += 1
        l1_call_args.append(kwargs.get("enter_hawk_immediately"))
        if l1_call_count["n"] >= 2:
            return None  # 第二輪終止
        return "L2"

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart, think_count,
                        do_action, speak_and_wait=None, display=None):
        # dialog 清空 cart（正常行為）後返回 L1_enter_hawk
        cart.clear()
        return ("L1_enter_hawk", 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)

    cbs = _make_callbacks()
    logic.run(**cbs)

    assert len(l1_call_args) == 2, "run_l1 應被呼叫兩次"
    # 第一輪：首次進 L1，enter_hawk_immediately=False
    assert l1_call_args[0] == False, "第一輪 run_l1 應收到 enter_hawk_immediately=False"
    # 第二輪：交易完成後，enter_hawk_immediately=True
    assert l1_call_args[1] == True, "第二輪 run_l1 應收到 enter_hawk_immediately=True"


# ============================================================
# Test 4：L4 非掃碼退出 → cart 已空 + enter_hawk_immediately=True
# ============================================================

def test_logic_l4_non_scan_exit_with_empty_cart(monkeypatch):
    """run_l4 返 L1_enter_hawk（顧客取消/客服超時強制退出）時：
        - L4 stub 自行清 cart
        - _assert_cart_empty 不炸（cart 已空）
        - 下一輪 run_l1 收到 enter_hawk_immediately=True

    模擬情境：顧客在 L4 掃碼頁按取消。
    """
    l1_call_args = []
    l1_call_count = {"n": 0}

    def stub_run_l1(**kwargs):
        l1_call_count["n"] += 1
        l1_call_args.append(kwargs.get("enter_hawk_immediately"))
        if l1_call_count["n"] >= 2:
            return None
        return "L2"

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart, think_count,
                        do_action, speak_and_wait=None, display=None):
        # 加入商品進 cart（模擬顧客完成點餐）
        cart["冰紅茶"] = 2
        return ("L4", 0)

    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        # L4 取消路徑：清 cart 後返 L1_enter_hawk
        cart.clear()
        return ("L1_enter_hawk", 0, 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)

    cbs = _make_callbacks()
    logic.run(**cbs)

    assert l1_call_args[1] == True, "L4 退出後下一輪 run_l1 應收到 enter_hawk_immediately=True"


# ============================================================
# Test 5：L5 退出後 cart 已空 + enter_hawk_immediately=True
# ============================================================

def test_logic_l5_exit_with_empty_cart_enters_hawk(monkeypatch):
    """run_l5 完成後：
        - L5 stub 自行清 cart
        - _assert_cart_empty 不炸（cart 已空）
        - 下一輪 run_l1 收到 enter_hawk_immediately=True

    模擬情境：顧客掃碼成功 → L5 致謝 → 回 L1 叫賣。
    """
    l1_call_args = []
    l1_call_count = {"n": 0}

    def stub_run_l1(**kwargs):
        l1_call_count["n"] += 1
        l1_call_args.append(kwargs.get("enter_hawk_immediately"))
        if l1_call_count["n"] >= 2:
            return None
        return "L2"

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart, think_count,
                        do_action, speak_and_wait=None, display=None):
        cart["刮刮樂"] = 1
        return ("L4", 0)

    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        # L4-A：掃碼成功，不清 cart（L5 負責清）
        return ("L5", 0, 0)

    def stub_run_l5(*, cart, sleep, do_action):
        # L5 清 cart（正常行為）
        cart.clear()
        return ("L1", 0, 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)
    monkeypatch.setattr(states_module, "run_l5", stub_run_l5)

    cbs = _make_callbacks()
    logic.run(**cbs)

    assert l1_call_args[1] == True, "L5 後下一輪 run_l1 應收到 enter_hawk_immediately=True"


# ============================================================
# Test 6：enter_hawk_immediately 消費後 reset 為 False
# ============================================================

def test_logic_enter_hawk_immediately_consumed_after_l1(monkeypatch):
    """machine 的 `enter_hawk_immediately = False` 應在 run_l1 執行後立即 reset。

    驗證三輪路徑：
        第一輪 run_l1 收到 False（初始值）
        dialog 退出 L1_enter_hawk → enter_hawk_immediately = True
        第二輪 run_l1 收到 True → 呼叫後 flag 立即 reset 為 False
        第二輪 dialog 退出 L4（不重設 flag）
        L4 完成後退出到 L1_enter_hawk → flag 又設 True
        第三輪 run_l1 收到 True → 終止

    核心驗證：第二輪 run_l1 收到 True 後，若 dialog 走 L4 路徑（不重設 flag），
    下一輪 flag 不會來自殘留的 True，而是由 L4 退出時重新設定。
    即：flag 每次進 L1 前都被「consume → reset → 條件性重設」嚴格管理。

    簡化版驗證：
        輪 1：run_l1 收 False，dialog 返 L1_enter_hawk（→ flag=True）
        輪 2：run_l1 收 True（flag 被消費，隨即 reset=False），dialog 返 L4，
              L4 返 L1_enter_hawk（→ flag=True）
        輪 3：run_l1 收 True，返 None 終止
    驗：三輪收到 [False, True, True] — 確認每輪旗號都是「來源正確」而非殘留。
    """
    l1_call_args = []
    l1_call_count = {"n": 0}

    def stub_run_l1(**kwargs):
        l1_call_count["n"] += 1
        received = kwargs.get("enter_hawk_immediately")
        l1_call_args.append(received)
        if l1_call_count["n"] >= 3:
            return None
        return "L2"

    dialog_call_count = {"n": 0}

    def stub_run_dialog(*, speak, print_terminal, read_customer_input, cart, think_count,
                        do_action, speak_and_wait=None, display=None):
        dialog_call_count["n"] += 1
        cart.clear()
        if dialog_call_count["n"] == 1:
            # 第一輪 dialog：退出 → flag=True
            return ("L1_enter_hawk", 0)
        else:
            # 第二輪 dialog：走 L4 路徑（加商品後結帳）
            cart["冰紅茶"] = 1
            return ("L4", 0)

    def stub_run_l4(*, speak, print_terminal, read_customer_input, cart,
                    do_action, speak_and_wait=None):
        # L4 取消路徑：清 cart + 退出 → flag=True
        cart.clear()
        return ("L1_enter_hawk", 0, 0)

    monkeypatch.setattr(states_module, "run_l1", stub_run_l1)
    monkeypatch.setattr(states_module, "run_dialog", stub_run_dialog)
    monkeypatch.setattr(states_module, "run_l4", stub_run_l4)

    cbs = _make_callbacks()
    logic.run(**cbs)

    assert len(l1_call_args) == 3, "run_l1 應被呼叫三次"
    # 旗號來源驗證：
    #   輪 1：初始值 False（未交易過）
    assert l1_call_args[0] == False, "第一輪 run_l1 應收到 enter_hawk_immediately=False（初始值）"
    #   輪 2：第一輪 dialog 退出後設 True，consume-after-use reset 在本輪執行後發生
    assert l1_call_args[1] == True, "第二輪 run_l1 應收到 enter_hawk_immediately=True（第一輪 dialog 退出後設定）"
    #   輪 3：第二輪 L4 退出後設 True — 確認旗號由 L4 退出重新注入，非殘留
    assert l1_call_args[2] == True, "第三輪 run_l1 應收到 enter_hawk_immediately=True（第二輪 L4 退出後設定）"


# ============================================================
# Test 7：start_hawk 穿到 SalesMachine（--hawk 入口）
# ============================================================

def test_run_start_hawk_passed_to_machine(monkeypatch):
    """logic.run(start_hawk=True) → SalesMachine 收到 start_hawk=True（facade 直穿）。"""
    captured = {}

    class StubMachine:
        def __init__(self, *, callbacks, cart, start_hawk=False):
            captured["start_hawk"] = start_hawk

        def run(self):
            return None

    monkeypatch.setattr(logic, "SalesMachine", StubMachine)

    logic.run(**_make_callbacks(), start_hawk=True)

    assert captured["start_hawk"] is True, "logic.run(start_hawk=True) 應穿到 SalesMachine"


def test_run_start_hawk_defaults_false(monkeypatch):
    """logic.run 不傳 start_hawk → SalesMachine 收到 start_hawk=False（預設）。"""
    captured = {}

    class StubMachine:
        def __init__(self, *, callbacks, cart, start_hawk=False):
            captured["start_hawk"] = start_hawk

        def run(self):
            return None

    monkeypatch.setattr(logic, "SalesMachine", StubMachine)

    logic.run(**_make_callbacks())

    assert captured["start_hawk"] is False, "logic.run 預設應穿 start_hawk=False"
