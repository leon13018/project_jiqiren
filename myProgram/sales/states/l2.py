"""L2：詢問需求（顧客互動 — 初次點單）。

對應規格書：resources/plans/業務程式邏輯規劃/L2.md

callback 集合：speak / do_action / print_terminal / read_customer_input
NLU dispatch 特性：L2 跳過「結帳意圖」（規格 L2.md「判定優先序」段第 4 條）
"""

from myProgram.sales.constants import (
    WAIT_NO_RESPONSE,
    SERVICE_PHONE,
    L2_ENTRY_PROMPT,
    L2_REJECT_THANKS,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
)
from myProgram.sales.nlu import classify_intent
from myProgram.sales.states._product_helpers import resolve_and_add_product


def run_l2(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int = 0,
) -> tuple:
    """L2 主迴圈：顧客互動初次點單層。

    Args:
        speak: callback(text: str) — 語音播放
        do_action: callback(name: str) — 動作（規格 TBD，stub 可 no-op）
        print_terminal: callback(text: str) — 印終端（B-2 客服電話）
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應；超時回 None
        cart: 購物車 dict（caller 傳入；run_l2 內 cart_module.add_item）
        think_count: 想一下次數（caller 持有，預設 0）

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L1_via_subroutine_a", "L3"}
        next_think_count: A/C 退出時 reset 0
    """
    # 進入時動作：播詢問語音
    speak(L2_ENTRY_PROMPT)

    # 主等待迴圈
    while True:
        response = read_customer_input(timeout=WAIT_NO_RESPONSE)

        # 超時 → 鏈路 A 拒絕
        if response is None:
            return _l2_exit_a(speak)

        # 判定優先序
        intent = classify_intent(response, "l2")

        # 優先序 1：拒絕
        if intent == "拒絕":
            return _l2_exit_a(speak)

        # 優先序 2：想一下 → B-3
        if intent == "想一下":
            result = _l2_b3(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
            )
            if isinstance(result, tuple):
                return result
            # result is None → B-3 沉默 timeout 後已 speak 重問語音，回主等待
            continue

        # 優先序 3：結帳意圖在 L2 跳過 → 視為無法判斷（B-1）
        if intent == "結帳":
            speak(L2_B1_CLARIFY)
            continue

        # 優先序 4：客服 → B-2
        if intent == "客服":
            print_terminal(SERVICE_PHONE)
            continue  # 自動回 L2 循環

        # 優先序 5：商品 → C（無數量自動追問；追問內 客服/拒絕/亂說 各自分流）
        if intent in ("商品:冰紅茶", "商品:刮刮樂"):
            added = resolve_and_add_product(
                intent=intent,
                response=response,
                cart=cart,
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                classify_intent_mode="l2",
            )
            if added:
                speak(L2_C_ADDED)
                return ("L3", 0)
            # 顧客在追問內取消 → re-prompt L2，繼續主迴圈等下一個商品意圖
            speak(L2_B3_REASK)
            continue

        # 優先序 6：無法判斷 → B-1
        speak(L2_B1_CLARIFY)
        continue


def _l2_exit_a(speak) -> tuple:
    """L2 鏈路 A 拒絕退出：speak 謝謝語音，回傳 (L1_via_subroutine_a, 0)。"""
    speak(L2_REJECT_THANKS)
    return ("L1_via_subroutine_a", 0)


def _l2_b3(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | None:
    """B-3 想一下鏈路。

    Args:
        think_count: 當前的想一下次數（進入此函式前的值，函式內累加）

    Returns:
        tuple → 已決定退出（鏈路 A 或 C）
        None  → 沉默 timeout 後說完重問語音，回主等待（由 run_l2 主迴圈繼續）
    """
    think_count += 1

    # 第 3 次：跳過沉默，直接走鏈路 A
    if think_count >= 3:
        speak(L2_B3_THIRD_REJECT)
        return _l2_exit_a(speak)

    # 沉默等待
    inner_response = read_customer_input(timeout=WAIT_NO_RESPONSE)

    if inner_response is not None:
        # 沉默期有回應 → 重跑判定優先序
        return _l2_dispatch_response(
            response=inner_response,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )

    # 沉默期 timeout → 重問語音後回主等待
    speak(L2_B3_REASK)
    return None  # 回主迴圈


def _l2_dispatch_response(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | None:
    """對一個顧客回應字串重跑 L2 判定優先序。

    與 run_l2 主迴圈內相同邏輯，抽出供 B-3 沉默期中斷後重用。

    Returns:
        tuple → 已決定退出
        None  → 應回主等待（B-1 / B-2 / B-3 timeout 後已 speak）
    """
    intent = classify_intent(response, "l2")

    if intent == "拒絕":
        return _l2_exit_a(speak)

    if intent == "想一下":
        return _l2_b3(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )

    if intent == "結帳":
        speak(L2_B1_CLARIFY)
        return None  # 回主等待

    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        return None  # 回主等待

    if intent in ("商品:冰紅茶", "商品:刮刮樂"):
        added = resolve_and_add_product(
            intent=intent,
            response=response,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="l2",
        )
        if added:
            speak(L2_C_ADDED)
            return ("L3", 0)
        # 顧客在追問內取消 → re-prompt L2 + 回主等待
        speak(L2_B3_REASK)
        return None

    # 無法判斷 → B-1
    speak(L2_B1_CLARIFY)
    return None  # 回主等待
