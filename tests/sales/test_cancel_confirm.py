"""test_cancel_confirm.py — 測試 myProgram/sales/states/_cancel_confirm.py。

2026-05-29 加：cross-cutting cancel intent + 6s confirm 子狀態 helper。

設計（跟 _dialog_c2_second_stage 一致 wall-clock pattern）：
    - speak CANCEL_CONFIRM_PROMPT，6s budget
    - YES keyword 命中 → return True（取消）
    - NO keyword 命中 → return False（不取消）
    - silent / timeout → return True（user 字面 promise「6 秒後系統將自動取消」）
    - 亂答 → 消耗 budget；budget 耗盡 → return True
    - NO 先 check 避免「不要取消」substring 誤命中 YES「取消」
"""

from myProgram.sales.states._cancel_confirm import cancel_confirm
from myProgram.sales.constants import (
    CANCEL_CONFIRM_TIMEOUT,
    CANCEL_CONFIRM_PROMPT,
)


class FakeCustomerInput:
    """模擬顧客輸入序列，支援 timeout 語義（取自 test_states.py pattern）。"""

    def __init__(self, sequence: list) -> None:
        self._seq = list(sequence)

    def read(self, timeout: float) -> str | None:
        if not self._seq:
            return None
        return self._seq.pop(0)


# ============================================================
# CANCEL-CONFIRM-001：YES keyword 立即 return True
# ============================================================

def test_cancel_confirm_yes_keyword_returns_true() -> None:
    """YES keyword 命中 → 立即 return True（取消確認）。"""
    speak_calls: list = []
    customer_input = FakeCustomerInput(["是的"])

    result = cancel_confirm(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=customer_input.read,
    )

    assert result is True, "YES keyword 應 return True"
    assert CANCEL_CONFIRM_PROMPT in speak_calls, (
        f"應 speak CANCEL_CONFIRM_PROMPT，實際：{speak_calls}"
    )


def test_cancel_confirm_strict_short_yes_returns_true() -> None:
    """strict-short YES（如「是」）也應 return True。"""
    speak_calls: list = []
    customer_input = FakeCustomerInput(["是"])

    result = cancel_confirm(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=customer_input.read,
    )

    assert result is True, "strict-short YES 應 return True"


def test_cancel_confirm_cancel_keyword_strict_short_returns_true() -> None:
    """strict-short「取消」應 return True（顧客重複確認取消）。"""
    customer_input = FakeCustomerInput(["取消"])

    result = cancel_confirm(
        speak=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result is True, "「取消」strict-short 應 return True"


# ============================================================
# CANCEL-CONFIRM-002：NO keyword return False
# ============================================================

def test_cancel_confirm_no_keyword_returns_false() -> None:
    """NO keyword 命中 → return False（繼續交易）。"""
    customer_input = FakeCustomerInput(["不要取消"])

    result = cancel_confirm(
        speak=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result is False, "NO keyword 應 return False"


def test_cancel_confirm_strict_short_no_returns_false() -> None:
    """strict-short NO（如「否」/「繼續」）應 return False。"""
    customer_input = FakeCustomerInput(["繼續"])

    result = cancel_confirm(
        speak=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result is False, "strict-short「繼續」應 return False"


# ============================================================
# CANCEL-CONFIRM-003：silent timeout → True
# ============================================================

def test_cancel_confirm_silent_timeout_returns_true() -> None:
    """silent（read 回 None）→ return True（user 字面 promise）。"""
    customer_input = FakeCustomerInput([None])

    result = cancel_confirm(
        speak=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result is True, "silent timeout 應 return True（自動取消）"


# ============================================================
# CANCEL-CONFIRM-004：亂答耗盡 budget → True
# ============================================================

def test_cancel_confirm_gibberish_exhausts_budget_returns_true() -> None:
    """亂答消耗 budget 不重置；耗盡後 return True。

    用 monkey-patch time.monotonic 模擬 wall-clock 推進，避免實際等 6s。
    """
    import myProgram.sales.states._cancel_confirm as cc_module

    # 第一次（deadline 計算）→ 0；第二次（remaining check）→ 0；亂答後 → 7（超過 6s）
    times = iter([0.0, 0.0, 7.0])
    original_monotonic = cc_module.time.monotonic

    def fake_monotonic():
        try:
            return next(times)
        except StopIteration:
            return 7.0

    cc_module.time.monotonic = fake_monotonic
    try:
        customer_input = FakeCustomerInput(["哈囉"])  # 不命中 YES/NO
        result = cancel_confirm(
            speak=lambda text: None,
            read_customer_input=customer_input.read,
        )
        assert result is True, "亂答耗盡 budget 應 return True"
    finally:
        cc_module.time.monotonic = original_monotonic


# ============================================================
# CANCEL-CONFIRM-005：NO 優先 — 「不要取消」不應誤命中 YES 的「取消」substring
# ============================================================

def test_cancel_confirm_no_priority_over_yes_substring() -> None:
    """「不要取消」應 hit NO（False），不被 YES「取消」substring 誤命中。

    這是 conservative 設計核心：顧客明確說「不要取消」必須被當作「不取消」處理，
    保護顧客錢包 — 不能因為字串含「取消」就被當作確認取消。
    """
    customer_input = FakeCustomerInput(["不要取消"])

    result = cancel_confirm(
        speak=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result is False, (
        "「不要取消」必須 hit NO（False），不應誤命中 YES「取消」substring"
    )


# ============================================================
# CANCEL-CONFIRM-006：read 用剩餘 budget（不超過 CANCEL_CONFIRM_TIMEOUT）
# ============================================================

def test_cancel_confirm_first_read_uses_full_budget() -> None:
    """第一次 read 應傳 ~CANCEL_CONFIRM_TIMEOUT 秒（容許小誤差）。"""
    captured_timeouts: list = []

    def capture_read(timeout):
        captured_timeouts.append(timeout)
        return "是的"

    cancel_confirm(
        speak=lambda text: None,
        read_customer_input=capture_read,
    )

    assert len(captured_timeouts) == 1
    assert abs(captured_timeouts[0] - CANCEL_CONFIRM_TIMEOUT) < 0.1, (
        f"第一次 read timeout 應 ~{CANCEL_CONFIRM_TIMEOUT}s，"
        f"實際：{captured_timeouts[0]}"
    )
