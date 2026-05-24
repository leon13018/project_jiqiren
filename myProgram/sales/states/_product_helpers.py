"""L2 / L3 鏈路 C 商品加單共享 helper（2026-05-25 加；同日加 sub-loop dispatcher）。

職責：把「解析商品 → 取得數量（若無則進追問 sub-loop）→ 加入 cart 或回報取消」
共用邏輯抽到一個函式，避免在 l2.py 與 l3.py 內重複 3 次。

追問 sub-loop 分流（2026-05-25 加，使用者實測「亂說預設 1 不合理」後改）：
    1. 顧客回應含數量 → 用該數量加 cart → 返 True
    2. 顧客 timeout（None）→ 預設 qty=1 加 cart → 返 True（保留原行為避免無限迴圈）
    3. 顧客講「客服」→ print_terminal 印電話 → 重新 speak clarify → 繼續追問
    4. 顧客講「拒絕」（L2 用 mode='l2' / L3 用 mode='normal'）→ 取消加單 → 返 False
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


def resolve_and_add_product(
    intent: str,
    response: str,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    classify_intent_mode: str,
) -> bool:
    """解析商品意圖 + 數量（若無則進追問 sub-loop）+ 加入 cart 或回報取消。

    Args:
        intent: 商品意圖字串（"商品:冰紅茶" / "商品:刮刮樂"）
        response: 顧客原始回應文字
        cart: 購物車 dict（in-place 修改）
        speak: callback(text: str)
        print_terminal: callback(text: str) — 客服印電話用
        read_customer_input: callback(timeout: float) -> str | None
        classify_intent_mode: "l2" 或 "normal"（L3）— 決定 reject keyword 集

    Returns:
        True: 已加入 cart（含「顧客有講數量」、「顧客 timeout 預設 1」兩種情況）
        False: 顧客在追問 sub-loop 內講拒絕意圖 → 取消加單，cart 未變動
    """
    product = intent.split(":")[1]

    # 快速路徑：原始 response 已含數量
    if has_quantity(response):
        cart_module.add_item(cart, product, parse_quantity(response))
        return True

    # 無數量 → 進追問 sub-loop
    unit = PRODUCTS[product]["單位"]
    speak(QTY_PROMPT_TEMPLATE.format(unit=unit))

    while True:
        follow_up = read_customer_input(timeout=WAIT_NO_RESPONSE)

        # Timeout（None）→ 預設 1 加 cart 並返回（保留原行為避免無限迴圈）
        if follow_up is None:
            cart_module.add_item(cart, product, 1)
            return True

        # 有數量 → 用該數量加 cart 並返回
        if has_quantity(follow_up):
            cart_module.add_item(cart, product, parse_quantity(follow_up))
            return True

        # 無數量但有回應 → 判 intent 分流
        follow_intent = classify_intent(follow_up, classify_intent_mode)

        if follow_intent == "客服":
            # 進客服流程：印電話，回來後 speak clarify 繼續追問
            print_terminal(SERVICE_PHONE)
            speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))
            continue

        if follow_intent == "拒絕":
            # 顧客取消加這個商品 → caller 自行 speak re-prompt
            return False

        # 其他（想一下 / 結帳 / 商品 / 無法判斷）→ speak clarify 繼續追問
        speak(QTY_CLARIFY_TEMPLATE.format(unit=unit))
