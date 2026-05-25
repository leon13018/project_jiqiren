"""test_nlu.py — 測試 myProgram/sales/nlu.py。

對應 BDD scenarios：
    - L0-NLU-001 ~ L0-NLU-013：關鍵字白名單意圖分類
    - L0-QTY-001 ~ L0-QTY-009：數量解析
"""

import myProgram.sales.nlu as nlu


# ============================================================
# L0-NLU-001
# ============================================================

## L0-NLU-001
### Scenario: 拒絕意圖任一關鍵字命中即分類為拒絕
### Given 顧客輸入「不要」（拒絕意圖 6 詞之一：不要 / 不用 / 不想 / 不買 / no / nope）
### When 對輸入做意圖分類
### Then 分類結果為「拒絕」
def test_nlu_reject_intent_in_l2_l4_classified_as_reject() -> None:
    """L2 / L4 mode 的「不要」直接判拒絕（L3 normal mode 視為「不追加」→ 結帳，另測）。"""
    assert nlu.classify_intent("不要", "l2") == "拒絕"
    assert nlu.classify_intent("不要", "l4") == "拒絕"


def test_nlu_l3_strict_reject_phrases_classified_as_reject() -> None:
    """L3 (normal mode) 嚴格 reject 詞：只有明確「整單作廢」意圖才視為拒絕。"""
    assert nlu.classify_intent("我不要了") == "拒絕"
    assert nlu.classify_intent("不想買了") == "拒絕"
    assert nlu.classify_intent("取消購買") == "拒絕"
    assert nlu.classify_intent("退出") == "拒絕"
    assert nlu.classify_intent("不買了") == "拒絕"


def test_nlu_l3_lenient_no_more_classified_as_checkout() -> None:
    """L3 (normal mode): 一般 reject 短詞「不要 / 不用 / 不想 / 不買」視為「不追加」→ 結帳。"""
    assert nlu.classify_intent("不要") == "結帳"
    assert nlu.classify_intent("不用") == "結帳"
    assert nlu.classify_intent("不想") == "結帳"
    assert nlu.classify_intent("不買") == "結帳"


# ============================================================
# L0-NLU-002
# ============================================================

## L0-NLU-002
### Scenario: 想一下意圖任一關鍵字命中即分類為想一下
### Given 顧客輸入「等等」（想一下 8 詞之一：等等 / 等一下 / 稍等 / 想想 / 考慮 / 想一下 / hold on / wait）
### When 對輸入做意圖分類
### Then 分類結果為「想一下」
def test_nlu_think_intent_classified_as_think() -> None:
    assert nlu.classify_intent("等等") == "想一下"


# ============================================================
# L0-NLU-003
# ============================================================

## L0-NLU-003
### Scenario: 結帳意圖任一關鍵字命中即分類為結帳
### Given 顧客輸入「結帳」（結帳 9 詞之一：結帳 / 買單 / 付款 / 好了 / 就這樣 / 可以了 / 沒了 / 沒有了 / 夠了）
### When 對輸入做意圖分類
### Then 分類結果為「結帳」
def test_nlu_checkout_intent_classified_as_checkout() -> None:
    assert nlu.classify_intent("結帳") == "結帳"


# ============================================================
# L0-NLU-004
# ============================================================

## L0-NLU-004
### Scenario: 想找客服意圖任一關鍵字命中即分類為客服
### Given 顧客輸入「客服」（客服 5 詞之一：客服 / 聯絡 / 聯繫 / contact / 服務）
### When 對輸入做意圖分類
### Then 分類結果為「客服」
def test_nlu_service_intent_classified_as_service() -> None:
    assert nlu.classify_intent("客服") == "客服"


# ============================================================
# L0-NLU-005
# ============================================================

## L0-NLU-005
### Scenario: 商品冰紅茶任一關鍵字命中即分類為點到冰紅茶
### Given 顧客輸入「冰紅茶」（冰紅茶 4 詞之一：紅茶 / 冰紅茶 / hong cha / tea）
### When 對輸入做意圖分類
### Then 分類結果為「商品:冰紅茶」
def test_nlu_iced_tea_keyword_classified_as_product_iced_tea() -> None:
    assert nlu.classify_intent("冰紅茶") == "商品:冰紅茶"


