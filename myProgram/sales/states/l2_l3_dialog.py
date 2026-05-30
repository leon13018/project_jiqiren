"""統一對話層（2026-05-25 B 方案重構：合併 L2/L3 為單一 cart-state-driven 函式）。

對應規格書：resources/plans/業務程式邏輯規劃/L2.md + L3.md + L0_共通.md「層狀態判定原則」

核心原則：**state machine 由世界狀態（cart）驅動，非動作歷史驅動**。

cart 狀態決定模式：
    - cart 空 → 「L2 模式」：未加單，問需求；timeout = 鏈路 A 拒絕退；結帳意圖視為 B-1 無法判斷
    - cart 非空 → 「L3 模式」：已有訂單，問加單 / 結帳；timeout = C-2 兩段自動結帳；結帳前 confirm

cart 狀態每輪 main loop 迭代都重新判定 — 未來加「刪除商品」功能時若 cart 變空，
下一輪自然回到 L2 模式詢問需求（不需額外 transition 邏輯）。

callback 集合：speak / print_terminal / read_customer_input / do_action
（do_action 2026-05-27 S3 restore — entry 觸發 ACTION_L2/L3；
 2026-05-27 修：cart empty → non-empty transition 也要觸發 ACTION_L3
 — Pi 實機驗證發現「L2 加單成功進 L3」只有 entry 觸發點不夠，因為 dispatcher
 不重新進入 run_dialog 直接 speak L3_ENTRY_PROMPT；修補：兩處 transition 點補上
 do_action(ACTION_L3) — _dialog_dispatch_inner_l2 added 後 / _dialog_main_loop
 was_empty 分支。L3 內後續加單仍不重跑動作 — 符合「每層只 entry 一次」精神）

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
    C2_DECISION_TIMEOUT,
    SERVICE_PHONE,
    UNCLEAR_MAX,
    L2_ENTRY_PROMPT,
    L2_CANCEL_DECLINED_RESUME,
    L2_REJECT_THANKS,
    L2_TIMEOUT_TO_HAWK_VOICE,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_UNCLEAR_REJECT_VOICE,
    L3_ENTRY_PROMPT,
    L2_TO_L3_TRANSITION,
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
    L3_C2_CONTINUE_ACK,
    L3_CANCEL_DECLINED_RESUME,
    CHECKOUT_CONFIRM_TIMEOUT,
    CHECKOUT_CONFIRM_UNCLEAR_MAX,
    PRODUCTS,
    KEYWORDS_CONFIRM_YES,
    KEYWORDS_CONFIRM_NO,
    KEYWORDS_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_CONFIRM_NO_STRICT_SHORT,
    KEYWORDS_C2_CONTINUE,
    KEYWORDS_C2_CONTINUE_STRICT_SHORT,
    KEYWORDS_C2_CHECKOUT,
    KEYWORDS_C2_CHECKOUT_STRICT_SHORT,
    KEYWORDS_C2_CANCEL,
    KEYWORDS_C2_CANCEL_STRICT_SHORT,
    DIALOG_VAGUE_BUY_REASK,
    CANCEL_DECLINED_NOTICE,
    ACTION_L2,
    ACTION_L3,
    ACTION_L3_CHECKOUT_GO,
)
from myProgram.sales.nlu import classify_intent, contains_any, equals_strict_short
from myProgram.sales.product_parser import parse_products
from myProgram.sales import cart as cart_module
from myProgram.sales.states._l2_l3_qty_followup import (
    resolve_and_add_products,
    format_cancel_prefix,
)
from myProgram.sales.states._cancel_confirm import cancel_confirm, is_cancel_intent


def run_dialog(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int = 0,
    *,
    opencv_disable,
    do_action,
    speak_and_wait=None,
) -> tuple:
    """統一對話層主迴圈 — cart 狀態驅動。

    speak_and_wait（2026-05-30 v2 加）：同步阻塞 speak callback。為 None 時
    fallback 到 speak（向後兼容既有測試）；production wire-up 必須傳真實 callback，
    供 wall-clock budget pattern 子函式用（_dialog_c2_second_stage / cancel_confirm
    從 TTS 播完起算 deadline，不被 synth/play 時間吃掉 budget）。

    Args:
        speak: callback(text: str) — 語音播放
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        cart: 購物車 dict（caller 傳入；本層做 in-place 修改 + 視情況 clear）
        think_count: 想一下次數（caller 持有，預設 0）
        opencv_disable: callback() — 關閉 OpenCV 偵測。dialog 進入後不再需要偵測
            （顧客已在面前對話），預設 no-op 給單元測試方便；production wire-up
            必須傳真實 callback（2026-05-25 OpenCV 作用域規格修訂）。
        do_action: callback(name: str) — 同步阻塞跑廠商動作組（S3 加，2026-05-27；
            同日修：cart empty→non-empty transition 也觸發 ACTION_L3）。
            觸發點：(1) entry — cart 空 → ACTION_L2；cart 非空 → ACTION_L3；
            (2) L2→L3 transition — _dialog_dispatch_inner_l2 / _dialog_main_loop
            內顧客加單使 cart 從空變非空時 → ACTION_L3。
            L3 內後續加單不跑動作（避免每次加單都動，servo 過熱風險）。

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L4", "L1_via_subroutine_a"}
        next_think_count: 退出時 reset 0
    """
    # 進入 dialog → OpenCV 已用完任務（觸發進 dialog 後不再偵測），明示關閉
    opencv_disable()

    # S3：entry 同步動作（cart 空 = L2 進場揮手；cart 非空 = L3 進場另一動作）
    # 先動作再 speak entry prompt：動作做完顧客眼神對齊機器，再聽指引較順
    do_action(ACTION_L2 if cart_module.is_empty(cart) else ACTION_L3)

    # Entry prompt 按 cart 狀態決定
    speak(L2_ENTRY_PROMPT if cart_module.is_empty(cart) else L3_ENTRY_PROMPT)

    return _dialog_main_loop(
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
        do_action=do_action,
        speak_and_wait=speak_and_wait,
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
    do_action,
    speak_and_wait=None,
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
        do_action=do_action,
        speak_and_wait=speak_and_wait,
    )


def _dialog_think_silence_l3(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
    do_action,
    speak_and_wait=None,
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
        do_action=do_action,
        speak_and_wait=speak_and_wait,
    )


def _dialog_dispatch_inner_l2(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
    do_action,
    speak_and_wait=None,
) -> tuple | None:
    """L2 B-3 沉默期內顧客有回應 → 重跑 L2 mode 判定（cart 仍空假設）。

    本函式只在 L2 mode（cart 空）的 B-3 沉默期內被呼叫。若顧客回應加了商品，
    cart 會在 resolve_and_add_products 內變非空，但此 helper 不需要切 mode —
    回到主迴圈下一輪自動 re-evaluate cart 狀態。
    """
    intent = classify_intent(response, "l2")
    if intent == "拒絕":
        # 2026-05-29 cross-L cancel：拒絕意圖 → 先過 cancel_confirm gate
        if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
            return _dialog_exit_a(speak, cart)
        # 顧客 NO「不要取消」→ speak 合成 voice（DECLINED + L2 entry 重啟），
        # 主迴圈進入不重播 entry → 一次 speak cover 兩件事，顧客不失去上下文
        # （2026-05-30 改：從 CANCEL_DECLINED_NOTICE 替換為合成版）
        speak(L2_CANCEL_DECLINED_RESUME)
        return None
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
            do_action=do_action,
            speak_and_wait=speak_and_wait,
        )
    if intent == "結帳":
        # L2 結帳當 B-1 unclear → speak clarify 回主等待
        speak(L2_B1_CLARIFY)
        return None
    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        # 2026-05-27 加：印完電話後重 speak L2 prompt，否則顧客失去對話上下文
        speak(L2_ENTRY_PROMPT)
        return None
    # 2026-05-26 加：L2 沉默期內「想買無商品」溫和引導（不 ++unclear / 不 ++think_count）
    if intent == "想買無商品":
        speak(DIALOG_VAGUE_BUY_REASK)
        return None
    products = parse_products(response)
    if products:
        added, cancel_notices = resolve_and_add_products(
            products=products,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="l2",
            speak_and_wait=speak_and_wait,
        )
        if added:
            # cart 從空 → 非空：speak L2_TO_L3_TRANSITION（合成 voice，原 L2_C_ADDED +
            # L3_ENTRY_PROMPT 兩條 speak 合併為一句連貫播報，S4 非阻塞 worker 兩條間
            # 「synth + ALSA drain 0.3s」停頓問題解除；見規格書 L2.md 鏈路 C「進 L3」）
            # B11：沉默期內加單同樣是 L2→L3 切換點，think_count 交由主迴圈 caller 處理
            # （_dialog_dispatch_inner_l2 不直接改 think_count；回 None 後主迴圈
            #  下一輪 was_empty 已為 False，think_count reset 在主迴圈 was_empty 分支已處理）
            # S3 同步動作（2026-05-27 fix）：L2→L3 transition 觸發 ACTION_L3，跟主迴圈一致
            do_action(ACTION_L3)
            # 2026-05-30 合成 speak：部分 skip 的 cancel notice 拼接到 transition 前
            speak(_prepend_cancel_notices(cancel_notices, L2_TO_L3_TRANSITION))
            return None
        # 全 skip → 拼接 cancel notices 與 L2_B3_REASK 為單一 speak
        speak(_prepend_cancel_notices(cancel_notices, L2_B3_REASK))
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
    do_action,
    speak_and_wait=None,
) -> tuple | int | None:
    """L3 B-4 沉默期 / C-2 第二段內顧客有回應 → 重跑 L3 mode 判定。

    Returns:
        tuple → final decision
        int → think_count 更新值（caller 回主等待）
        None → 已 speak 完，回主等待
    """
    intent = classify_intent(response, "normal")
    if intent == "拒絕":
        # 2026-05-29 cross-L cancel：拒絕意圖 → 先過 cancel_confirm gate
        if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
            return _dialog_exit_a(speak, cart)
        # 顧客 NO「不要取消」→ speak 合成 voice（DECLINED + L3 entry 重啟），
        # 主迴圈進入不重播 entry → 一次 speak cover 兩件事，顧客不失去上下文
        # （2026-05-30 改：從 CANCEL_DECLINED_NOTICE 替換為合成版）
        speak(L3_CANCEL_DECLINED_RESUME)
        return None
    if intent == "想一下":
        think_count += 1
        # C13 (2026-05-26 Wave 7a)：L3 模式 think_count 觸發 C-2 條件 3 → 4
        # 顧客在 L3 想了 3 次就直接結帳偏粗暴；第 4 次才觸發更貼近實際 UX
        # （L2 退出條件保留 3 — 那是 cart 空時的明確拒絕路徑，不是 C-2 觸發）
        if think_count >= 4:
            return _dialog_c2_second_stage(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                speak_and_wait=speak_and_wait,
            )
        return _dialog_think_silence_l3(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=think_count,
            do_action=do_action,
            speak_and_wait=speak_and_wait,
        )
    if intent == "結帳":
        # L3 結帳 → C-1 confirm
        result = _dialog_checkout_confirm(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            speak_and_wait=speak_and_wait,
        )
        if result == "yes":
            speak(L3_C1_CHECKOUT_GO)
            # S3 L3→L4 transition 動作（2026-05-28 加）：指向螢幕引導顧客掃碼視線
            # 先 speak 再動作 — 跟 L4_PAY / L5_FAREWELL 一致 pattern（聽到語音 → 注意力對齊 → 視線跟指向）
            do_action(ACTION_L3_CHECKOUT_GO)
            return ("L4", 0)
        if result == "cancel_to_l1":
            # 2026-05-30 加：cancel_confirm YES → 直退 L1（不回 main loop）
            return _dialog_exit_a(speak, cart)
        _handle_checkout_confirm_result(result, cart, speak)
        return None
    if intent == "客服":
        print_terminal(SERVICE_PHONE)
        # 2026-05-27 加：印完電話後重 speak L3 reask，否則顧客失去對話上下文
        speak(L3_REASK)
        return None
    # 2026-05-26 加：L3 沉默期內「想買無商品」溫和引導（不 ++unclear / 不 ++think_count）
    if intent == "想買無商品":
        speak(DIALOG_VAGUE_BUY_REASK)
        return None
    products = parse_products(response)
    if products:
        _added, cancel_notices = resolve_and_add_products(
            products=products,
            cart=cart,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode="normal",
            speak_and_wait=speak_and_wait,
        )
        # 2026-05-30 合成 speak：cancel notices 拼接到 L3_REASK 前
        speak(_prepend_cancel_notices(cancel_notices, L3_REASK))
        return None
    speak(L3_B1_CLARIFY)
    return None


def _dialog_c2_second_stage(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
    do_action,
    speak_and_wait=None,
) -> tuple:
    """L3 C-2 第二段：三選一子狀態（2026-05-28 重構：二元 yes/no → 繼續/結帳/取消）。

    設計：
    - speak C-2 三選一警告（L3_C2_WARNING_TEMPLATE）+ wall-clock budget C2_DECISION_TIMEOUT (6s)
    - 期間 read_customer_input，**亂答忽略不重置計時** — remaining 不斷縮短
    - Three-way dispatcher（CANCEL 優先：顧客錢包 conservative）：
        - CANCEL（KEYWORDS_C2_CANCEL + strict-short ["取消"]）→ _dialog_exit_a：
          清 cart + speak L3_REJECT_THANKS + return ("L1_via_subroutine_a", 0)
        - CONTINUE（KEYWORDS_C2_CONTINUE + strict-short ["繼續"]）→ speak L3_C2_CONTINUE_ACK + _dialog_main_loop：
          不清 cart，重入 dialog 主迴圈讓顧客繼續加單（ack 維持對話上下文，
          2026-05-30 加：main loop 不重播 entry prompt，無 ack 顧客失去語音回饋 → 沉默 → 又被 DYC_TIMEOUT 抓回 C-2）
        - CHECKOUT（KEYWORDS_C2_CHECKOUT + strict-short ["結"]）→ _c2_checkout_via_confirm：
          經 _dialog_checkout_confirm 確認明細 → "yes" 進 L4；非 yes 清 cart + 重入
    - 亂答（不在三組 keyword）→ silent 倒數（第一次提示「請說『繼續』、『結賬』或『取消』」，後續 silent）
    - 倒數歸零 / response is None（silent customer）→ _c2_checkout_via_confirm：進 confirm 子狀態
      （2026-05-29 反轉：silent timeout 不再直接 L4，與 CHECKOUT keyword path 合流經 confirm）

    解 Pi demo 2026-05-28 UX bug：舊版「結帳（是）/ 想想（不要）」二元，顧客「不要」歧義
    （「不要結帳」vs「不要整單」）被當成「拒絕整單」清 cart。新三選一語意明確、無歧義。

    Timeout 行為（2026-05-29 反轉）：
        silent / 倒數歸零 → 經 _c2_checkout_via_confirm（confirm yes 進 L4；非 yes 清 cart + 重入 dialog）
        CHECKOUT keyword → 經 _c2_checkout_via_confirm（兩條 path 完全合流）

    字面 promise 寬鬆解讀：新文案「{seconds} 秒後自動結賬」中「自動結賬」可解為
    「自動啟動結賬流程」（含 confirm 子狀態），不嚴格等於「跳過所有確認直接扣款」。
    """
    # 2026-05-30 v2：speak_and_wait warning 後算 deadline — 顧客拿到完整
    # C2_DECISION_TIMEOUT 秒 budget，而非「budget 減 warning 播放時間」
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    _speak_blocking(L3_C2_WARNING_TEMPLATE.format(seconds=C2_DECISION_TIMEOUT))

    deadline = time.monotonic() + C2_DECISION_TIMEOUT
    prompted_once = False  # 第一次亂答才 speak 提示，後續 silent（不重置 deadline）
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # 倒數歸零（亂答耗盡 budget）→ 進 confirm（與 CHECKOUT keyword path 合流）
            return _c2_checkout_via_confirm(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                do_action=do_action,
                speak_and_wait=speak_and_wait,
            )

        response = read_customer_input(timeout=remaining)
        if response is None:
            # read 直接 timeout（顧客全程沒回應）→ 進 confirm（與 CHECKOUT keyword path 合流）
            return _c2_checkout_via_confirm(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                do_action=do_action,
                speak_and_wait=speak_and_wait,
            )

        # 三選一 dispatcher（2026-05-28 重構：CANCEL 優先，顧客錢包 conservative）
        # CANCEL：清 cart + 退 L1（reuse _dialog_exit_a：speak L3_REJECT_THANKS + clear cart）
        if (
            contains_any(response, KEYWORDS_C2_CANCEL)
            or equals_strict_short(response, KEYWORDS_C2_CANCEL_STRICT_SHORT)
        ):
            return _dialog_exit_a(speak, cart)

        # CONTINUE：speak ack 後不清 cart，重入 dialog 主迴圈（顧客繼續加單）
        # 2026-05-30 加 ack speak：main loop 不重播 entry prompt，若直接 return
        # 顧客失去對話上下文 → 沉默 → 又被 DYC_TIMEOUT 抓回 C-2（Pi demo 實測 bug）
        if (
            contains_any(response, KEYWORDS_C2_CONTINUE)
            or equals_strict_short(response, KEYWORDS_C2_CONTINUE_STRICT_SHORT)
        ):
            speak(L3_C2_CONTINUE_ACK)
            return _dialog_main_loop(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                do_action=do_action,
                speak_and_wait=speak_and_wait,
            )

        # CHECKOUT：顧客主動講結帳 → 經 _dialog_checkout_confirm 確認明細
        # （2026-05-29 反轉：timeout path 也合流到此函數，兩條 path 完全一致）
        if (
            contains_any(response, KEYWORDS_C2_CHECKOUT)
            or equals_strict_short(response, KEYWORDS_C2_CHECKOUT_STRICT_SHORT)
        ):
            return _c2_checkout_via_confirm(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                do_action=do_action,
                speak_and_wait=speak_and_wait,
            )

        # 其他（不在三組 keyword 內）— 視為亂答
        # 第一次亂答 speak 一次提示，後續 silent；不重置 deadline
        if not prompted_once:
            speak("請說『繼續』、『結賬』或『取消』")
            prompted_once = True
        continue


def _c2_checkout_via_confirm(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
    do_action,
    speak_and_wait=None,
) -> tuple:
    """C-2 結賬 path（合流：CHECKOUT keyword + silent timeout 都走這裡）。

    經 _dialog_checkout_confirm 確認明細 → "yes" 進 L4；非 yes 清 cart + 重入 dialog 主迴圈。

    對齊既有 L3 C-1 結帳 path（_dialog_dispatch_inner_l3 / _dialog_main_loop 結帳分支）
    — 共用 confirm 子狀態。

    2026-05-29 反轉：silent timeout 不再走 _c2_direct_checkout 直接 L4,
    合流到此函數經 confirm（與 CHECKOUT keyword path 完全一致）。新文案
    「{seconds} 秒後自動結賬」字面 promise 寬鬆解讀為「自動啟動結賬流程」
    （含 confirm 子狀態保護顧客錢包）。
    """
    result = _dialog_checkout_confirm(
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        speak_and_wait=speak_and_wait,
    )
    if result == "yes":
        speak(L3_C1_CHECKOUT_GO)
        do_action(ACTION_L3_CHECKOUT_GO)
        return ("L4", 0)
    if result == "cancel_to_l1":
        # 2026-05-30 加：cancel_confirm YES → 直退 L1（不重入 main loop）
        return _dialog_exit_a(speak, cart)
    # 非 yes → 清 cart + speak 通知 + 重入 dialog 主迴圈
    _handle_checkout_confirm_result(result, cart, speak)
    return _dialog_main_loop(
        speak=speak,
        print_terminal=print_terminal,
        read_customer_input=read_customer_input,
        cart=cart,
        think_count=think_count,
        do_action=do_action,
        speak_and_wait=speak_and_wait,
    )


def _dialog_main_loop(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    think_count: int,
    do_action,
    speak_and_wait=None,
) -> tuple:
    """dialog 主迴圈 core — 由 run_dialog 與 _dialog_continue_after_c2_inner 共用。

    進入前的準備（opencv_disable / entry prompt speak）由 caller 負責；
    本函式直接進主等待迴圈（unclear_count 從 0 起算）。

    Returns:
        (next_state, next_think_count)
        next_state ∈ {"L4", "L1_via_subroutine_a"}

    無 wall-clock budget 是設計選擇（INTENTIONAL，2026-05-26 review B22）：
        - 跟 L4 (60s) 不同，dialog 沒有整體 wall-clock 上限
        - 理由：顧客主動加單 / 想一下 / 修改 cart 沒道理限時 — 對話越長代表
          顧客投入越多，業務上希望成交，限時反而趕走客人
        - 各「不互動」分支（think_count / unclear_count）有獨立計數器保護
          避免無限循環；read_customer_input 也有 WAIT_NO_RESPONSE 單輪 timeout
        - 若未來 demo 場景需要「整體 5 分鐘上限」可加 DIALOG_TOTAL_BUDGET，
          但目前無需求
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
                do_action=do_action,
                speak_and_wait=speak_and_wait,
            )

        # === 判定優先序（cart 狀態決定 NLU mode + 行為）===
        nlu_mode = "l2" if cart_empty else "normal"
        intent = classify_intent(response, nlu_mode)

        # 拒絕意圖 → 先過 cancel_confirm gate（2026-05-29 cross-L cancel）
        # True → 鏈路 A（依 cart 狀態決定是否清 cart）；False → speak 合成 voice 後 continue 重 prompt
        if intent == "拒絕":
            if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
                return _dialog_exit_a(speak, cart)
            # cancel_confirm NO → speak 合成 voice（DECLINED + 對應 mode entry 重啟）
            # cart_empty 已在迴圈頂端算過；mode 一致：cart 空 L2 / cart 非空 L3
            # （2026-05-30 改：從 CANCEL_DECLINED_NOTICE 替換為 mode-aware 合成版）
            speak(L2_CANCEL_DECLINED_RESUME if cart_empty else L3_CANCEL_DECLINED_RESUME)
            continue

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
                    do_action=do_action,
                    speak_and_wait=speak_and_wait,
                )
                if isinstance(result, tuple):
                    return result
                # B11：沉默期內顧客加單使 cart 從空變非空（L2→L3 切換）→ reset think_count
                if not cart_module.is_empty(cart):
                    think_count = 0
                continue
            # L3 B-4：第 4 次 → C-2 第二段
            # C13 (2026-05-26 Wave 7a)：3 → 4，讓顧客多一次想一下空間
            if think_count >= 4:
                return _dialog_c2_second_stage(
                    speak=speak,
                    print_terminal=print_terminal,
                    read_customer_input=read_customer_input,
                    cart=cart,
                    think_count=think_count,
                    do_action=do_action,
                    speak_and_wait=speak_and_wait,
                )
            result = _dialog_think_silence_l3(
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                think_count=think_count,
                do_action=do_action,
                speak_and_wait=speak_and_wait,
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
                speak_and_wait=speak_and_wait,
            )
            if result == "yes":
                speak(L3_C1_CHECKOUT_GO)
                # S3 L3→L4 transition 動作（2026-05-28 加）：指向螢幕引導顧客掃碼視線
                do_action(ACTION_L3_CHECKOUT_GO)
                return ("L4", 0)
            if result == "cancel_to_l1":
                # 2026-05-30 加：cancel_confirm YES → 直退 L1
                # （_dialog_exit_a 處理 clear cart + speak L3_REJECT_THANKS）
                return _dialog_exit_a(speak, cart)
            # 否認 / timeout / 亂答上限 → 清空 cart + 對應通知；下一輪 cart 空 → l2 mode → DnC
            _handle_checkout_confirm_result(result, cart, speak)
            continue

        # 客服 → B-2
        if intent == "客服":
            unclear_count = 0
            print_terminal(SERVICE_PHONE)
            # 2026-05-27 加：印完電話後 speak 對應 mode 的 re-entry prompt；
            # 否則 continue → 下一輪 read_customer_input 顧客失去對話上下文
            if cart_empty:
                speak(L2_ENTRY_PROMPT)
            else:
                speak(L3_REASK)
            continue

        # 商品 → C / B-3（多商品 parser + 各自缺數量追問）
        products = parse_products(response)
        if products:
            unclear_count = 0
            was_empty = cart_empty
            added, cancel_notices = resolve_and_add_products(
                products=products,
                cart=cart,
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                classify_intent_mode=nlu_mode,
                speak_and_wait=speak_and_wait,
            )
            if added:
                # cart 從空 → 非空：speak L2_TO_L3_TRANSITION（合成 voice，原 L2_C_ADDED +
                # L3_ENTRY_PROMPT 兩條 speak 合併為一句連貫播報，S4 非阻塞 worker 兩條間
                # 「synth + ALSA drain 0.3s」停頓問題解除；見規格書 L2.md 鏈路 C「進 L3」+ L3.md 進入時動作；
                # 漏播會讓顧客以為對話結束、6s timeout 直接觸發 C-2 自動結帳）
                # cart 已非空：speak L3_REASK（額外加單後重問）
                # 2026-05-30 合成 speak：cancel notices 拼接到 transition / reask 前
                if was_empty:
                    # B11：L2→L3 cart-state 切換點 reset think_count
                    # 各 mode 獨立計數：L2 think_count 不應污染 L3；否則顧客在 L2 想一下兩次
                    # 加單進 L3 後再想一下就誤觸 C-2 自動結帳
                    think_count = 0
                    # S3 同步動作（2026-05-27 fix）：L2→L3 transition 觸發 ACTION_L3
                    # — 修補「只在 run_dialog entry 跑」漏洞（Pi demo 實測 L2 加單後沒跑動作）
                    do_action(ACTION_L3)
                    speak(_prepend_cancel_notices(cancel_notices, L2_TO_L3_TRANSITION))
                else:
                    speak(_prepend_cancel_notices(cancel_notices, L3_REASK))
                continue
            # 全部商品在追問內取消 → re-prompt 依當前 cart 狀態
            # 2026-05-30 合成 speak：cancel notices 拼接到 reask 前
            reask = L2_B3_REASK if cart_empty else L3_REASK
            speak(_prepend_cancel_notices(cancel_notices, reask))
            continue

        # 2026-05-26 加：L2/L3 通用「想買無商品」溫和引導（與 L4「等待安撫」pattern 一致）
        # 不 ++unclear_count、不 ++think_count；主迴圈 continue 等下一輪
        if intent == "想買無商品":
            speak(DIALOG_VAGUE_BUY_REASK)
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
                speak_and_wait=speak_and_wait,
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


