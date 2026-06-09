"""L2 / L3 鏈路 C 商品加單共享 helper（2026-05-25 加；同日 B 方案升級為多商品）。

職責：把 parse_products 解出的 list 全部加 cart：
    - 有數量者直接加
    - 缺數量者各自進「QTY 追問 sub-loop」

追問 sub-loop 分流（6 個分支）：
    1. 顧客回應含數量 → 用該數量加 cart → 返 (True, None)
    2. 顧客 timeout（None）→ skip 該商品 → 返 (False, PRODUCT_CANCELLED_NOTICE)（2026-05-29 反轉，原本預設加 1）
    3. 顧客講「客服」→ 進 _service_confirm helper 24s confirm gate（2026-05-31 對齊 L4 pattern）
       - YES → 重 speak QTY_PROMPT_TEMPLATE（鏈路初始提示）→ 繼續追問（不計入 attempts）
       - NO/silent → skip 該商品 → 返 (False, PRODUCT_CANCELLED_NOTICE)
    4. 顧客講「拒絕」（L2 用 mode='l2' / L3 用 mode='normal'）→ skip 該商品 → 返 (False, PRODUCT_CANCELLED_NOTICE)
    5. 顧客講「結帳」（L3 normal mode 「不要 / 不用」→ 視為不追加此商品）→ skip 該商品 → 返 (False, PRODUCT_CANCELLED_NOTICE)
    6. 其他（想一下 / 商品 / 無法判斷）→ speak clarify → attempts++；達 3 次上限 → 返 (False, PRODUCT_CANCELLED_NOTICE)

2026-05-29 UX 統一：4 個 skip 分支（2/4/5/6）全部用同一 PRODUCT_CANCELLED_NOTICE_TEMPLATE
「商品{product}已幫您取消」。2026-05-31 客服 NO/silent 也走同一 notice path。

2026-05-30 合成 speak：4 個 skip 分支不再即時 speak notice，改 return 給 caller；
caller 將 notice 與後續 reask text 用全形「，」拼成單一 speak — 解 Pi demo「先聽到
『商品 X 已幫您取消』再隔停頓聽到『請問需要購買什麼東西嗎？』」UX 不連貫。

設計原則：
    - 接受 callback 注入（speak / print_terminal / read_customer_input）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 純函式對 cart 做 in-place 修改（與 cart_module.add_item 一致）
    - return tuple[bool, str | None] — caller 決定 cancel notice 拼接到 reask 的 UX
"""

from myProgram.sales.constants import (
    PRODUCTS,
    MAX_QTY_PER_ITEM,
    QTY_PROMPT_TEMPLATE,
    QTY_CLARIFY_TEMPLATE,
    QTY_FOLLOWUP_TIMEOUT,
    PRODUCT_CANCELLED_NOTICE_TEMPLATE,
    MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE,
)
from myProgram.sales.nlu import parse_quantity, has_quantity, classify_intent
from myProgram.sales import cart as cart_module
from myProgram.sales.states._service_confirm import service_confirm
from myProgram.sales.states._over_limit_reask import over_limit_reask


def format_cancel_prefix(cancel_notices: list[str]) -> str:
    """根據 cancel notices 數量決定 prefix 文案。

    N==0: "" （無 prefix，caller 直接 speak reask）
    N==1: 直接用 cancel_notices[0]（單商品 wording「商品X已幫您取消」，
          顧客需明確知道哪個被取消）
    N>=2: 用 MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE「有{N}項商品已幫您取消」
          （Pi demo 反饋：逐項列名太冗長，改 count 格式）

    2026-05-30 加：multi-product 從逐商品列名改成 count 格式，避免冗長。
    """
    if not cancel_notices:
        return ""
    if len(cancel_notices) == 1:
        return cancel_notices[0]
    return MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(count=len(cancel_notices))


