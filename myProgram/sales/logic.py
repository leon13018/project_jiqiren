"""業務邏輯入口 facade（S1 v2，2026-05-25 A2-c 落地；W5 調度移入 SalesMachine）。

職責：
    - facade：組 callbacks dict + 持有 cart（唯一 cycle state）+ 建 SalesMachine 並啟動
    - 4 層狀態機主迴圈 / 跨層 cycle dispatch / cart invariant check（A4-c）已移入
      myProgram.sales.states.machine.SalesMachine（W5 State pattern）

設計約束：
    - 純單線程，無 threading / queue / 旗號（incremental-rebuild S1 階段）
    - 嚴格不 import 廠商 SDK（選項 C）
    - 對外動作 callback 注入（caller = myProgram.py 入口層）

各 run_? return shape（states 對外契約文檔）：
    - run_l1 → str | None ("L2" / None — 字串保留沿用，但語義 = "進 dialog"）
    - run_dialog → tuple[str, int]（next_state ∈ {"L4", "L1_enter_hawk"}, next_think_count）
    - run_l4 / run_l5 → tuple[str, int, int]（next_state, 0, 0 — 兩個 0 占位，保留 3-tuple shape）
"""

from myProgram.sales import cart as cart_module
from myProgram.sales.states.machine import SalesMachine


def run(
    *,
    print_terminal,
    read_terminal_key,
    speak,
    do_action,
    read_customer_input,
    sleep,
    tts_is_idle,
    exit_program,
    show_hawk_help,
    speak_and_wait=None,
    display=None,
) -> None:
    """S1 v2 主迴圈 facade：組 callbacks + 建 SalesMachine（L1 → dialog → L4 → L5 → L1 cycle）。

    L1 入口流程：
    - 首次進 L1：顯示主選單，商家選 1（叫賣）
    - 交易完成後續 L1：跳過主選單直接進 hawk（連續叫賣，2026-05-26 加）
      涵蓋 4 個出口：dialog reject / dialog timeout / L4 cancel / L5 完成
    """
    callbacks = dict(
        print_terminal=print_terminal,
        read_terminal_key=read_terminal_key,
        speak=speak,
        do_action=do_action,
        read_customer_input=read_customer_input,
        sleep=sleep,
        tts_is_idle=tts_is_idle,
        exit_program=exit_program,
        show_hawk_help=show_hawk_help,
        speak_and_wait=speak_and_wait,
        display=display,
    )
    return SalesMachine(callbacks=callbacks, cart=cart_module.new_cart()).run()
