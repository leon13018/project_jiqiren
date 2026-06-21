"""test_input_reader.py — 測試 myProgram/input_reader.py 的非阻塞 stdin reader。

S6 incremental rebuild 第 6 步配套單元測試。

測試策略：用注入式 FakeByteSource 而非真 stdin。
    - production singleton `_reader` 在 import 時就啟動 daemon thread 卡在
      真 sys.stdin.buffer.readline()，不適合測試使用
    - 測試一律 `InputReader(source=FakeByteSource(...))` 自建實例
    - reader thread 是 daemon=True，pytest 跑完隨主程式退出自動清掉，
      不會 leak（即使測試結束時 thread 仍 blocking on source.readline）

覆蓋 8 個 case：
    1. basic read：正常一行輸入
    2. timeout：queue 空 + timeout 返回 None
    3. drain residual：read 進入時先 drain queue 殘留
    4. EOF：source 給 b"" 觸發 sentinel None
    5. multibyte invalid byte：errors="replace" 換 U+FFFD 不 raise
    6. multiple reads FIFO：連續兩筆輸入依序拿到
    7. Chinese UTF-8：繁中正確 decode
    8. shutdown clears queue：shutdown 後內部 queue 應空
"""

import queue
import threading
import time

import pytest

from myProgram.input_reader import InputReader


# ============================================================
# 測試工具：FakeByteSource — 用 list of bytes 模擬 stdin.buffer
# ============================================================


class FakeByteSource:
    """模擬 stdin.buffer：依序 readline() 返回預設好的 bytes 序列。

    用法：
        src = FakeByteSource([b"hello\\n", b"world\\n"])
        src.readline()  # → b"hello\\n"
        src.readline()  # → b"world\\n"
        src.readline()  # → b""（EOF，list 耗盡）

    支援動態追加（測試中模擬「延遲輸入」場景）：
        src = FakeByteSource([])
        src.feed(b"late\\n")  # 之後 readline() 才會拿到

    Blocking 語義：list 空時 readline() 不立即 EOF，而是 block 等
    `feed()` 餵新資料（用 threading.Event 同步），更貼近真 stdin.buffer
    的「沒輸入就 block」行為。`close()` 才推 EOF。
    """

    def __init__(self, initial_bytes: list) -> None:
        self._lines: list = list(initial_bytes)
        self._closed = False
        self._lock = threading.Lock()
        self._has_data = threading.Event()
        if self._lines:
            self._has_data.set()

    def readline(self) -> bytes:
        """阻塞讀一行 bytes；list 空且未 close 則 block 等 feed()。"""
        while True:
            with self._lock:
                if self._lines:
                    return self._lines.pop(0)
                if self._closed:
                    return b""  # EOF
                # list 空且未 close → 清 event 再 block
                self._has_data.clear()
            # 等 feed() 或 close() set event
            self._has_data.wait(timeout=1.0)

    def feed(self, line: bytes) -> None:
        """追加一行 bytes 供下次 readline() 取用。"""
        with self._lock:
            self._lines.append(line)
            self._has_data.set()

    def close(self) -> None:
        """模擬 stdin 關閉；下次 readline() 返回 b""。"""
        with self._lock:
            self._closed = True
            self._has_data.set()


# ============================================================
# Helper：等 reader thread 把 source bytes 消化到 queue
# ============================================================


