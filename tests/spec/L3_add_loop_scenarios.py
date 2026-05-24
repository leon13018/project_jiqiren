"""L3 加單迴圈（顧客互動 — 詢問額外需求）BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L3.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）由 subagent 把這些 scenarios 搬到 tests/sales/test_states.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - 全部 18 scenarios → myProgram/sales/states.py（加 run_l3 + 對應私有函式）
    - 可能擴：myProgram/sales/constants.py（追加 L3 語音字串常數）

設計約束（選項 C，沿用 L0-L2 規範）：
    - 禁 import 廠商 SDK
    - 對外動作走 callback 注入（沿用 L2 set + 不需新增）：
        - speak / do_action / print_terminal / read_customer_input(timeout) / cart / think_count
    - 觸發子例程 A：由 run_l3 return ("L1_via_subroutine_a", 0)
    - 進 L4：由 run_l3 return ("L4", 0)
    - 測試用純函式 lambda + inline class stub，不用 mock library

L3 與 L2 的關鍵差異（重要！）：
    1. 6s 超時 → **C-2 第一段**（不是 A 拒絕）— L2 的 6s 超時是 A 拒絕
    2. L3 dispatcher 用全 6 步白名單（不跳過任何）— L2 跳過結帳
    3. think_count == 3 → **走 C-2 第二段邏輯**（cart 有商品，要結帳）— L2 是走 A 拒絕
    4. 鏈路 A 拒絕 → **清空 cart**（整單作廢）
    5. B-3 加單後 → **保持 L3**（L2 的 C 點商品是進 L3，差異在「進 vs 留」）
    6. L3 跳過項：「繼續/退出」（L4 客服專用詞）→ B-1 無法判斷

判定優先序（L3 用全 6 步）：
    1. 6s 超時 → C-2 第一段
    2. 拒絕 → A
    3. 想一下 → B-4
    4. 結帳意圖 → C-1
    5. 客服 → B-2
    6. 商品 → B-3（加單繼續）
    7. 都沒命中 → B-1
"""


# ============================================================
# L3-ENTRY：進入時動作
# ============================================================

## L3-ENTRY-001
### Scenario: 進入 L3 即播詢問語音並初始化 think_count
### Given 從 L2 鏈路 C 加單完成進入 L3
### When run_l3 啟動執行進入時動作
### Then 系統 speak「請問還有額外需要購買的嗎？」且 think_count 初始化為 0，
###      開始等待顧客回應最多 WAIT_NO_RESPONSE（6）秒
def test_l3_entry_speaks_followup_and_inits_think_count() -> None:
    pass


# ============================================================
# L3-A：拒絕鏈路（不含 6s timeout）
# ============================================================

## L3-A-001
### Scenario: 顧客回應拒絕關鍵字觸發鏈路 A 清空 cart 並套子例程 A
### Given L3 等待中，cart 已含商品（從 L2 帶來，例：{冰紅茶: 1}）
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」/「取消」/「不買了」之一）
### Then 系統 speak 拒絕語音（建議「好的，取消這次購物，謝謝光臨」），
###      **清空 cart**（整單作廢），套用 L0 子例程 A 回 L1 叫賣
###      注意：L3-A 不含 6s timeout trigger（差異於 L2-A；timeout 在 L3 走 C-2）
def test_l3_a_reject_keyword_clears_cart_and_triggers_subroutine_a() -> None:
    pass


# ============================================================
# L3-B-1：無法判斷
# ============================================================

## L3-B-1-001
### Scenario: 顧客回應不命中任何白名單時走 B-1 並留在 L3 重新等待
### Given L3 等待中
### When 顧客輸入「今天天氣很好」（不命中任何白名單）
### Then 系統 speak「不好意思我聽不太懂，請問還要買什麼呢？或者您想聯繫客服？」
###      （L3 特有措辭，含「還要」），保持在 L3 重新進入等待狀態
def test_l3_b1_unknown_input_speaks_clarification_and_stays_in_l3() -> None:
    pass


# ============================================================
# L3-B-2：想找客服
# ============================================================

