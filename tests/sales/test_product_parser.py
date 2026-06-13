"""test_product_parser.py — 測試 myProgram/sales/product_parser.py。

對應 BDD scenarios：
    - L0-NLU-PARSE-PRODUCTS-001 ~ 008：多商品解析（B 方案）
    - P4 regression：含 filler 詞 / 長短 keyword 去重 / 中文數量

（2026-05-26 P7 從 test_nlu.py 拆出）
"""

from myProgram.sales import product_parser


# ============================================================
# L0-NLU-PARSE-PRODUCTS-001 ~ 008（2026-05-25 加，B 方案 multi-product）
# ============================================================

def test_parse_products_empty_input_returns_empty_list() -> None:
    assert product_parser.parse_products("") == []
    assert product_parser.parse_products("今天天氣很好") == []


def test_parse_products_single_with_quantity() -> None:
    result = product_parser.parse_products("冰紅茶 2")
    assert result == [("冰紅茶", 2)]


def test_parse_products_single_without_quantity_returns_none_qty() -> None:
    """單商品無數量 → qty 為 None（caller 進追問），不預設 1。"""
    result = product_parser.parse_products("我要紅茶")
    assert result == [("冰紅茶", None)]


def test_parse_products_two_products_with_quantities() -> None:
    """多商品 + 各自數量黏住對應商品（sticky-right）。"""
    result = product_parser.parse_products("紅茶 1 刮刮樂 2")
    assert result == [("冰紅茶", 1), ("刮刮樂", 2)]


def test_parse_products_two_products_first_has_qty_second_missing() -> None:
    """多商品 + 第一個有數量第二個沒 → 第一個用該數量，第二個 qty=None。"""
    result = product_parser.parse_products("紅茶 1 刮刮樂")
    assert result == [("冰紅茶", 1), ("刮刮樂", None)]


def test_parse_products_two_products_both_missing_qty() -> None:
    """多商品但都沒給數量 → 兩個 qty 都 None。"""
    result = product_parser.parse_products("紅茶 刮刮樂")
    assert result == [("冰紅茶", None), ("刮刮樂", None)]


def test_parse_products_duplicate_product_overwrites_to_last_qty() -> None:
    """重複商品 + 全部都有數量 → 覆寫為最後一個 qty（顧客修正語意）。

    （2026-05-26 Wave 7a C22：dedup 規則第 3 條改覆寫 —
     「紅茶 2 紅茶 3」= 顧客改成 3 瓶，非舊版累加 5 瓶。）
    """
    result = product_parser.parse_products("冰紅茶 2 冰紅茶 3")
    assert result == [("冰紅茶", 3)]


def test_parse_products_duplicate_all_missing_qty_merges_to_single() -> None:
    """重複商品 + 全部都沒數量 → 合併成一個 entry，只追問一次（2026-05-25 dedup 規則第 1 條）。

    使用者實機回報：「刮刮樂 紅茶 刮刮樂」會重複問兩次刮刮樂幾張，應合一只問一次。
    """
    result = product_parser.parse_products("刮刮樂 刮刮樂")
    assert result == [("刮刮樂", None)]

    result_mixed = product_parser.parse_products("刮刮樂 紅茶 刮刮樂")
    assert result_mixed == [("刮刮樂", None), ("冰紅茶", None)]


def test_parse_products_duplicate_mixed_qty_drops_missing() -> None:
    """重複商品 + 有數量 + 無數量混合 → 只保留有數量的，無數量的忽略（2026-05-25 dedup 規則第 2 條）。

    使用者實機回報規則：「刮刮樂3 刮刮樂 紅茶」應算 3 張刮刮樂（不追問第二次）+ 紅茶照常追問。
    """
    result = product_parser.parse_products("刮刮樂 3 刮刮樂 紅茶")
    assert result == [("刮刮樂", 3), ("冰紅茶", None)]

    # 有數量在後、無數量在前 → 同樣丟無數量
    result_reverse = product_parser.parse_products("刮刮樂 刮刮樂 3")
    assert result_reverse == [("刮刮樂", 3)]


# ============================================================
# P4 regression tests — parse_products 路徑（2026-05-26 從 test_nlu.py 拆出）
# ============================================================

def test_parse_products_iced_tea_short_word_tea_no_longer_matches() -> None:
    """S15：iced tea / black tea 具體詞仍能命中冰紅茶。"""
    assert product_parser.parse_products("iced tea 2") == [("冰紅茶", 2)]
    assert product_parser.parse_products("one black tea") == [("冰紅茶", None)]


# ============================================================
# 明確 0 透出（2026-06-09；invalid_qty_reask spec §2.7 前提修正）
# 視窗有阿拉伯數字但全為 0 → 回 0（非 None「缺數量」），對齊 nlu.parse_quantity B16。
# 讓 invalid_qty_reask 的 qty==0 偵測點可達。
# ============================================================
def test_parse_products_explicit_zero_surfaces_zero() -> None:
    """「紅茶0」→ qty 為 0（明確 0），非 None；多商品保留各自。"""
    assert product_parser.parse_products("紅茶0") == [("冰紅茶", 0)]
    assert product_parser.parse_products("紅茶0杯") == [("冰紅茶", 0)]
    assert product_parser.parse_products("紅茶 刮刮樂0") == [("冰紅茶", None), ("刮刮樂", 0)]


def test_parse_products_scratch_letou_and_caijuan_alias() -> None:
    """SCRATCH 補強：「樂透」「彩卷」（錯字）「即時樂」等同義詞能命中刮刮樂。"""
    assert product_parser.parse_products("我要樂透 2 張") == [("刮刮樂", 2)]
    assert product_parser.parse_products("彩卷一張") == [("刮刮樂", 1)]


def test_parse_products_with_filler_words_extracts_correctly() -> None:
    """含 filler 詞「想要」「跟」「謝謝」不影響解析。"""
    result = product_parser.parse_products("想要紅茶 2 跟刮刮樂 1 謝謝")
    assert result == [("冰紅茶", 2), ("刮刮樂", 1)]


def test_parse_products_long_keyword_not_double_counted_by_short() -> None:
    """「冰紅茶」涵蓋「紅茶」，不應被短詞二度匹配（去重）。"""
    result = product_parser.parse_products("冰紅茶 3")
    assert result == [("冰紅茶", 3)]


def test_parse_products_chinese_quantity() -> None:
    """中文數字也能解析。"""
    result = product_parser.parse_products("紅茶兩瓶")
    assert result == [("冰紅茶", 2)]
