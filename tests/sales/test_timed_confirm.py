"""test_timed_confirm.py — 測試 myProgram/sales/states/_timed_confirm.py（W3 oop_w3）。

TimedConfirm 多型家族（Template Method）類別層測試。**不重複 facade 行為網**
（test_cancel_confirm / test_service_confirm / test_invalid_qty_reask 已守對外行為），
本檔只測：
    - 骨架 hook 順序 + is-not-None 返回語意（含 classify 回 False 必立即返回）
    - 亂答不重置 deadline
    - 四個模組級單例 config 接線（prompt / timeout / allow_scan）
    - 各子類別 classify 行序 / on_enter / on_unclear 抽查

骨架測試用測試內自訂 micro 子類別 + 小 timeout（0.01~0.05）+ scripted lambda，禁 sleep。
"""

from myProgram.sales.states._timed_confirm import (
    TimedConfirm,
    CancelConfirm,
    ServiceConfirm,
    InvalidQtyCancelConfirm,
    CANCEL_CONFIRM,
    SERVICE_CONFIRM,
    SERVICE_CONFIRM_SCAN,
    INVALID_QTY_CANCEL_CONFIRM,
)
from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.constants import (
    CANCEL_CONFIRM_PROMPT,
    CANCEL_CONFIRM_TIMEOUT,
    L4_C_CONFIRM_TIMEOUT,
    L4_C_CONFIRM_PROMPT_TEMPLATE,
    L4_UNCLEAR_NOTICE,
    SERVICE_PHONE,
    INVALID_QTY_CANCEL_CONFIRM_PROMPT,
    INVALID_QTY_CANCEL_CONFIRM_TIMEOUT,
    INVALID_QTY_UNCLEAR_PREFIX,
)


class FakeCustomerInput:
    """模擬顧客輸入序列（耗盡後回 None = silent timeout）。"""

    def __init__(self, sequence: list) -> None:
        self._seq = list(sequence)

    def read(self, timeout: float) -> str | None:
        if not self._seq:
            return None
        return self._seq.pop(0)


def _make_io(speak_calls=None, terminal_calls=None, sequence=None, speak_blocking_calls=None):
    """組 scripted DialogIO：speak / speak_and_wait 各自記錄、read 走序列。"""
    speak_calls = speak_calls if speak_calls is not None else []
    terminal_calls = terminal_calls if terminal_calls is not None else []
    speak_blocking_calls = speak_blocking_calls if speak_blocking_calls is not None else []
    customer_input = FakeCustomerInput(sequence if sequence is not None else [])
    return DialogIO(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=customer_input.read,
        print_terminal=lambda text: terminal_calls.append(text),
        speak_and_wait=lambda text: speak_blocking_calls.append(text),
    )


# ============================================================
# 骨架測試（micro 子類別，小 timeout，禁 sleep）
# ============================================================

class _RecordingConfirm(TimedConfirm):
    """事件記錄 micro 子類別：classify 由建構時 scripted dict 決定。"""

    prompt = "MICRO_PROMPT"
    timeout = 0.05

    def __init__(self, classify_map, timeout_result="TIMED_OUT"):
        self._classify_map = classify_map
        self._timeout_result = timeout_result
        self.events: list = []

    def on_enter(self, io):
        self.events.append("on_enter")

    def classify(self, response):
        self.events.append(f"classify:{response}")
        return self._classify_map.get(response)  # 缺 key → None（亂答）

    def on_timeout(self):
        self.events.append("on_timeout")
        return self._timeout_result

    def on_unclear(self, io):
        self.events.append("on_unclear")


def test_skeleton_on_enter_precedes_prompt_speak() -> None:
    """hook 順序：on_enter 先於 prompt 的 speak_blocking。"""
    blocking_calls: list = []
    confirm = _RecordingConfirm(classify_map={"yes": "DONE"})
    io = _make_io(sequence=["yes"], speak_blocking_calls=blocking_calls)

    confirm.run(io)

    # on_enter 必在 events[0]；prompt 在 speak_blocking_calls[0]
    assert confirm.events[0] == "on_enter", f"on_enter 應最先，實際:{confirm.events}"
    assert blocking_calls[0] == "MICRO_PROMPT", (
        f"prompt 應透過 speak_blocking 播放，實際:{blocking_calls}"
    )
    # on_enter 在 prompt 之前：blocking_calls 在 events 記錄 on_enter 後才有第一筆
    # （以 events 第一筆為 on_enter 佐證順序）


def test_skeleton_classify_non_none_string_returns_immediately() -> None:
    """classify 回非 None 字串 → 立即返回該值，不續迴圈。"""
    confirm = _RecordingConfirm(classify_map={"go": "RESULT_X"})
    io = _make_io(sequence=["go", "should_not_reach"])

    result = confirm.run(io)

    assert result == "RESULT_X"
    assert confirm.events.count("classify:go") == 1
    assert "classify:should_not_reach" not in confirm.events, "命中即返回，不應讀第二筆"


