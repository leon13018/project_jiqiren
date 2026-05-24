"""S1 v2 入口層 — 純單線程對話程式 wire-up（A3-d 落地）。

S1 範圍（incremental-rebuild 第 1 步）：
    - 無語音 / 無動作 / 無 UI / 無 threading
    - 純終端對話模擬，可端對端走 L1→L2→L3→L4→L5→子例程 A→L1 cycle
    - 所有對外動作以 [標記] 文字印出，方便閱讀流程

A3-d：callback 直接 wire（dict 展開傳 logic.run(**callbacks)），不預先包 Context dataclass。
A2-c：本檔不持有業務 state（cart / counters），全部由 logic.run 內部管理。

廠商 SDK 隔離：本檔 **S1 階段不 import 廠商 SDK**（do_action 是 stub）。
S3+ 才接 `from myProgram import ActionGroupControl as Act` 並 wire。

操作說明（S1 chat-driven trick）：
    - L1 hawk 模式：輸入 'c' → 模擬 OpenCV 偵測到顧客 → 下次 check 轉 L2
    - L2-L5 顧客輸入：空 Enter → 模擬 6 秒 timeout
    - 任何時刻按 'q' → L1 主迴圈呼叫 exit_program 退出
    - Ctrl+C → KeyboardInterrupt 退出
"""

import sys

from myProgram.sales import logic
from myProgram.sales.constants import OPENCV_DWELL


class _S1State:
    """S1 wire-up 共享 state（OpenCV 模擬狀態 — 'c' 鍵觸發）。"""

    def __init__(self):
        self.opencv_enabled = False
        self.opencv_dwell = 0.0  # 'c' 鍵 → 設為 OPENCV_DWELL+0.5，下次讀觸發 L2


def _build_callbacks(state: _S1State) -> dict:
    """建立 S1 chat-driven callback 集合（12 個）。"""

    # === 終端 I/O ===
    def print_terminal(text):
        print(text)

    def read_terminal_key():
        """讀商家鍵盤輸入（一個字元）。

        特殊 'c' 鍵：模擬 OpenCV 偵測到顧客 → 設 dwell ≥ OPENCV_DWELL，下次 check 觸發 L2。
        """
        raw = input("[商家] 請輸入鍵（1/2/3/q）> ").strip().lower()
        if raw == "c":
            state.opencv_dwell = OPENCV_DWELL + 0.5
            print("[模擬] OpenCV 偵測到顧客（dwell ≥ 1.5s），下次 check 將轉 L2")
            return ""  # 不返回有效鍵；由 L1 hawk 主迴圈下次 check opencv
        return raw[:1] if raw else ""

    def read_customer_input(timeout):
        """讀顧客輸入（語音模擬）。

        空 Enter → 模擬 timeout（return None）；其他 → 返回字串。
        """
        raw = input(f"[顧客 timeout={timeout}s，空 Enter=timeout] > ").strip()
        return None if raw == "" else raw

    # === OpenCV 模擬 ===
    def opencv_enable():
        state.opencv_enabled = True
        print("[opencv] 已開啟偵測")

    def opencv_disable():
        state.opencv_enabled = False
        state.opencv_dwell = 0.0
        print("[opencv] 已關閉偵測")

    def opencv_dwell_seconds():
        if not state.opencv_enabled:
            return 0.0
        # 一次性消耗：回報後重置（避免持續觸發）
        if state.opencv_dwell >= OPENCV_DWELL:
            triggered = state.opencv_dwell
            state.opencv_dwell = 0.0
            return triggered
        return 0.0

    def mute_opencv(seconds):
        print(f"[opencv] mute {seconds}s（S1 不真實計時）")

    def unmute_opencv():
        print("[opencv] unmute")

    # === 對外動作 ===
    def speak(text):
        print(f"[語音] {text}")

    def do_action(name):
        print(f"[動作] {name}")

    # === 時間 / 程式控制 ===
    def schedule(seconds, fn):
        """S1 schedule：不真排程，僅印警告（單線程不能背景跑）。"""
        print(f"[schedule] 排程 {seconds}s 後執行 {fn.__name__}（S1 不真排程，立即跳過）")

    def exit_program():
        print("[系統] 程式結束")
        sys.exit(0)

    return {
        "print_terminal": print_terminal,
        "read_terminal_key": read_terminal_key,
        "opencv_dwell_seconds": opencv_dwell_seconds,
        "opencv_disable": opencv_disable,
        "opencv_enable": opencv_enable,
        "mute_opencv": mute_opencv,
        "unmute_opencv": unmute_opencv,
        "speak": speak,
        "do_action": do_action,
        "read_customer_input": read_customer_input,
        "schedule": schedule,
        "exit_program": exit_program,
    }


def main():
    """S1 v2 入口。"""
    print("=" * 50)
    print("Project_01 互動式銷售輔助機器人 — S1 v2 模擬模式")
    print("（純單線程對話、無語音 / 動作 / OpenCV / 廠商 SDK）")
    print("=" * 50)

    state = _S1State()
    callbacks = _build_callbacks(state)

    try:
        logic.run(**callbacks)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print("\n[系統] 中斷退出")


if __name__ == "__main__":
    main()
