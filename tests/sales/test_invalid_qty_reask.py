"""invalid_qty_reask / invalid_qty_cancel_confirm 單元測試（2026-06-09）。"""
from myProgram.sales.states._invalid_qty_reask import (
    invalid_qty_reask, invalid_qty_cancel_confirm,
)
from myProgram.sales import cart as cart_module


class FakeInput:
    """依序回傳腳本中的回應；耗盡後回 None（模擬 timeout）。"""
    def __init__(self, scripted):
        self._items = list(scripted)

    def read(self, timeout):
        return self._items.pop(0) if self._items else None


# ============================================================
# invalid_qty_cancel_confirm（二選一，6s）
# ============================================================
def test_cancel_confirm_exit_keyword_returns_exit() -> None:
    speaks = []
    assert invalid_qty_cancel_confirm(
        speak=speaks.append, read_customer_input=FakeInput(["退出"]).read,
    ) == "exit"


def test_cancel_confirm_continue_keyword_returns_cancel_overlimit() -> None:
    assert invalid_qty_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput(["取消超量的商品繼續交易"]).read,
    ) == "cancel_overlimit"


def test_cancel_confirm_silent_defaults_cancel_overlimit() -> None:
    # silent（read 回 None）→ 保守保 cart
    assert invalid_qty_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput([]).read,
    ) == "cancel_overlimit"


def test_cancel_confirm_continue_checked_before_exit() -> None:
    # 「不想退出，繼續」含「退出」與「繼續」→ CONTINUE 先 check → cancel_overlimit
    assert invalid_qty_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput(["不想退出，繼續"]).read,
    ) == "cancel_overlimit"


def test_cancel_confirm_gibberish_then_exit() -> None:
    # 亂答不終結、不重置 → 再講退出 → exit
    speaks = []
    assert invalid_qty_cancel_confirm(
        speak=speaks.append, read_customer_input=FakeInput(["天氣真好", "退出"]).read,
    ) == "exit"
    assert any("無法判斷" in s for s in speaks)


# ============================================================
# invalid_qty_reask（主 loop，12s + 2 reset）
# ============================================================
def test_reask_single_resolved_adds_to_cart() -> None:
    cart = cart_module.new_cart()
    # pending 冰紅茶，顧客重答 "5" → 加 5 → resolved
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["5"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 5


def test_reask_multi_combined_prompt_and_resolve() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 兩商品同時超量；首 prompt 應合併列出；顧客一次重講 → 全加入
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit", "刮刮樂": "over_limit"}, cart, speak=speaks.append,
        print_terminal=lambda t: None, read_customer_input=FakeInput(["紅茶40刮刮樂30"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 40
    assert cart_module.get_quantity(cart, "刮刮樂") == 30
    assert any("冰紅茶和刮刮樂" in s and "各選購" in s for s in speaks)


def test_reask_partial_fix_keeps_ok_reprompts_remaining() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 紅茶40(OK) 刮刮樂9999(仍超) → reset 重列刮刮樂 → "30" → 全加入
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit", "刮刮樂": "over_limit"}, cart, speak=speaks.append,
        print_terminal=lambda t: None, read_customer_input=FakeInput(["紅茶40刮刮樂9999", "30"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 40
    assert cart_module.get_quantity(cart, "刮刮樂") == 30


def test_reask_silent_returns_reenter_timeout() -> None:
    cart = cart_module.new_cart()
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput([]).read,
    )
    assert r == "reenter_timeout"
    assert cart_module.is_empty(cart)


def test_reask_cancel_intent_then_continue_returns_reenter_cancel() -> None:
    cart = cart_module.new_cart()
    # 「不買了」→ 二選一 → 「取消這些商品繼續」→ reenter_cancel
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["不買了", "取消超量的商品繼續"]).read,
    )
    assert r == "reenter_cancel"


def test_reask_cancel_intent_then_exit_returns_exit_l1() -> None:
    cart = cart_module.new_cart()
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["不買了", "退出"]).read,
    )
    assert r == "exit_l1"