def test_nlu_iced_tea_simplified_variants_also_classified() -> None:
    """2026-05-26 加：簡體「红茶 / 冰红茶」也應分類為冰紅茶（使用者 Windows 簡體系統實測）。"""
    assert nlu.classify_intent("红茶") == "商品:冰紅茶"
    assert nlu.classify_intent("冰红茶") == "商品:冰紅茶"
    # parse_products 也應吃簡體並回繁體 product_name
    assert nlu.parse_products("红茶 2") == [("冰紅茶", 2)]
    assert nlu.parse_products("我要冰红茶") == [("冰紅茶", None)]


# ============================================================
# L0-NLU-006
# ============================================================

## L0-NLU-006
### Scenario: 商品刮刮樂任一關鍵字命中即分類為點到刮刮樂
### Given 顧客輸入「刮刮樂」（刮刮樂 5 詞之一：刮刮樂 / 刮刮 / 彩券 / lottery / scratch）
### When 對輸入做意圖分類
### Then 分類結果為「商品:刮刮樂」
def test_nlu_scratch_card_keyword_classified_as_product_scratch_card() -> None:
    assert nlu.classify_intent("刮刮樂") == "商品:刮刮樂"


def test_nlu_scratch_card_simplified_variant_also_classified() -> None:
    """2026-05-26 加：簡體「刮刮乐」也應分類為刮刮樂。"""
    assert nlu.classify_intent("刮刮乐") == "商品:刮刮樂"
    assert nlu.parse_products("刮刮乐 3") == [("刮刮樂", 3)]


# ============================================================
# L0-NLU-007
# ============================================================

## L0-NLU-007
### Scenario: 無任何白名單命中時分類為無法判斷
### Given 顧客輸入「今天天氣很好」（無白名單命中）
### When 對輸入做意圖分類
### Then 分類結果為「無法判斷」
def test_nlu_no_keyword_match_classified_as_unknown() -> None:
    assert nlu.classify_intent("今天天氣很好") == "無法判斷"


# ============================================================
# L0-NLU-008
# ============================================================

## L0-NLU-008
### Scenario: 同時含拒絕與商品時依優先序判定為拒絕
### Given 顧客輸入「我不要冰紅茶了」（同時含拒絕 + 商品關鍵字）
### When 對輸入做意圖分類
### Then 分類結果為「拒絕」（拒絕優先序高於商品）
def test_nlu_reject_priority_over_product_in_l2_l4() -> None:
    """L2 / L4 mode 拒絕優先於商品：「我不要冰紅茶了」含「不要」（reject 詞）→ 拒絕（不視為「商品:冰紅茶」）。

    註：L3 normal mode 下「我不要冰紅茶了」因不在嚴格 reject 詞清單 → 走 L3 寬容規則 → 結帳。
    若日後使用者實測認定 L3 也該識別此句為拒絕，須擴充 _KEYWORDS_REJECT_L3_STRICT。
    """
    assert nlu.classify_intent("我不要冰紅茶了", "l2") == "拒絕"
    assert nlu.classify_intent("我不要冰紅茶了", "l4") == "拒絕"


# ============================================================
# L0-NLU-009
# ============================================================

## L0-NLU-009
### Scenario: 夠了歸類為結帳意圖（非拒絕）
### Given 顧客輸入「夠了」（2026-05-24 終審：歸結帳，不歸拒絕）
### When 對輸入做意圖分類
### Then 分類結果為「結帳」
def test_nlu_gou_le_classified_as_checkout_not_reject() -> None:
    assert nlu.classify_intent("夠了") == "結帳"


# ============================================================
# L0-NLU-010
# ============================================================

## L0-NLU-010
### Scenario: 沒了 / 沒有了歸類為結帳意圖
### Given 顧客輸入「沒了」或「沒有了」
### When 對輸入做意圖分類
### Then 分類結果均為「結帳」
def test_nlu_mei_le_classified_as_checkout() -> None:
    assert nlu.classify_intent("沒了") == "結帳"
    assert nlu.classify_intent("沒有了") == "結帳"


