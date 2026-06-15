"""L4：印金額 + 等掃碼（結帳層；2026-05-31 v3 雙計時器設計）。

對應規格書：
    - 原規格：resources/plans/業務程式邏輯規劃/L4.md（鏈路 A/B/C 退出語意保留）
    - v3 計時器設計：resources/specs/L4_v3_dual_timer_spec.md

設計（v3 雙計時器）：
    - 兩個獨立 wall-clock 計時器，與子鏈路狀態完全解耦：
        * L4_TOTAL_BUDGET = 36s 總 budget：耗盡 → forced exit
        * L4_QR_REFRESH_INTERVAL = 12s QR 刷新循環：每循環開頭無條件重印 + 重 speak
          L4_REMIND_PROMPT（不論顧客是否回應；模擬「QR code 每 12s 重新生成」UX）
    - 36 = 12 × 3，總 budget 期間共 3 個循環。進入 L4 算第 1 個循環開頭。
    - 亂答 / ack / cancel_confirm NO：完全不影響兩計時器（continue 主迴圈）
    - cancel_confirm / service_confirm 子狀態：兩計時器**暫停 + 補償**
      （子狀態實際耗時 += 兩個 deadline，凍結期間時間「回補」）
    - 客服 yes「繼續」：**重置兩計時器**（fresh 36s + 重印 + 重 speak entry prompt）
    - 鏈路：A 掃碼成功 → L5；B 拒絕（cancel_confirm gated）→ 退 L1；C 客服 → confirm 子狀態

v2 supersedes（commit 5710826 為止）：
    - v2「30s 單一 budget + 12s 沒回應重提示」
    - v2 視覺問題：ack 後 read 重新從 12 倒數像「循環被打斷重來」、30s 非循環倍數
    - v3 解：兩計時器解耦 → 循環視覺穩定 + budget 嚴格控管

更舊版移除（v1 過度設計，2026-05-30 已廢，v3 不變）：
    - loop_count / unclear_count / _l4_final_confirmation
    - L4_SERVICE_TIMEOUT 獨立 60s

Return shape 保持 (next_state, 0, 0) 3-tuple — 與 logic.py 既有 unpack 相容。
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    L4_TOTAL_BUDGET,
    L4_QR_REFRESH_INTERVAL,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_QR_MOCK_HINT,
    L4_A_PAY_SUCCESS_FAREWELL,
    L4_ACK_GENTLE,
    L4_B_CANCEL_THANKS,
    L4_D_FORCED_EXIT,
    L4_REMIND_PROMPT,
    L4_UNCLEAR_NOTICE,
    ACTION_L4_PAY,
    CANCEL_DECLINED_NOTICE,
)
from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.nlu import classify_intent
from myProgram.sales import cart as cart_module
from myProgram.sales.states._cancel_confirm import cancel_confirm
from myProgram.sales.states._service_confirm import service_confirm


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
    """L4 主迴圈：結帳層（印金額 + 等掃碼）— v3 雙計時器設計。

    顧客從 L3 攜帶 cart 進入，等掃碼付款。
    鏈路 A（掃碼）→ L5；
    鏈路 B（拒絕，cancel_confirm gated）→ 清空 cart → L1（子例程 A）；
    鏈路 C（客服）→ 一次性 24s 確認子狀態；
        客服 YES「繼續」回主迴圈時：**重置兩計時器** + 重印明細 + 重 speak entry prompt
        （fresh 36s + 12s 循環；對齊 v2 既有行為）。

    v3 雙計時器：
        - L4_TOTAL_BUDGET = 36s 總 budget：耗盡 → forced exit
        - L4_QR_REFRESH_INTERVAL = 12s 循環：每循環開頭無條件重印 + 重 speak REMIND
        - 兩計時器在 cancel_confirm / service_confirm 子狀態期間**暫停 + 補償**
        - 亂答 / ack / cancel_confirm NO：兩計時器完全不動

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
            L4 其他鏈路（B 取消 / C 客服 prompt / QR 循環刷新）不跑動作。

    Returns:
        (next_state, 0, 0) — 兩個 0 占位，保留 3-tuple shape 與 logic.py 相容；
        next_state ∈ {"L1_via_subroutine_a", "L5"}
    """
    # W2：facade 第一步建 io 束（全欄注入）；opencv_disable 不入 io（只在 facade 進場用一次）
    io = DialogIO(
        speak=speak,
        read_customer_input=read_customer_input,
        print_terminal=print_terminal,
        do_action=do_action,
        speak_and_wait=speak_and_wait,
    )

    # 進入 L4 → OpenCV 不需要（顧客已在掃碼），明示關閉（防呆）
    opencv_disable()

    # 進入時動作：計算總額、印明細（= 第 1 個循環刷新的視覺面）、speak 總額語音
    total = cart_module.calc_total(cart)
    _l4_print_entry_detail(cart, total, io)
    # v2 起：speak_and_wait 進場 prompt 後算 deadline — 顧客拿到完整 budget，
    # 而非「budget 減 entry prompt 播放時間」
    io.speak_blocking(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))

    # v3 雙計時器：兩個獨立 wall-clock deadline，從 entry prompt 播完起算
    budget_deadline, cycle_deadline = _l4_fresh_deadlines()

    # 主等待迴圈
    while True:
        now = time.monotonic()
        budget_remaining = budget_deadline - now
        cycle_remaining = cycle_deadline - now

        # 1. budget 耗盡 → forced exit（優先於循環刷新，避免在 budget 已耗盡時還刷一輪）
        if budget_remaining <= 0:
            return _l4_exit_to_l1(io, cart, L4_D_FORCED_EXIT)

        # 2. 循環到期 → 重印 + 重 speak L4_REMIND_PROMPT → 起下一個循環
        #    （不影響 budget_deadline；模擬「QR 每 12s 重新生成」UX）
        if cycle_remaining <= 0:
            _l4_print_entry_detail(cart, total, io)
            io.speak(L4_REMIND_PROMPT)
            cycle_deadline = time.monotonic() + L4_QR_REFRESH_INTERVAL
            continue

        # 3. read 顧客回應，timeout 取兩個 deadline 較小者
        #    （避免 read 超過 budget 或超過下個循環邊界）
        response = io.read_customer_input(timeout=min(cycle_remaining, budget_remaining))

        if response is None:
            # silent → 直接 continue（下次 iteration 由 cycle_deadline 判斷是否該刷新）
            # v3 改：v2 silent 立即 speak REMIND；v3 移除「沒回應重提示」概念，
            # 改用無條件循環刷新（cycle_deadline 到期時自然觸發）
            continue

        # 4. 有回應 → dispatch（含 cancel_confirm / service_confirm 暫停補償）
        result, pause_duration = _l4_dispatch_response(
            response=response,
            io=io,
            cart=cart,
        )
        if isinstance(result, tuple):
            return result
        if result == "reset":
            # 客服 yes「繼續」→ 重印明細 + 重 speak entry prompt + reset 兩計時器（fresh start）
            # 對齊 v2 既有「客服繼續 fresh 30s」行為（spec §2.4：reset 而非補償）
            _l4_print_entry_detail(cart, total, io)
            io.speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
            budget_deadline, cycle_deadline = _l4_fresh_deadlines()
            continue
        # result == "ack"
        # 若子狀態有耗時（cancel_confirm 進過子狀態）→ 補償兩個 deadline（時間「回補」）
        # 純 ack（等待安撫 / 亂輸入 / 沒進子狀態）→ pause_duration == 0.0 → no-op
        if pause_duration > 0:
            budget_deadline += pause_duration
            cycle_deadline += pause_duration
        continue


def _l4_fresh_deadlines() -> tuple:
    """回傳 (budget_deadline, cycle_deadline)——自此刻起算。

    entry 與客服 reset 兩處共用：兩計時器起算點必須同步（36 = 12 × 3 不變量，
    見 L4_v3_dual_timer_spec），抽單點避免雙處漂移。
    """
    now = time.monotonic()
    return now + L4_TOTAL_BUDGET, now + L4_QR_REFRESH_INTERVAL


def _l4_print_entry_detail(cart, total: int, io) -> None:
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

    Args:
        cart: 購物車 dict
        total: 訂單總額
        io: DialogIO callback 束
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
    io.print_terminal("\n".join(lines))


def _l4_exit_to_l1(io, cart, notice: str) -> tuple:
    """speak 退場語音、清空 cart，返回 L1（子例程 A）。

    W1 oop_w1：合併原 _l4_exit_b（鏈路 B 拒絕）/ _l4_exit_d_forced（budget 耗盡）
    — 兩者只差退場文案，以 notice 參數區分。

    Args:
        io: DialogIO callback 束
        cart: 購物車 dict
        notice: 退場語音文案
    """
    io.speak(notice)
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)


def _l4_pay_success(io) -> tuple:
    """鏈路 A 共同體：付款成功＋致謝合一句 speak + 鞠躬動作 + 進 L5（終端 "s" 與客服 "scan" 共用）。"""
    io.speak(L4_A_PAY_SUCCESS_FAREWELL)
    io.do_action(ACTION_L4_PAY)
    return ("L5", 0, 0)


def _l4_dispatch_response(response: str, io, cart) -> tuple:
    """L4 判定優先序 dispatcher（v3 雙計時器設計）。

    判定優先序：
        1. 終端 s → 鏈路 A（掃碼成功）→ L5
        2. 等待安撫意圖 → speak 溫和回應，無 pause（兩計時器不動）
        3. 拒絕意圖 → cancel_confirm gate（量測耗時 → 補償）
            YES → 退 L1；NO → speak DECLINED + 回報 pause_duration
        4. 客服意圖 → service_confirm（不量測耗時——reset 覆蓋補償）
            yes → "reset"（主迴圈重置兩計時器）
            no → 清 cart 退 L1
            scan → 進 L5（鏈路 A）
        5. 其他（想一下 / 結帳 / 商品 / 無法判斷）→ speak L4_UNCLEAR_NOTICE，無 pause

    Args:
        response: 顧客回應字串
        io: DialogIO callback 束
        cart: 購物車 dict

    Returns:
        (tuple, pause_duration) → 已決定（退出 L4）；caller 直接 return
        ("reset", 0.0) → 客服 yes「繼續」→ caller 重置兩計時器（不用 pause_duration）
        ("ack", pause_duration) → 純 ack 或 cancel NO；caller 補償 deadlines += pause_duration
            （純 ack pause_duration=0.0 → no-op；cancel NO pause_duration>0 → 真補償）
    """
    # 優先序 1：終端 s → 鏈路 A（S3：speak 付款成功語音後跑鞠躬動作）
    if response == "s":
        return (_l4_pay_success(io), 0.0)

    intent = classify_intent(response, "l4")

    # 優先序 2：等待安撫 → 溫和回應，無 pause
    if intent == "等待安撫":
        io.speak(L4_ACK_GENTLE)
        return ("ack", 0.0)

    # 優先序 3：拒絕 → cancel_confirm gate（量測耗時補償兩計時器）
    # l4 經 facade 呼叫（非 CANCEL_CONFIRM.run 實例）——既有測試以模組名 mock 此 seam（test_states 5697）
    if intent == "拒絕":
        paused_at = time.monotonic()
        cancelled = cancel_confirm(io.speak, io.read_customer_input, speak_and_wait=io.speak_and_wait)
        pause_duration = time.monotonic() - paused_at
        if cancelled:
            # YES → 退 L1（無需補償，已退出 L4）
            return (_l4_exit_to_l1(io, cart, L4_B_CANCEL_THANKS), 0.0)
        # NO → 繼續交易，補償子狀態凍結時間
        io.speak(CANCEL_DECLINED_NOTICE)
        return ("ack", pause_duration)

    # 優先序 4：客服 → service_confirm（24s 獨立 budget；不量測耗時——
    # 兩出口不是退出就是 reset，reset 覆蓋補償（spec §2.4），補償永不適用）
    if intent == "客服":
        result = _l4_service_mode(io=io, cart=cart)
        if isinstance(result, tuple):
            # service_mode 已決定退出（scan → L5 / no → L1），無需補償
            return (result, 0.0)
        # result is None → 客服 yes「繼續」→ caller 重置兩計時器（fresh start）
        return ("reset", 0.0)

    # 優先序 5：想一下 / 結帳 / 商品 / 無法判斷 → 印 unclear notice，無 pause
    io.speak(L4_UNCLEAR_NOTICE)
    return ("ack", 0.0)


def _l4_service_mode(io, cart) -> tuple | None:
    """L4 鏈路 C 客服模式（抽 _service_confirm helper）。

    使用共用 helper `service_confirm`（allow_scan=True 啟用終端 "s" fast path）；
    helper 內部行為：
        - print SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE「請問是否繼續交易？24秒...」
        - 一次性 L4_C_CONFIRM_TIMEOUT=24s 獨立 budget
        - YES keyword → "yes"（caller 回主迴圈）
        - NO keyword / silent / 24s 耗盡 → "no"（caller 清 cart 退 L1）
        - 終端 "s" → "scan"（L4 caller 進 L5 鏈路 A）
        - 亂答 → speak L4_UNCLEAR_NOTICE + 不重置 budget

    本函式只負責解讀 helper 回傳值並執行 L4-specific exit actions：
        - "yes" → return None（caller 重置兩計時器 + 重印明細 + 重 speak entry prompt）
        - "scan" → speak L4_A_PAY_SUCCESS + do_action(ACTION_L4_PAY) + 進 L5（鏈路 A）
        - "no" → 清 cart 退 L1

    Args:
        io: DialogIO callback 束
        cart: 購物車 dict

    Returns:
        tuple → 已決定（退 L1 / 進 L5）
        None  → 顧客選 YES「繼續」→ 回主迴圈（caller reset 兩計時器）
    """
    # l4 經 facade 呼叫（非 SERVICE_CONFIRM_SCAN.run 實例）——既有測試以模組名 mock 此 seam（test_states 5734/5774）
    result = service_confirm(
        speak=io.speak,
        print_terminal=io.print_terminal,
        read_customer_input=io.read_customer_input,
        speak_and_wait=io.speak_and_wait,
        allow_scan=True,
    )
    if result == "yes":
        return None
    if result == "scan":
        return _l4_pay_success(io)
    # result == "no" → 清 cart 退 L1
    cart_module.clear_cart(cart)
    return ("L1_via_subroutine_a", 0, 0)