## L3-B-2-001
### Scenario: 顧客回應客服關鍵字觸發 B-2 印電話後自動回 L3 循環
### Given L3 等待中
### When 顧客輸入命中客服關鍵字（如「客服」/「聯繫」之一）
### Then 終端印商家客服電話（SERVICE_PHONE），無等待 / 無確認，
###      自動回 L3 循環狀態（對比 L4 客服需手動選退出 / 繼續）
def test_l3_b2_service_keyword_prints_phone_and_returns_to_l3_loop() -> None:
    pass


# ============================================================
# L3-B-3：點到商品（額外加單，保持在 L3）
# ============================================================

## L3-B-3-001
### Scenario: 顧客回應商品關鍵字加 1 件入既有 cart 並保持在 L3
### Given L3 等待中，cart 已含 {冰紅茶: 1}（從 L2 帶來）
### When 顧客輸入「刮刮樂」（命中商品 — 刮刮樂，無數量描述）
### Then 數量解析為 1（預設），cart 加入刮刮樂 = {冰紅茶: 1, 刮刮樂: 1}，
###      系統 speak「請問還需要什麼東西嗎？」（L3 加單後重問措辭），保持在 L3
def test_l3_b3_product_default_quantity_adds_cart_and_stays_in_l3() -> None:
    pass


## L3-B-3-002
### Scenario: 顧客回應含數量的商品輸入正確解析並累加到 cart
### Given L3 等待中，cart = {冰紅茶: 1}
### When 顧客輸入「冰紅茶兩個」（命中商品 + 中文數量「兩」= 2）
### Then 數量解析為 2，cart 同商品累加 = {冰紅茶: 3}，保持在 L3
def test_l3_b3_product_with_quantity_accumulates_existing() -> None:
    pass


# ============================================================
# L3-B-4：想一下（think_count 狀態機，第 3 次走 C-2 第二段）
# ============================================================

## L3-B-4-001
### Scenario: 第 1 次想一下 think_count 自 0 增至 1 並進入沉默等待
### Given L3 think_count == 0，等待顧客回應中
### When 顧客輸入命中想一下意圖關鍵字（如「等等」/「稍等」之一）
### Then think_count 變為 1，進入沉默等待 WAIT_NO_RESPONSE（6）秒（不發任何語音）
def test_l3_b4_first_think_increments_count_and_enters_silence() -> None:
    pass


## L3-B-4-002
### Scenario: 沉默等待期間顧客有回應立即重跑判定優先序
### Given L3 處於想一下沉默期內（think_count == 1，sleep 中）
### When 6 秒內顧客輸入「冰紅茶」（命中商品）
### Then 跳出沉默立即處理該回應，重跑判定 1-7 → 走鏈路 B-3（加 cart + 留 L3）
def test_l3_b4_silence_interrupted_by_response_reruns_dispatch() -> None:
    pass


## L3-B-4-003
### Scenario: 沉默等待 6 秒滿無回應時 speak 重問語音並回主等待
### Given L3 處於想一下沉默期（think_count == 1）
### When 經過 WAIT_NO_RESPONSE（6）秒仍無顧客回應
### Then 系統 speak「請問還需要什麼東西嗎？」（L3 特有重問措辭，已加單版）
###      並回到 L3 主等待循環（timer 從 0 重起）
def test_l3_b4_silence_timeout_reasks_and_resumes_main_loop() -> None:
    pass


## L3-B-4-004
### Scenario: 第 2 次想一下 think_count 增至 2 但仍走沉默不轉 C-2
### Given L3 已走過 1 次 B-4，think_count == 1，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 2，再次進入沉默等待 6 秒（仍 < 3，未觸發 C-2）
def test_l3_b4_second_think_still_silence_below_threshold() -> None:
    pass


## L3-B-4-005
### Scenario: 第 3 次想一下 think_count 達 3 跳過沉默走 C-2 第二段邏輯
### Given L3 已走過 2 次 B-4，think_count == 2，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 3，**跳過 6s 沉默**，
###      speak C-2 第一段語音「請問是否要結帳？如果沒回應，10 秒後將為您結帳」，
###      **直接走 C-2 第二段邏輯**（等待 AUTO_CHECKOUT_NOTICE=10s）
###      （注意：L3 第 3 次想一下走「自動結帳推進」而非 L2 的「拒絕回 L1」
###      — 因為 L3 cart 已有商品，要結帳不是退單）
def test_l3_b4_third_think_skips_silence_and_triggers_c2_second_stage() -> None:
    pass


