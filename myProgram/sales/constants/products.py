"""商品定義常數（P8 拆分自 constants.py）。

包含：
    PRODUCTS dict（冰紅茶、刮刮樂）
    MAX_QTY_PER_ITEM（單次加入上限）
    QTY_PROMPT_TEMPLATE / QTY_CLARIFY_TEMPLATE（追問數量用語）
"""

__all__ = [
    "PRODUCTS",
    "MAX_QTY_PER_ITEM",
    "QTY_PROMPT_TEMPLATE",
    "QTY_CLARIFY_TEMPLATE",
    "AT_CAP_NOTICE_TEMPLATE",
    "QTY_NUMBER_WORDS",
]

# ============================================================
# 商品定義
# ============================================================

PRODUCTS: dict = {
    "冰紅茶": {"原價": 30, "折扣": 0.9, "實際": 27, "單位": "瓶"},
    "刮刮樂": {"原價": 200, "折扣": 0.9, "實際": 180, "單位": "張"},
}

# 單一商品單次加入的數量上限（防天文數字 / STT 雜訊 / 顧客誤念）
# 超過此值 → add_item raise AssertionError，由 caller 處理
MAX_QTY_PER_ITEM: int = 50

# L2 / L3 鏈路 C 商品意圖無數量時追問語音（2026-05-25 加）
# 用法：speak(QTY_PROMPT_TEMPLATE.format(product="冰紅茶", unit="瓶"))
QTY_PROMPT_TEMPLATE: str = "請問{product}要幾{unit}？"

# QTY 追問子迴圈內，顧客亂說 / 客服回來時的 clarify 語音（2026-05-25 加）
# 同 L2/L3 B-1 風格：「不好意思我聽不太懂...或者您想聯繫客服？」
QTY_CLARIFY_TEMPLATE: str = "不好意思我聽不太懂，請問您要幾{unit}，或者您想聯繫客服？"

# L2 / L3 加單時 cart 已達單筆上限的即時通知（2026-06-11 抽常數；
# 原 inline 於 _l2_l3_qty_followup.py 兩處逐字重複）
AT_CAP_NOTICE_TEMPLATE: str = "{product}已經點到單筆上限 {max_qty} {unit}，無法再加"

# 拼音糾錯候選用 canonical 口語量詞（2026-06-14 Phase B 從 _l2_l3_qty_followup 下移共用）。
# 問數量 sub-loop（Phase A）與 parse_products 內嵌數量糾錯（Phase B ①）共用此清單，
# 避免兩處平行維護（對齊既有「keyword 共享常數」慣例）。
# 一個量值一個口語詞（2 用「兩」），保歧義安全閥有效——避免同義候選互相壓低 margin。
QTY_NUMBER_WORDS: tuple = ("一", "兩", "三", "四", "五", "六", "七", "八", "九", "十")
