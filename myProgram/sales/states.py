"""L0-L5 各層鏈路實作（S1 v2，2026-05-25 全層齊全 + B 類 refactor）。

對應規格書：resources/plans/業務程式邏輯規劃/
    - L0：共通子例程 A（「回 L1 叫賣」）/ 共通常數 / NLU
    - L1：商家模式選擇層（叫賣 / 待機 / 客服）
    - L2：詢問需求（顧客互動 — 初次點單）
    - L3：詢問額外需求（顧客互動 — 加單迴圈）
    - L4：印金額 + 等掃碼（結帳層；客服特殊模式 + 6 次循環 + 雙計數器）
    - L5：謝謝惠顧（致謝層；純序列動作）

對外 callback 集合（各層子集，由 caller 注入；詳見每個 run_l? docstring）：
    - speak(text) / do_action(name) — 語音 / 動作
    - print_terminal(text) — 終端輸出
    - read_terminal_key() / read_customer_input(timeout) — 輸入（L1 商家鍵盤 / L2-L5 顧客回應）
    - opencv_disable() / opencv_enable() / opencv_dwell_seconds() — L1 OpenCV 控制
    - mute_opencv(seconds) / unmute_opencv() — L0 子例程 A / L5 OpenCV 屏蔽
    - exit_program() — L1 全域 q
    - schedule(seconds, fn) — L0 子例程 A / L1 叫賣輪播

設計原則（選項 C）：
    - **嚴格不 import 廠商 SDK**（ActionGroupControl / Board / pigpio / smbus2 等）
    - 純邏輯 + callback 注入：caller（myProgram.py 入口層）負責 wire-up
      真實 terminal / TTS / OpenCV / 廠商動作
    - 業務邏輯可完整在 Windows 跑 pytest（107 tests）

return shape（B1+B7 推遲 — 各層不一致由入口層處理）：
    - run_subroutine_a → None
    - run_l1 → str | None ("L2" / None)
    - run_l2 / run_l3 → tuple[str, int]（next_state, next_think_count）
    - run_l4 / run_l5 → tuple[str, int, int]（next_state, next_loop_count, next_unclear_count）
"""

from myProgram.sales.constants import (
    PRODUCTS,
    HAWK_SLOGANS,
    HAWK_INTERVAL,
    OPENCV_MUTE,
    OPENCV_DWELL,
    WAIT_NO_RESPONSE,
    AUTO_CHECKOUT_NOTICE,
    L1_MENU_BANNER,
    L1_HAWK_ENTRY_PROMPT,
    L1_STANDBY_ENTRY_PROMPT,
    SERVICE_PHONE,
    L2_ENTRY_PROMPT,
    L2_REJECT_THANKS,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
    L3_ENTRY_PROMPT,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_A_PAY_SUCCESS,
    L4_B_CANCEL_THANKS,
    L4_C_OPTIONS_PROMPT,
    L4_D_FORCED_EXIT,
    L4_E_CLARIFY,
    L4_E_AUTO_SERVICE,
    L4_D_VOICE_NEUTRAL,
    L4_D_VOICE_GENTLE,
    L4_D_VOICE_MODERATE,
    L4_D_VOICE_WARNING,
    L4_SERVICE_TIMEOUT,
    L4_MAX_LOOPS,
    THANK_DELAY,
    L5_THANKS,
)
from myProgram.sales.nlu import classify_intent, parse_quantity
from myProgram.sales import cart as cart_module


def run_subroutine_a(
    speak,
    mute_opencv,
    unmute_opencv,
    schedule,
) -> None:
    """子例程 A：「回 L1 叫賣」。

    步驟（依規格書 L0_共通.md「子例程 A」段）：
        1. 立即屏蔽 OpenCV 偵測 OPENCV_MUTE（12）秒
        2. OPENCV_MUTE 秒後恢復 OpenCV + 立即播第 1 組叫賣
        3. 後續每 HAWK_INTERVAL（12）秒換下一組，依 mod 6 輪流

    Args:
        speak: callback(text: str) — 語音播放
        mute_opencv: callback(seconds: float) — 屏蔽 OpenCV 偵測
        unmute_opencv: callback() — 恢復 OpenCV 偵測
        schedule: callback(seconds: float, fn) — 排程延遲執行
    """
    # 步驟 1：立即屏蔽 OpenCV
    mute_opencv(OPENCV_MUTE)

    # 步驟 2 + 3：OPENCV_MUTE 秒後恢復並開始叫賣
    _schedule_hawk(
        speak=speak,
        unmute_opencv=unmute_opencv,
        schedule=schedule,
        hawk_index=0,
        delay=OPENCV_MUTE,
        first_call=True,
    )


