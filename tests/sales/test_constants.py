"""test_constants.py — 測試 myProgram/sales/constants.py。

對應 BDD scenarios：
    - L0-CONST-001：時間常數值符合規格書定義
    - L0-PROD-001：商品列表含冰紅茶且價格正確
    - L0-PROD-002：商品列表含刮刮樂且價格正確
    - L0-HAWK-001：6 組叫賣術語完整存在
    - L0-HAWK-002：取第 N 輪叫賣術語以 mod 6 輪替
"""

import myProgram.sales.constants as const


# ============================================================
# L0-CONST-001
# ============================================================

## L0-CONST-001
### Scenario: 時間常數值符合規格書定義
### Given 載入 sales 模組的常數
### When 讀取所有時間常數
### Then WAIT_NO_RESPONSE=6 / HAWK_INTERVAL=12 / OPENCV_MUTE=12 /
###      THANK_DELAY=3 / AUTO_CHECKOUT_NOTICE=10 / L4_MAX_LOOPS=6 / OPENCV_DWELL=1.5
def test_time_constants_match_spec() -> None:
    assert const.WAIT_NO_RESPONSE == 6
    assert const.HAWK_INTERVAL == 12
    assert const.OPENCV_MUTE == 12
    assert const.THANK_DELAY == 3
    assert const.AUTO_CHECKOUT_NOTICE == 10
    assert const.L4_MAX_LOOPS == 6
    assert const.OPENCV_DWELL == 1.5


# ============================================================
# L0-PROD-001
# ============================================================

## L0-PROD-001
### Scenario: 商品列表含冰紅茶且價格正確
### Given 載入商品常數
### When 查詢冰紅茶
### Then 原價 30、折扣 0.9、實際價 27 元
def test_product_iced_tea_price_correct() -> None:
    tea = const.PRODUCTS["冰紅茶"]
    assert tea["原價"] == 30
    assert tea["折扣"] == 0.9
    assert tea["實際"] == 27


# ============================================================
# L0-PROD-002
# ============================================================

## L0-PROD-002
### Scenario: 商品列表含刮刮樂且價格正確
### Given 載入商品常數
### When 查詢刮刮樂
### Then 原價 200、折扣 0.9、實際價 180 元
def test_product_scratch_card_price_correct() -> None:
    sc = const.PRODUCTS["刮刮樂"]
    assert sc["原價"] == 200
    assert sc["折扣"] == 0.9
    assert sc["實際"] == 180


# ============================================================
# L0-HAWK-001
# ============================================================

## L0-HAWK-001
### Scenario: 6 組叫賣術語完整存在
### Given 載入叫賣術語常數
### When 讀取叫賣術語列表
### Then 列表長度為 6 且每組均為非空字串
def test_hawk_slogans_six_entries_all_nonempty() -> None:
    assert len(const.HAWK_SLOGANS) == 6
    for slogan in const.HAWK_SLOGANS:
        assert isinstance(slogan, str)
        assert len(slogan) > 0


# ============================================================
# L0-HAWK-002
# ============================================================

## L0-HAWK-002
### Scenario: 取第 N 輪叫賣術語以 mod 6 輪替
### Given 6 組叫賣術語已載入
### When 分別取第 0 / 1 / 5 / 6 / 7 / 11 / 12 輪
### Then 對應索引為 0 / 1 / 5 / 0 / 1 / 5 / 0（idx mod 6）
def test_hawk_slogan_rotates_by_mod_6() -> None:
    cases = [
        (0, 0),
        (1, 1),
        (5, 5),
        (6, 0),
        (7, 1),
        (11, 5),
        (12, 0),
    ]
    for n, expected_idx in cases:
        actual = const.HAWK_SLOGANS[n % 6]
        expected = const.HAWK_SLOGANS[expected_idx]
        assert actual == expected, (
            f"第 {n} 輪應為索引 {expected_idx}，但 HAWK_SLOGANS[{n} % 6] 不等於 HAWK_SLOGANS[{expected_idx}]"
        )
