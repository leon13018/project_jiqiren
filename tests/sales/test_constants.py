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
###      THANK_DELAY=3 / OPENCV_DWELL=1.5
###      （OPENCV_MUTE 2026-05-26 從 12 → 6，12s 對展演節奏太久，
###       6s 已足夠擋掉「同一顧客剛走又走回」）
###      （2026-05-30 L4 重構簡化：移除 L4_MAX_LOOPS — loop_count 機制廢除）
def test_time_constants_match_spec() -> None:
    assert const.WAIT_NO_RESPONSE == 6
    assert const.HAWK_INTERVAL == 12
    assert const.OPENCV_MUTE == 6
    assert const.THANK_DELAY == 3
    assert const.OPENCV_DWELL == 1.5
    assert const.C2_DECISION_TIMEOUT == 6


# ============================================================
# L4 v3 雙計時器常數（2026-05-31）
# 取代 v2「30s 單一 budget + L4_PROMPT_INTERVAL=12s 沒回應重提示」
# 詳見 resources/specs/L4_v3_dual_timer_spec.md
# ============================================================


def test_l4_total_budget_is_36_seconds() -> None:
    """L4_TOTAL_BUDGET v3 雙計時器設計 = 36s（v2 30s → v3 36s = 12 × 3 循環）。

    2026-05-31 v3 雙計時器設計：總 budget 拆成 3 個 QR 刷新循環整數倍，
    倒數視覺對齊循環邊界。耗盡 → forced exit。
    """
    assert const.L4_TOTAL_BUDGET == 36


def test_l4_qr_refresh_interval_is_12_seconds() -> None:
    """L4_QR_REFRESH_INTERVAL = 12s 無條件循環刷新間隔（v3；改名自 L4_PROMPT_INTERVAL）。

    每循環開頭：重印結帳區塊 + 重 speak L4_REMIND_PROMPT（不論顧客是否回應）。
    語意從 v2「沒回應才重提示」改為 v3「無條件循環刷新」。
    """
    assert const.L4_QR_REFRESH_INTERVAL == 12


def test_l4_total_budget_is_integer_multiple_of_qr_refresh_interval() -> None:
    """L4_TOTAL_BUDGET 必須是 L4_QR_REFRESH_INTERVAL 整數倍，倒數視覺對齊循環邊界。

    v3 設計：36 = 12 × 3 → 整個 budget 期間共 3 個 QR 刷新循環，最後一輪
    視覺上 12 → 0 結束於 forced exit（非 v2 30s 最後 6s 不齊感）。
    """
    assert const.L4_TOTAL_BUDGET % const.L4_QR_REFRESH_INTERVAL == 0, (
        f"L4_TOTAL_BUDGET={const.L4_TOTAL_BUDGET} 必須整除 "
        f"L4_QR_REFRESH_INTERVAL={const.L4_QR_REFRESH_INTERVAL}"
    )
    assert const.L4_QR_REFRESH_INTERVAL < const.L4_TOTAL_BUDGET


# ============================================================
# L4 客服模式「請問是否繼續交易？」確認子狀態常數（2026-05-30 二次重構）
# 取代舊版 retry loop + cancel_confirm 雙重 gate 設計：
# 一次性 24s 決策，silent / NO 自動取消，跟 cancel_confirm pattern 對齊。
# ============================================================


def test_l4_c_confirm_timeout_is_24_seconds() -> None:
    """L4_C_CONFIRM_TIMEOUT = 24s 一次性決策 budget（2026-05-31 從 12s 提升 — user 反饋打電話聯絡客服需充裕時間）。

    User 反饋客服需充裕思考時間；24s 比 CANCEL_CONFIRM_TIMEOUT=6s 更寬鬆，
    但比舊版「12s × 多次循環」乾淨單純。
    """
    assert const.L4_C_CONFIRM_TIMEOUT == 24, (
        f"L4_C_CONFIRM_TIMEOUT 應為 24 秒，實際：{const.L4_C_CONFIRM_TIMEOUT}"
    )


