"""L1：商家模式選擇層（叫賣 / 待機 / 客服）。

對應規格書：resources/plans/業務程式邏輯規劃/L1.md

callback 集合：
    print_terminal / read_terminal_key / opencv_dwell_seconds / opencv_disable /
    opencv_enable / speak / exit_program / schedule
"""

from myProgram.sales.constants import (
    HAWK_SLOGANS,
    HAWK_INTERVAL,
    OPENCV_DWELL,
    L1_MENU_BANNER,
    L1_HAWK_ENTRY_PROMPT,
    L1_STANDBY_ENTRY_PROMPT,
    SERVICE_PHONE,
)


def run_l1(
    print_terminal,
    read_terminal_key,
    opencv_dwell_seconds,
    opencv_disable,
    opencv_enable,
    speak,
    exit_program,
    schedule,
    enter_hawk_immediately: bool = False,
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
        enter_hawk_immediately: True 時跳過主選單直接進叫賣模式（2026-05-26 加）。
            用途：logic.py 在 subroutine_a（dialog / L4 cancel / L5 後續緩衝）後設為 True
            → 連續叫賣不中斷，不顯示「請選擇模式：1/2/3」主選單。
            False（預設）= 首次進 L1 走原本的主選單流程。

    Returns:
        'L2' — 叫賣模式中 OpenCV 觸發轉 L2
        None — 程式終止（exit_program 被呼叫）
    """
    if enter_hawk_immediately:
        # subroutine_a 後續路徑：跳過主選單，直接進 hawk（連續叫賣不中斷）
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

    while True:
        # 防呆：主選單 / 客服都不該偵測 OpenCV（待機鏈路自己會 disable）
        # 每輪明示關閉一次，涵蓋「從子例程 A / dialog / L4 回來時 enabled 狀態漂移」
        # （2026-05-25 OpenCV 作用域規格修訂：只在叫賣模式才 enable）
        opencv_disable()

        # ---- 印選單 ----
        print_terminal(L1_MENU_BANNER)

        # ---- 讀使用者輸入 ----
        key = read_terminal_key()

        if key == "q":
            exit_program()
            return None
        elif key == "3":
            _run_l1_service(print_terminal, opencv_disable)
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


def _run_l1_service(print_terminal, opencv_disable) -> None:
    """鏈路 A — 客服模式：明示關 OpenCV → 印電話 → 返回讓主迴圈回選單。

    （2026-05-25 加 opencv_disable 參數：客服期間不偵測，防呆。）
    """
    opencv_disable()
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
            # 按 r 回主選單 — OpenCV 維持關閉
            # 2026-05-25 規格修訂：L1 主選單預設不偵測 OpenCV；只有商家選 1 進叫賣模式才啟動。
            # 避免「待機 → 回選單」自動開 OpenCV，違反「商家未明確選叫賣前不偵測」的直覺。
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
