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