def resolve_and_add_products(
    products: list,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    classify_intent_mode: str,
    speak_and_wait=None,
) -> tuple[bool, list[str], str | None]:
    """多商品版本（2026-05-25 加，B 方案）：把 parse_products 解出的 list 全部加 cart。

    處理流程：
        1. 對每個 (product, qty) pair：
           - qty 不為 None → 直接 cart_module.add_item
           - qty 為 None → 進「該商品的 QTY 追問 sub-loop」（同單品 helper 邏輯）
        2. 追問 sub-loop 內顧客講拒絕 / timeout / 結帳-as-skip / attempts cap → 該商品 skip
           並累積一個 cancel notice 字串給 caller，由 caller 與後續 reask text 拼接 speak
        3. 全部跑完返 (added_count > 0, cancel_notices)

    Args:
        products: list of (product_name, qty_or_None) — from parse_products
        cart, speak, print_terminal, read_customer_input, classify_intent_mode: 同 single
        speak_and_wait（2026-05-30 v3 加）：同步阻塞 speak callback。為 None 時
            fallback 到 speak（向後兼容既有測試）；production wire-up 必須傳真實
            callback，讓「speak qty prompt 後接 read」path（QTY_PROMPT_TEMPLATE /
            QTY_CLARIFY_TEMPLATE / cart cap mid-loop reprompt）從 TTS 播完才開始
            算 QTY_FOLLOWUP_TIMEOUT=12s — 否則 2-3s 語音吃掉一半預算。
            （2026-05-30 從 WAIT_NO_RESPONSE=6s 改成專屬 12s，給顧客回答數量更寬鬆時間）

    Returns（2026-06-09 加第 3 元素 control，超量重問狀態鏈）:
        (added: bool, cancel_notices: list[str], control: str | None)

        control ∈ {None, "reenter_timeout", "reenter_cancel", "exit_l1"}：
            None             — 正常完成（既有行為）。added / cancel_notices 同舊語意。
            "reenter_timeout" / "reenter_cancel" — 超量重問鏈逾時 / 取消超量繼續，
                                caller 重 speak prefix+entry 回主迴圈；超量商品已丟棄。
            "exit_l1"        — 超量重問鏈選擇退出，caller 走 _dialog_exit_a 退 L1。

        cancel_notices 順序對應 products 內出現順序；caller 用全形「，」拼成單一 speak。
    """
    # 2026-05-30 v3：「speak prompt 後接 read」path 走 speak_and_wait — read 從 TTS
    # 播完才起算 timeout。其他即時通知（cart cap / 已達上限 skip）保持 speak。
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak

    added_count = 0
    cancel_notices: list[str] = []
    over_pending: list = []  # Pass 1 收集的真超量（remaining>0 且 qty>remaining）商品名
    missing: list = []       # Pass 1 收集的缺數量商品名

    # Pass 1：直接給數量者即時分類
    for product, qty in products:
        if qty is None:
            missing.append(product)
            continue
        existing = cart_module.get_quantity(cart, product)
        remaining = MAX_QTY_PER_ITEM - existing
        unit = PRODUCTS[product]["單位"]
        if remaining <= 0:
            # cart 內已達上限 → 完全 skip + speak 通知（at-cap 保留既有行為，不進重問鏈）
            speak(f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加")
            continue
        if qty > remaining:
            # 2026-06-09：不再 cap，收進 over_pending 走 Pass 1.5 合併重問
            over_pending.append(product)
            continue
        # 正常加入
        cart_module.add_item(cart, product, qty)
        added_count += 1

    # Pass 1.5：合併超量重問（情境1）；先於 missing 追問（情境3）
    if over_pending:
        n = len(over_pending)
        control = over_limit_reask(
            over_pending, cart, speak, print_terminal,
            read_customer_input, speak_and_wait,
        )
        if control == "resolved":
            added_count += n
        else:
            # reenter_timeout / reenter_cancel / exit_l1 → 冒泡給 caller，跳過 missing 追問
            return added_count > 0, cancel_notices, control

    # Pass 2：缺數量追問（情境2 在 sub-loop 內 funnel）
    for product in missing:
        unit = PRODUCTS[product]["單位"]
        # 2026-05-30 v3：speak_and_wait — 6s timeout 從 TTS 播完才起算
        _speak_blocking(QTY_PROMPT_TEMPLATE.format(product=product, unit=unit))

        accepted, cancel_notice, control = _qty_follow_up_sub_loop(
            product=product,
            unit=unit,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode=classify_intent_mode,
            cart=cart,
            speak_and_wait=speak_and_wait,
        )
        if control is not None:
            return added_count > 0, cancel_notices, control
        if accepted:
            added_count += 1
        elif cancel_notice is not None:
            cancel_notices.append(cancel_notice)

    return added_count > 0, cancel_notices, None


def _qty_follow_up_sub_loop(
    product: str,
    unit: str,
    speak,
    print_terminal,
    read_customer_input,
    classify_intent_mode: str,
    cart,
    speak_and_wait=None,
) -> tuple[bool, str | None, str | None]:
    """QTY 追問 sub-loop（給 resolve_and_add_products 用，每個缺數量商品獨立呼叫）。

    2026-05-30 合成 speak：4 個 skip 分支（timeout / 拒絕 / 結帳-as-skip / attempts cap）
    不再即時 speak PRODUCT_CANCELLED_NOTICE，改 return 該字串給 caller 拼接到 reask；
    其他即時通知（cart cap / qty 超量）保持即時 speak（與 cancel UX 不同）。

    2026-05-30 v3：speak_and_wait — 「speak prompt 後接 read」path（cart cap 超量
    重提 / attempts clarify / 客服 YES 後重 speak QTY_PROMPT）走 speak_and_wait，讓
    6s read timeout 從 TTS 播完才起算。其他即時通知（cart cap skip 不再 read）保持 speak。

    2026-05-31 客服 path 重構：對齊 L2/L3/L4 dialog 客服統一 _service_confirm helper
    （commit 92fedb6）— 24s confirm gate，YES → 重 speak QTY_PROMPT_TEMPLATE 繼續追問
    （不計 attempts）；NO/silent → skip 該商品（return cancel_notice，對齊既有 skip path）。
    解 Pi demo (2026-05-31) UX 怪：「客服」回「我聽不懂」誤導。

    Returns（2026-06-09 加第 3 元素 control，超量重問狀態鏈）:
        (accepted: bool, cancel_notice: str | None, control: str | None)

        (True, None, None) — 已加入 cart
        (False, cancel_notice_str, None) — 顧客在追問內 timeout / 拒絕 / 結帳-as-skip /
                                     attempts cap / 客服 NO/silent
                                     → skip 該商品；caller 用 notice 拼接 reask 後單一 speak
        (False, None, None) — cart cap 上限 skip（即時 speak 通知已發出，不需 caller 二次處理）
        (False, None, control) — 追問內答超量 → funnel 進 over_limit_reask；非 resolved 時
                                 control ∈ {"reenter_timeout","reenter_cancel","exit_l1"} 冒泡給 caller。
    """
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    cancel_notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product=product)
    attempts = 0
    while True:
        follow_up = read_customer_input(timeout=QTY_FOLLOWUP_TIMEOUT)

        if follow_up is None:
            # Timeout → skip 該商品（2026-05-29 反轉：原本自動加 1 改成視為顧客不買此商品）
            # 2026-05-30：notice 不即時 speak，return 給 caller 拼接到 reask
            return False, cancel_notice, None

        if has_quantity(follow_up):
            qty = parse_quantity(follow_up)
            # Wave 4 hotfix（2026-05-26）— caller 端 cart cap 業務檢查
            # 修 Pi 實機踩坑：顧客輸入「34435454545454545」→ parse_quantity 解析
            # 為天文數字 → cart.add_item assert raise → 程式 crash。
            existing = cart_module.get_quantity(cart, product)
            remaining = MAX_QTY_PER_ITEM - existing
            if remaining <= 0:
                # cart 內已達上限 → 無法再加，即時 speak 提示 + skip 此商品（非 cancel UX，不拼接）
                speak(f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加")
                return False, None, None
            if qty > remaining:
                # 2026-06-09：不再 cap，funnel 進 over_limit_reask（單商品）
                control = over_limit_reask(
                    [product], cart, speak, print_terminal,
                    read_customer_input, speak_and_wait,
                )
                if control == "resolved":
                    return True, None, None       # 已在 reask loop 內 add_item
                if control == "exit_l1":
                    return False, None, "exit_l1"
                return False, None, control        # reenter_timeout / reenter_cancel
            cart_module.add_item(cart, product, qty)
            return True, None, None

        follow_intent = classify_intent(follow_up, classify_intent_mode)

        if follow_intent == "客服":
            # 2026-05-31 改：對齊 L2/L3/L4 客服統一 confirm pattern（commit 92fedb6）
            # 進 _service_confirm helper：印電話 + 24s confirm「請問是否繼續交易？」
            # YES → 回到 qty 追問鏈路 + speak QTY_PROMPT_TEMPLATE（鏈路初始提示，不計 attempts）
            # NO/silent → return (False, cancel_notice) skip 該商品
            #   （對齊既有 timeout / 拒絕 / 結帳-as-skip path）
            result = service_confirm(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                speak_and_wait=speak_and_wait,
                allow_scan=False,
            )
            if result == "yes":
                _speak_blocking(QTY_PROMPT_TEMPLATE.format(product=product, unit=unit))
                continue
            # result == "no" → skip 該商品（caller 用 cancel_notice 拼接 reask）
            return False, cancel_notice, None

        if follow_intent == "拒絕":
            # 2026-05-30：notice 不即時 speak，return 給 caller 拼接到 reask
            return False, cancel_notice, None

        if follow_intent == "結帳":
            # B3：L3 normal mode「不要 / 不用」被分類為結帳意圖 — 視為「不追加此商品」
            # 2026-05-30：notice 不即時 speak，return 給 caller 拼接到 reask
            return False, cancel_notice, None

        # 其他（無法判斷 / 想一下 / 商品 等）
        attempts += 1
        if attempts >= 3:
            # B4：達 attempts cap → notice 不即時 speak，return 給 caller 拼接到 reask
            return False, cancel_notice, None
        # 2026-05-30 v3：speak_and_wait — 6s read timeout 從 TTS 播完才起算
        _speak_blocking(QTY_CLARIFY_TEMPLATE.format(unit=unit))


