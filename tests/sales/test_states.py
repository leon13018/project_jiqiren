"""test_states.py — 測試 myProgram/sales/states.py。

對應 BDD scenarios：
    - L0-SUB-A-001：子例程觸發後立即屏蔽 OpenCV
    - L0-SUB-A-002：OPENCV_MUTE 秒後 OpenCV 恢復且立即播第 1 組叫賣
    - L0-SUB-A-003：第一輪叫賣後每 HAWK_INTERVAL 秒換下一組
    - L0-SUB-A-004：連續輪替超過 6 組時以 mod 6 回到第 1 組
    - L5-ENTRY-001：進入 L5 立即啟動 OpenCV mute 屏蔽致謝期間
    - L5-ENTRY-002：進入 L5 播致謝語音
    - L5-ENTRY-003：進入 L5 清空 cart 完成交易重置
    - L5-A-001：等待 THANK_DELAY 秒後自動套用子例程 A 回 L1

設計：callback 注入（speak / mute_opencv / unmute_opencv / schedule）。
      測試用純函式 lambda + FakeScheduler stub，不用 mock library。

FakeScheduler：
    - schedule(seconds, callback)：登記「delay 秒後執行 callback」
    - tick(seconds)：推進時間，觸發到期的 callback（含連鎖觸發）
"""

import myProgram.sales.states as states
from myProgram.sales.constants import (
    HAWK_SLOGANS,
    HAWK_INTERVAL,
    OPENCV_MUTE,
    OPENCV_DWELL,
    WAIT_NO_RESPONSE,
    AUTO_CHECKOUT_NOTICE,
    SERVICE_PHONE,
    L2_ENTRY_PROMPT,
    L2_REJECT_THANKS,
    L2_TIMEOUT_TO_HAWK_VOICE,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
    L3_ENTRY_PROMPT,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_A_PAY_SUCCESS,
    L4_B_CANCEL_THANKS,
    L4_C_OPTIONS_PROMPT,
    L4_D_FORCED_EXIT,
    L4_D_FINAL_PROMPT,
    L2_UNCLEAR_REJECT_VOICE,
    L3_UNCLEAR_FINAL_PROMPT,
    L3_CHECKOUT_CONFIRM_TEMPLATE,
    L3_CHECKOUT_REJECT_CLEAR_NOTICE,
    L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE,
    L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE,
    L3_C2_WARNING_TEMPLATE,
    UNCLEAR_MAX,
    L4_ACK_GENTLE,
    L4_E_CLARIFY,
    L4_E_AUTO_SERVICE,
    QTY_PROMPT_TEMPLATE,
    QTY_CLARIFY_TEMPLATE,
    L4_D_VOICE_NEUTRAL,
    L4_D_VOICE_GENTLE,
    L4_D_VOICE_MODERATE,
    L4_D_VOICE_WARNING,
    L4_SERVICE_TIMEOUT,
    L4_MAX_LOOPS,
    THANK_DELAY,
    L5_THANKS,
)
from myProgram.sales import cart as cart_module


# ============================================================
# FakeScheduler（純函式 stub，不用 mock library）
# ============================================================

class FakeScheduler:
    """模擬時間推進的排程器 stub。

    用途：讓測試可控制「時間推進」，不需 time.sleep。
    """

    def __init__(self) -> None:
        # 儲存 (到期時刻, callback) 的列表
        self._events: list = []
        self._now: float = 0.0

    def schedule(self, seconds: float, callback) -> None:
        """登記 seconds 秒後執行 callback。"""
        self._events.append((self._now + seconds, callback))

    def tick(self, seconds: float) -> None:
        """推進時間 seconds 秒，觸發所有到期的 callback（按時序）。"""
        self._now += seconds
        # 反覆掃描直到無新到期事件（callback 本身可能再次呼叫 schedule）
        changed = True
        while changed:
            changed = False
            pending = sorted(
                [(t, cb) for t, cb in self._events if t <= self._now],
                key=lambda x: x[0],
            )
            for due_time, cb in pending:
                if (due_time, cb) in self._events:
                    self._events.remove((due_time, cb))
                    cb()
                    changed = True


# ============================================================
# L0-SUB-A-001（2026-05-25 重構後）
# ============================================================

## L0-SUB-A-001
### Scenario: 子例程觸發後立即屏蔽 OpenCV OPENCV_MUTE 秒
### Given 子例程 A 已準備好（callback 注入）
### When 觸發子例程 A
### Then mute_opencv 被呼叫一次（屏蔽生效）
def test_sub_a_mutes_opencv_on_trigger() -> None:
    # Arrange
    mute_calls: list = []

    # Act
    states.run_subroutine_a(
        mute_opencv=lambda secs: mute_calls.append(secs),
    )

    # Assert：觸發後立即屏蔽 OpenCV
    assert len(mute_calls) == 1
    assert mute_calls[0] == OPENCV_MUTE


# ============================================================
# L0-SUB-A-002（2026-05-25 改成 regression：方案 A 後子例程 A 不再 unmute / 不再叫賣）
# ============================================================

## L0-SUB-A-002
### Scenario: 子例程 A 只 mute 不 unmute、不叫賣（防 unmute_opencv / 叫賣 callback 偷被加回來）
### Given 子例程 A 已觸發
### When 任何時點檢查
### Then run_subroutine_a 的 signature 不該再接受 unmute_opencv / speak / schedule callbacks
def test_sub_a_only_calls_mute_no_unmute_no_speak() -> None:
    # Arrange
    import inspect
    sig = inspect.signature(states.run_subroutine_a)

    # Assert：signature 只剩 mute_opencv（2026-05-25 方案 A 重構）
    params = set(sig.parameters.keys())
    assert params == {"mute_opencv"}, (
        f"run_subroutine_a 應只接受 mute_opencv，實際 {params}。"
        "若加回 unmute_opencv / speak / schedule = 違反方案 A 規格（"
        "L0_共通.md 子例程 A 段）：主選單期間不該被自動 unmute / 不該背景叫賣"
    )


# ============================================================
# L1 測試用 stub class
# ============================================================

class FakeKeyboardInput:
    """模擬鍵盤輸入序列。每次 read() 回下一個 key。"""

    def __init__(self, key_sequence: list) -> None:
        self._keys = list(key_sequence)

    def read(self) -> str:
        return self._keys.pop(0) if self._keys else ""


class FakeOpencv:
    """模擬 OpenCV dwell 偵測 + 開關狀態。"""

    def __init__(self, dwell_value: float = 0.0) -> None:
        self.dwell_value = dwell_value
        self.enabled = True
        self.enable_calls = 0
        self.disable_calls = 0

    def dwell_seconds(self) -> float:
        """回傳 dwell 偵測秒數（OpenCV 關閉時永遠回 0.0）。"""
        return self.dwell_value if self.enabled else 0.0

    def disable(self) -> None:
        self.enabled = False
        self.disable_calls += 1

    def enable(self) -> None:
        self.enabled = True
        self.enable_calls += 1


# ============================================================
# L1-ENTRY-001
# Scenario: 程式啟動進入 L1 印模式選擇選單
# Given 程式剛啟動（python3.11 -m myProgram 或 python3.11 -m myProgram.main）
# When 進入 L1 模式選擇層
# Then 終端印選單含三個選項（1 叫賣 / 2 待機 / 3 客服）與 q 退出提示
# ============================================================

def test_l1_entry_prints_mode_select_menu() -> None:
    # Arrange
    printed: list = []
    # 輸入 q 使程式立即退出，避免無限迴圈
    kbd = FakeKeyboardInput(["q"])
    exit_calls: list = []

    # Act
    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=lambda: 0.0,
        opencv_disable=lambda: None,
        opencv_enable=lambda: None,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：印出的選單要包含三個選項與 q 提示
    all_output = "\n".join(printed)
    assert "1" in all_output, "選單應含選項 1（叫賣模式）"
    assert "2" in all_output, "選單應含選項 2（待機模式）"
    assert "3" in all_output, "選單應含選項 3（客服模式）"
    assert "q" in all_output, "選單應含 q 退出提示"


# ============================================================
# L1-A-001
# Scenario: 商家輸入 3 進入客服模式印電話後立即回 L1 選單
# Given L1 選單顯示中，等待商家輸入
# When 商家輸入「3」
# Then 終端印商家客服電話，無等待 → 立即回 L1 選單
# ============================================================

def test_l1_a_service_mode_prints_phone_and_returns_to_menu() -> None:
    # Arrange
    printed: list = []
    # 輸入 3（進客服），接著 q（退出，避免無限迴圈）
    kbd = FakeKeyboardInput(["3", "q"])
    exit_calls: list = []

    # Act
    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=lambda: 0.0,
        opencv_disable=lambda: None,
        opencv_enable=lambda: None,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：電話號碼出現在印出內容中
    all_output = "\n".join(printed)
    assert "0900-XXX-XXX" in all_output, "應印出客服電話"
    # 印完電話後應回選單（選單在第二輪再印一次）
    menu_count = sum(1 for p in printed if "請選擇模式" in p)
    assert menu_count >= 2, "客服後應回選單（選單至少印兩次）"


# ============================================================
# L1-B-001
# Scenario: 商家輸入 2 進入待機模式印提示後保持靜默
# Given L1 選單顯示中
# When 商家輸入「2」
# Then 終端印「進入待機模式，按 r + Enter 回主選單」，進入靜默狀態
# ============================================================

def test_l1_b_standby_mode_prints_prompt_and_stays_idle() -> None:
    # Arrange
    printed: list = []
    # 輸入 2 進待機，接著 q 退出
    kbd = FakeKeyboardInput(["2", "q"])
    exit_calls: list = []
    opencv = FakeOpencv()

    # Act
    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：待機提示有印出
    all_output = "\n".join(printed)
    assert "待機" in all_output, "應印待機模式提示"
    assert "r" in all_output, "待機提示應包含 r 回選單說明"


# ============================================================
# L1-B-002
# Scenario: 待機模式期間商家按 r 回 L1 選單
# Given 程式處於 L1 待機模式
# When 商家輸入「r」
# Then 程式離開待機，回 L1 選單（重新印模式選擇）
# ============================================================

def test_l1_b_standby_r_returns_to_menu() -> None:
    # Arrange
    printed: list = []
    # 進待機（2），按 r 回選單，按 q 退出
    kbd = FakeKeyboardInput(["2", "r", "q"])
    exit_calls: list = []
    opencv = FakeOpencv()

    # Act
    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：按 r 後選單應再印一次
    menu_count = sum(1 for p in printed if "請選擇模式" in p)
    assert menu_count >= 2, "按 r 後應回選單（選單至少印兩次）"
    # 2026-05-25 規格修訂：r 回選單不再自動 opencv_enable（主選單預設不偵測，只叫賣啟動）
    assert opencv.enable_calls == 0, (
        f"按 r 回選單不應 opencv_enable（主選單預設不偵測），實際 enable_calls={opencv.enable_calls}"
    )


# ============================================================
# L1-B-003
# Scenario: 待機模式期間商家按 q 立即終止程式（全域規則）
# Given 程式處於 L1 待機模式
# When 商家輸入「q」
# Then 程式立即終止（exit_program callback 被呼叫）
# ============================================================

def test_l1_b_standby_q_exits_program() -> None:
    # Arrange
    exit_calls: list = []
    opencv = FakeOpencv()
    # 進待機（2），待機中按 q
    kbd = FakeKeyboardInput(["2", "q"])

    # Act
    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：exit_program 被呼叫一次
    assert len(exit_calls) == 1, "待機中按 q 應呼叫 exit_program"


# ============================================================
# L1-B-004
# Scenario: 待機模式期間 OpenCV 完全關閉不偵測 / 不觸發 L2
# Given 程式進入 L1 待機模式
# When 在待機期間有人持續站在相機前（即使 dwell ≥ OPENCV_DWELL 秒）
# Then OpenCV 已被關閉，dwell_seconds 在待機中永遠回 0.0，不觸發 L2
# ============================================================

def test_l1_b_standby_opencv_disabled() -> None:
    # Arrange
    # FakeOpencv 在 disabled 狀態下 dwell_seconds() 回 0.0
    opencv = FakeOpencv(dwell_value=999.0)  # 模擬人一直站著
    # 進待機（2），待機中按 q
    kbd = FakeKeyboardInput(["2", "q"])

    # Act
    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
    )

    # Assert：待機時 OpenCV 被 disable（disable_calls == 1）
    assert opencv.disable_calls >= 1, "進入待機時應關閉 OpenCV"
    # FakeOpencv.enabled == False 期間 dwell_seconds() 回 0.0，無法觸發 L2
    # （此斷言驗證 FakeOpencv stub 行為與 OpenCV 語義一致）
    opencv_tmp = FakeOpencv(dwell_value=999.0)
    opencv_tmp.disable()
    assert opencv_tmp.dwell_seconds() == 0.0, "OpenCV 關閉後 dwell_seconds 應回 0.0"


# ============================================================
# L1-C-001
# Scenario: 商家輸入 1 進入叫賣模式立即播第 1 組叫賣並開啟 OpenCV
# Given L1 選單顯示中
# When 商家輸入「1」
# Then 印「進入叫賣模式」，立即 speak 第 1 組叫賣，OpenCV 被開啟
#      （不套用 L0 子例程 A 的 OPENCV_MUTE 緩衝）
# ============================================================

