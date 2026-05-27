"""test_main_decode_error.py — 測試 myProgram/main.py 的 input() decode error 處理。

歷史：
    2026-05-27 Wave 4 hotfix 3 加 noisy UnicodeDecodeError debug（含 raw hex），
    使用者於 Pi 端截到 hex 後定位根因為 Python stdin TextIOWrapper buffer 殘留
    partial UTF-8 byte 與新 read 序列互動異常（非 locale 設定問題）。修補方向：
    main() 內 sys.stdin.reconfigure(encoding='utf-8', errors='replace')，bad byte
    自動換 U+FFFD 不再 raise → UnicodeDecodeError 路徑已是 dead code 已移除。
    本檔僅保留 EOFError 處理測試（stdin 真被關閉時的 safety net）。

覆蓋 2 個 case：
    1. read_terminal_key + EOFError → 印 EOFError 訊息 + return ""
    2. read_customer_input + EOFError → 印 EOFError 訊息 + return None

設計：直接從 myProgram.main 取出 _build_callbacks 內封閉的 read_terminal_key /
      read_customer_input；用 monkeypatch.setattr("builtins.input", ...) 模擬 input()
      raise EOFError；capsys 捕 stdout 斷言訊息內容。
"""

from myProgram.main import _S1State, _build_callbacks


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
