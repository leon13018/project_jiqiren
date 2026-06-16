"""入口層 — 終端對話程式 wire-up（TerminalSim callback 集 + 主迴圈）。

純單線程對話模擬（語音 / 動作 / input 由各 worker 背景 thread 處理），可端對端
走 L1→L2→L3→L4→L5→子例程 A→L1 cycle；所有對外動作以 [標記] 文字印出。

callback wire 方式：`TerminalSim(state).callbacks()` 回傳 dict，展開傳
`logic.run(**callbacks)`，不預先包 Context dataclass；本檔不持有業務 state
（cart / counters），全部由 logic.run 內部管理。

廠商 SDK 隔離：do_action / speak 等 callback 內 lazy import（`from myProgram import
action` / `tts`），頂層不 import 廠商 SDK 也不 import worker 模組 → Windows pytest
可經 `from myProgram.main import _build_callbacks` 收到 main 而不觸發 edge_tts /
vendor import 或 worker thread 啟動。

操作說明（chat-driven trick）：
    - L1 hawk 模式：輸入 'c' → 模擬 OpenCV 偵測到顧客 → 下次 check 轉 L2
    - L2-L5 顧客輸入：空 Enter → 模擬 timeout
    - 任何時刻按 'q' → L1 主迴圈呼叫 exit_program 退出
    - Ctrl+C → KeyboardInterrupt 退出
"""

import math
import sys
import time

from myProgram.sales import logic
from myProgram.sales.constants import OPENCV_DWELL
from myProgram.sales.nlu import normalize_input


class _S1State:
    """wire-up 共享 state（OpenCV 模擬狀態 — 'c' 鍵觸發）。"""

    def __init__(self):
        self.opencv_enabled = False
        self.opencv_dwell = 0.0  # 'c' 鍵 → 設為 OPENCV_DWELL+0.5，下次讀觸發 L2
        # mute 時間戳 — 由 mute_opencv 設 time.monotonic() + seconds；
        # opencv_dwell_seconds 在 mute 期間強制回 0，即使 opencv_enabled=True 也擋偵測。
        # 這確保子例程 A 的 buffer 真實生效：hawk 重進 enable 後，buffer 內偵測仍被吃掉，
        # 避免「同一顧客剛走又被馬上拉回 dialog」。
        self.opencv_mute_until = 0.0


def _tick_countdown(total: float, label: str, wait_tick):
    """每秒對齊整秒邊界倒數印 `{label} = N`；wait_tick(seconds) 回非 None 即中斷並回傳。

    統一 read_customer_input（可被輸入打斷）/ sleep（跑滿不可打斷）兩個倒數迴圈：
    差異只在注入的 wait_tick（input_reader.read 可中斷 / time.sleep 恆回 None）。
    每秒對齊整秒邊界，time 用 module-global lookup（測試 patch 全域時鐘 seam）。
    """
    deadline = time.monotonic() + total
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        ticks = math.ceil(remaining)
        print(f"{label} = {ticks}")
        got = wait_tick(remaining - (ticks - 1))
        if got is not None:
            return got


