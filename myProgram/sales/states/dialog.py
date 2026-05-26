"""統一對話層（2026-05-25 B 方案重構：合併 L2/L3 為單一 cart-state-driven 函式）。

對應規格書：resources/plans/業務程式邏輯規劃/L2.md + L3.md + L0_共通.md「層狀態判定原則」

核心原則：**state machine 由世界狀態（cart）驅動，非動作歷史驅動**。

cart 狀態決定模式：
    - cart 空 → 「L2 模式」：未加單，問需求；timeout = 鏈路 A 拒絕退；結帳意圖視為 B-1 無法判斷
    - cart 非空 → 「L3 模式」：已有訂單，問加單 / 結帳；timeout = C-2 兩段自動結帳；結帳前 confirm

cart 狀態每輪 main loop 迭代都重新判定 — 未來加「刪除商品」功能時若 cart 變空，
下一輪自然回到 L2 模式詢問需求（不需額外 transition 邏輯）。

callback 集合：speak / print_terminal / read_customer_input
（do_action 已於 P1 移除 — S1 stage 從未呼叫，S3+ 真接動作層再加回）

Return shape：(next_state, next_think_count)
    next_state ∈ {"L4", "L1_via_subroutine_a"}
    ※ L2/L3 之間的 transition 已被內化（無 "L3" return 給 logic.py）
"""

import time

from myProgram.sales.constants import (
    WAIT_NO_RESPONSE,
    DNC_TIMEOUT,
    DYC_TIMEOUT,
    AUTO_CHECKOUT_NOTICE,
    SERVICE_PHONE,
    UNCLEAR_MAX,
    L2_ENTRY_PROMPT,
    L2_REJECT_THANKS,
    L2_TIMEOUT_TO_HAWK_VOICE,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
    L2_UNCLEAR_REJECT_VOICE,
    L3_ENTRY_PROMPT,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L3_UNCLEAR_FINAL_PROMPT,
    L3_CHECKOUT_CONFIRM_TEMPLATE,
    L3_CHECKOUT_REJECT_CLEAR_NOTICE,
    L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE,
    L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE,
    L3_C2_WARNING_TEMPLATE,
    CHECKOUT_CONFIRM_TIMEOUT,
    CHECKOUT_CONFIRM_UNCLEAR_MAX,
    PRODUCTS,
    KEYWORDS_CONFIRM_YES,
    KEYWORDS_CONFIRM_NO,
    KEYWORDS_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_CONFIRM_NO_STRICT_SHORT,
)
from myProgram.sales.nlu import classify_intent, parse_products, _contains_any, _equals_strict_short
from myProgram.sales import cart as cart_module
from myProgram.sales.states._product_helpers import resolve_and_add_products


def run_dialog(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int = 0,
    opencv_disable=lambda: None,
) -> tuple:
    """統一對話層主迴圈 — cart 狀態驅動。

    Args:
        speak: callback(text: str) — 語音播放
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        cart: 購物車 dict（caller 傳入；本層做 in-place 修改 + 視情況 clear）
        think_count: 想一下次數（caller 持有，預設 0）
        opencv_disable: callback() — 關閉 OpenCV 偵測。dialog 進入後不再需要偵測
            （顧客已在面前對話），預設 no-op 給單元測試方便；production wire-up
            必須傳真實 callback（2026-05-25 OpenCV 作用域規格修訂）。

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L4", "L1_via_subroutine_a"}
        next_think_count: 退出時 reset 0
    """
    # 進入 dialog → OpenCV 已用完任務（觸發進 dialog 後不再偵測），明示關閉
    opencv_disable()

    # Entry prompt 按 cart 狀態決定
    speak(L2_ENTRY_PROMPT if cart_module.is_empty(cart) else L3_ENTRY_PROMPT)

    return _dialog_main_loop(
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _dialog_exit_a(speak, cart) -> tuple:
    """鏈路 A 拒絕退出：cart 空 = L2-A（無清 cart）；cart 非空 = L3-A（清 cart）。"""
    if cart_module.is_empty(cart):
        speak(L2_REJECT_THANKS)
    else:
        speak(L3_REJECT_THANKS)
        cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0)


