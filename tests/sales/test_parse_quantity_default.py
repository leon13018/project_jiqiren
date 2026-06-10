"""test_parse_quantity_default.py — 測試 parse_quantity 的 default= 參數（W1 oop_w1）。

對應 spec：resources/specs/oop_w1_2026-06-10_spec.md §2-4。
parse_quantity 與 _parse_quantity_in_window 合併 — 用 default 參數區分 fallback：
    default=1（既有 caller 預設）/ default=None（原 _parse_quantity_in_window fallback 語意）。
"""

from myProgram.sales.nlu import parse_quantity


def test_no_number_returns_default_none() -> None:
    """無數字 + default=None → 回 None（原 _parse_quantity_in_window 語意）。"""
    assert parse_quantity("好的", default=None) is None


def test_no_number_default_one_explicit() -> None:
    """無數字 + default=1 → 回 1（既有預設）。"""
    assert parse_quantity("好的", default=1) == 1


def test_no_number_default_omitted_is_one() -> None:
    """無數字 + 不傳 default → 回 1（既有預設不變，向後相容）。"""
    assert parse_quantity("好的") == 1


def test_explicit_zero_returns_zero_regardless_of_default() -> None:
    """顯式 0（阿拉伯）→ 回 0，與 default 無關（B16）。"""
    assert parse_quantity("0 瓶", default=None) == 0
    assert parse_quantity("0 瓶", default=1) == 0


def test_compound_chinese_unaffected_by_default() -> None:
    """複合中文「三十五」→ 35，不受 default 影響。"""
    assert parse_quantity("三十五", default=None) == 35


def test_single_char_chinese_unaffected_by_default() -> None:
    """單字中文映射「兩瓶」→ 2，不受 default 影響。"""
    assert parse_quantity("兩瓶", default=None) == 2
