"""test_nlu.py — 測試 myProgram/sales/nlu.py。

對應 BDD scenarios：
    - L0-NLU-001 ~ L0-NLU-013：關鍵字白名單意圖分類
    - L0-QTY-001 ~ L0-QTY-009：數量解析

注意：parse_products 相關測試已於 2026-05-26 P7 移至 tests/sales/test_product_parser.py。
"""

import pytest

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


def test_nlu_cross_l_cancel_phrases_classified_as_reject() -> None:
    """2026-05-29 cross-L cancel 擴充：「取消交易」等 phrase 應分類為「拒絕」。

    覆蓋 L2 (l2 mode) / L4 (l4 mode) / L3 (normal mode strict)。
    後端 dispatch 接收「拒絕」intent 後會進 cancel_confirm gate。
    """
    # L2 mode
    assert nlu.classify_intent("我想取消交易", "l2") == "拒絕"
    assert nlu.classify_intent("取消交易", "l2") == "拒絕"
    assert nlu.classify_intent("我要取消交易", "l2") == "拒絕"
    assert nlu.classify_intent("退出交易", "l2") == "拒絕"
    # L4 mode
    assert nlu.classify_intent("取消交易", "l4") == "拒絕"
    # L3 mode（normal）— strict reject 也應命中
    assert nlu.classify_intent("取消交易") == "拒絕"
    assert nlu.classify_intent("退出交易") == "拒絕"
    assert nlu.classify_intent("我想取消交易") == "拒絕"


def test_nlu_l3_lenient_no_more_classified_as_checkout() -> None:
    """L3 (normal mode): 一般 reject 短詞「不要 / 不用 / 不想 / 不買」視為「不追加」→ 結帳。"""
    assert nlu.classify_intent("不要") == "結帳"
    assert nlu.classify_intent("不用") == "結帳"
    assert nlu.classify_intent("不想") == "結帳"
    assert nlu.classify_intent("不買") == "結帳"


@pytest.mark.parametrize(
    "reject_text",
    [
        "不要買了",
        "不想買",
    ],
)
def test_nlu_l3_strict_expanded_rejects(reject_text: str) -> None:
    """2026-05-30 加：L3_STRICT 擴展「不要買了」「不想買」應視為「拒絕」。

    避免 mode="normal" 用通用 _KEYWORDS_REJECT substring 把這些 phrase 視為「結帳」
    → 觸發 confirm「您即將結帳... 正確嗎？」UX 怪。
    L4 mode 一直視為「拒絕」（通用集已 cover），這裡只補 L3 normal mode 缺漏。
    """
    assert nlu.classify_intent(reject_text, mode="normal") == "拒絕", (
        f"L3 mode「{reject_text}」應視為「拒絕」，實際："
        f"{nlu.classify_intent(reject_text, mode='normal')!r}"
    )


# ============================================================
# L3-NLU-REJECT-001
### Scenario: L3 主迴圈「請問還有額外需要購買的嗎？」常見不買回應
### Given mode="normal"（L3 cart 非空模式）
### When 顧客回應 user 列表 7 個常見「不需要加購」用語之一
### Then classify_intent 應回「結帳」（不追加 → C-1 confirm path）
### Note 2026-05-30 加：修 Pi demo「不需要」/「不需要了」/「我不需要」/
###      「沒有額外需要購買的」走 unclear 的 UX bug
# ============================================================

@pytest.mark.parametrize(
    "reject_text",
    [
        "不需要",
        "不用",
        "我不需要",
        "不需要了",
        "沒有",
        "沒",
        "沒有額外需要購買的",
    ],
)
def test_l3_normal_mode_no_more_purchase_phrases_classified_as_checkout(reject_text: str) -> None:
    """L3 mode="normal"：常見「不再加購」用語應視為「結帳」進 C-1 confirm。

    user 列表 7 個用語覆蓋：
    - substring「不需要」cover 不需要 / 我不需要 / 不需要了
    - substring「不用」cover 不用
    - substring「沒有額外」cover 沒有額外需要購買的
    - strict_short「沒有」/「沒」cover 沒有 / 沒
    """
    assert nlu.classify_intent(reject_text, mode="normal") == "結帳", (
        f"L3 mode「{reject_text}」應視為「結帳」（不追加進 C-1 confirm），"
        f"實際：{nlu.classify_intent(reject_text, mode='normal')!r}"
    )


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