def _dialog_checkout_confirm(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    speak_and_wait=None,
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
        "cancel_to_l1" — 顧客在 confirm 內講 cancel intent 且 cancel_confirm YES（2026-05-30 加）；
                         caller 必須走 _dialog_exit_a 直退 L1，不可進 _handle_checkout_confirm_result
                         （此路徑跳過 clear cart 通知 + L2 entry 重啟，由 _dialog_exit_a
                          統一 speak L3_REJECT_THANKS。修 Pi demo 兩輪 YES 才退 L1 bug）
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
        # 2026-05-29 cross-L cancel：confirm 子狀態內偵測 cancel intent → 經 cancel_confirm gate
        # YES → return "cancel_to_l1"（caller 走 _dialog_exit_a 直退 L1）
        # NO → speak DECLINED 後 continue（不計入 unclear_count，這是顧客明確意圖溝通）
        # 2026-05-30 改：YES 從 "no_explicit" 改為新 sentinel "cancel_to_l1"。舊 path
        # 經 _handle_checkout_confirm_result clear cart + speak L3_CHECKOUT_REJECT_CLEAR_NOTICE
        # （含「請告訴我您想買什麼」L2 entry 內容）→ 回 main loop → cart 空 L2 mode →
        # 顧客再拒絕又 cancel_confirm → 兩輪 YES 才退 L1（Pi demo 實機踩過）。
        if is_cancel_intent(response):
            if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
                return "cancel_to_l1"
            speak(CANCEL_DECLINED_NOTICE)
            speak(prompt)
            continue
        if contains_any(response, KEYWORDS_CONFIRM_NO) or equals_strict_short(response, KEYWORDS_CONFIRM_NO_STRICT_SHORT):
            return "no_explicit"
        if contains_any(response, KEYWORDS_CONFIRM_YES) or equals_strict_short(response, KEYWORDS_CONFIRM_YES_STRICT_SHORT):
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
    elif result == "cancel_to_l1":
        # 2026-05-30 加：防呆 assertion。caller 必須在傳入此 helper 前識別
        # "cancel_to_l1" 並走 _dialog_exit_a 直退 L1，不該走到這裡（會誤
        # speak clear-cart 通知 + L2 entry → 兩輪拒絕 bug 重現）。
        raise AssertionError(
            "cancel_to_l1 應由 caller 直接走 _dialog_exit_a，"
            "不該傳入 _handle_checkout_confirm_result（會誤 speak clear-cart 通知）"
        )
    else:
        raise AssertionError(f"未知 confirm result: {result!r}")


def _dialog_unclear_final_confirmation(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    speak_and_wait=None,
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
            # 2026-05-29 cross-L cancel：unclear final 內語音退出 intent → 先過 cancel_confirm gate
            # （終端 "1" / silent timeout / unclear exhausted 仍直接退，不 gate — 那些是介面操作非 cancel intent）
            if cancel_confirm(speak, read_customer_input, speak_and_wait=speak_and_wait):
                return _dialog_exit_a(speak, cart)
            # NO → speak DECLINED + 重 prompt unclear final + continue（不計 unclear_count）
            speak(CANCEL_DECLINED_NOTICE)
            speak(L3_UNCLEAR_FINAL_PROMPT)
            continue
        if intent == "繼續交易":
            return None
        unclear_count += 1
        if unclear_count >= UNCLEAR_MAX:
            return _dialog_exit_a(speak, cart)
        speak(L3_UNCLEAR_FINAL_PROMPT)


def _prepend_cancel_notices(cancel_notices: list[str], reask: str) -> str:
    """把 sub_loop skip 累積的 cancel notice list 與後續 reask text 拼成單一 speak 字串。

    2026-05-30 加：解 Pi demo「先聽到『商品 X 已幫您取消』再隔停頓聽到『請問需要購買
    什麼東西嗎？』」兩段 separate speak 的 UX 不連貫（S4 非阻塞 worker 兩段間 synth +
    ALSA drain 0.3s 停頓明顯）。改成一段合成 voice。

    2026-05-30 更新：prefix 文案邏輯抽到 format_cancel_prefix（N==0/1/>=2 三分支）—
    N>=2 改 count 格式「有N項商品已幫您取消」取代逐項列名，避免多商品 cancel 過冗。

    格式：prefix 與 reask 之間用全形「，」分隔（繁中標點 — 中文語感比半形自然）。

    Returns:
        cancel_notices 空 → 直接返 reask（無拼接，與既有行為一致）
        cancel_notices 長度 1 → 「商品X已幫您取消，{reask}」
        cancel_notices 長度 >=2 → 「有N項商品已幫您取消，{reask}」
    """
    prefix = format_cancel_prefix(cancel_notices)
    if not prefix:
        return reask
    return prefix + "，" + reask


def _build_order_summary(cart) -> str:
    """組「3 瓶冰紅茶、2 張刮刮樂，合計 N 元」格式字串（給 checkout confirm 用）。

    C10：結帳前 confirm 列總金額，讓顧客知道要付多少錢。
    """
    parts = []
    for product, qty in cart.items():
        unit = PRODUCTS[product]["單位"]
        parts.append(f"{qty} {unit}{product}")
    items = "、".join(parts)
    total = cart_module.calc_total(cart)
    return f"{items}，合計 {total} 元"
