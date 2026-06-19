"""keyterm 詞表與 DEEPGRAM_URL 編碼測試（純模組常數，無網路無音訊）。"""
from urllib.parse import quote

from myProgram.stt import DEEPGRAM_URL, KEYTERMS, _build_deepgram_url


def test_every_keyterm_percent_encoded_in_url():
    # 每個詞以 percent-encoded 形式出現在 URL（中文必須 encode）
    for kt in KEYTERMS:
        assert f"keyterm={quote(kt)}" in DEEPGRAM_URL


def test_raw_chinese_not_in_url():
    # 強制 encode：裸中文不得出現在 URL（否則 websockets handshake 會壞）
    assert "三瓶" not in DEEPGRAM_URL
    assert "冰紅茶" not in DEEPGRAM_URL


def test_table_covers_critical_and_excludes_shangpin():
    assert "三瓶" in KEYTERMS          # 原始誤辨識回歸案例
    assert "冰紅茶" in KEYTERMS
    assert "刮刮樂" in KEYTERMS
    assert "商品" not in KEYTERMS       # 反例不可入清單（會反向 boost 加劇 bug）


def test_full_one_to_ten_bottles_and_sheets():
    for n in "一兩三四五六七八九十":
        assert f"{n}瓶" in KEYTERMS
        assert f"{n}張" in KEYTERMS


def test_base_params_preserved():
    # keyterm 是 append，既有參數不得被破壞
    assert "model=nova-3" in DEEPGRAM_URL
    assert "language=zh-TW" in DEEPGRAM_URL
    assert "endpointing=300" in DEEPGRAM_URL


def test_endpointing_default_300_in_built_url():
    assert "endpointing=300" in _build_deepgram_url(300)


def test_endpointing_override_reflected_in_built_url():
    url = _build_deepgram_url(200)
    assert "endpointing=200" in url
    assert "endpointing=300" not in url


def test_built_url_still_carries_keyterms_and_base_params():
    url = _build_deepgram_url(250)
    assert "model=nova-3" in url and "language=zh-TW" in url
    assert "keyterm=" in url  # keyterm append 未被破壞