def test_nlu_zheyang_jiu_hao_classified_as_checkout() -> None:
    """Pi 實測：L3 加單狀態「這樣就好 / 這樣就好了」表達不追加 → 結帳。

    原本不在 CHECKOUT keyword → 落「無法判斷」→ 回「聽不懂」；而「不用這樣就好了」
    碰巧命中「不用」(REJECT，L3 normal mode 視為不追加 → 結帳) 而 work，造成
    「有的變體行、有的不行」不一致。加入「這樣就好」substring 後三變體一致走結帳。
    """
    assert nlu.classify_intent("這樣就好") == "結帳"
    assert nlu.classify_intent("這樣就好了") == "結帳"
    assert nlu.classify_intent("這樣就好", mode="normal") == "結帳"  # L3 加單 context


# ============================================================
# 合音還原 expand_fusion（2026-06-15，spec §2.2）
# 台灣合音「這樣→醬(jiàng)」+ ASR 同音變體「將」未還原 →「醬/將就好」無法判斷。
# expand_fusion 固定表逐字替換；無命中原樣返回（idempotent）。
# ============================================================

def test_expand_fusion_jiang_restored_to_zheyang() -> None:
    """「將就好」→「這樣就好」（ASR 同音變體「將」還原）。"""
    assert nlu.expand_fusion("將就好") == "這樣就好"


def test_expand_fusion_jiang_sauce_restored_to_zheyang() -> None:
    """「醬就好」→「這樣就好」（台灣合音「醬」還原）。"""
    assert nlu.expand_fusion("醬就好") == "這樣就好"


def test_expand_fusion_idempotent_no_fusion_char() -> None:
    """無合音字（「這樣就好」已展開、「紅茶」普通詞）→ 原樣返回（idempotent，遞迴安全）。"""
    assert nlu.expand_fusion("這樣就好") == "這樣就好"
    assert nlu.expand_fusion("紅茶") == "紅茶"


def test_expand_fusion_empty_string() -> None:
    """空字串 → 空字串。"""
    assert nlu.expand_fusion("") == ""


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


def test_nlu_short_mei_classified_by_mode() -> None:
    """2026-05-26 加：單字「沒」依層別解析。

    - L2 (DnC)：「沒」= 沒有要買 → 拒絕（退 L1）
    - L3 normal (DyC)：「沒」= 沒了，不追加 → 結帳（進 confirm）
    - L4 / l4_service：「沒」走 L2/L4 mode 規則 → 拒絕
    """
    assert nlu.classify_intent("沒", "l2") == "拒絕"
    assert nlu.classify_intent("沒", "normal") == "結帳"
    assert nlu.classify_intent("沒", "l4") == "拒絕"


def test_nlu_english_no_nope_in_l3_normal_mode_classified_as_unknown() -> None:
    """2026-05-26 P0 strict-match 修正：L3（normal 模式）顧客講「no」/「nope」→ 無法判斷。

    舊行為：「no」/「nope」在 _KEYWORDS_CHECKOUT 內，L3 normal mode → 結帳。
    新行為（2026-05-26）：移除「no/nope」出 _KEYWORDS_CHECKOUT（短詞，會在 C-2 strict yes/no
    上下文誤命中 YES 條件）。L3 normal mode「no/nope」→ 無法判斷（走 B-1 clarify）。
    C-2 strict yes/no 上下文「no/nope」走 CONFIRM_NO_STRICT_SHORT 完全等於路徑。
    """
    assert nlu.classify_intent("no") == "無法判斷"
    assert nlu.classify_intent("nope") == "無法判斷"


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
### Scenario: 阿拉伯數字 0 — 顧客明確說 0 回 0（B16 修正）
### Given 顧客輸入「我要 0 杯」（規格更新 2026-05-26 B16：顯式 0 應回 0，不 fallback 1）
### When 解析數量
### Then 數量為 0（顧客明確表達不要，不應默默加 1 個 — B16 顧客錢包保護）
def test_qty_arabic_0_returns_0() -> None:
    """B16 修正：「我要 0 杯」阿拉伯數字 0 → 明確回 0，不 fallback 為 1。

    舊規格（>0 時生效，否則預設 1）是 silent failure，顧客明確說 0 卻被默默加 1 個。
    新規格（2026-05-26）：所有阿拉伯數字皆為 0 時視為顧客明確表達「不要」→ 回 0。
    """
    assert nlu.parse_quantity("我要 0 杯") == 0


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
# Bug2（2026-06-14 Pi 實測）：split_at_quantity — 商品名歪 + 數量同句拆句
# ============================================================
# 「刮樂一千張」(garble 商品 + 數量) 整句 phonetic_match 認不出 → 拆出商品段糾錯。
# 從首個數量指示字（阿拉伯數字 / CHINESE_DIGIT_MAP 字 / multiplier 十拾百佰千仟萬万）
# 切成 (head, tail)。

