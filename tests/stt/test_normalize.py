"""_normalize_transcript 單元測試 — 去頭尾標點（strict-short 比對前置防線）。"""
import pytest

from myProgram.stt import _normalize_transcript


@pytest.mark.parametrize("raw, expected", [
    ("我要紅茶兩杯。", "我要紅茶兩杯"),      # 句尾全形句號
    ("好。", "好"),                          # strict-short 核心案例
    ("  結帳！  ", "結帳"),                  # 空白 + 驚嘆號
    ("，嗯，好的，", "嗯，好的"),            # 頭尾標點去除、句中保留
    ("紅茶 2 杯", "紅茶 2 杯"),              # 無標點原樣
    ("。！？", ""),                          # 全標點 → 空字串
    ("", ""),                                # 空輸入
])
def test_normalize_transcript(raw, expected):
    assert _normalize_transcript(raw) == expected
