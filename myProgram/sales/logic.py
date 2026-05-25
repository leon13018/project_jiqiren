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
    unmute_opencv,
    speak,
    do_action,
    read_customer_input,
    sleep,
    schedule,
    exit_program,
) -> None:
    """S1 v2 主迴圈：L1 → dialog → L4 → L5 → 子例程 A → L1 cycle。"""
    cart = cart_module.new_cart()

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
            exit_program=exit_program,
            schedule=schedule,
        )
        if result is None:
            return
        # result == "L2" — 進 dialog 層

        # === dialog（L2/L3 合一）===
        _assert_cart_empty(cart, "進 dialog")
        next_state, _think = states.run_dialog(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=0,
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(cart, "dialog 退出後（dialog A 已視情況清 cart）")
            _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule)
            continue
        # next_state == "L4"

        # === L4 ===
        _assert_cart_nonempty(cart, "進 L4")
        next_state, _loop, _unclear = states.run_l4(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            loop_count=0,
            unclear_count=0,
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(cart, "L4 非掃碼退出後（L4-B/C/D 已清 cart）")
            _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule)
            continue
        # next_state == "L5"

        # === L5 ===
        _assert_cart_nonempty(cart, "進 L5（從 L4-A 帶 cart）")
        next_state, _, _ = states.run_l5(
            speak=speak,
            do_action=do_action,
            mute_opencv=mute_opencv,
            cart=cart,
            sleep=sleep,
        )
        _assert_cart_empty(cart, "L5 退出後（L5 應已清 cart）")
        _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule)


def _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule) -> None:
    """呼叫子例程 A（背景排程叫賣，fire-and-forget）。"""
    states.run_subroutine_a(
        speak=speak,
        mute_opencv=mute_opencv,
        unmute_opencv=unmute_opencv,
        schedule=schedule,
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