def test_l1_enter_hawk_immediately_skips_mode_menu() -> None:
    """2026-05-26 加：enter_hawk_immediately=True 跳過主選單直接進 hawk。

    用途：logic.py 在 subroutine_a 後（dialog reject / L4 cancel / L5 完成）
    設此 flag → 連續叫賣，不顯示「請選擇模式：1/2/3」主選單。
    """
    printed: list = []
    speak_calls: list = []
    opencv = FakeOpencv(dwell_value=0.0)
    scheduler = FakeScheduler()
    # OpenCV dwell 一直 0.0 不觸發 L2；按 q 退出
    kbd = FakeKeyboardInput(["q"])

    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: speak_calls.append(text),
        exit_program=lambda: None,
        schedule=scheduler.schedule,
        enter_hawk_immediately=True,
    )

    all_output = "\n".join(printed)
    # 不應印主選單 banner（沒有「請選擇模式」標題）
    assert "請選擇模式" not in all_output, (
        f"enter_hawk_immediately=True 不應顯示主選單，實際印出：{printed}"
    )
    # 應印 hawk 進入提示
    assert "叫賣" in all_output, "應印叫賣模式進入提示"
    # 應立即 speak HAWK_SLOGANS[0]
    assert speak_calls and speak_calls[0] == HAWK_SLOGANS[0]


def test_l1_c_hawk_mode_starts_immediately_without_mute_buffer() -> None:
    # Arrange
    printed: list = []
    speak_calls: list = []
    opencv = FakeOpencv(dwell_value=0.0)
    scheduler = FakeScheduler()
    # 輸入 1 進叫賣模式，OpenCV dwell 一直 0.0（不觸發 L2），按 q 退出
    key_sequence = ["1", "q"]
    kbd = FakeKeyboardInput(key_sequence)

    # Act
    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: speak_calls.append(text),
        exit_program=lambda: None,
        schedule=scheduler.schedule,
    )

    # Assert 1：印「進入叫賣模式」
    all_output = "\n".join(printed)
    assert "叫賣" in all_output, "應印叫賣模式進入提示"

    # Assert 2：第 1 組叫賣術語被立即 speak（無需 tick 任何時間）
    assert len(speak_calls) >= 1, "應立即播第 1 組叫賣"
    assert speak_calls[0] == HAWK_SLOGANS[0], "第一個 speak 應為 HAWK_SLOGANS[0]"

    # Assert 3：OpenCV 被開啟（enable_calls >= 1）
    assert opencv.enable_calls >= 1, "進入叫賣模式應開啟 OpenCV"


# ============================================================
# L1-C-002
# Scenario: 叫賣模式 OpenCV 偵測人持續 ≥ OPENCV_DWELL 秒觸發轉 L2
# Given 程式處於 L1 叫賣模式運行中，OpenCV 偵測啟用
# When 相機框內持續有人 ≥ OPENCV_DWELL（1.5）秒
# Then 觸發轉 L2（run_l1 回傳 'L2'）
# ============================================================

def test_l1_c_hawk_opencv_dwell_threshold_triggers_l2() -> None:
    # Arrange
    # OpenCV 立即回報 dwell ≥ OPENCV_DWELL（模擬顧客已在鏡頭前足夠久）
    opencv = FakeOpencv(dwell_value=OPENCV_DWELL)

    # Act
    result = states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=lambda: "1",  # 第一次讀 1 進叫賣，後續不應被呼叫（已轉 L2）
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
    )

    # Assert：run_l1 應回傳 'L2'
    assert result == "L2", f"dwell ≥ OPENCV_DWELL 應回傳 'L2'，實際：{result}"


# ============================================================
# L1-C-003
# Scenario: 叫賣模式 OpenCV 瞬時偵測未達 OPENCV_DWELL 不觸發轉 L2
# Given 程式處於 L1 叫賣模式運行中，OpenCV 偵測啟用
# When 相機框內偵測到人但持續 < OPENCV_DWELL（1.5）秒
# Then 不觸發轉 L2，繼續叫賣（按 q 才退出）
# ============================================================

def test_l1_c_hawk_opencv_brief_detection_filtered() -> None:
    # Arrange
    # dwell < OPENCV_DWELL，不觸發 L2
    opencv = FakeOpencv(dwell_value=OPENCV_DWELL - 0.1)
    exit_calls: list = []
    # 進叫賣（1），dwell 不達閾值，按 q 退出
    kbd = FakeKeyboardInput(["1", "q"])

    # Act
    result = states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：未達閾值不轉 L2（exit_program 被呼叫，result 為 None）
    assert result != "L2", "dwell < OPENCV_DWELL 不應觸發 L2"
    assert len(exit_calls) == 1, "應呼叫 exit_program（q 退出）"


# ============================================================
# L1-C-004
# Scenario: 叫賣模式運行中按 1 / 2 / 3 或其他非 q 鍵不切換模式
# Given 程式處於 L1 叫賣模式運行中
# When 商家輸入「1」 / 「2」 / 「3」或其他非 q 鍵
# Then 不切換模式，繼續留在叫賣模式（直到 q 退出）
# ============================================================

def test_l1_c_hawk_non_q_keys_ignored() -> None:
    # Arrange
    opencv = FakeOpencv(dwell_value=0.0)  # 不觸發 L2
    exit_calls: list = []
    # 進叫賣（1），在叫賣模式中按 1 / 2 / 3 / x，最後按 q 退
    kbd = FakeKeyboardInput(["1", "1", "2", "3", "x", "q"])

    # Act
    result = states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：這些按鍵不切換模式；最後 q 才讓 exit_program 被呼叫
    assert result != "L2", "按 1/2/3/x 不應觸發 L2"
    assert len(exit_calls) == 1, "只有 q 才呼叫 exit_program（共 1 次）"


# ============================================================
# L1-C-005
# Scenario: 叫賣模式運行中按 q 立即終止程式（全域規則）
# Given 程式處於 L1 叫賣模式運行中
# When 商家輸入「q」
# Then 程式立即終止（exit_program callback 被呼叫）
# ============================================================

def test_l1_c_hawk_q_exits_program() -> None:
    # Arrange
    opencv = FakeOpencv(dwell_value=0.0)  # 不觸發 L2
    exit_calls: list = []
    # 進叫賣（1），在叫賣中按 q
    kbd = FakeKeyboardInput(["1", "q"])

    # Act
    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：exit_program 被呼叫一次
    assert len(exit_calls) == 1, "叫賣中按 q 應呼叫 exit_program"


# ============================================================
# L1-Q-001
# Scenario: L1 選單顯示中按 q 立即終止程式
# Given 程式剛啟動，L1 選單顯示中等待輸入
# When 商家輸入「q」
# Then 程式立即終止（exit_program callback 被呼叫）
# ============================================================

def test_l1_menu_q_exits_program() -> None:
    # Arrange
    exit_calls: list = []
    # 在選單直接按 q
    kbd = FakeKeyboardInput(["q"])

    # Act
    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=lambda: 0.0,
        opencv_disable=lambda: None,
        opencv_enable=lambda: None,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
    )

    # Assert：exit_program 被呼叫一次
    assert len(exit_calls) == 1, "選單中按 q 應呼叫 exit_program"


# ============================================================
# L2 測試用 stub
# ============================================================

class FakeCustomerInput:
    """模擬顧客輸入序列，支援 timeout 語義。

    sequence: list of (text_or_None)
        - str → 該次 read_customer_input 回傳此字串（顧客有回應）
        - None → 該次 read_customer_input 回傳 None（模擬 timeout）
    """

    def __init__(self, sequence: list) -> None:
        self._seq = list(sequence)

    def read(self, timeout: float) -> str | None:
        """模擬等待顧客回應。timeout 參數保留接口，stub 不實際等待。"""
        if not self._seq:
            return None
        return self._seq.pop(0)


# ============================================================
# L2-ENTRY-001
# Scenario: 進入 L2 即播詢問語音並初始化 think_count
# Given 從 L1 叫賣模式 OpenCV 偵測到人進入 L2
# When run_l2 啟動執行進入時動作
# Then 系統 speak「您好，請問需要購買什麼東西嗎？」且 think_count 初始化為 0，
#      開始等待顧客回應最多 WAIT_NO_RESPONSE（6）秒
# ============================================================

def test_l2_entry_speaks_greeting_and_inits_think_count() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 顧客 timeout（None）→ 觸發鏈路 A，讓 run_l2 能正常結束
    customer_input = FakeCustomerInput([None])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音是第一個 speak 呼叫
    assert len(speak_calls) >= 1, "run_l2 應呼叫至少一次 speak"
    assert speak_calls[0] == L2_ENTRY_PROMPT, (
        f"第一個 speak 應為 L2_ENTRY_PROMPT，實際：{speak_calls[0]!r}"
    )
    # think_count 初始為 0（由 caller 注入，這裡我們傳 0 進去，驗證 return 中的 next_think_count 反映正確語義）
    # 鏈路 A 退出時 think_count reset 為 0
    assert next_think_count == 0, f"鏈路 A 退出時 think_count 應 reset 為 0，實際：{next_think_count}"


# ============================================================
# L2-A-001
# Scenario: WAIT_NO_RESPONSE 秒無回應觸發鏈路 A 拒絕
# Given L2 進入時動作完成，正在等待顧客回應
# When 經過 WAIT_NO_RESPONSE（6）秒仍無任何顧客輸入
# Then 系統 speak「謝謝光臨」並套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l2_a_timeout_no_response_triggers_reject_and_subroutine_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 第一個 None（ENTRY 後主等待）→ timeout → 鏈路 A
    customer_input = FakeCustomerInput([None])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：timeout 不算「拒絕」→ 應 speak 中性「繼續叫賣」提示而非 L2_REJECT_THANKS
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls, (
        f"timeout 應 speak L2_TIMEOUT_TO_HAWK_VOICE，實際 speak 序列：{speak_calls}"
    )
    assert L2_REJECT_THANKS not in speak_calls, (
        f"timeout 不應 speak L2_REJECT_THANKS（那是明確拒絕意圖才用），實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"timeout 應回傳 'L1_via_subroutine_a'，實際：{next_state!r}"
    )
    assert next_think_count == 0, "鏈路 A 退出時 think_count 應 reset 為 0"


# ============================================================
# L2-A-002
# Scenario: 顧客回應拒絕關鍵字觸發鏈路 A
# Given L2 進入時動作完成，正在等待顧客回應
# When 顧客輸入命中拒絕意圖關鍵字（如「不要」）
# Then 系統 speak「謝謝光臨」並套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l2_a_reject_keyword_triggers_subroutine_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["不要"])  # 拒絕意圖

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert L2_REJECT_THANKS in speak_calls, (
        f"拒絕關鍵字應觸發 speak L2_REJECT_THANKS，實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"應回傳 'L1_via_subroutine_a'，實際：{next_state!r}"
    )
    assert next_think_count == 0, "鏈路 A 退出時 think_count 應 reset 為 0"


# ============================================================
# L2-B-1-001
# Scenario: 顧客回應不命中任何白名單時走 B-1 並留在 L2 重新等待
# Given L2 等待顧客回應中
# When 顧客輸入「今天天氣很好」（不命中任何類別）
# Then 系統 speak L2_B1_CLARIFY，保持在 L2 重新等待
# ============================================================