def _wait_for_queue_size(reader: InputReader, expected: int, timeout: float = 1.0) -> None:
    """polling 等 reader._q 內元素數達 expected（防 reader thread 還沒消化完的 race）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if reader._q.qsize() >= expected:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"等了 {timeout}s reader queue 仍只 {reader._q.qsize()} 筆，預期 {expected}"
    )


# ============================================================
# Test 1：basic read 正常拿一行
# ============================================================


def test_basic_read_returns_line():
    """source 餵 b'hello\\n' → read(timeout=0.5) 回 'hello'（rstrip newline）。"""
    src = FakeByteSource([b"hello\n"])
    reader = InputReader(source=src)
    result = reader.read(timeout=0.5)
    assert result == "hello"


# ============================================================
# Test 2：timeout queue 空時返回 None
# ============================================================


def test_read_timeout_returns_none_when_queue_empty():
    """source 不餵任何 bytes → read(timeout=0.05) 應在 ~0.05s 內返回 None。"""
    src = FakeByteSource([])
    reader = InputReader(source=src)
    start = time.monotonic()
    result = reader.read(timeout=0.05)
    elapsed = time.monotonic() - start
    assert result is None
    # 容忍 0.15s（Windows pytest 排程 jitter）
    assert elapsed < 0.15, f"timeout 0.05s 卻耗時 {elapsed:.3f}s，疑似阻塞錯誤"


# ============================================================
# Test 3：drain residual — read 進入時清空殘留
# ============================================================


def test_drain_residual_before_get():
    """source 餵 3 行；wait queue 累積後 read → 拿到「最新」一筆（latest-wins drain）。

    drain on enter 採「保留最新」語義（latest-wins）：吃掉所有殘留只回最新一筆，
    避免「全清」race window 殺掉合法輸入（user 剛打的字也被當殘留丟）。詳見
    input_reader.InputReader.read docstring。
    """
    src = FakeByteSource([b"old1\n", b"old2\n", b"new\n"])
    reader = InputReader(source=src)
    # 等 reader thread 把 3 筆全消化進 queue
    _wait_for_queue_size(reader, 3)
    # read() 進入時 drain 留最後一筆「new」，舊的 old1/old2 丟掉
    result = reader.read(timeout=0.05)
    assert result == "new", f"latest-wins drain 應拿到「new」，實際 {result!r}"


# ============================================================
# Test 4：EOF 推 sentinel None
# ============================================================


def test_eof_returns_none_sentinel():
    """source 餵一行後 close → reader 推 hello + None sentinel；latest-wins drain
    讓 read 拿到「最新一筆」即 None（EOF sentinel）。

    驗證 EOF 語義：source 關閉後，reader._loop 偵測 readline() 返 b"" → push
    None sentinel + break 退出 loop。caller 看到的是 None（latest-wins drain
    保留最新 sentinel）。
    """
    src = FakeByteSource([b"hello\n"])
    reader = InputReader(source=src)
    # 等第一筆進 queue
    _wait_for_queue_size(reader, 1)
    # 關 source → reader thread 下一輪 readline() 返 b"" → 推 None sentinel
    src.close()
    # 等 reader 把 sentinel 推進去（queue 應有 "hello" + None 兩筆）
    _wait_for_queue_size(reader, 2)
    # latest-wins drain 拿到最後一筆 = None sentinel
    result = reader.read(timeout=0.05)
    assert result is None, f"EOF sentinel 應為 None，實際 {result!r}"


# ============================================================
# Test 5：multibyte invalid byte → 換 U+FFFD 不 raise
# ============================================================


def test_multibyte_invalid_byte_replaced():
    """source 餵無效 UTF-8 序列 → decode errors='replace' 換 U+FFFD（�），不 raise。"""
    # b"\xe5\xe5\xe5" 三個 leading byte 連在一起，無 continuation byte → 無效 UTF-8
    src = FakeByteSource([b"\xe5\xe5\xe5\n"])
    reader = InputReader(source=src)
    result = reader.read(timeout=0.5)
    assert result is not None, "errors='replace' 應該不 raise，仍返回字串"
    # U+FFFD（REPLACEMENT CHARACTER）應該出現至少一次
    assert "�" in result, f"無效 byte 應換 U+FFFD（�），實際 {result!r}"


# ============================================================
# Test 6：multiple reads FIFO 連續兩筆依序拿
# ============================================================


def test_multiple_reads_fifo():
    """先讀第一筆（reader 立即 push 後 read 拿到）→ 再餵第二筆 → 再讀拿到第二筆。

    設計成「reader 消化一筆 → read 拿走 → 再餵下一筆」避免 drain 殺掉殘留。
    """
    src = FakeByteSource([b"A\n"])
    reader = InputReader(source=src)
    # 第一次 read：等到 A
    result1 = reader.read(timeout=0.5)
    assert result1 == "A"
    # 第二次餵入並讀
    src.feed(b"B\n")
    result2 = reader.read(timeout=0.5)
    assert result2 == "B"


# ============================================================
# Test 7：繁中 UTF-8 正確 decode
# ============================================================


def test_chinese_utf8_decoded():
    """source 餵繁中 UTF-8 編碼 + newline → read 回繁中原字串。"""
    text = "刮刮樂"
    src = FakeByteSource([text.encode("utf-8") + b"\n"])
    reader = InputReader(source=src)
    result = reader.read(timeout=0.5)
    assert result == text, f"繁中 UTF-8 decode 失敗，預期 {text!r} 實際 {result!r}"


# ============================================================
# Test 8：shutdown 清空 queue
# ============================================================


def test_shutdown_clears_queue():
    """source 餵兩行 → 等 reader 消化 → shutdown → 內部 queue 應空。"""
    src = FakeByteSource([b"a\n", b"b\n"])
    reader = InputReader(source=src)
    _wait_for_queue_size(reader, 2)
    # 確認 shutdown 前有殘留
    assert reader._q.qsize() == 2
    reader.shutdown()
    # 確認 queue 已清空
    assert reader._q.qsize() == 0, f"shutdown 後 queue 應空，實際剩 {reader._q.qsize()} 筆"


# ============================================================
# Test 9：SALES_KEYBOARD gate — keyboard_enabled 控制 stdin reader thread
# ============================================================


def test_keyboard_disabled_does_not_read_source_but_inject_works():
    """keyboard_enabled=False：不啟 stdin reader thread → source 不被讀（queue 不進
    鍵盤輸入）；但 inject()（web/語音 sink）+ read() 仍照常運作。

    對應 SALES_KEYBOARD=0（預設關鍵盤）：關掉鍵盤後仍由 web/語音經 inject 完整驅動。
    """
    src = FakeByteSource([b"x\n"])
    reader = InputReader(source=src, keyboard_enabled=False)
    # 給 thread 若誤啟動的時間窗口；keyboard_enabled=False 應根本沒 thread 去讀 source
    time.sleep(0.1)
    assert reader._q.qsize() == 0, "keyboard_enabled=False 不應讀 source（queue 應空）"
    # inject + read 仍可用（web/語音路徑不受 gate 影響）
    reader.inject("web")
    assert reader.read(timeout=0.1) == "web"


def test_keyboard_enabled_reads_source():
    """keyboard_enabled=True（既有預設）：啟 stdin reader thread → 讀到 source（行為不變）。"""
    src = FakeByteSource([b"hello\n"])
    reader = InputReader(source=src, keyboard_enabled=True)
    assert reader.read(timeout=0.5) == "hello"