def test_reask_gibberish_does_not_reset_and_prompts() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 亂答一次 → speak 不明白 → 再答 "5" → resolved
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=speaks.append, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["天氣真好", "5"]).read,
    )
    assert r == "resolved"
    assert any("無法判斷" in s for s in speaks)


def test_apply_quantities_multi_pending_partial_name_no_leak() -> None:
    """多 pending 時顧客只報一個商品名 → 不可把該數字誤套到未提及的另一商品。"""
    from myProgram.sales.states._invalid_qty_reask import _apply_quantities
    cart = cart_module.new_cart()
    pending = {"冰紅茶": "over_limit", "刮刮樂": "over_limit"}
    _apply_quantities("刮刮樂5", pending, cart)
    assert cart_module.get_quantity(cart, "刮刮樂") == 5
    assert cart_module.get_quantity(cart, "冰紅茶") == 0   # 未提及 → 不應被設值
    assert pending == {"冰紅茶": "over_limit"}              # 仍待重問


def test_reask_service_yes_reprompts_then_resolve() -> None:
    cart = cart_module.new_cart()
    # 客服 → service_confirm YES → 重 prompt → "5" → resolved
    # （service_confirm YES keyword「繼續」/「好的」；NO keyword「不繼續」等）
    r = invalid_qty_reask(
        {"冰紅茶": "over_limit"}, cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["客服", "繼續", "5"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 5


# ============================================================
# Task 2：formatter 依 reason 分組 + dict pending + zero 文案
# ============================================================
def test_format_prompt_zero_single() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "zero"}, cart)
    assert "不接受" in s and "冰紅茶0瓶" in s and "請重新說" in s


def test_format_prompt_overlimit_single_unchanged() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "over_limit"}, cart)
    assert "最多只能選購 50 瓶" in s


def test_format_prompt_mixed_reasons_concatenated() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "zero", "刮刮樂": "over_limit"}, cart)
    assert "冰紅茶0瓶" in s and "不接受" in s          # zero 句
    assert "刮刮樂" in s and "最多只能選購" in s         # over 句


def test_reask_dict_overlimit_resolved_still_works() -> None:
    # over-limit 行為等價回歸：dict pending 單商品 over_limit → 重答 5 → resolved
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "over_limit"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["5"]).read)
    assert r == "resolved" and cart_module.get_quantity(cart, "冰紅茶") == 5


def test_reask_zero_then_valid_resolved() -> None:
    # zero pending → 顧客重答合法 7 → resolved（reason 機制驗證）
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "zero"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["7"]).read)
    assert r == "resolved" and cart_module.get_quantity(cart, "冰紅茶") == 7


def test_reask_zero_answer_again_stays_pending_reenter() -> None:
    # zero pending → 顧客又答 0（reset）→ 再 silent → reenter_timeout，未加入
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "zero"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["0"]).read)
    assert r == "reenter_timeout" and cart_module.is_empty(cart)


# ============================================================
# Task 3：混合 reason（zero + over_limit）合併進同一鏈
# ============================================================
def test_resolve_mixed_zero_and_overlimit_one_loop() -> None:
    """直接給『紅茶0刮刮樂9999』→ 合併進同一鏈，混合 reason → 重答全部 → 全加入。"""
    from myProgram.sales.states._l2_l3_qty_followup import resolve_and_add_products
    cart = cart_module.new_cart()
    speaks = []
    added, _notices, control = resolve_and_add_products(
        [("冰紅茶", 0), ("刮刮樂", 9999)], cart, speak=speaks.append,
        print_terminal=lambda t: None, read_customer_input=FakeInput(["紅茶4刮刮樂3"]).read,
        classify_intent_mode="l2",
    )
    assert control is None and added is True
    assert cart_module.get_quantity(cart, "冰紅茶") == 4
    assert cart_module.get_quantity(cart, "刮刮樂") == 3