def _schedule_hawk(
    speak,
    unmute_opencv,
    schedule,
    hawk_index: int,
    delay: float,
    first_call: bool = False,
) -> None:
    """排程下一輪叫賣（遞迴排程）。

    Args:
        speak: 語音 callback
        unmute_opencv: 恢復 OpenCV callback（第一次才呼叫）
        schedule: 排程 callback
        hawk_index: 當前叫賣術語索引（0-based，mod 6 輪替）
        delay: 距下次叫賣的延遲秒數
        first_call: 是否為 OpenCV mute 結束後的第一次叫賣
    """
    def _on_due():
        # 第一次才恢復 OpenCV
        if first_call:
            unmute_opencv()
        # 播放當前索引對應的叫賣術語
        speak(HAWK_SLOGANS[hawk_index % 6])
        # 排程下一輪
        _schedule_hawk(
            speak=speak,
            unmute_opencv=unmute_opencv,
            schedule=schedule,
            hawk_index=hawk_index + 1,
            delay=HAWK_INTERVAL,
            first_call=False,
        )

    schedule(delay, _on_due)


# ============================================================
# L1：模式選擇（商家層）
# ============================================================

def run_l1(
    print_terminal,
    read_terminal_key,
    opencv_dwell_seconds,
    opencv_disable,
    opencv_enable,
    speak,
    exit_program,
    schedule,
):
    """L1 主迴圈：商家模式選擇層。

    顯示選單 → 讀鍵 → 分派三個鏈路（叫賣 / 待機 / 客服）。
    按 q 任何時刻退出程式。

    Args:
        print_terminal: callback(text: str) — 印終端文字
        read_terminal_key: callback() -> str — 讀一個鍵盤輸入
        opencv_dwell_seconds: callback() -> float — 取得 OpenCV 偵測人持續秒數
        opencv_disable: callback() -> None — 關閉 OpenCV
        opencv_enable: callback() -> None — 開啟 OpenCV
        speak: callback(text: str) -> None — 播語音（叫賣用）
        exit_program: callback() -> None — 終止程式
        schedule: callback(seconds, fn) -> None — 排程（叫賣輪播用）

    Returns:
        'L2' — 叫賣模式中 OpenCV 觸發轉 L2
        None — 程式終止（exit_program 被呼叫）
    """
    while True:
        # ---- 印選單 ----
        print_terminal(L1_MENU_BANNER)

        # ---- 讀使用者輸入 ----
        key = read_terminal_key()

        if key == "q":
            exit_program()
            return None
        elif key == "3":
            _run_l1_service(print_terminal)
            # 客服印完電話立即回選單（continue 到下一輪）
            continue
        elif key == "2":
            result = _run_l1_standby(
                print_terminal=print_terminal,
                read_terminal_key=read_terminal_key,
                opencv_disable=opencv_disable,
                opencv_enable=opencv_enable,
                exit_program=exit_program,
            )
            if result is None:
                return None
            # result == 'menu' → 回選單
            continue
        elif key == "1":
            result = _run_l1_hawk(
                print_terminal=print_terminal,
                read_terminal_key=read_terminal_key,
                opencv_dwell_seconds=opencv_dwell_seconds,
                opencv_enable=opencv_enable,
                speak=speak,
                exit_program=exit_program,
                schedule=schedule,
            )
            if result == "L2":
                return "L2"
            return None
        # 其他鍵：重印選單（但按 q 已在上面處理）


