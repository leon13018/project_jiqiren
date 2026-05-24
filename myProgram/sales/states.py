"""L0-L1 各層鏈路實作（S1 v2）。

對應規格書：
    - L0：共通子例程 A（「回 L1 叫賣」）
    - L1：商家模式選擇層（叫賣 / 待機 / 客服）
    - L2-L5：尚未實作（TODO）

設計原則：
    - 對外動作以 callback 注入（speak / mute_opencv / unmute_opencv / schedule）
    - 不直接 import 廠商 SDK（ActionGroupControl / Board）
    - 單檔起步，等長到 >300 行再拆 states/ 子資料夾
"""

from myProgram.sales.constants import (
    HAWK_SLOGANS,
    HAWK_INTERVAL,
    OPENCV_MUTE,
    OPENCV_DWELL,
    WAIT_NO_RESPONSE,
    L1_MENU_BANNER,
    L1_HAWK_ENTER_PROMPT,
    L1_STANDBY_ENTER_PROMPT,
    SERVICE_PHONE,
    L2_GREETING_PROMPT,
    L2_REJECT_THANKS,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
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
    print_terminal(L1_STANDBY_ENTER_PROMPT)

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
    print_terminal(L1_HAWK_ENTER_PROMPT)
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
    speak(L2_GREETING_PROMPT)

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


def _schedule_hawk_l1(speak, schedule, hawk_index: int) -> None:
    """叫賣輪播排程（L1 叫賣模式，不需 unmute_opencv）。"""
    def _on_due():
        speak(HAWK_SLOGANS[hawk_index % 6])
        _schedule_hawk_l1(speak=speak, schedule=schedule, hawk_index=hawk_index + 1)

    schedule(HAWK_INTERVAL, _on_due)
