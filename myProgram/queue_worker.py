"""W6 QueueWorker 基底 — consumer worker 三胞胎的共通骨架（tts / action）。

收斂動機（盤點 #6）：
    tts.py / action.py 兩個 consumer worker 共用「FIFO queue + daemon thread +
    get → _process → on_done 迴圈」骨架；drain-queue 清空迴圈在 tts / action /
    input_reader 重複 ×3。本基底收 consumer 骨架，drain_queue helper 收清空迴圈。

兩個刻意的設計決定（與傘狀 §4-6 對齊；傘狀隨本 wave 修正）：
    1. **基底無 except-all / 無 on_error hook**：現行 TtsWorker `_loop` 只有
       try/finally（未知例外殺 thread 是現狀）；ActionWorker 的 catch 在自己
       迴圈體內 → 改造後住進其 `_process`。基底加 catch-all 會改變 TtsWorker
       行為（純重構零行為改變的紅線），故不做。
    2. **`shutdown` 不入基底**：兩 worker 順序相反（tts：terminate proc → drain；
       action：drain → 守衛 stopAction），各自保留現行實作，改用 `self.drain()` /
       `drain_queue` 取代手寫清空迴圈。

InputReader 不繼承本基底（producer 形狀：daemon thread 是 readline→put 的生產者，
read() 是主線程消費 — 與 consumer 骨架相反），只 reuse drain_queue。
"""

import queue
import threading
from abc import ABC, abstractmethod


def drain_queue(q: "queue.Queue") -> None:
    """清空 queue（共用 helper——原 tts / action / input_reader 三份相同迴圈）。"""
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            break


class QueueWorker(ABC):
    """FIFO daemon 消費者骨架：queue + daemon thread + get → _process → on_done 迴圈。

    ⚠️ 子類別若有自有欄位（如 TtsWorker 的 _pending / _cv），必須在呼叫
    super().__init__() **之前**設好——基底 __init__ 立即啟動 daemon thread，
    thread 第一時間可能觸碰子類別欄位。
    """

    thread_name: str   # 子類別 class attr

    def __init__(self) -> None:
        self._q: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._loop, name=self.thread_name, daemon=True).start()

    def submit(self, item) -> None:
        self._q.put(item)

    def _loop(self) -> None:
        self.on_thread_start()
        while True:
            item = self._q.get()
            try:
                self._process(item)
            finally:
                self.on_done(item)

    @abstractmethod
    def _process(self, item) -> None: ...

    def on_thread_start(self) -> None:
        pass   # ActionWorker：lazy import vendor

    def on_done(self, item) -> None:
        pass   # TtsWorker：dec _pending + notify

    def drain(self) -> None:
        drain_queue(self._q)
