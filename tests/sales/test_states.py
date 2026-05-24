"""test_states.py — 測試 myProgram/sales/states.py。

對應 BDD scenarios：
    - L0-SUB-A-001：子例程觸發後立即屏蔽 OpenCV
    - L0-SUB-A-002：OPENCV_MUTE 秒後 OpenCV 恢復且立即播第 1 組叫賣
    - L0-SUB-A-003：第一輪叫賣後每 HAWK_INTERVAL 秒換下一組
    - L0-SUB-A-004：連續輪替超過 6 組時以 mod 6 回到第 1 組

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
    L2_GREETING_PROMPT,
    L2_REJECT_THANKS,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
    L3_FOLLOWUP_PROMPT,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L4_ENTRY_VOICE_TEMPLATE,
    L4_A_PAY_SUCCESS,
    L4_B_CANCEL_THANKS,
    L4_C_OPTIONS_PROMPT,
    L4_D_FORCED_EXIT,
    L4_E_CLARIFY,
    L4_E_AUTO_SERVICE,
    L4_D_VOICE_NEUTRAL,
    L4_D_VOICE_GENTLE,
    L4_D_VOICE_MODERATE,
    L4_D_VOICE_WARNING,
    L4_SERVICE_TIMEOUT,
    L4_MAX_LOOPS,
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
# L0-SUB-A-001
# ============================================================

## L0-SUB-A-001
### Scenario: 子例程觸發後立即屏蔽 OpenCV
### Given 子例程 A 已準備好（callback 注入）
### When 觸發子例程 A
### Then mute_opencv 被呼叫一次（屏蔽生效）
def test_sub_a_mutes_opencv_on_trigger() -> None:
    # Arrange
    speak_calls: list = []
    mute_calls: list = []
    unmute_calls: list = []
    scheduler = FakeScheduler()

    # Act
    states.run_subroutine_a(
        speak=lambda text: speak_calls.append(text),
        mute_opencv=lambda secs: mute_calls.append(secs),
        unmute_opencv=lambda: unmute_calls.append(True),
        schedule=scheduler.schedule,
    )

    # Assert：觸發後立即屏蔽 OpenCV（不需推進時間）
    assert len(mute_calls) == 1
    assert mute_calls[0] == OPENCV_MUTE


# ============================================================
# L0-SUB-A-002
# ============================================================

## L0-SUB-A-002
### Scenario: OPENCV_MUTE 秒後 OpenCV 恢復且立即播第 1 組叫賣
### Given 子例程 A 已觸發，模擬時間推進
### When 經過 OPENCV_MUTE (12) 秒
### Then unmute_opencv 被呼叫且第 1 組叫賣（索引 0）被 speak
def test_sub_a_unmute_and_first_hawk_after_mute_window() -> None:
    # Arrange
    speak_calls: list = []
    mute_calls: list = []
    unmute_calls: list = []
    scheduler = FakeScheduler()

    states.run_subroutine_a(
        speak=lambda text: speak_calls.append(text),
        mute_opencv=lambda secs: mute_calls.append(secs),
        unmute_opencv=lambda: unmute_calls.append(True),
        schedule=scheduler.schedule,
    )

    # Act：推進 OPENCV_MUTE 秒
    scheduler.tick(OPENCV_MUTE)

    # Assert
    assert len(unmute_calls) == 1, "unmute_opencv 應被呼叫一次"
    assert len(speak_calls) >= 1, "第 1 組叫賣應被 speak"
    assert speak_calls[0] == HAWK_SLOGANS[0], "應為第 1 組叫賣（索引 0）"


# ============================================================
# L0-SUB-A-003
# ============================================================

## L0-SUB-A-003
### Scenario: 第一輪叫賣後每 HAWK_INTERVAL 秒換下一組
### Given 子例程 A 已播第 1 組叫賣
### When 再經過 HAWK_INTERVAL (12) 秒
### Then 第 2 組叫賣（索引 1）被 speak
def test_sub_a_advances_to_next_hawk_after_interval() -> None:
    # Arrange
    speak_calls: list = []
    scheduler = FakeScheduler()

    states.run_subroutine_a(
        speak=lambda text: speak_calls.append(text),
        mute_opencv=lambda secs: None,
        unmute_opencv=lambda: None,
        schedule=scheduler.schedule,
    )

    # 推進至第 1 組叫賣
    scheduler.tick(OPENCV_MUTE)
    # 再推進 HAWK_INTERVAL → 觸發第 2 組叫賣
    scheduler.tick(HAWK_INTERVAL)

    # Assert
    assert len(speak_calls) >= 2, "第 2 組叫賣應被 speak"
    assert speak_calls[1] == HAWK_SLOGANS[1], "應為第 2 組叫賣（索引 1）"


# ============================================================
# L0-SUB-A-004
# ============================================================

## L0-SUB-A-004
### Scenario: 連續輪替超過 6 組時以 mod 6 回到第 1 組
### Given 子例程 A 已連續播第 1~6 組叫賣
### When 觸發第 7 次叫賣
### Then 第 1 組叫賣（索引 0，6 mod 6）再次被 speak
def test_sub_a_wraps_around_after_six_hawks() -> None:
    # Arrange
    speak_calls: list = []
    scheduler = FakeScheduler()

    states.run_subroutine_a(
        speak=lambda text: speak_calls.append(text),
        mute_opencv=lambda secs: None,
        unmute_opencv=lambda: None,
        schedule=scheduler.schedule,
    )

    # 推進至第 1 組叫賣（OPENCV_MUTE 秒）
    scheduler.tick(OPENCV_MUTE)
    # 再推進 6 個 HAWK_INTERVAL → 觸發第 2~7 組叫賣（第 7 組 = 索引 6 mod 6 = 0）
    for _ in range(6):
        scheduler.tick(HAWK_INTERVAL)

    # Assert：總共有 7 組叫賣（第 1 + 後 6 輪）
    assert len(speak_calls) >= 7, f"應有 7 次叫賣呼叫，實際 {len(speak_calls)} 次"
    # 第 7 次（索引 6）應為 HAWK_SLOGANS[6 % 6] = HAWK_SLOGANS[0]
    assert speak_calls[6] == HAWK_SLOGANS[0], "第 7 次叫賣應回到第 1 組（mod 6）"


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
# Given 程式剛啟動（python3.11 myProgram/myProgram.py）
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音是第一個 speak 呼叫
    assert len(speak_calls) >= 1, "run_l2 應呼叫至少一次 speak"
    assert speak_calls[0] == L2_GREETING_PROMPT, (
        f"第一個 speak 應為 L2_GREETING_PROMPT，實際：{speak_calls[0]!r}"
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：should speak L2_REJECT_THANKS and return subroutine_a state
    assert L2_REJECT_THANKS in speak_calls, (
        f"鏈路 A 應 speak L2_REJECT_THANKS，實際 speak 序列：{speak_calls}"
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：沉默期無多餘語音（不應在想一下之後、沉默期中發語音）
    # 進入語音 → L2_GREETING_PROMPT（索引 0）
    # 沉默後重問語音 → L2_B3_REASK
    # 然後 None → A → L2_REJECT_THANKS
    assert speak_calls[0] == L2_GREETING_PROMPT, "第一個 speak 應為進入語音"
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：走 C 進 L3
    assert next_state == "L3", (
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, next_think_count = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L3", f"商品命中應進 L3，實際：{next_state!r}"
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
    next_state, _ = states.run_l2(
        speak=lambda text: None,
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L3"
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

def test_l2_c_scratch_card_adds_cart_and_goes_l3() -> None:
    # Arrange
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["刮刮樂"])

    # Act
    next_state, _ = states.run_l2(
        speak=lambda text: None,
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert next_state == "L3"
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
    next_state, _ = states.run_l2(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音是第一個 speak 呼叫
    assert len(speak_calls) >= 1, "run_l3 應呼叫至少一次 speak"
    assert speak_calls[0] == L3_FOLLOWUP_PROMPT, (
        f"第一個 speak 應為 L3_FOLLOWUP_PROMPT，實際：{speak_calls[0]!r}"
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
    customer_input = FakeCustomerInput(["不要"])

    # Act
    next_state, next_think_count = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: None,
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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

def test_l3_b3_product_with_quantity_accumulates_existing() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 商品含數量 → B-3；None → C-2；None → L4
    customer_input = FakeCustomerInput(["冰紅茶兩個", None, None])

    # Act
    next_state, _ = states.run_l3(
        speak=lambda text: None,
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：進入語音後，想一下期間不應有多餘語音
    # 序列：L3_FOLLOWUP_PROMPT → [沉默] → L3_REASK → [C-2 第一段語音] → L4
    assert speak_calls[0] == L3_FOLLOWUP_PROMPT, "第一個 speak 應為 L3_FOLLOWUP_PROMPT"
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
    next_state, _ = states.run_l3(
        speak=lambda text: None,
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, next_think_count = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=2,  # 已累積 2 次
    )

    # Assert：C-2 第一段語音被 speak（包含 AUTO_CHECKOUT_NOTICE 插值）
    c2_warning = f"請問是否要結帳？如果沒回應，{AUTO_CHECKOUT_NOTICE} 秒後將為您結帳"
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
    customer_input = FakeCustomerInput(["結帳"])

    # Act
    next_state, next_think_count = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：C-2 第一段語音被 speak
    c2_warning = f"請問是否要結帳？如果沒回應，{AUTO_CHECKOUT_NOTICE} 秒後將為您結帳"
    assert c2_warning in speak_calls, (
        f"6s timeout 應 speak C-2 第一段語音，實際：{speak_calls}"
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
    next_state, _ = states.run_l3(
        speak=lambda text: None,
        do_action=lambda name: None,
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
### Scenario: C-2 第二段內顧客回應商品取消自動結帳走 B-3 加單
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段 10 秒內顧客輸入「冰紅茶」（命中商品）
### Then 取消自動結帳，重跑判定優先序 → 走 B-3（加 cart + 留 L3）
# ============================================================

def test_l3_c2_second_stage_product_reruns_dispatch_to_b3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；冰紅茶 → B-3 加 cart；None → C-2；None → L4
    customer_input = FakeCustomerInput([None, "冰紅茶", None, None])

    # Act
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert：C-2 第二段有回應 → B-3 加 cart
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"C-2 第二段回應商品應加到 cart（冰紅茶 1→2），實際：{cart}"
    )
    assert L3_REASK in speak_calls, (
        f"B-3 後應 speak L3_REASK，實際：{speak_calls}"
    )
    assert next_state == "L4"


# ============================================================
# L3-C-2-004
### Scenario: C-2 第二段內顧客回應拒絕關鍵字取消自動結帳走鏈路 A
### Given L3 處於 C-2 第二段等待中（已播警告語音），cart 含商品
### When 第二段 10 秒內顧客輸入「不要」（命中拒絕意圖）
### Then 取消自動結帳，走鏈路 A（清空 cart + 套子例程 A 回 L1）
# ============================================================

def test_l3_c2_second_stage_reject_reruns_dispatch_to_a() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；不要 → 鏈路 A（清空 cart + 回 L1）
    customer_input = FakeCustomerInput([None, "不要"])

    # Act
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert L3_REJECT_THANKS in speak_calls, (
        f"C-2 第二段拒絕應 speak L3_REJECT_THANKS，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"拒絕後 cart 應清空，實際：{cart}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"拒絕應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-005
### Scenario: C-2 第二段內顧客回應結帳關鍵字走 C-1 進 L4
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段 10 秒內顧客輸入「結帳」（命中結帳意圖）
### Then 走鏈路 C-1（speak 結帳語音 + 進 L4）
# ============================================================

def test_l3_c2_second_stage_checkout_reruns_dispatch_to_c1() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；結帳 → C-1 進 L4
    customer_input = FakeCustomerInput([None, "結帳"])

    # Act
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
    )

    # Assert
    assert L3_C1_CHECKOUT_GO in speak_calls, (
        f"C-2 第二段回應結帳應 speak L3_C1_CHECKOUT_GO，實際：{speak_calls}"
    )
    assert next_state == "L4", (
        f"結帳應進 L4，實際：{next_state!r}"
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
    next_state, _ = states.run_l3(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
    )

    # Assert：終端含電話 + 選項提示；語音含選項提示
    all_terminal = " ".join(terminal_calls)
    all_spoken = " ".join(speak_calls)
    assert SERVICE_PHONE in all_terminal, f"進客服模式應印電話，終端：{terminal_calls}"
    assert L4_C_OPTIONS_PROMPT in all_spoken, (
        f"進客服模式應 speak 選項提示，實際：{speak_calls}"
    )
    assert L4_C_OPTIONS_PROMPT in all_terminal, (
        f"進客服模式應終端印選項提示，實際：{terminal_calls}"
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
    # loop_count=6（第 6 次 D 已播語音），再 None → 強制退
    customer_input = FakeCustomerInput([None])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
        do_action=lambda name: None,
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
