"""test_service_confirm.py — 測試 myProgram/sales/states/_service_confirm.py。

2026-05-31 加：跨層共用客服 confirm 子狀態 helper（抽 L4 既有 _l4_service_mode pattern）。

設計（跟 _cancel_confirm.py 對稱；語意 inverse）：
    - print SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE「請問是否繼續交易？12秒後將自動取消交易。」
    - 一次性 L4_C_CONFIRM_TIMEOUT=12s wall-clock budget
    - YES keyword 命中 → return "yes"
    - NO keyword 命中 → return "no"
    - silent / 倒數歸零 → return "no"（跟 prompt 字面「自動取消」對齊）
    - 終端 "s"（僅 allow_scan=True）→ return "scan"
    - 亂答 → speak L4_UNCLEAR_NOTICE + continue（不重置 12s budget）

NO 必須先 check 避免「不繼續」substring 含「繼續」strict_short 誤命中 YES。
"""

from myProgram.sales.states._service_confirm import service_confirm
from myProgram.sales.constants import (
    SERVICE_PHONE,
    L4_C_CONFIRM_TIMEOUT,
    L4_C_CONFIRM_PROMPT_TEMPLATE,
    L4_UNCLEAR_NOTICE,
)


class FakeCustomerInput:
    """模擬顧客輸入序列，支援 timeout 語義（取自 test_cancel_confirm.py pattern）。"""

    def __init__(self, sequence: list) -> None:
        self._seq = list(sequence)

    def read(self, timeout: float) -> str | None:
        if not self._seq:
            return None
        return self._seq.pop(0)


# ============================================================
# SERVICE-CONFIRM-001：YES keyword 立即 return "yes"
# ============================================================

def test_service_confirm_yes_keyword_returns_yes() -> None:
    """YES keyword 命中 → 立即 return "yes"。"""
    speak_calls: list = []
    terminal_calls: list = []
    customer_input = FakeCustomerInput(["是的"])

    result = service_confirm(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
    )

    assert result == "yes", f"YES keyword 應 return 'yes'，實際:{result!r}"
    assert SERVICE_PHONE in terminal_calls, (
        f"應 print_terminal(SERVICE_PHONE)，實際:{terminal_calls}"
    )
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_prompt in speak_calls, (
        f"應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際:{speak_calls}"
    )


def test_service_confirm_strict_short_yes_returns_yes() -> None:
    """strict-short YES（如「繼續」）應 return "yes"。"""
    customer_input = FakeCustomerInput(["繼續"])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "yes", f"strict-short「繼續」應 return 'yes'，實際:{result!r}"


# ============================================================
# SERVICE-CONFIRM-002：NO keyword return "no"
# ============================================================

def test_service_confirm_no_keyword_returns_no() -> None:
    """NO keyword 命中 → return "no"。"""
    customer_input = FakeCustomerInput(["取消交易"])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "no", f"NO keyword 應 return 'no'，實際:{result!r}"


def test_service_confirm_strict_short_no_returns_no() -> None:
    """strict-short NO（如「不要」）應 return "no"。"""
    customer_input = FakeCustomerInput(["不要"])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "no", f"strict-short「不要」應 return 'no'，實際:{result!r}"


# ============================================================
# SERVICE-CONFIRM-003：silent → "no"（自動取消）
# ============================================================

def test_service_confirm_silent_timeout_returns_no() -> None:
    """silent（read 回 None）→ return "no"（跟 prompt 字面「自動取消」對齊）。"""
    customer_input = FakeCustomerInput([None])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "no", f"silent 應 return 'no'（自動取消），實際:{result!r}"


# ============================================================
# SERVICE-CONFIRM-004：NO 優先 — 「不繼續」必須 hit NO（防 YES「繼續」strict_short）
# ============================================================

def test_service_confirm_no_priority_over_yes_substring() -> None:
    """「不繼續」應 hit NO（'no'），不被 YES「繼續」strict_short 誤命中。

    這是 conservative 設計核心：顧客明確說「不繼續」必須被當作「不要交易」處理。
    """
    customer_input = FakeCustomerInput(["不繼續"])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "no", (
        f"「不繼續」必須 hit NO，不應誤命中 YES「繼續」strict_short，實際:{result!r}"
    )


# ============================================================
# SERVICE-CONFIRM-005：allow_scan=True 時終端 "s" → "scan"
# ============================================================

def test_service_confirm_scan_returns_scan_when_allowed() -> None:
    """allow_scan=True + 顧客輸入 "s" → return "scan"（L4 caller 用）。"""
    customer_input = FakeCustomerInput(["s"])

    result = service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        allow_scan=True,
    )

    assert result == "scan", f"allow_scan=True + 's' 應 return 'scan'，實際:{result!r}"


# ============================================================
# SERVICE-CONFIRM-006：allow_scan=False 時終端 "s" 視為亂答（L2/L3 caller 不開放掃碼）
# ============================================================