def test_nlu_english_no_nope_classified_as_checkout() -> None:
    """L3（normal 模式）顧客講「no」/「nope」→ 結帳意圖（語意「沒了，不追加」）。"""
    assert nlu.classify_intent("no") == "結帳"
    assert nlu.classify_intent("nope") == "結帳"


def test_nlu_english_no_nope_in_l2_mode_classified_as_reject() -> None:
    """L2 顧客講「no」/「nope」→ 拒絕意圖（語意「不要 / 不需要」→ L2-A 退出）。"""
    assert nlu.classify_intent("no", "l2") == "拒絕"
    assert nlu.classify_intent("nope", "l2") == "拒絕"


def test_nlu_english_no_nope_in_l4_mode_classified_as_reject() -> None:
    """L4 顧客講「no」/「nope」→ 拒絕意圖（語意「不要了 / 取消」→ L4-B 取消交易）。"""
    assert nlu.classify_intent("no", "l4") == "拒絕"
    assert nlu.classify_intent("nope", "l4") == "拒絕"


def test_nlu_english_no_nope_in_l4_service_mode_classified_as_exit() -> None:
    """L4 客服模式顧客講「no」/「nope」→ 退出交易意圖。"""
    assert nlu.classify_intent("no", "l4_service") == "退出交易"
    assert nlu.classify_intent("nope", "l4_service") == "退出交易"


def test_nlu_bu_le_classified_per_layer() -> None:
    """「不了」layer-aware（2026-05-25 加：使用者實測 L3 講「不了」未識別 → 加進 REJECT）：
    - L2 mode：「不了」→ 拒絕（短詞 reject 觸發 L2-A 退 L1）
    - L4 mode：「不了」→ 拒絕（觸發 L4-B 取消交易）
    - L3 normal mode：「不了」→ 結帳（layer-aware override，同「不用」/「不買」）
    """
    assert nlu.classify_intent("不了", "l2") == "拒絕"
    assert nlu.classify_intent("不了", "l4") == "拒絕"
    assert nlu.classify_intent("不了") == "結帳"  # L3 normal mode


# ============================================================
# L0-NLU-011
# ============================================================

## L0-NLU-011
### Scenario: L4 客服模式內繼續關鍵字分類為繼續交易
### Given 當前處於 L4 客服模式，顧客輸入「繼續」（5 詞之一：繼續 / 接著 / 繼續買 / 繼續交易 / continue）
### When 對輸入做意圖分類（傳入 mode=l4_service）
### Then 分類結果為「繼續交易」
def test_nlu_continue_in_l4_service_mode_classified_as_continue() -> None:
    assert nlu.classify_intent("繼續", mode="l4_service") == "繼續交易"


# ============================================================
# L0-NLU-012
# ============================================================

## L0-NLU-012
### Scenario: L4 客服模式內退出關鍵字分類為退出交易
### Given 當前處於 L4 客服模式，顧客輸入「退出」（6 詞之一：退出 / 取消 / 離開 / 算了 / 不買了 / exit）
### When 對輸入做意圖分類（傳入 mode=l4_service）
### Then 分類結果為「退出交易」
def test_nlu_exit_in_l4_service_mode_classified_as_exit() -> None:
    assert nlu.classify_intent("退出", mode="l4_service") == "退出交易"


# ============================================================
# L0-NLU-013
# ============================================================

