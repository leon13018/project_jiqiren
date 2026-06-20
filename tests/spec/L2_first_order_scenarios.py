"""L2 詢問需求（顧客互動 — 初次點單）BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L2.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）由 subagent 把這些 scenarios 搬到 tests/sales/test_states.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - 全部 14 scenarios → myProgram/sales/states.py（加 run_l2 + 對應私有函式）
    - 可能擴：myProgram/sales/constants.py（追加 L2 語音字串常數）

設計約束（選項 C，沿用 L0/L1 規範）：
    - 禁 import 廠商 SDK（ActionGroupControl / Board）
    - 對外動作走 callback 注入：
        - speak(text) — 語音
        - do_action(name) — 動作（規格 TBD，stub 可 no-op）
        - print_terminal(text) — 客服印電話
        - read_customer_input(timeout: float) -> str | None — 等顧客回應；超時回 None
        - 觸發子例程 A：由 run_l2 return 值或 callback 通知主迴圈
    - 測試用純函式 lambda + inline class stub，不用 mock library

L2 與既有層的關係：
    - L1 鏈路 C 顧客觸控「開始點餐」後 → 進 L2
    - L2 鏈路 A 拒絕後 → 套 L0 子例程 A 回 L1
    - L2 鏈路 C 點到商品 → cart 加商品 → 進 L3
    - think_count 屬 L2 內部 state：ENTRY init 0，鏈路 A / C 觸發時 reset 0

判定優先序（L2 跳過「結帳意圖」）：
    1. 6s 超時 → A
    2. 拒絕 → A
    3. 想一下 → B-3
    4. ~~結帳~~（不適用 L2）
    5. 客服 → B-2
    6. 商品 → C
    7. 都沒命中 → B-1
"""


# ============================================================
# L2-ENTRY：進入時動作
# ============================================================

## L2-ENTRY-001
### Scenario: 進入 L2 即播詢問語音並初始化 think_count
### Given 從 L1 叫賣模式 顧客觸控「開始點餐」進入 L2
### When run_l2 啟動執行進入時動作
### Then 系統 speak「您好，請問需要購買什麼東西嗎？」且 think_count 初始化為 0，
###      開始等待顧客回應最多 WAIT_NO_RESPONSE（6）秒
def test_l2_entry_speaks_greeting_and_inits_think_count() -> None:
    pass


# ============================================================
# L2-A：拒絕鏈路（兩種 trigger 都走相同退出）
# ============================================================

## L2-A-001
### Scenario: DNC_TIMEOUT 秒無回應觸發回 L1 叫賣（非「拒絕」語意）
### Given L2 進入時動作完成（cart 空），正在等待顧客回應
### When 經過 DNC_TIMEOUT（12）秒仍無任何顧客輸入
### Then 系統 speak L2_TIMEOUT_TO_HAWK_VOICE「由於顧客沒有回應，我將繼續叫賣模式」
###      並回 L1 叫賣（enter_hawk）
### Note 2026-05-26 修：原規格 6s + 「謝謝光臨」會誤導旁人（顧客只是沒回應而非拒絕）；
###      改 12s + 中性提示，僅顧客明確拒絕意圖（L2-A-002）才講「謝謝光臨」
def test_l2_a_timeout_no_response_triggers_reject_and_enter_hawk() -> None:
    pass


## L2-A-002
### Scenario: 顧客回應拒絕關鍵字觸發鏈路 A
### Given L2 進入時動作完成，正在等待顧客回應
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」/「不買」/「no」之一）
### Then 系統 speak「謝謝光臨」並回 L1 叫賣（enter_hawk）
def test_l2_a_reject_keyword_triggers_enter_hawk() -> None:
    pass


# ============================================================
# L2-B-1：無法判斷（鏈路 B 子情況）
# ============================================================

## L2-B-1-001
### Scenario: 顧客回應不命中任何白名單時走 B-1 並留在 L2 重新等待
### Given L2 等待顧客回應中
### When 顧客輸入「今天天氣很好」（不命中拒絕 / 想一下 / 客服 / 商品任一類別）
### Then 系統 speak「不好意思我聽不太懂，請問要買什麼呢？或者您想聯繫客服？」，
###      保持在 L2 重新進入等待狀態（最多 WAIT_NO_RESPONSE 秒）
def test_l2_b1_unknown_input_speaks_clarification_and_stays_in_l2() -> None:
    pass


# ============================================================
# L2-B-2：想找客服（鏈路 B 子情況）
# ============================================================

## L2-B-2-001
### Scenario: 顧客回應客服關鍵字觸發 B-2 印電話後自動回 L2 循環
### Given L2 等待顧客回應中
### When 顧客輸入命中客服意圖關鍵字（如「客服」/「聯繫」之一）
### Then 終端印商家客服電話（SERVICE_PHONE），無等待 / 無確認，
###      自動回 L2 循環詢問狀態（對比 L4 客服需手動選退出 / 繼續）
def test_l2_b2_service_keyword_prints_phone_and_returns_to_l2_loop() -> None:
    pass


