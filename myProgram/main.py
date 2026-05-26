"""S1 v2 入口層 — 純單線程對話程式 wire-up（A3-d 落地）。

S1 範圍（incremental-rebuild 第 1 步）：
    - 無語音 / 無動作 / 無 UI / 無 threading
    - 純終端對話模擬，可端對端走 L1→L2→L3→L4→L5→子例程 A→L1 cycle
    - 所有對外動作以 [標記] 文字印出，方便閱讀流程

A3-d：callback 直接 wire（dict 展開傳 logic.run(**callbacks)），不預先包 Context dataclass。
A2-c：本檔不持有業務 state（cart / counters），全部由 logic.run 內部管理。

廠商 SDK 隔離：本檔 **S1 階段不 import 廠商 SDK**（do_action 已移除，S3+ 再加回）。
S3+ 才接 `from myProgram.vendor import ActionGroupControl as Act` 並 wire。

操作說明（S1 chat-driven trick）：
    - L1 hawk 模式：輸入 'c' → 模擬 OpenCV 偵測到顧客 → 下次 check 轉 L2
    - L2-L5 顧客輸入：空 Enter → 模擬 6 秒 timeout
    - 任何時刻按 'q' → L1 主迴圈呼叫 exit_program 退出
    - Ctrl+C → KeyboardInterrupt 退出
"""

import sys
import time

from myProgram.sales import logic
from myProgram.sales.constants import OPENCV_DWELL
from myProgram.sales.nlu import normalize_input


class _S1State:
    """S1 wire-up 共享 state（OpenCV 模擬狀態 — 'c' 鍵觸發）。"""

    def __init__(self):
        self.opencv_enabled = False
        self.opencv_dwell = 0.0  # 'c' 鍵 → 設為 OPENCV_DWELL+0.5，下次讀觸發 L2
        # mute 時間戳（2026-05-26 加）— 由 mute_opencv 設 time.monotonic() + seconds；
        # opencv_dwell_seconds 在 mute 期間強制回 0，即使 opencv_enabled=True 也擋偵測。
        # 這確保子例程 A 的 12s buffer 真實生效：hawk 重進 enable 後，12s 內偵測仍被吃掉，
        # 避免「同一顧客剛走又被馬上拉回 dialog」。
        self.opencv_mute_until = 0.0