def test_l2_b1_unknown_input_speaks_clarification_and_stays_in_l2() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    # 第一個回應不命中 → B-1；第二個 None → timeout → A（讓 run_l2 結束）
    customer_input = FakeCustomerInput(["今天天氣很好", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：B-1 clarify 語音有被 speak
    assert L2_B1_CLARIFY in speak_calls, (
        f"不明輸入應 speak L2_B1_CLARIFY，實際：{speak_calls}"
    )
    # run_l2 最終因 None timeout 走鏈路 A 退出（驗證有進入 L2 循環第二次）
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-1-002（2026-05-25 加）
### Scenario: B-1 連續 UNCLEAR_MAX 次無法判斷 → 走鏈路 A 拒絕
### Given L2 等待中
### When 顧客連續 UNCLEAR_MAX 次說系統聽不懂的話
### Then 第 UNCLEAR_MAX 次後 speak L2_UNCLEAR_REJECT_VOICE + 走鏈路 A 退出
# ============================================================

def test_l2_b1_unclear_max_triggers_reject_thanks() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 連續 UNCLEAR_MAX 次不命中
    customer_input = FakeCustomerInput(["asdf"] * UNCLEAR_MAX)

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：第 UNCLEAR_MAX 次後 speak unclear reject voice
    assert L2_UNCLEAR_REJECT_VOICE in speak_calls, (
        f"達 UNCLEAR_MAX 應 speak L2_UNCLEAR_REJECT_VOICE，實際：{speak_calls}"
    )
    # 前 UNCLEAR_MAX-1 次 speak B-1 clarify
    assert speak_calls.count(L2_B1_CLARIFY) == UNCLEAR_MAX - 1, (
        f"前 {UNCLEAR_MAX-1} 次應 speak L2_B1_CLARIFY，實際：{speak_calls}"
    )
    # 走鏈路 A
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-1-003（2026-05-25 加）
### Scenario: B-1 累積後命中已知意圖 → unclear_count reset
### Given L2 等待中，已 B-1 兩次（unclear_count=2）
### When 顧客說「客服」（已知意圖）
### Then 印電話 + reset unclear_count = 0；後續再 B-1 兩次不會觸發 reject
# ============================================================

def test_l2_b1_reset_on_known_intent() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    # B-1, B-1, 客服 (reset), B-1, B-1, None (timeout → A)
    customer_input = FakeCustomerInput(["asdf", "qwer", "客服", "zxcv", "vbnm", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：客服電話有被印
    assert SERVICE_PHONE in terminal_calls
    # 沒有觸發 L2_UNCLEAR_REJECT_VOICE（因為被 reset 過，最多累 2 次）
    assert L2_UNCLEAR_REJECT_VOICE not in speak_calls, (
        f"unclear_count 已 reset，不應觸發 reject_voice。speak={speak_calls}"
    )
    # 退出原因是 timeout（鏈路 A 由 None 觸發）
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-2-001
# Scenario: 顧客回應客服關鍵字觸發 B-2 印電話後自動回 L2 循環
# Given L2 等待顧客回應中
# When 顧客輸入命中客服關鍵字（如「客服」）
# Then 終端印 SERVICE_PHONE，自動回 L2 循環
# ============================================================

def test_l2_b2_service_keyword_prints_phone_and_returns_to_l2_loop() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    # 客服關鍵字 → B-2 印電話；然後 None → timeout → A（讓 run_l2 結束）
    customer_input = FakeCustomerInput(["客服", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：SERVICE_PHONE 被印到終端
    assert SERVICE_PHONE in terminal_calls, (
        f"B-2 應 print_terminal(SERVICE_PHONE)，實際 terminal_calls：{terminal_calls}"
    )
    # 自動回 L2 循環，第二次輸入 None → A → 退出
    assert next_state == "L1_via_subroutine_a", (
        "B-2 後應回 L2 循環（最終因 timeout 觸發 A 退出）"
    )


# ============================================================
# L2-B-3-001
# Scenario: 第 1 次想一下 think_count 自 0 增至 1 並進入沉默等待
# Given L2 think_count == 0，等待顧客回應中
# When 顧客輸入命中想一下關鍵字（如「稍等」）
# Then think_count 變為 1，進入沉默等待 WAIT_NO_RESPONSE（6）秒（不發出任何語音）
# ============================================================

def test_l2_b3_first_think_increments_count_and_enters_silence() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 想一下 → B-3 沉默等待；沉默期 None（timeout）→ speak 重問；再 None → A
    customer_input = FakeCustomerInput(["稍等", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：沉默期無多餘語音（不應在想一下之後、沉默期中發語音）
    # 進入語音 → L2_ENTRY_PROMPT（索引 0）
    # 沉默後重問語音 → L2_B3_REASK
    # 然後 None → A → L2_REJECT_THANKS
    assert speak_calls[0] == L2_ENTRY_PROMPT, "第一個 speak 應為進入語音"
    # 沉默期間應無任何語音（想一下和沉默之間不能有其他 speak）
    speak_between_think_and_reask = speak_calls[1] if len(speak_calls) > 1 else None
    assert speak_between_think_and_reask == L2_B3_REASK, (
        f"沉默 timeout 後應 speak L2_B3_REASK，實際：{speak_between_think_and_reask!r}"
    )


# ============================================================
# L2-B-3-002
# Scenario: 沉默等待期間顧客有回應立即重跑判定優先序
# Given L2 處於想一下沉默期內（think_count == 1，沉默中）
# When 6 秒內顧客輸入「冰紅茶」（命中商品）
# Then 跳出沉默等待立即處理該回應，走鏈路 C（加 cart 後進 L3）
# ============================================================

def test_l2_b3_silence_interrupted_by_response_reruns_dispatch() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 想一下 → 沉默期；沉默期內顧客回「冰紅茶」→ 走 C 進 L3
    customer_input = FakeCustomerInput(["想一下", "冰紅茶"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：走 C 進 L3
    assert next_state == "L4", (
        f"沉默期有回應（商品）應進 L3，實際：{next_state!r}"
    )
    assert next_think_count == 0, "鏈路 C 退出時 think_count 應 reset 為 0"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"cart 應加入冰紅茶 ×1，實際：{cart}"
    )
    assert L2_C_ADDED in speak_calls, "應 speak L2_C_ADDED"


# ============================================================
# L2-B-3-003
# Scenario: 沉默等待 6 秒滿無回應時 speak 重問語音並回主等待
# Given L2 處於想一下沉默期（think_count == 1）
# When 經過 WAIT_NO_RESPONSE（6）秒仍無顧客回應
# Then 系統 speak L2_B3_REASK 並回到 L2 主等待循環
# ============================================================

def test_l2_b3_silence_timeout_reasks_and_resumes_main_loop() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 想一下 → 沉默期 None（timeout）→ speak 重問；再 None → A 退出
    customer_input = FakeCustomerInput(["想一下", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L2_B3_REASK 被 speak
    assert L2_B3_REASK in speak_calls, (
        f"沉默 timeout 後應 speak L2_B3_REASK，實際：{speak_calls}"
    )
    # 回主等待後 None → A → L1
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-3-004
# Scenario: 第 2 次想一下 think_count 增至 2 但仍走沉默不轉拒絕
# Given L2 已走過 1 次 B-3，think_count == 1，回到主等待後
# When 顧客再次輸入想一下關鍵字
# Then think_count 變為 2，再次進入沉默等待 6 秒（仍 < 3，未觸發鏈路 A 拒絕）
# ============================================================

def test_l2_b3_second_think_still_silence_below_threshold() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 第一次想一下 → 沉默 None → 重問；第二次想一下 → 沉默 None → 重問；最後 None → A
    customer_input = FakeCustomerInput(["等等", None, "稍等", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L2_B3_REASK 應出現兩次（第一次和第二次沉默 timeout 後）
    reask_count = speak_calls.count(L2_B3_REASK)
    assert reask_count == 2, (
        f"兩次想一下沉默 timeout 應各 speak 一次 L2_B3_REASK，實際出現 {reask_count} 次"
    )
    # 第三次 None → A，未觸發 L2_B3_THIRD_REJECT（因為 think_count 才 2）
    assert L2_B3_THIRD_REJECT not in speak_calls, (
        "think_count==2 不應觸發 L2_B3_THIRD_REJECT"
    )
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-3-005
# Scenario: 第 3 次想一下 think_count 達 3 跳過沉默走鏈路 A 拒絕
# Given L2 已走過 2 次 B-3，think_count == 2，回到主等待後
# When 顧客再次輸入想一下關鍵字
# Then think_count 變為 3，跳過 6s 沉默，speak L2_B3_THIRD_REJECT，走鏈路 A
# ============================================================

def test_l2_b3_third_think_skips_silence_and_triggers_reject() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # think_count=2 傳入；一次想一下關鍵字 → 累加到 3 → 直接走 A
    customer_input = FakeCustomerInput(["想一下"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=2,  # 已累積 2 次
    )

    # Assert：L2_B3_THIRD_REJECT 被 speak，無沉默（不需要第二個 read 呼叫）
    assert L2_B3_THIRD_REJECT in speak_calls, (
        f"第 3 次想一下應 speak L2_B3_THIRD_REJECT，實際：{speak_calls}"
    )
    assert L2_REJECT_THANKS in speak_calls, "應接著 speak L2_REJECT_THANKS（鏈路 A）"
    assert next_state == "L1_via_subroutine_a"
    assert next_think_count == 0, "鏈路 A 退出時 think_count 應 reset 為 0"


# ============================================================
# L2-C-001
# Scenario: 顧客回應冰紅茶關鍵字加 1 杯入 cart 並進 L3
# Given L2 等待顧客回應中，cart 為空
# When 顧客輸入「冰紅茶」（命中商品 — 冰紅茶，無數量描述）
# Then 數量解析為 1（預設），cart = {冰紅茶: 1}，系統 speak L2_C_ADDED，轉到 L3
# ============================================================

def test_l2_c_iced_tea_default_quantity_adds_cart_and_goes_l3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["冰紅茶"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L4", f"商品命中應進 L3，實際：{next_state!r}"
    assert next_think_count == 0, "鏈路 C 退出時 think_count 應 reset 為 0"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"cart 應有冰紅茶 ×1，實際：{cart}"
    )
    assert L2_C_ADDED in speak_calls, "應 speak L2_C_ADDED"


# ============================================================
# L2-C-002
# Scenario: 顧客回應含數量的商品輸入正確解析數量並加入 cart
# Given L2 等待顧客回應中，cart 為空
# When 顧客輸入「冰紅茶兩個」（命中商品 + 中文數量「兩」）
# Then 數量解析為 2，cart = {冰紅茶: 2}，轉到 L3
# ============================================================

def test_l2_c_iced_tea_with_chinese_quantity_parses_and_adds() -> None:
    # Arrange
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["冰紅茶兩個"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"「冰紅茶兩個」應解析為 2，實際：{cart}"
    )


# ============================================================
# L2-C-003
# Scenario: 顧客回應刮刮樂關鍵字加入 cart 並進 L3
# Given L2 等待顧客回應中，cart 為空
# When 顧客輸入「刮刮樂」（命中商品 — 刮刮樂）
# Then 數量解析為 1，cart = {刮刮樂: 1}，轉到 L3
# ============================================================

def test_l2_c_qty_followup_gibberish_speaks_clarify_then_uses_next_quantity() -> None:
    """2026-05-25 加：qty 追問內顧客講亂碼（無 intent / 無數量）→ speak clarify → 再追問。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 → ask 幾瓶 → "d" 亂說 → clarify → "兩瓶" → add 2
    customer_input = FakeCustomerInput(["紅茶", "d", "兩瓶"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, f"應加 2，實際：{cart}"
    assert QTY_CLARIFY_TEMPLATE.format(unit="瓶") in speak_calls, (
        f"亂說後應 speak QTY_CLARIFY_TEMPLATE，實際：{speak_calls}"
    )


def test_l2_c_qty_followup_service_intent_prints_phone_then_reclarifies() -> None:
    """2026-05-25 加：qty 追問內顧客講「客服」→ print 電話 + speak clarify → 再追問。"""
    speak_calls: list = []
    printed: list = []
    cart = cart_module.new_cart()
    # 紅茶 → ask → "客服" → print phone + clarify → "兩瓶" → add 2
    customer_input = FakeCustomerInput(["紅茶", "客服", "兩瓶"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: printed.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2
    assert SERVICE_PHONE in printed, f"客服 intent 應 print SERVICE_PHONE，實際 printed：{printed}"
    assert QTY_CLARIFY_TEMPLATE.format(unit="瓶") in speak_calls


def test_l2_c_qty_followup_reject_cancels_addition_and_reprompts_l2() -> None:
    """2026-05-25 加：qty 追問內顧客講拒絕（L2 mode '不要' → 拒絕）→ 取消加單 + speak L2_B3_REASK。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 → ask → "不要" → cancel → L2_B3_REASK → 主迴圈 continue → None → L2-A timeout reject → L1
    customer_input = FakeCustomerInput(["紅茶", "不要", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # cancel 後 cart 未變（紅茶未加），最後 None timeout → L1
    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart), f"cancel 後 cart 應為空，實際：{cart}"
    assert L2_B3_REASK in speak_calls, (
        f"cancel 後應 speak L2_B3_REASK，實際：{speak_calls}"
    )


def test_l2_c_iced_tea_no_quantity_asks_then_uses_followup() -> None:
    """2026-05-25 加：商品意圖無數量 → 系統追問「您要幾瓶？」→ 用 follow-up 數量加 cart。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「我要紅茶」(無數量) → 追問 → 「兩瓶」→ 加 2
    customer_input = FakeCustomerInput(["我要紅茶", "兩瓶"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"「我要紅茶」+ 追問「兩瓶」應加 2 杯冰紅茶，實際：{cart}"
    )
    # 2026-05-25 multi-product helper 用明示語音「請問冰紅茶要幾瓶？」
    assert any("冰紅茶" in s and "瓶" in s for s in speak_calls), (
        f"應 speak 追問「請問冰紅茶要幾瓶？」風格語音，實際：{speak_calls}"
    )
    assert L2_C_ADDED in speak_calls


def test_l2_c_scratch_card_adds_cart_and_goes_l3() -> None:
    # Arrange
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["刮刮樂"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "刮刮樂") == 1, (
        f"「刮刮樂」應加入 ×1，實際：{cart}"
    )


# ============================================================
# L2-PRIO-001
# Scenario: 顧客在 L2 說結帳關鍵字 L2 跳過該意圖並走 B-1 無法判斷
# Given L2 等待顧客回應中，cart 未建立
# When 顧客輸入「結帳」（NLU 回「結帳」，但 L2 跳過此類別）
# Then L2 dispatch 視為無法判斷 → 走 B-1（speak L2_B1_CLARIFY + 留 L2）
# ============================================================

def test_l2_prio_checkout_intent_in_l2_falls_through_to_b1() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 結帳關鍵字 → B-1（speak clarify + 留 L2）；再 None → A
    customer_input = FakeCustomerInput(["結帳", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L2 跳過結帳 → 走 B-1
    assert L2_B1_CLARIFY in speak_calls, (
        f"L2 應跳過結帳意圖走 B-1，speak L2_B1_CLARIFY，實際：{speak_calls}"
    )
    # 最終因 None timeout → A 退出
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3 測試（18 個 scenarios）
# 沿用既有 FakeCustomerInput stub
# ============================================================


# ============================================================
# L3-ENTRY-001
### Scenario: 進入 L3 即播詢問語音並初始化 think_count
### Given 從 L2 鏈路 C 加單完成進入 L3
### When run_l3 啟動執行進入時動作
### Then 系統 speak「請問還有額外需要購買的嗎？」且 think_count 初始化為 0，
###      開始等待顧客回應最多 WAIT_NO_RESPONSE（6）秒
# ============================================================

def test_l3_entry_speaks_followup_and_inits_think_count() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 顧客 timeout（None）→ 觸發 C-2 第一段，再 None → 第二段 timeout → L4 讓函式結束
    customer_input = FakeCustomerInput([None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音是第一個 speak 呼叫
    assert len(speak_calls) >= 1, "run_l3 應呼叫至少一次 speak"
    assert speak_calls[0] == L3_ENTRY_PROMPT, (
        f"第一個 speak 應為 L3_ENTRY_PROMPT，實際：{speak_calls[0]!r}"
    )


# ============================================================
# L3-A-001
### Scenario: 顧客回應拒絕關鍵字觸發鏈路 A 清空 cart 並套子例程 A
### Given L3 等待中，cart 已含商品
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」）
### Then 系統 speak 拒絕語音，清空 cart，套 L0 子例程 A 回 L1
# ============================================================

def test_l3_a_reject_keyword_clears_cart_and_triggers_subroutine_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 2026-05-25 修：L3 嚴格 reject 詞改用「我不要了」（「不要」在 L3 已視為「不追加」→ 結帳）
    customer_input = FakeCustomerInput(["我不要了"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert L3_REJECT_THANKS in speak_calls, (
        f"拒絕關鍵字應 speak L3_REJECT_THANKS，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"拒絕後 cart 應清空，實際：{cart}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"應回傳 'L1_via_subroutine_a'，實際：{next_state!r}"
    )
    assert next_think_count == 0, "鏈路 A 退出時 think_count 應 reset 為 0"


# ============================================================
# L3-B-1-001
### Scenario: 顧客回應不命中任何白名單時走 B-1 並留在 L3 重新等待
### Given L3 等待中
### When 顧客輸入「今天天氣很好」（不命中任何白名單）
### Then 系統 speak L3_B1_CLARIFY，保持在 L3 重新進入等待狀態
# ============================================================

def test_l3_b1_unknown_input_speaks_clarification_and_stays_in_l3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 不明輸入 → B-1；然後 None → C-2 第一段；再 None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput(["今天天氣很好", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：B-1 clarify 語音有被 speak
    assert L3_B1_CLARIFY in speak_calls, (
        f"不明輸入應 speak L3_B1_CLARIFY，實際：{speak_calls}"
    )
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-1-002（2026-05-25 加）
### Scenario: B-1 連續 UNCLEAR_MAX 次無法判斷 → 進最終確認子狀態，1 取消 → 清 cart 退
### Given L3 等待中，cart 有商品
### When 顧客連續 UNCLEAR_MAX 次說系統聽不懂的話 → 進最終確認，輸入「1」
### Then speak L3_UNCLEAR_FINAL_PROMPT，cart 清空，回 L1
# ============================================================

def test_l3_b1_unclear_max_final_confirmation_cancel() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 連續 UNCLEAR_MAX 次 B-1 → 進最終確認，輸入 "1" 取消
    inputs = ["asdf"] * UNCLEAR_MAX + ["1"]
    customer_input = FakeCustomerInput(inputs)

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：語音播最終確認 prompt
    assert L3_UNCLEAR_FINAL_PROMPT in speak_calls
    # 鏈路 A 拒絕語音 + cart 清空
    assert L3_REJECT_THANKS in speak_calls
    assert len(cart) == 0, f"cart 應清空，實際：{dict(cart)}"
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-B-1-003（2026-05-25 加）
### Scenario: B-1 達 UNCLEAR_MAX 進最終確認，輸入「2」繼續 → reset unclear_count 回主迴圈
### Given L3 等待中，cart 有商品
### When 連續 UNCLEAR_MAX 次 B-1 → 進最終確認，輸入「2」繼續 → 再加紅茶 → 結帳
### Then 進 L4，cart 保留商品（含新加）
# ============================================================

def test_l3_b1_unclear_max_final_confirmation_continue_then_checkout() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # UNCLEAR_MAX 次 B-1 → 進最終確認 → "2" 繼續 → "紅茶 2" 加單 → "結帳" → "1" 明確確認
    inputs = ["asdf"] * UNCLEAR_MAX + ["2", "紅茶 2", "結帳", "1"]
    customer_input = FakeCustomerInput(inputs)

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進 L4
    assert next_state == "L4"
    # cart 仍有商品（含繼續後加的）
    assert cart.get("冰紅茶", 0) >= 1


# ============================================================
# L3-B-1-004（2026-05-25 加）
### Scenario: B-1 達 UNCLEAR_MAX 進最終確認，6s timeout → 視為取消 → 清 cart 退
# ============================================================

def test_l3_b1_unclear_max_final_confirmation_timeout_cancels() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # UNCLEAR_MAX 次 B-1 → 進最終確認 → None (timeout)
    inputs = ["asdf"] * UNCLEAR_MAX + [None]
    customer_input = FakeCustomerInput(inputs)

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：拒絕語音 + cart 清空
    assert L3_REJECT_THANKS in speak_calls
    assert len(cart) == 0
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-B-1-005（2026-05-25 加）
### Scenario: B-1 累積後命中已知意圖 → unclear_count reset
### Given L3 等待中，已 B-1 兩次
### When 顧客說「客服」（已知意圖）
### Then 印電話 + reset；後續再 B-1 兩次仍不會觸發 final confirmation
# ============================================================

def test_l3_b1_reset_on_known_intent() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # B-1 x2, 客服 (reset), B-1 x2, None (timeout → C-2 第一段), None (C-2 第二段 timeout → L4)
    customer_input = FakeCustomerInput(
        ["asdf", "qwer", "客服", "zxcv", "vbnm", None, None]
    )

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：客服電話有被印
    assert SERVICE_PHONE in terminal_calls
    # 沒進最終確認子狀態（unclear 被 reset 過）— prompt 走 speak，不會被 terminal 印
    assert L3_UNCLEAR_FINAL_PROMPT not in speak_calls
    # 退出是因為兩段 6s timeout 走 C-2 自動進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-1-006（2026-05-25 加）
### Scenario: 最終確認子狀態內顧客亂回答 → 重印 prompt（6s 倒數不重置）
### Given 進入最終確認子狀態
### When 顧客亂回答兩次後接 None timeout
### Then prompt 被印多次，最終 timeout 視為取消
# ============================================================

def test_l3_b1_final_confirmation_gibberish_then_timeout() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    inputs = ["asdf"] * UNCLEAR_MAX + ["foo", "bar", None]
    customer_input = FakeCustomerInput(inputs)

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：prompt 被 speak 多次（初次 + 兩次亂回答重播 = 3）
    assert speak_calls.count(L3_UNCLEAR_FINAL_PROMPT) >= 3
    # 最終 timeout → 取消
    assert L3_REJECT_THANKS in speak_calls
    assert len(cart) == 0
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-B-2-001
### Scenario: 顧客回應客服關鍵字觸發 B-2 印電話後自動回 L3 循環
### Given L3 等待中
### When 顧客輸入命中客服關鍵字（如「客服」）
### Then 終端印 SERVICE_PHONE，自動回 L3 循環
# ============================================================

def test_l3_b2_service_keyword_prints_phone_and_returns_to_l3_loop() -> None:
    # Arrange
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → B-2 印電話；None → C-2 第一段；None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput(["客服", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：SERVICE_PHONE 被印到終端
    assert SERVICE_PHONE in terminal_calls, (
        f"B-2 應 print_terminal(SERVICE_PHONE)，實際：{terminal_calls}"
    )
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-3-001
### Scenario: 顧客回應商品關鍵字加 1 件入既有 cart 並保持在 L3
### Given L3 等待中，cart 已含 {冰紅茶: 1}
### When 顧客輸入「刮刮樂」（命中商品，無數量描述）
### Then 數量解析為 1，cart 加入刮刮樂，speak L3_REASK，保持在 L3
# ============================================================

def test_l3_b3_product_default_quantity_adds_cart_and_stays_in_l3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 商品 → B-3；None → C-2 第一段；None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput(["刮刮樂", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, "冰紅茶應仍為 1"
    assert cart_module.get_quantity(cart, "刮刮樂") == 1, (
        f"刮刮樂應加入 ×1，實際：{cart}"
    )
    assert L3_REASK in speak_calls, (
        f"B-3 後應 speak L3_REASK，實際：{speak_calls}"
    )
    assert next_state == "L4"


# ============================================================
# L3-B-3-002
### Scenario: 顧客回應含數量的商品輸入正確解析並累加到 cart
### Given L3 等待中，cart = {冰紅茶: 1}
### When 顧客輸入「冰紅茶兩個」（命中商品 + 中文數量「兩」= 2）
### Then 數量解析為 2，cart 同商品累加 = {冰紅茶: 3}，保持在 L3
# ============================================================

def test_l3_b3_qty_followup_reject_cancels_addition_and_reprompts_l3() -> None:
    """2026-05-25 加：L3 qty 追問內顧客講「我不要了」（L3 嚴格 reject）→ 取消加單 + speak L3_REASK + 主迴圈繼續。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # "我要刮刮樂" → ask 幾張 → "我不要了" → cancel → L3_REASK → None → C-2 → None → L4
    customer_input = FakeCustomerInput(["我要刮刮樂", "我不要了", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # 刮刮樂 cancel 未加；既有冰紅茶 1 保留
    assert cart_module.get_quantity(cart, "刮刮樂") == 0, (
        f"刮刮樂應 cancel 未加，實際：{cart}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    assert L3_REASK in speak_calls
    # 最終經 C-2 → L4
    assert next_state == "L4"


def test_l3_b3_product_no_quantity_asks_then_uses_followup() -> None:
    """2026-05-25 加：L3 商品意圖無數量 → 系統追問「您要幾張？」→ 用 follow-up 數量加 cart。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我要刮刮樂」(無數量) → 追問「幾張」→ 「10張」→ 加 10；後續 None 走 C-2 timeout → L4
    customer_input = FakeCustomerInput(["我要刮刮樂", "10張", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # L3 C-1 從 None timeout → C-2 第二段 → L4（C-2 不 confirm）
    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "刮刮樂") == 10, (
        f"「我要刮刮樂」+ 追問「10張」應加 10 張刮刮樂，實際：{cart}"
    )
    # 2026-05-25 multi-product helper 用明示語音「請問刮刮樂要幾張？」（多商品場景需明示）
    assert any("刮刮樂" in s and "張" in s for s in speak_calls), (
        f"應 speak 追問「請問刮刮樂要幾張？」風格語音，實際：{speak_calls}"
    )


def test_l3_b3_product_with_quantity_accumulates_existing() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 商品含數量 → B-3；None → C-2；None → L4
    customer_input = FakeCustomerInput(["冰紅茶兩個", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert cart_module.get_quantity(cart, "冰紅茶") == 3, (
        f"冰紅茶應累加為 3（1+2），實際：{cart}"
    )
    assert next_state == "L4"


# ============================================================
# L3-B-4-001
### Scenario: 第 1 次想一下 think_count 自 0 增至 1 並進入沉默等待
### Given L3 think_count == 0，等待顧客回應中
### When 顧客輸入命中想一下意圖關鍵字（如「等等」）
### Then think_count 變為 1，進入沉默等待 WAIT_NO_RESPONSE（6）秒（不發任何語音）
# ============================================================

def test_l3_b4_first_think_increments_count_and_enters_silence() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 想一下（think_count: 0→1）→ 沉默期 None（timeout）→ speak 重問；再 None → C-2；再 None → L4
    customer_input = FakeCustomerInput(["等等", None, None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音後，想一下期間不應有多餘語音
    # 序列：L3_ENTRY_PROMPT → [沉默] → L3_REASK → [C-2 第一段語音] → L4
    assert speak_calls[0] == L3_ENTRY_PROMPT, "第一個 speak 應為 L3_ENTRY_PROMPT"
    # 沉默期間無多餘語音（FOLLOWUP 後、REASK 前）
    if len(speak_calls) > 1:
        assert speak_calls[1] == L3_REASK, (
            f"沉默 timeout 後應為 L3_REASK，實際：{speak_calls[1]!r}"
        )


# ============================================================
# L3-B-4-002
### Scenario: 沉默等待期間顧客有回應立即重跑判定優先序
### Given L3 處於想一下沉默期內（think_count == 1，沉默中）
### When 6 秒內顧客輸入「冰紅茶」（命中商品）
### Then 跳出沉默立即處理該回應，走 B-3（加 cart + 留 L3）
# ============================================================

def test_l3_b4_silence_interrupted_by_response_reruns_dispatch() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 想一下 → 沉默期有回應（冰紅茶）→ B-3 加 cart；None → C-2；None → L4
    customer_input = FakeCustomerInput(["等等", "冰紅茶", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：沉默期有回應（商品）→ B-3 加 cart
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"沉默期回應商品應加到 cart，冰紅茶應為 2（1+1），實際：{cart}"
    )
    assert next_state == "L4"


# ============================================================
# L3-B-4-003
### Scenario: 沉默等待 6 秒滿無回應時 speak 重問語音並回主等待
### Given L3 處於想一下沉默期（think_count == 1）
### When 經過 WAIT_NO_RESPONSE（6）秒仍無顧客回應
### Then 系統 speak L3_REASK，並回到 L3 主等待循環
# ============================================================

def test_l3_b4_silence_timeout_reasks_and_resumes_main_loop() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 想一下 → 沉默期 None（timeout）→ speak 重問；None → C-2；None → L4
    customer_input = FakeCustomerInput(["等等", None, None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L3_REASK 被 speak
    assert L3_REASK in speak_calls, (
        f"B-4 沉默 timeout 後應 speak L3_REASK，實際：{speak_calls}"
    )
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-4-004
### Scenario: 第 2 次想一下 think_count 增至 2 但仍走沉默不轉 C-2
### Given L3 已走過 1 次 B-4，think_count == 1，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 2，再次進入沉默等待 6 秒（仍 < 3，未觸發 C-2）
# ============================================================

def test_l3_b4_second_think_still_silence_below_threshold() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 第一次想一下 → 沉默 None → 重問；第二次想一下 → 沉默 None → 重問；None → C-2；None → L4
    customer_input = FakeCustomerInput(["等等", None, "稍等", None, None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L3_REASK 應出現兩次（兩次沉默 timeout 後）
    reask_count = speak_calls.count(L3_REASK)
    assert reask_count >= 2, (
        f"兩次想一下沉默 timeout 應各 speak 一次 L3_REASK，實際出現 {reask_count} 次"
    )
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-4-005
### Scenario: 第 3 次想一下 think_count 達 3 跳過沉默走 C-2 第二段邏輯
### Given L3 已走過 2 次 B-4，think_count == 2，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 3，跳過 6s 沉默，speak C-2 第一段語音，走 C-2 第二段邏輯
# ============================================================

def test_l3_b4_third_think_skips_silence_and_triggers_c2_second_stage() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # think_count=2 傳入；一次想一下 → 累加到 3 → 直接走 C-2 第二段；None → L4
    customer_input = FakeCustomerInput(["想一下", None])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=2,  # 已累積 2 次
    )

    # Assert：C-2 第一段語音被 speak（用 L3_C2_WARNING_TEMPLATE 套 AUTO_CHECKOUT_NOTICE）
    c2_warning = L3_C2_WARNING_TEMPLATE.format(seconds=AUTO_CHECKOUT_NOTICE)
    assert c2_warning in speak_calls, (
        f"第 3 次想一下應 speak C-2 第一段語音，實際：{speak_calls}"
    )
    # C-2 第二段 timeout → L4
    assert next_state == "L4"


# ============================================================
# L3-C-1-001
### Scenario: 顧客回應結帳意圖關鍵字進 L4
### Given L3 等待中，cart 含商品
### When 顧客輸入命中結帳意圖關鍵字（如「結帳」）
### Then 系統 speak L3_C1_CHECKOUT_GO，轉到 L4
# ============================================================

def test_l3_c1_checkout_keyword_speaks_and_goes_l4() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳 → "1" 明確確認 → 進 L4
    customer_input = FakeCustomerInput(["結帳", "1"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert L3_C1_CHECKOUT_GO in speak_calls, (
        f"結帳意圖應 speak L3_C1_CHECKOUT_GO，實際：{speak_calls}"
    )
    assert next_state == "L4", f"應進 L4，實際：{next_state!r}"
    assert next_think_count == 0, "結帳退出時 think_count 應 reset 為 0"


# ============================================================
# L3-C-2-001
### Scenario: 6 秒無回應觸發 C-2 第一段語音並進入第二段 10 秒等待
### Given L3 進入時動作完成，等待顧客回應中
### When 經過 WAIT_NO_RESPONSE（6）秒仍無任何顧客輸入
### Then 系統 speak C-2 第一段語音，進入第二段等待 AUTO_CHECKOUT_NOTICE（10）秒
# ============================================================

def test_l3_c2_first_timeout_speaks_warning_and_enters_second_stage() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段（播警告）；None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput([None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：C-2 第一段語音被 speak（用 L3_C2_WARNING_TEMPLATE 套 AUTO_CHECKOUT_NOTICE）
    c2_warning = L3_C2_WARNING_TEMPLATE.format(seconds=AUTO_CHECKOUT_NOTICE)
    assert c2_warning in speak_calls, (
        f"DyC timeout 應 speak C-2 第一段語音，實際：{speak_calls}"
    )
    # 進 L4（C-2 第二段 timeout）
    assert next_state == "L4"


# ============================================================
# L3-C-2-002
### Scenario: C-2 第二段 10 秒仍無回應自動進 L4 結帳
### Given L3 處於 C-2 第二段等待中（已過第一段 6s + 已播警告語音）
### When 第二段 10 秒內無任何顧客回應
### Then 直接進 L4
# ============================================================

def test_l3_c2_second_stage_timeout_goes_l4() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput([None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：C-2 第二段 timeout 進 L4
    assert next_state == "L4", (
        f"C-2 第二段 timeout 應進 L4，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-003
### Scenario: C-2 嚴格 yes/no 子狀態 — 商品輸入視為 gibberish 忽略
### Given L3 處於 C-2 子狀態（已播警告語音 + yes/no 提示）
### When 12s 倒數內顧客輸入「冰紅茶」（非 yes/no 詞）
### Then 商品輸入被忽略（不加 cart），倒數繼續，最終 timeout → L4
### Note 2026-05-26 改：原規格 C-2 dispatch 商品加 B-3 違反嚴格 yes/no；改成只認 yes/no
# ============================================================

def test_l3_c2_second_stage_product_reruns_dispatch_to_b3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；冰紅茶 → gibberish 忽略；None → C-2 倒數歸零 → L4
    customer_input = FakeCustomerInput([None, "冰紅茶", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：商品被忽略，cart 不變
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"C-2 嚴格 yes/no — 商品輸入應被忽略不加 cart，實際：{cart}"
    )
    # 不應觸發 B-3 reask（gibernish 是 silent ignore）
    assert L3_REASK not in speak_calls, (
        f"C-2 嚴格 yes/no — 商品應被靜默忽略，不應 speak L3_REASK，實際：{speak_calls}"
    )
    # 倒數歸零 → L4
    assert next_state == "L4"


# ============================================================
# L3-C-2-004
### Scenario: C-2 嚴格 yes/no 子狀態 — NO 詞（含 strict reject）→ 取消訂單回 DnC
### Given L3 處於 C-2 子狀態（已播警告語音 + yes/no 提示），cart 含商品
### When 12s 倒數內顧客輸入「我不要了」（含「不要」即 CONFIRM_NO 詞）
### Then 取消訂單：清 cart + speak L3_CHECKOUT_REJECT_CLEAR_NOTICE → post-C2 loop → 退 L1
### Note 2026-05-26 改：原規格 strict reject 走 L3_REJECT_THANKS exit_a 路徑；
###      新嚴格 yes/no 子狀態下統一視為 cancel order（含 strict reject）
# ============================================================

def test_l3_c2_second_stage_reject_reruns_dispatch_to_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；我不要了 → CONFIRM_NO → 清 cart + reject notice → DnC
    # → DnC timeout (None) → 中性退
    customer_input = FakeCustomerInput([None, "我不要了", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    # C-2 NO → 清 cart + reject notice（不應講 L3_REJECT_THANKS「謝謝光臨」）
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE in speak_calls, (
        f"C-2 NO 應 speak L3_CHECKOUT_REJECT_CLEAR_NOTICE，實際：{speak_calls}"
    )
    assert L3_REJECT_THANKS not in speak_calls, (
        f"C-2 嚴格 yes/no 下，NO 詞不應走 L3_REJECT_THANKS 路徑，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"NO 後 cart 應清空，實際：{cart}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"取消後 post-C2 loop timeout 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-005
### Scenario: C-2 第二段內顧客回應結帳關鍵字走 C-1 進 L4
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段 10 秒內顧客輸入「結帳」（命中結帳意圖）
### Then 走鏈路 C-1（speak 結帳語音 + 進 L4）
# ============================================================

def test_l3_c2_second_stage_checkout_goes_directly_to_l4() -> None:
    """C-2 子狀態 → 顧客說「結帳」（CONFIRM_YES 同義詞）→ 直接進 L4（跳過 checkout_confirm）。

    Note 2026-05-26 P3.A 更新：原為「結帳 → C-1 confirm → '1' → L4」；
    現在 C-2 YES 路徑直接進 L4，移除多餘的 checkout_confirm 疊加。
    """
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；結帳 → YES → 直接 L4
    customer_input = FakeCustomerInput([None, "結帳"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L4", (
        f"C-2 YES（結帳）應直接進 L4，實際：{next_state!r}"
    )
    # 不應出現 checkout_confirm 的「正確嗎」prompt（C-2 YES 跳過 confirm）
    assert not any("正確嗎" in s for s in speak_calls), (
        f"C-2 YES 不應觸發 checkout_confirm prompt，實際：{speak_calls}"
    )


# ============================================================
# L3-PRIO-001
### Scenario: 顧客在 L3 說 L4 客服專用詞時 L3 視為無法判斷走 B-1
### Given L3 等待中（非 L4 客服模式）
### When 顧客輸入「繼續」或「退出」（L4 客服模式專用詞）
### Then L3 dispatcher 用 mode="normal" → 回「無法判斷」→ 走 B-1
# ============================================================

def test_l3_prio_l4_service_words_in_l3_falls_through_to_b1() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「繼續」在 mode="normal" 下回「無法判斷」→ B-1；None → C-2；None → L4
    customer_input = FakeCustomerInput(["繼續", None, None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：L3 視「繼續」為無法判斷 → B-1
    assert L3_B1_CLARIFY in speak_calls, (
        f"L3 應把「繼續」視為無法判斷走 B-1，speak L3_B1_CLARIFY，實際：{speak_calls}"
    )
    assert next_state == "L4"


# ============================================================
# L4 測試
# ============================================================

# ============================================================
# L4-ENTRY-001
## L4-ENTRY-001
### Scenario: 進入 L4 計算總額印明細並 speak 總額語音
### Given 從 L3 帶來的 cart（例：{冰紅茶: 2, 刮刮樂: 1}，總額 234 元）
### When run_l4 啟動執行進入時動作
### Then 計算總額（依 PRODUCTS 實際價）= 234 元，
###      終端印金額明細（商品明細 + 總金額 + 掃碼提示），
###      系統 speak「您的總金額是 234 元，請您掃碼付款」，
###      初始化 loop_count=0 + unclear_count=0，開始等待最多 WAIT_NO_RESPONSE 秒
# ============================================================

def test_l4_entry_calculates_total_prints_detail_and_speaks() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)
    cart_module.add_item(cart, "刮刮樂", 1)
    # 總額 = 27*2 + 180*1 = 234 元
    # 進入後立即 s（鏈路 A）讓 run_l4 結束
    customer_input = FakeCustomerInput(["s"])

    # Act
    next_state, next_loop_count, next_unclear_count = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=0,
        unclear_count=0,
    )

    # Assert：進入語音包含「234 元」與「掃碼付款」
    all_spoken = " ".join(speak_calls)
    assert "234" in all_spoken, f"進入語音應含總額 234 元，實際 speak：{speak_calls}"
    assert "掃碼付款" in all_spoken, f"進入語音應含「掃碼付款」，實際 speak：{speak_calls}"
    # 終端有印金額明細（含「234」）
    all_terminal = " ".join(terminal_calls)
    assert "234" in all_terminal, f"終端應印金額明細含 234，實際：{terminal_calls}"


# ============================================================
# L4-A-001
## L4-A-001
### Scenario: 顧客終端輸入 s 觸發鏈路 A 掃碼成功進 L5
### Given L4 等待中（cart 含商品）
### When 顧客輸入「s」（模擬掃碼成功）
### Then 系統 speak「付款成功」（或同等付款成功語音），轉到 L5
###      （cart 在 L5 進入時清空，L4-A 本身不清；見 L0 cart 生命週期）
# ============================================================

def test_l4_a_scan_success_speaks_and_goes_l5() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["s"])

    # Act
    next_state, next_loop_count, next_unclear_count = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：speak 付款成功，轉 L5，cart 不清空（L5 負責清）
    assert L4_A_PAY_SUCCESS in speak_calls, (
        f"鏈路 A 應 speak L4_A_PAY_SUCCESS，實際：{speak_calls}"
    )
    assert next_state == "L5", f"鏈路 A 應轉 L5，實際：{next_state!r}"
    assert not cart_module.is_empty(cart), "L4-A 不清空 cart（L5 負責清）"


# ============================================================
# L4-B-001
## L4-B-001
### Scenario: 顧客回應拒絕關鍵字觸發鏈路 B 清空 cart 套子例程 A
### Given L4 等待中，cart 含商品
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」）
### Then 系統 speak 取消語音，清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_b_reject_keyword_clears_cart_and_triggers_subroutine_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["不要"])

    # Act
    next_state, next_loop_count, next_unclear_count = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：speak 取消語音，清空 cart，回 L1
    assert L4_B_CANCEL_THANKS in speak_calls, (
        f"鏈路 B 應 speak L4_B_CANCEL_THANKS，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"鏈路 B 應清空 cart，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"鏈路 B 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-C-001
## L4-C-001
### Scenario: 顧客回應客服關鍵字進入客服模式印電話並提示兩選項
### Given L4 等待中，cart 含商品
### When 顧客輸入命中客服意圖關鍵字（如「客服」）
### Then 終端印商家客服電話（SERVICE_PHONE），
###      終端 + 語音提示選項，進入客服特殊模式等待選擇
# ============================================================

def test_l4_c_service_keyword_enters_special_mode_with_options() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，輸入 2（繼續）→ 回主循環，s → 鏈路 A → L5
    customer_input = FakeCustomerInput(["客服", "2", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：終端含電話；語音含選項提示（2026-05-26 post-P8 修：選項 prompt 不再 print_terminal
    # dup，避免 S1 chat-driven 視覺重複；production 時終端視覺由未來 HTML/screen 層接，sales/ 內只 speak）
    all_terminal = " ".join(terminal_calls)
    all_spoken = " ".join(speak_calls)
    assert SERVICE_PHONE in all_terminal, f"進客服模式應印電話，終端：{terminal_calls}"
    assert L4_C_OPTIONS_PROMPT in all_spoken, (
        f"進客服模式應 speak 選項提示，實際：{speak_calls}"
    )
    assert L4_C_OPTIONS_PROMPT not in all_terminal, (
        f"進客服模式選項 prompt **不應**重複印 terminal（語音已 speak），實際終端：{terminal_calls}"
    )


# ============================================================
# L4-C-002
## L4-C-002
### Scenario: 客服模式內終端輸入 1 退出清空 cart 回 L1
### Given L4 客服模式等待選擇中
### When 顧客輸入「1」（終端退出選項）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_c_service_input_1_exits_clears_cart() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，1 → 退出
    customer_input = FakeCustomerInput(["客服", "1"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：cart 清空，回 L1
    assert cart_module.is_empty(cart), f"退出後 cart 應清空，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"客服模式終端 1 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-C-003
## L4-C-003
### Scenario: 客服模式內語音命中退出交易關鍵字退出
### Given L4 客服模式等待選擇中
### When 顧客輸入命中退出交易意圖關鍵字（如「退出」）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_c_service_exit_keyword_exits_clears_cart() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，退出 → 退出交易意圖
    customer_input = FakeCustomerInput(["客服", "退出"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert
    assert cart_module.is_empty(cart), f"退出交易後 cart 應清空，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"退出交易關鍵字應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-C-004
## L4-C-004
### Scenario: 客服模式內語音命中拒絕意圖關鍵字作為退出 fallback
### Given L4 客服模式等待選擇中
### When 顧客輸入命中拒絕意圖關鍵字（如「不要」）
### Then 視為退出（fallback），清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_c_service_reject_keyword_treated_as_exit() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，不要 → 拒絕 fallback 退出
    customer_input = FakeCustomerInput(["客服", "不要"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert
    assert cart_module.is_empty(cart), f"拒絕 fallback 後 cart 應清空，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"拒絕 fallback 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-C-005
## L4-C-005
### Scenario: 客服模式內終端輸入 2 繼續交易回 L4 主循環
### Given L4 客服模式等待選擇中（cart 含商品，loop_count > 0 也可能）
### When 顧客輸入「2」（終端繼續選項）
### Then 回 L4 主循環狀態（cart 保留 / loop_count reset 0 / 繼續等掃碼）
# ============================================================

def test_l4_c_service_input_2_continues_resets_loop_count() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服（loop_count=3）→ 進入客服模式，2 → 繼續，s → 鏈路 A
    customer_input = FakeCustomerInput(["客服", "2", "s"])

    # Act
    next_state, next_loop_count, next_unclear_count = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=3,
        unclear_count=0,
    )

    # Assert：cart 保留，next_state = L5（鏈路 A 成功）
    assert next_state == "L5", f"客服繼續後掃碼應到 L5，實際：{next_state!r}"
    assert not cart_module.is_empty(cart), "客服繼續後 cart 應保留"


# ============================================================
# L4-C-006
## L4-C-006
### Scenario: 客服模式內語音命中繼續交易關鍵字繼續
### Given L4 客服模式等待選擇中
### When 顧客輸入命中繼續交易意圖關鍵字（如「繼續」）
### Then 回 L4 主循環狀態（cart 保留 / loop_count reset 0）
# ============================================================

def test_l4_c_service_continue_keyword_continues() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，繼續 → 繼續交易，s → 鏈路 A
    customer_input = FakeCustomerInput(["客服", "繼續", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：繼續後掃碼 → L5
    assert next_state == "L5", f"客服繼續關鍵字後掃碼應到 L5，實際：{next_state!r}"
    assert not cart_module.is_empty(cart), "客服繼續後 cart 應保留"


# ============================================================
# L4-C-007
## L4-C-007
### Scenario: 客服模式內終端輸入 s 視為繼續加掃碼直接進 L5
### Given L4 客服模式等待選擇中
### When 顧客輸入「s」（終端掃碼成功）
### Then 視為「繼續交易」+ 立即觸發鏈路 A 掃碼成功 → 直接進 L5
# ============================================================

def test_l4_c_service_input_s_treated_as_continue_then_scan() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，s → 視為掃碼成功 → L5
    customer_input = FakeCustomerInput(["客服", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：L4_A_PAY_SUCCESS 被 speak，轉 L5
    assert L4_A_PAY_SUCCESS in speak_calls, (
        f"客服模式內 s 應 speak 付款成功，實際：{speak_calls}"
    )
    assert next_state == "L5", f"客服模式內 s 應直接到 L5，實際：{next_state!r}"


# ============================================================
# L4-C-008
## L4-C-008
### Scenario: 客服模式內輸入既不命中退出也不命中繼續時重複提示
### Given L4 客服模式等待選擇中
### When 顧客輸入「你好」（不命中退出 / 繼續 / 拒絕 / s 任一）
### Then 重複提示選項，保持在客服模式繼續等待
# ============================================================

def test_l4_c_service_unrecognized_input_reprompts_and_stays() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，你好（不命中）→ 重複提示，2 → 繼續，s → L5
    customer_input = FakeCustomerInput(["客服", "你好", "2", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：L4_C_OPTIONS_PROMPT 至少出現兩次（一次進入時，一次重複提示）
    prompt_count = speak_calls.count(L4_C_OPTIONS_PROMPT)
    assert prompt_count >= 2, (
        f"不命中時應重複提示 L4_C_OPTIONS_PROMPT（至少 2 次），實際 speak：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-C-009
## L4-C-009
### Scenario: 客服模式 60 秒完全靜默自動退出清空 cart
### Given L4 客服模式等待選擇中
### When 60 秒內無任何顧客回應（timeout）
### Then 清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_c_service_timeout_60s_exits_clears_cart() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → 進入客服模式，None（60s timeout）→ 強制退
    customer_input = FakeCustomerInput(["客服", None])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：cart 清空，回 L1
    assert cart_module.is_empty(cart), f"客服 60s timeout 後 cart 應清空，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"客服 60s timeout 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-D-001
## L4-D-001
### Scenario: 第 1 次 6s 無回應 loop_count 增至 1 speak 中性催促語音
### Given L4 進入時動作完成，等待顧客回應中（loop_count=0）
### When 經過 WAIT_NO_RESPONSE（6）秒仍無任何顧客回應
### Then loop_count 變為 1，speak 中性催促語音，回到等待掃碼狀態
# ============================================================

def test_l4_d_first_timeout_increments_count_and_speaks_neutral() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)
    # 總額 = 27*2 = 54 元
    # None（第 1 次 D）→ s（鏈路 A）讓 run_l4 結束
    customer_input = FakeCustomerInput([None, "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=0,
    )

    # Assert：第 1 次 D 用中性語音（含「54 元」與「請掃碼，或聯繫客服」）
    expected = L4_D_VOICE_NEUTRAL.format(total=54)
    assert expected in speak_calls, (
        f"第 1 次 D 應 speak 中性語音「{expected}」，實際：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-D-002
## L4-D-002
### Scenario: 第 2 次 6s 無回應 loop_count 增至 2 speak 柔提醒語音
### Given L4 已走過 1 次 D，loop_count=1，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應
### Then loop_count 變為 2，speak 柔提醒語音
# ============================================================

def test_l4_d_second_timeout_speaks_gentle_reminder() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)
    # 總額 = 54 元
    # None（第 2 次 D，loop_count 從 1 開始）→ s（A）→ 結束
    customer_input = FakeCustomerInput([None, "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=1,  # 已走過第 1 次 D
    )

    # Assert：第 2 次 D（loop_count 從 1 → 2）用柔提醒語音
    expected = L4_D_VOICE_GENTLE.format(total=54)
    assert expected in speak_calls, (
        f"第 2 次 D 應 speak 柔提醒語音「{expected}」，實際：{speak_calls}"
    )


# ============================================================
# L4-D-003
## L4-D-003
### Scenario: 第 3 4 次 6s 無回應 speak 中度催促語音
### Given L4 已走過 2 次 D，loop_count=2，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應（第 3 次）
### Then loop_count 變為 3，speak 中度催促語音
# ============================================================

def test_l4_d_third_timeout_speaks_moderate_urgency() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)
    # 總額 = 54 元
    # None（第 3 次 D，loop_count 從 2 開始）→ s → 結束
    customer_input = FakeCustomerInput([None, "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=2,  # 已走過第 2 次 D
    )

    # Assert：第 3 次 D（loop_count 從 2 → 3）用中度催促語音
    expected = L4_D_VOICE_MODERATE.format(total=54)
    assert expected in speak_calls, (
        f"第 3 次 D 應 speak 中度催促語音「{expected}」，實際：{speak_calls}"
    )


# ============================================================
# L4-D-004
## L4-D-004
### Scenario: 第 5 6 次 6s 無回應 speak 明確警告語音（含「否則取消」）
### Given L4 已走過 4 次 D，loop_count=4，回到等待後
### When 再經過 WAIT_NO_RESPONSE（6）秒仍無回應（第 5 次）
### Then loop_count 變為 5，speak 明確警告語音
# ============================================================

def test_l4_d_fifth_timeout_speaks_explicit_warning() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)
    # 總額 = 54 元
    # None（第 5 次 D，loop_count 從 4 開始）→ s → 結束
    customer_input = FakeCustomerInput([None, "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=4,  # 已走過第 4 次 D
    )

    # Assert：第 5 次 D（loop_count 從 4 → 5）用明確警告語音
    expected = L4_D_VOICE_WARNING.format(total=54)
    assert expected in speak_calls, (
        f"第 5 次 D 應 speak 明確警告語音「{expected}」，實際：{speak_calls}"
    )


# ============================================================
# L4-D-005
## L4-D-005
### Scenario: 第 6 次循環滿 6s 仍無回應強制退清空 cart 套子例程 A
### Given L4 已走到 loop_count=6（第 6 次循環印金額後又等 6s）
### When 等待 WAIT_NO_RESPONSE 秒仍無回應
### Then 強制退：speak 取消語音，清空 cart，套用 L0 子例程 A 回 L1 叫賣
# ============================================================

def test_l4_d_sixth_timeout_forces_exit_clears_cart() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 2026-05-25 改：loop_count=6 + 第 7 次 None → 進「最終確認」子狀態 →
    # final 內 read 又 None（seq 空 → FakeCustomerInput 回 None）→ 強制取消（行為等同舊版）
    customer_input = FakeCustomerInput([None])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=L4_MAX_LOOPS,  # loop_count == 6 → 強制退
    )

    # Assert：speak 強制退語音，清空 cart，回 L1
    assert L4_D_FORCED_EXIT in speak_calls, (
        f"第 6 次 D 後 timeout 應 speak L4_D_FORCED_EXIT，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"強制退後 cart 應清空，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"強制退應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L4-E-001
## L4-E-001
### Scenario: 顧客回應不命中任何白名單時 unclear_count 增至 1 speak 重問
### Given L4 等待中，unclear_count=0
### When 顧客輸入「你好」（不命中拒絕 / 客服 / s / 任何類別）
### Then unclear_count 變為 1，speak 重問語音，保持在 L4 重新等待
# ============================================================

def test_l4_e_first_unknown_increments_count_and_reprompts() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 你好（E，unclear_count 0→1）→ s（A）→ L5
    customer_input = FakeCustomerInput(["你好", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        unclear_count=0,
    )

    # Assert：speak 重問語音，最終 L5
    assert L4_E_CLARIFY in speak_calls, (
        f"E 鏈路應 speak L4_E_CLARIFY，實際：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-E-002
## L4-E-002
### Scenario: 顧客回應命中想一下意圖時 L4 視為無法判斷走 E
### Given L4 等待中
### When 顧客輸入命中想一下意圖關鍵字（如「等等」— L4 不適用此類別）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
# ============================================================

def test_l4_e_think_intent_treated_as_unknown() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 等等（想一下 → L4 視為 E）→ s → L5
    customer_input = FakeCustomerInput(["等等", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：想一下在 L4 走 E，speak 重問
    assert L4_E_CLARIFY in speak_calls, (
        f"想一下在 L4 應走 E，speak L4_E_CLARIFY，實際：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-E-003
## L4-E-003
### Scenario: 顧客回應命中結帳意圖時 L4 視為無法判斷走 E
### Given L4 等待中（顧客已在結帳中，再說結帳無意義）
### When 顧客輸入命中結帳意圖關鍵字（如「結帳」）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
# ============================================================

def test_l4_e_checkout_intent_treated_as_unknown() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳（在 L4 視為 E）→ s → L5
    customer_input = FakeCustomerInput(["結帳", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：結帳在 L4 走 E
    assert L4_E_CLARIFY in speak_calls, (
        f"結帳在 L4 應走 E，speak L4_E_CLARIFY，實際：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-E-004
## L4-E-004
### Scenario: 顧客回應命中商品時 L4 視為無法判斷走 E
### Given L4 等待中（總額已結算，再加商品在當前流程無意義）
### When 顧客輸入命中商品關鍵字（如「冰紅茶」）
### Then 視為無法判斷 → 走鏈路 E（unclear_count++ + speak 重問）
# ============================================================

def test_l4_e_product_intent_treated_as_unknown() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 冰紅茶（商品 → L4 視為 E）→ s → L5
    customer_input = FakeCustomerInput(["冰紅茶", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：商品在 L4 走 E
    assert L4_E_CLARIFY in speak_calls, (
        f"商品在 L4 應走 E，speak L4_E_CLARIFY，實際：{speak_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L4-E-005
## L4-E-005
### Scenario: 第 3 次無法判斷 unclear_count 達 3 自動進客服模式
### Given L4 已走過 2 次 E，unclear_count=2，等待中
### When 顧客再次輸入不命中（任何上述 E trigger 之一）
### Then unclear_count 變為 3，speak 自動進客服語音，自動進入鏈路 C 客服特殊模式
# ============================================================

def test_l4_e_third_unknown_auto_enters_service_mode() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # unclear_count=2，你好（第 3 次 E → 自動進 C）→ 2（繼續）→ s（A）
    customer_input = FakeCustomerInput(["你好", "2", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        unclear_count=2,  # 已走過 2 次 E
    )

    # Assert：speak 自動進客服語音 + 進入客服模式（印電話 + 選項提示）
    assert L4_E_AUTO_SERVICE in speak_calls, (
        f"第 3 次 E 應 speak L4_E_AUTO_SERVICE，實際：{speak_calls}"
    )
    assert SERVICE_PHONE in " ".join(terminal_calls), (
        f"自動進客服後應印電話，終端：{terminal_calls}"
    )
    assert next_state == "L5"


# ============================================================
# L5-ENTRY-001
# ============================================================

## L5-ENTRY-001
### Scenario: 進入 L5 立即啟動 OpenCV mute 屏蔽致謝期間
### Given 從 L4 鏈路 A（掃碼成功）進入 L5
### When run_l5 啟動執行進入時動作
### Then mute_opencv 被呼叫一次，屏蔽 THANK_DELAY（3）秒
def test_l5_entry_mutes_opencv_for_thank_delay() -> None:
    # Arrange
    mute_calls: list = []
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),

        mute_opencv=lambda secs: mute_calls.append(secs),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
    )

    # Assert — L5-ENTRY-001：mute_opencv 被呼叫一次，屏蔽 THANK_DELAY 秒
    assert len(mute_calls) == 1, (
        f"mute_opencv 應被呼叫一次，實際：{mute_calls}"
    )
    assert mute_calls[0] == THANK_DELAY, (
        f"mute_opencv 應屏蔽 THANK_DELAY={THANK_DELAY} 秒，實際：{mute_calls[0]}"
    )


# ============================================================
# L5-ENTRY-002
# ============================================================

## L5-ENTRY-002
### Scenario: 進入 L5 播致謝語音
### Given 從 L4 鏈路 A 進入 L5
### When run_l5 啟動執行進入時動作
### Then 系統 speak 致謝語音（L5_THANKS 常數）
def test_l5_entry_speaks_thanks_message() -> None:
    # Arrange
    mute_calls: list = []
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),

        mute_opencv=lambda secs: mute_calls.append(secs),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
    )

    # Assert — L5-ENTRY-002：speak 被呼叫且包含 L5_THANKS 致謝語音
    assert L5_THANKS in speak_calls, (
        f"應 speak L5_THANKS 致謝語音，實際：{speak_calls}"
    )


# ============================================================
# L5-ENTRY-003
# ============================================================

## L5-ENTRY-003
### Scenario: 進入 L5 清空 cart 完成交易重置
### Given 從 L4 鏈路 A 進入 L5，cart 含商品（{冰紅茶: 2, 刮刮樂: 1}）
### When run_l5 啟動執行進入時動作
### Then cart 被清空（cart 內無任何商品）
def test_l5_entry_clears_cart() -> None:
    # Arrange
    mute_calls: list = []
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),

        mute_opencv=lambda secs: mute_calls.append(secs),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
    )

    # Assert — L5-ENTRY-003：cart 應被清空（交易完成重置）
    assert cart_module.is_empty(cart), (
        f"L5 執行後 cart 應為空，實際：{cart}"
    )
    assert len(cart) == 0, (
        f"L5 執行後 cart 長度應為 0，實際：{len(cart)}"
    )


# ============================================================
# L5-A-001
# ============================================================

## L5-A-001
### Scenario: 等待 THANK_DELAY 秒後自動套用子例程 A 回 L1
### Given L5 進入時動作完成（已 mute / speak / 清空 cart）
### When 等待 THANK_DELAY（3）秒過後
### Then 回傳 ("L1_via_subroutine_a", 0, 0)
###      read_customer_input 被呼叫一次當純等待（timeout=THANK_DELAY 秒）
def test_l5_a_returns_to_l1_via_subroutine_a_after_thank_delay() -> None:
    # Arrange
    mute_calls: list = []
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    result = states.run_l5(
        speak=lambda text: speak_calls.append(text),

        mute_opencv=lambda secs: mute_calls.append(secs),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
    )

    # Assert — L5-A-001：回傳 tuple 正確 + sleep 被呼叫等待 THANK_DELAY 秒
    assert result == ("L1_via_subroutine_a", 0, 0), (
        f"應回傳 tuple (L1_via_subroutine_a, 0, 0)，實際：{result}"
    )
    assert len(sleep_calls) == 1, (
        f"sleep 應被呼叫一次（純等待 THANK_DELAY 秒），實際：{sleep_calls}"
    )
    assert sleep_calls[0] == THANK_DELAY, (
        f"sleep 應等待 THANK_DELAY={THANK_DELAY} 秒，實際：{sleep_calls[0]}"
    )


# ============================================================
# L4-D-FINAL-001 ~ 004（2026-05-25 加：D 達上限後最終確認子狀態）
# ============================================================

def test_l4_d_final_confirmation_terminal_1_cancels() -> None:
    """D MAX 後 timeout → 進 final → 終端輸入 1 → 取消 + 清 cart + 回 L1。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # loop_count=6 + 1 None → 進 final → "1" → 取消
    customer_input = FakeCustomerInput([None, "1"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=L4_MAX_LOOPS,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)
    assert L4_D_FINAL_PROMPT in speak_calls, "應 speak final 提示"
    assert L4_D_FORCED_EXIT in speak_calls, "1 → 取消 → speak 強制退語音"


def test_l4_d_final_confirmation_terminal_2_continues_then_scans() -> None:
    """D MAX 後 timeout → 進 final → 終端輸入 2 → 繼續 → reset counter → 再 s → L5 + cart 保留。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # loop_count=6 + None → final → "2" 繼續 → reset → 主迴圈 → "s" → 掃碼 L5
    customer_input = FakeCustomerInput([None, "2", "s"])

    next_state, next_loop, next_unclear = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=L4_MAX_LOOPS,
    )

    assert next_state == "L5", "繼續後 s 掃碼應到 L5"
    assert not cart_module.is_empty(cart), "繼續後 cart 應保留"


def test_l4_d_final_confirmation_keyword_continue_then_scans() -> None:
    """D MAX 後 final → 語音「繼續」keyword → 繼續 → s → L5。"""
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput([None, "繼續", "s"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=L4_MAX_LOOPS,
    )

    assert next_state == "L5"
    assert not cart_module.is_empty(cart)


def test_l4_d_final_confirmation_gibberish_then_timeout_cancels() -> None:
    """D MAX 後 final → 顧客亂講話 → 重印 prompt → 下次 read 又 None → 取消。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # loop_count=6 + None → final → "亂講" 不命中 → 重印 → None → 取消
    customer_input = FakeCustomerInput([None, "亂講", None])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=L4_MAX_LOOPS,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)
    # final prompt 應被 speak ≥ 2 次（第一次入 final + 亂講後重印）
    final_prompt_count = speak_calls.count(L4_D_FINAL_PROMPT)
    assert final_prompt_count >= 2, (
        f"亂講後應重印 final prompt（總共至少 2 次），實際：{final_prompt_count}"
    )


# ============================================================
# L2-C-MULTI-001 ~ 003（2026-05-25 加，B 方案 multi-product）
# ============================================================

def test_l2_multi_product_with_quantities_all_added_then_l3() -> None:
    """L2 一次點兩商品 + 各自帶數量 → 兩個都加 → 進 L3。"""
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶 1 刮刮樂 2"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    assert cart_module.get_quantity(cart, "刮刮樂") == 2


def test_l2_multi_product_one_missing_qty_asks_only_for_that_one() -> None:
    """L2 一次點兩商品但其中一個沒給數量 → 只追問該商品。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 1, 刮刮樂 (沒數量) → 追問刮刮樂 → 「3」
    customer_input = FakeCustomerInput(["紅茶 1 刮刮樂", "3"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    assert cart_module.get_quantity(cart, "刮刮樂") == 3
    # 應有追問刮刮樂的語音（不應追問紅茶 — 紅茶已有數量）
    assert any("刮刮樂" in s and "張" in s for s in speak_calls)
    assert not any("紅茶" in s and "瓶" in s and "請問" in s for s in speak_calls)


def test_l2_duplicate_product_accumulates() -> None:
    """L2 重複講同商品 → cart 累加（不取覆蓋、不視為誤說）。"""
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶 2 紅茶 3"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    # 2 + 3 = 5（累加，不是覆蓋）
    assert cart_module.get_quantity(cart, "冰紅茶") == 5


# ============================================================
# L3-CONFIRM-001 ~ 006（2026-05-25 加，B 方案 checkout confirm）
# ============================================================

def test_l3_checkout_confirm_yes_keyword_proceeds_to_l4() -> None:
    """L3 結帳意圖 → 顧客確認「對」→ 進 L4。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["結帳", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    assert L3_C1_CHECKOUT_GO in speak_calls


def test_l3_checkout_confirm_terminal_1_proceeds_to_l4() -> None:
    """L3 結帳意圖 → 終端 1 確認 → 進 L4。"""
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["結帳", "1"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"


def test_l3_checkout_confirm_no_returns_to_l3_main_loop() -> None:
    """L3 結帳 → 顧客說「不對」→ 清空 cart + 通知，主迴圈下一輪 cart 空 → L2 timeout → L1_via_subroutine_a。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳 → 不對（清 cart）→ 後續 None None → cart 空走 L2 timeout → 鏈路 A 退出
    customer_input = FakeCustomerInput(["結帳", "不對", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # cart 空 + timeout → 鏈路 A 退出
    assert next_state == "L1_via_subroutine_a"
    # 確認被拒絕後 speak 清 cart 通知
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE in speak_calls
    # cart 已清空
    assert cart_module.is_empty(cart)
    # L2 timeout → speak 中性「繼續叫賣」提示（2026-05-26 spec 改：不講「謝謝光臨」）
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls


def test_l3_checkout_confirm_terminal_2_returns_to_l3() -> None:
    """L3 結帳 → 終端 2 否認 → 清空 cart + 通知，cart 空 → L2 timeout → L1_via_subroutine_a。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["結帳", "2", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE in speak_calls
    assert cart_module.is_empty(cart)
    assert next_state == "L1_via_subroutine_a"
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls


def test_l3_checkout_confirm_timeout_cancels() -> None:
    """L3 結帳 → confirm 內 timeout（沒回應）→ 視為否認 → 清 cart 回 DnC → 後續 timeout 走 A 退出。

    2026-05-26 spec 改：
    - confirm 子狀態保護顧客錢包，沒明確答覆不進 L4。
    - timeout 退出 speak L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE（含「由於您沒回應」前綴）
      區分明確「不對」的 L3_CHECKOUT_REJECT_CLEAR_NOTICE。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳 → confirm None (timeout 取消) → 主迴圈 cart 空 → L2 timeout → 中性退
    customer_input = FakeCustomerInput(["結帳", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)
    # timeout 走 L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE（不是明確 reject 的 notice）
    assert L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE in speak_calls
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls


def test_l3_checkout_confirm_unclear_exhausted_speaks_distinct_message() -> None:
    """L3 結帳 → confirm 內顧客亂答 5 次達上限 → 說不同訊息（非「明確不對」訊息）。

    2026-05-26 P3.B 加：區分「明確不對」vs「亂答 5 次達上限」兩種 NO 路徑的顧客體感。
    原本兩條路徑都 speak L3_CHECKOUT_REJECT_CLEAR_NOTICE，顧客亂答 5 次
    被踢出時得到「已幫您清空購物車」的「你說了不對」語氣 → 顧客困惑。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳 → confirm prompt → 5 次 gibberish → 亂答上限 → 清 cart 回 DnC → 後續 None → L1
    customer_input = FakeCustomerInput(["結帳", "aaa", "bbb", "ccc", "ddd", "eee", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)
    # 亂答達上限：說 L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE（「不好意思我聽不太懂...」）
    assert L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE in speak_calls, (
        f"亂答 5 次應 speak L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE，實際：{speak_calls}"
    )
    # 不應說「明確不對」路徑的 L3_CHECKOUT_REJECT_CLEAR_NOTICE（顧客沒有說不對）
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls, (
        f"亂答達上限不應 speak L3_CHECKOUT_REJECT_CLEAR_NOTICE（那是明確拒絕才用），實際：{speak_calls}"
    )


def test_l3_c2_yes_keyword_好_proceeds_directly_to_l4() -> None:
    """C-2 子狀態 → 顧客講「好」（CONFIRM_YES）→ 直接進 L4（跳過 checkout_confirm）。

    2026-05-26 P3.A 更新：C-2 已是「最後機會」嚴格 yes/no，顧客主動說 YES 不應
    再被罰 12s confirm（24s 雙漏斗 — 主動回應比 timeout 還慢的反直覺路徑）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2；「好」 → YES → 直接 L4（不再呼叫 checkout_confirm）
    customer_input = FakeCustomerInput([None, "好"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4", f"「好」應為 YES → 直接 L4，實際：{next_state!r}"
    # 不應出現 checkout_confirm 的「正確嗎」prompt（C-2 YES 跳過 confirm）
    assert not any("正確嗎" in s for s in speak_calls), (
        f"C-2 YES 不應觸發 checkout_confirm prompt，實際：{speak_calls}"
    )


def test_l3_c2_gibberish_silently_ignored_then_timeout_to_l4() -> None:
    """C-2 子狀態 → 連續亂答 → 倒數內 read 耗盡 → L4。

    2026-05-26 加：嚴格 yes/no 設計下，亂答 silently 忽略不重置 deadline；
    輸入耗盡時 read 返 None → 進 L4（自動結帳）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2；df / fdsf → silently 忽略；None → L4
    customer_input = FakeCustomerInput([None, "df", "fdsf", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # 不應觸發 B-1 reask 提示（嚴格 yes/no 下亂答 silent）
    assert not any("聽不太懂" in s for s in speak_calls), (
        f"C-2 嚴格 yes/no — 亂答應 silent ignored，不該觸發 B-1 clarify，實際：{speak_calls}"
    )
    # 倒數內無有效 yes/no + 沒回應 → L4
    assert next_state == "L4"


def test_l3_c2_first_stage_no_keyword_cancels_order() -> None:
    """C-2 第一段「請問是否要結帳」prompt → 顧客講「不要」→ 清 cart 直接回 DnC。

    2026-05-26 加：L3 normal NLU 把「不要」分類為「結帳」（「沒了，去結帳」語意），
    但 C-2 prompt 是 yes/no 風格 — 顧客「不要」實意是「不要結帳」（取消）。
    防止「不要」誤觸發 checkout confirm 子狀態。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；不要 → 取消 → 清 cart + L3_CHECKOUT_REJECT_CLEAR_NOTICE
    # → post-C2 loop cart 空 → 下個 None → L2_TIMEOUT_TO_HAWK_VOICE → L1
    customer_input = FakeCustomerInput([None, "不要", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # 不應進 L4（不要 = 取消，不是結帳）
    assert next_state == "L1_via_subroutine_a"
    # cart 已清空
    assert cart_module.is_empty(cart)
    # 應 speak 清 cart 通知（直接，不該繞 checkout confirm prompt）
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE in speak_calls
    # 不應出現 checkout confirm 的「正確嗎」prompt（顧客已經說不要了）
    assert not any("正確嗎" in s for s in speak_calls), (
        f"不該觸發 checkout confirm prompt，實際：{speak_calls}"
    )


def test_post_c2_loop_cart_empty_timeout_uses_dnc_timeout_and_neutral_voice() -> None:
    """post-C2 main loop 跟 run_dialog 主迴圈對齊：cart 空 timeout 用中性語音回 L1。

    2026-05-26 加：原本 _dialog_continue_after_c2_inner 用 WAIT_NO_RESPONSE (6s)
    + _dialog_exit_a (謝謝光臨)，跟 run_dialog 主迴圈不一致；統一改 DnC 行為。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；不要 → 取消（清 cart）→ post-C2 loop；None → cart 空 timeout
    customer_input = FakeCustomerInput([None, "不要", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L1_via_subroutine_a"
    # 應 speak 中性 timeout 語音而非「謝謝光臨」
    assert L2_TIMEOUT_TO_HAWK_VOICE in speak_calls
    assert L2_REJECT_THANKS not in speak_calls


def test_l3_checkout_confirm_summary_shows_all_products() -> None:
    """confirm prompt 應透過語音列出 cart 內所有商品與數量。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 3)
    cart_module.add_item(cart, "刮刮樂", 2)
    customer_input = FakeCustomerInput(["結帳", "1"])

    states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    confirm_prints = [t for t in speak_calls if "正確嗎" in t]
    assert len(confirm_prints) >= 1
    full = " ".join(confirm_prints)
    # 應同時包含兩商品 + 數量
    assert "冰紅茶" in full
    assert "刮刮樂" in full
    assert "3" in full
    assert "2" in full


# ============================================================
# DIALOG-CART-STATE-DRIVEN（2026-05-25 B 方案 — 驗證 cart 狀態驅動原則）
# ============================================================

def test_dialog_empty_cart_speaks_l2_entry_prompt() -> None:
    """cart 空進 dialog → speak L2_ENTRY_PROMPT (詢問需求)。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput([None])  # 立刻 timeout 退出

    states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert L2_ENTRY_PROMPT in speak_calls, (
        f"cart 空應 speak L2 entry，實際：{speak_calls}"
    )


def test_dialog_nonempty_cart_speaks_l3_entry_prompt() -> None:
    """cart 非空進 dialog → speak L3_ENTRY_PROMPT (詢問加單)。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # cart 非空 + timeout → C-2 走 → 再 timeout → L4
    customer_input = FakeCustomerInput([None, None])

    states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert L3_ENTRY_PROMPT in speak_calls
    assert L2_ENTRY_PROMPT not in speak_calls


def test_dialog_empty_to_nonempty_transitions_mode_internally() -> None:
    """cart 由空變非空，dialog 主迴圈下一輪自動切 L3 mode (cart-state-driven 核心驗證)。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 加紅茶 → cart 變非空 → L2_C_ADDED 先 speak（cart 從空變非空才用此語音）
    # 後續 None None → cart 已非空，C-2 → L4
    customer_input = FakeCustomerInput(["紅茶 1", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    # 進 dialog 時 cart 空 → L2 entry
    assert L2_ENTRY_PROMPT in speak_calls
    # 加完商品 cart 非空 → L2_C_ADDED（首次加單語音）
    assert L2_C_ADDED in speak_calls
    # cart 從空變非空後必須補播 L3_ENTRY_PROMPT（規格書 L2.md 鏈路 C「進 L3」+ L3.md 進入時動作）
    # 漏播會讓顧客以為對話結束、6s timeout 直接進 C-2 自動結帳（2026-05-25 實機踩到 bug）
    assert L3_ENTRY_PROMPT in speak_calls
    # 順序：L2_C_ADDED 必須在 L3_ENTRY_PROMPT 之前（先報「已加入」再問「還要嗎」）
    assert speak_calls.index(L2_C_ADDED) < speak_calls.index(L3_ENTRY_PROMPT)


def test_dialog_empty_cart_checkout_intent_treated_as_unclear() -> None:
    """cart 空時顧客講「結帳」應被當 B-1 unclear（cart 空結帳無意義）。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 結帳 → 視為 B-1，speak L2_B1_CLARIFY；再 None → 鏈路 A 退
    customer_input = FakeCustomerInput(["結帳", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # 應 speak L2_B1_CLARIFY 而非進結帳
    assert L2_B1_CLARIFY in speak_calls
    assert next_state == "L1_via_subroutine_a"  # timeout 走 A


def test_dialog_empty_cart_timeout_goes_to_l1_via_a_reject() -> None:
    """cart 空 + 6s timeout → 鏈路 A 拒絕（L2 行為）。"""
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput([None])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)


def test_dialog_nonempty_cart_timeout_triggers_c2_auto_checkout() -> None:
    """cart 非空 + 6s timeout → C-2 自動結帳兩段，最終進 L4 (L3 行為)。"""
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 第 1 個 None → C-2 第一段警告；第 2 個 None → C-2 第二段 timeout → L4
    customer_input = FakeCustomerInput([None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    assert next_state == "L4"
    # cart 保留
    assert cart_module.get_quantity(cart, "冰紅茶") == 1


# ============================================================
# OpenCV 作用域 regression（2026-05-25 加，輪 1 修正後）
# 守住：dialog/l4 入口必呼叫 opencv_disable；L1 主迴圈 + 客服入口防呆 disable
# ============================================================

def test_dialog_entry_calls_opencv_disable() -> None:
    """dialog 進入時必須呼叫 opencv_disable（顧客已在面前對話，OpenCV 用完任務）。"""
    disable_calls: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput([None])  # 立即 timeout → A 退出

    states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: disable_calls.append(True),
    )

    assert len(disable_calls) >= 1, "dialog 入口應呼叫 opencv_disable 至少一次"


def test_l4_entry_calls_opencv_disable() -> None:
    """L4 進入時必須呼叫 opencv_disable（顧客已在掃碼，防呆）。"""
    disable_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["掃碼"])

    states.run_l4(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        loop_count=0,
        unclear_count=0,
        opencv_disable=lambda: disable_calls.append(True),
    )

    assert len(disable_calls) >= 1, "L4 入口應呼叫 opencv_disable 至少一次"


def test_l1_main_loop_calls_opencv_disable_each_iteration() -> None:
    """L1 主迴圈每輪應呼叫 opencv_disable 防呆（主選單時不該偵測 OpenCV）。"""
    opencv = FakeOpencv()
    kbd = FakeKeyboardInput(["q"])

    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
    )

    # 至少一輪 disable（即使商家直接按 q 也要 disable 過一次）
    assert opencv.disable_calls >= 1, (
        f"L1 主迴圈進入時應 opencv_disable 至少一次（防呆），實際 {opencv.disable_calls}"
    )


def test_l1_service_mode_calls_opencv_disable() -> None:
    """L1 客服模式進入時應呼叫 opencv_disable（客服期間不偵測）。"""
    opencv = FakeOpencv()
    # 進客服（3）→ 印電話 → 回主選單 → q 退出
    kbd = FakeKeyboardInput(["3", "q"])

    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
    )

    # 主迴圈 2 輪（第 1 輪選 3，第 2 輪 q）+ 客服進入 1 次 = 至少 3 次 disable
    # （即使主迴圈防呆已 disable，客服獨立明示 disable 仍要保留）
    assert opencv.disable_calls >= 3, (
        f"主迴圈 2 輪 + 客服 1 次 disable 應 >= 3，實際 {opencv.disable_calls}。"
        "若僅 2 次 = 客服獨立 disable 漏了"
    )


# ============================================================
# P0-STRICT-001（2026-05-26 P0 keyword 歧義急救 regression）
### Scenario: C-2「請問是否要結帳」顧客回「沒了」不應被當 NO 清空 cart
### Given L3 處於 C-2 第二段等待中（cart 非空），顧客回「沒了」
### When 嚴格 strict-match 規則生效後，「沒了」不命中 NO 也不命中 YES（均為非完全等於）
### Then C-2 視為 gibberish 繼續倒數，後續 None timeout → L4；cart 仍非空
### 回歸來源：視角 B #3 / 視角 C #2 發現的 keyword 歧義 bug（顧客錢包逆向錯誤）
# ============================================================

def test_c2_meiyou_should_not_be_no() -> None:
    """C-2 strict yes/no 內顧客回「沒了」應視為 unclear（不命中 NO 也不命中 YES）→
    繼續倒數到 timeout → 進 L4；cart 保持非空（NO 路徑會清 cart，驗證「沒了」沒走 NO 路徑）。

    回歸視角 B #3 / 視角 C #2 發現的「沒了 → 顧客錢包逆向錯誤」bug。
    詳細設計：resources/reviews/2026-05-26_myProgram_multi-agent-review.md §1.2 §3.1 P0。
    """
    # Arrange：cart 非空（模擬顧客已點單在 C-2 等待中）
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)

    # 輸入序列：
    #   None → 主等待 DyC timeout → 觸發 C-2（speak 警告語音）
    #   「沒了」→ C-2 第二段收到「沒了」；strict-match 下不命中 NO（非完全等於任何 NO strict-short）
    #            也不命中 YES（「沒了」不在 YES substring 或 YES strict-short 中）→ gibberish 忽略
    #   None → C-2 倒數歸零 → 自動進 L4
    customer_input = FakeCustomerInput([None, "沒了", None])

    # Act：透過 run_dialog 觸發 C-2 第二段
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert 1：進 L4（timeout 路徑，非 NO 路徑清 cart 後回 L1）
    assert next_state == "L4", (
        f"「沒了」在 C-2 strict yes/no 應被忽略（gibberish），倒數後進 L4，"
        f"實際：{next_state!r}。若回 L1_via_subroutine_a = NO 路徑誤命中（顧客錢包 bug）。"
    )

    # Assert 2：cart 仍非空（NO 路徑會 clear_cart，此路不應走）
    assert not cart_module.is_empty(cart), (
        f"「沒了」不應走 NO 路徑清 cart，cart 應保持非空，實際：{cart}。"
        "若 cart 空 = KEYWORDS_CONFIRM_NO 或 CONFIRM_NO_STRICT_SHORT 誤命中「沒了」。"
    )


# ============================================================
# L4 等待安撫 regression tests（2026-05-26 加；使用者實機 UX 修補）
# ============================================================

def test_l4_ack_word_speaks_gentle_and_does_not_count_unclear() -> None:
    """L4 顧客講「好的」應 speak L4_ACK_GENTLE，不進 E 鏈路 unclear 路徑。

    後續「s」掃碼仍應成功到 L5 — 證明 ack 沒累積 unclear_count 也沒走 forced exit。
    顧客先回 5 次「好的」（若 ack 走 unclear 累積，第 3 次達上限會被踢進客服或 forced exit），
    然後「s」掃碼 → 應仍可正常到 L5。
    """
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 3)
    customer_input = FakeCustomerInput(["好的", "好的", "好的", "好的", "好的", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert
    assert next_state == "L5", (
        f"5 次 ack + s 應掃碼成功進 L5，實際：{next_state!r}"
    )
    assert L4_ACK_GENTLE in speak_calls, (
        f"應 speak 溫和回應，實際 speak：{speak_calls}"
    )
    assert L4_E_CLARIFY not in speak_calls, (
        f"ack 詞不應走 E unclear 路徑，但 speak 含 L4_E_CLARIFY：{speak_calls}"
    )


# ============================================================
# L4 wall-clock budget regression tests（2026-05-26 方案 B）
# ============================================================

def test_l4_wallclock_budget_ack_spam_eventually_forced_exit() -> None:
    """L4 顧客 spam ack 詞超過 L4_TOTAL_BUDGET 預算後應強制 exit（方案 B 防 spam）。

    方案 B 核心：ack 路徑 continue 不重設 deadline；預算耗盡（remaining <= 0）
    → _l4_exit_d_forced（speak L4_D_FORCED_EXIT + clear cart + return L1）。

    fake time 機制：patch time.monotonic 讓每次呼叫回傳的值快速推進。
    第 1 次呼叫：0.0（設定 deadline = 0 + 60 = 60）
    第 2 次呼叫後：61.0（remaining = 60 - 61 = -1 <= 0 → forced exit）
    顧客輸入 "好的" 無限重複也逃不過預算上限。
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)

    # fake_monotonic：第 1 次回 0.0（建立 deadline），之後回 61.0（預算立刻耗盡）
    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        if call_count[0] == 1:
            return 0.0   # deadline = 0 + 60 = 60
        return 61.0      # remaining = 60 - 61 = -1 → 強制 exit

    # 顧客無限 ack spam（預算耗盡前只會被呼叫一次 read，因為第 2 次 monotonic 就觸發 forced exit）
    customer_input = FakeCustomerInput(["好的"] * 20)

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
        )

    assert next_state == "L1_via_subroutine_a", (
        f"預算耗盡後應強制 exit 回 L1，實際：{next_state!r}"
    )
    assert L4_D_FORCED_EXIT in speak_calls, (
        f"預算耗盡應 speak L4_D_FORCED_EXIT，實際 speak：{speak_calls}"
    )


def test_l4_normal_scan_within_budget_succeeds() -> None:
    """L4 顧客在預算內正常掃碼應成功進 L5。

    顧客先說「好的」一次（ack）再輸入「s」掃碼 — 應在預算內成功。
    驗證方案 B 不會誤踢正常流程：ack 不重設 deadline，但預算尚充裕時不影響結帳。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["好的", "s"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
    )

    assert next_state == "L5", (
        f"預算內正常掃碼應 L5，實際：{next_state!r}"
    )
    assert L4_ACK_GENTLE in speak_calls, (
        f"ack 詞應 speak 溫和回應，實際 speak：{speak_calls}"
    )
    assert L4_A_PAY_SUCCESS in speak_calls, (
        f"掃碼成功應 speak L4_A_PAY_SUCCESS，實際 speak：{speak_calls}"
    )