## L0-NLU-013
### Scenario: 非 L4 客服模式內繼續 / 退出關鍵字不生效
### Given 當前為 L2 一般詢問模式，顧客輸入「繼續」或「退出」
### When 對輸入做意圖分類（mode=normal）
### Then 分類結果為「無法判斷」（繼續 / 退出僅於 L4 客服模式內生效）
def test_nlu_continue_exit_outside_l4_service_classified_as_unknown() -> None:
    """L4 客服模式專用關鍵字在其他模式的判定：
    - 「繼續」：所有 L4 服務外模式皆 → 無法判斷
    - 「退出」：2026-05-25 起加入 L3 嚴格 reject 詞 → normal (L3) mode 視為拒絕；
      L2 / L4 mode 不在嚴格清單 → 仍 unmatched 走無法判斷
    """
    assert nlu.classify_intent("繼續", mode="normal") == "無法判斷"
    assert nlu.classify_intent("繼續", mode="l2") == "無法判斷"
    assert nlu.classify_intent("繼續", mode="l4") == "無法判斷"
    # 「退出」：L3 (normal mode) 視為嚴格 reject 詞 → 拒絕；L2 / L4 仍 unmatched
    assert nlu.classify_intent("退出", mode="normal") == "拒絕"
    assert nlu.classify_intent("退出", mode="l2") == "無法判斷"
    assert nlu.classify_intent("退出", mode="l4") == "無法判斷"


# ============================================================
# L0-QTY-001
# ============================================================

## L0-QTY-001
### Scenario: 中文數字命中時取對應數值
### Given 顧客輸入「冰紅茶兩個」
### When 解析數量
### Then 數量為 2
def test_qty_chinese_two_returns_2() -> None:
    assert nlu.parse_quantity("冰紅茶兩個") == 2


# ============================================================
# L0-QTY-002
# ============================================================

## L0-QTY-002
### Scenario: 阿拉伯數字命中時取首個正整數
### Given 顧客輸入「3 杯冰紅茶」
### When 解析數量
### Then 數量為 3
def test_qty_arabic_3_returns_3() -> None:
    assert nlu.parse_quantity("3 杯冰紅茶") == 3


# ============================================================
# L0-QTY-003
# ============================================================

## L0-QTY-003
### Scenario: 無任何數字命中時預設為 1
### Given 顧客輸入「我要刮刮樂」（無數字）
### When 解析數量
### Then 數量為 1（預設）
def test_qty_no_number_defaults_to_1() -> None:
    assert nlu.parse_quantity("我要刮刮樂") == 1


# ============================================================
# L0-QTY-004
# ============================================================

## L0-QTY-004
### Scenario: 中文一字命中時數量為 1
### Given 顧客輸入「給我一杯紅茶」
### When 解析數量
### Then 數量為 1
def test_qty_chinese_one_returns_1() -> None:
    assert nlu.parse_quantity("給我一杯紅茶") == 1


# ============================================================
# L0-QTY-005
# ============================================================

## L0-QTY-005
### Scenario: 阿拉伯多位數命中
### Given 顧客輸入「我要 5 個刮刮樂」
### When 解析數量
### Then 數量為 5
def test_qty_arabic_5_returns_5() -> None:
    assert nlu.parse_quantity("我要 5 個刮刮樂") == 5


# ============================================================
# L0-QTY-006
# ============================================================

## L0-QTY-006
### Scenario: 中文十命中時數量為 10
### Given 顧客輸入「十杯冰紅茶」
### When 解析數量
### Then 數量為 10
def test_qty_chinese_ten_returns_10() -> None:
    assert nlu.parse_quantity("十杯冰紅茶") == 10


# ============================================================
# L0-QTY-007
# ============================================================

## L0-QTY-007
### Scenario: 中文異體字（壹 / 貳 / 參 / 拾）命中對應數量
### Given 顧客輸入「我要壹杯」 / 「貳杯」 / 「參個」 / 「拾杯」
### When 解析數量
### Then 對應數量為 1 / 2 / 3 / 10
def test_qty_chinese_variants_recognized() -> None:
    assert nlu.parse_quantity("我要壹杯") == 1
    assert nlu.parse_quantity("貳杯") == 2
    assert nlu.parse_quantity("參個") == 3
    assert nlu.parse_quantity("拾杯") == 10


# ============================================================
# L0-QTY-008
# ============================================================

## L0-QTY-008
### Scenario: 阿拉伯數字 0 不生效，回退預設 1
### Given 顧客輸入「我要 0 杯」（規格定義：>0 時生效，否則預設 1）
### When 解析數量
### Then 數量為 1（預設）
def test_qty_arabic_0_falls_back_to_default_1() -> None:
    assert nlu.parse_quantity("我要 0 杯") == 1


