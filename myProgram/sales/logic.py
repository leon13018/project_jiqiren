"""業務邏輯主控（S1 v2，2026-05-25 A2-c 落地）。

職責：
    - 5 層狀態機主迴圈（L1 模式選擇 → L2 詢問需求 → L3 加單迴圈 → L4 結帳 → L5 致謝）
    - 跨層 cycle dispatch（L1→L2→L3→L4→L5→子例程 A→L1）
    - 持有 cart（唯一 cycle state）；think_count / loop_count / unclear_count 由各層內部管理
    - cart invariant check（A4-c）— 每進新層 fail-fast assert

設計約束：
    - 純單線程，無 threading / queue / 旗號（incremental-rebuild S1 階段）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 對外動作 callback 注入（caller = myProgram.py 入口層）

各 run_l? return shape 不一致（B1+B7 推遲，本層統一吸收）：
    - run_l1 → str | None ("L2" / None)
    - run_l2 / run_l3 → tuple[str, int]（next_state, next_think_count）
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
    schedule,
    exit_program,
) -> None:
    """S1 v2 主迴圈：L1 → L2 → L3 → L4 → L5 → 子例程 A → L1 cycle。

    持有 cycle state：cart（dict）
    各 run_l? 內部持有 think_count / loop_count / unclear_count（caller 重置為 0 進每一層新一輪）

    當 run_l1 回 None（exit_program 已呼叫）→ return（程式結束流程）
    """
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
            return  # exit_program 已呼叫
        # result == "L2"

        # === L2 ===
        _assert_cart_empty(cart, "進 L2")
        next_state, _think = states.run_l2(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=0,
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(cart, "L2-A 退出後（cart 應未動）")
            _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule)
            continue
        # next_state == "L3"

        # === L3 ===
        _assert_cart_nonempty(cart, "進 L3（從 L2-C 帶 cart）")
        next_state, _think = states.run_l3(
            speak=speak,
            do_action=do_action,
            print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            cart=cart,
            think_count=0,
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(cart, "L3-A 退出後（L3-A 已清 cart）")
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
            read_customer_input=read_customer_input,
        )
        # L5 內部已清 cart
        _assert_cart_empty(cart, "L5 退出後（L5 應已清 cart）")
        _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule)
        # 自然 continue 回 L1


def _invoke_subroutine_a(speak, mute_opencv, unmute_opencv, schedule) -> None:
    """呼叫子例程 A（背景排程叫賣，fire-and-forget），返回後 caller 進 L1。"""
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