def _run_l1_service(print_terminal) -> None:
    """鏈路 A — 客服模式：印電話後返回（讓 run_l1 主迴圈回選單）。"""
    print_terminal(SERVICE_PHONE)


def _run_l1_standby(
    print_terminal,
    read_terminal_key,
    opencv_disable,
    opencv_enable,
    exit_program,
):
    """鏈路 B — 待機模式：印提示 → 靜默等待 → r 回選單 / q 退出。

    Returns:
        'menu' — 按 r 回 L1 選單
        None — 按 q 退出程式
    """
    # 關閉 OpenCV（待機期間完全暫停）
    opencv_disable()
    # 印提示
    print_terminal(L1_STANDBY_ENTRY_PROMPT)

    while True:
        key = read_terminal_key()
        if key == "q":
            exit_program()
            return None
        elif key == "r":
            # 按 r 回主選單，重新開啟 OpenCV
            opencv_enable()
            return "menu"
        # 其他鍵忽略，繼續等待


def _run_l1_hawk(
    print_terminal,
    read_terminal_key,
    opencv_dwell_seconds,
    opencv_enable,
    speak,
    exit_program,
    schedule,
):
    """鏈路 C — 叫賣模式：立即播第 1 組 + OpenCV 開 → 等 OpenCV 觸發或 q 退出。

    Returns:
        'L2' — OpenCV dwell ≥ OPENCV_DWELL 觸發轉 L2
        None — 按 q 退出程式
    """
    # 印進入提示
    print_terminal(L1_HAWK_ENTRY_PROMPT)
    # 開啟 OpenCV
    opencv_enable()
    # 立即播第 1 組叫賣（無 OPENCV_MUTE 緩衝）
    speak(HAWK_SLOGANS[0])
    # 排程後續叫賣輪播（從索引 1 開始，延遲 HAWK_INTERVAL 秒）
    _schedule_hawk_l1(speak=speak, schedule=schedule, hawk_index=1)

    # 主迴圈：檢查 OpenCV dwell / 讀鍵
    while True:
        # 檢查 OpenCV dwell（有無顧客持續停留）
        if opencv_dwell_seconds() >= OPENCV_DWELL:
            return "L2"
        # 讀鍵（non-blocking；測試以序列模擬）
        key = read_terminal_key()
        if key == "q":
            exit_program()
            return None
        # 其他鍵（1 / 2 / 3 等）忽略，繼續叫賣


def _schedule_hawk_l1(speak, schedule, hawk_index: int) -> None:
    """叫賣輪播排程（L1 叫賣模式，不需 unmute_opencv）。"""
    def _on_due():
        speak(HAWK_SLOGANS[hawk_index % 6])
        _schedule_hawk_l1(speak=speak, schedule=schedule, hawk_index=hawk_index + 1)

    schedule(HAWK_INTERVAL, _on_due)


# ============================================================
# L2：詢問需求（顧客互動 — 初次點單）
# ============================================================

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
        intent = classify_intent(response, "normal")

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

        # 優先序 5：商品 → C
        if intent in ("商品:冰紅茶", "商品:刮刮樂"):
            product = intent.split(":")[1]
            qty = parse_quantity(response)
            cart_module.add_item(cart, product, qty)
            speak(L2_C_ADDED)
            return ("L3", 0)

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
    intent = classify_intent(response, "normal")

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
        product = intent.split(":")[1]
        qty = parse_quantity(response)
        cart_module.add_item(cart, product, qty)
        speak(L2_C_ADDED)
        return ("L3", 0)

    # 無法判斷 → B-1
    speak(L2_B1_CLARIFY)
    return None  # 回主等待


