"""test_keyword_group.py — 測試 myProgram/sales/keyword_group.py（W1 oop_w1）。

對應 spec：resources/specs/oop_w1_2026-06-10_spec.md §2-1 / §2-2。

兩組：
    1. KeywordGroup 類別行為（matches = substring OR strict-short）
    2. 11 個 KG_* 配對實例接線（substrings / strict_short 對齊既有 list 常數）
"""

from myProgram.sales.keyword_group import KeywordGroup
from myProgram.sales.constants import (
    KG_CONFIRM_YES,
    KG_CONFIRM_NO,
    KG_C2_CONTINUE,
    KG_C2_CHECKOUT,
    KG_C2_CANCEL,
    KG_CANCEL_CONFIRM_YES,
    KG_CANCEL_CONFIRM_NO,
    KG_L4_C_CONFIRM_YES,
    KG_L4_C_CONFIRM_NO,
    KG_INVALID_QTY_CONTINUE,
    KG_INVALID_QTY_EXIT,
    KEYWORDS_CONFIRM_YES,
    KEYWORDS_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_CONFIRM_NO,
    KEYWORDS_CONFIRM_NO_STRICT_SHORT,
    KEYWORDS_C2_CONTINUE,
    KEYWORDS_C2_CONTINUE_STRICT_SHORT,
    KEYWORDS_C2_CHECKOUT,
    KEYWORDS_C2_CHECKOUT_STRICT_SHORT,
    KEYWORDS_C2_CANCEL,
    KEYWORDS_C2_CANCEL_STRICT_SHORT,
    KEYWORDS_CANCEL_CONFIRM_YES,
    KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_CANCEL_CONFIRM_NO,
    KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT,
    KEYWORDS_L4_C_CONFIRM_YES,
    KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_L4_C_CONFIRM_NO,
    KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT,
    KEYWORDS_INVALID_QTY_CONTINUE,
    KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT,
    KEYWORDS_INVALID_QTY_EXIT,
    KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT,
)


# ============================================================
# KeywordGroup 類別行為（matches = substring OR strict-short）
# ============================================================

def test_matches_substring_hit() -> None:
    """substring 命中：text 含 substring keyword → True。"""
    kg = KeywordGroup(("確認取消",), ("取消",))
    assert kg.matches("我要確認取消了") is True


def test_matches_substring_case_insensitive() -> None:
    """substring 大小寫不敏感。"""
    kg = KeywordGroup(("yes cancel",))
    assert kg.matches("YES Cancel") is True


def test_matches_strict_short_exact_only() -> None:
    """strict-short 完全相等才命中；非完全相等且無 substring 命中 → False。"""
    kg = KeywordGroup(("確認取消",), ("取消",))
    assert kg.matches("取消") is True
    assert kg.matches("取消會議") is False


def test_matches_strict_short_strips_and_lowercases() -> None:
    """strict-short 去頭尾空白 + 大小寫不敏感。"""
    kg = KeywordGroup(("確認取消",), ("取消",))
    assert kg.matches("  取消  ") is True
    kg_en = KeywordGroup((), ("yes",))
    assert kg_en.matches("  YES  ") is True


def test_matches_no_hit_returns_false() -> None:
    """substring + strict-short 皆未命中 → False。"""
    kg = KeywordGroup(("確認取消",), ("取消",))
    assert kg.matches("今天天氣很好") is False


def test_matches_default_empty_strict_short_pure_substring() -> None:
    """strict_short 預設空 tuple → 純 substring 行為。"""
    kg = KeywordGroup(("結帳",))
    assert kg.matches("我要結帳") is True
    assert kg.matches("結") is False  # 無 strict-short，單字不命中


# ============================================================
# 11 個 KG_* 配對實例接線（對照表抄 spec §2-2）
# ============================================================

def test_kg_confirm_yes_wired() -> None:
    assert KG_CONFIRM_YES.substrings == tuple(KEYWORDS_CONFIRM_YES)
    assert KG_CONFIRM_YES.strict_short == tuple(KEYWORDS_CONFIRM_YES_STRICT_SHORT)


def test_kg_confirm_no_wired() -> None:
    assert KG_CONFIRM_NO.substrings == tuple(KEYWORDS_CONFIRM_NO)
    assert KG_CONFIRM_NO.strict_short == tuple(KEYWORDS_CONFIRM_NO_STRICT_SHORT)


def test_kg_c2_continue_wired() -> None:
    assert KG_C2_CONTINUE.substrings == tuple(KEYWORDS_C2_CONTINUE)
    assert KG_C2_CONTINUE.strict_short == tuple(KEYWORDS_C2_CONTINUE_STRICT_SHORT)


def test_kg_c2_checkout_wired() -> None:
    assert KG_C2_CHECKOUT.substrings == tuple(KEYWORDS_C2_CHECKOUT)
    assert KG_C2_CHECKOUT.strict_short == tuple(KEYWORDS_C2_CHECKOUT_STRICT_SHORT)


def test_kg_c2_cancel_wired() -> None:
    assert KG_C2_CANCEL.substrings == tuple(KEYWORDS_C2_CANCEL)
    assert KG_C2_CANCEL.strict_short == tuple(KEYWORDS_C2_CANCEL_STRICT_SHORT)


def test_kg_cancel_confirm_yes_wired() -> None:
    assert KG_CANCEL_CONFIRM_YES.substrings == tuple(KEYWORDS_CANCEL_CONFIRM_YES)
    assert KG_CANCEL_CONFIRM_YES.strict_short == tuple(KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT)


def test_kg_cancel_confirm_no_wired() -> None:
    assert KG_CANCEL_CONFIRM_NO.substrings == tuple(KEYWORDS_CANCEL_CONFIRM_NO)
    assert KG_CANCEL_CONFIRM_NO.strict_short == tuple(KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT)


def test_kg_l4_c_confirm_yes_wired() -> None:
    assert KG_L4_C_CONFIRM_YES.substrings == tuple(KEYWORDS_L4_C_CONFIRM_YES)
    assert KG_L4_C_CONFIRM_YES.strict_short == tuple(KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT)


def test_kg_l4_c_confirm_no_wired() -> None:
    assert KG_L4_C_CONFIRM_NO.substrings == tuple(KEYWORDS_L4_C_CONFIRM_NO)
    assert KG_L4_C_CONFIRM_NO.strict_short == tuple(KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT)


def test_kg_invalid_qty_continue_wired() -> None:
    assert KG_INVALID_QTY_CONTINUE.substrings == tuple(KEYWORDS_INVALID_QTY_CONTINUE)
    assert KG_INVALID_QTY_CONTINUE.strict_short == tuple(KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT)


def test_kg_invalid_qty_exit_wired() -> None:
    assert KG_INVALID_QTY_EXIT.substrings == tuple(KEYWORDS_INVALID_QTY_EXIT)
    assert KG_INVALID_QTY_EXIT.strict_short == tuple(KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT)


# ============================================================
# 行為抽查（spec plan step 1：2 個跨集合行為驗證）
# ============================================================

def test_kg_cancel_confirm_no_behavior_spot_check() -> None:
    """「不要取消」應命中 NO（substring「不要取消」）。"""
    assert KG_CANCEL_CONFIRM_NO.matches("不要取消") is True


def test_kg_confirm_yes_behavior_spot_check() -> None:
    """「沒有錯」應命中 YES（substring「沒有錯」）。"""
    assert KG_CONFIRM_YES.matches("沒有錯") is True
