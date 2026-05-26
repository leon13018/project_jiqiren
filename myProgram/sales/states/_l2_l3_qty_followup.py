"""L2 / L3 鏈路 C 商品加單共享 helper（2026-05-25 加；同日 B 方案升級為多商品）。

職責：把 parse_products 解出的 list 全部加 cart：
    - 有數量者直接加
    - 缺數量者各自進「QTY 追問 sub-loop」

追問 sub-loop 分流（5 個分支）：
    1. 顧客回應含數量 → 用該數量加 cart → 返 True
    2. 顧客 timeout（None）→ 預設 qty=1 加 cart → 返 True（避免無限迴圈）
    3. 顧客講「客服」→ print_terminal 印電話 → 重新 speak clarify → 繼續追問
    4. 顧客講「拒絕」（L2 用 mode='l2' / L3 用 mode='normal'）→ skip 該商品 → 返 False
    5. 其他（想一下 / 結帳 / 商品 / 無法判斷）→ speak clarify → 繼續追問

設計原則：
    - 接受 callback 注入（speak / print_terminal / read_customer_input）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 純函式對 cart 做 in-place 修改（與 cart_module.add_item 一致）
    - 返 bool 讓 caller 決定取消後的 UX（L2 = speak L2_B3_REASK，L3 = speak L3_REASK）
"""

from myProgram.sales.constants import (
    PRODUCTS,
    QTY_PROMPT_TEMPLATE,
    QTY_CLARIFY_TEMPLATE,
    SERVICE_PHONE,
    WAIT_NO_RESPONSE,
)
from myProgram.sales.nlu import parse_quantity, has_quantity, classify_intent
from myProgram.sales import cart as cart_module


def resolve_and_add_products(
    products: list,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    classify_intent_mode: str,
) -> bool:
    """多商品版本（2026-05-25 加，B 方案）：把 parse_products 解出的 list 全部加 cart。

    處理流程：
        1. 對每個 (product, qty) pair：
           - qty 不為 None → 直接 cart_module.add_item
           - qty 為 None → 進「該商品的 QTY 追問 sub-loop」（同單品 helper 邏輯）
        2. 追問 sub-loop 內顧客講拒絕 → 該商品 skip（其他仍照加）
        3. 全部跑完返 True if 至少一個加入 cart，否則 False

    Args:
        products: list of (product_name, qty_or_None) — from parse_products
        cart, speak, print_terminal, read_customer_input, classify_intent_mode: 同 single

    Returns:
        True: 至少一個商品加入 cart
        False: 全部商品被拒絕（cart 未變動）
    """
    added_count = 0

    for product, qty in products:
        if qty is not None:
            cart_module.add_item(cart, product, qty)
            added_count += 1
            continue

        # 該商品缺數量 → 進追問 sub-loop
        unit = PRODUCTS[product]["單位"]
        # 多商品場景明示是「哪個商品」要問數量
        speak(QTY_PROMPT_TEMPLATE.format(product=product, unit=unit))

        accepted = _qty_follow_up_sub_loop(
            product=product,
            unit=unit,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode=classify_intent_mode,
            cart=cart,
        )
        if accepted:
            added_count += 1

    return added_count > 0


def _qty_follow_up_sub_loop(
    product: str,
    unit: str,
    speak,
    print_terminal,
    read_customer_input,
    classify_intent_mode: str,
    cart,
) -> bool:
    """QTY 追問 sub-loop（給 resolve_and_add_products 用，每個缺數量商品獨立呼叫）。

    Returns:
        True 已加入 cart（含 timeout 預設 1）；False 顧客在追問內拒絕 → skip 該商品
    """
    while True:
        follow_up = read_customer_input(timeout=WAIT_NO_RESPONSE)

        if follow_up is None:
            # Timeout → 預設 1 加 cart
            cart_module.add_item(cart, product, 1)
            return True

        if has_quantity(follow_up):
            cart_module.add_item(cart, product, parse_quantity(follow_up))
            return True

        follow_intent = classify_intent(follow_up, classify_intent_mode)

        if follow_intent == "客服":
            print_terminal(SERVICE_PHONE)
            speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))
            continue

        if follow_intent == "拒絕":
            return False

        speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))


