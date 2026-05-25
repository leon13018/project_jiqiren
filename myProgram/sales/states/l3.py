"""L3：詢問額外需求（顧客互動 — 加單迴圈）。

對應規格書：resources/plans/業務程式邏輯規劃/L3.md

callback 集合：speak / do_action / print_terminal / read_customer_input
NLU dispatch 特性：
    - L3 用全 6 步白名單（不跳過任何類別）
    - 6s timeout 走 C-2 第一段（非 L2 的 A 拒絕）
    - think_count == 3 走 C-2 第二段（非 L2 的 A 拒絕）
    - 鏈路 A 拒絕清空 cart（整單作廢）
"""

import time

from myProgram.sales.constants import (
    WAIT_NO_RESPONSE,
    AUTO_CHECKOUT_NOTICE,
    SERVICE_PHONE,
    UNCLEAR_MAX,
    L3_ENTRY_PROMPT,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L3_UNCLEAR_FINAL_PROMPT,
)
from myProgram.sales.nlu import classify_intent
from myProgram.sales import cart as cart_module
from myProgram.sales.states._product_helpers import resolve_and_add_product


def run_l3(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int = 0,
) -> tuple:
    """L3 主迴圈：加單迴圈層。

    顧客已從 L2 加了第一件商品，詢問是否還要加單。
    唯一進 L4 結帳的入口層。

    Args:
        speak: callback(text: str) — 語音播放
        do_action: callback(name: str) — 動作（規格 TBD，stub 可 no-op）
        print_terminal: callback(text: str) — 印終端（B-2 客服電話）
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應；超時回 None
        cart: 購物車 dict（caller 傳入；L3-A 會 clear_cart）
        think_count: 想一下次數（caller 持有，預設 0）

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L1_via_subroutine_a", "L4"}
        next_think_count: A/C-1 退出時 reset 0
    """
    # 進入時動作：播詢問語音
    speak(L3_ENTRY_PROMPT)

    # 進入主等待迴圈（不重播進入語音）
    return _l3_main_loop(
        speak=speak,
        do_action=do_action,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _l3_exit_a(speak, cart) -> tuple:
    """L3 鏈路 A 拒絕退出：speak 語音、清空 cart，回傳 (L1_via_subroutine_a, 0)。"""
    speak(L3_REJECT_THANKS)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0)


def _l3_final_confirmation(
    speak,
    print_terminal,
    read_customer_input,
    cart,
) -> tuple | None:
    """L3 B-1 累積到 UNCLEAR_MAX 後的最終確認子狀態（2026-05-25 加，仿 L4 D 最終確認）。

    顧客已被 B-1 無法判斷 UNCLEAR_MAX 次。給最後 WAIT_NO_RESPONSE 秒選擇：
        - 取消訂單（"1" / 「退出」/「取消」/「不要了」等）→ 清 cart 回 L1
        - 繼續加單（"2" / 「繼續」/「continue」等）→ caller 重置 unclear_count 回 L3 主迴圈
        - 亂回答 → 重印 prompt，**6s 倒數不重置**（time.time() wall-clock 追蹤）
        - 6s timeout → 視為取消（清 cart 回 L1）

    Returns:
        tuple ("L1_via_subroutine_a", 0) → 取消（caller 直接 return）
        None  → 顧客選繼續（caller 應 reset unclear_count = 0）

    S1 注意：用 time.time() wall-clock 追蹤；S4+ 上 threading 時改 worker thread + timer。
    """
    print_terminal(L3_UNCLEAR_FINAL_PROMPT)
    speak(L3_UNCLEAR_FINAL_PROMPT)

    start = time.time()

    while True:
        elapsed = time.time() - start
        remaining = WAIT_NO_RESPONSE - elapsed
        if remaining <= 0:
            return _l3_exit_a(speak, cart)

        response = read_customer_input(timeout=remaining)

        if response is None:
            return _l3_exit_a(speak, cart)

        if response == "1":
            return _l3_exit_a(speak, cart)

        if response == "2":
            return None

        # 語音意圖（用 l4_service mode，含 繼續 / 退出 keyword + no/nope → 退出）
        intent = classify_intent(response, "l4_service")
        if intent == "退出交易":
            return _l3_exit_a(speak, cart)
        if intent == "繼續交易":
            return None

        # 亂回答 → 重印 prompt（6s 倒數不重置，下輪 elapsed 繼續累積）
        print_terminal(L3_UNCLEAR_FINAL_PROMPT)
        speak(L3_UNCLEAR_FINAL_PROMPT)


