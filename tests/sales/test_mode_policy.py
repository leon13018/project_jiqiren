"""test_mode_policy.py — W4 ModePolicy（Strategy）+ DialogSession 接線與推導測試。

對應 spec：resources/specs/oop_w4_2026-06-10_spec.md（§2-1 policy 欄位表 + §2-2 session）。

範圍：
    - 兩 policy 全資料欄位接線（§2-1 表 9 欄逐一，含 think_limit 3/4、writeback flag）
    - L2_POLICY / L3_POLICY 是 ModePolicy 實例
    - session.policy() 依 cart 世界狀態即時推導、不快取（不變式 #8）
    - 行為抽查：空 cart main_loop timeout → hawk voice 轉 L1（L2 on_timeout hook 接線）

設計：純函式 lambda + FakeCustomerInput stub（與 test_states.py 一致），不用 mock library。
hooks 的細部行為由 test_states.py 既有 469 條回歸網覆蓋；本檔只證接線正確。
"""

from myProgram.sales.states.l2_l3_dialog import (
    ModePolicy,
    L2_POLICY,
    L3_POLICY,
    DialogSession,
)
from myProgram.sales import cart as cart_module
from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.constants import (
    DNC_TIMEOUT,
    DYC_TIMEOUT,
    L2_ENTRY_PROMPT,
    L3_ENTRY_PROMPT,
    L2_B1_CLARIFY,
    L3_B1_CLARIFY,
    L2_B3_REASK,
    L3_REASK,
    L2_CANCEL_DECLINED_RESUME,
    L3_CANCEL_DECLINED_RESUME,
    L2_TIMEOUT_TO_HAWK_VOICE,
)


class FakeCustomerInput:
    """模擬顧客輸入序列（與 test_states.py 同形）。"""

    def __init__(self, sequence: list) -> None:
        self._seq = list(sequence)

    def read(self, timeout: float) -> str | None:
        if not self._seq:
            return None
        return self._seq.pop(0)


# ============================================================
# §2-1：L2Policy 全資料欄位接線
# ============================================================

def test_l2_policy_is_mode_policy_instance() -> None:
    assert isinstance(L2_POLICY, ModePolicy)


def test_l2_policy_data_fields_wired() -> None:
    assert L2_POLICY.nlu_mode == "l2"
    assert L2_POLICY.read_timeout == DNC_TIMEOUT
    assert L2_POLICY.entry_prompt == L2_ENTRY_PROMPT
    assert L2_POLICY.clarify == L2_B1_CLARIFY
    assert L2_POLICY.reask == L2_B3_REASK
    assert L2_POLICY.cancel_declined_resume == L2_CANCEL_DECLINED_RESUME
    assert L2_POLICY.think_limit == 3
    assert L2_POLICY.service_yes_prompt == L2_ENTRY_PROMPT
    assert L2_POLICY.silence_think_writeback is False


# ============================================================
# §2-1：L3Policy 全資料欄位接線
# ============================================================

def test_l3_policy_is_mode_policy_instance() -> None:
    assert isinstance(L3_POLICY, ModePolicy)


def test_l3_policy_data_fields_wired() -> None:
    assert L3_POLICY.nlu_mode == "normal"
    assert L3_POLICY.read_timeout == DYC_TIMEOUT
    assert L3_POLICY.entry_prompt == L3_ENTRY_PROMPT
    assert L3_POLICY.clarify == L3_B1_CLARIFY
    assert L3_POLICY.reask == L3_REASK
    assert L3_POLICY.cancel_declined_resume == L3_CANCEL_DECLINED_RESUME
    assert L3_POLICY.think_limit == 4
    assert L3_POLICY.service_yes_prompt == L3_REASK
    assert L3_POLICY.silence_think_writeback is True


# ============================================================
# §2-2：session.policy() 依 cart 世界狀態即時推導、不快取（不變式 #8）
# ============================================================

def test_session_policy_empty_cart_is_l2() -> None:
    session = DialogSession(io=None, cart=cart_module.new_cart(), think_count=0)
    assert session.policy() is L2_POLICY


def test_session_policy_nonempty_cart_is_l3() -> None:
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    session = DialogSession(io=None, cart=cart, think_count=0)
    assert session.policy() is L3_POLICY


def test_session_policy_recomputed_not_cached_after_cart_changes() -> None:
    """同一 session：先空 cart → L2_POLICY；add_item 後再呼叫 → L3_POLICY（證不快取）。"""
    cart = cart_module.new_cart()
    session = DialogSession(io=None, cart=cart, think_count=0)
    assert session.policy() is L2_POLICY
    cart_module.add_item(cart, "冰紅茶", 1)
    assert session.policy() is L3_POLICY


# ============================================================
# 行為抽查：空 cart main_loop timeout → L2 on_timeout hook（hawk voice + 退 L1）
# ============================================================

def test_main_loop_empty_cart_timeout_returns_enter_hawk_with_hawk_voice() -> None:
    speak_calls: list = []
    io = DialogIO(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=FakeCustomerInput([None]).read,
        print_terminal=lambda text: None,
        do_action=lambda *a, **k: None,
    )
    session = DialogSession(io=io, cart=cart_module.new_cart(), think_count=0)

    result = session.main_loop()

    assert result == ("L1_enter_hawk", 0)
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls
