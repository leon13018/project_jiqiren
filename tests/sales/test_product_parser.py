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


def test_parse_products_filler_before_exact_product_unaffected() -> None:
    """filler 在精確商品前：「我要冰紅茶」→ 冰紅茶精確命中，gap「我要」剝空 → 不誤造商品。"""
    assert product_parser.parse_products("我要冰紅茶") == [("冰紅茶", None)]


def test_parse_products_pure_filler_yields_nothing() -> None:
    """純 filler / 無商品殘段 → 不誤造商品。"""
    assert product_parser.parse_products("我要") == []
    assert product_parser.parse_products("今天天氣很好") == []


def test_parse_products_long_keyword_not_double_counted_by_short() -> None:
    """「冰紅茶」涵蓋「紅茶」，不應被短詞二度匹配（去重）。"""
    result = product_parser.parse_products("冰紅茶 3")
    assert result == [("冰紅茶", 3)]


def test_parse_products_chinese_quantity() -> None:
    """中文數字也能解析。"""
    result = product_parser.parse_products("紅茶兩瓶")
    assert result == [("冰紅茶", 2)]


# ============================================================
# ① 一句內嵌數量拼音糾錯（2026-06-14 Phase B，spec §2.1）
# parse_quantity 解不出視窗數量時，對視窗做拼音近音糾錯（重用 phonetic_match）。
# 整合測試 mock product_parser.phonetic_match（Windows 無 pypinyin；
# 聲韻母演算法正確性由 test_phonetic.py 注入 fake 覆蓋）。
# ============================================================

from unittest.mock import patch  # noqa: E402


def test_parse_products_embedded_qty_phonetic_correction_hits() -> None:
    """「紅茶商品」(=紅茶三瓶)：商品認得、內嵌數量「商品」聽歪 →
    phonetic_match 糾回「三瓶」→ 直接 冰紅茶 ×3，不再多問一次。

    2026-06-15 統一 token-parser 重寫後 phonetic_match 兩處被呼叫：
      step 3（garbled 品名糾錯，候選=商品候選）→ 「商品」非 garbled 品名 → 回 None；
      step 6（garbled 數量糾錯，候選=量詞域）→ 「商品」≈「三瓶」→ 回「三瓶」。
    side_effect 依候選域區分（取代舊單一 return_value，避免 step 3 誤把「商品」當品名）。
    """
    def side_effect(seg, candidates, **kwargs):
        # 量詞域候選（如「三瓶」）→ 糾回三瓶；商品候選域 → 非品名 → None
        if any(str(c).endswith("瓶") for c in candidates):
            return "三瓶"
        return None

    with patch.object(product_parser, "phonetic_match", side_effect=side_effect):
        assert product_parser.parse_products("紅茶商品") == [("冰紅茶", 3)]


def test_parse_products_embedded_qty_correction_none_keeps_missing() -> None:
    """糾錯失敗（phonetic_match 回 None，含 Windows graceful no-op）→
    視窗數量仍 None，落回 (商品, None) 走既有追問，行為同今天（不劣化）。"""
    with patch.object(product_parser, "phonetic_match", return_value=None):
        assert product_parser.parse_products("紅茶商品") == [("冰紅茶", None)]


def test_parse_products_embedded_qty_not_triggered_when_qty_resolved() -> None:
    """視窗已解出數量（「紅茶 2」）→ 不觸發糾錯（phonetic_match 完全不被呼叫）。"""
    with patch.object(product_parser, "phonetic_match") as mock_pm:
        assert product_parser.parse_products("紅茶 2") == [("冰紅茶", 2)]
        mock_pm.assert_not_called()


def test_parse_products_empty_window_not_corrected() -> None:
    """單商品無後方視窗內容（「紅茶」）→ 空視窗不誤糾（phonetic_match 不被呼叫）。"""
    with patch.object(product_parser, "phonetic_match") as mock_pm:
        assert product_parser.parse_products("紅茶") == [("冰紅茶", None)]
        mock_pm.assert_not_called()


# ============================================================
# ② 數量提前（2026-06-15，spec §2.1）
# 數量在商品**前**（自然語序「三瓶紅茶」）→ sticky-right 右視窗落空，
# 改解析第一商品前導段 text[:found[0][0]] 補綁。只綁第一商品（避免重綁 between-product）。
# ============================================================

def test_parse_products_leading_quantity_before_product() -> None:
    """「三瓶紅茶」：數量在商品前 → 解析前導段補綁第一商品 → 冰紅茶 ×3。"""
    assert product_parser.parse_products("三瓶紅茶") == [("冰紅茶", 3)]


def test_parse_products_leading_quantity_large_number() -> None:
    """「一千瓶紅茶」：前導段含千位複合中文數字 → 冰紅茶 ×1000。"""
    assert product_parser.parse_products("一千瓶紅茶") == [("冰紅茶", 1000)]


def test_parse_products_qty_after_product_unchanged_by_leading() -> None:
    """回歸：數量在商品後（sticky-right）仍正確，前導段不重複介入。"""
    assert product_parser.parse_products("紅茶三瓶") == [("冰紅茶", 3)]
    assert product_parser.parse_products("刮刮樂兩張") == [("刮刮樂", 2)]


