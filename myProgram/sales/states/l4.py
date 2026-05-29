"""L4：印金額 + 等掃碼（結帳層）。

對應規格書：resources/plans/業務程式邏輯規劃/L4.md

L 系列最複雜層特性：
    - 客服特殊模式（不自動返回，60s timeout，6 種 trigger）
    - 6 次循環印金額（loop_count 1-6 對應 4 階段語氣）
    - 雙計數器（loop_count + unclear_count）
    - dispatcher 過濾 3 類（想一下 / 結帳 / 商品 → 鏈路 E）
    - unclear_count == 3 自動進客服模式（E → C 串接）
    - return 3-tuple (next_state, next_loop_count, next_unclear_count)
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    WAIT_NO_RESPONSE,
    SERVICE_PHONE,
    L4_MAX_LOOPS,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_QR_MOCK_HINT,
    L4_A_PAY_SUCCESS,
    L4_ACK_GENTLE,
    L4_B_CANCEL_THANKS,
    L4_C_OPTIONS_PROMPT,
    L4_D_FORCED_EXIT,
    L4_D_FINAL_PROMPT,
    L4_E_CLARIFY,
    L4_E_AUTO_SERVICE,
    L4_D_VOICE_NEUTRAL,
    L4_D_VOICE_GENTLE,
    L4_D_VOICE_MODERATE,
    L4_D_VOICE_WARNING,
    L4_SERVICE_TIMEOUT,
    L4_TOTAL_BUDGET,
    UNCLEAR_MAX,
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
    loop_count: int = 0,
    unclear_count: int = 0,
    *,
    opencv_disable,
    do_action,
) -> tuple:
    """L4 主迴圈：結帳層（印金額 + 等掃碼）。

    顧客從 L3 攜帶 cart 進入，等掃碼付款。
    鏈路 A（掃碼）→ L5；
    鏈路 B（拒絕）→ 清空 cart → L1（子例程 A）；
    鏈路 C（客服）→ 客服特殊模式（不自動返回）；
    鏈路 D（6s 無回應）→ loop_count++，4 階段語氣催促；
    鏈路 E（無法判斷）→ unclear_count++，第 3 次自動進 C。

    Args:
        speak: callback(text: str) — 語音播放
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        cart: 購物車 dict（從 L3 帶來）
        loop_count: D 鏈路循環計數（預設 0；客服繼續時 reset 0）
        unclear_count: E 鏈路計數（預設 0；A / B 觸發時 reset 0）

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
            L4 其他鏈路（B 取消 / C 客服 prompt / D 催促 / E unclear）不跑動作。

    Returns:
        (next_state, next_loop_count, next_unclear_count)
        next_state ∈ {"L1_via_subroutine_a", "L5"}

    Wall-clock budget 鏈條（INTENTIONAL，2026-05-26 review B13 文件化）：
        - L4 主迴圈嚴守 L4_TOTAL_BUDGET = 60s 預算（每輪 check remaining）
        - 但 _l4_final_confirmation sub-helper 走自己的 6s × UNCLEAR_MAX (3) = 18s 上限，
          不檢查主迴圈預算（設計如此，給最終確認子狀態獨立時間）
        - 最壞情況：60s 主迴圈到尾 → 進 _l4_final_confirmation → 再 18s → forced exit
        - 即 L4 整體最壞 78s（60 + 18），文件化避免未來誤判為「budget 漏算」bug
        - _l4_service_mode 60s timeout 也獨立於主迴圈（已知 trade-off，見 review B8）
    """
    # 進入 L4 → OpenCV 不需要（顧客已在掃碼），明示關閉（防呆）
    opencv_disable()

    # 進入時動作：計算總額、印明細、speak 總額語音
    total = cart_module.calc_total(cart)
    _l4_print_entry_detail(cart, total, print_terminal)
    speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))

    # 2026-05-26 方案 B：L4 全程 wall-clock 預算（60s）
    # ack 路徑 speak gentle 後 continue 不重設 deadline — 顧客可講禮貌詞但整體上限固定
    deadline = time.monotonic() + L4_TOTAL_BUDGET

    # 主等待迴圈
    while True:
        # 預算檢查：預算耗盡 → 強制 exit（speak forced exit voice + clear cart + return L1）
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _l4_exit_d_forced(speak, cart)

        # 若 loop_count 已達 L4_MAX_LOOPS，此輪 6s timeout 進「最終確認」子狀態（非直接退）
        if loop_count >= L4_MAX_LOOPS:
            response = read_customer_input(timeout=min(WAIT_NO_RESPONSE, remaining))
            if response is None:
                # 2026-05-25 改：第 7 次 6s timeout 不再直接 forced exit，給顧客最後 6s 選 1 / 2
                result = _l4_final_confirmation(
                    speak=speak,
                    print_terminal=print_terminal,
                    read_customer_input=read_customer_input,
                    cart=cart,
                    total=total,
                )
                if result is not None:
                    return result  # 取消 → ("L1_via_subroutine_a", 0, 0)
                # None → 顧客選繼續 → reset counter + QR 刷新 + 重 speak entry + 回主迴圈
                # 2026-05-27 加 re-speak：對齊 L2/L3 dialog 客服 re-speak fix (a2eee27)
                # — 顧客只聽語音不看終端，重印明細無法傳達「現在仍在 L4 等掃碼」context，
                # 必須 speak entry prompt 讓顧客知道下一步動作。
                loop_count = 0
                unclear_count = 0
                _l4_print_entry_detail(cart, total, print_terminal)
                speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
                continue
            # 有回應 → 仍走判定優先序
            result = _l4_dispatch_response(
                response=response,
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                loop_count=loop_count,
                unclear_count=unclear_count,
                do_action=do_action,
            )
            if isinstance(result, tuple):
                return result
            # 等待安撫：重置催促計數（禮貌顧客不被催促），但保留 wall-clock 60s 預算
            if result == "ack":
                # C8：顧客主動 ack → reset loop_count，不重設 deadline
                loop_count = 0
                continue
            # E 類（unclear_count 更新）
            if isinstance(result, int):
                unclear_count = result
                # QR 刷新：E 鏈路顧客無法判斷，重印金額明細模擬 QR code 重新顯示
                _l4_print_entry_detail(cart, total, print_terminal)
            continue

        # 一般等待（timeout 不超過剩餘預算）
        response = read_customer_input(timeout=min(WAIT_NO_RESPONSE, remaining))

        if response is None:
            # 鏈路 D：loop_count++，說催促語音 + QR 刷新（2026-05-25 加：每次循環都重印金額明細）
            loop_count += 1
            _l4_d_speak_loop_voice(loop_count, total, speak)
            _l4_print_entry_detail(cart, total, print_terminal)
            continue

        # 有回應 → 判定優先序
        result = _l4_dispatch_response(
            response=response,
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=loop_count,
            unclear_count=unclear_count,
            do_action=do_action,
        )

        if isinstance(result, tuple):
            return result

        # 等待安撫：重置催促計數（禮貌顧客不被催促），但保留 wall-clock 60s 預算
        if result == "ack":
            # C8：顧客主動 ack → reset loop_count，不重設 deadline
            loop_count = 0
            continue

        # E 類回傳 int（更新後的 unclear_count）
        if isinstance(result, int):
            unclear_count = result
            # QR 刷新：E 鏈路顧客無法判斷，重印金額明細模擬 QR code 重新顯示
            _l4_print_entry_detail(cart, total, print_terminal)
            continue

        # result is None → C 繼續（loop_count / unclear_count 已在 _l4_service_mode 內 reset）
        # 但 _l4_dispatch_response 會在 C 繼續時回傳 tuple 或 None
        # 這裡 None 代表繼續（客服繼續後 reset 兩個計數器）
        loop_count = 0
        unclear_count = 0
        # QR 刷新：客服繼續後重印金額明細，幫助顧客回到 L4 主場景對齊狀態
        # 2026-05-27 加 re-speak：對齊 L2/L3 dialog 客服 re-speak fix (a2eee27)
        # — 顧客只聽語音不看終端，重印明細無法傳達「現在仍在 L4 等掃碼」context，
        # 必須 speak entry prompt 讓顧客知道下一步動作。
        _l4_print_entry_detail(cart, total, print_terminal)
        speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))


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


def _l4_d_speak_loop_voice(loop_count: int, total: int, speak) -> None:
    """L4 鏈路 D 4 階段催促語音 dispatcher。

    loop_count 1 → 中性；2 → 柔提醒；3/4 → 中度催促；>= 5 → 明確警告（含第 7 次及以上）。
    """
    if loop_count == 1:
        speak(L4_D_VOICE_NEUTRAL.format(total=total))
    elif loop_count == 2:
        speak(L4_D_VOICE_GENTLE.format(total=total))
    elif loop_count in (3, 4):
        speak(L4_D_VOICE_MODERATE.format(total=total))
    elif loop_count >= 5:
        speak(L4_D_VOICE_WARNING.format(total=total))


def _l4_exit_b(speak, cart) -> tuple:
    """鏈路 B 退出：speak 取消語音、清空 cart，返回 L1（子例程 A）。"""
    speak(L4_B_CANCEL_THANKS)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_exit_d_forced(speak, cart) -> tuple:
    """鏈路 D 強制退：speak 取消語音、清空 cart，返回 L1（子例程 A）。"""
    speak(L4_D_FORCED_EXIT)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_final_confirmation(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    total: int,
) -> tuple | None:
    """L4 D 達上限後的最終確認子狀態（2026-05-25 加；2026-05-26 重構 wall-clock）。

    顧客已被催促 6 次仍沒回應 + 第 7 次 timeout 進此狀態。給選擇：
        - 取消訂單（"1" / 「退出」/「取消」等）→ 清 cart 回 L1
        - 繼續當前付款（"2" / 「繼續」等）→ caller 重置 counter，回 L4 主迴圈
        - 亂回答 → 重 speak prompt，**每次重新給 6s**；亂答達 UNCLEAR_MAX 次 → 視為取消
        - 6s timeout → 視為取消（清 cart 回 L1）

    每次 read 都給 full WAIT_NO_RESPONSE 秒，避免 wall-clock 倒數造成「重 prompt 後
    顧客來不及答就被當 timeout」+「終端 timeout 顯示 5.999... 小數」兩個 UX bug。

    Returns:
        tuple ("L1_via_subroutine_a", 0, 0) → 取消（caller 直接 return）
        None  → 顧客選繼續（caller 應 reset loop_count + unclear_count = 0）
    """
    speak(L4_D_FINAL_PROMPT)
    unclear_count = 0

    while True:
        response = read_customer_input(timeout=WAIT_NO_RESPONSE)

        if response is None:
            return _l4_exit_d_forced(speak, cart)

        if response == "1":
            return _l4_exit_d_forced(speak, cart)

        if response == "2":
            return None

        # 語音意圖（用 l4_service mode，已含繼續 / 退出 keyword 處理 + no/nope → 退出）
        intent = classify_intent(response, "l4_service")
        if intent == "退出交易":
            return _l4_exit_d_forced(speak, cart)
        if intent == "繼續交易":
            return None

        # 亂回答 → 重 speak prompt；達 unclear 上限視為取消（同 timeout 行為，防無限重 prompt）
        unclear_count += 1
        if unclear_count >= UNCLEAR_MAX:
            return _l4_exit_d_forced(speak, cart)
        speak(L4_D_FINAL_PROMPT)


def _l4_service_mode(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    loop_count: int,
    do_action,
) -> tuple | None:
    """L4 鏈路 C 客服特殊模式（不自動返回）。

    顯示電話 + 提示選項，等顧客明確選擇退出或繼續。

    Returns:
        tuple → 已決定（退出 L1 或掃碼 L5）
        None  → 顧客選「繼續」→ 回 L4 主迴圈（loop_count / unclear_count 將被 reset）
    """
    print_terminal(SERVICE_PHONE)
    speak(L4_C_OPTIONS_PROMPT)
    # 2026-05-26 post-P8 修：移除 print_terminal(L4_C_OPTIONS_PROMPT) — 與上一行 speak
    # 同訊息形成 S1 chat-driven 視覺重複（語音模式 + 終端模式雙印）。production TTS 階段
    # 語音 prompt 由顧客聽，終端視覺顯示由未來 HTML/screen 層另接，無需在 sales/ 內 dup。

    while True:
        response = read_customer_input(timeout=L4_SERVICE_TIMEOUT)

        # 60s timeout → 強制退（清空 cart）
        if response is None:
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        # 終端 s → 視為繼續 + 掃碼成功 → L5（S3：speak 付款成功後跑鞠躬動作）
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

        # 語音判定（mode="l4_service"）
        intent = classify_intent(response, "l4_service")

        if intent == "退出交易":
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        if intent == "拒絕":
            # fallback：不強制顧客學「退出」一詞
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        if intent == "繼續交易":
            return None

        # 不命中 → 重複提示（同上：移除 print_terminal dup，只留 speak）
        speak(L4_C_OPTIONS_PROMPT)


def _l4_dispatch_response(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    loop_count: int,
    unclear_count: int,
    do_action,
) -> tuple | int | None | str:
    """L4 判定優先序 dispatcher（有回應時）。

    判定優先序：
        1. 終端 s → 鏈路 A（掃碼成功）
        2. 等待安撫意圖 → speak 溫和回應，不累計 unclear，不重印明細（2026-05-26 加）
        3. 拒絕意圖 → 鏈路 B
        4. 客服意圖 → 鏈路 C 客服特殊模式
        5. 想一下 / 結帳 / 商品 / 無法判斷 → 鏈路 E

    Returns:
        tuple → 已決定退出（next_state, next_loop_count, next_unclear_count）
        int   → unclear_count 更新值，回主迴圈繼續（E 鏈路；主迴圈重印明細）
        None  → 客服繼續（loop_count / unclear_count 應 reset），回主迴圈
        "ack" → 等待安撫（主迴圈 continue；不改計數器、不重印明細）
    """
    # 優先序 1：終端 s → 鏈路 A（S3：speak 付款成功語音後跑鞠躬動作）
    if response == "s":
        speak(L4_A_PAY_SUCCESS)
        do_action(ACTION_L4_PAY)
        return ("L5", 0, 0)

    # 優先序 2：拒絕 → 鏈路 B（classify_intent 先做，後面共用 intent）
    intent = classify_intent(response, "l4")

    # 2026-05-26 加：L4 顧客禮貌肯定 / 等待掃碼 → 溫和回應，不踢進 E 鏈路
    # 不 ++unclear_count、不重印明細、不重設 D 鏈路 loop —— 主迴圈自然 continue
    if intent == "等待安撫":
        speak(L4_ACK_GENTLE)
        return "ack"

    if intent == "拒絕":
        # 2026-05-29 cross-L cancel：拒絕意圖 → 先過 cancel_confirm gate
        # True → 鏈路 B 清 cart 退 L1；False → speak 繼續通知，回主迴圈 continue（不重置 budget）
        if cancel_confirm(speak, read_customer_input):
            return _l4_exit_b(speak, cart)
        speak(CANCEL_DECLINED_NOTICE)
        # 回主迴圈 continue（無計數器需更新；wall-clock budget 保留不重置）
        return "ack"

    # 優先序 4：客服 → 鏈路 C
    if intent == "客服":
        result = _l4_service_mode(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=loop_count,
            do_action=do_action,
        )
        if result is not None:
            return result
        # 客服選繼續 → 回 None（主迴圈 reset loop_count + unclear_count）
        return None

    # 優先序 4：想一下 / 結帳 / 商品 / 無法判斷 → 鏈路 E
    # （這三類在 L4 不適用，視為無法判斷）
    unclear_count += 1

    if unclear_count >= 3:
        # 自動進客服
        speak(L4_E_AUTO_SERVICE)
        result = _l4_service_mode(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=loop_count,
            do_action=do_action,
        )
        if result is not None:
            return result
        # 客服選繼續 → reset 兩計數器（回 None，主迴圈負責 reset）
        return None

    # unclear_count < 3 → speak 重問
    speak(L4_E_CLARIFY)
    return unclear_count
