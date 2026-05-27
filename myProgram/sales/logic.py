"""業務邏輯主控（S1 v2，2026-05-25 A2-c 落地；同日合併 L2/L3 為 dialog 層）。

職責：
    - 4 層狀態機主迴圈（L1 模式選擇 → dialog 對話層 → L4 結帳 → L5 致謝）
    - 跨層 cycle dispatch（L1→dialog→L4→L5→子例程 A→L1）
    - 持有 cart（唯一 cycle state）
    - cart invariant check（A4-c）— 每進新層 fail-fast assert

設計約束：
    - 純單線程，無 threading / queue / 旗號（incremental-rebuild S1 階段）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 對外動作 callback 注入（caller = myProgram.py 入口層）

層狀態判定原則（2026-05-25 B 方案敲定）：
    - L1 ↔ dialog ↔ L4 ↔ L5 由「世界狀態」決定（非動作歷史）
    - dialog 內部 cart 狀態決定模式：cart 空 = 詢問需求；cart 非空 = 詢問加單 / 結帳
    - 未來加刪除商品時 cart 變空，dialog 下一輪自動回詢問需求模式（無需額外 transition）

各 run_? return shape：
    - run_l1 → str | None ("L2" / None — 字串保留沿用，但語義 = "進 dialog"）
    - run_dialog → tuple[str, int]（next_state ∈ {"L4", "L1_via_subroutine_a"}, next_think_count）
    - run_l4 / run_l5 → tuple[str, int, int]（next_state, next_loop_count, next_unclear_count）
"""

from myProgram.sales import states
from myProgram.sales import cart as cart_module


def run(
    *,
    print_terminal,
    read_terminal_key,
    opencv_dwell_seconds,
    opencv_disable,
    opencv_enable,
    mute_opencv,
    speak,
    do_action,
    read_customer_input,
    sleep,
    schedule,
    exit_program,
    show_hawk_help,
) -> None:
    """S1 v2 主迴圈：L1 → dialog → L4 → L5 → 子例程 A → L1 cycle。

    L1 入口流程：
    - 首次進 L1：顯示主選單，商家選 1/2/3
    - subroutine_a 後續 L1：跳過主選單直接進 hawk（連續叫賣，2026-05-26 加）
      涵蓋 4 個出口：dialog reject / dialog timeout / L4 cancel / L5 完成
    """
    cart = cart_module.new_cart()
    # 2026-05-26 加：subroutine_a 後續 L1 跳過主選單直接 hawk；首次進 L1 走主選單
    enter_hawk_immediately = False

    while True:
        # === L1 ===
        _assert_cart_empty(cart, "進 L1")
        result = states.run_l1(
            print_terminal=print_terminal,
            read_terminal_key=read_terminal_key,
            opencv_dwell_seconds=opencv_dwell_seconds,
            opencv_disable=opencv_disable,
            opencv_enable=opencv_enable,
            speak=speak,
            do_action=do_action,
            exit_program=exit_program,
            schedule=schedule,
            show_hawk_help=show_hawk_help,
            enter_hawk_immediately=enter_hawk_immediately,
        )
        enter_hawk_immediately = False  # 消費後 reset；下次需重設才會跳選單
        if result is None:
            return
        # result == "L2" — 進 dialog 層

        # === dialog（L2/L3 合一）===
        _assert_cart_empty(cart, "進 dialog")
        next_state, _think = states.run_dialog(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=0,
            opencv_disable=opencv_disable,
            do_action=do_action,
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(cart, "dialog 退出後（dialog A 已視情況清 cart）")
            _invoke_subroutine_a(mute_opencv)
            enter_hawk_immediately = True
            continue
        # next_state == "L4"

        # === L4 ===
        _assert_cart_nonempty(cart, "進 L4")
        next_state, _loop, _unclear = states.run_l4(
            speak=speak,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=0,
            unclear_count=0,
            opencv_disable=opencv_disable,
            do_action=do_action,
        )
        if next_state == "L1_via_subroutine_a":
            # L4 非 L5 路徑必清 cart（_l4_exit_b / _l4_exit_d_forced / _l4_service_mode 退出三條
            # 皆 clear_cart；掃碼 → L5 走 elif 分支由 L5 自身 clear，不踩此 assert）
            # （2026-05-26 P3.C 修訂：原「L4-B/C/D 已清 cart」漏列 _l4_service_mode 掃碼→L5 路徑）
            _assert_cart_empty(cart, "L4 非掃碼退出後（L4 三條清 cart 路徑）")
            _invoke_subroutine_a(mute_opencv)
            enter_hawk_immediately = True
            continue
        # next_state == "L5"

        # === L5 ===
        _assert_cart_nonempty(cart, "進 L5（從 L4-A 帶 cart）")
        next_state, _, _ = states.run_l5(
            speak=speak,
            cart=cart,
            sleep=sleep,
            do_action=do_action,
        )
        _assert_cart_empty(cart, "L5 退出後（L5 應已清 cart）")
        _invoke_subroutine_a(mute_opencv)
        enter_hawk_immediately = True


def _invoke_subroutine_a(mute_opencv) -> None:
    """呼叫子例程 A（2026-05-25 簡化：只 mute 12s 緩衝，不再 unmute / 不再叫賣）。"""
    states.run_subroutine_a(
        mute_opencv=mute_opencv,
    )


def _assert_cart_empty(cart, ctx: str) -> None:
    """A4-c：fail-fast assert cart 應為空。違反 → 系統 bug，立刻爆。"""
    if not cart_module.is_empty(cart):
        raise AssertionError(
            f"Cart invariant 違反 [{ctx}]：應為空但 cart={dict(cart)}"
        )


def _assert_cart_nonempty(cart, ctx: str) -> None:
    """A4-c：fail-fast assert cart 應非空。違反 → 系統 bug，立刻爆。"""
    if cart_module.is_empty(cart):
        raise AssertionError(
            f"Cart invariant 違反 [{ctx}]：應非空但 cart 為空"
        )
