"""test_queue_worker.py — 測試 myProgram/queue_worker.py QueueWorker 基底 + drain_queue helper。

W6 重構：tts / action 兩個 consumer worker 共用的「FIFO queue + daemon thread +
get → _process → on_done 迴圈」骨架收進 QueueWorker(ABC)；三份相同的清空 queue
迴圈收進 drain_queue helper。

測試策略：
    - drain_queue：純函式直接測（塞滿 → 呼叫 → empty；空 queue 不炸）
    - QueueWorker 骨架：建 fake 子類別（_process 記錄到 list），用 threading.Event
      同步驗證骨架行為（**禁 sleep 輪詢** — Event.wait(timeout) 精確等到事件）
    - ActionWorker 不在此測（vendor import 在 worker thread 內，Windows 無法直測；
      等價性靠逐行對照 + Pi 實機驗證，見 spec §2-3 / §6）
"""

import queue
import threading

import pytest

from myProgram.queue_worker import QueueWorker, drain_queue


# ============================================================
# drain_queue helper
# ============================================================


def test_drain_queue_empties_a_full_queue():
    """塞 3 筆 → drain_queue → queue 應為空。"""
    q: "queue.Queue" = queue.Queue()
    for i in range(3):
        q.put(i)
    assert not q.empty()

    drain_queue(q)

    assert q.empty()


def test_drain_queue_on_empty_queue_does_not_raise():
    """空 queue 呼叫 drain_queue 不炸（while not empty 直接跳過）。"""
    q: "queue.Queue" = queue.Queue()
    drain_queue(q)  # 不應 raise
    assert q.empty()


# ============================================================
# Fake 子類別 — 記錄事件序到 list，用 Event 同步
# ============================================================


class _RecordingWorker(QueueWorker):
    """記錄骨架各回調的 fake 子類別。

    - on_thread_start / _process / on_done 各 append 一筆到 events（含 item）
    - 每次 on_done 後 set done_event（caller 用 wait(timeout) 同步，禁 sleep 輪詢）
    """

    thread_name = "RecordingWorker"

    def __init__(self) -> None:
        self.events: list = []
        self.done_event = threading.Event()
        super().__init__()

    def on_thread_start(self) -> None:
        self.events.append(("thread_start", None))

    def _process(self, item) -> None:
        self.events.append(("process", item))

    def on_done(self, item) -> None:
        self.events.append(("done", item))
        self.done_event.set()


class _RaisingWorker(QueueWorker):
    """_process 永遠 raise 的 fake 子類別 — 驗 try/finally 仍呼叫 on_done。"""

    thread_name = "RaisingWorker"

    def __init__(self) -> None:
        self.on_done_called = threading.Event()
        super().__init__()

    def _process(self, item) -> None:
        raise RuntimeError("boom")

    def on_done(self, item) -> None:
        self.on_done_called.set()


# ============================================================
# QueueWorker 骨架
# ============================================================


def test_submit_passes_item_to_process():
    """submit(item) → worker thread 的 _process 收到該 item。"""
    worker = _RecordingWorker()
    worker.submit("hello")

    assert worker.done_event.wait(timeout=2.0), "on_done 應在 2s 內被呼叫"
    process_items = [item for kind, item in worker.events if kind == "process"]
    assert process_items == ["hello"]


def test_on_done_called_even_when_process_raises(monkeypatch):
    """_process raise 時 on_done 仍被呼叫（_loop 的 try/finally）。

    基底刻意無 catch-all（spec §2-1 決定 1）：未捕例外會傳出 _loop 殺掉該 thread
    — 這是現行 TtsWorker `_loop`（僅 try/finally）的等價行為。本 test 只驗 finally
    內 on_done 必被呼叫。

    例外從 daemon thread 傳出會觸發 threading.excepthook（pytest 轉成
    PytestUnhandledThreadExceptionWarning）；monkeypatch threading.excepthook 為
    no-op 吞掉這個測試設計副產物，保持輸出乾淨（非 prod 問題）。
    """
    monkeypatch.setattr(threading, "excepthook", lambda args: None)

    worker = _RaisingWorker()
    worker.submit("x")

    assert worker.on_done_called.wait(timeout=2.0), (
        "_process raise 後 on_done 仍應被呼叫（try/finally）"
    )


def test_on_thread_start_runs_before_first_process():
    """on_thread_start 在首次 _process 之前執行（事件序）。"""
    worker = _RecordingWorker()
    worker.submit("first")

    assert worker.done_event.wait(timeout=2.0)
    kinds = [kind for kind, _ in worker.events]
    assert kinds[0] == "thread_start", f"首事件應為 thread_start，實際序：{kinds}"
    assert kinds.index("thread_start") < kinds.index("process")


def test_multiple_submits_processed_in_fifo_order():
    """多筆 submit 依 FIFO 順序被 _process。"""
    worker = _RecordingWorker()
    n = 5
    for i in range(n):
        worker.submit(i)

    # 等最後一筆處理完（每次 on_done 都 set；最後一筆 set 後 list 完整）
    deadline_items = []
    for _ in range(50):  # 最多等 ~5s（Event.wait 0.1s × 50），非 sleep 輪詢主邏輯
        worker.done_event.wait(timeout=0.1)
        deadline_items = [item for kind, item in worker.events if kind == "process"]
        if len(deadline_items) == n:
            break
    assert deadline_items == list(range(n)), f"FIFO 順序錯：{deadline_items}"


def test_drain_removes_unconsumed_items():
    """drain() 清空尚未消費的 queue 項。

    用一個會卡在第一筆 _process 的 worker：第一筆卡住時後續 submit 累積在 queue，
    drain() 應把累積項清掉。
    """
    release = threading.Event()
    started = threading.Event()

    class _BlockingWorker(QueueWorker):
        thread_name = "BlockingWorker"

        def _process(self, item) -> None:
            started.set()
            release.wait()  # 卡住第一筆，讓後續 submit 累積在 _q

    worker = _BlockingWorker()
    worker.submit("blocker")
    assert started.wait(timeout=2.0), "worker 應已開始處理第一筆"

    # 第一筆卡住期間再塞 3 筆 → 累積在 _q（未被消費）
    for i in range(3):
        worker.submit(i)
    worker.drain()

    assert worker._q.empty(), "drain 應清空未消費項"
    release.set()  # cleanup：放行 worker


def test_thread_name_reflected_in_running_thread():
    """thread_name 反映在實際 daemon thread 的 name（threading.enumerate 找得到）。"""
    worker = _RecordingWorker()
    names = [t.name for t in threading.enumerate()]
    assert "RecordingWorker" in names, f"應有名為 RecordingWorker 的 thread，實際：{names}"