def test_service_confirm_scan_treated_as_gibberish_when_disallowed() -> None:
    """allow_scan=False（預設）+ 顧客輸入 "s" → 視為亂答 speak L4_UNCLEAR_NOTICE。

    後續輸入 NO → return "no"，確認 "s" 沒被當作 scan 處理。
    """
    speak_calls: list = []
    # "s" → 亂答 → speak unclear；「不要」 → NO → return "no"
    customer_input = FakeCustomerInput(["s", "不要"])

    result = service_confirm(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        allow_scan=False,
    )

    assert result == "no", (
        f"allow_scan=False + 's' 應 fall through 亂答，後續 NO 應 return 'no'，"
        f"實際:{result!r}"
    )
    assert L4_UNCLEAR_NOTICE in speak_calls, (
        f"亂答 's' 應 speak L4_UNCLEAR_NOTICE，實際 speak:{speak_calls}"
    )


# ============================================================
# SERVICE-CONFIRM-007：亂答 → speak L4_UNCLEAR_NOTICE + continue（不重置 budget）
# ============================================================

def test_service_confirm_gibberish_speaks_unclear_and_continues() -> None:
    """亂答 → speak L4_UNCLEAR_NOTICE + 繼續等回應（不重置 budget）。

    後續輸入 YES → return "yes"，確認亂答不立即退出且不重置 budget。
    """
    speak_calls: list = []
    # 「你好」→ 亂答 → unclear；「繼續」 → YES → return "yes"
    customer_input = FakeCustomerInput(["你好", "繼續"])

    result = service_confirm(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
    )

    assert result == "yes", f"亂答後 YES 應 return 'yes'，實際:{result!r}"
    assert L4_UNCLEAR_NOTICE in speak_calls, (
        f"亂答應 speak L4_UNCLEAR_NOTICE，實際 speak:{speak_calls}"
    )


# ============================================================
# SERVICE-CONFIRM-008：亂答耗盡 budget → "no"
# ============================================================

def test_service_confirm_gibberish_exhausts_budget_returns_no() -> None:
    """亂答消耗 budget 不重置；耗盡後 return "no"。

    用 monkey-patch time.monotonic 模擬 wall-clock 推進，避免實際等 12s。
    """
    import myProgram.sales.states._service_confirm as sc_module

    # 第一次（deadline 計算）→ 0；第二次（remaining check）→ 0；亂答後 → 13（超過 12s）
    times = iter([0.0, 0.0, 13.0])
    original_monotonic = sc_module.time.monotonic

    def fake_monotonic():
        try:
            return next(times)
        except StopIteration:
            return 13.0

    sc_module.time.monotonic = fake_monotonic
    try:
        customer_input = FakeCustomerInput(["哈囉"])  # 不命中 YES/NO
        result = service_confirm(
            speak=lambda text: None,
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
        )
        assert result == "no", f"亂答耗盡 budget 應 return 'no'，實際:{result!r}"
    finally:
        sc_module.time.monotonic = original_monotonic


# ============================================================
# SERVICE-CONFIRM-009：第一次 read 用 ~L4_C_CONFIRM_TIMEOUT 秒
# ============================================================

def test_service_confirm_first_read_uses_full_budget() -> None:
    """第一次 read 應傳 ~L4_C_CONFIRM_TIMEOUT 秒（容許小誤差）。"""
    captured_timeouts: list = []

    def capture_read(timeout):
        captured_timeouts.append(timeout)
        return "繼續"

    service_confirm(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=capture_read,
    )

    assert len(captured_timeouts) == 1
    assert abs(captured_timeouts[0] - L4_C_CONFIRM_TIMEOUT) < 0.1, (
        f"第一次 read timeout 應 ~{L4_C_CONFIRM_TIMEOUT}s，"
        f"實際:{captured_timeouts[0]}"
    )


# ============================================================
# SERVICE-CONFIRM-010：speak_and_wait callback 優先於 speak（從 TTS 播完才起算 budget）
# ============================================================

def test_service_confirm_uses_speak_and_wait_for_prompt() -> None:
    """傳 speak_and_wait callback → prompt 走 speak_and_wait 阻塞版（不走 speak）。

    驗證 wall-clock budget 從 TTS 播完才起算 — production wire-up 必要 invariant。
    """
    speak_calls: list = []
    speak_and_wait_calls: list = []
    customer_input = FakeCustomerInput(["繼續"])

    service_confirm(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        speak_and_wait=lambda text: speak_and_wait_calls.append(text),
    )

    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_prompt in speak_and_wait_calls, (
        f"prompt 應走 speak_and_wait（阻塞），實際 speak_and_wait:{speak_and_wait_calls}"
    )
    assert expected_prompt not in speak_calls, (
        f"傳 speak_and_wait 後 prompt 不應走 speak，實際 speak:{speak_calls}"
    )
