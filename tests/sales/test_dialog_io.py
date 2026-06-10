"""test_dialog_io.py — 測試 myProgram/sales/dialog_io.py。

W2 oop_w2：DialogIO callback 束物件（frozen dataclass）。私有對話函式一律收 io 單參，
取代手傳 5-8 個 callback。speak_blocking 取代 8 處 `_speak_blocking = ... if ... else ...`
fallback 三元式，語意一字不差（is not None 判斷，非 truthiness）。
"""

import dataclasses

import pytest

from myProgram.sales.dialog_io import DialogIO


# ============================================================
# DIALOG-IO-001：speak_blocking 有 speak_and_wait → 呼叫它，speak 不被呼叫
# ============================================================

def test_speak_blocking_with_speak_and_wait_calls_it_not_speak() -> None:
    """有 speak_and_wait → speak_blocking 呼叫 speak_and_wait、speak 完全不被呼叫。"""
    speak_calls: list = []
    saw_calls: list = []
    io = DialogIO(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=lambda timeout: None,
        speak_and_wait=lambda text: saw_calls.append(text),
    )

    io.speak_blocking("阻塞播報")

    assert saw_calls == ["阻塞播報"], f"應呼叫 speak_and_wait，實際 saw_calls={saw_calls}"
    assert speak_calls == [], f"speak 不應被呼叫，實際 speak_calls={speak_calls}"


# ============================================================
# DIALOG-IO-002：無 speak_and_wait（None）→ fallback 呼叫 speak
# ============================================================

def test_speak_blocking_without_speak_and_wait_falls_back_to_speak() -> None:
    """speak_and_wait 為 None → speak_blocking fallback 呼叫 speak。"""
    speak_calls: list = []
    io = DialogIO(
        speak=lambda text: speak_calls.append(text),
        read_customer_input=lambda timeout: None,
    )

    io.speak_blocking("fallback 播報")

    assert speak_calls == ["fallback 播報"], (
        f"無 speak_and_wait 應 fallback speak，實際 speak_calls={speak_calls}"
    )


# ============================================================
# DIALOG-IO-003：欄位注入保持 — 建構後欄位即注入的 callback
# ============================================================

def test_fields_hold_injected_callbacks() -> None:
    """建構後 io.speak / io.read_customer_input 即注入的 callback 物件本身。"""
    def f(text):
        return None

    def g(timeout):
        return None

    io = DialogIO(speak=f, read_customer_input=g)

    assert io.speak is f, "speak 應為注入的 callback"
    assert io.read_customer_input is g, "read_customer_input 應為注入的 callback"


# ============================================================
# DIALOG-IO-004：print_terminal / do_action / speak_and_wait 預設 None
# ============================================================

def test_optional_fields_default_none() -> None:
    """print_terminal / do_action / speak_and_wait 不傳時預設 None（部分注入需求）。"""
    io = DialogIO(speak=lambda text: None, read_customer_input=lambda timeout: None)

    assert io.print_terminal is None, "print_terminal 預設應為 None"
    assert io.do_action is None, "do_action 預設應為 None"
    assert io.speak_and_wait is None, "speak_and_wait 預設應為 None"


# ============================================================
# DIALOG-IO-005：frozen — 對欄位賦值 raise FrozenInstanceError
# ============================================================

def test_frozen_disallows_field_reassignment() -> None:
    """frozen=True：callback 束建好不重指派，對 io.speak 賦值 raise FrozenInstanceError。"""
    io = DialogIO(speak=lambda text: None, read_customer_input=lambda timeout: None)

    with pytest.raises(dataclasses.FrozenInstanceError):
        io.speak = lambda text: None
