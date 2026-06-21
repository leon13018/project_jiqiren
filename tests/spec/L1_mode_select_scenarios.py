"""L1 商家模式選擇 BDD scenarios。

對應規格書：resources/plans/業務程式邏輯規劃/L1.md
階段：BDD（Stage 1）— 僅含 Gherkin 格式行為注解 + 空函式 pass，無實際斷言。
TDD（Stage 3）會由 subagent 把這些 scenarios 搬到 tests/sales/test_*.py 並補實作。

對應 prod 模組（subagent Stage 3 階段決定如何分配）：
    - L1-ENTRY / L1-C / L1-Q → myProgram/sales/states.py 或 logic.py
      （L1 屬主迴圈級邏輯，states.py 加 run_l1(...) 或 logic.py 主迴圈處理）
      （2026-06-21：L1-A 客服 / L1-B 待機兩模式已移除，只保留叫賣）

設計約束（選項 C，沿用 L0 規範）：
    - 禁 import 廠商 SDK（ActionGroupControl / Board）
    - 對外動作走 callback 注入：
        - print_terminal(text) — 印終端文字
        - read_terminal_key() — 讀終端輸入（blocking 或 non-blocking 由實作決定）；
          叫賣模式讀到 't'（觸控開始點餐 / web wake 注入）→ 轉 L2
        - speak(text) — 播叫賣語音（叫賣模式用，雖 L1 規格寫「無語音」但叫賣是例外，
          因 L1 鏈路 C 明寫「播一組叫賣術語」）
        - exit_program() — 全域 q 觸發
        - tts_is_idle() -> bool — 非阻塞查 TTS 是否播完當前句（叫賣輪播「上一句
          播完才起算 HAWK_INTERVAL 間距」用，2026-06-20 取代舊 schedule 死抽象）
    - 測試用純函式 lambda 收集呼叫紀錄，不用 mock library

L1 鏈路 C（叫賣模式啟動）：立即播第 1 組叫賣，按 't' 轉 L2
（2026-06-20 移除偵測模擬層；觸發來源改為觸控「開始點餐」→ token 't'）。
"""


# ============================================================
# L1-ENTRY：程式啟動與選單顯示
# ============================================================

## L1-ENTRY-001
### Scenario: 程式啟動進入 L1 印模式選擇選單
### Given 程式剛啟動（python3.11 myProgram/myProgram.py）
### When 進入 L1 模式選擇層
### Then 終端印選單含一個選項（1 叫賣）與 q 退出提示（待機 / 客服模式已移除）
def test_l1_entry_prints_mode_select_menu() -> None:
    pass


# ============================================================
# L1-C：叫賣模式（吸引顧客 + 't' 觸控觸發進 L2 入口）
# ============================================================

## L1-C-001
### Scenario: 商家輸入 1 進入叫賣模式立即播第 1 組叫賣
### Given L1 選單顯示中
### When 商家輸入「1」
### Then 終端印「進入叫賣模式」，立即播第 1 組叫賣術語
def test_l1_c_hawk_mode_starts_immediately_without_mute_buffer() -> None:
    pass


## L1-C-002
### Scenario: 叫賣模式按 't'（觸控開始點餐）觸發轉 L2
### Given 程式處於 L1 叫賣模式運行中
### When read_terminal_key 讀到 't'（終端按鍵或 web wake 注入 token 't'）
### Then 觸發轉 L2（run_l1 回傳 'L2'）
def test_l1_hawk_t_key_triggers_l2() -> None:
    pass


## L1-C-004
### Scenario: 叫賣模式運行中按 1 / 2 / 3 或其他非 q/t 鍵不切換模式
### Given 程式處於 L1 叫賣模式運行中
### When 商家輸入「1」 / 「2」 / 「3」或其他非 q/t 鍵
### Then 不切換模式，繼續留在叫賣模式
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