def _build_callbacks(state: _S1State) -> dict:
    """建立 S1 chat-driven callback 集合（11 個）。
    （do_action 已於 P1 移除 — S1 stage 從未呼叫，S3+ 真接動作層再加回）
    """

    # === 終端 I/O ===
    def print_terminal(text):
        print(text)

    def show_hawk_help():
        """印叫賣模式操作提示（S1 wire-up — 給商家看的提示）。"""
        print(">>> [模擬提示] 叫賣模式只接受兩個鍵：'c' = 模擬 OpenCV 偵測顧客 → 轉 L2；'q' = 退出程式。其他輸入會被忽略。<<<")

    def read_terminal_key():
        """讀商家鍵盤輸入（嚴格匹配整段；多字元自動失配被 caller 忽略）。

        特殊 'c' 鍵（嚴格相等才觸發）：模擬 OpenCV 偵測到顧客 → 設 dwell ≥ OPENCV_DWELL。
        其他：回傳完整輸入（不截首字元）。caller 用 `key == "1"` / `"2"` / `"3"` / `"q"` /
        `"r"` 嚴格比對；像「123」/「3434」/「2543333」這類多字元亂打**自然不匹配任何
        單字元 menu key → 自動 ignored**（不再像舊版會截首字元誤進模式）。
        """
        try:
            raw = input("[商家] > ").strip().lower()
        except (UnicodeDecodeError, EOFError) as e:
            print(f"[系統] 輸入解析失敗（{type(e).__name__}），請重試")
            return ""
        raw = normalize_input(raw)  # 2026-05-26 P5 加：商家若用全形輸入法「１」也能對應到 "1"
        if raw == "c":
            state.opencv_dwell = OPENCV_DWELL + 0.5
            # 區分「mute 期間 'c' 被吃掉」vs「真的觸發 L2」訊息（2026-05-26 加；
            # 之前都印同一句「已自動觸發 L2」造成使用者按兩次以為應該觸發但沒反應的誤會）
            remaining = state.opencv_mute_until - time.monotonic()
            if remaining > 0:
                print(f"[模擬] 收到 'c'，但 opencv 還在 mute 期間（剩 {remaining:.1f}s）→ 本次 detection 被擋下，請等 mute 結束再按 'c'")
            else:
                print("[模擬] OpenCV 偵測到顧客 → 已自動觸發 L2（hawk loop 下次迭代立即 check opencv，無需再按鍵）")
            return ""  # 不返回有效鍵；由 L1 hawk 主迴圈下次 check opencv
        return raw  # post-P8（2026-05-26）：原 `raw[:1]` 會把「123」截為「1」誤進叫賣模式、「3434」截為「3」誤進客服。改回整段不截，依賴 caller `== "1"` 嚴格比對。

    def read_customer_input(timeout):
        """讀顧客輸入（語音模擬）。

        空 Enter → 模擬 timeout（return None）
        'q' → S1 wire-up 便利：直接退出程式（production 不會有人講「q」當顧客語音）
        其他 → 返回字串
        非 UTF-8 byte / EOF → 視為 timeout（return None），避免 Python input() raise
        """
        try:
            raw = input(f"[顧客 timeout={timeout}s，空 Enter=timeout / q=退出] > ").strip()
        except (UnicodeDecodeError, EOFError) as e:
            print(f"[系統] 輸入解析失敗（{type(e).__name__}），視為 timeout")
            return None
        raw = normalize_input(raw)  # 2026-05-26 P5 加：IO 邊界統一 normalize（長度上限 / 控制字元 / 全形數字）
        if raw == "q":
            print("[系統] 程式結束（顧客層 q 退出）")
            sys.exit(0)
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
        # mute 期間（time.monotonic() < mute_until）即使 enabled 也擋偵測
        # 2026-05-26 加：確保子例程 A 12s buffer 真實生效，避免剛走的顧客被馬上拉回
        if time.monotonic() < state.opencv_mute_until:
            return 0.0
        # 一次性消耗：回報後重置（避免持續觸發）
        if state.opencv_dwell >= OPENCV_DWELL:
            triggered = state.opencv_dwell
            state.opencv_dwell = 0.0
            return triggered
        return 0.0

    def mute_opencv(seconds):
        # 2026-05-25 補 S1 wire-up 暗坑：原本只印訊息不改 state，導致實機接 OpenCV 時
        # 子例程 A / L5 致謝期屏蔽全部失效。現在真實設 state 一致（無背景 timer，純設旗號）。
        # 2026-05-26 補：除 flag 外另記 mute_until 時間戳；opencv_dwell_seconds 在
        # mute 期間強制回 0，即使後續 opencv_enable() 把 flag 設回 True 也不會偵測，
        # 確保 buffer 真實生效（之前 hawk 重進 enable 馬上 override flag 的 bug）。
        state.opencv_enabled = False
        state.opencv_dwell = 0.0
        state.opencv_mute_until = time.monotonic() + seconds
        print(f"[opencv] mute {seconds}s（生效到 {seconds}s 後；期間 detection 全部回 0）")

    # === 對外動作 ===
    def speak(text):
        print(f"[語音] {text}")

    # === 時間 / 程式控制 ===
    def sleep(seconds):
        """S1 sleep：印訊息但不真阻塞（純單線程 chat-driven 無實際時序需求）。

        Why 不 time.sleep：S1 階段無真實 TTS 需要等播完、無真實 OpenCV mute 期間需要 tick；
        真 sleep 只會卡住主線程連商家 q 退出都送不進去（壞 UX）。S4+ 上 threading 時改
        worker thread sleep / timer fire-and-forget，主線程立即返回，sleep 期間 q 仍可送入。
        """
        print(f"[等待] {seconds}s（S1 跳過實際 sleep，立即返回）")

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
        "speak": speak,
        "read_customer_input": read_customer_input,
        "sleep": sleep,
        "schedule": schedule,
        "exit_program": exit_program,
        "show_hawk_help": show_hawk_help,
    }


def main():
    """S1 v2 入口。"""
    print("=" * 50)
    print("Project_01 互動式銷售輔助機器人 — S1 v2 模擬模式")
    print("（純單線程對話、無語音 / 動作 / OpenCV / 廠商 SDK）")
    print("=" * 50)
    print("操作小抄（S1 chat-driven 模擬）：")
    print("  [L1 商家層] 1=叫賣 / 2=待機 / 3=客服 / q=退出")
    print("    └ 進叫賣後按 'c' 模擬 OpenCV 偵測顧客 → 轉 L2 對話")
    print("    └ 進待機後按 'r' 回主選單（其他鍵無效）")
    print("    └ 進客服印電話後自動回主選單")
    print("  [L2-L5 顧客對話層] 打字=顧客語音回應 / 空 Enter=模擬 6s timeout")
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
