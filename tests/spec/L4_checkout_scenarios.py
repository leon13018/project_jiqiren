"""L4 印金額 + 等掃碼（結帳層）BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L4.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）由 subagent 把這些 scenarios 搬到 tests/sales/test_states.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - 全部 22 scenarios → myProgram/sales/states.py（加 run_l4 + 對應私有函式）
    - 可能擴：myProgram/sales/constants.py（追加 L4 語音字串常數 + 催促 4 階段語音模板）

設計約束（選項 C，沿用 L0-L3 規範）：
    - 禁 import 廠商 SDK
    - 對外動作走 callback 注入：
        - speak / do_action / print_terminal / read_customer_input(timeout) -> str | None
        - cart / loop_count（caller 注入）/ unclear_count（caller 注入）
    - 觸發回 L1 直接 hawk：return ("L1_enter_hawk", 0, 0)
    - 進 L5：return ("L5", 0, 0)
    - 測試用純函式 lambda + inline class stub（沿用 FakeCustomerInput）

L4 與其他層的關鍵差異（必看）：
    1. **L4 客服模式不自動返回** — 需顧客手動選「退出 / 繼續」（L1/L2/L3 客服印完自動返回）
    2. **客服模式 60s timeout** — 完全靜默 → 強制退（清空 cart + 子例程 A）
    3. **客服模式內按 s** → 視為繼續 + 立即觸發鏈路 A（直接 L5）
    4. **客服模式內拒絕關鍵字 = 退出 fallback** — 不強制顧客學「退出」一詞
    5. **鏈路 D 6 次循環印金額**，4 階段語氣（中性 / 柔提醒 / 中度催促 / 明確警告）
    6. **雙計數器**：loop_count（D 鏈路用，最大 6 → 強制退；客服繼續時 reset 0）
                    unclear_count（E 鏈路用，最大 3 → 自動進 C；A / B 觸發時 reset 0）
    7. **L4 dispatcher 不適用：想一下 / 結帳意圖 / 商品**（這三類視為「無法判斷」走 E）
    8. **L4 入口印金額不算 loop_count**（loop_count 從第一次 6s timeout 才 ++）
    9. **L4 等待總時長上限 42 秒**（6×7=42；不含客服模式可一直等）

判定優先序：
    當有回應時：1.終端 s → A；2.拒絕 → B；3.客服 → C；
              4.想一下/結帳/商品 → 視為無法判斷 → E；5.其他不命中 → E
    6s 內無回應：→ D（loop_count++）
"""


# ============================================================
# L4-ENTRY：進入時動作
# ============================================================

## L4-ENTRY-001
### Scenario: 進入 L4 計算總額印明細並 speak 總額語音
### Given 從 L3 帶來的 cart（例：{冰紅茶: 2, 刮刮樂: 1}，總額 234 元）
### When run_l4 啟動執行進入時動作
### Then 計算總額（依 PRODUCTS 實際價）= 234 元，
###      終端印金額明細（商品明細 + 總金額 + 掃碼提示），
###      系統 speak「您的總金額是 234 元，請您掃碼付款」，
###      初始化 loop_count=0 + unclear_count=0，開始等待最多 WAIT_NO_RESPONSE 秒
def test_l4_entry_calculates_total_prints_detail_and_speaks() -> None:
    pass


# ============================================================
# L4-A：掃碼成功
# ============================================================

## L4-A-001
### Scenario: 顧客終端輸入 s 觸發鏈路 A 掃碼成功進 L5
### Given L4 等待中（cart 含商品）
### When 顧客輸入「s」（模擬掃碼成功）
### Then 系統 speak「付款成功，謝謝光臨，歡迎再來」（2026-06-15 結帳收尾語音合併，
###      原 L4「付款成功」與 L5 致謝併為 L4_A_PAY_SUCCESS_FAREWELL 單句），轉到 L5
###      （cart 在 L5 進入時清空，L4-A 本身不清；見 L0 cart 生命週期）
def test_l4_a_scan_success_speaks_and_goes_l5() -> None:
    pass


# ============================================================
# L4-B：拒絕（顧客主動取消）
# ============================================================

## L4-B-001
### Scenario: 顧客回應拒絕關鍵字觸發鏈路 B 清空 cart 套子例程 A
### Given L4 等待中，cart 含商品
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」/「不買了」之一）
### Then 系統 speak 取消語音（建議「好的，取消這次交易，謝謝光臨」），
###      **清空 cart**（整單作廢），套用 L0 子例程 A 回 L1 叫賣
###      （規格：loop_count 任何值下，拒絕鏈路 B 行為一致）
def test_l4_b_reject_keyword_clears_cart_and_triggers_enter_hawk() -> None:
    pass