# ============================================================
# L3：詢問額外需求（顧客互動 — 加單迴圈）
# ============================================================

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

    # 優先序 6：商品 → 鏈路 B-3（加單繼續循環）
    if intent in ("商品:冰紅茶", "商品:刮刮樂"):
        product = intent.split(":")[1]
        qty = parse_quantity(response)
        cart_module.add_item(cart, product, qty)
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

    Returns:
        tuple (next_state, next_think_count)
    """
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


# ============================================================
# L4：印金額 + 等掃碼（結帳層）
# ============================================================

def run_l4(
    speak,
    do_action,
    print_terminal,
    read_customer_input,
    cart,
    loop_count: int = 0,
    unclear_count: int = 0,
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
        do_action: callback(name: str) — 動作（規格 TBD，stub 可 no-op）
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        cart: 購物車 dict（從 L3 帶來）
        loop_count: D 鏈路循環計數（預設 0；客服繼續時 reset 0）
        unclear_count: E 鏈路計數（預設 0；A / B 觸發時 reset 0）

    Returns:
        (next_state, next_loop_count, next_unclear_count)
        next_state ∈ {"L1_via_subroutine_a", "L5"}
    """
    # 進入時動作：計算總額、印明細、speak 總額語音
    total = cart_module.calc_total(cart)
    _l4_print_entry_detail(cart, total, print_terminal)
    speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))

    # 主等待迴圈
    while True:
        # 若 loop_count 已達 L4_MAX_LOOPS，此輪等待完直接強制退
        if loop_count >= L4_MAX_LOOPS:
            response = read_customer_input(timeout=WAIT_NO_RESPONSE)
            if response is None:
                # 強制退
                return _l4_exit_d_forced(speak, cart)
            # 有回應 → 仍走判定優先序
            result = _l4_dispatch_response(
                response=response,
                speak=speak,
                print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                cart=cart,
                loop_count=loop_count,
                unclear_count=unclear_count,
            )
            if isinstance(result, tuple):
                return result
            # E 類（unclear_count 更新）
            if isinstance(result, int):
                unclear_count = result
            continue

        # 一般等待
        response = read_customer_input(timeout=WAIT_NO_RESPONSE)

        if response is None:
            # 鏈路 D：loop_count++，說催促語音
            loop_count += 1
            _l4_d_speak_loop_voice(loop_count, total, speak)
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
        )

        if isinstance(result, tuple):
            return result

        # E 類回傳 int（更新後的 unclear_count）
        if isinstance(result, int):
            unclear_count = result
            continue

        # result is None → C 繼續（loop_count / unclear_count 已在 _l4_service_mode 內 reset）
        # 但 _l4_dispatch_response 會在 C 繼續時回傳 tuple 或 None
        # 這裡 None 代表繼續（客服繼續後 reset 兩個計數器）
        loop_count = 0
        unclear_count = 0


def _l4_print_entry_detail(cart, total: int, print_terminal) -> None:
    """印 L4 進入時的金額明細。

    格式：
        ====================================
        您的訂單：
          商品名 ×qty = 小計 元
          ...
        ------------------------------------
        總金額：X 元
        請掃碼付款（終端輸入 s + Enter 模擬掃碼成功）
        ====================================
    """
    lines = [
        "====================================",
        "您的訂單：",
    ]
    for product, qty in cart.items():
        unit = PRODUCTS[product]["實際"]
        subtotal = unit * qty
        lines.append(f"  {product} ×{qty} = {subtotal} 元")
    lines.append("------------------------------------")
    lines.append(f"總金額：{total} 元")
    lines.append("請掃碼付款（終端輸入 s + Enter 模擬掃碼成功）")
    lines.append("====================================")
    print_terminal("\n".join(lines))


def _l4_d_speak_loop_voice(loop_count: int, total: int, speak) -> None:
    """L4 鏈路 D 4 階段催促語音 dispatcher。

    loop_count 1 → 中性；2 → 柔提醒；3/4 → 中度催促；5/6 → 明確警告。
    """
    if loop_count == 1:
        speak(L4_D_VOICE_NEUTRAL.format(total=total))
    elif loop_count == 2:
        speak(L4_D_VOICE_GENTLE.format(total=total))
    elif loop_count in (3, 4):
        speak(L4_D_VOICE_MODERATE.format(total=total))
    elif loop_count in (5, 6):
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


