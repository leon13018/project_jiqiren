"""tests/stt 共用 fakes — 零真網路、零真音訊（Windows 紅線）。"""
import queue
import threading
import time


class FakeAudioSource:
    """依序回傳 chunks；耗盡或 close 後回 b""（模擬 arecord EOF）。"""

    def __init__(self, chunks=()):
        self._chunks = list(chunks)
        self.closed = False

    def read(self, n: int) -> bytes:
        if self.closed or not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeWs:
    """Queue 化：recv() 阻塞至有訊息或 close()；feed() 動態餵 server 訊息；
    sent 收所有 send（bytes 音框 + str control 如 KeepAlive/Finalize/CloseStream）。"""

    _SENTINEL = object()

    def __init__(self, messages=()):
        self._q = queue.Queue()
        for m in messages:
            self._q.put(m)
        self._closed = threading.Event()
        self.sent = []

    def send(self, data) -> None:
        if self._closed.is_set():
            raise RuntimeError("ws closed")
        self.sent.append(data)

    def feed(self, message) -> None:
        """動態加一筆 server 訊息（多輪 / 收音窗外測試用）。"""
        self._q.put(message)

    def recv(self):
        item = self._q.get()
        if item is FakeWs._SENTINEL:
            raise RuntimeError("ws closed")
        return item

    def close(self) -> None:
        self._closed.set()
        self._q.put(FakeWs._SENTINEL)


def wait_until(predicate, timeout: float = 2.0) -> bool:
    """輪詢等待背景 thread 效果（取代裸 sleep——失敗訊息更快、成功不空等）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()
