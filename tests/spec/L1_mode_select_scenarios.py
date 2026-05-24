"""L1 商家模式選擇 BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L1.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）會由 subagent 把這些 scenarios 搬到 tests/sales/test_*.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - L1-ENTRY / L1-A / L1-B / L1-C / L1-Q → myProgram/sales/states.py 或 logic.py
      （L1 屬主迴圈級邏輯，states.py 加 run_l1(...) 或 logic.py 主迴圈處理）

設計約束（選項 C，沿用 L0 規範）：
    - 禁 import 廠商 SDK（ActionGroupControl / Board）
    - 對外動作走 callback 注入：
        - print_terminal(text) — 印終端文字
        - read_terminal_key() — 讀終端輸入（blocking 或 non-blocking 由實作決定）
        - opencv_dwell_seconds() -> float — 取得 OpenCV 偵測到人持續秒數
        - opencv_disable() / opencv_enable() — 關閉 / 開啟 OpenCV
        - speak(text) — 播叫賣語音（叫賣模式用，雖 L1 規格寫「無語音」但叫賣是例外，
          因 L1 鏈路 C 明寫「播一組叫賣術語」）
        - exit_program() — 全域 q 觸發
        - schedule(seconds, callback) — 排程（叫賣輪播用，沿用 L0 子例程 A pattern）
    - 測試用純函式 lambda 收集呼叫紀錄，不用 mock library

L1 vs L0 子例程 A 的關鍵差異：
    - L1 鏈路 C（叫賣模式啟動）：立即播第 1 組 + OpenCV 開（無 mute 緩衝）
    - L0 子例程 A（L2-L5 結束後回 L1）：先 mute OPENCV_MUTE (12s) 才恢復 + 播第 1 組
    - 子例程 A 已在 L0-SUB-A 測完，本檔不重測
"""


# ============================================================
# L1-ENTRY：程式啟動與選單顯示
# ============================================================

## L1-ENTRY-001
### Scenario: 程式啟動進入 L1 印模式選擇選單
### Given 程式剛啟動（python3.11 myProgram/myProgram.py）
### When 進入 L1 模式選擇層
### Then 終端印選單含三個選項（1 叫賣 / 2 待機 / 3 客服）與 q 退出提示
def test_l1_entry_prints_mode_select_menu() -> None:
    pass


# ============================================================
# L1-A：客服模式（商家查電話）
# ============================================================

## L1-A-001
### Scenario: 商家輸入 3 進入客服模式印電話後立即回 L1 選單
### Given L1 選單顯示中，等待商家輸入
### When 商家輸入「3」
### Then 終端印商家客服電話（從 L0 客服電話常數取），無等待 / 無確認 → 立即回 L1 選單
###      （對比 L4 客服模式需手動選退出 / 繼續，因 L1 無進行中交易可保留）
def test_l1_a_service_mode_prints_phone_and_returns_to_menu() -> None:
    pass


# ============================================================
# L1-B：待機模式（商家暫停）
# ============================================================

## L1-B-001
### Scenario: 商家輸入 2 進入待機模式印提示後保持靜默
### Given L1 選單顯示中
### When 商家輸入「2」
### Then 終端印「進入待機模式，按 r + Enter 回主選單」，
###      程式進入「不主動做任何事」狀態（不叫賣 / 不發語音 / 不轉層）
def test_l1_b_standby_mode_prints_prompt_and_stays_idle() -> None:
    pass


## L1-B-002
### Scenario: 待機模式期間商家按 r 回 L1 選單
### Given 程式處於 L1 待機模式
### When 商家輸入「r」
### Then 程式離開待機，回 L1 選單（重新印模式選擇）
def test_l1_b_standby_r_returns_to_menu() -> None:
    pass


## L1-B-003
### Scenario: 待機模式期間商家按 q 立即終止程式（全域規則）
### Given 程式處於 L1 待機模式
### When 商家輸入「q」
### Then 程式立即終止（exit_program callback 被呼叫；對齊 L0 全域 q 退出規則）
def test_l1_b_standby_q_exits_program() -> None:
    pass


## L1-B-004
### Scenario: 待機模式期間 OpenCV 完全關閉不偵測 / 不觸發 L2
### Given 程式進入 L1 待機模式
### When 在待機期間有人持續站在相機前（即使 dwell ≥ OPENCV_DWELL 秒）
### Then OpenCV 已被關閉，不偵測也不觸發 L2 轉層（商家暫停 = 完全暫停）
def test_l1_b_standby_opencv_disabled() -> None:
    pass


# ============================================================
# L1-C：叫賣模式（吸引顧客 + OpenCV 觸發進 L2 入口）
# ============================================================

## L1-C-001
### Scenario: 商家輸入 1 進入叫賣模式立即播第 1 組叫賣並開啟 OpenCV
### Given L1 選單顯示中
### When 商家輸入「1」
### Then 終端印「進入叫賣模式」，立即播第 1 組叫賣術語（無 OPENCV_MUTE 緩衝），
###      OpenCV 同時開啟偵測（商家主動開店，不套用 L0 子例程 A 的 mute 12s 緩衝）
def test_l1_c_hawk_mode_starts_immediately_without_mute_buffer() -> None:
    pass


## L1-C-002
### Scenario: 叫賣模式 OpenCV 偵測人持續 ≥ OPENCV_DWELL 秒觸發轉 L2
### Given 程式處於 L1 叫賣模式運行中，OpenCV 偵測啟用
### When 相機框內持續有人 ≥ OPENCV_DWELL（1.5）秒
### Then 觸發轉 L2（dwell 時長確認後才轉，避免瞬時誤觸）
def test_l1_c_hawk_opencv_dwell_threshold_triggers_l2() -> None:
    pass


## L1-C-003
### Scenario: 叫賣模式 OpenCV 瞬時偵測未達 OPENCV_DWELL 不觸發轉 L2
### Given 程式處於 L1 叫賣模式運行中，OpenCV 偵測啟用
### When 相機框內偵測到人但持續 < OPENCV_DWELL（1.5）秒（路人經過 / 商家走過 / 光影誤觸）
### Then 不觸發轉 L2，繼續叫賣
def test_l1_c_hawk_opencv_brief_detection_filtered() -> None:
    pass


## L1-C-004
### Scenario: 叫賣模式運行中按 1 / 2 / 3 或其他非 q 鍵不切換模式
### Given 程式處於 L1 叫賣模式運行中
### When 商家輸入「1」 / 「2」 / 「3」或其他非 q 鍵
### Then 不切換模式（避免叫賣中誤切回選單導致 OpenCV 中斷）
def test_l1_c_hawk_non_q_keys_ignored() -> None:
    pass


## L1-C-005
### Scenario: 叫賣模式運行中按 q 立即終止程式（全域規則）
### Given 程式處於 L1 叫賣模式運行中
### When 商家輸入「q」
### Then 程式立即終止（exit_program callback 被呼叫）
def test_l1_c_hawk_q_exits_program() -> None:
    pass


# ============================================================
# L1-Q：選單時全域 q 退出
# ============================================================

## L1-Q-001
### Scenario: L1 選單顯示中按 q 立即終止程式
### Given 程式剛啟動，L1 選單顯示中等待輸入
### When 商家輸入「q」
### Then 程式立即終止（exit_program callback 被呼叫）
def test_l1_menu_q_exits_program() -> None:
    pass
