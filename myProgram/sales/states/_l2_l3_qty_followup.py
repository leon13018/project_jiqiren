"""L2 / L3 鏈路 C 商品加單共享 helper（2026-05-25 加；同日 B 方案升級為多商品）。

職責：把 parse_products 解出的 list 全部加 cart：
    - 有數量者直接加
    - 缺數量者各自進「QTY 追問 sub-loop」

追問 sub-loop 分流（6 個分支）：
    1. 顧客回應含數量 → 用該數量加 cart → 返 True
    2. 顧客 timeout（None）→ 預設 qty=1 加 cart → 返 True（避免無限迴圈）
    3. 顧客講「客服」→ print_terminal 印電話 → 重新 speak clarify → 繼續追問（不計入 attempts）
    4. 顧客講「拒絕」（L2 用 mode='l2' / L3 用 mode='normal'）→ skip 該商品 → 返 False
    5. 顧客講「結帳」（L3 normal mode 「不要 / 不用」→ 視為不追加此商品）→ 返 False
    6. 其他（想一下 / 商品 / 無法判斷）→ speak clarify → attempts++；達 3 次上限 speak 跳過 + 返 False

設計原則：
    - 接受 callback 注入（speak / print_terminal / read_customer_input）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 純函式對 cart 做 in-place 修改（與 cart_module.add_item 一致）
    - 返 bool 讓 caller 決定取消後的 UX（L2 = speak L2_B3_REASK，L3 = speak L3_REASK）
"""

from myProgram.sales.constants import (
    PRODUCTS,
    MAX_QTY_PER_ITEM,
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
            # Wave 4 hotfix 2（2026-05-26）— caller 端 cart cap 業務檢查
            # 修 Pi 實機踩坑：顧客一次說「紅茶 34435454545454545」走此路徑
            # → parse_products 直接返天文數字 → cart.add_item assert raise → crash。
            # 設計差異 vs hotfix 1：本路徑是「一次給」（顧客一句話含商品+數量），
            # 無 follow-up 重新追問機會 → 採「cap 為 remaining + speak 通知實際加入量」。
            existing = cart_module.get_quantity(cart, product)
            remaining = MAX_QTY_PER_ITEM - existing
            unit = PRODUCTS[product]["單位"]
            if remaining <= 0:
                # cart 內已達上限 → 完全 skip + speak 通知
                speak(f"{product}已達單筆訂單上限 {MAX_QTY_PER_ITEM} {unit}，無法再加")
                continue
            if qty > remaining:
                # 超量（含天文數字 / 累加超量）→ cap 為 remaining + speak 透明告知
                cart_module.add_item(cart, product, remaining)
                speak(f"{product}已加入 {remaining} {unit}（達單筆上限 {MAX_QTY_PER_ITEM} {unit}，您要求的 {qty} 超量）")
                added_count += 1
                continue
            # 正常加入
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
    attempts = 0
    while True:
        follow_up = read_customer_input(timeout=WAIT_NO_RESPONSE)

        if follow_up is None:
            # Timeout → 預設 1 加 cart
            cart_module.add_item(cart, product, 1)
            return True

        if has_quantity(follow_up):
            qty = parse_quantity(follow_up)
            # Wave 4 hotfix（2026-05-26）— caller 端 cart cap 業務檢查
            # 修 Pi 實機踩坑：顧客輸入「34435454545454545」→ parse_quantity 解析
            # 為天文數字 → cart.add_item assert raise → 程式 crash。
            # 解法：add_item 前先查 cart 既有量算 remaining，超量 → speak 友善
            # 提示 + 不計 attempts 重新追問（speak 已給明確指引算合理重試）。
            existing = cart_module.get_quantity(cart, product)
            remaining = MAX_QTY_PER_ITEM - existing
            if remaining <= 0:
                # cart 內已達上限 → 無法再加，speak 提示 + skip 此商品
                speak(f"{product}已達單筆訂單上限 {MAX_QTY_PER_ITEM} {unit}，無法再加")
                return False
            if qty > remaining:
                # 顧客單筆超量（含天文數字 / 累加超量）→ speak 剩餘額度 + 重新追問
                speak(f"{product}還可加最多 {remaining} {unit}（已有 {existing}），請重新告訴我數量")
                continue
            cart_module.add_item(cart, product, qty)
            return True

        follow_intent = classify_intent(follow_up, classify_intent_mode)

        if follow_intent == "客服":
            # 客服不計入 attempts
            print_terminal(SERVICE_PHONE)
            speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))
            continue

        if follow_intent == "拒絕":
            return False

        if follow_intent == "結帳":
            # B3：L3 normal mode「不要 / 不用」被分類為結帳意圖 — 視為「不追加此商品」
            return False

        # 其他（無法判斷 / 想一下 / 商品 等）
        attempts += 1
        if attempts >= 3:
            # B4：達 attempts cap → speak 跳過 + 退出
            speak(f"好的，這次先不加{product}")
            return False
        speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))


