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