def test_skeleton_classify_false_returns_false_immediately() -> None:
    """⚠️ classify 回 False → 立即返回 False（is-not-None 語意核心）。

    False 是 CancelConfirm NO 的合法返回值；若骨架用 truthiness 判斷會把 False 當
    亂答續迴圈 → 顧客「不要取消」被吃掉。這條防 if outcome: 的回歸 bug。
    """
    confirm = _RecordingConfirm(classify_map={"no": False})
    io = _make_io(sequence=["no", "extra"])

    result = confirm.run(io)

    assert result is False, f"classify 回 False 必須立即返回 False，實際:{result!r}"
    assert "classify:extra" not in confirm.events, "False 不得被當亂答續迴圈"


def test_skeleton_classify_none_triggers_on_unclear_then_continues() -> None:
    """classify 回 None → on_unclear 被呼叫、迴圈續跑，下一筆命中即返回。"""
    confirm = _RecordingConfirm(classify_map={"hit": "OK"})  # "gibberish" 不在 map → None
    io = _make_io(sequence=["gibberish", "hit"])

    result = confirm.run(io)

    assert result == "OK"
    assert confirm.events == [
        "on_enter",
        "classify:gibberish",
        "on_unclear",
        "classify:hit",
    ], f"亂答應觸發 on_unclear 後續跑，實際:{confirm.events}"


def test_skeleton_silent_read_returns_on_timeout_result() -> None:
    """read 回 None（silent）→ 返回 on_timeout 結果。"""
    confirm = _RecordingConfirm(classify_map={}, timeout_result="TIMEOUT_VAL")
    io = _make_io(sequence=[None])

    result = confirm.run(io)

    assert result == "TIMEOUT_VAL"
    assert "on_timeout" in confirm.events


def test_skeleton_gibberish_does_not_reset_deadline() -> None:
    """亂答不重置 deadline：micro timeout + 連續亂答 → 最終返回 on_timeout 結果。

    monkey-patch time.monotonic 模擬 wall-clock 推進（避免實際等待）：
    deadline 計算 → 0；首次 remaining check → 0；亂答後第二次 check → 超過 timeout。
    """
    import myProgram.sales.states._timed_confirm as tc_module

    times = iter([0.0, 0.0, 99.0])  # 第三次已超過 0.05 timeout

    def fake_monotonic():
        try:
            return next(times)
        except StopIteration:
            return 99.0

    original = tc_module.time.monotonic
    tc_module.time.monotonic = fake_monotonic
    try:
        confirm = _RecordingConfirm(classify_map={}, timeout_result="EXHAUSTED")
        io = _make_io(sequence=["亂答1", "亂答2"])
        result = confirm.run(io)
        assert result == "EXHAUSTED", "亂答耗盡 budget 應返回 on_timeout 結果（無重置）"
    finally:
        tc_module.time.monotonic = original


def test_skeleton_on_unclear_default_is_silent_noop() -> None:
    """TimedConfirm 預設 on_unclear 為 no-op（不 speak）。"""

    class _MinimalConfirm(TimedConfirm):
        prompt = "P"
        timeout = 0.05

        def classify(self, response):
            return "HIT" if response == "ok" else None

        def on_timeout(self):
            return "TO"

    speak_calls: list = []
    confirm = _MinimalConfirm()
    io = _make_io(speak_calls=speak_calls, sequence=["x", "ok"])

    result = confirm.run(io)

    assert result == "HIT"
    assert speak_calls == [], f"預設 on_unclear 應 silent，實際 speak:{speak_calls}"


# ============================================================
# 單例 config 接線
# ============================================================

def test_cancel_confirm_singleton_config() -> None:
    """CANCEL_CONFIRM 接 CANCEL_CONFIRM_PROMPT / TIMEOUT。"""
    assert isinstance(CANCEL_CONFIRM, CancelConfirm)
    assert CANCEL_CONFIRM.prompt is CANCEL_CONFIRM_PROMPT
    assert CANCEL_CONFIRM.timeout == CANCEL_CONFIRM_TIMEOUT


def test_service_confirm_singletons_config() -> None:
    """SERVICE_CONFIRM / SERVICE_CONFIRM_SCAN 接 allow_scan + L4 timeout。"""
    assert isinstance(SERVICE_CONFIRM, ServiceConfirm)
    assert isinstance(SERVICE_CONFIRM_SCAN, ServiceConfirm)
    assert SERVICE_CONFIRM.allow_scan is False
    assert SERVICE_CONFIRM_SCAN.allow_scan is True
    assert SERVICE_CONFIRM.timeout == L4_C_CONFIRM_TIMEOUT
    assert SERVICE_CONFIRM_SCAN.timeout == L4_C_CONFIRM_TIMEOUT


