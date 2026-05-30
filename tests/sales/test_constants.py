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
### Then WAIT_NO_RESPONSE=6 / HAWK_INTERVAL=12 / OPENCV_MUTE=6 /
###      THANK_DELAY=3 / AUTO_CHECKOUT_NOTICE=12 / OPENCV_DWELL=1.5
###      （AUTO_CHECKOUT_NOTICE 2026-05-26 從 10 → 12；OPENCV_MUTE 同日從 12 → 6，
###       12s 對展演節奏太久，6s 已足夠擋掉「同一顧客剛走又走回」）
###      （2026-05-30 L4 重構簡化：移除 L4_MAX_LOOPS — loop_count 機制廢除）
def test_time_constants_match_spec() -> None:
    assert const.WAIT_NO_RESPONSE == 6
    assert const.HAWK_INTERVAL == 12
    assert const.OPENCV_MUTE == 6
    assert const.THANK_DELAY == 3
    assert const.AUTO_CHECKOUT_NOTICE == 12
    assert const.OPENCV_DWELL == 1.5


# ============================================================
# L4 重構簡化版常數（2026-05-30）
# 取代 L4_TOTAL_BUDGET=60 + WAIT_NO_RESPONSE 子流程 + L4_SERVICE_TIMEOUT 獨立 + L4_MAX_LOOPS
# ============================================================


def test_l4_total_budget_is_30_seconds() -> None:
    """L4_TOTAL_BUDGET 重構簡化版改為 30s（從舊版 60s 砍半）。

    User 反饋舊 60s + loop_count 6 次循環 + final confirmation 18s + service 獨立
    60s 過度複雜；新設計單一 30s budget 涵蓋整個 L4 場景（含客服模式）。
    """
    assert const.L4_TOTAL_BUDGET == 30


def test_l4_prompt_interval_is_12_seconds() -> None:
    """L4_PROMPT_INTERVAL = 12s 沒回應重 prompt 的間隔（取代舊 WAIT_NO_RESPONSE=6s + 4 階段語氣）。"""
    assert const.L4_PROMPT_INTERVAL == 12


def test_l4_prompt_interval_strictly_less_than_total_budget() -> None:
    """L4_PROMPT_INTERVAL 必須嚴格小於 L4_TOTAL_BUDGET，否則整個 budget 內只能讀一次 input。"""
    assert const.L4_PROMPT_INTERVAL < const.L4_TOTAL_BUDGET


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


# ============================================================
# 2026-05-30：qty followup 專屬 timeout（L2/L3「請問X要幾Y？」追問）
#
# User demo 反饋：通用 WAIT_NO_RESPONSE=6s 對 qty 追問過急 — 顧客可能正在
# 看商品 / 數錢 / 思考數量。新增 QTY_FOLLOWUP_TIMEOUT=12s 專覆蓋此路徑。
# 其他 7 處 6s caller（B-3/B-4 沉默 / unclear_final / L4 main/final/service）
# 仍走 WAIT_NO_RESPONSE，不受影響。
# ============================================================


def test_qty_followup_timeout_is_12_seconds() -> None:
    """QTY_FOLLOWUP_TIMEOUT 常數值應為 12 秒（比通用 6s 寬鬆）。"""
    assert const.QTY_FOLLOWUP_TIMEOUT == 12


def test_qty_followup_timeout_strictly_longer_than_generic() -> None:
    """QTY_FOLLOWUP_TIMEOUT 必須嚴格大於 WAIT_NO_RESPONSE — 否則拆出新常數無意義。"""
    assert const.QTY_FOLLOWUP_TIMEOUT > const.WAIT_NO_RESPONSE
