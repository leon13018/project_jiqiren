"""意圖識別（S1 v2）— 純函式，可單獨單測。

職責：
    - 6 步判定優先序（規格書 L0「關鍵字白名單」段）
    - 數量解析（阿拉伯優先，中文映射，預設 1）
    - 各層共用的 classify_intent / parse_quantity 純函式

設計原則：
    - 無 IO、無 print、無副作用
    - 輸入字串 → 輸出意圖字串
    - 純函式，適合 BDD/TDD 切入點
"""

import re

# ============================================================
# 關鍵字白名單（依規格書 L0_共通.md）
# ============================================================

_KEYWORDS_REJECT = ["不要", "不用", "不想", "不買"]

_KEYWORDS_THINK = ["等等", "等一下", "稍等", "想想", "考慮", "想一下", "hold on", "wait"]

# 「no」/「nope」歸 CHECKOUT（語意 = 沒了 / 不追加 → L3 進結帳）
# 2026-05-25 從 REJECT 移過來：L3 顧客講 no 本意是「沒了，去結帳」而非「整單作廢」。
# 副作用：L2 講 no 變 B-1 clarify；L4 講 no 變 E 無法判斷。顧客真要拒絕請說「不要 / 取消」。
_KEYWORDS_CHECKOUT = ["結帳", "買單", "付款", "好了", "就這樣", "可以了", "沒了", "沒有了", "夠了", "no", "nope"]

_KEYWORDS_SERVICE = ["客服", "聯絡", "聯繫", "contact", "服務"]

_KEYWORDS_ICED_TEA = ["紅茶", "冰紅茶", "hong cha", "tea"]

_KEYWORDS_SCRATCH = ["刮刮樂", "刮刮", "彩券", "lottery", "scratch"]

# 僅 L4 客服模式內生效
_KEYWORDS_CONTINUE = ["繼續", "接著", "繼續買", "繼續交易", "continue"]

_KEYWORDS_EXIT = ["退出", "取消", "離開", "算了", "不買了", "exit"]


def _contains_any(text: str, keywords: list) -> bool:
    """判斷 text 是否含有 keywords 中的任一詞。"""
    return any(kw in text for kw in keywords)


def classify_intent(text: str, mode: str = "normal") -> str:
    """對顧客輸入做意圖分類。

    優先序（先命中先返回）：
        L4 客服模式：繼續交易 → 退出交易 → 以下通用優先序
        通用：拒絕 → 想一下 → 結帳 → 客服 → 商品:冰紅茶 → 商品:刮刮樂 → 無法判斷

    Args:
        text: 顧客輸入字串
        mode: "normal"（預設）或 "l4_service"（L4 客服模式）

    Returns:
        意圖字串，例：「拒絕」 / 「想一下」 / 「結帳」 / 「客服」 /
                      「商品:冰紅茶」 / 「商品:刮刮樂」 / 「繼續交易」 / 「退出交易」 / 「無法判斷」
    """
    # L4 客服模式專用：繼續交易 / 退出交易（最高優先）
    if mode == "l4_service":
        if _contains_any(text, _KEYWORDS_CONTINUE):
            return "繼續交易"
        if _contains_any(text, _KEYWORDS_EXIT):
            return "退出交易"

    # 通用優先序
    if _contains_any(text, _KEYWORDS_REJECT):
        return "拒絕"
    if _contains_any(text, _KEYWORDS_THINK):
        return "想一下"
    if _contains_any(text, _KEYWORDS_CHECKOUT):
        return "結帳"
    if _contains_any(text, _KEYWORDS_SERVICE):
        return "客服"
    if _contains_any(text, _KEYWORDS_ICED_TEA):
        return "商品:冰紅茶"
    if _contains_any(text, _KEYWORDS_SCRATCH):
        return "商品:刮刮樂"

    return "無法判斷"


# ============================================================
# 中文數字映射（含異體字）
# ============================================================

_CHINESE_DIGIT_MAP: dict = {
    "一": 1, "壹": 1,
    "兩": 2, "二": 2, "貳": 2,
    "三": 3, "參": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陸": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
    "十": 10, "拾": 10,
}


def parse_quantity(text: str) -> int:
    """從顧客輸入解析商品數量。

    判定規則（依優先序）：
        1. 阿拉伯數字優先（re.findall 取第一個 >0 整數）
        2. 中文數字映射（依 _CHINESE_DIGIT_MAP）
        3. 以上皆無命中 → 預設 1

    Args:
        text: 顧客輸入字串

    Returns:
        數量整數，最小為 1
    """
    # 阿拉伯數字優先
    arabic_matches = re.findall(r"\d+", text)
    for m in arabic_matches:
        n = int(m)
        if n > 0:
            return n

    # 中文數字映射
    for char, value in _CHINESE_DIGIT_MAP.items():
        if char in text:
            return value

    # 預設
    return 1
