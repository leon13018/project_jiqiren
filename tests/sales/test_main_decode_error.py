"""test_main_decode_error.py — 測試 myProgram/main.py 的 input() decode error 處理。

2026-05-27 Wave 4 hotfix 3 新增：
    顧客在 Pi 上輸入「皆可」二字時觸發 UnicodeDecodeError，當前 except 只印一行籠統訊息
    就吃掉，無法 debug 是哪個 byte 序列炸的。本檔測試 noisy debug 模式：印出
    UnicodeDecodeError 的 codec / reason / start-end / raw hex bytes，方便使用者
    截圖回報。

覆蓋 4 個 case：
    1. read_terminal_key + UnicodeDecodeError → 印 hex + return ""
    2. read_customer_input + UnicodeDecodeError → 印 hex + return None
    3. read_terminal_key + EOFError → 印 EOFError 訊息 + return ""
    4. read_customer_input + EOFError → 印 EOFError 訊息 + return None

設計：直接從 myProgram.main 取出 _build_callbacks 內封閉的 read_terminal_key /
      read_customer_input；用 monkeypatch.setattr("builtins.input", ...) 模擬 input()
      raise 對應 exception；capsys 捕 stdout 斷言訊息內容。
"""

from myProgram.main import _S1State, _build_callbacks


# ============================================================
# read_terminal_key — UnicodeDecodeError
# ============================================================

def test_read_terminal_key_unicode_decode_error_prints_hex_and_returns_empty(monkeypatch, capsys):
    """read_terminal_key 遇 UnicodeDecodeError → 印 raw hex + return ""。"""
    state = _S1State()
    callbacks = _build_callbacks(state)
    read_terminal_key = callbacks["read_terminal_key"]

    def fake_input(prompt=""):
        # b"\xc3\x28" 是經典 invalid UTF-8 continuation byte 序列
        raise UnicodeDecodeError("utf-8", b"\xc3\x28", 0, 1, "invalid continuation byte")

    monkeypatch.setattr("builtins.input", fake_input)
    result = read_terminal_key()
    out = capsys.readouterr().out

    assert result == ""
    assert "UnicodeDecodeError" in out
    assert "raw hex" in out
    assert "c3" in out  # b"\xc3\x28" 的 hex 第一個 byte


# ============================================================
# read_customer_input — UnicodeDecodeError
# ============================================================

def test_read_customer_input_unicode_decode_error_prints_hex_and_returns_none(monkeypatch, capsys):
    """read_customer_input 遇 UnicodeDecodeError → 印 raw hex + return None。"""
    state = _S1State()
    callbacks = _build_callbacks(state)
    read_customer_input = callbacks["read_customer_input"]

    def fake_input(prompt=""):
        # 用 end=2 涵蓋兩個 byte，驗證 slice 完整 hex 印出
        raise UnicodeDecodeError("utf-8", b"\xc3\x28", 0, 2, "invalid continuation byte")

    monkeypatch.setattr("builtins.input", fake_input)
    result = read_customer_input(6)
    out = capsys.readouterr().out

    assert result is None
    assert "UnicodeDecodeError" in out
    assert "raw hex" in out
    assert "c328" in out  # b"\xc3\x28"[0:2] 的完整 hex


# ============================================================
# read_terminal_key — EOFError
# ============================================================

def test_read_terminal_key_eof_error_returns_empty(monkeypatch, capsys):
    """read_terminal_key 遇 EOFError → 印 EOFError 訊息 + return ""。"""
    state = _S1State()
    callbacks = _build_callbacks(state)
    read_terminal_key = callbacks["read_terminal_key"]

    def fake_input(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    result = read_terminal_key()
    out = capsys.readouterr().out

    assert result == ""
    assert "EOFError" in out


# ============================================================
# read_customer_input — EOFError
# ============================================================

def test_read_customer_input_eof_error_returns_none(monkeypatch, capsys):
    """read_customer_input 遇 EOFError → 印 EOFError 訊息 + return None。"""
    state = _S1State()
    callbacks = _build_callbacks(state)
    read_customer_input = callbacks["read_customer_input"]

    def fake_input(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    result = read_customer_input(6)
    out = capsys.readouterr().out

    assert result is None
    assert "EOFError" in out