# ============================================================
# L3-C-1：結帳意圖（顧客主動結帳）
# ============================================================

## L3-C-1-001
### Scenario: 顧客回應結帳意圖關鍵字進 L4
### Given L3 等待中，cart 含商品
### When 顧客輸入命中結帳意圖關鍵字（如「結帳」/「買單」/「好了」/「夠了」之一）
### Then 系統 speak 結帳語音（建議「好的，為您結帳」），轉到 L4
def test_l3_c1_checkout_keyword_speaks_and_goes_l4() -> None:
    pass


# ============================================================
# L3-C-2：自動結帳（6s + 10s 兩段，C-2 是 L3 最特殊機制）
# ============================================================

## L3-C-2-001
### Scenario: 6 秒無回應觸發 C-2 第一段語音並進入第二段 10 秒等待
### Given L3 進入時動作完成，等待顧客回應中
### When 經過 WAIT_NO_RESPONSE（6）秒仍無任何顧客輸入
### Then 系統 speak C-2 第一段「請問是否要結帳？如果沒回應，10 秒後將為您結帳」
###      （f-string 插值 AUTO_CHECKOUT_NOTICE 常數），
###      進入第二段等待 AUTO_CHECKOUT_NOTICE（10）秒
def test_l3_c2_first_timeout_speaks_warning_and_enters_second_stage() -> None:
    pass


## L3-C-2-002
### Scenario: C-2 第二段 10 秒仍無回應自動進 L4 結帳
### Given L3 處於 C-2 第二段等待中（已過第一段 6s + 已播警告語音）
### When 第二段 10 秒內無任何顧客回應
### Then 直接進 L4（自動結帳完成）
def test_l3_c2_second_stage_timeout_goes_l4() -> None:
    pass


## L3-C-2-003
### Scenario: C-2 第二段內顧客回應商品取消自動結帳走 B-3 加單
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段 10 秒內顧客輸入「冰紅茶」（命中商品）
### Then 取消自動結帳，重跑判定優先序 → 走鏈路 B-3（加 cart + 留 L3）
def test_l3_c2_second_stage_product_reruns_dispatch_to_b3() -> None:
    pass


## L3-C-2-004
### Scenario: C-2 第二段內顧客回應拒絕關鍵字取消自動結帳走鏈路 A
### Given L3 處於 C-2 第二段等待中（已播警告語音），cart 含商品
### When 第二段 10 秒內顧客輸入「不要」（命中拒絕意圖）
### Then 取消自動結帳，走鏈路 A（清空 cart + 套子例程 A 回 L1）
def test_l3_c2_second_stage_reject_reruns_dispatch_to_a() -> None:
    pass


## L3-C-2-005
### Scenario: C-2 第二段內顧客回應結帳關鍵字走 C-1 進 L4
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段 10 秒內顧客輸入「結帳」（命中結帳意圖）
### Then 走鏈路 C-1（speak 結帳語音 + 進 L4）
def test_l3_c2_second_stage_checkout_reruns_dispatch_to_c1() -> None:
    pass


# ============================================================
# L3-PRIO：判定優先序特例（L3 跳過 L4 客服專用詞）
# ============================================================

## L3-PRIO-001
### Scenario: 顧客在 L3 說 L4 客服專用詞時 L3 視為無法判斷走 B-1
### Given L3 等待中（非 L4 客服模式）
### When 顧客輸入「繼續」或「退出」（L4 客服模式專用詞，僅該情境生效）
### Then L3 dispatcher 用 mode="normal" 呼叫 classifier → 回「無法判斷」 → 走 B-1
###      （規格 L3「判定優先序」段「L3 跳過項」說明 — 繼續/退出/取消/離開 不適用）
def test_l3_prio_l4_service_words_in_l3_falls_through_to_b1() -> None:
    pass