# ============================================================
# L4-C：客服特殊模式（不自動返回，需手動選擇）
# ============================================================

## L4-C-001
### Scenario: 顧客回應客服關鍵字進入客服模式印電話並提示兩選項
### Given L4 等待中，cart 含商品
### When 顧客輸入命中客服意圖關鍵字（如「客服」/「聯繫」之一）
### Then 終端印商家客服電話（SERVICE_PHONE），
###      終端 + 語音提示「請選擇『退出交易』或『繼續交易』
###      （語音說或終端輸入 1=退出 / 2=繼續 皆可）」，
###      進入客服特殊模式等待選擇（最多 60s）
def test_l4_c_service_keyword_enters_special_mode_with_options() -> None:
    pass


## L4-C-002
### Scenario: 客服模式內終端輸入 1 退出清空 cart 回 L1
### Given L4 客服模式等待選擇中
### When 顧客輸入「1」（終端退出選項）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
def test_l4_c_service_input_1_exits_clears_cart() -> None:
    pass


## L4-C-003
### Scenario: 客服模式內語音命中退出交易關鍵字退出
### Given L4 客服模式等待選擇中
### When 顧客輸入命中退出交易意圖關鍵字（如「退出」/「離開」/「算了」之一，
###      classify_intent 用 mode="l4_service"）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
def test_l4_c_service_exit_keyword_exits_clears_cart() -> None:
    pass


## L4-C-004
### Scenario: 客服模式內語音命中拒絕意圖關鍵字作為退出 fallback
### Given L4 客服模式等待選擇中
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」/「不買了」之一）
### Then 視為退出（fallback — 不強制顧客學「退出」一詞），
###      清空 cart，套用 L0 子例程 A 回 L1 叫賣
def test_l4_c_service_reject_keyword_treated_as_exit() -> None:
    pass


## L4-C-005
### Scenario: 客服模式內終端輸入 2 繼續交易回 L4 主循環
### Given L4 客服模式等待選擇中（cart 含商品，loop_count > 0 也可能）
### When 顧客輸入「2」（終端繼續選項）
### Then 回 L4 主循環狀態（cart 保留 / loop_count reset 0 / 繼續等掃碼）
def test_l4_c_service_input_2_continues_resets_loop_count() -> None:
    pass


## L4-C-006
### Scenario: 客服模式內語音命中繼續交易關鍵字繼續
### Given L4 客服模式等待選擇中
### When 顧客輸入命中繼續交易意圖關鍵字（如「繼續」/「接著」/「繼續交易」之一）
### Then 回 L4 主循環狀態（cart 保留 / loop_count reset 0）
def test_l4_c_service_continue_keyword_continues() -> None:
    pass


## L4-C-007
### Scenario: 客服模式內終端輸入 s 視為繼續加掃碼直接進 L5
### Given L4 客服模式等待選擇中
### When 顧客輸入「s」（終端掃碼成功）
### Then 視為「繼續交易」+ 立即觸發鏈路 A 掃碼成功 → 直接進 L5
###      （設計理由：顧客在客服模式內按 s 真實意圖 100% 是「我打完電話、要付款了」）
def test_l4_c_service_input_s_treated_as_continue_then_scan() -> None:
    pass


## L4-C-008
### Scenario: 客服模式內輸入既不命中退出也不命中繼續時重複提示
### Given L4 客服模式等待選擇中
### When 顧客輸入「你好」（不命中退出 / 繼續 / 拒絕 / s 任一）
### Then 重複提示「請選擇：『退出交易』或『繼續交易』」（同 C-001 提示語），
###      保持在客服模式繼續等待
def test_l4_c_service_unrecognized_input_reprompts_and_stays() -> None:
    pass


## L4-C-009
### Scenario: 客服模式 60 秒完全靜默自動退出清空 cart
### Given L4 客服模式等待選擇中
### When 60 秒內無任何顧客回應（避免顧客拿到電話就走人造成系統卡死）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
def test_l4_c_service_timeout_60s_exits_clears_cart() -> None:
    pass


# ============================================================
# L4-D：循環印金額（6s 無回應，loop_count 累加，4 階段語氣）
# ============================================================

## L4-D-001
### Scenario: 第 1 次 6s 無回應 loop_count 增至 1 speak 中性催促語音
### Given L4 進入時動作完成，等待顧客回應中（loop_count=0）
### When 經過 WAIT_NO_RESPONSE（6）秒仍無任何顧客回應
### Then loop_count 變為 1，
###      系統 speak 中性催促「您的總金額是 X 元，請掃碼，或聯繫客服」，
###      回到等待掃碼狀態（loop_count<L4_MAX_LOOPS=6 → 繼續循環）
def test_l4_d_first_timeout_increments_count_and_speaks_neutral() -> None:
    pass


