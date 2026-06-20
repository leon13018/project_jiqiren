"""L0 共通規則 / 常數 / 子例程 BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L0_共通.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）會由 subagent 把這些 scenarios 搬到 tests/sales/test_*.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - L0-CONST / L0-PROD / L0-HAWK → myProgram/sales/constants.py
    - L0-NLU / L0-QTY              → myProgram/sales/nlu.py
    - L0-CART                       → myProgram/sales/cart.py
    - L0-SUB-A                      → myProgram/sales/states.py（callback 注入）

設計約束（選項 C）：
    - 禁 import 廠商 SDK（ActionGroupControl / Board）
    - 對外動作 speak / mute_opencv / tts_is_idle 走 callback 注入
    - 測試用純函式 lambda 收集呼叫紀錄，不用 mock library
"""


# ============================================================
# L0-CONST：時間常數
# ============================================================

## L0-CONST-001
### Scenario: 時間常數值符合規格書定義
### Given 載入 sales 模組的常數
### When 讀取所有時間常數
### Then WAIT_NO_RESPONSE=6 / HAWK_INTERVAL=12 / OPENCV_MUTE=12 /
###      THANK_DELAY=3 / AUTO_CHECKOUT_NOTICE=10 / L4_MAX_LOOPS=6 / OPENCV_DWELL=1.5
def test_time_constants_match_spec() -> None:
    pass


# ============================================================
# L0-PROD：商品列表
# ============================================================

## L0-PROD-001
### Scenario: 商品列表含冰紅茶且價格正確
### Given 載入商品常數
### When 查詢冰紅茶
### Then 原價 30、折扣 0.9、實際價 27 元
def test_product_iced_tea_price_correct() -> None:
    pass


## L0-PROD-002
### Scenario: 商品列表含刮刮樂且價格正確
### Given 載入商品常數
### When 查詢刮刮樂
### Then 原價 200、折扣 0.9、實際價 180 元
def test_product_scratch_card_price_correct() -> None:
    pass


# ============================================================
# L0-HAWK：6 組叫賣術語 + mod 6 輪替
# ============================================================

## L0-HAWK-001
### Scenario: 6 組叫賣術語完整存在
### Given 載入叫賣術語常數
### When 讀取叫賣術語列表
### Then 列表長度為 6 且每組均為非空字串
def test_hawk_slogans_six_entries_all_nonempty() -> None:
    pass


## L0-HAWK-002
### Scenario: 取第 N 輪叫賣術語以 mod 6 輪替
### Given 6 組叫賣術語已載入
### When 分別取第 0 / 1 / 5 / 6 / 7 / 11 / 12 輪
### Then 對應索引為 0 / 1 / 5 / 0 / 1 / 5 / 0（idx mod 6）
def test_hawk_slogan_rotates_by_mod_6() -> None:
    pass


# ============================================================
# L0-NLU：關鍵字白名單分類（依規格判定優先序）
# ============================================================
# 優先序：1.拒絕 → 2.想一下 → 3.結帳 → 4.客服 → 5.商品 → 6.無法判斷
# L4 客服模式專用：繼續 / 退出（僅 L4 客服模式內生效）

## L0-NLU-001
### Scenario: 拒絕意圖任一關鍵字命中即分類為拒絕
### Given 顧客輸入「不要」（拒絕意圖 6 詞之一：不要 / 不用 / 不想 / 不買 / no / nope）
### When 對輸入做意圖分類
### Then 分類結果為「拒絕」
def test_nlu_reject_intent_classified_as_reject() -> None:
    pass


## L0-NLU-002
### Scenario: 想一下意圖任一關鍵字命中即分類為想一下
### Given 顧客輸入「等等」（想一下 8 詞之一：等等 / 等一下 / 稍等 / 想想 / 考慮 / 想一下 / hold on / wait）
### When 對輸入做意圖分類
### Then 分類結果為「想一下」
def test_nlu_think_intent_classified_as_think() -> None:
    pass


## L0-NLU-003
### Scenario: 結帳意圖任一關鍵字命中即分類為結帳
### Given 顧客輸入「結帳」（結帳 9 詞之一：結帳 / 買單 / 付款 / 好了 / 就這樣 / 可以了 / 沒了 / 沒有了 / 夠了）
### When 對輸入做意圖分類
### Then 分類結果為「結帳」
def test_nlu_checkout_intent_classified_as_checkout() -> None:
    pass


## L0-NLU-004
### Scenario: 想找客服意圖任一關鍵字命中即分類為客服
### Given 顧客輸入「客服」（客服 5 詞之一：客服 / 聯絡 / 聯繫 / contact / 服務）
### When 對輸入做意圖分類
### Then 分類結果為「客服」
def test_nlu_service_intent_classified_as_service() -> None:
    pass