def _l3_c2_second_stage(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple:
    """C-2 第二段：播警告語音後等待 AUTO_CHECKOUT_NOTICE 秒。

    - 有回應 → 重跑判定優先序
    - timeout → 直接進 L4

    Returns:
        tuple (next_state, next_think_count)
    """
    # C-2 第一段語音（f-string 插值 AUTO_CHECKOUT_NOTICE，未來改數值文案自動同步）
    c2_warning = f"請問是否要結帳？如果沒回應，{AUTO_CHECKOUT_NOTICE} 秒後將為您結帳"
    speak(c2_warning)

    # 第二段等待
    response = read_customer_input(timeout=AUTO_CHECKOUT_NOTICE)

    if response is None:
        # 第二段 timeout → L4
        return ("L4", 0)

    # 第二段有回應 → 重跑判定優先序
    result = _l3_dispatch_response(
        response=response,
        speak=speak,
        do_action=do_action,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )

    if isinstance(result, tuple):
        return result

    # _l3_dispatch_response 回 None（B-1/B-2/B-3）或 int（think_count 更新）
    # → 回主等待迴圈繼續等待
    if isinstance(result, int):
        think_count = result

    # 繼續主等待（重入 L3 主迴圈）
    return _l3_main_loop(
        speak=speak,
        do_action=do_action,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _l3_b4(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | int | None:
    """B-4 想一下鏈路。

    Args:
        think_count: 進入此函式前的值，函式內累加

    Returns:
        tuple → 已決定退出（鏈路 A 或 C-2 第二段等）
        int   → think_count 已更新，回主等待
        None  → 沉默 timeout 後已 speak 重問，回主等待（think_count 未回傳）
    """
    think_count += 1

    # 第 3 次（think_count == 3）：跳過沉默，直接走 C-2 第二段邏輯
    if think_count >= 3:
        return _l3_c2_second_stage(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )

    # 沉默等待（think_count < 3）
    inner_response = read_customer_input(timeout=WAIT_NO_RESPONSE)

    if inner_response is not None:
        # 沉默期有回應 → 重跑判定優先序
        result = _l3_dispatch_response(
            response=inner_response,
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )
        if isinstance(result, tuple):
            return result
        if isinstance(result, int):
            return result  # think_count 更新，回主等待
        return think_count  # B-1/B-2/B-3 → 回主等待

    # 沉默期 timeout → speak 重問後回主等待
    speak(L3_REASK)
    return think_count  # 回傳更新後的 think_count，讓主迴圈繼續


def _l3_dispatch_response(
    response: str,
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | int | None:
    """對一個顧客回應字串跑 L3 判定優先序（全 6 步，mode='normal'）。

    Returns:
        tuple → 已決定退出（next_state, next_think_count）
        int   → think_count 已更新，應回主等待
        None  → 應回主等待（B-1 / B-2 已處理完）
    """
    intent = classify_intent(response, "normal")

    # 優先序 2：拒絕 → 鏈路 A
    if intent == "拒絕":
        return _l3_exit_a(speak, cart)

    # 優先序 3：想一下 → 鏈路 B-4
    if intent == "想一下":
        return _l3_b4(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )

    # 優先序 4：結帳意圖 → 鏈路 C-1
    if intent == "結帳":
        speak(L3_C1_CHECKOUT_GO)
        return ("L4", 0)

    # 優先序 5：客服 → 鏈路 B-2
    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        return None  # 回主等待

    # 優先序 6：商品 → 鏈路 B-3（無數量自動追問；追問內 客服/拒絕/亂說 各自分流）
    if intent in ("商品:冰紅茶", "商品:刮刮樂"):
        # added True/False 兩條都 speak L3_REASK + 回主等待（user 要求：取消後一樣 re-prompt）
        resolve_and_add_product(
            intent=intent,
            response=response,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="normal",
        )
        speak(L3_REASK)
        return None  # 回主等待

    # 優先序 7：都沒命中 → 鏈路 B-1（無法判斷）
    speak(L3_B1_CLARIFY)
    return None  # 回主等待


def _l3_main_loop(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple:
    """L3 主等待迴圈（內部函式，供 C-2 / B-4 回主等待時使用）。

    不播進入語音，直接進入等待循環。

    內部 unclear_count：B-1「無法判斷」累積計數（2026-05-25 加，仿 L4 但用 UNCLEAR_MAX）
    - 任何被識別意圖（拒絕 / 想一下 / 結帳 / 客服 / 商品）→ reset 0
    - B-1 命中 → ++；達 UNCLEAR_MAX → 進 _l3_final_confirmation 子狀態
    - 主迴圈內 inline 處理 B-1（不走 _l3_dispatch_response，避免改 dispatch signature）；
      _l3_dispatch_response 內的 B-1 path 僅供 C-2 / B-4 sub-dispatch 路徑使用，
      該 path 不參與 unclear_count 累積（與 think_count 在 sub-dispatch 不傳遞行為一致）

    Returns:
        tuple (next_state, next_think_count)
    """
    unclear_count = 0

    while True:
        response = read_customer_input(timeout=WAIT_NO_RESPONSE)

        if response is None:
            return _l3_c2_second_stage(
                speak=speak,
                do_action=do_action,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
            )

        intent = classify_intent(response, "normal")

        # B-1 路徑（不命中任何已知意圖）→ inline 處理 + unclear_count 累積
        if intent not in (
            "拒絕", "想一下", "結帳", "客服", "商品:冰紅茶", "商品:刮刮樂",
        ):
            unclear_count += 1
            if unclear_count >= UNCLEAR_MAX:
                final = _l3_final_confirmation(
                    speak=speak,
                    print_terminal=print_terminal,
                    read_customer_input=read_customer_input,
                    cart=cart,
                )
                if final is not None:
                    return final  # 取消 → ("L1_via_subroutine_a", 0)
                # 顧客選繼續 → reset unclear_count + 重播 L3 進入語音 + 回主等待
                unclear_count = 0
                speak(L3_ENTRY_PROMPT)
                continue
            speak(L3_B1_CLARIFY)
            continue

        # 已識別意圖 → reset unclear_count + delegate 到既有 dispatch
        unclear_count = 0
        result = _l3_dispatch_response(
            response=response,
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )

        if isinstance(result, tuple):
            return result

        if isinstance(result, int):
            think_count = result
            continue

        continue