## L4-D-002
### Scenario: 第 2 次 6s 無回應 loop_count 增至 2 speak 柔提醒語音
### Given L4 已走過 1 次 D，loop_count=1，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應
### Then loop_count 變為 2，
###      系統 speak 柔提醒「提醒您，您的總金額是 X 元，需要協助請說『聯繫客服』」
def test_l4_d_second_timeout_speaks_gentle_reminder() -> None:
    pass


## L4-D-003
### Scenario: 第 3 4 次 6s 無回應 speak 中度催促語音（去掉威脅）
### Given L4 已走過 2 次 D，loop_count=2，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應（第 3 次）
### Then loop_count 變為 3，
###      系統 speak 中度催促「您的總金額是 X 元，請儘快完成掃碼」（不含「否則取消」威脅）
###      （第 4 次 loop_count=4 時用同一語音模板）
def test_l4_d_third_timeout_speaks_moderate_urgency() -> None:
    pass


## L4-D-004
### Scenario: 第 5 6 次 6s 無回應 speak 明確警告語音（含「否則取消」）
### Given L4 已走過 4 次 D，loop_count=4，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應（第 5 次）
### Then loop_count 變為 5，
###      系統 speak 明確警告「您的總金額是 X 元，請儘快完成掃碼，否則將取消這次交易」
###      （第 6 次 loop_count=6 時用同一語音模板）
def test_l4_d_fifth_timeout_speaks_explicit_warning() -> None:
    pass


## L4-D-005
### Scenario: 第 6 次循環滿 6s 仍無回應強制退清空 cart 套子例程 A
### Given L4 已走到 loop_count=6，第 6 次循環印金額完語音後又等 6s
### When 該次等待 WAIT_NO_RESPONSE 秒仍無回應
### Then **強制退**：系統 speak「已取消這次交易」（或同等取消語音），
###      清空 cart，套用 L0 子例程 A 回 L1 叫賣
###      （L4 等待總時長上限：42 秒，6×7=42）
def test_l4_d_sixth_timeout_forces_exit_clears_cart() -> None:
    pass


# ============================================================
# L4-E：無法判斷（unclear_count 狀態機，第 3 次自動進 C）
# ============================================================

## L4-E-001
### Scenario: 顧客回應不命中任何白名單時 unclear_count 增至 1 speak 重問
### Given L4 等待中，unclear_count=0
### When 顧客輸入「你好」（不命中拒絕 / 客服 / s / 任何類別）
### Then unclear_count 變為 1，
###      系統 speak「不好意思我聽不太懂，如果想付款請掃碼，需要協助請說『聯繫客服』」，
###      保持在 L4 重新進入等待狀態
def test_l4_e_first_unknown_increments_count_and_reprompts() -> None:
    pass


## L4-E-002
### Scenario: 顧客回應命中想一下意圖時 L4 視為無法判斷走 E
### Given L4 等待中
### When 顧客輸入命中想一下意圖關鍵字（如「等等」之一 — L4 不適用此類別）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
def test_l4_e_think_intent_treated_as_unknown() -> None:
    pass


## L4-E-003
### Scenario: 顧客回應命中結帳意圖時 L4 視為無法判斷走 E
### Given L4 等待中（顧客已在結帳中，再說結帳無意義）
### When 顧客輸入命中結帳意圖關鍵字（如「結帳」/「買單」之一）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
def test_l4_e_checkout_intent_treated_as_unknown() -> None:
    pass


## L4-E-004
### Scenario: 顧客回應命中商品時 L4 視為無法判斷走 E
### Given L4 等待中（總額已結算，再加商品在當前流程無意義）
### When 顧客輸入命中商品關鍵字（如「冰紅茶」/「刮刮樂」之一）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
def test_l4_e_product_intent_treated_as_unknown() -> None:
    pass


## L4-E-005
### Scenario: 第 3 次無法判斷 unclear_count 達 3 自動進客服模式
### Given L4 已走過 2 次 E，unclear_count=2，等待中
### When 顧客再次輸入不命中（任何上述 E trigger 之一）
### Then unclear_count 變為 3，
###      系統 speak「我可能無法協助您，正在為您聯繫客服」，
###      **自動進入鏈路 C 客服特殊模式**（印電話 + 等選擇）
def test_l4_e_third_unknown_auto_enters_service_mode() -> None:
    pass