class TerminalSim:
    """終端模擬 callback 集：14 個 bound methods 餵 logic.run(**callbacks())。

    持 _S1State（OpenCV 模擬狀態）；各 method 對應一個對外 callback。method 內的
    lazy import（tts / action / input_reader）原樣保留 — Windows pytest seam。
    """

    def __init__(self, state: _S1State) -> None:
        self._state = state

    # === 終端 I/O ===
    def print_terminal(self, text):
        # 純印字（叫賣模式操作提示已抽 show_hawk_help callback 顯式呼叫，不在此偵測 magic string）。
        print(text)

    def show_hawk_help(self):
        """印叫賣模式操作提示（給商家看的提示）。

        caller（l1._run_l1_hawk）在印完 entry prompt 後顯式呼叫，取代原 print_terminal
        內 `if text == L1_HAWK_ENTRY_PROMPT` magic string 偵測（解耦常數值）。
        """
        print(">>> [模擬提示] 叫賣模式只接受兩個鍵：'c' = 模擬 OpenCV 偵測顧客 → 轉 L2；'q' = 退出程式。其他輸入會被忽略。<<<")

    def read_terminal_key(self, timeout=None):
        """讀商家鍵盤輸入（嚴格匹配整段；多字元自動失配被 caller 忽略）。

        透過 `input_reader.read(timeout)` 從 daemon reader thread 的 queue 取（非阻塞）。

        **預設 timeout=None（無限阻塞等鍵）**：適用主選單 / standby 兩個 caller
        — 它們期待「使用者按鍵才繼續」語意，busy polling 會每 100ms 重印 banner
        造成洗版。hawk 主迴圈必須跟 OpenCV polling 並行，**caller 顯式傳 timeout=0.1**
        走 polling cadence（見 l1._run_l1_hawk）。

        timeout 內無輸入 → input_reader 返回 None → 本函式回 ""（對齊既有「無輸入」
        語意，caller 走 fallback）。

        特殊 'c' 鍵（嚴格相等才觸發）：模擬 OpenCV 偵測到顧客 → 設 dwell ≥ OPENCV_DWELL。
        其他：回傳完整輸入（不截首字元）。caller 用 `key == "1"` / `"2"` / `"3"` / `"q"` /
        `"r"` 嚴格比對；像「123」/「3434」/「2543333」這類多字元亂打**自然不匹配任何
        單字元 menu key → 自動 ignored**。
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
        raw = normalize_input(raw)  # 商家若用全形輸入法「１」也能對應到 "1"
        if raw == "c":
            # mute 期間 'c' 不設 dwell（嚴格行為，對齊 print 字面）：否則設 dwell 會殘留
            # 到 mute 結束 → opencv_dwell_seconds 自動觸發 L2，與 print「擋下，請等 mute
            # 結束再按 'c'」訊息矛盾。mute 內 'c' 完全忽略，商家須等 mute 結束後再按一次。
            remaining = self._state.opencv_mute_until - time.monotonic()
            if remaining > 0:
                print(f"[模擬] 收到 'c'，但 opencv 還在 mute 期間（剩 {remaining:.1f}s）→ 已忽略，請等 mute 結束後再按 'c' 才會觸發 L2")
            else:
                self._state.opencv_dwell = OPENCV_DWELL + 0.5
                print("[模擬] OpenCV 偵測到顧客 → 已自動觸發 L2（hawk loop 下次迭代立即 check opencv，無需再按鍵）")
            return ""  # 不返回有效鍵；由 L1 hawk 主迴圈下次 check opencv
        return raw  # 整段不截（依賴 caller `== "1"` 嚴格比對）；截首字元會把「123」誤進叫賣模式

    def read_customer_input(self, timeout):
        """讀顧客輸入（語音模擬，非阻塞 timeout）。

        透過 `input_reader.read(timeout)` 從 daemon reader thread 的 queue 取；timeout
        真的會生效（input() 不支援 timeout），L4 60s wall-clock 預算耗盡可真正 forced exit。

        read 前先 `tts.wait_idle()` 等 TTS 播完才開始倒數（避免顧客還在聽 prompt 就被
        扣秒）：對 wall-clock budget caller 是 no-op（speak_and_wait 後 pending=0 immediate）；
        對非 budget caller 自動 cover TTS 等待（不必逐個 speak 改 speak_and_wait）。

        timeout 內無輸入（顧客沒打字 / 沒掃碼）→ input_reader 返回 None → 本函式回 None。
        倒數期間每秒 print `timeout = N`（語音播完瞬間印第一個 = ceil(timeout)）；對既有
        sales/ caller 行為透明（回值 / timeout 語意完全保留）。

        'q' → wire-up 便利：直接退出程式（production 顧客是語音 STT，不會傳「q」）。
        """
        # 等 TTS 播完才開始倒數（max_wait=30s 防 synth/mpg123 hang 永久阻塞）。
        # Lazy import 對齊既有 speak callback pattern（Windows pytest 不觸發 edge_tts import）。
        from myProgram import stt
        # STT Phase 2 v2：進場先預熱 Deepgram 連線（只連線、不送音訊；播放期送 KeepAlive
        # 維持）→ wait_idle 後 arm 才開始送顧客音訊，省 ws 連線等待、且機器人聲不進辨識。
        stt.prewarm()
        from myProgram import tts
        tts.wait_idle()
        from myProgram import input_reader

        # timeout is None / <= 0 不適用倒數（read_customer_input caller 不會傳；守備性
        # fallback 走原 single read 保證向後相容）。否則走 _tick_countdown：每秒對齊
        # 整秒邊界印 `timeout = N`，input_reader.read 拿到 input 即中斷回傳，deadline
        # 耗盡回 None。
        # STT Phase 2 v2：TTS 播完才 arm（開始送音訊 go-live；連線已預熱，零等待）。
        # finally 保證三條路徑（拿到輸入 / timeout / 'q' sys.exit）皆收麥。
        stt.arm()
        try:
            if timeout is None or timeout <= 0:
                raw = input_reader.read(timeout)
            else:
                raw = _tick_countdown(timeout, "timeout", input_reader.read)
        finally:
            stt.disarm()
        if raw is None:
            return None  # timeout（既有語意）
        raw = raw.strip()
        raw = normalize_input(raw)  # IO 邊界統一 normalize（長度上限 / 控制字元 / 全形數字）
        # wire-up 便利：顧客輸入路徑也允許「q」直接退出程式（production 顧客是語音
        # STT，理論不會傳「q」，但 STT 把語音「Q」/「kiu」誤識別仍可觸發）。
        if raw == "q":
            print("[系統] 程式結束（顧客層 q 退出）")
            sys.exit(0)
        return None if raw == "" else raw

    # === OpenCV 模擬 ===
    def opencv_enable(self):
        self._state.opencv_enabled = True
        print("[opencv] 已開啟偵測")

    def opencv_disable(self):
        self._state.opencv_enabled = False
        self._state.opencv_dwell = 0.0
        print("[opencv] 已關閉偵測")

    def opencv_dwell_seconds(self):
        if not self._state.opencv_enabled:
            return 0.0
        # mute 期間（time.monotonic() < mute_until）即使 enabled 也擋偵測，
        # 確保子例程 A buffer 真實生效，避免剛走的顧客被馬上拉回。
        if time.monotonic() < self._state.opencv_mute_until:
            return 0.0
        # 一次性消耗：回報後重置（避免持續觸發）
        if self._state.opencv_dwell >= OPENCV_DWELL:
            triggered = self._state.opencv_dwell
            self._state.opencv_dwell = 0.0
            return triggered
        return 0.0

    def mute_opencv(self, seconds):
        # 真實設 state（無背景 timer，純設旗號）：除 flag 外另記 mute_until 時間戳；
        # opencv_dwell_seconds 在 mute 期間強制回 0，即使後續 opencv_enable() 把 flag
        # 設回 True 也不會偵測，確保 buffer 真實生效（避免 hawk 重進 enable 馬上 override
        # flag → 子例程 A / L5 致謝期屏蔽失效）。
        self._state.opencv_enabled = False
        self._state.opencv_dwell = 0.0
        self._state.opencv_mute_until = time.monotonic() + seconds
        print(f"[opencv] mute {seconds}s（生效到 {seconds}s 後；期間 detection 全部回 0）")

    # === 對外動作 ===
    def speak(self, text):
        # call tts.speak（非阻塞 enqueue）；tts.speak 內已印 [語音] xxx，這裡不重複印。
        # Lazy import：tts.py 頂層 `import edge_tts` 是 fail-fast（缺套件直接 ImportError）；
        # 放這裡讓 Windows 端 pytest 可經 `from myProgram.main import _build_callbacks` 收到
        # main 而不觸發 edge_tts import — Pi 端 L1 hawk entry 第一次 speak 立即觸發 import。
        from myProgram import tts
        tts.speak(text)

    def speak_and_wait(self, text):
        """同步阻塞 TTS — 給 wall-clock budget pattern caller 用。

        相比 speak（非阻塞 enqueue）：阻塞至 TTS 完整播完才 return，讓 caller 之後
        算 deadline = monotonic + N 時，N 秒 budget 不被 TTS 播放時間吃掉。

        Wire-up 範圍（wall-clock budget pattern 共 3 處）：
            - sales/states/_cancel_confirm.py: speak CANCEL_CONFIRM_PROMPT
            - sales/states/l2_l3_dialog.py: DialogSession.c2_second_stage() speak warning
            - sales/states/l4.py: run_l4 entry speak total prompt

        Lazy import 對齊既有 speak callback pattern。
        """
        from myProgram import tts
        tts.speak_and_wait(text)

    def do_action(self, name):
        """非阻塞動作 callback：lazy import action 模組 + enqueue 立即返回。

        對齊 speak callback 的 lazy import pattern — action 模組頂層雖無 vendor import，
        但 module-level 建 worker singleton 會啟動 daemon thread；放函式內讓 Windows
        pytest 可 import _build_callbacks 不觸發 worker 啟動。

        行為：立即返回（背景 worker 排隊播）— 動作 + 語音可真正並行。

        Args:
            name: 動作組名（對應 /home/pi/TonyPi/ActionGroups/<name>.d6a）
                從 myProgram.sales.constants.actions 取常數，不寫死字串。
        """
        from myProgram import action  # lazy（避免 import _build_callbacks 觸發 worker start）
        action.do(name)  # action.do 內自己印 [動作] xxx + enqueue（不阻塞）

    # === 時間 / 程式控制 ===
    def sleep(self, seconds):
        """阻塞 seconds 秒（單線程同步阻塞）。

        實作 L5 規格意圖：thanks 後等 THANK_DELAY=3s 給顧客轉身離開的禮貌間隔，
        避免「謝謝光臨」剛播完就立刻接「歡迎光臨」叫賣下個顧客造成擁擠感。

        sleep 前先 `tts.wait_idle()` 等 TTS 播完才開始倒數（對齊 read_customer_input
        的 wait-then-count pattern）：解 latent bug — speak 非阻塞 + do_action 非阻塞 →
        sleep(3) 立即倒數 → 顧客 effective 離開時間 ~1s 而非規格 3s。只等 TTS 不等
        do_action — 揮手動作可跟 3s 禮貌間隔並行（regular UX）。

        倒數每秒印 `wait = N`（格式用 `wait` 而非 `timeout` 區分語意：sleep 不可被打斷，
        read_customer_input 可被輸入打斷）。每秒對齊整秒邊界，time.sleep 不浮點漂移。
        """
        # 等 TTS 播完才開始倒數（規格 3s「禮貌間隔」生效）。
        # Lazy import 對齊既有 speak / read_customer_input callback pattern。
        from myProgram import tts
        tts.wait_idle()
        # seconds is None / <= 0 fallback：no-op（向後相容；理論上 sleep caller 不會傳）。
        # 否則走 _tick_countdown：每秒對齊整秒邊界印 `wait = N`，time.sleep 注入版恆回
        # None → 跑滿不可中斷。
        if seconds is None or seconds <= 0:
            return
        _tick_countdown(seconds, "wait", lambda s: time.sleep(s))

    def schedule(self, seconds, fn):
        """不真排程，僅印警告（單線程不能背景跑）。"""
        print(f"[schedule] 排程 {seconds}s 後執行 {fn.__name__}（不真排程，立即跳過）")

    def exit_program(self):
        print("[系統] 程式結束")
        sys.exit(0)

    def callbacks(self) -> dict:
        """回傳 callback dict（14 鍵，餵 logic.run(**callbacks)）；值為 bound methods。"""
        return {
            "print_terminal": self.print_terminal,
            "read_terminal_key": self.read_terminal_key,
            "opencv_dwell_seconds": self.opencv_dwell_seconds,
            "opencv_disable": self.opencv_disable,
            "opencv_enable": self.opencv_enable,
            "mute_opencv": self.mute_opencv,
            "speak": self.speak,
            "speak_and_wait": self.speak_and_wait,
            "do_action": self.do_action,
            "read_customer_input": self.read_customer_input,
            "sleep": self.sleep,
            "schedule": self.schedule,
            "exit_program": self.exit_program,
            "show_hawk_help": self.show_hawk_help,
        }


def _build_callbacks(state: _S1State) -> dict:
    """建立 chat-driven callback 集合（facade — 委派 TerminalSim）。"""
    return TerminalSim(state).callbacks()


def main():
    """入口。

    stdin 由 `myProgram.input_reader` daemon thread 透過 `sys.stdin.buffer.readline()`
    拿 bytes 自己 `decode(errors="replace")`，繞過 TextIOWrapper buffer 邏輯 → 消除
    「partial multibyte 殘留」bug class（曾於 0xe5 byte raise「invalid continuation byte」）。
    """
    print("=" * 50)
    print("Project_01 互動式銷售輔助機器人 — 模擬模式")
    print("（單線程對話 + 背景 worker 處理語音 / 動作 / input）")
    print("=" * 50)
    print("操作小抄（chat-driven 模擬）：")
    print("  [L1 商家層] 1=叫賣 / 2=待機 / 3=客服 / q=退出")
    print("    └ 進叫賣後按 'c' 模擬 OpenCV 偵測顧客 → 轉 L2 對話")
    print("    └ 進待機後按 'r' 回主選單（其他鍵無效）")
    print("    └ 進客服印電話後自動回主選單")
    print("  [L2-L5 顧客對話層] 打字=顧客語音回應 / 空 Enter=模擬 timeout")
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
        # 程式退出 cleanup：三個 worker 各自 shutdown（tts terminate mpg123 + drain；
        # action 守衛 stopAction + drain；input_reader drain queue）。
        # Lazy import + swallow ImportError：finally 內不該因 cleanup 失敗反過來污染
        # 主流程；Windows pytest 環境無 edge_tts / vendor SDK，import 可能 ImportError。
        import importlib
        for name in ("stt", "tts", "action", "input_reader"):
            try:
                importlib.import_module(f"myProgram.{name}").shutdown()
            except ImportError:
                pass
        # 強退避開 daemon thread 卡 stdin readline syscall 害 Python finalizer hang
        # 的問題：input_reader daemon thread 阻塞在 sys.stdin.buffer.readline() 的
        # C-level kernel syscall，main() return 後 Python finalizer 會卡在 stdin lock
        # 互動（Linux kernel close(fd) 不 wake 已阻塞在 read(fd) 的 thread）。所有
        # worker shutdown 已跑完 → os._exit(0) 強退跳過 finalizer（atexit / module
        # finalize / daemon thread join）對本專案無副作用（daemon=True 隨 process die
        # 是設計目的）。
        import os
        os._exit(0)


if __name__ == "__main__":
    main()