def test_parse_products_leading_no_qty_keeps_missing() -> None:
    """回歸：商品前後皆無數量（「紅茶刮刮樂」）→ 兩者 qty 都 None，前導段不誤糾。"""
    assert product_parser.parse_products("紅茶刮刮樂") == [
        ("冰紅茶", None),
        ("刮刮樂", None),
    ]


# ============================================================
# comprehensive 統一 token-parser（2026-06-15，spec §2.1 Part 2）
# 任意順序 + 多商品 + 數量在前/後 → 鄰近綁定（數量綁前一未綁商品，無則後一）。
# ============================================================

def test_parse_products_qty_before_each_of_two_products() -> None:
    """「五張刮刮樂三瓶紅茶」：數量各在自身商品前 → 鄰近綁定 → [(刮刮樂,5),(冰紅茶,3)]。
    （現 sticky-right 把刮刮樂右視窗三瓶綁錯成 [(刮刮樂,3),(冰紅茶,None)] → RED）"""
    assert product_parser.parse_products("五張刮刮樂三瓶紅茶") == [
        ("刮刮樂", 5),
        ("冰紅茶", 3),
    ]


def test_parse_products_qty_after_each_of_two_products_baseline() -> None:
    """「刮刮樂五張紅茶三瓶」：數量各在自身商品後 → [(刮刮樂,5),(冰紅茶,3)]（現已對，當基準）。"""
    assert product_parser.parse_products("刮刮樂五張紅茶三瓶") == [
        ("刮刮樂", 5),
        ("冰紅茶", 3),
    ]


def test_parse_products_qty_before_and_after_mixed_order() -> None:
    """「三瓶紅茶兩張刮刮樂」：數量各在自身商品前 → 鄰近綁定 → [(冰紅茶,3),(刮刮樂,2)]。"""
    assert product_parser.parse_products("三瓶紅茶兩張刮刮樂") == [
        ("冰紅茶", 3),
        ("刮刮樂", 2),
    ]


# ============================================================
# garbled 品名 + 數量（step 3 garbled 品名 span + step 5 鄰近綁定）
# 整合測試 mock product_parser.phonetic_match，依候選域區分：
#   商品候選域（不以瓶/張結尾）→ garbled 品名糾錯；量詞域 → garbled 數量糾錯。
# ============================================================

def _garbled_product_side_effect(mapping):
    """build side_effect：seg 在 mapping 內且候選為商品域 → 回對應商品；其餘 → None。"""
    def side_effect(seg, candidates, **kwargs):
        is_qty_domain = any(
            str(c).endswith("瓶") or str(c).endswith("張") for c in candidates
        )
        if is_qty_domain:
            return None
        return mapping.get(seg)
    return side_effect


def test_parse_products_garbled_name_with_leading_qty() -> None:
    """「五張刮樂三瓶紅茶」：刮樂 garbled 品名（step3 糾刮刮樂）+ 數量在各自前 →
    [(刮刮樂,5),(冰紅茶,3)]。"""
    se = _garbled_product_side_effect({"刮樂": "刮刮樂"})
    with patch.object(product_parser, "phonetic_match", side_effect=se):
        assert product_parser.parse_products("五張刮樂三瓶紅茶") == [
            ("刮刮樂", 5),
            ("冰紅茶", 3),
        ]


def test_parse_products_garbled_name_single_with_leading_qty() -> None:
    """「五張刮樂」：單一 garbled 品名（糾刮刮樂）+ 前導數量 → [(刮刮樂,5)]。"""
    se = _garbled_product_side_effect({"刮樂": "刮刮樂"})
    with patch.object(product_parser, "phonetic_match", side_effect=se):
        assert product_parser.parse_products("五張刮樂") == [("刮刮樂", 5)]


def test_parse_products_garbled_qty_homophone_tiebreak() -> None:
    """「紅茶食品」(=紅茶十瓶)：商品認得、garbled 數量「食品」→ step6 量詞域糾錯
    （含 2.0 完全同音 tie-break，食≡十）→ 十瓶 → [(冰紅茶,10)]。"""
    def side_effect(seg, candidates, **kwargs):
        if any(str(c).endswith("瓶") for c in candidates):
            return "十瓶"
        return None

    with patch.object(product_parser, "phonetic_match", side_effect=side_effect):
        assert product_parser.parse_products("紅茶食品") == [("冰紅茶", 10)]


def test_parse_products_filler_diluted_garbled_name() -> None:
    """「我要刮樂」：意圖前綴 filler「我要」剝除後殘段「刮樂」→ garbled 刮刮樂。"""
    se = _garbled_product_side_effect({"刮樂": "刮刮樂"})
    with patch.object(product_parser, "phonetic_match", side_effect=se):
        assert product_parser.parse_products("我要刮樂") == [("刮刮樂", None)]
        assert product_parser.parse_products("我要刮樂三張") == [("刮刮樂", 3)]
