"""L4：印金額 + 等掃碼（結帳層；2026-05-30 重構簡化版）。

對應規格書：resources/plans/業務程式邏輯規劃/L4.md

設計（重構版）：
    - 單一 wall-clock budget L4_TOTAL_BUDGET = 30s（從進場 prompt 播完起算）
    - 每 L4_PROMPT_INTERVAL = 12s 沒回應重新 speak L4_REMIND_PROMPT（不重置 budget）
    - 亂輸入只印 L4_UNCLEAR_NOTICE（不重置 budget、不計次）
    - budget 耗盡 → forced exit（speak L4_D_FORCED_EXIT + clear cart + 退 L1）
    - 鏈路：A 掃碼成功 → L5；B 拒絕（cancel_confirm gated）→ 退 L1；C 客服→特殊模式
    - 客服模式共用主 budget remaining（移除原獨立 L4_SERVICE_TIMEOUT=60）

從舊版移除（user 反饋過度設計）：
    - loop_count（D 鏈路 4 階段語氣 6 次循環機制）
    - unclear_count（E 鏈路達 3 自動進客服機制）
    - _l4_final_confirmation（達上限後「1=取消 / 2=繼續」18s 子狀態）
    - L4_SERVICE_TIMEOUT 獨立 60s（客服共用主 budget）

Return shape 保持 (next_state, 0, 0) 3-tuple — 與 logic.py 既有 unpack 相容
（兩個 0 占位，未來若改 2-tuple 需同步 logic.py），avoid breaking change。
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    SERVICE_PHONE,
    L4_TOTAL_BUDGET,
    L4_PROMPT_INTERVAL,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_QR_MOCK_HINT,
    L4_A_PAY_SUCCESS,
    L4_ACK_GENTLE,
    L4_B_CANCEL_THANKS,
    L4_C_OPTIONS_PROMPT,
    L4_D_FORCED_EXIT,
    L4_REMIND_PROMPT,
    L4_UNCLEAR_NOTICE,
    ACTION_L4_PAY,
    CANCEL_DECLINED_NOTICE,
)
from myProgram.sales.nlu import classify_intent
from myProgram.sales import cart as cart_module
from myProgram.sales.states._cancel_confirm import cancel_confirm


def run_l4(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    *,
    opencv_disable,
    do_action,
    speak_and_wait=None,
) -> tuple:
    """L4 主迴圈：結帳層（印金額 + 等掃碼）。

    顧客從 L3 攜帶 cart 進入，等掃碼付款。
    鏈路 A（掃碼）→ L5；
    鏈路 B（拒絕，cancel_confirm gated）→ 清空 cart → L1（子例程 A）；
    鏈路 C（客服）→ 客服特殊模式（共用主 budget remaining，2026-05-30 重構）；
    無回應 / 亂輸入 → 12s 重提示 / 不重置 budget；budget 耗盡 → forced exit。

    Args:
        speak: callback(text: str) — 語音播放
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        cart: 購物車 dict（從 L3 帶來）

        opencv_disable: callback() — 關閉 OpenCV 偵測。L4 結帳期間不需要偵測
            （顧客已在面前掃碼），預設 no-op 給單元測試方便；production wire-up
            必須傳真實 callback（2026-05-25 OpenCV 作用域規格修訂）。
            注意：dialog 進入時已 disable 過；本處 disable 是 defence-in-depth，
            涵蓋未來「不經 dialog 直接進 L4」的可能架構。
        do_action: callback(name: str) — 同步阻塞跑廠商動作組（S3 加，2026-05-27）。
            L4 內**只**在鏈路 A 掃碼付款成功（speak L4_A_PAY_SUCCESS 後）觸發
            ACTION_L4_PAY（鞠躬）；兩處進入鏈路 A 都會跑：
              (a) `_l4_dispatch_response` 終端 's' 路徑
              (b) `_l4_service_mode` 客服模式內 's' 路徑
            L4 其他鏈路（B 取消 / C 客服 prompt / 無回應重提示）不跑動作。

    Returns:
        (next_state, 0, 0) — 兩個 0 占位，保留 3-tuple shape 與 logic.py 相容；
        next_state ∈ {"L1_via_subroutine_a", "L5"}
    """
    # 進入 L4 → OpenCV 不需要（顧客已在掃碼），明示關閉（防呆）
    opencv_disable()

    # 進入時動作：計算總額、印明細、speak 總額語音
    total = cart_module.calc_total(cart)
    _l4_print_entry_detail(cart, total, print_terminal)
    # 2026-05-30 v2：speak_and_wait 進場 prompt 後算 deadline — 顧客拿到完整
    # L4_TOTAL_BUDGET budget，而非「budget 減 entry prompt 播放時間」
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    _speak_blocking(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))

    # 2026-05-30 重構：單一 wall-clock budget L4_TOTAL_BUDGET
    deadline = time.monotonic() + L4_TOTAL_BUDGET

    # 主等待迴圈
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _l4_exit_d_forced(speak, cart)

        # 每 L4_PROMPT_INTERVAL 沒回應 → 重 speak L4_REMIND_PROMPT（不重置 budget）
        response = read_customer_input(timeout=min(L4_PROMPT_INTERVAL, remaining))

        if response is None:
            speak(L4_REMIND_PROMPT)
            continue

        # 有回應 → 共用 dispatcher 判定優先序
        result = _l4_dispatch_response(
            response=response,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            deadline=deadline,
            do_action=do_action,
            speak_and_wait=speak_and_wait,
        )
        if isinstance(result, tuple):
            return result
        # "ack" / None → 回主迴圈繼續，不重置 budget
        # ("ack" = 等待安撫 / cancel_confirm NO / 亂輸入；None = 客服繼續)
        continue


def _l4_print_entry_detail(cart, total: int, print_terminal) -> None:
    """印 L4 進入時的金額明細（2026-05-25 加九折計算公式明示）。

    格式：
        ====================================
        您的訂單（全品項九折優惠）：
          商品 ×qty 單位｜原價 X × 0.9 = Y 元/單位｜小計 Y × qty = Z 元
          ...
        ------------------------------------
        總金額：N 元（已含九折優惠）
        請掃碼付款（終端輸入 s + Enter 模擬掃碼成功）
        ====================================

    Why 寫出 *0.9 公式：使用者要求顯示完整計算，避免被誤認為算錯。
    """
    lines = [
        "====================================",
        "您的訂單（全品項九折優惠）：",
    ]
    for product, qty in cart.items():
        info = PRODUCTS[product]
        original = info["原價"]
        discount = info["折扣"]
        unit_price = info["實際"]
        unit_name = info["單位"]
        subtotal = unit_price * qty
        lines.append(
            f"  {product} ×{qty} {unit_name}｜"
            f"原價 {original} × {discount} = {unit_price} 元/{unit_name}｜"
            f"小計 {unit_price} × {qty} = {subtotal} 元"
        )
    lines.append("------------------------------------")
    lines.append(f"總金額：{total} 元（已含九折優惠）")
    # C21 (2026-05-26 Wave 7a)：QR mock 提示抽常數；未來真 QR 接入時只動一處
    lines.append(L4_QR_MOCK_HINT)
    lines.append("====================================")
    print_terminal("\n".join(lines))


def _l4_exit_b(speak, cart) -> tuple:
    """鏈路 B 退出：speak 取消語音、清空 cart，返回 L1（子例程 A）。"""
    speak(L4_B_CANCEL_THANKS)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_exit_d_forced(speak, cart) -> tuple:
    """budget 耗盡強制退：speak 取消語音、清空 cart，返回 L1（子例程 A）。"""
    speak(L4_D_FORCED_EXIT)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_dispatch_response(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    deadline: float,
    do_action,
    speak_and_wait=None,
) -> tuple | None | str:
    """L4 判定優先序 dispatcher（重構簡化版）。

    判定優先序：
        1. 終端 s → 鏈路 A（掃碼成功）→ L5
        2. 等待安撫意圖 → speak 溫和回應，不重置 budget
        3. 拒絕意圖 → cancel_confirm gate → YES 退 L1；NO speak DECLINED 不重置 budget
        4. 客服意圖 → 鏈路 C 客服特殊模式（共用主 budget remaining）
        5. 其他（想一下 / 結帳 / 商品 / 無法判斷）→ speak L4_UNCLEAR_NOTICE 不重置 budget

    Returns:
        tuple → 已決定（next_state, 0, 0）
        None  → 客服繼續（caller continue 不重置 budget）
        "ack" → 等待安撫 / cancel_confirm NO / 亂輸入（caller continue 不重置 budget）
    """
    # 優先序 1：終端 s → 鏈路 A（S3：speak 付款成功語音後跑鞠躬動作）
    if response == "s":
        speak(L4_A_PAY_SUCCESS)
        do_action(ACTION_L4_PAY)
        return ("L5", 0, 0)

    intent = classify_intent(response, "l4")

    # 優先序 2：等待安撫 → 溫和回應，不重置 budget
    if intent == "等待安撫":
        speak(L4_ACK_GENTLE)
        return "ack"

    # 優先序 3：拒絕 → cancel_confirm gate
    if intent == "拒絕":
        if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
            return _l4_exit_b(speak, cart)
        speak(CANCEL_DECLINED_NOTICE)
        return "ack"

    # 優先序 4：客服 → 鏈路 C 特殊模式（共用主 budget remaining）
    if intent == "客服":
        result = _l4_service_mode(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            deadline=deadline,
            do_action=do_action,
            speak_and_wait=speak_and_wait,
        )
        if result is not None:
            return result
        return None  # 客服繼續

    # 優先序 5：想一下 / 結帳 / 商品 / 無法判斷 → 印 unclear notice，不重置 budget
    speak(L4_UNCLEAR_NOTICE)
    return "ack"


def _l4_service_mode(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    deadline: float,
    do_action,
    speak_and_wait=None,
) -> tuple | None:
    """L4 鏈路 C 客服特殊模式（2026-05-30 重構：移除獨立 60s timeout，共用主 budget remaining）。

    顯示電話 + 提示選項，等顧客明確選擇退出或繼續。
    L4_PROMPT_INTERVAL 沒回應 → 重 speak L4_C_OPTIONS_PROMPT；
    亂輸入 → 印 L4_UNCLEAR_NOTICE；都不重置主 budget。
    budget 耗盡 → 清 cart 退 L1。

    Returns:
        tuple → 已決定（退出 L1 或掃碼 L5）
        None  → 顧客選「繼續」→ 回主迴圈
    """
    print_terminal(SERVICE_PHONE)
    speak(L4_C_OPTIONS_PROMPT)

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        response = read_customer_input(timeout=min(L4_PROMPT_INTERVAL, remaining))

        if response is None:
            speak(L4_C_OPTIONS_PROMPT)
            continue

        # 終端 s → 視為掃碼成功 → L5
        if response == "s":
            speak(L4_A_PAY_SUCCESS)
            do_action(ACTION_L4_PAY)
            return ("L5", 0, 0)

        # 終端 1 → 退出（清空 cart）
        if response == "1":
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        # 終端 2 → 繼續
        if response == "2":
            return None

        intent = classify_intent(response, "l4_service")

        if intent == "退出交易":
            # 2026-05-29 cross-L cancel：service mode 內語音退出 intent → 先過 cancel_confirm gate
            # （終端 "1" / silent timeout 仍直接退，不 gate — 那些是介面操作 / 預設安全退場）
            if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
                cart_module.clear_cart(cart)
                return ("L1_via_subroutine_a", 0, 0)
            speak(CANCEL_DECLINED_NOTICE)
            speak(L4_C_OPTIONS_PROMPT)
            continue

        if intent == "拒絕":
            # fallback：不強制顧客學「退出」一詞
            if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
                cart_module.clear_cart(cart)
                return ("L1_via_subroutine_a", 0, 0)
            speak(CANCEL_DECLINED_NOTICE)
            speak(L4_C_OPTIONS_PROMPT)
            continue

        if intent == "繼續交易":
            return None

        # 不命中 → 印 unclear notice（service mode 同主迴圈設計）
        speak(L4_UNCLEAR_NOTICE)