def _l4_service_mode(
    speak,
    print_terminal,
    read_customer_input,
    cart,
    loop_count: int,
) -> tuple | None:
    """L4 鏈路 C 客服特殊模式（不自動返回）。

    顯示電話 + 提示選項，等顧客明確選擇退出或繼續。

    Returns:
        tuple → 已決定（退出 L1 或掃碼 L5）
        None  → 顧客選「繼續」→ 回 L4 主迴圈（loop_count / unclear_count 將被 reset）
    """
    print_terminal(SERVICE_PHONE)
    speak(L4_C_OPTIONS_PROMPT)
    print_terminal(L4_C_OPTIONS_PROMPT)

    while True:
        response = read_customer_input(timeout=L4_SERVICE_TIMEOUT)

        # 60s timeout → 強制退（清空 cart）
        if response is None:
            cart_module.clear_cart(cart)
            return ("L1_via_subroutine_a", 0, 0)

        # 終端 s → 視為繼續 + 掃碼成功 → L5
        if response == "s":
            speak(L4_A_PAY_SUCCESS)
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

        # 不命中 → 重複提示
        speak(L4_C_OPTIONS_PROMPT)
        print_terminal(L4_C_OPTIONS_PROMPT)


# ============================================================
# L5：謝謝惠顧（致謝層）
# ============================================================

def run_l5(
    speak,
    do_action,
    mute_opencv,
    cart,
    sleep,
) -> tuple:
    """L5 致謝層：最簡單一層，純序列動作，無顧客互動。

    進入時動作（依規格書 L5.md）：
        1. 立即啟動 OpenCV mute THANK_DELAY 秒（致謝屏蔽期）
        2. speak 致謝語音（L5_THANKS）
        3. 清空 cart（交易完成重置）
        4. 等 THANK_DELAY 秒（sleep callback）
        5. 套用子例程 A 回 L1（return ("L1_via_subroutine_a", 0, 0)）

    Args:
        speak: callback(text: str) — 語音播放
        do_action: callback(name: str) — 動作（規格 TBD，stub no-op）
        mute_opencv: callback(seconds: float) — 屏蔽 OpenCV 偵測
        cart: 購物車 dict（L5 內清空）
        sleep: callback(seconds: float) — 等待（純睡眠，無回傳值）

    Returns:
        ("L1_via_subroutine_a", 0, 0)
        （沿用 L4 三態 return tuple shape，loop_count + unclear_count reset 為 0）
    """
    # ENTRY-001：進入時立即屏蔽 OpenCV THANK_DELAY 秒
    mute_opencv(THANK_DELAY)

    # ENTRY-002：speak 致謝語音
    speak(L5_THANKS)

    # ENTRY-003：清空 cart（交易完成）
    cart_module.clear_cart(cart)

    # A-001：等 THANK_DELAY 秒後套用子例程 A 回 L1
    sleep(THANK_DELAY)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_dispatch_response(
    response: str,
    speak,
    print_terminal,
    read_customer_input,
    cart,
    loop_count: int,
    unclear_count: int,
) -> tuple | int | None:
    """L4 判定優先序 dispatcher（有回應時）。

    判定優先序：
        1. 終端 s → 鏈路 A（掃碼成功）
        2. 拒絕意圖 → 鏈路 B
        3. 客服意圖 → 鏈路 C 客服特殊模式
        4. 想一下 / 結帳 / 商品 / 無法判斷 → 鏈路 E

    Returns:
        tuple → 已決定退出（next_state, next_loop_count, next_unclear_count）
        int   → unclear_count 更新值，回主迴圈繼續
        None  → 客服繼續（loop_count / unclear_count 應 reset），回主迴圈
    """
    # 優先序 1：終端 s → 鏈路 A
    if response == "s":
        speak(L4_A_PAY_SUCCESS)
        return ("L5", 0, 0)

    # 優先序 2：拒絕 → 鏈路 B
    intent = classify_intent(response, "normal")

    if intent == "拒絕":
        return _l4_exit_b(speak, cart)

    # 優先序 3：客服 → 鏈路 C
    if intent == "客服":
        result = _l4_service_mode(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=loop_count,
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
        )
        if result is not None:
            return result
        # 客服選繼續 → reset 兩計數器（回 None，主迴圈負責 reset）
        return None

    # unclear_count < 3 → speak 重問
    speak(L4_E_CLARIFY)
    return unclear_count