## L0-NLU-005
### Scenario: 商品冰紅茶任一關鍵字命中即分類為點到冰紅茶
### Given 顧客輸入「冰紅茶」（冰紅茶 4 詞之一：紅茶 / 冰紅茶 / hong cha / tea）
### When 對輸入做意圖分類
### Then 分類結果為「商品:冰紅茶」
def test_nlu_iced_tea_keyword_classified_as_product_iced_tea() -> None:
    pass


## L0-NLU-006
### Scenario: 商品刮刮樂任一關鍵字命中即分類為點到刮刮樂
### Given 顧客輸入「刮刮樂」（刮刮樂 5 詞之一：刮刮樂 / 刮刮 / 彩券 / lottery / scratch）
### When 對輸入做意圖分類
### Then 分類結果為「商品:刮刮樂」
def test_nlu_scratch_card_keyword_classified_as_product_scratch_card() -> None:
    pass


## L0-NLU-007
### Scenario: 無任何白名單命中時分類為無法判斷
### Given 顧客輸入「今天天氣很好」（無白名單命中）
### When 對輸入做意圖分類
### Then 分類結果為「無法判斷」
def test_nlu_no_keyword_match_classified_as_unknown() -> None:
    pass


## L0-NLU-008
### Scenario: 同時含拒絕與商品時依優先序判定為拒絕
### Given 顧客輸入「我不要冰紅茶了」（同時含拒絕 + 商品關鍵字）
### When 對輸入做意圖分類
### Then 分類結果為「拒絕」（拒絕優先序高於商品）
def test_nlu_reject_priority_over_product() -> None:
    pass


## L0-NLU-009
### Scenario: 夠了歸類為結帳意圖（非拒絕）
### Given 顧客輸入「夠了」（2026-05-24 終審：歸結帳，不歸拒絕）
### When 對輸入做意圖分類
### Then 分類結果為「結帳」
def test_nlu_gou_le_classified_as_checkout_not_reject() -> None:
    pass


## L0-NLU-010
### Scenario: 沒了 / 沒有了歸類為結帳意圖
### Given 顧客輸入「沒了」或「沒有了」
### When 對輸入做意圖分類
### Then 分類結果均為「結帳」
def test_nlu_mei_le_classified_as_checkout() -> None:
    pass


## L0-NLU-011
### Scenario: L4 客服模式內繼續關鍵字分類為繼續交易
### Given 當前處於 L4 客服模式，顧客輸入「繼續」（5 詞之一：繼續 / 接著 / 繼續買 / 繼續交易 / continue）
### When 對輸入做意圖分類（傳入 mode=l4_service）
### Then 分類結果為「繼續交易」
def test_nlu_continue_in_l4_service_mode_classified_as_continue() -> None:
    pass


## L0-NLU-012
### Scenario: L4 客服模式內退出關鍵字分類為退出交易
### Given 當前處於 L4 客服模式，顧客輸入「退出」（6 詞之一：退出 / 取消 / 離開 / 算了 / 不買了 / exit）
### When 對輸入做意圖分類（傳入 mode=l4_service）
### Then 分類結果為「退出交易」
def test_nlu_exit_in_l4_service_mode_classified_as_exit() -> None:
    pass


## L0-NLU-013
### Scenario: 非 L4 客服模式內繼續 / 退出關鍵字不生效
### Given 當前為 L2 一般詢問模式，顧客輸入「繼續」或「退出」
### When 對輸入做意圖分類（mode=normal）
### Then 分類結果為「無法判斷」（繼續 / 退出僅於 L4 客服模式內生效）
def test_nlu_continue_exit_outside_l4_service_classified_as_unknown() -> None:
    pass


# ============================================================
# L0-QTY：數量解析
# ============================================================

## L0-QTY-001
### Scenario: 中文數字命中時取對應數值
### Given 顧客輸入「冰紅茶兩個」
### When 解析數量
### Then 數量為 2
def test_qty_chinese_two_returns_2() -> None:
    pass


## L0-QTY-002
### Scenario: 阿拉伯數字命中時取首個正整數
### Given 顧客輸入「3 杯冰紅茶」
### When 解析數量
### Then 數量為 3
def test_qty_arabic_3_returns_3() -> None:
    pass


## L0-QTY-003
### Scenario: 無任何數字命中時預設為 1
### Given 顧客輸入「我要刮刮樂」（無數字）
### When 解析數量
### Then 數量為 1（預設）
def test_qty_no_number_defaults_to_1() -> None:
    pass


## L0-QTY-004
### Scenario: 中文一字命中時數量為 1
### Given 顧客輸入「給我一杯紅茶」
### When 解析數量
### Then 數量為 1
def test_qty_chinese_one_returns_1() -> None:
    pass


## L0-QTY-005
### Scenario: 阿拉伯多位數命中
### Given 顧客輸入「我要 5 個刮刮樂」
### When 解析數量
### Then 數量為 5
def test_qty_arabic_5_returns_5() -> None:
    pass


## L0-QTY-006
### Scenario: 中文十命中時數量為 10
### Given 顧客輸入「十杯冰紅茶」
### When 解析數量
### Then 數量為 10
def test_qty_chinese_ten_returns_10() -> None:
    pass


