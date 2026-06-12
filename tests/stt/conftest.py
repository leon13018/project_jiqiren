"""tests/stt 共用 fakes — 零真網路、零真音訊（Windows 紅線）。"""
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
    """recv() 依序回傳 messages；耗盡後阻塞直到 close()（模擬等伺服器）。"""

    def __init__(self, messages=()):
        self._messages = list(messages)
        self._closed = threading.Event()
        self.sent = []

    def send(self, data) -> None:
        if self._closed.is_set():
            raise RuntimeError("ws closed")
        self.sent.append(data)

    def recv(self):
        if self._messages:
            return self._messages.pop(0)
        self._closed.wait()
        raise RuntimeError("ws closed")

    def close(self) -> None:
        self._closed.set()


def wait_until(predicate, timeout: float = 2.0) -> bool:
    """輪詢等待背景 thread 效果（取代裸 sleep——失敗訊息更快、成功不空等）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()