def test_split_at_quantity_商品名歪加數量():
    """「刮樂一千張」→ ("刮樂", "一千張")（從首個數量字「一」切）。"""
    assert nlu.split_at_quantity("刮樂一千張") == ("刮樂", "一千張")


def test_split_at_quantity_無數量字():
    """無數量字 → (text, "")。"""
    assert nlu.split_at_quantity("刮刮樂") == ("刮刮樂", "")


def test_split_at_quantity_數量字在開頭():
    """數量字在開頭 → ("", text)。"""
    assert nlu.split_at_quantity("一千張") == ("", "一千張")


def test_split_at_quantity_商品加阿拉伯數量():
    """阿拉伯數字也算數量指示字。"""
    assert nlu.split_at_quantity("刮樂3張") == ("刮樂", "3張")


def test_split_at_quantity_商品加中文個位():
    """「刮樂三張」→ ("刮樂", "三張")。"""
    assert nlu.split_at_quantity("刮樂三張") == ("刮樂", "三張")


def test_split_at_quantity_multiplier_十():
    """multiplier「十」(在 CHINESE_DIGIT_MAP) 也是切點。"""
    assert nlu.split_at_quantity("紅茶十瓶") == ("紅茶", "十瓶")


def test_split_at_quantity_空字串():
    """空字串 → ("", "")。"""
    assert nlu.split_at_quantity("") == ("", "")


# ============================================================
# find_quantity_spans（2026-06-15，spec §2.1 Part 1）
# 掃描數量字元段 regex（阿拉伯 + CHINESE_DIGIT_MAP + multiplier + 單位 瓶張），
# 每段 parse_quantity 得值；值為 None 的段棄。回 [(start, end, value), ...]。
# 供 parse_products 統一 token-parser 找數量 token。
# ============================================================

def test_find_quantity_spans_single_after_product():
    """「紅茶三瓶」：紅茶 0-2 不在數量集、三瓶 2-4 → [(2, 4, 3)]。"""
    assert nlu.find_quantity_spans("紅茶三瓶") == [(2, 4, 3)]


def test_find_quantity_spans_two_spans_around_product():
    """「五張刮刮樂三瓶」：五張 0-2、刮刮樂 2-5 不在數量集、三瓶 5-7 → [(0,2,5),(5,7,3)]。"""
    assert nlu.find_quantity_spans("五張刮刮樂三瓶") == [(0, 2, 5), (5, 7, 3)]


def test_find_quantity_spans_arabic_multiplier():
    """「9萬瓶」：阿拉伯數字緊接乘數 → span 0-3、值 90000。"""
    assert nlu.find_quantity_spans("9萬瓶") == [(0, 3, 90000)]


def test_find_quantity_spans_no_quantity_returns_empty():
    """「紅茶」無數量字 → []。"""
    assert nlu.find_quantity_spans("紅茶") == []


def test_find_quantity_spans_unit_only_no_value_dropped():
    """「瓶」單位字但無數字 → parse_quantity(default=None) 回 None → 該段棄 → []。"""
    assert nlu.find_quantity_spans("瓶") == []


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
# P4 regression tests（2026-05-26）
# ============================================================

def test_nlu_l3_strict_reject_includes_whole_order_cancel_phrasings() -> None:
    """S14：_KEYWORDS_REJECT_L3_STRICT 補強後覆蓋常見整單作廢表達。

    L3 normal mode 顧客講「全部取消」「都不要了」「整單取消」「取消」
    應 return 「拒絕」（整單作廢），而非 fallthrough 通用 REJECT 變「結帳」誤推進 L4。
    """
    # 繁體新增詞
    assert nlu.classify_intent("全部取消") == "拒絕"
    assert nlu.classify_intent("都不要了") == "拒絕"
    assert nlu.classify_intent("整單取消") == "拒絕"
    assert nlu.classify_intent("取消") == "拒絕"
    assert nlu.classify_intent("全部不要") == "拒絕"
    assert nlu.classify_intent("都取消") == "拒絕"


