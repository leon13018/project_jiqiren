"""S1 v2 入口層 — 純單線程對話程式 wire-up（A3-d 落地）。

S1 範圍（incremental-rebuild 第 1 步）：
    - 無語音 / 無動作 / 無 UI / 無 threading
    - 純終端對話模擬，可端對端走 L1→L2→L3→L4→L5→子例程 A→L1 cycle
    - 所有對外動作以 [標記] 文字印出，方便閱讀流程

A3-d：callback 直接 wire（dict 展開傳 logic.run(**callbacks)），不預先包 Context dataclass。
A2-c：本檔不持有業務 state（cart / counters），全部由 logic.run 內部管理。

廠商 SDK 隔離：S3（2026-05-27 加）restore do_action callback — lazy import
`from myProgram.vendor import ActionGroupControl as Act` 在 do_action 函式內，
頂層仍不 import 廠商 SDK，保 Windows pytest 兼容性（對齊 speak callback pattern）。

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
    """建立 chat-driven callback 集合（13 個，2026-05-27 S3 起加 do_action）。"""

    # === 終端 I/O ===
    def print_terminal(text):
        # B21（Wave 7b）：原本這裡比對 text == L1_HAWK_ENTRY_PROMPT 偵測「剛進 hawk」
        # 時加印操作提示，緊耦合常數值。改由獨立 show_hawk_help callback 顯式呼叫
        # （見下方），這裡只剩純印字。
        print(text)

    def show_hawk_help():
        """印叫賣模式操作提示（S1 wire-up — 給商家看的提示）。

        B21（Wave 7b）：取代原 print_terminal 內 if text == L1_HAWK_ENTRY_PROMPT
        magic string 偵測。caller（l1._run_l1_hawk）在印完 entry prompt 後顯式呼叫。
        """
        print(">>> [模擬提示] 叫賣模式只接受兩個鍵：'c' = 模擬 OpenCV 偵測顧客 → 轉 L2；'q' = 退出程式。其他輸入會被忽略。<<<")

    def read_terminal_key(timeout=None):
        """讀商家鍵盤輸入（嚴格匹配整段；多字元自動失配被 caller 忽略）。

        S6（incremental-rebuild 第 6 步）改造：原本 `input()` 阻塞 → 改透過
        `input_reader.read(timeout)` 從 daemon reader thread 的 queue 取。

        **預設 timeout=None（無限阻塞等鍵）**：適用主選單 / standby 兩個 caller
        — 它們期待「使用者按鍵才繼續」語意，busy polling 會每 100ms 重印 banner
        造成洗版（2026-05-28 Pi 實機踩到的 hot fix；之前 default 設 0.1 是設計錯誤）。
        hawk 主迴圈必須跟 OpenCV polling 並行，**caller 顯式傳 timeout=0.1**
        走 polling cadence（見 l1._run_l1_hawk）。

        timeout 內無輸入 → input_reader 返回 None → 本函式回 ""（對齊既有「無輸入」
        語意，caller 走 fallback；舊 EOFError 路徑也是回 ""，行為相容）。

        特殊 'c' 鍵（嚴格相等才觸發）：模擬 OpenCV 偵測到顧客 → 設 dwell ≥ OPENCV_DWELL。
        其他：回傳完整輸入（不截首字元）。caller 用 `key == "1"` / `"2"` / `"3"` / `"q"` /
        `"r"` 嚴格比對；像「123」/「3434」/「2543333」這類多字元亂打**自然不匹配任何
        單字元 menu key → 自動 ignored**（不再像舊版會截首字元誤進模式）。
        """
        # Lazy import：對齊 tts.speak / action.do 的 lazy import pattern；
        # input_reader 雖無 vendor 依賴（純 stdlib），對齊結構讓 Windows pytest
        # 經 `from myProgram.main import _build_callbacks` 不會強制啟動 reader thread。
        from myProgram import input_reader
        raw = input_reader.read(timeout)
        if raw is None:
            # timeout 內無輸入 → 回空字串（caller 走 fallback；無輸入語意對齊舊版）
            return ""
        raw = raw.strip().lower()
        raw = normalize_input(raw)  # 2026-05-26 P5 加：商家若用全形輸入法「１」也能對應到 "1"
        if raw == "c":
            # 2026-05-27 改：mute 期間 'c' 不設 dwell（嚴格行為，對齊 print 字面）。
            # 舊版會在 mute 期間也設 state.opencv_dwell = OPENCV_DWELL+0.5 殘留到
            # mute 結束 → opencv_dwell_seconds 自動觸發 L2，與 print「擋下，請等 mute
            # 結束再按 'c'」訊息矛盾。現在 mute 內 'c' 完全忽略，商家必須等 mute
            # 結束後再按一次才會觸發 L2。
            remaining = state.opencv_mute_until - time.monotonic()
            if remaining > 0:
                print(f"[模擬] 收到 'c'，但 opencv 還在 mute 期間（剩 {remaining:.1f}s）→ 已忽略，請等 mute 結束後再按 'c' 才會觸發 L2")
            else:
                state.opencv_dwell = OPENCV_DWELL + 0.5
                print("[模擬] OpenCV 偵測到顧客 → 已自動觸發 L2（hawk loop 下次迭代立即 check opencv，無需再按鍵）")
            return ""  # 不返回有效鍵；由 L1 hawk 主迴圈下次 check opencv
        return raw  # post-P8（2026-05-26）：原 `raw[:1]` 會把「123」截為「1」誤進叫賣模式、「3434」截為「3」誤進客服。改回整段不截，依賴 caller `== "1"` 嚴格比對。

    def read_customer_input(timeout):
        """讀顧客輸入（語音模擬，非阻塞 timeout）。

        S6（incremental-rebuild 第 6 步）改造：原本 `input()` 阻塞使得 L4
        60s wall-clock 預算實際沒在跑（input 不支援 timeout） → 改透過
        `input_reader.read(timeout)` 從 daemon reader thread 的 queue 取。
        現在 timeout 真的會生效，L4 預算耗盡可真正 forced exit。

        timeout 內無輸入（顧客沒打字 / 沒掃碼）→ input_reader 返回 None →
        本函式回 None（既有 timeout 語意）。

        'q' → S1 wire-up 便利：直接退出程式（production 不會有人講「q」當顧客語音）
        其他 → 返回字串
        """
        # Lazy import：對齊 read_terminal_key / tts.speak / action.do 的 lazy import pattern。
        from myProgram import input_reader
        raw = input_reader.read(timeout)
        if raw is None:
            return None  # timeout（既有語意）
        raw = raw.strip()
        raw = normalize_input(raw)  # 2026-05-26 P5 加：IO 邊界統一 normalize（長度上限 / 控制字元 / 全形數字）
        # TODO(S2+): 真 STT 接入後移除此「q 退出」處理 — S1 chat-driven 為了
        # 商家測試方便，顧客輸入路徑也允許「q」直接退出程式；production 顧客是
        # 語音 STT，理論上不會傳「q」，但 STT 把語音「Q」/「kiu」誤識別仍可觸發。
        # S2+ 接入真 STT 時刪掉此分支（顧客層 q 退出僅是 S1 chat-driven 便利）。
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
        # S2：call tts.speak（同步阻塞至播完）；tts.speak 內已印 [語音] xxx，這裡不重複印
        # Lazy import：tts.py 頂層 `import edge_tts` 是 fail-fast（缺套件直接 ImportError）；
        # 放這裡讓 Windows 端 pytest 可經 `from myProgram.main import _build_callbacks` 收
        # 到 main 而不觸發 edge_tts import — Pi 端啟動後 L1 hawk entry 第一次 speak 立即
        # 觸發 import edge_tts，缺套件仍 fail-fast，不違反 noisy 原則。
        from myProgram import tts
        tts.speak(text)

    def do_action(name):
        """S5 非阻塞動作 callback：lazy import action 模組 + enqueue 立即返回。

        對齊 speak callback 的 lazy import pattern — action 模組頂層雖無 vendor
        import，但 module-level 建 worker singleton 會啟動 daemon thread；放函式
        內讓 Windows pytest 可 import _build_callbacks 不觸發 worker 啟動。

        對比 S3 同步版：對外 signature 不變（接 name、回 None），但行為從
        「阻塞至動作播完（2-5 秒）」改為「立即返回（背景 worker 排隊播）」—
        動作 + 語音可真正並行（S3 主線程被 runAction 卡死的問題解除）。

        Args:
            name: 動作組名（對應 /home/pi/TonyPi/ActionGroups/<name>.d6a）
                從 myProgram.sales.constants.actions 取常數，不寫死字串。
        """
        from myProgram import action  # lazy（避免 import _build_callbacks 觸發 worker start）
        action.do(name)  # action.do 內自己印 [動作] xxx + enqueue（不阻塞）

    # === 時間 / 程式控制 ===
    def sleep(seconds):
        """阻塞 seconds 秒（單線程同步阻塞 — S2 起恢復 real time.sleep）。

        實作 L5 規格意圖：thanks 後等 THANK_DELAY=3s 給顧客轉身離開的禮貌間隔，
        避免「謝謝光臨」剛播完就立刻接「歡迎光臨」叫賣下個顧客造成擁擠感。

        歷史：S1 階段曾改為 print no-op + 立即返回，當時 docstring 寫「真 sleep
        會卡住主線程連 q 退出都送不進去」。**S2 同步阻塞 TTS 接入後該前提已失效**
        — speak() 本身就同步阻塞主線程到播完（典型 2-4s），TTS 阻塞期間 q 也送
        不進來，sleep 阻塞同等狀況、未新增副作用。S4+ 上 threading 時可改 worker
        thread sleep 不阻塞主迴圈。
        """
        print(f"[等待] {seconds}s")
        time.sleep(seconds)

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
        "do_action": do_action,
        "read_customer_input": read_customer_input,
        "sleep": sleep,
        "schedule": schedule,
        "exit_program": exit_program,
        "show_hawk_help": show_hawk_help,
    }


def main():
    """S1 v2 入口。

    S6（2026-05-28）起 stdin 由 `myProgram.input_reader` daemon thread 透過
    `sys.stdin.buffer.readline()` 拿 bytes 自己 `decode(errors="replace")`，
    繞過 TextIOWrapper buffer 邏輯 → 徹底消除舊版 reconfigure hack 處理的
    「partial multibyte 殘留」bug class（2026-05-27 Pi「刮刮樂冰紅茶」於 0xe5
    raise「invalid continuation byte」案例）。
    """
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
    finally:
        # S4：程式退出時 terminate 當前播放中的 mpg123 + 清空 queue，避免
        # 「程式結束了但 mpg123 還在播完最後一段音檔」（user S4 訴求 #3）。
        # Lazy import 對齊現有 speak callback 的 lazy import pattern — Windows
        # pytest 環境無 edge_tts,此 path 走進來時 import 會 ImportError,swallow
        # 即可（finally 內不該因 cleanup 失敗反過來污染主流程）。
        try:
            from myProgram import tts
            tts.shutdown()
        except ImportError:
            pass  # Windows / pytest 無 edge_tts，無 tts module 可用
        # S5：程式退出時清 action queue + 守衛呼叫 Act.stopAction（sticky 旗號
        # 處理見 [[vendor-stop-action-sticky]] memory）。跟 tts.shutdown 對稱
        # — Windows pytest 環境無 vendor SDK（pigpio / RPi.GPIO 等 Pi-only），
        # import action 觸發 module-level _worker 建立時若意外 reach 到 vendor
        # import 會 ImportError；swallow 即可（finally 內不該因 cleanup 失敗
        # 反過來污染主流程）。實際上 action 頂層不 import vendor，worker thread
        # 內第一次 dispatch 才 import — 純 import action 模組本身在 Windows 也
        # 不會 ImportError；但保留 try/except 跟 tts.shutdown 結構對稱、防呆。
        try:
            from myProgram import action
            action.shutdown()
        except ImportError:
            pass  # Windows / pytest 無 vendor SDK，無 action module 可用
        # S6：程式退出時清 input_reader queue 殘留（對齊 tts/action shutdown 對稱性）。
        # input_reader 純 stdlib（queue / threading / sys），理論不會 ImportError；
        # 保留 try/except 跟 tts/action shutdown 結構對稱、防呆。daemon=True 隨主程式
        # 退出自動 die，不需 join。
        try:
            from myProgram import input_reader
            input_reader.shutdown()
        except ImportError:
            pass  # 理論不會發生（純 stdlib），結構對稱用
        # 2026-05-28 hot fix：強退避開 daemon thread 卡 stdin readline syscall
        # 害 Python finalizer hang 的問題。
        #
        # 背景：input_reader daemon thread 阻塞在 sys.stdin.buffer.readline()
        # 的 C-level kernel syscall。input_reader.shutdown 已嘗試 sys.stdin.close()
        # 觸發 ValueError unblock readline，但 Linux kernel close(fd) 不會 wake
        # 已阻塞在 read(fd) 的 thread（implementation-defined 行為）— next read
        # 才 EBADF。結果：main() return 後 Python finalizer 卡在 stdin lock 互動，
        # user 必須按鍵 unblock readline syscall 才退出（Pi 2026-05-28 實機踩到）。
        #
        # 解法：所有 worker shutdown 已跑完（tts terminate mpg123 + action stopAction
        # + input_reader clear queue + close stdin），可安全 os._exit(0) 強退 process。
        # 跳過 Python finalizer（atexit / module finalize / daemon thread join）對
        # 本專案無副作用 — 無 logging flush / 無 pickle save / daemon=True 隨 process
        # die 是設計目的。
        import os
        os._exit(0)


if __name__ == "__main__":
    main()
