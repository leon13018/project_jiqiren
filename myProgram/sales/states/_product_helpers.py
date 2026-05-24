"""L2 / L3 鏈路 C 商品加單共享 helper（2026-05-25 加）。

職責：把「解析商品 → 取得數量（若無則追問）→ 加入 cart」這段 L2/L3 共用
邏輯抽到一個函式，避免在 l2.py 與 l3.py 內重複三次。

設計原則：
    - 接受 callback 注入（speak / read_customer_input）— 同 L2/L3 主迴圈風格
    - 嚴格不 import 廠商 SDK（選項 C）
    - 純函式對 cart 做 in-place 修改（與 cart_module.add_item 一致）
"""

from myProgram.sales.constants import PRODUCTS, QTY_PROMPT_TEMPLATE, WAIT_NO_RESPONSE
from myProgram.sales.nlu import parse_quantity, has_quantity
from myProgram.sales import cart as cart_module


def resolve_and_add_product(
    intent: str,
    response: str,
    cart,
    speak,
    read_customer_input,
) -> None:
    """解析商品意圖 + 數量（若原始 response 無數量則追問顧客）+ 加入 cart。

    流程：
        1. 從 intent 字串取出商品名（"商品:冰紅茶" → "冰紅茶"）
        2. 若 response 內含數量（has_quantity）→ 直接 parse_quantity 取值
        3. 否則 → speak 追問語音（QTY_PROMPT_TEMPLATE）→ 讀顧客 follow-up
           - follow-up 有回應 → parse_quantity（沒命中數字仍 fallback 為 1）
           - follow-up timeout（None）→ 預設 qty=1
        4. cart_module.add_item(cart, product, qty)

    Args:
        intent: 商品意圖字串（"商品:冰紅茶" / "商品:刮刮樂"）
        response: 顧客原始回應文字
        cart: 購物車 dict（in-place 修改）
        speak: callback(text: str) -> None
        read_customer_input: callback(timeout: float) -> str | None
    """
    product = intent.split(":")[1]

    if has_quantity(response):
        qty = parse_quantity(response)
    else:
        # 追問數量
        unit = PRODUCTS[product]["單位"]
        speak(QTY_PROMPT_TEMPLATE.format(unit=unit))
        follow_up = read_customer_input(timeout=WAIT_NO_RESPONSE)
        if follow_up is not None:
            qty = parse_quantity(follow_up)
        else:
            # 顧客 timeout 無回應 → 預設 1
            qty = 1

    cart_module.add_item(cart, product, qty)