def test_nlu_iced_tea_short_word_tea_no_longer_matches() -> None:
    """S15：移除短詞「tea」後，含「tea」substring 但非冰紅茶語境的字串不應誤命中商品識別。

    STT 結果若混雜英文 noise（如「matter」「outreach」），
    不應因含「tea」substring 而誤識別為冰紅茶。
    改「iced tea」/「black tea」更具體，仍涵蓋顧客講英文情境。
    parse_products 的驗證已移至 test_product_parser.py。
    """
    # 不應誤命中（含 tea substring 但非商品）
    assert nlu.classify_intent("matter") == "無法判斷"
    assert nlu.classify_intent("outreach") == "無法判斷"
    assert nlu.classify_intent("steam") == "無法判斷"
    assert nlu.classify_intent("team") == "無法判斷"
    # 正確英文命中仍有效
    assert nlu.classify_intent("iced tea") == "商品:冰紅茶"
    assert nlu.classify_intent("black tea") == "商品:冰紅茶"


# ============================================================
# L4 等待安撫 regression tests（2026-05-26 加）
# ============================================================

def test_nlu_l4_mode_ack_words_classified_as_wait_calm() -> None:
    """L4 mode 顧客禮貌肯定 / 等待詞應 classify 為「等待安撫」。"""
    # 長詞 substring
    assert nlu.classify_intent("好的", "l4") == "等待安撫"
    assert nlu.classify_intent("沒問題", "l4") == "等待安撫"
    assert nlu.classify_intent("等等我", "l4") == "等待安撫"
    assert nlu.classify_intent("等我", "l4") == "等待安撫"
    assert nlu.classify_intent("稍等", "l4") == "等待安撫"
    assert nlu.classify_intent("okay", "l4") == "等待安撫"
    # strict-short
    assert nlu.classify_intent("好", "l4") == "等待安撫"
    assert nlu.classify_intent("嗯", "l4") == "等待安撫"
    assert nlu.classify_intent("ok", "l4") == "等待安撫"


def test_nlu_l4_mode_short_ack_strict_match_avoids_false_positive() -> None:
    """strict-short 防 substring 誤命中。

    「好像」substring 含「好」但 strict-short 要 == 「好」才命中；
    在 L4 mode「好像」不該被當「等待安撫」（會 fall through）。
    """
    assert nlu.classify_intent("好像", "l4") != "等待安撫"
    assert nlu.classify_intent("好亂", "l4") != "等待安撫"


def test_nlu_l4_ack_does_not_affect_other_modes() -> None:
    """「等待安撫」是 L4 mode 專屬；L2 / L3 normal / l4_service 不該命中。

    L3 normal「好的」是 fall through 通用區 → 不是「等待安撫」。
    """
    assert nlu.classify_intent("好的", "normal") != "等待安撫"  # L3 normal
    assert nlu.classify_intent("好的", "l2") != "等待安撫"
    assert nlu.classify_intent("好的", "l4_service") != "等待安撫"


def test_nlu_scratch_letou_and_caijuan_alias() -> None:
    """SCRATCH 補強：「樂透」「彩卷」（錯字）「即時樂」等同義詞能命中刮刮樂。

    Demo 場景顧客可能講「樂透」「彩卷」（常見錯字）；
    當前缺漏會 fall through 到 unclear，補強後應正確識別。
    parse_products 路徑的驗證已移至 test_product_parser.py。
    """
    # classify_intent 路徑
    assert nlu.classify_intent("樂透") == "商品:刮刮樂"
    assert nlu.classify_intent("彩卷") == "商品:刮刮樂"
    assert nlu.classify_intent("即時樂") == "商品:刮刮樂"


# ============================================================
# P5 normalize_input 單元測試（2026-05-26）
# ============================================================

def test_normalize_input_truncates_at_default_max_length() -> None:
    """超過 200 字的輸入應被截斷至 200 字（防 STT 雜訊 / 異常超長輸入）。"""
    long_input = "紅" * 300  # 300 字，超過預設上限 200
    result = nlu.normalize_input(long_input)
    assert len(result) == 200
    assert result == "紅" * 200