# ============================================================
# L2-B-3：想一下（鏈路 B 子情況，含 think_count 狀態機）
# ============================================================

## L2-B-3-001
### Scenario: 第 1 次想一下 think_count 自 0 增至 1 並進入沉默等待
### Given L2 think_count == 0，等待顧客回應中
### When 顧客輸入命中想一下意圖關鍵字（如「等等」/「稍等」之一）
### Then think_count 變為 1，進入沉默等待 WAIT_NO_RESPONSE（6）秒（不發出任何語音）
def test_l2_b3_first_think_increments_count_and_enters_silence() -> None:
    pass


## L2-B-3-002
### Scenario: 沉默等待期間顧客有回應立即重跑判定優先序
### Given L2 處於想一下沉默期內（think_count == 1，sleep 中）
### When 6 秒內顧客輸入「冰紅茶」（命中商品）
### Then 跳出沉默等待立即處理該回應，重跑判定 1-7 → 走鏈路 C（加 cart 後進 L3）
def test_l2_b3_silence_interrupted_by_response_reruns_dispatch() -> None:
    pass


## L2-B-3-003
### Scenario: 沉默等待 6 秒滿無回應時 speak 重問語音並回主等待
### Given L2 處於想一下沉默期（think_count == 1）
### When 經過 WAIT_NO_RESPONSE（6）秒仍無顧客回應
### Then 系統 speak「請問需要購買什麼東西嗎？」（L2 特有重問措辭，未加單版）
###      並回到 L2 主等待循環（再次等待 WAIT_NO_RESPONSE 秒，timer 從 0 重起）
def test_l2_b3_silence_timeout_reasks_and_resumes_main_loop() -> None:
    pass


## L2-B-3-004
### Scenario: 第 2 次想一下 think_count 增至 2 但仍走沉默不轉拒絕
### Given L2 已走過 1 次 B-3，think_count == 1，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 2，再次進入沉默等待 6 秒（仍 < 3，未觸發鏈路 A 拒絕）
def test_l2_b3_second_think_still_silence_below_threshold() -> None:
    pass


## L2-B-3-005
### Scenario: 第 3 次想一下 think_count 達 3 跳過沉默走鏈路 A 拒絕
### Given L2 已走過 2 次 B-3，think_count == 2，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 3，**跳過 6s 沉默**，speak 拒絕語音
###      （建議「看來您還在猶豫，謝謝光臨歡迎下次再來」），
###      套用 L0 子例程 A 回 L1（cart 未建立、無需清空）
def test_l2_b3_third_think_skips_silence_and_triggers_reject() -> None:
    pass


# ============================================================
# L2-C：點到商品（轉 L3）
# ============================================================

## L2-C-001
### Scenario: 顧客回應冰紅茶關鍵字加 1 杯入 cart 並進 L3
### Given L2 等待顧客回應中，cart 為空
### When 顧客輸入「冰紅茶」（命中商品 — 冰紅茶，無數量描述）
### Then 數量解析為 1（預設），cart = {冰紅茶: 1}，
###      系統 speak 加入購物車語音，轉到 L3
def test_l2_c_iced_tea_default_quantity_adds_cart_and_goes_l3() -> None:
    pass


## L2-C-002
### Scenario: 顧客回應含數量的商品輸入正確解析數量並加入 cart
### Given L2 等待顧客回應中，cart 為空
### When 顧客輸入「冰紅茶兩個」（命中商品 — 冰紅茶 + 中文數量「兩」）
### Then 數量解析為 2，cart = {冰紅茶: 2}，轉到 L3
def test_l2_c_iced_tea_with_chinese_quantity_parses_and_adds() -> None:
    pass


## L2-C-003
### Scenario: 顧客回應刮刮樂關鍵字加入 cart 並進 L3
### Given L2 等待顧客回應中，cart 為空
### When 顧客輸入「刮刮樂」（命中商品 — 刮刮樂）
### Then 數量解析為 1，cart = {刮刮樂: 1}，轉到 L3
def test_l2_c_scratch_card_adds_cart_and_goes_l3() -> None:
    pass


# ============================================================
# L2-PRIO：判定優先序特例（L2 跳過結帳意圖）
# ============================================================

## L2-PRIO-001
### Scenario: 顧客在 L2 說結帳關鍵字 L2 跳過該意圖並走 B-1 無法判斷
### Given L2 等待顧客回應中，cart 未建立
### When 顧客輸入「結帳」（NLU 分類器會回「結帳」，但 L2 規格跳過此類別）
### Then L2 dispatch 視為無法判斷 → 走鏈路 B-1（speak「不好意思我聽不太懂」+ 留 L2）
###      （規格依據：L2「判定優先序」段第 4 條 ~~結帳意圖~~ 不適用 L2）
def test_l2_prio_checkout_intent_in_l2_falls_through_to_b1() -> None:
    pass
