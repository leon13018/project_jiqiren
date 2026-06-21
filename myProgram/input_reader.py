"""S6 非阻塞 input 模組 — daemon reader thread + queue + bytes-level decode。

S6 範圍（incremental-rebuild 第 6 步）：
    - 對外 API：`read(timeout) -> str | None` + `shutdown() -> None`
    - 行為：reader thread 持續 `sys.stdin.buffer.readline()` 把 line push 進 queue；
      caller `read(timeout)` 從 queue 取，timeout 內無輸入返回 None
    - 為 S7 / STT 並行 + hawk 觸控 polling 鋪基礎 — 主線程不再被 `input()` 阻塞
    - 順便根治 stdin TextIOWrapper buffer multibyte 殘留 bug
      （移除 main.py 內 `sys.stdin.reconfigure(...)` hack）

S6 動機（S1-S5 同步 `input()` 實機踩到的問題）：
    1. L4 60s wall-clock 預算實際沒在跑 — `read_customer_input(timeout)` 內部
       `input()` 不支援 timeout，顧客只要不打字主線程就阻塞，`deadline -
       time.monotonic()` 永遠 check 不到。production 顧客若不掃碼也不打字會
       永遠卡在 L4。
    2. l1.py hawk 主迴圈靠 `read_terminal_key(timeout=0.1)` polling 跑叫賣輪播
       + 偵測 't' 觸控（開始點餐）；`read_terminal_key()` 內部若用阻塞 `input()`
       會卡死整個 poll loop — 輪播停、't' 收不到。
    3. stdin TextIOWrapper buffer 殘留 partial UTF-8 序列把新一輪 leading byte
       誤判為 continuation（2026-05-27 Pi 實測「刮刮樂冰紅茶」於 0xe5 byte
       raise「invalid continuation byte」）。S6 改用 `sys.stdin.buffer.readline()`
       拿 bytes 自己 `decode(errors="replace")`，繞過 TextIOWrapper 整個 buffer
       邏輯 → 徹底消除此 bug class。

設計準則（依 `.claude/rules/incremental-rebuild.md` S6 段 + threading-conventions）：
    - **單 queue 單消費者**：對齊 tts.py / action.py，避免旗號分流 race
    - **daemon=True**：主程式退出時 thread 自動 die（不卡住整個程序退出）
    - **bytes-level**：`sys.stdin.buffer.readline()` 拿 bytes + 自己
      `decode("utf-8", errors="replace")`；繞過 TextIOWrapper buffer 邏輯，
      徹底消除 partial multibyte 殘留 bug class
    - **drain on enter**：每次 `read()` 進入時清空 queue 殘留（對齊
      single-queue-preference memory「順序消費 + 切換情境時 drain」），
      避免前一情境（如 hawk 期間商家亂打鍵）殘留漏到 dialogue
    - **print 在 caller thread**：對齊 tts / action — reader 純讀，不印 prompt；
      caller（main.py / l1.py / l4.py）若需要 visual cue 自行印
    - **不用 Lock**：queue.Queue 內建 thread-safe，加 Lock 反而違反
      threading-conventions「手動 Lock 避免」原則

差異對比 tts.py / action.py：
    - 無 subprocess（純 Python IO）→ 不需 `_proc` / `_lock`
    - 無 ALSA drain / sticky 旗號處理 → shutdown 純清 queue
    - 失敗策略：bytes decode 用 `errors="replace"` 自動把無效 byte 換 U+FFFD（�），
      不 raise；EOF 推 sentinel `None` 結束 loop

caller（main.py 的 read_terminal_key / read_customer_input）使用方式：
    >>> from myProgram import input_reader
    >>> raw = input_reader.read(timeout=0.1)  # polling cadence
    >>> if raw is None:
    ...     ...  # timeout，無輸入
    >>> input_reader.shutdown()  # main() finally 呼叫，對齊 tts/action
"""

import os
import queue
import sys
import threading
from typing import Optional

from myProgram.queue_worker import drain_queue


# SALES_KEYBOARD 鍵盤 gate（env 旗標）：預設 0 = 關鍵盤（demo 改用 web/語音驅動）；=1 才啟
# stdin reader thread。production singleton `_reader` 由此值帶入 keyboard_enabled。
# 各模組各自讀 env（沿用 SALES_VOICE precedent，不新增跨模組 import；main 的啟動防呆
# 另自讀同一 env，production 同一啟動值一致）。
_KEYBOARD = bool(int(os.environ.get("SALES_KEYBOARD", "0")))