def _dialog_think_silence_l2(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | None:
    """L2 B-3 想一下沉默期（think_count < 3）：等 6s，有回應重 dispatch；無回應 → 重問。"""
    inner = read_customer_input(timeout=WAIT_NO_RESPONSE)
    if inner is None:
        speak(L2_B3_REASK)
        return None
    return _dialog_dispatch_inner_l2(
        response=inner,
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _dialog_think_silence_l3(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | int | None:
    """L3 B-4 想一下沉默期（think_count < 3）：等 6s，有回應重 dispatch；無回應 → 重問。"""
    inner = read_customer_input(timeout=WAIT_NO_RESPONSE)
    if inner is None:
        speak(L3_REASK)
        return think_count
    return _dialog_dispatch_inner_l3(
        response=inner,
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _dialog_dispatch_inner_l2(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | None:
    """L2 B-3 沉默期內顧客有回應 → 重跑 L2 mode 判定（cart 仍空假設）。

    本函式只在 L2 mode（cart 空）的 B-3 沉默期內被呼叫。若顧客回應加了商品，
    cart 會在 resolve_and_add_products 內變非空，但此 helper 不需要切 mode —
    回到主迴圈下一輪自動 re-evaluate cart 狀態。
    """
    intent = classify_intent(response, "l2")
    if intent == "拒絕":
        return _dialog_exit_a(speak, cart)
    if intent == "想一下":
        # 沉默期內又說想一下 → 遞增 think_count + 再走 B-3
        think_count += 1
        if think_count >= 3:
            speak(L2_B3_THIRD_REJECT)
            return _dialog_exit_a(speak, cart)
        return _dialog_think_silence_l2(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )
    if intent == "結帳":
        # L2 結帳當 B-1 unclear → speak clarify 回主等待
        speak(L2_B1_CLARIFY)
        return None
    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        return None
    products = parse_products(response)
    if products:
        added = resolve_and_add_products(
            products=products,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="l2",
        )
        if added:
            # cart 從空 → 非空：補播 L3_ENTRY_PROMPT 銜接到 L3 模式
            # （與主迴圈 transition 行為一致，見規格書 L2.md 鏈路 C「進 L3」）
            speak(L2_C_ADDED)
            speak(L3_ENTRY_PROMPT)
            return None
        speak(L2_B3_REASK)
        return None
    speak(L2_B1_CLARIFY)
    return None


def _dialog_dispatch_inner_l3(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple | int | None:
    """L3 B-4 沉默期 / C-2 第二段內顧客有回應 → 重跑 L3 mode 判定。

    Returns:
        tuple → final decision
        int → think_count 更新值（caller 回主等待）
        None → 已 speak 完，回主等待
    """
    intent = classify_intent(response, "normal")
    if intent == "拒絕":
        return _dialog_exit_a(speak, cart)
    if intent == "想一下":
        think_count += 1
        if think_count >= 3:
            return _dialog_c2_second_stage(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
            )
        return _dialog_think_silence_l3(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
        )
    if intent == "結帳":
        # L3 結帳 → C-1 confirm
        result = _dialog_checkout_confirm(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
        )
        if result == "yes":
            speak(L3_C1_CHECKOUT_GO)
            return ("L4", 0)
        _handle_checkout_confirm_result(result, cart, speak)
        return None
    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        return None
    products = parse_products(response)
    if products:
        resolve_and_add_products(
            products=products,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="normal",
        )
        speak(L3_REASK)
        return None
    speak(L3_B1_CLARIFY)
    return None


def _dialog_c2_second_stage(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple:
    """L3 C-2 第二段：嚴格 yes/no 子狀態（2026-05-26 重構）。

    設計：
    - speak C-2 警告 + 「請說『是』/『否』」提示
    - 啟動 wall-clock 倒數 deadline = now + AUTO_CHECKOUT_NOTICE（12s）
    - 期間 read_customer_input，**亂答忽略不重置計時** — remaining 不斷縮短
    - 只認：CONFIRM_YES / "1" → 進 checkout_confirm；CONFIRM_NO / "2" → 取消清 cart
    - 其他（商品 / 想一下 / 客服 / 亂講）→ 視為 gibberish，silently 消耗 input，繼續倒數
    - deadline 內無有效回應 / read 返回 None → 自動進 L4 結帳

    為何嚴格：規格書 yes/no prompt 避免 NLU 在 L3 normal mode 把「不要」誤分為「結帳」
    再進 checkout confirm 的多步繞路；同時避免亂答觸發 B-1 reask 子流程的另一個 timer。
    """
    speak(L3_C2_WARNING_TEMPLATE.format(seconds=AUTO_CHECKOUT_NOTICE))

    deadline = time.monotonic() + AUTO_CHECKOUT_NOTICE
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # 倒數歸零（亂答耗盡 budget）→ 自動進 L4
            return ("L4", 0)

        response = read_customer_input(timeout=remaining)
        if response is None:
            # read 直接 timeout（顧客全程沒回應）→ 自動進 L4
            return ("L4", 0)

        # NO 先檢查 — 防止 L3 normal NLU 把「不要」誤分為「結帳」造成繞路
        # 使用 substring + strict-short 雙路：
        #   substring 命中長詞（如「不正確」）；strict-short 命中短詞（如「no/nope」）
        if (
            response == "2"
            or _contains_any(response, KEYWORDS_CONFIRM_NO)
            or _equals_strict_short(response, KEYWORDS_CONFIRM_NO_STRICT_SHORT)
        ):
            cart_module.clear_cart(cart)
            speak(L3_CHECKOUT_REJECT_CLEAR_NOTICE)
            return _dialog_continue_after_c2_inner(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
            )

        # YES 檢查：明確肯定詞（substring + strict-short 雙路）
        # 移除 classify_intent==結帳 條件：lenient 模式會把「no/nope/沒了」誤命中 YES
        # 顧客若「沒了/夠了」想結帳，C-2 timeout 後自然進 L4，仍是正確終點
        is_yes = (
            response == "1"
            or _contains_any(response, KEYWORDS_CONFIRM_YES)
            or _equals_strict_short(response, KEYWORDS_CONFIRM_YES_STRICT_SHORT)
        )
        if is_yes:
            # C-2 是「最後機會」嚴格 yes/no — 顧客主動說 YES 不應再被罰 12s confirm。
            # _dialog_checkout_confirm 由 L3 主對話的「結帳」意圖路徑保留（仍需商品明細確認）。
            # （2026-05-26 P3.A：移除 24s 雙漏斗 — 主動回應比 timeout 還慢的反直覺路徑）
            return ("L4", 0)

        # 其他（商品 / 想一下 / 客服 / 亂講）— 嚴格 yes/no 設計下視為 gibberish，
        # silently 消耗、不重置 deadline，下一輪 read 用 remaining 縮短的 timeout 繼續等
        continue


def _dialog_main_loop(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple:
    """dialog 主迴圈 core — 由 run_dialog 與 _dialog_continue_after_c2_inner 共用。

    進入前的準備（opencv_disable / entry prompt speak）由 caller 負責；
    本函式直接進主等待迴圈（unclear_count 從 0 起算）。

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L4", "L1_via_subroutine_a"}
    """
    unclear_count = 0

    while True:
        cart_empty = cart_module.is_empty(cart)

        # DnC（cart 空）/ DyC（cart 非空）皆給較長 timeout — 顧客可能還在挑商品 / 考慮加單
        timeout = DNC_TIMEOUT if cart_empty else DYC_TIMEOUT
        response = read_customer_input(timeout=timeout)

        # === Timeout 分流（cart 狀態決定）===
        if response is None:
            if cart_empty:
                # L2 模式：timeout 不算「拒絕」而是「無回應」→ 中性提示後回 L1 叫賣
                # （speak L2_REJECT_THANKS=「謝謝光臨」會誤導旁人；保留給明確拒絕意圖用）
                speak(L2_TIMEOUT_TO_HAWK_VOICE)
                return ("L1_via_subroutine_a", 0)
            # L3 模式：6s timeout → C-2 兩段自動結帳
            return _dialog_c2_second_stage(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
            )

        # === 判定優先序（cart 狀態決定 NLU mode + 行為）===
        nlu_mode = "l2" if cart_empty else "normal"
        intent = classify_intent(response, nlu_mode)

        # 拒絕意圖 → 鏈路 A（自動依 cart 狀態決定是否清 cart）
        if intent == "拒絕":
            return _dialog_exit_a(speak, cart)

        # 想一下意圖 → B-3/B-4（行為依 cart 狀態）
        if intent == "想一下":
            unclear_count = 0
            think_count += 1
            if cart_empty:
                # L2 B-3：第 3 次 → 鏈路 A
                if think_count >= 3:
                    speak(L2_B3_THIRD_REJECT)
                    return _dialog_exit_a(speak, cart)
                result = _dialog_think_silence_l2(
                    speak=speak,
                    print_terminal=print_terminal,
                    read_customer_input=read_customer_input,
                    cart=cart,
                    think_count=think_count,
                )
                if isinstance(result, tuple):
                    return result
                continue
            # L3 B-4：第 3 次 → C-2 第二段
            if think_count >= 3:
                return _dialog_c2_second_stage(
                    speak=speak,
                    print_terminal=print_terminal,
                    read_customer_input=read_customer_input,
                    cart=cart,
                    think_count=think_count,
                )
            result = _dialog_think_silence_l3(
                speak=speak,
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

        # 結帳意圖 → cart 空時視為 B-1 unclear；cart 非空時走 C-1 confirm
        if intent == "結帳":
            if cart_empty:
                # L2 模式：結帳意圖無意義 → 當 B-1 unclear 處理
                unclear_count += 1
                if unclear_count >= UNCLEAR_MAX:
                    speak(L2_UNCLEAR_REJECT_VOICE)
                    return _dialog_exit_a(speak, cart)
                speak(L2_B1_CLARIFY)
                continue
            # L3 模式：C-1 結帳前 confirm
            unclear_count = 0
            result = _dialog_checkout_confirm(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
            )
            if result == "yes":
                speak(L3_C1_CHECKOUT_GO)
                return ("L4", 0)
            # 否認 / timeout → 清空 cart + 對應通知；下一輪 cart 空 → l2 mode → DnC
            _handle_checkout_confirm_result(result, cart, speak)
            continue

        # 客服 → B-2
        if intent == "客服":
            unclear_count = 0
            print_terminal(SERVICE_PHONE)
            continue

        # 商品 → C / B-3（多商品 parser + 各自缺數量追問）
        products = parse_products(response)
        if products:
            unclear_count = 0
            was_empty = cart_empty
            added = resolve_and_add_products(
                products=products,
                cart=cart,
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                classify_intent_mode=nlu_mode,
            )
            if added:
                # cart 從空 → 非空：speak L2_C_ADDED + L3_ENTRY_PROMPT
                #   （規格書 L2.md 鏈路 C「進 L3」+ L3.md 進入時動作；
                #    漏播 L3_ENTRY_PROMPT 會讓顧客以為對話結束，6s timeout 直接觸發 C-2 自動結帳）
                # cart 已非空：speak L3_REASK（額外加單後重問）
                if was_empty:
                    speak(L2_C_ADDED)
                    speak(L3_ENTRY_PROMPT)
                else:
                    speak(L3_REASK)
                continue
            # 全部商品在追問內取消 → re-prompt 依當前 cart 狀態
            speak(L2_B3_REASK if cart_empty else L3_REASK)
            continue

        # 都沒命中 → B-1（unclear_count++）
        unclear_count += 1
        if unclear_count >= UNCLEAR_MAX:
            if cart_empty:
                # L2: 直接走 A
                speak(L2_UNCLEAR_REJECT_VOICE)
                return _dialog_exit_a(speak, cart)
            # L3: 進最終確認子狀態（有 cart 要保護）
            final = _dialog_unclear_final_confirmation(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
            )
            if final is not None:
                return final
            # 顧客選繼續 → reset 所有 counter + 重播 L3 entry + 回主等待
            # think_count 也歸零：unclear final「繼續」= 重啟對話，不只清 unclear；
            # 若只 reset unclear 而保留 think_count，顧客返回後多想一次就可能誤觸 C-2
            # （2026-05-26 P3.C 加：修 think_count 跨 C-2/continue 累積 bug）
            unclear_count = 0
            think_count = 0
            speak(L3_ENTRY_PROMPT)
            continue
        speak(L2_B1_CLARIFY if cart_empty else L3_B1_CLARIFY)


def _dialog_continue_after_c2_inner(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
) -> tuple:
    """C-2 NO / unclear-final「繼續」後重入 dialog — 跳過 entry prompt + opencv_disable。

    跟 run_dialog 主迴圈邏輯完全一致；差別：
      - 不呼叫 opencv_disable()（C-2 之前已 disable）
      - 不 speak entry prompt（避免重複播放）
    直接委派給 _dialog_main_loop。
    """
    return _dialog_main_loop(
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
    )


def _dialog_checkout_confirm(
    speak,
    print_terminal,
    read_customer_input,
    cart,
) -> bool:
    """L3 C-1 結帳前 confirm 子狀態（每次重 prompt 重置 timeout + unclear 上限）。

    使用專用常數 CHECKOUT_CONFIRM_TIMEOUT (12s) / CHECKOUT_CONFIRM_UNCLEAR_MAX (5) —
    比通用 6s / 3 次寬鬆，因「結帳前確認金額」這步驟顧客可能正在數錢 / 看商品。

    每次 read 都給 full timeout 秒，避免 wall-clock 倒數造成「重 prompt 後顧客來不及答
    就被當 timeout」+「終端 timeout 顯示 5.999... 小數」兩個 UX bug。

    **必須明確答覆才確認進 L4**（2026-05-26 修：保護顧客錢包）：
    - timeout（沒回應）→ return "timeout"；caller 用 timeout 專屬通知（「由於您沒回應...」）
    - 連續 unclear 達上限 → return "no_unclear_exhausted"；caller 用亂答專屬通知
    - 明確「不對」/「2」/「不要」等 → return "no_explicit"；caller 用明確拒絕通知
    - 只有「1 / 對 / 是」等明確肯定詞才 return "yes" 進 L4

    Returns（string sentinel，2026-05-26 P3.B 改：取代舊 True/False/None 三態）：
        "yes" — 顧客明確確認（終端 1 / CONFIRM_YES 命中）
        "no_explicit" — 顧客明確否認（終端 2 / CONFIRM_NO 命中）
        "no_unclear_exhausted" — 顧客亂答 CHECKOUT_CONFIRM_UNCLEAR_MAX 次達上限
        "timeout" — 顧客 CHECKOUT_CONFIRM_TIMEOUT 秒無回應
    """
    summary = _build_order_summary(cart)
    prompt = L3_CHECKOUT_CONFIRM_TEMPLATE.format(summary=summary)
    speak(prompt)
    unclear_count = 0

    while True:
        response = read_customer_input(timeout=CHECKOUT_CONFIRM_TIMEOUT)
        if response is None:
            return "timeout"
        if response == "1":
            return "yes"
        if response == "2":
            return "no_explicit"
        if _contains_any(response, KEYWORDS_CONFIRM_NO) or _equals_strict_short(response, KEYWORDS_CONFIRM_NO_STRICT_SHORT):
            return "no_explicit"
        if _contains_any(response, KEYWORDS_CONFIRM_YES) or _equals_strict_short(response, KEYWORDS_CONFIRM_YES_STRICT_SHORT):
            return "yes"
        unclear_count += 1
        if unclear_count >= CHECKOUT_CONFIRM_UNCLEAR_MAX:
            return "no_unclear_exhausted"
        speak(prompt)


def _handle_checkout_confirm_result(result: str, cart, speak) -> None:
    """checkout_confirm 非 "yes" 時的清 cart + 通知處理（共用 helper）。

    Args:
        result: _dialog_checkout_confirm 的 string sentinel（"yes" 不應呼叫此 helper）
        cart: 購物車 dict
        speak: 語音 callback

    "no_explicit" → speak L3_CHECKOUT_REJECT_CLEAR_NOTICE（顧客明確說不對）
    "no_unclear_exhausted" → speak L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE（亂答 5 次達上限）
    "timeout" → speak L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE（含「由於您沒回應」前綴）

    （2026-05-26 P3.B 改：string sentinel 四態取代舊 True/False/None 三態，
     區分「明確不對」vs「亂答 5 次」兩種 NO 路徑的顧客體感）
    """
    cart_module.clear_cart(cart)
    if result == "timeout":
        speak(L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE)
    elif result == "no_unclear_exhausted":
        speak(L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE)
    elif result == "no_explicit":
        speak(L3_CHECKOUT_REJECT_CLEAR_NOTICE)
    else:
        raise AssertionError(f"未知 confirm result: {result!r}")


def _dialog_unclear_final_confirmation(
    speak,
    print_terminal,
    read_customer_input,
    cart,
) -> tuple | None:
    """L3 B-1 累積到 UNCLEAR_MAX 後的最終確認子狀態（仿 L4 D；2026-05-26 重構 wall-clock）。

    每次 read 都給 full WAIT_NO_RESPONSE 秒，避免 wall-clock 倒數造成「重 prompt 後
    顧客來不及答就被當 timeout」+「終端 timeout 顯示 5.999... 小數」兩個 UX bug。
    亂答達 UNCLEAR_MAX 次 → 視為取消（同 timeout 行為，防無限重 prompt）。

    Returns tuple = caller 直接 return；None = 顧客選繼續，caller reset unclear 回主等待。
    """
    speak(L3_UNCLEAR_FINAL_PROMPT)
    unclear_count = 0

    while True:
        response = read_customer_input(timeout=WAIT_NO_RESPONSE)
        if response is None:
            return _dialog_exit_a(speak, cart)
        if response == "1":
            return _dialog_exit_a(speak, cart)
        if response == "2":
            return None
        intent = classify_intent(response, "l4_service")
        if intent == "退出交易":
            return _dialog_exit_a(speak, cart)
        if intent == "繼續交易":
            return None
        unclear_count += 1
        if unclear_count >= UNCLEAR_MAX:
            return _dialog_exit_a(speak, cart)
        speak(L3_UNCLEAR_FINAL_PROMPT)


def _build_order_summary(cart) -> str:
    """組「3 瓶冰紅茶、2 張刮刮樂」格式字串（給 checkout confirm 用）。"""
    parts = []
    for product, qty in cart.items():
        unit = PRODUCTS[product]["單位"]
        parts.append(f"{qty} {unit}{product}")
    return "、".join(parts)
