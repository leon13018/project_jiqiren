"""L5 謝謝惠顧（致謝層）BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L5.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）由 subagent 把這些 scenarios 搬到 tests/sales/test_states.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - 全部 4 scenarios → myProgram/sales/states.py（加 run_l5）
    - constants.py 追加 `L5_THANKS` 字串
      （2026-06-15 結帳收尾語音合併後 L5 不再獨立 speak，致謝語音已併入
       L4 鏈路 A 的 L4_A_PAY_SUCCESS_FAREWELL 單句；L5_THANKS 死常數已移除。
       L5-ENTRY-002 改為「L5 不 speak、僅 do_action 揮手送客」。）

L5 設計約束（最簡單一層）：
    - **唯一進入**：L4 鏈路 A 掃碼成功
    - **無顧客互動**：3s 等待期間不接受任何顧客輸入（除全域 q 退出，屬主迴圈級）
    - **唯一出口**：3s 後自動回 L1 直接 hawk 連續叫賣
    - **cart 清空**：L5 進入時清空（規格敲定 — vs L4-A 不清，由 L5 統一負責）

callback 集合（subagent 自決細節）：
    - speak(text) — 致謝語音
    - do_action(name) — 動作 TBD（stub no-op）
    - cart — 既有 cart dict（L5 內 clear_cart）
    - sleep / read_customer_input(timeout) — 等 3s 的時間延遲（任一可選，
      推薦 sleep callback 因 L5 不需中斷 + 語義最明確）

回傳：tuple `("L1_enter_hawk", 0, 0)`（沿用 L4 三態 return tuple shape，
loop_count 與 unclear_count reset 為 0）
"""


# ============================================================
# L5-ENTRY：進入時動作（4 個獨立可驗證行為，但「do_action」TBD 不入測試）
# ============================================================

## L5-ENTRY-002（2026-06-15 結帳收尾語音合併後修訂）
### Scenario: 進入 L5 不再獨立 speak（致謝語音已併入 L4 鏈路 A）
### Given 從 L4 鏈路 A 進入 L5（L4 已 speak L4_A_PAY_SUCCESS_FAREWELL 合併句）
### When run_l5 啟動執行進入時動作
### Then run_l5 不再 speak，僅 do_action(ACTION_L5_FAREWELL) 揮手送客
def test_l5_entry_does_not_speak() -> None:
    pass


## L5-ENTRY-003
### Scenario: 進入 L5 清空 cart 完成交易重置
### Given 從 L4 鏈路 A 進入 L5，cart 含商品（例：{冰紅茶: 2, 刮刮樂: 1}）
### When run_l5 啟動執行進入時動作
### Then cart 被清空（cart_module.clear_cart 被呼叫；cart 內無任何商品）
###      （規格敲定 — cart 在 L5 進入時清，非 L4-A 掃碼成功時）
def test_l5_entry_clears_cart() -> None:
    pass


# ============================================================
# L5-A：致謝完成 → 回 L1 直接 hawk
# ============================================================

## L5-A-001
### Scenario: 等待 THANK_DELAY 秒後自動回 L1 直接 hawk 連續叫賣
### Given L5 進入時動作完成（已 speak / 清空 cart）
### When 等待 THANK_DELAY（3）秒過後
### Then 自動回 L1 直接 hawk 叫賣，
###      回傳 ("L1_enter_hawk", 0, 0)（沿用 L4 三態 return tuple shape，
###      loop_count + unclear_count 皆 reset 為 0）
###      （本層無顧客互動，3s 期間不解析任何關鍵字，除全域 q 屬主迴圈級）
def test_l5_a_returns_to_l1_enter_hawk_after_thank_delay() -> None:
    pass
