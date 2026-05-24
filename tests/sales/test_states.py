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
    SERVICE_PHONE,
    L2_GREETING_PROMPT,
    L2_REJECT_THANKS,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
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