def test_invalid_qty_singleton_config() -> None:
    """INVALID_QTY_CANCEL_CONFIRM 接 INVALID_QTY timeout。"""
    assert isinstance(INVALID_QTY_CANCEL_CONFIRM, InvalidQtyCancelConfirm)
    assert INVALID_QTY_CANCEL_CONFIRM.timeout == INVALID_QTY_CANCEL_CONFIRM_TIMEOUT


# ============================================================
# 行為抽查（scripted DialogIO，類別層）
# ============================================================

def test_cancel_confirm_no_returns_false() -> None:
    """CancelConfirm「不要取消」→ classify 回 False → run 返回 False。"""
    io = _make_io(sequence=["不要取消"])
    assert CANCEL_CONFIRM.run(io) is False


def test_cancel_confirm_yes_returns_true() -> None:
    """CancelConfirm「取消」→ True。"""
    io = _make_io(sequence=["取消"])
    assert CANCEL_CONFIRM.run(io) is True


def test_cancel_confirm_silent_returns_true() -> None:
    """CancelConfirm silent → on_timeout = True（保守取消）。"""
    io = _make_io(sequence=[None])
    assert CANCEL_CONFIRM.run(io) is True


def test_service_confirm_scan_first_in_classify() -> None:
    """SERVICE_CONFIRM_SCAN 收 "s" → "scan"（scan 行序最先，allow_scan=True）。"""
    io = _make_io(sequence=["s"])
    assert SERVICE_CONFIRM_SCAN.run(io) == "scan"


def test_service_confirm_no_scan_treats_s_as_unclear() -> None:
    """SERVICE_CONFIRM（allow_scan=False）收 "s" → 走亂答（speak L4_UNCLEAR_NOTICE）後下一筆「好」→ "yes"。"""
    speak_calls: list = []
    io = _make_io(speak_calls=speak_calls, sequence=["s", "好"])

    result = SERVICE_CONFIRM.run(io)

    assert result == "yes"
    assert L4_UNCLEAR_NOTICE in speak_calls, (
        f"allow_scan=False 收 's' 應走亂答 speak L4_UNCLEAR_NOTICE，實際:{speak_calls}"
    )


def test_service_confirm_on_enter_prints_phone() -> None:
    """ServiceConfirm on_enter → print_terminal(SERVICE_PHONE)。"""
    terminal_calls: list = []
    io = _make_io(terminal_calls=terminal_calls, sequence=["是的"])

    SERVICE_CONFIRM.run(io)

    assert SERVICE_PHONE in terminal_calls, (
        f"on_enter 應 print SERVICE_PHONE，實際:{terminal_calls}"
    )


def test_service_confirm_prompt_uses_timeout_seconds() -> None:
    """ServiceConfirm prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)。"""
    expected = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert SERVICE_CONFIRM.prompt == expected
    assert SERVICE_CONFIRM_SCAN.prompt == expected


def test_invalid_qty_exit_keyword_returns_exit() -> None:
    """InvalidQtyCancelConfirm「退出」→ "exit"。"""
    io = _make_io(sequence=["退出"])
    assert INVALID_QTY_CANCEL_CONFIRM.run(io) == "exit"


def test_invalid_qty_silent_returns_cancel_overlimit() -> None:
    """InvalidQtyCancelConfirm silent → "cancel_overlimit"（保 cart）。"""
    io = _make_io(sequence=[None])
    assert INVALID_QTY_CANCEL_CONFIRM.run(io) == "cancel_overlimit"


def test_invalid_qty_unclear_replays_with_prefix() -> None:
    """InvalidQtyCancelConfirm 亂答 → on_unclear speak_blocking 帶 INVALID_QTY_UNCLEAR_PREFIX 開頭重播。"""
    blocking_calls: list = []
    io = _make_io(sequence=["亂答", "退出"], speak_blocking_calls=blocking_calls)

    result = INVALID_QTY_CANCEL_CONFIRM.run(io)

    assert result == "exit"
    # blocking_calls[0] = prompt（on_enter 後）；亂答後的重播帶前綴
    replays = [c for c in blocking_calls if c.startswith(INVALID_QTY_UNCLEAR_PREFIX)]
    assert replays, f"亂答應 speak_blocking 帶 INVALID_QTY_UNCLEAR_PREFIX 重播，實際:{blocking_calls}"
    expected_replay = INVALID_QTY_UNCLEAR_PREFIX + INVALID_QTY_CANCEL_CONFIRM_PROMPT
    assert expected_replay in blocking_calls, (
        f"重播應為 PREFIX + prompt，實際:{blocking_calls}"
    )