def test_normalize_input_removes_control_chars() -> None:
    """控制字元（\\x00 / \\x07 / \\x1f）應被移除；\\t / \\n / \\r 應保留。"""
    # 含 NUL（\\x00）和 BEL（\\x07）→ 應被移除
    assert nlu.normalize_input("你好\x00世界") == "你好世界"
    assert nlu.normalize_input("test\x07bell") == "testbell"
    assert nlu.normalize_input("\x1f控制\x08字元") == "控制字元"
    # \\t / \\n / \\r 保留（caller 自行 strip）
    assert nlu.normalize_input("行一\n行二") == "行一\n行二"
    assert nlu.normalize_input("tab\there") == "tab\there"


def test_normalize_input_converts_full_width_digits() -> None:
    """全形數字（０-９）應轉為半形（0-9）；中文字元不受影響。"""
    assert nlu.normalize_input("１２３") == "123"
    assert nlu.normalize_input("請問１杯紅茶") == "請問1杯紅茶"
    assert nlu.normalize_input("０９８") == "098"
    # 已是半形 → 不變
    assert nlu.normalize_input("123abc") == "123abc"


# ============================================================
# 「想買無商品」intent 測試（2026-05-26 加）
# 使用者實機回報：L3 DyC 回「有」被誤判 unclear，L2 DnC 回「要」同 pattern
# ============================================================

def test_nlu_l2_l3_vague_buy_intent_classified_correctly() -> None:
    """L2/L3 normal mode 顧客講「有/要/想買/我要」等肯定詞無具體商品 → 「想買無商品」intent。"""
    # strict-short — L2 mode
    assert nlu.classify_intent("有", "l2") == "想買無商品"
    assert nlu.classify_intent("要", "l2") == "想買無商品"
    # strict-short — normal (L3) mode
    assert nlu.classify_intent("有", "normal") == "想買無商品"
    assert nlu.classify_intent("要", "normal") == "想買無商品"
    # substring 長詞 — L2 mode
    assert nlu.classify_intent("我要", "l2") == "想買無商品"
    assert nlu.classify_intent("想買", "l2") == "想買無商品"
    # substring 長詞 — normal (L3) mode
    assert nlu.classify_intent("還想", "normal") == "想買無商品"
    assert nlu.classify_intent("還要", "normal") == "想買無商品"


def test_nlu_vague_buy_strict_short_avoids_false_positive() -> None:
    """strict-short 防 substring 誤命中。

    「沒有」含「有」substring，但已先被 REJECT/CHECKOUT 攔截（在 L2 mode → 拒絕；在 L3 normal mode → 結帳）。
    「不要」同上。
    """
    # 「沒有」在 L2 → 拒絕（不是「想買無商品」）
    assert nlu.classify_intent("沒有", "l2") == "拒絕"
    # 「沒有」在 L3 normal → 結帳（_KEYWORDS_REJECT 不在 L3 嚴格清單 → lenient 路徑 → 結帳）
    assert nlu.classify_intent("沒有", "normal") == "結帳"
    # 「不要」在 L2 → 拒絕
    assert nlu.classify_intent("不要", "l2") == "拒絕"
    # 「不要」在 L3 normal → 結帳（lenient 路徑）
    assert nlu.classify_intent("不要", "normal") == "結帳"


def test_nlu_vague_buy_does_not_affect_other_modes() -> None:
    """「想買無商品」L2/normal 專屬；l4 / l4_service 不命中。"""
    # 「有」在 L4 → 等待安撫（L4 ack 機制接管），不該變「想買無商品」
    assert nlu.classify_intent("有", "l4") != "想買無商品"
    assert nlu.classify_intent("有", "l4_service") != "想買無商品"
    assert nlu.classify_intent("要", "l4") != "想買無商品"


def test_nlu_specific_product_takes_priority_over_vague_buy() -> None:
    """顧客講「我要冰紅茶」—「冰紅茶」先命中商品 keyword，不會被「我要」帶到「想買無商品」。"""
    # classify_intent：「我要冰紅茶」含「冰紅茶」→ 商品意圖（不是「想買無商品」）
    assert nlu.classify_intent("我要冰紅茶", "l2") != "想買無商品"
    assert nlu.classify_intent("我要冰紅茶", "l2") == "商品:冰紅茶"