class InputReader:
    """非阻塞 stdin reader：daemon thread + queue.Queue + bytes-level decode。

    Thread model（依 [[threading-conventions]] 推薦：blocking 任務全推背景）：
        - 主線程：呼叫 `read(timeout)`（從 queue 取）+ `shutdown()`（清 queue）
        - 背景 daemon thread：跑 `_loop()` 持續 `readline()` push 進 queue

    注入式 byte source：
        為了單元測試方便，建構時可注入自定義 byte source（任何具
        `readline() -> bytes` 介面的物件）。production 使用 module-level
        singleton `_reader` 預設綁 `sys.stdin.buffer`。
    """

    def __init__(self, source: object = None, *, keyboard_enabled: bool = True) -> None:
        """初始化 reader；keyboard_enabled 才啟動 stdin reader daemon thread。

        Args:
            source: 注入式 byte source（須有 `readline() -> bytes` 方法）。
                None = 用 `sys.stdin.buffer`（production 預設）。
                測試環境用 FakeByteSource 餵假 bytes 避開真 stdin。
            keyboard_enabled: True 才啟 `_loop` stdin reader thread（讀鍵盤）；False
                則完全不啟 thread（不讀 source），但 inject()（web/語音 sink）/ read()
                / shutdown() 全照常 → 關鍵盤後 web/語音仍完整驅動。
                **預設 True**：給既有測試 fixtures（`InputReader(source=...)`）沿用——
                它們要 thread 跑去消化 FakeByteSource；production 唯一實例是 module
                singleton `_reader`，明確帶 `_KEYBOARD`（env SALES_KEYBOARD，預設關）。
        """
        self._source = source if source is not None else sys.stdin.buffer
        # type hint 用 string annotation：對齊 tts.py / action.py 的 Python 3.7
        # 相容寫法（Pi 環境）。Queue 元素可以是 str（一行輸入）或 None（EOF sentinel）。
        self._q: "queue.Queue[Optional[str]]" = queue.Queue()
        # daemon=True：主程式退出時自動 die（即使卡在 readline 也會被 runtime 清掉）。
        # keyboard_enabled=False → 不啟 thread（鍵盤關）；inject/read 仍可用（共用同 queue）。
        if keyboard_enabled:
            threading.Thread(target=self._loop, name="InputReader", daemon=True).start()

    def _loop(self) -> None:
        """Daemon reader：持續 readline → decode → push queue（EOF 推 None 退出）。

        bytes-level decode：用 `errors="replace"` 把無效 UTF-8 byte 換成 U+FFFD（�），
        不 raise；caller 拿到含 � 的字串仍可走 normalize_input + NLU pipe，比
        「一次 decode 失敗整個 dialog timeout」友善（對齊舊 main.py reconfigure 設計目的）。

        EOF 處理：`readline()` 返回 b""（empty bytes）代表 stdin 已關閉 → push
        `None` 當 sentinel 通知 caller，然後 break 退出 loop（daemon thread 結束，
        不需 join，主程式退出時自動清掉）。
        """
        while True:
            try:
                raw_bytes = self._source.readline()
            except (OSError, ValueError):
                # OSError: Windows pytest captured stdin 環境 raise「pytest:
                # reading from stdin while output is captured!」。module-level
                # singleton 在 pytest collect 啟動就會撞。
                # ValueError: shutdown() 期間 sys.stdin.close() 觸發
                # 「I/O operation on closed file」(2026-05-28 加，配合 shutdown
                # 主動關閉 stdin 解 Fatal Python error _enter_buffered_busy)。
                # 兩種情境下都靜默退出 loop（push EOF sentinel 通知 caller）。
                self._q.put(None)
                break
            if not raw_bytes:
                # EOF：push sentinel + 退出 loop（不再有輸入可讀）
                self._q.put(None)
                break
            line = raw_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            self._q.put(line)

    def read(self, timeout: Optional[float]) -> Optional[str]:
        """從 queue 取一行；timeout 內無輸入返回 None。

        drain on enter（保留最新一筆語義）：先把 queue 內**過期**殘留清掉，
        只保留最新一筆。對齊 single-queue-preference memory「順序消費 + 切換
        情境時 drain」原則 — 避免前一情境（如 hawk 期間商家亂打鍵）spam
        殘留漏到本次 read，但同時保留「user 剛打完還沒被 caller 消費」的
        最新輸入。

        為何「保留最新」而非「全清」：
        - 若 read 進入時 queue 已有 1 筆（user 剛打完 reader 剛 push）→ 全清
          會吃掉這個 valid 輸入；保留最新可避免 race window 殺掉合法輸入
        - 若 queue 已有多筆（hawk 期間 spam 累積）→ 只保留最後一筆，舊的丟掉
        - 實機 production hawk 100ms polling + user 打字 ~1s，user 一次只會
          push 一筆，「保留最新」=「保留 user 剛打的這筆」=「不漏輸入」

        Args:
            timeout: 等待秒數；None = 無限阻塞等到有輸入（給商家主選單 /
                standby 模式用，保留現行 UX）。

        Returns:
            一行輸入字串（已 strip "\\r\\n"），或 None（timeout / EOF sentinel）。
        """
        # 1. drain：吃掉所有殘留並記錄最後一筆（latest-wins 語義）
        latest: Optional[str] = None
        has_residual = False
        while True:
            try:
                latest = self._q.get_nowait()
                has_residual = True
            except queue.Empty:
                break
        # 2. 若 drain 撈到殘留，直接回最新一筆（不再 block 等下一筆）
        if has_residual:
            return latest
        # 3. queue 原本就空 → 阻塞 get（timeout=None 表無限等）
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def shutdown(self) -> None:
        """清空 queue（main.py exit 時呼叫，對齊 tts/action shutdown 對稱性）。

        daemon=True 隨主程式退出自動 die，不需 join；此函式只清 queue 殘留，
        讓 cleanup 語義跟 tts.shutdown / action.shutdown 一致比較好維護。

        無 subprocess 可 terminate / 無 vendor sticky 旗號可守衛 — 純 stdlib
        queue 操作（共用 drain_queue helper；read() 的 latest-wins drain 語意
        不同，**不**改用此 helper）。
        """
        drain_queue(self._q)

    def inject(self, text: str) -> None:
        """外部 producer（STT speech_final 文字）注入一行輸入。

        與鍵盤 reader thread 共用同一 queue（單 queue 原則，producer 端零分流；
        見 incremental-rebuild §單 queue 偏好）——caller 端 read() 的 drain /
        timeout 語意對兩種來源完全一致。
        """
        self._q.put(text)