def test_l4_c_confirm_prompt_template_includes_seconds_placeholder() -> None:
    """L4_C_CONFIRM_PROMPT_TEMPLATE 含 {seconds} 模板，可 format 入 24 秒倒數值。"""
    assert "{seconds}" in const.L4_C_CONFIRM_PROMPT_TEMPLATE
    rendered = const.L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=12)
    assert "12" in rendered
    # 句末「。」對齊 L3_C2_WARNING_TEMPLATE 風格
    assert rendered.endswith("。")


def test_l4_c_confirm_prompt_template_asks_continue_and_auto_cancel() -> None:
    """文案應問「是否繼續」+ 警告「自動取消」（user 字面）— 對齊新設計語意。"""
    rendered = const.L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=12)
    assert "繼續" in rendered, f"prompt 應問是否繼續，實際：{rendered!r}"
    assert "自動取消" in rendered, f"prompt 應警告自動取消，實際：{rendered!r}"


def test_l4_c_options_prompt_removed() -> None:
    """舊 L4_C_OPTIONS_PROMPT 已移除（被新 template 取代）。"""
    assert not hasattr(const, "L4_C_OPTIONS_PROMPT"), (
        "L4_C_OPTIONS_PROMPT 應被移除（被 L4_C_CONFIRM_PROMPT_TEMPLATE 取代）"
    )


def test_l4_c_confirm_yes_keywords_exist() -> None:
    """KEYWORDS_L4_C_CONFIRM_YES + _STRICT_SHORT 存在且含明確繼續詞。"""
    yes = const.KEYWORDS_L4_C_CONFIRM_YES
    yes_short = const.KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT
    assert isinstance(yes, list) and isinstance(yes_short, list)
    # 「繼續交易」應在 substring 集（user 列）
    assert "繼續交易" in yes
    # 「繼續」短詞在 strict_short（防「繼續努力」substring 誤命中）
    assert "繼續" in yes_short


def test_l4_c_confirm_no_keywords_exist() -> None:
    """KEYWORDS_L4_C_CONFIRM_NO + _STRICT_SHORT 存在且含明確取消詞。"""
    no = const.KEYWORDS_L4_C_CONFIRM_NO
    no_short = const.KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT
    assert isinstance(no, list) and isinstance(no_short, list)
    # 「取消交易」/「不繼續」在 substring 集（user 列）
    assert "取消交易" in no
    assert "不繼續" in no
    # 「取消」/「不」短詞在 strict_short
    assert "取消" in no_short


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


# ============================================================
# 無效數量重問狀態鏈 invalid_qty_reask（2026-06-09 加；spec invalid_qty_reask）
# ============================================================
def test_invalid_qty_constants_present_and_valued() -> None:
    from myProgram.sales.constants import (
        INVALID_QTY_REASK_TIMEOUT, INVALID_QTY_MAX_RESETS,
        INVALID_QTY_CANCEL_CONFIRM_TIMEOUT,
        INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE, INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE,
        INVALID_QTY_ZERO_TEMPLATE,
        INVALID_QTY_UNCLEAR_PREFIX, INVALID_QTY_CANCEL_CONFIRM_PROMPT,
        INVALID_QTY_TIMEOUT_REENTER_PREFIX, INVALID_QTY_CANCEL_REENTER_PREFIX,
        KEYWORDS_INVALID_QTY_CANCEL_TRIGGER, KEYWORDS_INVALID_QTY_CONTINUE,
        KEYWORDS_INVALID_QTY_EXIT,
    )
    assert INVALID_QTY_REASK_TIMEOUT == 12
    assert INVALID_QTY_MAX_RESETS == 2
    assert INVALID_QTY_CANCEL_CONFIRM_TIMEOUT == 6
    assert "{product}" in INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE
    assert "{products}" in INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE and "{details}" in INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE
    assert "{items}" in INVALID_QTY_ZERO_TEMPLATE and "{products}" in INVALID_QTY_ZERO_TEMPLATE
    assert "退出" in KEYWORDS_INVALID_QTY_EXIT
    assert "繼續" in KEYWORDS_INVALID_QTY_CONTINUE