## L0-QTY-007
### Scenario: 中文異體字（壹 / 貳 / 參 / 拾）命中對應數量
### Given 顧客輸入「我要壹杯」 / 「貳杯」 / 「參個」 / 「拾杯」
### When 解析數量
### Then 對應數量為 1 / 2 / 3 / 10
def test_qty_chinese_variants_recognized() -> None:
    pass


## L0-QTY-008
### Scenario: 阿拉伯數字 0 不生效，回退預設 1
### Given 顧客輸入「我要 0 杯」（規格定義：>0 時生效，否則預設 1）
### When 解析數量
### Then 數量為 1（預設）
def test_qty_arabic_0_falls_back_to_default_1() -> None:
    pass


## L0-QTY-009
### Scenario: 同時含阿拉伯與中文數字時阿拉伯優先
### Given 顧客輸入「我要 3 杯，給我貳個」（同時含 3 與貳）
### When 解析數量
### Then 數量為 3（阿拉伯數字優先於中文）
def test_qty_arabic_priority_over_chinese() -> None:
    pass


# ============================================================
# L0-CART：購物車生命週期
# ============================================================

## L0-CART-001
### Scenario: 新建 cart 為空容器
### Given 呼叫 cart 工廠新建一個 cart
### When 檢查內容
### Then cart 為空（無任何商品）
def test_cart_new_is_empty() -> None:
    pass


## L0-CART-002
### Scenario: 加入單一商品後 cart 含該商品與數量
### Given 一個空 cart
### When 加入冰紅茶 ×1
### Then cart 為 {冰紅茶: 1}
def test_cart_add_single_product() -> None:
    pass


## L0-CART-003
### Scenario: 重複加入同商品時數量累加而非 append 新條目
### Given cart 已有冰紅茶 ×1
### When 再加入冰紅茶 ×1
### Then cart 為 {冰紅茶: 2}（同商品累加，不新增條目）
def test_cart_add_same_product_accumulates_quantity() -> None:
    pass


## L0-CART-004
### Scenario: 單品總額正確計算（含九折）
### Given cart 為 {冰紅茶: 2}
### When 計算總額
### Then 總額為 54 元（27 × 2）
def test_cart_total_single_product_correct() -> None:
    pass


## L0-CART-005
### Scenario: 多品總額正確計算
### Given cart 為 {冰紅茶: 1, 刮刮樂: 1}
### When 計算總額
### Then 總額為 207 元（27 + 180）
def test_cart_total_multiple_products_correct() -> None:
    pass


## L0-CART-006
### Scenario: 清空 cart 後容器為空
### Given cart 為 {冰紅茶: 2, 刮刮樂: 1}
### When 清空 cart
### Then cart 為空（無任何商品）
def test_cart_clear_empties_container() -> None:
    pass


# ============================================================
# L0-SUB-A：「回 L1 叫賣」共通子例程
# ============================================================
# 規格步驟（見 L0_共通.md）：
#   1. 觸發後立即屏蔽 OpenCV OPENCV_MUTE (12s) 秒（不偵測 / 不叫賣）
#   2. OPENCV_MUTE 秒後恢復 OpenCV + 立即播第 1 組叫賣
#   3. 後續每 HAWK_INTERVAL (12s) 秒換下一組，依 6 組 mod 6 輪流
# 設計：對外動作以 callback 注入（mute_opencv / unmute_opencv / speak / tts_is_idle）

## L0-SUB-A-001
### Scenario: 子例程觸發後立即屏蔽 OpenCV
### Given 子例程 A 已準備好（callback 注入）
### When 觸發子例程 A
### Then mute_opencv 被呼叫一次（屏蔽生效）
def test_sub_a_mutes_opencv_on_trigger() -> None:
    pass


## L0-SUB-A-002
### Scenario: OPENCV_MUTE 秒後 OpenCV 恢復且立即播第 1 組叫賣
### Given 子例程 A 已觸發，模擬時間推進
### When 經過 OPENCV_MUTE (12) 秒
### Then unmute_opencv 被呼叫且第 1 組叫賣（索引 0）被 speak
def test_sub_a_unmute_and_first_hawk_after_mute_window() -> None:
    pass


## L0-SUB-A-003
### Scenario: 第一輪叫賣後每 HAWK_INTERVAL 秒換下一組
### Given 子例程 A 已播第 1 組叫賣
### When 再經過 HAWK_INTERVAL (12) 秒
### Then 第 2 組叫賣（索引 1）被 speak
def test_sub_a_advances_to_next_hawk_after_interval() -> None:
    pass


## L0-SUB-A-004
### Scenario: 連續輪替超過 6 組時以 mod 6 回到第 1 組
### Given 子例程 A 已連續播第 1~6 組叫賣
### When 觸發第 7 次叫賣
### Then 第 1 組叫賣（索引 0，6 mod 6）再次被 speak
def test_sub_a_wraps_around_after_six_hawks() -> None:
    pass
