"""input_reader.inject 注入點測試 — STT 與鍵盤共用單 queue。"""
import threading

from myProgram.input_reader import InputReader


class BlockingByteSource:
    """readline 永久阻塞的假 source——隔離 daemon reader，queue 內容全由 inject 控制。"""

    def __init__(self):
        self._ev = threading.Event()

    def readline(self) -> bytes:
        self._ev.wait()
        return b""


def test_inject_then_read_returns_text():
    reader = InputReader(source=BlockingByteSource())
    reader.inject("我要紅茶兩杯")
    assert reader.read(timeout=0.5) == "我要紅茶兩杯"


def test_inject_multiple_latest_wins():
    # 既有 read() drain 語意：殘留多筆只回最新（與鍵盤 spam 行為一致）
    reader = InputReader(source=BlockingByteSource())
    reader.inject("第一句")
    reader.inject("第二句")
    assert reader.read(timeout=0.5) == "第二句"