# ============================================================
# L0-QTY-009
# ============================================================

## L0-QTY-009
### Scenario: 同時含阿拉伯與中文數字時阿拉伯優先
### Given 顧客輸入「我要 3 杯，給我貳個」（同時含 3 與貳）
### When 解析數量
### Then 數量為 3（阿拉伯數字優先於中文）
def test_qty_arabic_priority_over_chinese() -> None:
    assert nlu.parse_quantity("我要 3 杯，給我貳個") == 3


# ============================================================
# L0-QTY-010 (2026-05-25 加)
# ============================================================

## L0-QTY-010
### Scenario: has_quantity 判斷文字內是否含可解析數量
### Given 顧客輸入文字
### When 呼叫 has_quantity
### Then 含阿拉伯或中文數字 → True；否則 → False
def test_has_quantity_detects_arabic_and_chinese() -> None:
    """供 L2 / L3 鏈路 C 區分「顯式 1 vs 預設 1」用 — 預設 1 才追問數量。"""
    # 阿拉伯數字 → True
    assert nlu.has_quantity("我要 5 瓶")
    assert nlu.has_quantity("10張")
    # 中文數字 → True
    assert nlu.has_quantity("我要兩瓶冰紅茶")
    assert nlu.has_quantity("三個")
    assert nlu.has_quantity("拾杯")
    assert nlu.has_quantity("壹瓶")
    # 無數量 → False
    assert not nlu.has_quantity("冰紅茶")
    assert not nlu.has_quantity("我要紅茶")
    assert not nlu.has_quantity("刮刮樂")
    assert not nlu.has_quantity("")


# ============================================================
# L0-QTY-011 (2026-05-25 加：量詞 agnostic 契約)
# ============================================================

## L0-QTY-011
### Scenario: parse_quantity 忽略量詞變體，只抽商品數量
### Given 顧客輸入含各種量詞（個 / 罐 / typo / 無量詞）+ 阿拉伯數字
### When 解析數量
### Then 數量正確抽出，量詞被視為「不關心的字元」
def test_qty_ignores_chinese_measure_word_variants() -> None:
    """量詞 agnostic 原則：「中文的量詞對我們來說不重要，我們只捕捉商品名和數量做決策」。

    無論顧客用「個 / 北(typo) / 罐」或省略量詞，parse_quantity 只看阿拉伯數字。
    """
    assert nlu.parse_quantity("紅茶20個") == 20      # 個（常見泛用量詞）
    assert nlu.parse_quantity("紅茶10北") == 10      # 北（量詞 typo — 顧客誤打）
    assert nlu.parse_quantity("紅茶10罐") == 10      # 罐
    assert nlu.parse_quantity("刮刮樂100") == 100   # 無量詞
    assert nlu.parse_quantity("冰紅茶 5 罐") == 5    # 數字前後皆有字 + 空格


# ============================================================
# L0-NLU-012 (2026-05-25 加：商品識別 量詞 agnostic)
# ============================================================

## L0-NLU-012
### Scenario: classify_intent 商品識別不受量詞影響
### Given 顧客輸入含商品名 + 各種量詞變體
### When 對輸入做意圖分類
### Then 商品 keyword substring 命中即正確分類，前後文字不影響
def test_nlu_classify_intent_ignores_chinese_measure_word_variants() -> None:
    """商品識別 substring 比對：商品名 substring 命中即可，量詞 / 形容詞 / 副詞全不關心。"""
    assert nlu.classify_intent("紅茶20個") == "商品:冰紅茶"
    assert nlu.classify_intent("紅茶10北") == "商品:冰紅茶"
    assert nlu.classify_intent("紅茶10罐") == "商品:冰紅茶"
    assert nlu.classify_intent("刮刮樂100") == "商品:刮刮樂"


# ============================================================
# L0-NLU-PARSE-PRODUCTS-001 ~ 008（2026-05-25 加，B 方案 multi-product）
# ============================================================