# Module-level singleton：import 時建立；keyboard_enabled=_KEYBOARD（env SALES_KEYBOARD，
# 預設關）才啟 daemon reader thread。使用者多次 `from myProgram import input_reader` 不會
# 重複建（Python module cache）。對齊 tts._worker / action._worker pattern。
#
# Windows pytest 環境注意：SALES_KEYBOARD 預設關 → singleton 不啟 thread，不再有
# pytest collect 時 daemon thread 卡 `sys.stdin.buffer.readline()` 的 leak（若 env 開
# 鍵盤則仍會啟，pytest 結束時 runtime 自動清掉——daemon=True 的設計目的）。
# 測試一律 `InputReader(source=FakeByteSource(...))` 自建實例，不用 module 級 `_reader`。
_reader = InputReader(keyboard_enabled=_KEYBOARD)


def read(timeout: Optional[float]) -> Optional[str]:
    """對外 API：從 reader queue 取一行，timeout 內無輸入返回 None。

    Args:
        timeout: 等待秒數；None = 無限阻塞等到有輸入。

    Returns:
        一行輸入字串（已 strip newline），或 None（timeout / EOF）。
    """
    return _reader.read(timeout)


def shutdown() -> None:
    """對外 API：清 queue 殘留（main.py finally 呼叫，對齊 tts/action）。

    歷史 / 為何不關 stdin（2026-05-28 Pi 實機 root cause 排查）：
        曾經這裡有 `sys.stdin.close()` 試圖「主動 unblock daemon reader thread 的
        readline syscall」+ 抑制 interpreter shutdown 階段的 Fatal Python error
        訊息。實測在 Pi 上**反而 hang**：
        1. `sys.stdin.close()` 內部 acquire stdin BufferedReader 的 lock
        2. 但 daemon reader thread 此刻正卡在 `readline()` syscall 持有那個 lock
        3. main thread 永遠拿不到 lock → close() 卡死 → main 沒到 os._exit
        4. user 必須按一個鍵 → kernel deliver byte → reader readline 返回 →
           release lock → main close 終於 OK → 繼續走到 os._exit → 真退出
        結論：close stdin 反 productive。Linux kernel `close(fd)` 本來也 unblock
        不了 in-syscall read（kernel implementation-defined：只 mark fd 不可用，
        next read 才 EBADF），所以這個 close 完全沒解決 hang，只造成 lock
        deadlock。

    現在策略：shutdown 只 clear queue（instant，無 IO，不卡）。daemon reader
    thread 隨 main 的 os._exit(0) 殺 process 一起 die — Python 不會在 finalizer
    階段卡 stdin lock 因為根本沒 finalizer（os._exit 跳過 finalize）。

    對齊 tts/action shutdown 對稱（純清自己 queue）。
    """
    _reader.shutdown()


def inject(text: str) -> None:
    """對外 API：注入一行輸入（STT worker 的 sink；與鍵盤共用單 queue）。"""
    _reader.inject(text)