def test_parse_products_empty_input_returns_empty_list() -> None:
    assert nlu.parse_products("") == []
    assert nlu.parse_products("今天天氣很好") == []


def test_parse_products_single_with_quantity() -> None:
    result = nlu.parse_products("冰紅茶 2")
    assert result == [("冰紅茶", 2)]


def test_parse_products_single_without_quantity_returns_none_qty() -> None:
    """單商品無數量 → qty 為 None（caller 進追問），不預設 1。"""
    result = nlu.parse_products("我要紅茶")
    assert result == [("冰紅茶", None)]


def test_parse_products_two_products_with_quantities() -> None:
    """多商品 + 各自數量黏住對應商品（sticky-right）。"""
    result = nlu.parse_products("紅茶 1 刮刮樂 2")
    assert result == [("冰紅茶", 1), ("刮刮樂", 2)]


def test_parse_products_two_products_first_has_qty_second_missing() -> None:
    """多商品 + 第一個有數量第二個沒 → 第一個用該數量，第二個 qty=None。"""
    result = nlu.parse_products("紅茶 1 刮刮樂")
    assert result == [("冰紅茶", 1), ("刮刮樂", None)]


def test_parse_products_two_products_both_missing_qty() -> None:
    """多商品但都沒給數量 → 兩個 qty 都 None。"""
    result = nlu.parse_products("紅茶 刮刮樂")
    assert result == [("冰紅茶", None), ("刮刮樂", None)]


def test_parse_products_duplicate_product_returns_separate_entries() -> None:
    """重複商品 + 全部都有數量 → 保留各自獨立 entry（caller 累加）。

    （2026-05-25 dedup 規則第 3 條：全有數量 → 保留累加。）
    """
    result = nlu.parse_products("冰紅茶 2 冰紅茶 3")
    assert result == [("冰紅茶", 2), ("冰紅茶", 3)]


def test_parse_products_duplicate_all_missing_qty_merges_to_single() -> None:
    """重複商品 + 全部都沒數量 → 合併成一個 entry，只追問一次（2026-05-25 dedup 規則第 1 條）。

    使用者實機回報：「刮刮樂 紅茶 刮刮樂」會重複問兩次刮刮樂幾張，應合一只問一次。
    """
    result = nlu.parse_products("刮刮樂 刮刮樂")
    assert result == [("刮刮樂", None)]

    result_mixed = nlu.parse_products("刮刮樂 紅茶 刮刮樂")
    assert result_mixed == [("刮刮樂", None), ("冰紅茶", None)]


def test_parse_products_duplicate_mixed_qty_drops_missing() -> None:
    """重複商品 + 有數量 + 無數量混合 → 只保留有數量的，無數量的忽略（2026-05-25 dedup 規則第 2 條）。

    使用者實機回報規則：「刮刮樂3 刮刮樂 紅茶」應算 3 張刮刮樂（不追問第二次）+ 紅茶照常追問。
    """
    result = nlu.parse_products("刮刮樂 3 刮刮樂 紅茶")
    assert result == [("刮刮樂", 3), ("冰紅茶", None)]

    # 有數量在後、無數量在前 → 同樣丟無數量
    result_reverse = nlu.parse_products("刮刮樂 刮刮樂 3")
    assert result_reverse == [("刮刮樂", 3)]


def test_parse_products_with_filler_words_extracts_correctly() -> None:
    """含 filler 詞「想要」「跟」「謝謝」不影響解析。"""
    result = nlu.parse_products("想要紅茶 2 跟刮刮樂 1 謝謝")
    assert result == [("冰紅茶", 2), ("刮刮樂", 1)]


def test_parse_products_long_keyword_not_double_counted_by_short() -> None:
    """「冰紅茶」涵蓋「紅茶」，不應被短詞二度匹配（去重）。"""
    result = nlu.parse_products("冰紅茶 3")
    assert result == [("冰紅茶", 3)]


def test_parse_products_chinese_quantity() -> None:
    """中文數字也能解析。"""
    result = nlu.parse_products("紅茶兩瓶")
    assert result == [("冰紅茶", 2)]
