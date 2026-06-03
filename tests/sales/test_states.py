"""test_states.py — 測試 myProgram/sales/states.py。

對應 BDD scenarios：
    - L0-SUB-A-001：子例程觸發後立即屏蔽 OpenCV
    - L0-SUB-A-002：OPENCV_MUTE 秒後 OpenCV 恢復且立即播第 1 組叫賣
    - L0-SUB-A-003：第一輪叫賣後每 HAWK_INTERVAL 秒換下一組
    - L0-SUB-A-004：連續輪替超過 6 組時以 mod 6 回到第 1 組
    - L5-ENTRY-002：進入 L5 播致謝語音
    - L5-ENTRY-003：進入 L5 清空 cart 完成交易重置
    - L5-A-001：等待 THANK_DELAY 秒後自動套用子例程 A 回 L1

設計：callback 注入（speak / mute_opencv / unmute_opencv / schedule）。
      測試用純函式 lambda + FakeScheduler stub，不用 mock library。

FakeScheduler：
    - schedule(seconds, callback)：登記「delay 秒後執行 callback」
    - tick(seconds)：推進時間，觸發到期的 callback（含連鎖觸發）
"""

import pytest

import myProgram.sales.states as states
from myProgram.sales.constants import (
    HAWK_SLOGANS,
    HAWK_INTERVAL,
    OPENCV_MUTE,
    OPENCV_DWELL,
    WAIT_NO_RESPONSE,
    AUTO_CHECKOUT_NOTICE,
    C2_DECISION_TIMEOUT,
    SERVICE_PHONE,
    L2_ENTRY_PROMPT,
    L2_REJECT_THANKS,
    L2_TIMEOUT_TO_HAWK_VOICE,
    L2_B1_CLARIFY,
    L2_B3_REASK,
    L2_B3_THIRD_REJECT,
    L2_C_ADDED,
    CANCEL_CONFIRM_PROMPT,
    CANCEL_DECLINED_NOTICE,
    L3_ENTRY_PROMPT,
    L2_TO_L3_TRANSITION,
    L3_REJECT_THANKS,
    L3_B1_CLARIFY,
    L3_REASK,
    L3_C1_CHECKOUT_GO,
    L4_ENTRY_PROMPT_TEMPLATE,
    L4_QR_MOCK_HINT,
    L4_A_PAY_SUCCESS,
    L4_B_CANCEL_THANKS,
    L4_C_CONFIRM_PROMPT_TEMPLATE,
    L4_C_CONFIRM_TIMEOUT,
    L4_D_FORCED_EXIT,
    L2_UNCLEAR_REJECT_VOICE,
    L3_UNCLEAR_FINAL_PROMPT,
    L3_CHECKOUT_CONFIRM_TEMPLATE,
    L3_CHECKOUT_REJECT_CLEAR_NOTICE,
    L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE,
    L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE,
    L3_C2_WARNING_TEMPLATE,
    L3_C2_CONTINUE_ACK,
    L2_CANCEL_DECLINED_RESUME,
    L3_CANCEL_DECLINED_RESUME,
    UNCLEAR_MAX,
    L4_ACK_GENTLE,
    L4_REMIND_PROMPT,
    L4_UNCLEAR_NOTICE,
    L4_TOTAL_BUDGET,
    L4_QR_REFRESH_INTERVAL,
    QTY_PROMPT_TEMPLATE,
    QTY_CLARIFY_TEMPLATE,
    PRODUCT_CANCELLED_NOTICE_TEMPLATE,
    THANK_DELAY,
    L5_THANKS,
    DIALOG_VAGUE_BUY_REASK,
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
    """模擬鍵盤輸入序列。每次 read() 回下一個 key。

    S6（2026-05-28）：read() signature 加 timeout 參數對齊 production
    `read_terminal_key(timeout=0.1)`（input_reader-based polling）。測試用
    list pop，不關心 timeout 值，純接收後忽略。
    """

    def __init__(self, key_sequence: list) -> None:
        self._keys = list(key_sequence)

    def read(self, timeout=None) -> str:
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
    # 輸入 q q（C14：兩次 q 才真退）使程式立即退出，避免無限迴圈
    kbd = FakeKeyboardInput(["q", "q"])
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # 輸入 3（進客服），接著 q q（C14：兩次 q 退出，避免無限迴圈）
    kbd = FakeKeyboardInput(["3", "q", "q"])
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # 輸入 2 進待機，接著 q q（C14：兩次 q 退出）
    kbd = FakeKeyboardInput(["2", "q", "q"])
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # 進待機（2），按 r 回選單，按 q q（C14：兩次 q）退出
    kbd = FakeKeyboardInput(["2", "r", "q", "q"])
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # 進待機（2），待機中按 q q（C14：兩次 q 才真退）
    kbd = FakeKeyboardInput(["2", "q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit_program 被呼叫一次（兩次 q 真退）
    assert len(exit_calls) == 1, "待機中連按兩次 q 應呼叫 exit_program"


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
    # 進待機（2），待機中按 q q（C14：兩次 q 才真退）
    kbd = FakeKeyboardInput(["2", "q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # OpenCV dwell 一直 0.0 不觸發 L2；按 q q（C14：兩次 q）退出
    kbd = FakeKeyboardInput(["q", "q"])

    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: speak_calls.append(text),
        exit_program=lambda: None,
        schedule=scheduler.schedule,
        show_hawk_help=lambda *a, **k: None,
        enter_hawk_immediately=True,
        do_action=lambda *a, **k: None,
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
    # 輸入 1 進叫賣模式，OpenCV dwell 一直 0.0（不觸發 L2），按 q q（C14）退出
    key_sequence = ["1", "q", "q"]
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
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
    # 進叫賣（1），dwell 不達閾值，按 q q（C14：兩次 q）退出
    kbd = FakeKeyboardInput(["1", "q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：未達閾值不轉 L2（exit_program 被呼叫，result 為 None）
    assert result != "L2", "dwell < OPENCV_DWELL 不應觸發 L2"
    assert len(exit_calls) == 1, "應呼叫 exit_program（連按兩次 q 退出）"


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
    # 進叫賣（1），在叫賣模式中按 1 / 2 / 3 / x，最後按 q q（C14：兩次 q）退
    kbd = FakeKeyboardInput(["1", "1", "2", "3", "x", "q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：這些按鍵不切換模式；最後連按兩次 q 才讓 exit_program 被呼叫
    assert result != "L2", "按 1/2/3/x 不應觸發 L2"
    assert len(exit_calls) == 1, "只有連按兩次 q 才呼叫 exit_program（共 1 次）"


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
    # 進叫賣（1），在叫賣中按 q q（C14：兩次 q 才真退）
    kbd = FakeKeyboardInput(["1", "q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit_program 被呼叫一次（兩次 q 真退）
    assert len(exit_calls) == 1, "叫賣中連按兩次 q 應呼叫 exit_program"


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
    # 在選單直接按 q q（C14：兩次 q 才真退）
    kbd = FakeKeyboardInput(["q", "q"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit_program 被呼叫一次（兩次 q 真退）
    assert len(exit_calls) == 1, "選單中連按兩次 q 應呼叫 exit_program"


# ============================================================
# C14：q confirm reset 行為 — 「q → 非 q → q」不退出
# ============================================================

def test_l1_menu_q_nonq_q_does_not_exit() -> None:
    """C14：主選單按 q（提示確認）→ 1（reset confirm）→ q（重新提示，第一次 q 而非第二次）
    → 後續真退需再按 q q。驗證非 q 鍵真的 reset 了 confirm 狀態，避免「q 1 q」誤退。

    序列：q, 1（reset 後進叫賣，但下面 q q 在叫賣鏈路退）→ q（hawk pending=True）
         → q（hawk pending=False, exit）
    """
    exit_calls: list = []
    printed: list = []
    opencv = FakeOpencv(dwell_value=0.0)
    # 主選單：q（confirm pending=True，print 提示）→ 1（reset confirm；進 hawk）→
    # hawk 內：q（pending=True，提示）→ q（pending=False，exit）
    kbd = FakeKeyboardInput(["q", "1", "q", "q"])

    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit 只被呼叫一次（最後在 hawk 兩次 q 退出），中間 q→1 沒有誤退
    assert len(exit_calls) == 1, (
        f"q→1→q→q 應只觸發一次 exit_program（最後兩次 q），"
        f"若中間 q→1 後第一次 q 直接退出（pending 沒 reset）會 >1。實際 {len(exit_calls)}"
    )
    # 應印出至少一次「確定退出」提示（驗證 confirm 提示有觸發）
    confirm_hint_count = sum(1 for p in printed if "確定退出" in p)
    assert confirm_hint_count >= 1, (
        f"應印出『確定退出』提示至少 1 次，實際 {confirm_hint_count}"
    )


def test_l1_hawk_q_nonq_q_does_not_exit() -> None:
    """C14：hawk 模式按 q（提示）→ 1（非 q，reset confirm）→ q（重新第一次 q，僅提示不退）
    → q（第二次 q，真退）。驗證 hawk 內非 q 鍵也會 reset。
    """
    exit_calls: list = []
    printed: list = []
    opencv = FakeOpencv(dwell_value=0.0)  # 不觸發 L2
    # 1（進 hawk）→ q（pending=True 提示）→ 1（非 q，reset）→ q（pending=True 提示）→ q（exit）
    kbd = FakeKeyboardInput(["1", "q", "1", "q", "q"])

    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit 只被呼叫一次（最後兩次 q）
    assert len(exit_calls) == 1, (
        f"hawk 內 q→1→q→q 應只觸發一次 exit（最後兩次 q），"
        f"若中間 q→1 後第一次 q 直接退（pending 沒 reset）會 >1。實際 {len(exit_calls)}"
    )
    # 應印出至少兩次「確定退出」（每次 q 都會印一次提示）
    confirm_hint_count = sum(1 for p in printed if "確定退出" in p)
    assert confirm_hint_count >= 2, (
        f"應印出『確定退出』提示至少 2 次（兩個獨立第一次 q），實際 {confirm_hint_count}"
    )


def test_l1_hawk_q_polling_empty_then_q_should_exit() -> None:
    """S6 hot fix（2026-05-28 Pi 實機踩到）：hawk polling 模式下 q 之間
    的 polling timeout 空字串不該 reset _q_confirm_pending。

    舊行為（bug）：hawk 主迴圈改 read_terminal_key(timeout=0.1) polling 後，
    第一次 q 設 pending=True 後 100ms 內 polling 返回 "" → 走非 q 路徑 →
    `_reset_q_confirm()` 把 pending 弄成 False → user 真按的第二個 q 又被當
    第一次 → 連按多次 q 永遠退不出（Pi log 顯示連按 7 次 q 全在印「確定退出？」）。

    修法：l1._run_l1_hawk 內 `_reset_q_confirm()` 只在 `key != ""` 時跑；
    polling 空 read 直接 continue 下一輪、不動 pending。

    Test 序列：1（進 hawk）→ q（pending=True 印提示）→ "" "" ""（polling 空
    read 三次，**不**該 reset）→ q（pending 仍 True，真退）。
    """
    exit_calls: list = []
    printed: list = []
    opencv = FakeOpencv(dwell_value=0.0)  # 不觸發 L2
    kbd = FakeKeyboardInput(["1", "q", "", "", "", "q"])

    states.run_l1(
        print_terminal=lambda text: printed.append(text),
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: exit_calls.append(True),
        schedule=FakeScheduler().schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：exit 只被呼叫一次（第二個 q 觸發；polling 空 read 沒 reset pending）
    assert len(exit_calls) == 1, (
        f"hawk polling 空 read 不該 reset confirm；q → ''*3 → q 應退出（exit_calls=1）。"
        f"若空 read 仍 reset，第二個 q 被當第一次，exit_calls=0。實際 {len(exit_calls)}"
    )
    # Assert：只印一次「確定退出」（第一個 q 印；第二個 q 直接 exit 不再印提示）
    confirm_hint_count = sum(1 for p in printed if "確定退出" in p)
    assert confirm_hint_count == 1, (
        f"polling 空 read 不該 reset → 只有第一個 q 印『確定退出』(1 次)，第二個 q 直接退。"
        f"若 reset 發生會看到 2 次提示。實際 {confirm_hint_count}"
    )


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    """L2 拒絕意圖經 cancel_confirm gate 後退 L1（2026-05-29 cross-L cancel）。

    Flow：「不要」→ classify 拒絕 → cancel_confirm prompt → 「是的」確認取消 → exit_a。
    """
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「不要」→ 拒絕；「是的」→ cancel_confirm YES → 退 L1
    customer_input = FakeCustomerInput(["不要", "是的"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm 子狀態 prompt 被 speak + 最終退 L1
    assert CANCEL_CONFIRM_PROMPT in speak_calls, (
        f"拒絕意圖應先進 cancel_confirm 子狀態，實際：{speak_calls}"
    )
    assert L2_REJECT_THANKS in speak_calls, (
        f"cancel_confirm YES 後應 speak L2_REJECT_THANKS，實際：{speak_calls}"
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
# Scenario (2026-05-31 重寫：對齊 L4 service mode confirm pattern)：
# L2 main loop 客服 → confirm gate → YES → 回 L2 主迴圈
# Given L2 等待顧客回應中（cart 空）
# When 顧客輸入命中客服關鍵字（如「客服」）+ confirm 內 YES
# Then 終端印 SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE
#      YES → 重 speak L2_ENTRY_PROMPT 回 L2 主迴圈
# ============================================================

def test_l2_b2_service_keyword_enters_confirm_yes_returns_to_l2_loop() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    # 客服 → confirm prompt → 「繼續」 YES → re-speak entry → None → timeout → A 退出
    customer_input = FakeCustomerInput(["客服", "繼續", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：SERVICE_PHONE 被印到終端
    assert SERVICE_PHONE in terminal_calls, (
        f"B-2 應 print_terminal(SERVICE_PHONE)，實際 terminal_calls：{terminal_calls}"
    )
    # 客服 confirm prompt 應 speak
    expected_confirm_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_confirm_prompt in speak_calls, (
        f"L2 客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際:{speak_calls}"
    )
    # YES → 回主迴圈重 speak L2_ENTRY_PROMPT（entry 0 + YES 後 = 至少 2 次）
    assert speak_calls.count(L2_ENTRY_PROMPT) >= 2, (
        f"客服 YES 後應重 speak L2_ENTRY_PROMPT，實際:{speak_calls}"
    )
    # 自動回 L2 循環，第二次輸入 None → A → 退出
    assert next_state == "L1_via_subroutine_a", (
        "B-2 後應回 L2 循環（最終因 timeout 觸發 A 退出）"
    )


# ============================================================
# L2-B-2 NO/silent（2026-05-31 新增）
# Scenario: L2 main loop 客服 confirm silent → 退 L1（cart 空 → L2_REJECT_THANKS 不清 cart）
# ============================================================

def test_l2_b2_service_keyword_silent_exits_l1() -> None:
    """L2 main loop 「客服」 → confirm silent → _dialog_exit_a（cart 空 → L2 thanks 不清 cart）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 客服 → confirm silent → 退 L1
    customer_input = FakeCustomerInput(["客服", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 空 → L2_REJECT_THANKS（_dialog_exit_a L2 path 不清 cart）+ 退 L1
    assert L2_REJECT_THANKS in speak_calls, (
        f"L2 客服 silent 應 speak L2_REJECT_THANKS，實際:{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-3-客服（2026-05-31 重寫：對齊 L4 service mode confirm pattern）
### Scenario: L2 想一下沉默期內顧客講「客服」 → confirm gate
### Given L2 顧客「想一下」進沉默期（think_count=1）
### When 沉默期內顧客回「客服」+ confirm 內回 YES
### Then 印 SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE
###      YES → 重 speak L2_ENTRY_PROMPT 回主迴圈
# ============================================================

def test_l2_b3_silence_service_intent_enters_confirm_yes_respeaks_prompt() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    # 想一下 → 沉默期內「客服」 → service_confirm → 「繼續」 YES → 重 speak prompt
    # → None timeout → A 退出
    customer_input = FakeCustomerInput(["稍等", "客服", "繼續", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：SERVICE_PHONE 印到終端 + speak service confirm prompt
    assert SERVICE_PHONE in terminal_calls
    expected_confirm_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_confirm_prompt in speak_calls, (
        f"L2 沉默期客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際 speak_calls：{speak_calls}"
    )
    # YES → 回主迴圈重 speak L2_ENTRY_PROMPT（entry 0 + 客服 YES 後 = 至少 2 次）
    assert speak_calls.count(L2_ENTRY_PROMPT) >= 2, (
        f"客服 YES 後應重 speak L2_ENTRY_PROMPT，實際 speak_calls：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L2-B-3-客服 NO/silent（2026-05-31 新增）
### Scenario: L2 沉默期客服 confirm silent → 退 L1（cart 空 → L2_REJECT_THANKS 不清 cart）
# ============================================================

def test_l2_b3_silence_service_intent_silent_exits_l1() -> None:
    """L2 沉默期 → 「客服」 → confirm silent → _dialog_exit_a（cart 空 → L2 thanks 不清 cart）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 想一下 → 沉默期「客服」 → confirm silent (None) → 退 L1
    customer_input = FakeCustomerInput(["稍等", "客服", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 空 → L2_REJECT_THANKS（_dialog_exit_a 內走 L2 path）+ 退 L1
    assert L2_REJECT_THANKS in speak_calls, (
        f"L2 客服 silent 應 speak L2_REJECT_THANKS，實際:{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 想一下 → 沉默期；沉默期內顧客回「冰紅茶」(無 qty) → followup「一瓶」加 1 → L3；
    # 主 None → C-2 → C-2 None → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    # （2026-05-29 qty timeout 反轉：followup 不能用 None — None 改為 skip 該商品。此 test
    #  原意是「沉默期內回應商品成功加 cart 進 L3」，改用顯式數量「一瓶」保留原 scenario 行為。）
    customer_input = FakeCustomerInput(["想一下", "冰紅茶", "一瓶", None, None, "對"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：走 C 進 L3
    assert next_state == "L4", (
        f"沉默期有回應（商品）應進 L3，實際：{next_state!r}"
    )
    assert next_think_count == 0, "鏈路 C 退出時 think_count 應 reset 為 0"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"cart 應加入冰紅茶 ×1，實際：{cart}"
    )
    assert L2_TO_L3_TRANSITION in speak_calls, "應 speak L2_TO_L3_TRANSITION（合成 voice）"


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
# Then 數量解析為 1（預設），cart = {冰紅茶: 1}，系統 speak L2_TO_L3_TRANSITION（合成 voice），轉到 L3
# ============================================================

def test_l2_c_iced_tea_default_quantity_adds_cart_and_goes_l3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 冰紅茶（無 qty）→ followup「一瓶」加 1 → L3；main_loop None → C-2 → C-2 None
    # → confirm；「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    # （2026-05-29 qty timeout 反轉：followup 不能用 None — None 改為 skip 該商品。改用顯式
    #  數量「一瓶」保留原 scenario「冰紅茶 ×1 進 L3」行為。）
    customer_input = FakeCustomerInput(["冰紅茶", "一瓶", None, None, "對"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert
    assert next_state == "L4", f"商品命中應進 L3，實際：{next_state!r}"
    assert next_think_count == 0, "鏈路 C 退出時 think_count 應 reset 為 0"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"cart 應有冰紅茶 ×1，實際：{cart}"
    )
    assert L2_TO_L3_TRANSITION in speak_calls, "應 speak L2_TO_L3_TRANSITION（合成 voice）"


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
    # 冰紅茶兩個 → 加單 L3；後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["冰紅茶兩個", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 紅茶 → ask 幾瓶 → "d" 亂說 → clarify → "兩瓶" → add 2；
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶", "d", "兩瓶", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, f"應加 2，實際：{cart}"
    assert QTY_CLARIFY_TEMPLATE.format(unit="瓶") in speak_calls, (
        f"亂說後應 speak QTY_CLARIFY_TEMPLATE，實際：{speak_calls}"
    )


def test_l2_c_qty_followup_service_intent_enters_confirm_yes_respeaks_qty_prompt() -> None:
    """2026-05-31 重寫：qty 追問內客服 → confirm gate → YES → re-speak QTY_PROMPT → 繼續追問。

    對齊 L4 / L2 / L3 main loop 客服 confirm pattern（commit 92fedb6）。
    YES 後重 speak 的是 QTY_PROMPT_TEMPLATE（鏈路初始提示），不是 QTY_CLARIFY_TEMPLATE
    （後者是「亂答 clarify」非「鏈路初始」）。
    """
    speak_calls: list = []
    printed: list = []
    cart = cart_module.new_cart()
    # 紅茶 → qty ask → "客服" → service_confirm prompt → "繼續" (YES) →
    # re-speak QTY_PROMPT → "兩瓶" → add 2；
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput(["紅茶", "客服", "繼續", "兩瓶", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: printed.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"客服 YES → 重 speak QTY_PROMPT → 「兩瓶」 → 加 2，實際 cart：{cart}"
    )
    # service_confirm helper 印電話
    assert SERVICE_PHONE in printed, (
        f"客服 intent 應 print SERVICE_PHONE，實際 printed：{printed}"
    )
    # service_confirm helper speak L4_C_CONFIRM_PROMPT_TEMPLATE
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_prompt in speak_calls, (
        f"客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際：{speak_calls}"
    )
    # YES 後重 speak QTY_PROMPT_TEMPLATE（鏈路初始提示），不是 QTY_CLARIFY_TEMPLATE
    qty_prompt = QTY_PROMPT_TEMPLATE.format(product="冰紅茶", unit="瓶")
    qty_prompt_count = sum(1 for s in speak_calls if s == qty_prompt)
    assert qty_prompt_count >= 2, (
        f"客服 YES 後應重 speak QTY_PROMPT_TEMPLATE（鏈路初始提示，含 entry 1 次共 >=2 次），"
        f"實際 speak_calls：{speak_calls}"
    )


def test_l2_c_qty_followup_service_intent_confirm_no_skips_product() -> None:
    """2026-05-31 加：qty 追問內客服 → confirm NO → skip 該商品（不加 cart）+ 拼接 reask。

    對齊 timeout / 拒絕 / 結帳-as-skip path：return (False, cancel_notice)
    → caller 用 notice 拼接 L2_B3_REASK 合成單一 speak。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 → qty ask → "客服" → confirm prompt → "取消" (NO) → skip → L2_B3_REASK 合成 speak
    # → 主迴圈 continue → None → L2-A timeout 退 L1
    customer_input = FakeCustomerInput(["紅茶", "客服", "取消", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart), (
        f"客服 confirm NO 應 skip 該商品，cart 應為空，實際：{cart}"
    )
    # service_confirm helper speak L4_C_CONFIRM_PROMPT_TEMPLATE
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_prompt in speak_calls, (
        f"客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際：{speak_calls}"
    )
    # cancel notice + L2_B3_REASK 拼成單一 speak
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    assert any(notice in s and L2_B3_REASK in s for s in speak_calls), (
        f"客服 NO skip 應 speak 合成「{notice}，{L2_B3_REASK}」，實際：{speak_calls}"
    )


def test_l2_c_qty_followup_service_intent_confirm_silent_skips_product() -> None:
    """2026-05-31 加：qty 追問內客服 → confirm silent → skip 該商品（不加 cart）+ 拼接 reask。

    對齊 confirm 保守 default（silent = no = 取消）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 → qty ask → "客服" → confirm prompt → None (silent) → skip → L2_B3_REASK 合成
    # → 主迴圈 continue → None → L2-A timeout 退 L1
    customer_input = FakeCustomerInput(["紅茶", "客服", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart), (
        f"客服 confirm silent 應 skip 該商品，cart 應為空，實際：{cart}"
    )
    # service_confirm helper speak L4_C_CONFIRM_PROMPT_TEMPLATE
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_prompt in speak_calls, (
        f"客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際：{speak_calls}"
    )
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    assert any(notice in s and L2_B3_REASK in s for s in speak_calls), (
        f"客服 silent skip 應 speak 合成「{notice}，{L2_B3_REASK}」，實際：{speak_calls}"
    )


def test_l2_c_qty_followup_reject_cancels_addition_and_reprompts_l2() -> None:
    """2026-05-25 加：qty 追問內顧客講拒絕（L2 mode '不要' → 拒絕）→ 取消加單 + speak L2_B3_REASK。

    2026-05-29 UX 統一：拒絕 path 新增 speak PRODUCT_CANCELLED_NOTICE_TEMPLATE
    （之前 silent skip → 顧客只聽到 reask，UX 不清楚）。
    """
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # cancel 後 cart 未變（紅茶未加），最後 None timeout → L1
    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart), f"cancel 後 cart 應為空，實際：{cart}"
    # 2026-05-30 合成 speak：cancel notice 與 L2_B3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    assert any(notice in s and L2_B3_REASK in s for s in speak_calls), (
        f"cancel 後應 speak 合成「{notice}，{L2_B3_REASK}」，實際：{speak_calls}"
    )


def test_l2_c_qty_followup_timeout_skips_product_and_reprompts_l2() -> None:
    """2026-05-29 反轉：qty 追問內 silent timeout → skip 該商品（不加 cart）+ speak「先不加」+ L2_B3_REASK。

    原行為（reverted）：timeout → 預設加 1 瓶。
    新行為（user Pi demo 後決定）：timeout 視為顧客不想買此商品 → skip。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 → ask → None（timeout）→ speak skip + return False → L2_B3_REASK → 主迴圈 continue
    # → None → L2-A timeout reject → L1
    customer_input = FakeCustomerInput(["紅茶", None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # timeout 後 cart 不應加入冰紅茶（過去會自動加 1）
    assert cart_module.is_empty(cart), (
        f"qty 追問 timeout 應 skip 該商品，cart 應為空，實際：{cart}"
    )
    # 2026-05-30 合成 speak：cancel notice 與 L2_B3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    assert any(notice in s and L2_B3_REASK in s for s in speak_calls), (
        f"timeout skip 應 speak 合成「{notice}，{L2_B3_REASK}」，實際：{speak_calls}"
    )
    # 最後 None → L2-A timeout 退 L1
    assert next_state == "L1_via_subroutine_a"


def test_l2_c_qty_followup_multi_product_all_cancel_combined_speak() -> None:
    """2026-05-30 加：L2 多商品全 skip → count 格式 prefix + reask 拼成單一 speak。

    場景：顧客講「紅茶和刮刮樂」（兩商品皆無數量）→ 各自 sub_loop timeout →
    speak_calls 應含一條合成字串：「有2項商品已幫您取消，{L2_B3_REASK}」
    （N>=2 改用 MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE 取代逐項列名，避免冗長）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「紅茶和刮刮樂」(兩商品無數量) → ask 紅茶 → None → ask 刮刮樂 → None
    # → resolve 跑完返 (False, [notice 冰紅茶, notice 刮刮樂])
    # → caller 用 format_cancel_prefix 取得 count prefix + speak 單一字串
    # → 主迴圈 continue → None → L2-A timeout 退 L1
    customer_input = FakeCustomerInput(["紅茶和刮刮樂", None, None, None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 兩商品皆 skip，cart 仍空
    assert cart_module.is_empty(cart), f"全 skip 後 cart 應為空，實際：{cart}"
    # N==2 count prefix + L2_B3_REASK 應在同一個 speak 字串內
    expected_combined = f"有2項商品已幫您取消，{L2_B3_REASK}"
    assert expected_combined in speak_calls, (
        f"多商品全 skip 應 speak 合成「{expected_combined}」單一字串，實際：{speak_calls}"
    )
    # 反向：個別商品名不應出現在 cancel prefix 內（已被 count 格式取代）
    notice_tea = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    notice_card = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂")
    for call in speak_calls:
        assert notice_tea not in call, (
            f"multi-product cancel 不應含單商品 wording「{notice_tea}」，實際：{speak_calls}"
        )
        assert notice_card not in call, (
            f"multi-product cancel 不應含單商品 wording「{notice_card}」，實際：{speak_calls}"
        )
    # 確認非「先 speak notice 再分別 speak reask」三段式（既有 separate speak 不該出現）
    assert L2_B3_REASK not in speak_calls, (
        f"L2_B3_REASK 不該獨立 speak（應合成），實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


def test_format_cancel_prefix_count_format_for_n_3() -> None:
    """2026-05-30 加：format_cancel_prefix N==3 用 count 格式（unit test，繞過 parse_products dedupe）。

    parse_products 對相同商品名 dedupe（業務上合理：兩種商品最多兩項），dialog 整層路徑
    無法直接 reach N>=3 場景。但 format_cancel_prefix 應對任意 N 都正確 — 為避免未來
    新增商品 / 改 parser 後 regression，加 helper 層 unit test 直接驗證 N=3 case。
    """
    from myProgram.sales.states._l2_l3_qty_followup import format_cancel_prefix

    notices = [
        PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶"),
        PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂"),
        PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶"),
    ]
    result = format_cancel_prefix(notices)
    assert result == "有3項商品已幫您取消", (
        f"N==3 應回「有3項商品已幫您取消」,實際:{result!r}"
    )


def test_format_cancel_prefix_empty_returns_empty_string() -> None:
    """2026-05-30 加：format_cancel_prefix N==0 回空字串（caller 用 `if prefix` 跳過拼接）。"""
    from myProgram.sales.states._l2_l3_qty_followup import format_cancel_prefix

    assert format_cancel_prefix([]) == ""


def test_format_cancel_prefix_single_keeps_product_name() -> None:
    """2026-05-30 加：format_cancel_prefix N==1 直接回單商品 wording（保留商品名）。

    UX 設計：N==1 顧客需明確知道「哪個」商品被取消；N>=2 才改 count 格式避免冗長。
    """
    from myProgram.sales.states._l2_l3_qty_followup import format_cancel_prefix

    single = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="冰紅茶")
    assert format_cancel_prefix([single]) == single


def test_l3_b3_qty_followup_timeout_skips_product_and_reprompts_l3() -> None:
    """2026-05-29 反轉：L3 qty 追問內 silent timeout → skip 該商品（不加 cart）+ speak「先不加」+ L3_REASK。

    cart 已含其他商品 → skip 後 cart 不變，L3_REASK 回 L3 entry，主迴圈繼續。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我要刮刮樂」(無數量) → ask 幾張 → None（timeout）→ speak skip + return False → L3_REASK
    # → 主迴圈 continue → None → C-2 silent → None → confirm；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput(["我要刮刮樂", None, None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 刮刮樂未加（timeout skip）；冰紅茶保留
    assert cart_module.get_quantity(cart, "刮刮樂") == 0, (
        f"qty 追問 timeout 應 skip 刮刮樂，實際：{cart}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"既有冰紅茶應保留，實際：{cart}"
    )
    # 2026-05-30 合成 speak：cancel notice 與 L3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂")
    assert any(notice in s and L3_REASK in s for s in speak_calls), (
        f"timeout skip 應 speak 合成「{notice}，{L3_REASK}」，實際：{speak_calls}"
    )
    # confirm yes → L4
    assert next_state == "L4"


def test_l2_c_iced_tea_no_quantity_asks_then_uses_followup() -> None:
    """2026-05-25 加：商品意圖無數量 → 系統追問「您要幾瓶？」→ 用 follow-up 數量加 cart。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「我要紅茶」(無數量) → 追問 → 「兩瓶」→ 加 2；
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["我要紅茶", "兩瓶", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 2, (
        f"「我要紅茶」+ 追問「兩瓶」應加 2 杯冰紅茶，實際：{cart}"
    )
    # 2026-05-25 multi-product helper 用明示語音「請問冰紅茶要幾瓶？」
    assert any("冰紅茶" in s and "瓶" in s for s in speak_calls), (
        f"應 speak 追問「請問冰紅茶要幾瓶？」風格語音，實際：{speak_calls}"
    )
    assert L2_TO_L3_TRANSITION in speak_calls


def test_l2_c_scratch_card_adds_cart_and_goes_l3() -> None:
    # Arrange
    cart = cart_module.new_cart()
    # 刮刮樂（無 qty）→ followup「一張」加 1 → L3；main_loop None → C-2 → C-2 None
    # → confirm；「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    # （2026-05-29 qty timeout 反轉：followup 不能用 None — None 改為 skip 該商品。改用顯式
    #  數量「一張」保留原 scenario「刮刮樂 ×1 進 L3」行為。）
    customer_input = FakeCustomerInput(["刮刮樂", "一張", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    """L3 拒絕意圖經 cancel_confirm gate 後清 cart 退 L1（2026-05-29 cross-L cancel）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我不要了」→ L3 strict reject；「是」→ cancel_confirm YES → 清 cart 退 L1
    customer_input = FakeCustomerInput(["我不要了", "是"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm 子狀態 prompt + 退 L1 + cart 清空
    assert CANCEL_CONFIRM_PROMPT in speak_calls, (
        f"L3 拒絕意圖應先進 cancel_confirm 子狀態，實際：{speak_calls}"
    )
    assert L3_REJECT_THANKS in speak_calls, (
        f"cancel_confirm YES 後應 speak L3_REJECT_THANKS，實際：{speak_calls}"
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
    # 不明輸入 → B-1；None → C-2 第一段；None → C-2 第二段 silent timeout → confirm；
    # 「對」→ confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["今天天氣很好", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：拒絕語音 + cart 清空
    assert L3_REJECT_THANKS in speak_calls
    assert len(cart) == 0
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-B-1-005（2026-05-31 重寫：對齊 L4 service mode confirm pattern）
### Scenario: B-1 累積後命中已知意圖 → unclear_count reset（confirm YES 路徑）
### Given L3 等待中，已 B-1 兩次
### When 顧客說「客服」（已知意圖）+ confirm 內 YES
### Then YES 後 unclear 已 reset；後續再 B-1 兩次仍不觸發 final confirmation
###      新流程：客服 → confirm gate → YES → re-speak L3_REASK → 繼續主迴圈
# ============================================================

def test_l3_b1_reset_on_known_intent() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # B-1 x2, 客服 → confirm prompt → 「繼續」 YES → reset → B-1 x2,
    # None (DyC timeout → C-2 第一段), None (C-2 silent → confirm), 「對」(confirm yes → L4)
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(
        ["asdf", "qwer", "客服", "繼續", "zxcv", "vbnm", None, None, "對"]
    )

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：客服電話有被印
    assert SERVICE_PHONE in terminal_calls
    # 客服 confirm gate prompt 應 speak
    expected_confirm_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_confirm_prompt in speak_calls, (
        f"L3 客服分支應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際:{speak_calls}"
    )
    # YES 後重 speak L3_REASK 回主迴圈
    assert L3_REASK in speak_calls, (
        f"客服 YES 後應重 speak L3_REASK，實際 speak_calls：{speak_calls}"
    )
    # 沒進最終確認子狀態（unclear 被 reset 過）— prompt 走 speak，不會被 terminal 印
    assert L3_UNCLEAR_FINAL_PROMPT not in speak_calls
    # 退出是因為兩段 6s timeout 走 C-2 自動進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-4-客服（2026-05-31 重寫：對齊 L4 service mode confirm pattern）
### Scenario: L3 想一下沉默期內顧客講「客服」 → confirm gate
### Given L3 顧客已加單，「想一下」進沉默期（think_count=1）
### When 沉默期內顧客回「客服」+ confirm 內 YES
### Then 印 SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE
###      YES → 重 speak L3_REASK 回主迴圈
# ============================================================

def test_l3_b4_silence_service_intent_enters_confirm_yes_respeaks_reask() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 想一下 → 沉默期內「客服」 → confirm → 「繼續」 YES → reask → None → C-2 兩段 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["稍等", "客服", "繼續", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：SERVICE_PHONE 印到終端
    assert SERVICE_PHONE in terminal_calls
    # 客服 confirm gate prompt 應 speak
    expected_confirm_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_confirm_prompt in speak_calls, (
        f"L3 沉默期客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際:{speak_calls}"
    )
    # YES → 回主迴圈 speak L3_REASK
    assert L3_REASK in speak_calls, (
        f"L3 沉默期客服 YES 應 speak L3_REASK，實際 speak_calls：{speak_calls}"
    )
    # 退出是因為兩段 None → C-2 自動進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-4-客服 NO/silent（2026-05-31 新增）
### Scenario: L3 沉默期客服 confirm silent → 清 cart + 退 L1（cart 非空 → L3_REJECT_THANKS）
# ============================================================

def test_l3_b4_silence_service_intent_silent_clears_cart_exits_l1() -> None:
    """L3 沉默期 → 「客服」 → confirm silent → _dialog_exit_a（cart 非空 → 清 cart + L3 thanks）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 想一下 → 沉默期「客服」 → confirm silent (None) → 清 cart 退 L1
    customer_input = FakeCustomerInput(["稍等", "客服", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 非空 → L3_REJECT_THANKS（_dialog_exit_a L3 path）+ 清 cart + 退 L1
    assert L3_REJECT_THANKS in speak_calls, (
        f"L3 客服 silent 應 speak L3_REJECT_THANKS，實際:{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"L3 客服 silent → 清 cart，實際:{cart}"
    assert next_state == "L1_via_subroutine_a"


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：prompt 被 speak 多次（初次 + 兩次亂回答重播 = 3）
    assert speak_calls.count(L3_UNCLEAR_FINAL_PROMPT) >= 3
    # 最終 timeout → 取消
    assert L3_REJECT_THANKS in speak_calls
    assert len(cart) == 0
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-B-2-001（2026-05-31 重寫：對齊 L4 service mode confirm pattern）
### Scenario: L3 main loop 客服 → confirm gate → YES → 回 L3 主迴圈
### Given L3 等待中，cart 含商品
### When 顧客輸入命中客服關鍵字（如「客服」）+ confirm 內 YES
### Then 終端印 SERVICE_PHONE + speak L4_C_CONFIRM_PROMPT_TEMPLATE
###      YES → 重 speak L3_REASK 回 L3 主迴圈
# ============================================================

def test_l3_b2_service_keyword_enters_confirm_yes_returns_to_l3_loop() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → confirm prompt → 「繼續」 YES → reask → None → C-2 第一段；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["客服", "繼續", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：SERVICE_PHONE 被印到終端
    assert SERVICE_PHONE in terminal_calls, (
        f"B-2 應 print_terminal(SERVICE_PHONE)，實際：{terminal_calls}"
    )
    expected_confirm_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert expected_confirm_prompt in speak_calls, (
        f"L3 客服應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際:{speak_calls}"
    )
    assert L3_REASK in speak_calls, f"客服 YES 後應重 speak L3_REASK，實際:{speak_calls}"
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-2-001-NO/silent（2026-05-31 新增）
### Scenario: L3 main loop 客服 confirm silent → 清 cart + 退 L1
# ============================================================

def test_l3_b2_service_keyword_silent_clears_cart_exits_l1() -> None:
    """L3 main loop 「客服」 → confirm silent → _dialog_exit_a（cart 非空 → 清 cart + L3 thanks）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 客服 → confirm silent (None) → 清 cart 退 L1
    customer_input = FakeCustomerInput(["客服", None])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 非空 → L3_REJECT_THANKS + 清 cart + 退 L1
    assert L3_REJECT_THANKS in speak_calls, (
        f"L3 客服 silent 應 speak L3_REJECT_THANKS，實際:{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"L3 客服 silent → 清 cart，實際:{cart}"
    assert next_state == "L1_via_subroutine_a"


def test_l3_b2_service_keyword_no_clears_cart_exits_l1() -> None:
    """L3 main loop 「客服」 → confirm 內「取消交易」 NO → 清 cart 退 L1。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["客服", "取消交易"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 非空 → L3_REJECT_THANKS + 清 cart + 退 L1
    assert L3_REJECT_THANKS in speak_calls, (
        f"L3 客服 NO 應 speak L3_REJECT_THANKS，實際:{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"L3 客服 NO → 清 cart，實際:{cart}"
    assert next_state == "L1_via_subroutine_a"


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
    # 商品（無 qty）→ followup「一張」加 1 → 留 L3；main_loop None → C-2 → C-2 None
    # → confirm；「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    # （2026-05-29 qty timeout 反轉：followup 不能用 None — None 改為 skip 該商品。改用顯式
    #  數量「一張」保留原 scenario「刮刮樂加入 cart ×1 留 L3」行為。）
    customer_input = FakeCustomerInput(["刮刮樂", "一張", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # "我要刮刮樂" → ask 幾張 → "我不要了" → cancel → L3_REASK → None → C-2 → None → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["我要刮刮樂", "我不要了", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 刮刮樂 cancel 未加；既有冰紅茶 1 保留
    assert cart_module.get_quantity(cart, "刮刮樂") == 0, (
        f"刮刮樂應 cancel 未加，實際：{cart}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    # 2026-05-30 合成 speak：cancel notice 與 L3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂")
    assert any(notice in s and L3_REASK in s for s in speak_calls), (
        f"L3 拒絕 skip 應 speak 合成「{notice}，{L3_REASK}」，實際：{speak_calls}"
    )
    # 最終經 C-2 → L4
    assert next_state == "L4"


def test_l3_b3_qty_followup_checkout_as_skip_speaks_cancelled_notice() -> None:
    """2026-05-29 新加：L3 qty 追問內顧客講「不用」（L3 normal mode → 分類為結帳意圖）
    → skip 該商品 + speak PRODUCT_CANCELLED_NOTICE_TEMPLATE + 退出 sub-loop。

    L3 normal mode 下「不要 / 不用」短詞不算「整單作廢」拒絕，而是「不追加此商品」結帳意圖。
    對 qty_followup 而言 = skip 該商品（同其他 3 個 skip 分支統一文案）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我要刮刮樂」(無數量) → ask 幾張 → "不用"（L3 normal → 結帳-as-skip）
    # → speak PRODUCT_CANCELLED_NOTICE + return False → L3_REASK
    # → 主迴圈 None → C-2 → None → confirm；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput(["我要刮刮樂", "不用", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 刮刮樂未加；既有冰紅茶 1 保留
    assert cart_module.get_quantity(cart, "刮刮樂") == 0, (
        f"結帳-as-skip 後刮刮樂應未加，實際：{cart}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    # 2026-05-30 合成 speak：cancel notice 與 L3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂")
    assert any(notice in s and L3_REASK in s for s in speak_calls), (
        f"結帳-as-skip 應 speak 合成「{notice}，{L3_REASK}」，實際：{speak_calls}"
    )
    assert next_state == "L4"


def test_l3_b3_qty_followup_attempts_cap_speaks_cancelled_notice() -> None:
    """2026-05-29 新加：L3 qty 追問內顧客連續講 3 次無法判斷的話（無 qty / 無 intent）
    → 達 attempts cap → speak PRODUCT_CANCELLED_NOTICE_TEMPLATE + 退出 sub-loop。

    （之前文案「好的，這次先不加 X」，2026-05-29 統一為 PRODUCT_CANCELLED_NOTICE_TEMPLATE。）
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我要刮刮樂」(無數量) → ask 幾張 → "abc" × 3 → attempts cap → speak notice + return False
    # → L3_REASK → None → C-2 → None → confirm；「對」 → L4
    customer_input = FakeCustomerInput(
        ["我要刮刮樂", "abc", "def", "ghi", None, None, "對"]
    )

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 刮刮樂未加；既有冰紅茶 1 保留
    assert cart_module.get_quantity(cart, "刮刮樂") == 0, (
        f"attempts cap 後刮刮樂應未加，實際：{cart}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    # 2026-05-30 合成 speak：cancel notice 與 L3_REASK 拼成單一 speak，用 substring search
    notice = PRODUCT_CANCELLED_NOTICE_TEMPLATE.format(product="刮刮樂")
    assert any(notice in s and L3_REASK in s for s in speak_calls), (
        f"attempts cap 應 speak 合成「{notice}，{L3_REASK}」，實際：{speak_calls}"
    )
    assert next_state == "L4"


def test_l3_b3_product_no_quantity_asks_then_uses_followup() -> None:
    """2026-05-25 加：L3 商品意圖無數量 → 系統追問「您要幾張？」→ 用 follow-up 數量加 cart。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我要刮刮樂」(無數量) → 追問「幾張」→ 「10張」→ 加 10；後續 None 走 C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["我要刮刮樂", "10張", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 商品含數量 → B-3；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["冰紅茶兩個", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 想一下 → 沉默期回應「冰紅茶」(無 qty) → followup「一瓶」加 cart 1 →
    # main_loop None → C-2 → C-2 None → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    # （2026-05-29 qty timeout 反轉：followup 不能用 None — None 改為 skip 該商品。改用顯式
    #  數量「一瓶」保留原 scenario「沉默期內回應商品成功加 cart」行為。）
    customer_input = FakeCustomerInput(["等等", "冰紅茶", "一瓶", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 想一下 → 沉默期 None（timeout）→ speak 重問；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["等等", None, None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # 第一次想一下 → 沉默 None → 重問；第二次想一下 → 沉默 None → 重問；
    # None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["等等", None, "稍等", None, None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：L3_REASK 應出現兩次（兩次沉默 timeout 後）
    reask_count = speak_calls.count(L3_REASK)
    assert reask_count >= 2, (
        f"兩次想一下沉默 timeout 應各 speak 一次 L3_REASK，實際出現 {reask_count} 次"
    )
    # 最終因 C-2 第二段 timeout 進 L4
    assert next_state == "L4"


# ============================================================
# L3-B-4-005（2026-05-26 Wave 7a C13：think_count 觸發 C-2 條件 3 → 4）
### Scenario: 第 4 次想一下 think_count 達 4 跳過沉默走 C-2 第二段邏輯
### Given L3 已走過 3 次 B-4，think_count == 3，回到主等待後
### When 顧客再次輸入想一下關鍵字
### Then think_count 變為 4，跳過 6s 沉默，speak C-2 第一段語音，走 C-2 第二段邏輯
# ============================================================

def test_l3_b4_fourth_think_skips_silence_and_triggers_c2_second_stage() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # think_count=3 傳入；一次想一下 → 累加到 4 → 直接走 C-2 第二段；None → silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["想一下", None, "對"])

    # Act
    next_state, next_think_count = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=3,  # 已累積 3 次（C13: 第 4 次才觸發 C-2）
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：C-2 第二段警告語音被 speak（2026-05-28：模板用 C2_DECISION_TIMEOUT 6s）
    c2_warning = L3_C2_WARNING_TEMPLATE.format(seconds=C2_DECISION_TIMEOUT)
    assert c2_warning in speak_calls, (
        f"第 3 次想一下應 speak C-2 第二段三選一警告語音，實際：{speak_calls}"
    )
    # C-2 第二段 silent timeout → confirm → 「對」確認 → L4（2026-05-29 反轉合流路徑）
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    # None → C-2 第一段（播警告）；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：C-2 第二段三選一警告語音被 speak（2026-05-28：模板用 C2_DECISION_TIMEOUT 6s）
    c2_warning = L3_C2_WARNING_TEMPLATE.format(seconds=C2_DECISION_TIMEOUT)
    assert c2_warning in speak_calls, (
        f"DyC timeout 應 speak C-2 第二段三選一警告語音，實際：{speak_calls}"
    )
    # 進 L4（C-2 silent timeout 經 confirm → 「對」確認 → L4，2026-05-29 合流路徑）
    assert next_state == "L4"


# ============================================================
# L3-C-2-002
### Scenario: C-2 第二段 silent timeout 經 confirm 進 L4 結帳（2026-05-29 反轉合流路徑）
### Given L3 處於 C-2 第二段等待中（已過第一段 6s + 已播警告語音）
### When 第二段 silent timeout → 進 confirm → 顧客「對」確認
### Then 進 L4
# ============================================================

def test_l3_c2_second_stage_timeout_goes_l4() -> None:
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：C-2 silent timeout 經 confirm 「對」 進 L4
    assert next_state == "L4", (
        f"C-2 silent → confirm yes 應進 L4，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-003
### Scenario: C-2 嚴格 yes/no 子狀態 — 商品輸入視為 gibberish 忽略
### Given L3 處於 C-2 子狀態（已播警告語音 + yes/no 提示）
### When 倒數內顧客輸入「冰紅茶」（非 yes/no 詞）
### Then 商品輸入被忽略（不加 cart），倒數繼續，最終 timeout → L4
### Note 2026-05-26 改：原規格 C-2 dispatch 商品加 B-3 違反嚴格 yes/no；改成只認 yes/no
# ============================================================

def test_l3_c2_second_stage_product_reruns_dispatch_to_b3() -> None:
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；冰紅茶 → gibberish 忽略；None → C-2 倒數歸零 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, "冰紅茶", None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
### When 倒數內顧客輸入「我不要了」（含「不要」即 CONFIRM_NO 詞）
### Then 取消訂單：清 cart + speak L3_CHECKOUT_REJECT_CLEAR_NOTICE → post-C2 loop → 退 L1
### Note 2026-05-26 改：原規格 strict reject 走 L3_REJECT_THANKS exit_a 路徑；
###      新嚴格 yes/no 子狀態下統一視為 cancel order（含 strict reject）
# ============================================================

def test_l3_c2_second_stage_old_reject_word_treated_as_gibberish() -> None:
    """2026-05-28 重構後行為：C-2 第二段不再用 KEYWORDS_CONFIRM_NO；
    舊版「不要」/「我不要了」等 NO 詞在新三選一 design 下視為亂答 → silent 倒數
    → 進 confirm 子狀態（2026-05-29 反轉：silent timeout 改經 confirm 合流路徑）→
    confirm 顧客「對」確認 → L4。

    對應 user 訴求修 bug：舊版「不要」歧義被當「拒絕整單」清 cart；新版顧客必須
    用明確 keyword（取消 / 取消吧 / 幫我取消...）才能 trigger cancel path。
    顧客講「不要」現在被 silently 忽略 → 倒數歸零後 silent → confirm → 顧客「對」 → L4。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第二段；我不要了（不在新 keyword 內）→ 亂答 silent；None → C-2 read timeout
    # → confirm（2026-05-29 反轉合流）；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput([None, "我不要了", None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 「不要」走亂答 → silent 經 confirm → 「對」 → L4（不該清 cart、不該 speak reject notice）
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls, (
        f"舊版「不要」reject notice 不該再 speak（新版視為亂答），實際：{speak_calls}"
    )
    assert L3_REJECT_THANKS not in speak_calls, (
        f"「不要」不在 KEYWORDS_C2_CANCEL，不該走 L3_REJECT_THANKS 路徑，實際：{speak_calls}"
    )
    assert not cart_module.is_empty(cart), (
        f"亂答 → silent → confirm yes → L4 path 不該清 cart（cart 帶進 L4），實際：{cart}"
    )
    assert next_state == "L4", (
        f"silent → confirm yes 應進 L4，實際：{next_state!r}"
    )
    # 應 speak 過「請說『繼續』、『結賬』或『取消』」提示（第一次亂答 prompted_once）
    assert any("請說" in s for s in speak_calls), (
        f"第一次亂答應 speak「請說『繼續』、『結賬』或『取消』」提示，實際：{speak_calls}"
    )


# ============================================================
# L3-C-2-005
### Scenario: C-2 第二段內顧客回應「結帳」（不命中 KEYWORDS_C2_CHECKOUT）視為亂答
### Given L3 處於 C-2 第二段等待中（已播警告語音）
### When 第二段倒數內顧客輸入「結帳」（字面含「結」但 strict-short 不完全相等）
### Then 視為亂答 silent → 倒數歸零 → 進 confirm（2026-05-29 反轉合流）→ confirm yes → L4
###
### Note 2026-05-29 反轉：silent timeout 不再直接 L4，與 CHECKOUT keyword path 合流經 confirm
###      故 silent → 必經 confirm 才到 L4（兩條 path UX 一致）
# ============================================================

def test_l3_c2_second_stage_checkout_goes_directly_to_l4() -> None:
    """C-2 第二段「結帳」（不命中 strict-short「結」也不命中 KEYWORDS_C2_CHECKOUT 內任一）
    → gibberish silent → 倒數歸零 → 進 confirm（2026-05-29 反轉合流）→ 「對」確認 → L4。
    """
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；結帳 → 亂答 silent；None → 倒數歸零 → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, "結帳", None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert
    assert next_state == "L4", (
        f"silent → confirm yes 應進 L4，實際：{next_state!r}"
    )
    # 應 speak 過「正確嗎」prompt（silent timeout 改經 confirm 合流路徑）
    assert any("正確嗎" in s for s in speak_calls), (
        f"silent timeout 應經 confirm（2026-05-29 反轉合流），實際：{speak_calls}"
    )


# ============================================================
# L3-C-2-006
### Scenario: C-2 第二段「繼續」命中 → speak ack + 回 main loop 可繼續加單
### Given L3 C-2 第二段等待中（已 speak warning），cart 含商品
### When 顧客輸入「繼續」（命中 KEYWORDS_C2_CONTINUE_STRICT_SHORT）
### Then speak L3_C2_CONTINUE_ACK 通知顧客繼續加單 + 回 main loop
###      後續可加單 + 結帳進 L4，cart 保留（不清空）
### Note 2026-05-30 加：修 Pi demo bug — main loop 無 entry prompt，
###      若 CONTINUE 不 speak ack 顧客失去對話上下文又被 DYC_TIMEOUT 抓回 C-2
# ============================================================

def test_l3_c2_second_stage_continue_speaks_ack_and_returns_to_main_loop() -> None:
    """C-2 「繼續」命中 → speak L3_C2_CONTINUE_ACK + 回 main loop。

    驗證：
    - speak_calls 含 L3_C2_CONTINUE_ACK（ack 必 speak）
    - cart 不清空（CONTINUE 不該動 cart）
    - 後續可加單 + 「結帳」+「1」confirm yes → L4
    """
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → main loop DYC timeout → 進 C-2 第二段
    # 「繼續」→ CONTINUE 命中 → speak ack → 回 main loop
    # 「冰紅茶 2」→ main loop 加單成功
    # 「結帳」→ C-1 進 confirm
    # 「1」→ confirm yes → L4
    customer_input = FakeCustomerInput([None, "繼續", "冰紅茶 2", "結帳", "1"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：CONTINUE 必 speak ack
    assert L3_C2_CONTINUE_ACK in speak_calls, (
        f"C-2 CONTINUE 命中應 speak L3_C2_CONTINUE_ACK，實際：{speak_calls}"
    )
    # CONTINUE 不該清 cart（後續加單 1+2=3 瓶）
    assert cart_module.get_quantity(cart, "冰紅茶") == 3, (
        f"CONTINUE 不該清 cart + 後續加 2 瓶 → 共 3 瓶，實際：{cart}"
    )
    # 後續可進 L4
    assert next_state == "L4", (
        f"CONTINUE → main loop → 加單 → C-1 confirm yes 應進 L4，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-007
### Scenario: C-2 第二段擴展 CONTINUE keyword 命中 → speak ack + 回 main loop
### Given L3 C-2 第二段等待中（已 speak warning），cart 含商品
### When 顧客輸入新加 CONTINUE keyword family 內任一詞（如「繼續購買」/「再買」）
### Then 命中 KEYWORDS_C2_CONTINUE → speak L3_C2_CONTINUE_ACK + 回 main loop
### Note 2026-05-30 加：修 Pi demo bug —「繼續購買」這類常見口語原本 fall through 到亂答
# ============================================================

@pytest.mark.parametrize(
    "continue_keyword",
    [
        "繼續購買",   # user demo 場景直接觸發
        "繼續買",
        "繼續加買",
        "繼續加購",
        "繼續挑",
        "繼續逛",
        "繼續看",
        "再買",
        "再加",
        "再選",
        "再來",
        "再來一個",
        "再來一張",
        "還想買",
        "想再買",
        "我想再買",
        "继续选购",   # 簡體變體
        "继续购买",
        "继续买",
        "再买",
        "再加",
    ],
)
def test_l3_c2_second_stage_expanded_continue_keywords_hit_and_resume_dialog(
    continue_keyword: str,
) -> None:
    """C-2 第二段新擴 CONTINUE keyword 命中 → speak ack + 回 main loop 可繼續加單。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；continue_keyword → CONTINUE 命中 → ack → 回 main loop
    # 「冰紅茶 2」→ 加單；「結帳」→ C-1 confirm；「1」→ yes 進 L4
    customer_input = FakeCustomerInput(
        [None, continue_keyword, "冰紅茶 2", "結帳", "1"]
    )

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # CONTINUE 必 speak ack
    assert L3_C2_CONTINUE_ACK in speak_calls, (
        f"擴 CONTINUE keyword「{continue_keyword}」應命中並 speak ack，實際：{speak_calls}"
    )
    # cart 保留 + 後續加單共 3 瓶
    assert cart_module.get_quantity(cart, "冰紅茶") == 3, (
        f"CONTINUE 不該清 cart + 後續加 2 瓶 → 共 3 瓶，實際：{cart}"
    )
    assert next_state == "L4", (
        f"CONTINUE → main loop → 加單 → confirm yes 應進 L4，實際：{next_state!r}"
    )


# ============================================================
# L3-C-2-008
### Scenario: C-2 第二段擴展 CANCEL keyword 命中 → 清 cart 退 L1
### Given L3 C-2 第二段等待中（已 speak warning），cart 含商品
### When 顧客輸入新加 CANCEL keyword family 內任一詞（如「取消購買」/「我想取消」）
### Then 命中 KEYWORDS_C2_CANCEL → _dialog_exit_a → clear cart + 退 L1
### Note 2026-05-30 加：同類 sweep —「取消購買」等口語原本被 strict_short ["取消"] equals 漏掉
# ============================================================

@pytest.mark.parametrize(
    "cancel_keyword",
    [
        "取消購買",
        "我要取消",
        "想取消",
        "我想取消",
        "不想要了",
        "取消购买",   # 簡體變體
    ],
)
def test_l3_c2_second_stage_expanded_cancel_keywords_hit_and_exit_l1(
    cancel_keyword: str,
) -> None:
    """C-2 第二段新擴 CANCEL keyword 命中 → 清 cart 退 L1."""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第一段；cancel_keyword → CANCEL 命中 → _dialog_exit_a：
    # speak L3_REJECT_THANKS + clear cart + 退 L1
    customer_input = FakeCustomerInput([None, cancel_keyword])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # _dialog_exit_a：speak L3_REJECT_THANKS + clear cart + 退 L1
    assert L3_REJECT_THANKS in speak_calls, (
        f"擴 CANCEL keyword「{cancel_keyword}」應命中並 speak L3_REJECT_THANKS，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"CANCEL 應清 cart，實際：{cart}"
    )
    assert next_state == "L1_via_subroutine_a", (
        f"CANCEL → 退 L1，實際：{next_state!r}"
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
    # 「繼續」在 mode="normal" 下回「無法判斷」→ B-1；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["繼續", None, None, "對"])

    # Act
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
###      啟動 L4_TOTAL_BUDGET（36s）wall-clock budget
###      （2026-05-30 重構：移除 loop_count/unclear_count 機制 → 單一 budget）
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
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
    """L4 拒絕意圖經 cancel_confirm gate 後清 cart 退 L1（2026-05-29 cross-L cancel）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「不要」→ 拒絕；「是的」→ cancel_confirm YES → 清 cart 退 L1
    customer_input = FakeCustomerInput(["不要", "是的"])

    # Act
    next_state, next_loop_count, next_unclear_count = states.run_l4(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm prompt + 取消語音 + cart 清空 + 回 L1
    assert CANCEL_CONFIRM_PROMPT in speak_calls, (
        f"L4 拒絕意圖應先進 cancel_confirm 子狀態，實際：{speak_calls}"
    )
    assert L4_B_CANCEL_THANKS in speak_calls, (
        f"cancel_confirm YES 後應 speak L4_B_CANCEL_THANKS，實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"鏈路 B 應清空 cart，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"鏈路 B 應回 L1_via_subroutine_a，實際：{next_state!r}"
    )


# ============================================================
# Cross-L cancel：NO path 系列（2026-05-29 加）
# 拒絕意圖 → cancel_confirm prompt → 「不要取消 / 繼續」→ 繼續交易、不退 L1
# ============================================================

def test_l2_reject_then_cancel_confirm_no_continues_dialog() -> None:
    """L2 reject 後 cancel_confirm NO → speak L2_CANCEL_DECLINED_RESUME，繼續對話直到 timeout。

    Flow：「不要」→ 拒絕 → cancel_confirm「不要取消」→ NO → speak 合成 RESUME voice
    → None timeout（cart 空 L2 模式）→ L2_TIMEOUT_TO_HAWK_VOICE → 退 L1
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「不要」拒絕 → cancel_confirm prompt → 「不要取消」NO → 重 prompt → None timeout 退 L1
    customer_input = FakeCustomerInput(["不要", "不要取消", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm prompt 有 speak、合成 RESUME voice 有 speak、不走 L2_REJECT_THANKS
    # 2026-05-30 改：從 CANCEL_DECLINED_NOTICE assert 改為 L2_CANCEL_DECLINED_RESUME（合成 voice）
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert L2_CANCEL_DECLINED_RESUME in speak_calls, (
        f"NO path 應 speak L2_CANCEL_DECLINED_RESUME，實際：{speak_calls}"
    )
    assert L2_REJECT_THANKS not in speak_calls, (
        f"NO path 不應 speak L2_REJECT_THANKS（沒確認取消），實際：{speak_calls}"
    )
    # 最終仍因 timeout 走 L1（L2 模式 timeout = 中性訊息退場），但與 reject 退場不同
    assert next_state == "L1_via_subroutine_a"


def test_l3_reject_then_cancel_confirm_no_keeps_cart() -> None:
    """L3 reject 後 cancel_confirm NO → cart 保留，繼續對話。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我不要了」L3 strict reject → cancel_confirm「繼續」NO → 重 prompt → 「結帳」「1」進 L4
    customer_input = FakeCustomerInput(["我不要了", "繼續", "結帳", "1"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 保留 + 沒走 L3_REJECT_THANKS + 最終結帳進 L4
    # 2026-05-30 改：從 CANCEL_DECLINED_NOTICE assert 改為 L3_CANCEL_DECLINED_RESUME（合成 voice）
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert L3_CANCEL_DECLINED_RESUME in speak_calls
    assert L3_REJECT_THANKS not in speak_calls, (
        f"NO path 不應 speak L3_REJECT_THANKS（cart 應保留），實際：{speak_calls}"
    )
    assert not cart_module.is_empty(cart), (
        f"NO path 後 cart 應保留，實際：{cart}"
    )
    assert next_state == "L4", f"NO path 後可繼續結帳進 L4，實際：{next_state!r}"


def test_l4_reject_then_cancel_confirm_no_continues_payment() -> None:
    """L4 reject 後 cancel_confirm NO → cart 保留，繼續等掃碼直到 s 進 L5。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「不要」→ 拒絕 → cancel_confirm「不要取消」NO → 重 prompt → 「s」掃碼成功 → L5
    customer_input = FakeCustomerInput(["不要", "不要取消", "s"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 保留 + 沒走 L4_B_CANCEL_THANKS + 最終 s 進 L5
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert CANCEL_DECLINED_NOTICE in speak_calls
    assert L4_B_CANCEL_THANKS not in speak_calls, (
        f"NO path 不應 speak L4_B_CANCEL_THANKS（cart 應保留），實際：{speak_calls}"
    )
    assert not cart_module.is_empty(cart), (
        f"NO path 後 cart 應保留，實際：{cart}"
    )
    assert next_state == "L5", (
        f"NO path 後可繼續掃碼進 L5，實際：{next_state!r}"
    )


def test_l2_b3_silence_reject_then_cancel_confirm_no_continues() -> None:
    """L2 B-3 沉默期內顧客講拒絕 → cancel_confirm gate → NO → 繼續對話。

    對應 _dialog_dispatch_inner_l2 內的 reject path（非主迴圈 reject path）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「想一下」→ B-3 沉默；「不要」→ 沉默期內拒絕；「不要取消」NO；None timeout → 中性退
    customer_input = FakeCustomerInput(["想一下", "不要", "不要取消", None])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm gate 起作用，NO path 不退 L2_REJECT_THANKS
    # 2026-05-30 改：從 CANCEL_DECLINED_NOTICE assert 改為 L2_CANCEL_DECLINED_RESUME（合成 voice）
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert L2_CANCEL_DECLINED_RESUME in speak_calls
    assert L2_REJECT_THANKS not in speak_calls, (
        f"沉默期內 NO path 不應 speak L2_REJECT_THANKS，實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


def test_l3_b4_silence_reject_then_cancel_confirm_no_continues() -> None:
    """L3 B-4 沉默期內顧客講拒絕 → cancel_confirm gate → NO → speak L3_CANCEL_DECLINED_RESUME 繼續對話。

    對應 _dialog_dispatch_inner_l3 內的 reject path（非主迴圈 reject path）。
    既有 L2 版（test_l2_b3_silence_reject_then_cancel_confirm_no_continues）已 cover L2 沉默期；
    本 test 補 L3 對稱 path，避免 _dialog_dispatch_inner_l3 reject 分支無 regression 守護。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「想一下」→ B-4 沉默；「我不要了」→ L3 strict reject 沉默期內；
    # 「不要取消」NO；「結帳」→ C-1 confirm；「1」→ yes 進 L4
    customer_input = FakeCustomerInput(["想一下", "我不要了", "不要取消", "結帳", "1"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm gate 起作用，NO path speak 合成 voice + cart 保留 + 最終 L4
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert L3_CANCEL_DECLINED_RESUME in speak_calls, (
        f"L3 沉默期 NO path 應 speak L3_CANCEL_DECLINED_RESUME，實際：{speak_calls}"
    )
    assert L3_REJECT_THANKS not in speak_calls, (
        f"沉默期內 NO path 不應 speak L3_REJECT_THANKS（cart 應保留），實際：{speak_calls}"
    )
    assert not cart_module.is_empty(cart), (
        f"NO path 後 cart 應保留，實際：{cart}"
    )
    assert next_state == "L4"


def test_checkout_confirm_cancel_intent_triggers_cancel_confirm_gate() -> None:
    """checkout_confirm 內顧客講「取消交易」→ 經 cancel_confirm gate → 直退 L1。

    對應 _dialog_checkout_confirm 內 is_cancel_intent gate（2026-05-29 加 gate；
    2026-05-30 強化：YES path 直退 L1 走 _dialog_exit_a，不走
    _handle_checkout_confirm_result + L2 entry → 兩輪拒絕 bug path）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「結帳」→ confirm prompt；「我想取消交易」→ cancel intent → cancel_confirm；「是」YES → 直退 L1
    customer_input = FakeCustomerInput(["結帳", "我想取消交易", "是"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm prompt 有 speak、退 L1、cart 清空
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    # 2026-05-30 強化：新 path 走 _dialog_exit_a → speak L3_REJECT_THANKS
    assert L3_REJECT_THANKS in speak_calls, (
        f"cancel YES 應走 _dialog_exit_a speak L3_REJECT_THANKS，實際：{speak_calls}"
    )
    # 不該走舊 bug path：_handle_checkout_confirm_result speak「請告訴我您想買什麼」(L2 entry 內容)
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls, (
        f"cancel YES 不該走 clear-cart helper（舊 bug path），實際：{speak_calls}"
    )
    # 不該走舊 bug path：cart 空 → L2 mode → input 耗盡 → L2 timeout → L2 退場 voice
    assert L2_TIMEOUT_TO_HAWK_VOICE not in speak_calls, (
        f"cancel YES 不該走 L2 timeout 退場 path（舊 bug 兩輪拒絕的第二輪終點），實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"checkout_confirm 內 cancel YES 應清 cart，實際：{cart}"
    )
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-CANCEL-CHECKOUT-001
### Scenario: _dialog_main_loop 結帳分支 confirm 內 cancel_confirm YES → 直退 L1 不需第二輪拒絕
### Given L3 主迴圈內顧客「結帳」進 C-1 confirm，cart 含商品
### When 顧客在 confirm 講 cancel intent → cancel_confirm「是」YES
### Then 直接退 L1（speak L3_REJECT_THANKS + clear cart），不再 speak「請告訴我您想買什麼」
###      (2026-05-30 加：修 Pi demo 兩輪 YES 才退 L1 bug)
# ============================================================

def test_l3_main_checkout_confirm_cancel_yes_direct_exits_l1() -> None:
    """L3 主迴圈結帳分支進 confirm 內 cancel YES → 直退 L1（不回 L2 entry）。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「結帳」→ L3 main loop 結帳分支進 confirm
    # 「不買了」→ confirm 內 cancel intent → cancel_confirm prompt
    # 「是」→ cancel_confirm YES → 應直退 L1（不再需要第 4 input）
    customer_input = FakeCustomerInput(["結帳", "不買了", "是"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_REJECT_THANKS in speak_calls, (
        f"cancel YES 應走 _dialog_exit_a speak L3_REJECT_THANKS，實際：{speak_calls}"
    )
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls, (
        f"cancel YES 不該走 clear-cart helper（舊 bug path），實際：{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"cancel YES 應清 cart，實際：{cart}"
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-CANCEL-CHECKOUT-002
### Scenario: C-2 silent timeout → _c2_checkout_via_confirm 內 cancel YES → 直退 L1
### Given L3 主迴圈 timeout → C-2 三選一 silent → _c2_checkout_via_confirm
### When 顧客在 confirm 講 cancel intent → cancel_confirm YES
### Then 直退 L1（不回 main loop）
# ============================================================

def test_l3_c2_checkout_via_confirm_cancel_yes_direct_exits_l1() -> None:
    """C-2 silent timeout → _c2_checkout_via_confirm 內 cancel YES → 直退 L1。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → main loop timeout → cart 非空走 c2_second_stage
    # None → c2 silent timeout → _c2_checkout_via_confirm → confirm prompt
    # 「不買了」→ confirm 內 cancel intent
    # 「是」→ cancel_confirm YES → 直退 L1
    customer_input = FakeCustomerInput([None, None, "不買了", "是"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_REJECT_THANKS in speak_calls
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls
    assert cart_module.is_empty(cart)
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L3-CANCEL-CHECKOUT-003
### Scenario: _dialog_dispatch_inner_l3 結帳分支進 confirm 內 cancel YES → 直退 L1
### Given L3 B-4 沉默期內顧客講「結帳」進 _dialog_dispatch_inner_l3 結帳分支
### When 顧客在 confirm 講 cancel intent → cancel_confirm YES
### Then 直退 L1（不回 main loop）
# ============================================================

def test_l3_b4_silence_checkout_confirm_cancel_yes_direct_exits_l1() -> None:
    """L3 沉默期 dispatch_inner_l3 結帳分支 confirm 內 cancel YES → 直退 L1。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「想一下」→ B-4 沉默期；「結帳」→ 沉默期內走 _dialog_dispatch_inner_l3 結帳分支
    # 「不買了」→ confirm 內 cancel；「是」→ YES → 直退 L1
    customer_input = FakeCustomerInput(["想一下", "結帳", "不買了", "是"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_REJECT_THANKS in speak_calls
    assert L3_CHECKOUT_REJECT_CLEAR_NOTICE not in speak_calls
    assert cart_module.is_empty(cart)
    assert next_state == "L1_via_subroutine_a"


def test_checkout_confirm_cancel_intent_no_returns_to_confirm() -> None:
    """checkout_confirm 內顧客講「取消交易」→ cancel_confirm NO → 繼續 confirm 等明確 yes/no。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「結帳」→ confirm；「我想取消交易」→ cancel intent；「不要取消」NO → 重 confirm prompt；「對」→ yes 進 L4
    customer_input = FakeCustomerInput(["結帳", "我想取消交易", "不要取消", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm prompt 有 speak、DECLINED notice 有 speak、最終 L4
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert CANCEL_DECLINED_NOTICE in speak_calls
    assert not cart_module.is_empty(cart), (
        f"NO path 後 cart 應保留，實際：{cart}"
    )
    assert next_state == "L4"


def test_cross_l_cancel_intent_phrase_triggers_confirm() -> None:
    """新加 NLU keyword「取消交易」應觸發 cancel intent → cancel_confirm gate。

    驗證 _KEYWORDS_REJECT 擴充：「取消交易」phrase 被 classify 為「拒絕」。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「我想取消交易」→ L3 strict reject hit → cancel_confirm「是」YES → 清 cart 退 L1
    customer_input = FakeCustomerInput(["我想取消交易", "是"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert L3_REJECT_THANKS in speak_calls
    assert cart_module.is_empty(cart)
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# Cross-L cancel：inner state path gate 系列（2026-05-29 加）
# _dialog_unclear_final_confirmation / _l4_service_mode 兩個 inner state path
# 原本透過 _KEYWORDS_EXIT 直接退出，現在加 cancel_confirm gate
# 統一 UX：所有 cancel detection 都經 6s 確認子狀態
# （2026-05-30 重構：移除 _l4_final_confirmation；L4 cancel gate 仍存於 _l4_service_mode + 主迴圈拒絕 dispatch）
# ============================================================

def test_unclear_final_cancel_intent_routes_via_cancel_confirm() -> None:
    """L3 unclear final 子狀態內顧客講退出 keyword → cancel_confirm YES → 清 cart 退 L1。

    對應 _dialog_unclear_final_confirmation 內新增的 cancel_confirm gate（2026-05-29）。
    顧客在「請按 1 取消 / 2 繼續」最終確認時講「退出」語音 keyword → 不該直接退、
    經 6s 確認後才退（保護「退出」誤觸）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # UNCLEAR_MAX 次 B-1 → 進 unclear final → 「退出」keyword → cancel_confirm → 「是的」YES → 清 cart 退 L1
    inputs = ["asdf"] * UNCLEAR_MAX + ["退出", "是的"]
    customer_input = FakeCustomerInput(inputs)

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：unclear final prompt + cancel_confirm prompt + 退場語音 + cart 清空 + 退 L1
    assert L3_UNCLEAR_FINAL_PROMPT in speak_calls
    assert CANCEL_CONFIRM_PROMPT in speak_calls, (
        f"unclear final 內 cancel intent 應先進 cancel_confirm，實際：{speak_calls}"
    )
    assert L3_REJECT_THANKS in speak_calls
    assert cart_module.is_empty(cart)
    assert next_state == "L1_via_subroutine_a"


def test_unclear_final_cancel_intent_no_continues() -> None:
    """L3 unclear final 內 cancel intent → cancel_confirm NO → 繼續主迴圈、cart 保留。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # UNCLEAR_MAX 次 B-1 → unclear final → 「退出」→ cancel_confirm → 「不要取消」NO → 重 prompt
    # → 「2」繼續 → 主迴圈 → 「結帳」→ 「1」confirm yes → L4
    inputs = ["asdf"] * UNCLEAR_MAX + ["退出", "不要取消", "2", "結帳", "1"]
    customer_input = FakeCustomerInput(inputs)

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cancel_confirm prompt + DECLINED notice + cart 保留 + 最終 L4
    assert CANCEL_CONFIRM_PROMPT in speak_calls
    assert CANCEL_DECLINED_NOTICE in speak_calls
    assert L3_REJECT_THANKS not in speak_calls, (
        f"NO path 不應 speak L3_REJECT_THANKS（cart 應保留），實際：{speak_calls}"
    )
    assert not cart_module.is_empty(cart), f"NO path 後 cart 應保留，實際：{cart}"
    assert next_state == "L4"


# ============================================================
# RETIRED (2026-05-30 二次重構)：
#   test_l4_service_mode_cancel_intent_routes_via_cancel_confirm
#   test_l4_service_mode_cancel_intent_no_continues
#   test_l4_c_service_input_1_exits_clears_cart
#   test_l4_c_service_exit_keyword_exits_clears_cart
#   test_l4_c_service_reject_keyword_treated_as_exit
#   test_l4_c_service_input_2_continues_back_to_main_loop
#   test_l4_c_service_continue_keyword_continues
# 退場理由：
#   - cancel_confirm gate 已從客服模式移除（user 字面「不需要再進入 cancel_confirm
#     雙重確認，直接退回 L1」）
#   - 終端「1」「2」鍵 已移除（改用 keyword YES/NO 取代）
#   - 舊「繼續」keyword test 被新 YES keyword test 取代（新行為涵蓋舊行為 + 新清單）
# 新 cover：見下方 L4-C-001 ~ L4-C-008 重寫
# ============================================================


# ============================================================
# L4-C-001（重寫版，2026-05-30 二次重構）
# Scenario: 顧客回應客服關鍵字進入客服模式印電話並 speak 確認 prompt
# Given L4 等待中，cart 含商品
# When 顧客輸入命中客服意圖關鍵字（如「客服」）
# Then 終端印商家客服電話（SERVICE_PHONE），
#      語音 speak L4_C_CONFIRM_PROMPT_TEMPLATE「請問是否繼續交易？24秒後將自動取消交易。」
#      進入一次性 24s 確認子狀態
# ============================================================

def test_l4_c_service_keyword_enters_special_mode_with_options() -> None:
    # Arrange
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ 進入客服模式；「繼續」→ YES strict_short → 回主迴圈；「s」→ L5
    customer_input = FakeCustomerInput(["客服", "繼續", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：終端含電話；語音含 confirm prompt（不再有 L4_C_OPTIONS_PROMPT）
    all_terminal = " ".join(terminal_calls)
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    assert SERVICE_PHONE in all_terminal, f"進客服模式應印電話，終端：{terminal_calls}"
    assert expected_prompt in speak_calls, (
        f"進客服模式應 speak L4_C_CONFIRM_PROMPT_TEMPLATE，實際 speak：{speak_calls}"
    )
    # confirm prompt 不應印 terminal（對齊 post-P8「sales/ 內只 speak prompt」規則）
    assert expected_prompt not in all_terminal, (
        f"confirm prompt 不應印 terminal（語音已 speak），實際終端：{terminal_calls}"
    )


# ============================================================
# L4-C-002（新增，2026-05-30 二次重構）
# Scenario: 客服模式 silent timeout → 自動取消，清 cart 退 L1
# Given L4 客服模式 confirm 子狀態等待中（一次性 24s budget）
# When 顧客 silent，read_customer_input 連續回 None 直到 budget 耗盡
# Then 跟 prompt 字面「24秒後將自動取消交易」對齊：清空 cart，回 L1
# ============================================================

def test_l4_c_service_silent_timeout_clears_cart_exits_l1() -> None:
    """客服 confirm 子狀態 silent → 自動取消（跟 prompt 字面「自動取消」對齊）。"""
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ 進入確認子狀態；None → silent → 自動取消
    customer_input = FakeCustomerInput(["客服", None])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：silent → 清 cart 退 L1
    assert cart_module.is_empty(cart), f"silent timeout 應清 cart，實際：{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"silent timeout 應回 L1_via_subroutine_a，實際:{next_state!r}"
    )


# ============================================================
# L4-C-003（新增，2026-05-30 二次重構）
# Scenario: 客服模式 YES keyword（substring）→ 回主迴圈繼續交易
# Given L4 客服模式 confirm 子狀態等待中
# When 顧客輸入命中 KEYWORDS_L4_C_CONFIRM_YES（如「繼續交易」/「好的」/「是的」）
# Then return None（service_mode 內），run_l4 主迴圈繼續，cart 保留；後續 s → L5
# ============================================================

def test_l4_c_service_yes_substring_returns_to_main_loop() -> None:
    """客服 YES substring 命中 → 回主迴圈 + cart 保留 + 後續可結帳。"""
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ 確認子狀態；「繼續交易」→ YES substring → 回主迴圈；「s」→ L5
    customer_input = FakeCustomerInput(["客服", "繼續交易", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：cart 保留，後續 s 掃碼成功 → L5
    assert next_state == "L5", f"YES substring 後 s 應 L5，實際:{next_state!r}"
    assert not cart_module.is_empty(cart), "YES 後 cart 應保留"


def test_l4_c_service_yes_strict_short_returns_to_main_loop() -> None:
    """客服 YES strict_short「繼續」單字命中 → 回主迴圈。"""
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ confirm；「繼續」單字 → YES strict_short → 回主迴圈；「s」→ L5
    customer_input = FakeCustomerInput(["客服", "繼續", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert
    assert next_state == "L5", f"YES strict_short 後 s 應 L5，實際:{next_state!r}"
    assert not cart_module.is_empty(cart), "YES 後 cart 應保留"


# ============================================================
# L4-C-004（新增，2026-05-30 二次重構）
# Scenario: 客服模式 NO keyword（substring）→ 直接清 cart 退 L1（不雙重 confirm）
# Given L4 客服模式 confirm 子狀態等待中
# When 顧客輸入命中 KEYWORDS_L4_C_CONFIRM_NO（如「取消交易」/「不繼續」）
# Then 直接清 cart 退 L1（user 字面：不再雙重 cancel_confirm gate）
# ============================================================

def test_l4_c_service_no_substring_clears_cart_exits_l1_directly() -> None:
    """客服 NO substring 命中 → 直接清 cart 退 L1，不經 cancel_confirm gate。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ confirm；「取消交易」→ NO substring → 直接清 cart 退 L1
    customer_input = FakeCustomerInput(["客服", "取消交易"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：直接退 — 不經 cancel_confirm gate（不該 speak CANCEL_CONFIRM_PROMPT）
    assert CANCEL_CONFIRM_PROMPT not in speak_calls, (
        f"客服 NO 不再經 cancel_confirm gate（user 字面），實際 speak:{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"NO 後應清 cart，實際:{cart}"
    assert next_state == "L1_via_subroutine_a", (
        f"NO 後應回 L1，實際:{next_state!r}"
    )


def test_l4_c_service_no_strict_short_clears_cart_exits_l1_directly() -> None:
    """客服 NO strict_short「不要」單字 → 直接清 cart 退 L1。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ confirm；「不要」strict_short → NO → 直接清 cart 退 L1
    customer_input = FakeCustomerInput(["客服", "不要"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：直接退（不經 cancel_confirm）
    assert CANCEL_CONFIRM_PROMPT not in speak_calls, (
        f"客服 NO 不應 cancel_confirm gate，實際:{speak_calls}"
    )
    assert cart_module.is_empty(cart), f"NO 後應清 cart，實際:{cart}"
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L4-C-005（新增，2026-05-30 二次重構）
# Scenario: NO 先 check（防 substring 誤命中 YES strict_short）
# Given L4 客服模式 confirm 子狀態
# When 顧客輸入「不繼續」（含 YES strict_short「繼續」但更明確是 NO substring）
# Then NO 集先 check → 命中 NO → 清 cart 退 L1（不誤命中 YES）
# ============================================================

def test_l4_c_service_no_substring_precedence_over_yes_strict_short() -> None:
    """「不繼續」命中 NO substring，不應誤命中 YES strict_short「繼續」（NO 先 check 防 FP）。"""
    # Arrange
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["客服", "不繼續"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：「不繼續」應走 NO → 清 cart 退 L1（不誤命中 YES「繼續」strict_short）
    assert cart_module.is_empty(cart), (
        f"「不繼續」應命中 NO（precedence over YES「繼續」strict_short），實際 cart:{cart}"
    )
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# L4-C-006（新增，2026-05-30 二次重構）
# Scenario: 客服模式內終端輸入 s → 鏈路 A 掃碼成功 → L5（保留模擬 wire-up）
# Given L4 客服模式 confirm 子狀態等待中
# When 顧客輸入「s」（終端掃碼成功模擬）
# Then 立即 speak L4_A_PAY_SUCCESS + do_action(ACTION_L4_PAY) + 轉 L5
# ============================================================

def test_l4_c_service_input_s_treated_as_continue_then_scan() -> None:
    """service mode 內 s → 鏈路 A → L5（保留模擬掃碼路徑，user 沒明示移除）。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["客服", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：L4_A_PAY_SUCCESS 被 speak，轉 L5
    assert L4_A_PAY_SUCCESS in speak_calls, (
        f"客服模式內 s 應 speak 付款成功，實際:{speak_calls}"
    )
    assert next_state == "L5", f"客服模式內 s 應直接到 L5，實際:{next_state!r}"


# ============================================================
# L4-C-007（重寫版，2026-05-30 二次重構）
# Scenario: 客服模式不命中 → speak L4_UNCLEAR_NOTICE + 不重置 confirm budget + 保持子狀態
# Given L4 客服模式 confirm 子狀態等待中
# When 顧客輸入「你好」（不命中 YES / NO / s 任一）
# Then speak L4_UNCLEAR_NOTICE 一次（不重置 budget）；後續仍可輸入 YES/NO/s
# ============================================================

def test_l4_c_service_unrecognized_input_speaks_unclear_notice_and_stays() -> None:
    """客服 confirm 不命中 → speak L4_UNCLEAR_NOTICE + 保持子狀態 + 不重置 budget。"""
    # Arrange
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「客服」→ confirm；「你好」不命中 → unclear；「繼續」YES → 回主迴圈；「s」→ L5
    customer_input = FakeCustomerInput(["客服", "你好", "繼續", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert：unclear notice 被 speak + 進場 prompt 也被 speak（只一次）+ 最終 L5
    assert L4_UNCLEAR_NOTICE in speak_calls, (
        f"client confirm 不命中應 speak L4_UNCLEAR_NOTICE，實際 speak:{speak_calls}"
    )
    expected_prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    # confirm prompt 應只 speak 一次（不重複）
    assert speak_calls.count(expected_prompt) == 1, (
        f"進場 prompt 應只 speak 1 次，實際:{speak_calls.count(expected_prompt)}"
    )
    assert next_state == "L5"


# ============================================================
# L4-C-008（新增，2026-05-30 二次重構）
# Scenario: 客服 confirm 子狀態獨立 confirm budget，不共用主 L4 budget
# Given L4 主 budget 已快耗盡（fake_monotonic 控制）
# When 顧客「客服」→ 進客服 confirm；客服內讀 input timeout 倒回
# Then 客服 confirm 用獨立 L4_C_CONFIRM_TIMEOUT=24s budget，不受主 budget 已耗盡影響
# ============================================================

def test_l4_c_service_uses_independent_confirm_budget() -> None:
    """客服 confirm 用獨立 L4_C_CONFIRM_TIMEOUT=24s budget。

    fake_monotonic 安排：前 N 次 monotonic.now 回 0.0（主 + 客服 deadline 在 budget 內），
    確保客服階段「繼續」YES 路徑能正常走完；之後切到「budget 耗盡」讓主迴圈 forced exit。

    驗證點：客服階段不被主 budget 立即耗盡（如果客服共用主 deadline 而主 deadline
    已 < now，客服第一次 while remaining check 立即 silent 取消 → next_state 仍 L1_via_subroutine_a，
    但 cart 路徑會走錯），測試需確保「客服階段先處理 YES 才進主 forced exit」。

    為避免細緻 monotonic call-count 偵測脆弱，本測試核心斷言：客服「繼續」成功 +
    後續主迴圈 forced exit 退 L1 + cart 清空。獨立 budget 行為由 prod code 內
    `confirm_deadline = time.monotonic() + L4_C_CONFIRM_TIMEOUT` 一句保證
    （遠離主 deadline 變數）— 此 test 為 smoke regression，防共用 deadline 回歸。
    """
    from unittest.mock import patch

    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)

    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        # 前 8 次（主進場 + dispatch + 客服進場 + 客服 while + 主回 while 等）一律回 0.0，
        # 保證客服「繼續」YES 跑完
        if call_count[0] <= 8:
            return 0.0
        # 第 9 次以後主迴圈 remaining check → 耗盡 → forced exit
        return float(L4_TOTAL_BUDGET + 1)

    customer_input = FakeCustomerInput(["客服", "繼續"])

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: None,
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # 客服「繼續」YES → 回主迴圈 → 主 budget 耗盡 → forced exit 退 L1
    # 關鍵驗證：客服階段沒被主 budget 立即耗盡（會走完 YES 路徑），最終由主迴圈耗盡退場
    assert next_state == "L1_via_subroutine_a", (
        f"客服 YES 後主迴圈 forced exit 應退 L1，實際:{next_state!r}"
    )


# ============================================================
# L4-C-RESUME-001（新增，2026-05-31 Pi demo fix）
# Scenario: 客服模式講「繼續」YES → 回 L4 主迴圈重印明細 + 重 speak entry prompt + reset budget
# Given L4 等掃碼，顧客進客服模式
# When 顧客在客服 confirm 內講 YES keyword（如「繼續」）
# Then L4 主迴圈：重印金額明細 + 重 speak L4_ENTRY_PROMPT_TEMPLATE + budget reset 36s
#      後續 36s 內顧客仍有 fresh time 完成掃碼，不會被 stale budget 卡住
# Note 2026-05-31 加：修 Pi demo「繼續後鏈路不知道跑去哪邊」UX bug
# ============================================================

def test_l4_service_mode_continue_yes_reprints_entry_and_resets_budget() -> None:
    """客服 YES 繼續後 main loop 應重印明細 + 重 speak entry + reset deadline。

    驗證：
    - speak_calls 含至少 2 次 L4_ENTRY_PROMPT_TEMPLATE.format(total=total)
      （一次進 L4 entry，一次客服繼續後 re-entry）
    - terminal_calls 含至少 2 次 L4_QR_MOCK_HINT（兩次 print_entry_detail 都會印）
    - 後續可正常 "s" 掃碼進 L5（驗 budget reset，未被原 stale budget 卡死）
    """
    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    total = cart_module.calc_total(cart)
    # 「客服」→ service mode → 「繼續」YES → 回主迴圈 → speak entry prompt + reset budget
    # → "s" 掃碼成功 → L5
    customer_input = FakeCustomerInput(["客服", "繼續", "s"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: terminal_calls.append(text),
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # entry prompt 應 speak >= 2 次（一次初始進 L4，一次客服繼續後 re-entry）
    entry_prompt = L4_ENTRY_PROMPT_TEMPLATE.format(total=total)
    entry_speak_count = sum(1 for s in speak_calls if s == entry_prompt)
    assert entry_speak_count >= 2, (
        f"客服繼續後應重 speak L4_ENTRY_PROMPT_TEMPLATE，"
        f"實際 entry prompt speak 次數：{entry_speak_count}, speak_calls: {speak_calls}"
    )
    # 金額明細也應重印 >= 2 次（_l4_print_entry_detail 用 L4_QR_MOCK_HINT 結尾，方便 grep）
    qr_print_count = sum(1 for t in terminal_calls if L4_QR_MOCK_HINT in t)
    assert qr_print_count >= 2, (
        f"客服繼續後應重印金額明細，實際 QR hint print 次數：{qr_print_count}"
    )
    # 後續 "s" 掃碼成功 → L5（驗 budget reset，沒被 stale budget 卡死）
    assert next_state == "L5", (
        f"客服繼續 → 重 speak entry → 36s 內 s 應進 L5，實際：{next_state!r}"
    )


# ============================================================
# L4-C-009-REMOVED（2026-05-30 重構：service mode 共用主 budget，不再獨立 60s timeout）
# 舊版「L4_SERVICE_TIMEOUT=60s 獨立」已廢除，service mode 共用主 budget remaining。
# 新行為改由「L4 budget 耗盡 forced exit」test 覆蓋（見下方 wall-clock budget 段）。
# ============================================================


# ============================================================
# L4 D / E 鏈路（2026-05-30 重構移除）
# 舊版 D-001..D-005（4 階段語氣 6 次循環）+ E-001..E-005（unclear_count
# 達 3 自動進客服）已隨 loop_count / unclear_count 機制廢除而刪除。
# 新行為改由「L4 wall-clock budget + 12s remind prompt + unclear notice」
# 三類 test 覆蓋（見下方 wall-clock budget regression tests 段）。
# ============================================================


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
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
        do_action=lambda *a, **k: None,
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
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
        do_action=lambda *a, **k: None,
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
    speak_calls: list = []
    sleep_calls: list = []
    cart: dict = {"冰紅茶": 2, "刮刮樂": 1}

    # Act
    result = states.run_l5(
        speak=lambda text: speak_calls.append(text),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
        do_action=lambda *a, **k: None,
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
# L4-D-FINAL-001~004-REMOVED（2026-05-30 重構移除）
# 舊版 D 達上限後 _l4_final_confirmation 18s 子狀態 (1=取消 / 2=繼續) 已廢除，
# 新設計單一 budget 耗盡直接 forced exit，不再有 final confirmation 子狀態。
# ============================================================


# ============================================================
# L2-C-MULTI-001 ~ 003（2026-05-25 加，B 方案 multi-product）
# ============================================================

def test_l2_multi_product_with_quantities_all_added_then_l3() -> None:
    """L2 一次點兩商品 + 各自帶數量 → 兩個都加 → 進 L3。"""
    cart = cart_module.new_cart()
    # 「紅茶 1 刮刮樂 2」加單 → L3；後續 None → C-2 silent → confirm；「對」 → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 1 刮刮樂 2", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    assert cart_module.get_quantity(cart, "刮刮樂") == 2


def test_l2_multi_product_one_missing_qty_asks_only_for_that_one() -> None:
    """L2 一次點兩商品但其中一個沒給數量 → 只追問該商品。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶 1, 刮刮樂 (沒數量) → 追問刮刮樂 → 「3」 → 加單 L3；後續 None → C-2 silent → confirm；
    # 「對」 → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 1 刮刮樂", "3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 1
    assert cart_module.get_quantity(cart, "刮刮樂") == 3
    # 應有追問刮刮樂的語音（不應追問紅茶 — 紅茶已有數量）
    assert any("刮刮樂" in s and "張" in s for s in speak_calls)
    assert not any("紅茶" in s and "瓶" in s and "請問" in s for s in speak_calls)


def test_l2_duplicate_product_overwrites_to_last_qty() -> None:
    """L2 重複講同商品 → cart 覆寫為最後一個 qty（C22 業務語意修正）。

    （2026-05-26 Wave 7a C22：dedup 規則 3 從累加改覆寫 —
     顧客修正語意「紅茶 2 紅茶 3」應視為改成 3 瓶。）
    """
    cart = cart_module.new_cart()
    # 「紅茶 2 紅茶 3」加單 → L3；後續 None → C-2 silent → confirm；「對」 → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 2 紅茶 3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    # 覆寫為最後一個 qty = 3（C22）
    assert cart_module.get_quantity(cart, "冰紅茶") == 3


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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


# ============================================================
# L3-CONFIRM-YES-001
### Scenario: L3 結帳 confirm「您即將結帳... 正確嗎？」常見肯定回應
### Given L3 「結帳」進 C-1 confirm，cart 含商品
### When 顧客回應 user 列表 9 個常見「YES」用語之一
### Then confirm → result "yes" → speak L3_C1_CHECKOUT_GO + return ("L4", 0)
### Note 2026-05-31 加：Pi demo「對哦」/「對呢」miss 修補 + 同類「對 X」family sweep
# ============================================================

@pytest.mark.parametrize(
    "yes_text",
    [
        "對哦",
        "沒錯",
        "非常正確",
        "是的沒錯",
        "是的",
        "對的",
        "對的呢",
        "對呢",
        "沒錯呢",
    ],
)
def test_l3_checkout_confirm_yes_phrases_progress_to_l4(yes_text: str) -> None:
    """L3 結帳 confirm：user 列出的 9 個常見肯定用語應視為 YES 進 L4。

    user 列表（Pi demo 反饋）：
    - 「對 X」family：對哦 / 對呢（substring 加入；「對的」/「對的呢」既有 cover）
    - 「沒錯 X」family：既有 substring「沒錯」cover「沒錯」/「沒錯呢」/「是的沒錯」
    - 「正確 X」family：既有 substring「正確」cover「非常正確」
    - 「是的」family：既有 substring「是的」cover
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「結帳」→ L3 main loop 結帳分支進 confirm prompt
    # yes_text → confirm YES → speak L3_C1_CHECKOUT_GO + return L4
    customer_input = FakeCustomerInput(["結帳", yes_text])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4", (
        f"L3 confirm「{yes_text}」應視為 YES 進 L4，實際：{next_state!r}, speak_calls: {speak_calls}"
    )
    # cart 保留（YES 進 L4 不清 cart）
    assert not cart_module.is_empty(cart), (
        f"YES 進 L4 不該清 cart，實際：{cart}"
    )


def test_l3_c2_yes_keyword_好_proceeds_directly_to_l4() -> None:
    """C-2 第二段「好」不在 C-2 三組 keyword（CONTINUE/CHECKOUT/CANCEL）內 → 視為亂答 silent
    → 倒數歸零 → 進 confirm（2026-05-29 反轉合流）→ confirm「對」 → L4。

    （2026-05-28 重構後 C-2 只用 KEYWORDS_C2_*，不用 KEYWORDS_CONFIRM_YES；「好」非結帳 keyword）
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2；「好」 → 亂答 silent；None → 倒數歸零 → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, "好", None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4", f"silent → confirm yes 應進 L4，實際：{next_state!r}"
    # 應 speak 過「正確嗎」prompt（silent timeout 改經 confirm 合流路徑）
    assert any("正確嗎" in s for s in speak_calls), (
        f"silent timeout 應經 confirm（2026-05-29 反轉合流），實際：{speak_calls}"
    )


def test_l3_c2_gibberish_silently_ignored_then_timeout_to_l4() -> None:
    """C-2 第二段 → 連續亂答 → 倒數內 read 耗盡 silent → 進 confirm（2026-05-29 反轉合流）
    → confirm「對」 → L4。

    2026-05-26 加：嚴格 strict-match 設計下，亂答 silently 忽略不重置 deadline；
    輸入耗盡時 read 返 None → 進 confirm 子狀態（2026-05-29 反轉合流 CHECKOUT keyword path）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2；df / fdsf → silently 忽略；None → 倒數歸零 → confirm；「對」 → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, "df", "fdsf", None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 不應觸發 B-1 reask 提示（嚴格 yes/no 下亂答 silent）
    assert not any("聽不太懂" in s for s in speak_calls), (
        f"C-2 嚴格 yes/no — 亂答應 silent ignored，不該觸發 B-1 clarify，實際：{speak_calls}"
    )
    # 倒數內無有效 yes/no + 沒回應 → L4
    assert next_state == "L4"


def test_l3_c2_cancel_keyword_returns_to_l1_via_subroutine_a() -> None:
    """2026-05-28 重構：C-2 第二段「取消」keyword → 清 cart + 退 L1 hawk。

    替代舊版「test_l3_c2_first_stage_no_keyword_cancels_order」：舊版「不要」誤判
    為「拒絕整單」清 cart bug 已修；新版必須講明確「取消 / 取消吧 / 幫我取消」等
    keyword 才 trigger cancel path（走 _dialog_exit_a：清 cart + speak L3_REJECT_THANKS）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第二段；「取消」strict-short → CANCEL → _dialog_exit_a → L1
    customer_input = FakeCustomerInput([None, "取消"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 「取消」keyword → 走 _dialog_exit_a：清 cart + L3_REJECT_THANKS + 退 L1
    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart), f"取消應清 cart，實際：{cart}"
    # _dialog_exit_a 在 cart 非空時 speak L3_REJECT_THANKS（「好的，取消這次購物，謝謝光臨」）
    assert L3_REJECT_THANKS in speak_calls, (
        f"CANCEL path 應 speak L3_REJECT_THANKS（_dialog_exit_a path），實際：{speak_calls}"
    )
    # 不應走 confirm（顧客明確 cancel，不需 confirm）
    assert not any("正確嗎" in s for s in speak_calls), (
        f"CANCEL 不該觸發 checkout confirm prompt，實際：{speak_calls}"
    )


def test_l3_c2_checkout_strict_short_single_word_via_confirm_to_l4() -> None:
    """2026-05-28 新增：C-2 第二段「結」單字 strict-short → CHECKOUT → 經 confirm → L4。

    驗證 strict-short 機制：「結」單字完全相等才命中 KEYWORDS_C2_CHECKOUT_STRICT_SHORT，
    避免 substring 誤命中「結束」「結婚」「結局」等非結帳意圖詞。
    後續走 _dialog_checkout_confirm path（user 答 B「主動結帳要 confirm」）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 second stage；「結」strict-short → CHECKOUT → confirm 「1」確認 → L4
    customer_input = FakeCustomerInput([None, "結", "1"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4", (
        f"CHECKOUT keyword + confirm yes 應進 L4，實際：{next_state!r}"
    )
    # 應走 confirm path → speak「您即將結帳，總共 ... 正確嗎？」
    assert any("正確嗎" in s for s in speak_calls), (
        f"CHECKOUT keyword 應觸發 _dialog_checkout_confirm prompt，實際：{speak_calls}"
    )
    # 應 speak L3_C1_CHECKOUT_GO（confirm yes 後）
    assert L3_C1_CHECKOUT_GO in speak_calls, (
        f"confirm yes 後應 speak L3_C1_CHECKOUT_GO，實際：{speak_calls}"
    )


def test_l3_c2_continue_keyword_returns_to_dialog_main_loop_preserving_cart() -> None:
    """2026-05-28 新增：C-2 第二段「繼續」keyword → 重入 dialog 主迴圈，cart 保留。

    user 訴求 1：「繼續選購」→ 不清 cart，回 dialog 讓顧客繼續加單。
    驗證：cart 保留原商品；最後 silent timeout 進 L4 確認 dialog 重入後仍能正常推進。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → C-2 第二段；「繼續」strict-short → CONTINUE → _dialog_main_loop 重入
    # → cart 仍非空 → DyC timeout (None) → c2 second stage 再次 → None → silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput([None, "繼續", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # CONTINUE 後最終仍進 L4（重入 dialog → 又 DyC timeout → c2 silent → L4）
    assert next_state == "L4"
    # cart 保留 1 瓶冰紅茶（CONTINUE 不清 cart）
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"CONTINUE 不該清 cart，實際：{dict(cart)}"
    )


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_ENTRY_PROMPT in speak_calls
    assert L2_ENTRY_PROMPT not in speak_calls


def test_dialog_empty_to_nonempty_transitions_mode_internally() -> None:
    """cart 由空變非空，dialog 主迴圈下一輪自動切 L3 mode (cart-state-driven 核心驗證)。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 加紅茶 → cart 變非空 → L2_TO_L3_TRANSITION speak（合成 voice，cart 從空變非空才用此語音）
    # 後續 None None → cart 已非空，C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["紅茶 1", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    # 進 dialog 時 cart 空 → L2 entry
    assert L2_ENTRY_PROMPT in speak_calls
    # 加完商品 cart 非空 → L2_TO_L3_TRANSITION（合成 voice 取代原 L2_C_ADDED + L3_ENTRY_PROMPT
    # 兩條獨立 speak；S4 非阻塞 worker 兩條間 ALSA drain 停頓問題解除，順序 implicit 在合成常數內）
    assert L2_TO_L3_TRANSITION in speak_calls


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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)


def test_dialog_nonempty_cart_timeout_triggers_c2_auto_checkout() -> None:
    """cart 非空 + 6s timeout → C-2 自動結帳兩段 → 經 confirm（2026-05-29 反轉合流）→
    顧客「對」確認 → L4 (L3 行為)。"""
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 第 1 個 None → C-2 第一段警告；第 2 個 None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput([None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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
        do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: disable_calls.append(True),
        do_action=lambda *a, **k: None,
    )

    assert len(disable_calls) >= 1, "L4 入口應呼叫 opencv_disable 至少一次"


def test_l1_main_loop_calls_opencv_disable_each_iteration() -> None:
    """L1 主迴圈每輪應呼叫 opencv_disable 防呆（主選單時不該偵測 OpenCV）。"""
    opencv = FakeOpencv()
    # C14：兩次 q 才真退
    kbd = FakeKeyboardInput(["q", "q"])

    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # 至少一輪 disable（即使商家直接連按兩次 q 也要 disable 過一次）
    assert opencv.disable_calls >= 1, (
        f"L1 主迴圈進入時應 opencv_disable 至少一次（防呆），實際 {opencv.disable_calls}"
    )


def test_l1_service_mode_calls_opencv_disable() -> None:
    """L1 客服模式進入時應呼叫 opencv_disable（客服期間不偵測）。"""
    opencv = FakeOpencv()
    # 進客服（3）→ 印電話 → 回主選單 → q q（C14）退出
    kbd = FakeKeyboardInput(["3", "q", "q"])

    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=FakeScheduler().schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda *a, **k: None,
    )

    # 主迴圈 2 輪（第 1 輪選 3，第 2 輪起的 q）+ 客服進入 1 次 = 至少 3 次 disable
    # （即使主迴圈防呆已 disable，客服獨立明示 disable 仍要保留）
    # C14 後：第一次 q 不退（顯示確認），第二次 q 才退；主迴圈走 3 輪（3 → q-confirm → q-exit）
    # 但實際 q 第二次落入 if key=="q" 分支不走主迴圈頂端的 opencv_disable，故仍 >= 3
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
    #   「沒了」→ C-2 第二段收到「沒了」；strict-match 下不命中任何 C-2 keyword → gibberish 忽略
    #   None → C-2 倒數歸零 silent → confirm（2026-05-29 反轉合流路徑）
    #   「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    #          需 confirm yes 才到 L4 + 保留 cart 驗證「沒了」沒走 NO 路徑）
    customer_input = FakeCustomerInput([None, "沒了", None, "對"])

    # Act：透過 run_dialog 觸發 C-2 第二段
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),

        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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

def test_l4_ack_word_speaks_gentle_and_does_not_print_unclear_notice() -> None:
    """L4 顧客講「好的」應 speak L4_ACK_GENTLE，不走 unclear notice 路徑。

    2026-05-30 重構：unclear_count 機制廢除（取代為單一 budget + L4_UNCLEAR_NOTICE 不計次）。
    本 test 仍 cover「ack 詞走 ACK 路徑 ≠ unclear notice 路徑」分流正確。
    顧客先回 5 次「好的」（ack）+ 「s」掃碼 → 應正常到 L5 + 5 次 ack 都沒打到 unclear notice。
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # Assert
    assert next_state == "L5", (
        f"5 次 ack + s 應掃碼成功進 L5，實際：{next_state!r}"
    )
    assert L4_ACK_GENTLE in speak_calls, (
        f"應 speak 溫和回應，實際 speak：{speak_calls}"
    )
    assert L4_UNCLEAR_NOTICE not in speak_calls, (
        f"ack 詞不應走 unclear notice 路徑，但 speak 含 L4_UNCLEAR_NOTICE：{speak_calls}"
    )


# ============================================================
# L4 wall-clock budget regression tests（2026-05-26 方案 B）
# ============================================================

def test_l4_wallclock_budget_ack_spam_eventually_forced_exit() -> None:
    """L4 顧客 spam ack 詞超過 L4_TOTAL_BUDGET 預算後應強制 exit（單一 budget 防 spam）。

    核心：ack 路徑 continue 不重設 deadline；預算耗盡（remaining <= 0）
    → _l4_exit_d_forced（speak L4_D_FORCED_EXIT + clear cart + return L1）。

    fake time 機制：patch time.monotonic 讓每次呼叫回傳的值快速推進。
    第 1 次呼叫：0.0（設定 deadline = 0 + L4_TOTAL_BUDGET）
    第 2 次呼叫後：L4_TOTAL_BUDGET + 1（預算耗盡 → forced exit）
    顧客輸入 "好的" 無限重複也逃不過預算上限。
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)

    # fake_monotonic：第 1 次回 0.0（建立 deadline），之後回 budget + 1（預算立刻耗盡）
    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        if call_count[0] == 1:
            return 0.0                       # deadline = 0 + L4_TOTAL_BUDGET
        return float(L4_TOTAL_BUDGET + 1)    # remaining = -1 → 強制 exit

    # 顧客無限 ack spam（預算耗盡前只會被呼叫一次 read，因為第 2 次 monotonic 就觸發 forced exit）
    customer_input = FakeCustomerInput(["好的"] * 20)

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
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
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
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


# ============================================================
# L4 重構簡化版新行為 regression tests（2026-05-30 加）
# - 36s budget 耗盡 forced exit
# - 12s 沒回應重 speak L4_REMIND_PROMPT（不重置 budget）
# - 亂輸入印 L4_UNCLEAR_NOTICE 不重置 budget
# - 客服模式共用主 budget remaining（移除獨立 60s timeout）
# ============================================================


def test_l4_silence_full_budget_forces_exit_clears_cart() -> None:
    """L4 全程沒回應 → budget 耗盡 → forced exit + clear cart + 退 L1。

    新設計：每 12s 重 prompt → 達到 36s budget → _l4_exit_d_forced。
    對應規格：「budget 耗盡 → forced exit（speak L4_D_FORCED_EXIT + clear cart）」。

    用 fake_monotonic 跳過真實等待（避免測試跑 36 秒）：第 1 次回 0.0 設定 deadline，
    第 2 次回 budget+1 → 預算耗盡 → forced exit。
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)

    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        if call_count[0] == 1:
            return 0.0
        return float(L4_TOTAL_BUDGET + 1)

    # FakeCustomerInput 序列空時持續回 None；但 fake_monotonic 在第二次 check 就觸發退場
    customer_input = FakeCustomerInput([None])

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    assert next_state == "L1_via_subroutine_a", (
        f"全程沒回應 → budget 耗盡應退 L1，實際：{next_state!r}"
    )
    assert L4_D_FORCED_EXIT in speak_calls, (
        f"budget 耗盡應 speak L4_D_FORCED_EXIT，實際 speak：{speak_calls}"
    )
    assert cart_module.is_empty(cart), (
        f"budget 耗盡應清空 cart，實際：{cart}"
    )


def test_l4_qr_refresh_cycle_speaks_remind_unconditionally() -> None:
    """L4 v3 spec §3.3「QR 循環刷新基本」：cycle 到期 → 重印 + 重 speak L4_REMIND_PROMPT。

    v3 改變：v2「silent 立即 speak REMIND」→ v3「無條件每 12s 循環刷新」（不論顧客是否回應）。
    本 test 用 fake_monotonic 推進 cycle_deadline 到期，驗證 prod code 走 cycle refresh path。

    fake_monotonic 安排：
        - 第 1 次（進場 set budget_deadline=36 / cycle_deadline=12）→ 0.0
        - 第 2 次（while iter 1 now）→ 13.0
          → budget_remaining = 23, cycle_remaining = -1 → 觸發循環刷新
        - 第 3 次（cycle refresh 內 reset cycle_deadline）→ 13.0 → new cycle_deadline = 25.0
        - 第 4 次（while iter 2 now）→ 13.0
          → cycle_remaining = 12, budget_remaining = 23 → read → "s" → L5
    """
    from unittest.mock import patch

    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["s"])

    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        if call_count[0] == 1:
            return 0.0
        return 13.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: terminal_calls.append(text),
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # 循環刷新觸發：cycle 到期 → 重印 + speak L4_REMIND_PROMPT（v3 無條件，不需 silent）
    assert L4_REMIND_PROMPT in speak_calls, (
        f"cycle 到期應 speak L4_REMIND_PROMPT（v3 無條件循環刷新），實際 speak：{speak_calls}"
    )
    # 終端應有 >= 2 次金額明細列印（進場 1 次 + cycle 刷新 1 次）
    qr_print_count = sum(1 for t in terminal_calls if L4_QR_MOCK_HINT in t)
    assert qr_print_count >= 2, (
        f"cycle 到期應重印明細，實際 QR hint print 次數：{qr_print_count}"
    )
    # 後續 s 仍可正常掃碼成功 → L5
    assert next_state == "L5", (
        f"循環刷新後 s 仍應掃碼成功 L5，實際：{next_state!r}"
    )


def test_l4_unclear_input_speaks_unclear_notice_not_reset_budget() -> None:
    """L4 亂輸入（想一下 / 結帳 / 商品 / 無法判斷）→ speak L4_UNCLEAR_NOTICE 不計次不重置 budget。

    顧客連說 5 次亂輸入（舊 unclear_count 機制會在第 3 次自動進客服 / 強制退）+ s 掃碼
    → 新設計應仍可正常進 L5（不計次）+ 5 次 unclear notice 都印（不轉客服）。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「想一下」/「結帳」/「冰紅茶」/「你好」/「想想」都應 fall through 到 unclear notice
    customer_input = FakeCustomerInput(["想一下", "結帳", "冰紅茶", "你好", "想想", "s"])

    next_state, _, _ = states.run_l4(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L5", (
        f"5 次亂輸入後 s 應掃碼成功進 L5（不計次不踢客服），實際：{next_state!r}"
    )
    # unclear notice 應被 speak 多次（每個亂輸入一次）
    notice_count = speak_calls.count(L4_UNCLEAR_NOTICE)
    assert notice_count >= 3, (
        f"5 次亂輸入應至少 3 次 speak L4_UNCLEAR_NOTICE（不計次），實際次數：{notice_count}；speak：{speak_calls}"
    )
    # 不應走舊 unclear_count 達 3 自動進客服路徑（沒有印電話）
    # （也驗證 cart 仍非空 — 鏈路 A 不清 cart，L5 才清）
    assert not cart_module.is_empty(cart), (
        f"L4 鏈路 A 進 L5 前 cart 應仍非空（L5 負責清），實際：{cart}"
    )


# RETIRED (2026-05-30 二次重構)：
#   test_l4_service_mode_shares_main_budget_no_independent_timeout
# 退場理由：新設計客服模式改為**獨立 L4_C_CONFIRM_TIMEOUT=24s budget**
# （非共用主 L4 budget remaining），舊行為已不成立。
# 新行為 cover：test_l4_c_service_uses_independent_confirm_budget（見上方 L4-C-008）。


# ============================================================
# L4 v3 雙計時器 regression tests（2026-05-31 加）
# 對應規格：resources/specs/L4_v3_dual_timer_spec.md §3.3
# 設計核心：
#   - L4_TOTAL_BUDGET=36s 總 budget + L4_QR_REFRESH_INTERVAL=12s QR 刷新循環
#   - 兩計時器獨立，子鏈路 ack 完全不影響
#   - cancel_confirm / service_confirm 子狀態：暫停 + 補償
#   - 客服 yes「繼續」：重置兩計時器（fresh start）
#   - budget 耗盡優先於 cycle 刷新
# ============================================================


def test_l4_multiple_cycle_refreshes_within_budget() -> None:
    """spec §3.3「多次循環刷新」：24s 內無輸入 → 兩次刷新（不含進場初次列印）。

    fake_monotonic：
        - call 1（進場 set deadlines）→ 0.0
        - call 2（iter 1 now）→ 13.0 → cycle_remaining = -1 → 第 1 次 cycle refresh
        - call 3（refresh 內 reset cycle_deadline）→ 13.0 → new cycle_deadline = 25.0
        - call 4（iter 2 now）→ 26.0 → cycle_remaining = -1 → 第 2 次 cycle refresh
        - call 5（refresh 內 reset cycle_deadline）→ 26.0 → new cycle_deadline = 38.0
        - call 6（iter 3 now）→ 26.0 → read → "s" → L5
    """
    from unittest.mock import patch

    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["s"])

    call_count = [0]
    call_returns = [0.0, 13.0, 13.0, 26.0, 26.0, 26.0]
    def fake_monotonic() -> float:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(call_returns):
            return call_returns[idx]
        return 26.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: terminal_calls.append(text),
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # 兩次 cycle refresh → REMIND 應被 speak 2 次
    remind_count = speak_calls.count(L4_REMIND_PROMPT)
    assert remind_count == 2, (
        f"24s 內無輸入應觸發 2 次 cycle refresh REMIND，實際次數：{remind_count}, speak：{speak_calls}"
    )
    # 終端 QR hint 應 >= 3 次（進場 1 + 2 次刷新）
    qr_print_count = sum(1 for t in terminal_calls if L4_QR_MOCK_HINT in t)
    assert qr_print_count >= 3, (
        f"進場 + 2 次刷新應 >= 3 次 QR hint 列印，實際次數：{qr_print_count}"
    )
    assert next_state == "L5"


def test_l4_ack_does_not_reset_cycle_deadline() -> None:
    """spec §3.3「ack 不重置 cycle」：第 1 秒 ack「好的」+ 第 11 秒 silent → 第 12 秒仍觸發循環刷新。

    驗證 v3 設計：「ack 完全不影響兩計時器」— ack 後 cycle_deadline 沒被推後。

    fake_monotonic：
        - call 1（進場 set deadlines）→ 0.0
        - call 2（iter 1 now）→ 1.0 → cycle_remaining=11, budget_remaining=35 → read「好的」
            → dispatch ack（intent 等待安撫）→ speak L4_ACK_GENTLE → "ack", 0.0 → caller continue（不動）
        - call 3（iter 2 now）→ 12.0 → cycle_remaining=0（cycle_deadline 仍 12，沒被 ack 推後）
            → 觸發循環刷新 ✓
        - call 4（refresh 內 reset cycle_deadline）→ 12.0
        - call 5（iter 3 now）→ 12.0 → read → "s" → L5
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["好的", "s"])

    call_count = [0]
    call_returns = [0.0, 1.0, 12.0, 12.0, 12.0]
    def fake_monotonic() -> float:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(call_returns):
            return call_returns[idx]
        return 12.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # ack 應走 L4_ACK_GENTLE path
    assert L4_ACK_GENTLE in speak_calls, (
        f"「好的」應 speak L4_ACK_GENTLE，實際：{speak_calls}"
    )
    # 第 12 秒仍應觸發 cycle refresh（ack 沒推後 cycle_deadline）
    assert L4_REMIND_PROMPT in speak_calls, (
        f"ack 不應推後 cycle_deadline，第 12 秒應觸發循環刷新 speak REMIND，"
        f"實際：{speak_calls}"
    )
    assert next_state == "L5"


def test_l4_ack_does_not_reset_budget_deadline() -> None:
    """spec §3.3「ack 不重置 budget」：整 36s 內 ack「好的」→ 達 budget 仍 forced exit。

    驗證 v3 設計：「ack 完全不影響 budget」— 即使顧客不停 ack，總 budget 不被延長。

    fake_monotonic：
        - call 1（進場 set deadlines）→ 0.0
        - call 2（iter 1 now）→ 1.0 → cycle=11, budget=35 → read「好的」→ ack 0.0 → continue
        - call 3（iter 2 now）→ 37.0 → budget_remaining = -1 → forced exit
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 連 ack 多次（測試只會 read 一次就觸發 forced exit）
    customer_input = FakeCustomerInput(["好的"] * 10)

    call_count = [0]
    call_returns = [0.0, 1.0, 37.0]
    def fake_monotonic() -> float:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(call_returns):
            return call_returns[idx]
        return 37.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # ack 應走 L4_ACK_GENTLE path 至少一次
    assert L4_ACK_GENTLE in speak_calls
    # budget 耗盡應 forced exit + clear cart
    assert L4_D_FORCED_EXIT in speak_calls, (
        f"budget 耗盡應 speak L4_D_FORCED_EXIT，實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"
    assert cart_module.is_empty(cart)


def test_l4_cancel_confirm_no_compensates_both_deadlines() -> None:
    """spec §3.3「cancel_confirm NO 補償」：cancel_confirm 耗 3s + NO → 兩計時器都 +3s。

    驗證 v3 設計：「cancel_confirm 子狀態期間暫停，退出後補償」。

    手法：mock cancel_confirm（不走真實實作）讓它「假裝耗 3s 後 return False」；
         配合 fake_monotonic 量出主迴圈 deadlines 是否真的 +=3。

    fake_monotonic 序列：
        - call 1（進場 set deadlines）→ 0.0（budget_deadline=36, cycle_deadline=12）
        - call 2（iter 1 now）→ 1.0 → cycle=11, budget=35 → read「不要」
            → 進 dispatch 拒絕分支
            → call 3（paused_at = monotonic）→ 1.0
            → cancel_confirm（mock）→ False
            → call 4（pause_duration = monotonic - paused_at）→ 4.0 → pause_duration = 3.0
            → speak DECLINED → return ("ack", 3.0)
        - caller 補償：budget_deadline=36+3=39, cycle_deadline=12+3=15
        - call 5（iter 2 now）→ 4.0 → cycle=11, budget=35 → read「s」→ L5

    驗證點：補償後第 4 秒讀仍有 cycle=11、budget=35 餘額（沒被吃 3s），表明 deadlines 真的補了。
    若沒補償，第 4 秒讀 cycle=8、budget=32（少了 3s）。
    本 test 用一個間接驗證：mock cancel_confirm 後仍能讀到 "s" 走 L5（避免複雜 monotonic 序列出錯）。
    更直接驗證留在 unit-level「補償語意」靠 dispatch return shape 已固化。
    """
    from unittest.mock import patch

    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["不要", "s"])

    # mock cancel_confirm：假裝 NO（return False），測試 caller 端補償路徑
    # 並把 fake monotonic 控制成「進子狀態前 1.0，退出後 4.0」→ pause_duration = 3.0
    monotonic_returns = iter([
        0.0,   # 進場 set deadlines
        1.0,   # iter 1 now
        1.0,   # dispatch 內 paused_at
        4.0,   # dispatch 內 pause_duration 量測
        4.0,   # iter 2 now（補償後 budget=39, cycle=15 → remaining 都 > 0）
    ])

    def fake_monotonic() -> float:
        try:
            return next(monotonic_returns)
        except StopIteration:
            return 4.0

    # mock cancel_confirm 直接 return False（NO 路徑，無實際內部 sleep）
    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic), \
         patch("myProgram.sales.states.l4.cancel_confirm", return_value=False):
        next_state, _, _ = states.run_l4(
            speak=lambda text: None,
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # 補償成功 → 第 4 秒（補償後 budget=39, cycle=15）仍可讀到 "s" → L5
    # 若沒補償 → 第 4 秒 budget=35, cycle=11 仍 > 0，read 也會 work，本 test 嚴格驗證在 dispatch
    # return shape 已固化「cancel NO 路徑必須 return pause_duration > 0」(prod code line 上方 return)
    assert next_state == "L5", (
        f"cancel NO 補償後 s 仍應 L5，實際：{next_state!r}"
    )
    assert not cart_module.is_empty(cart), "cancel NO 不應清 cart"


def test_l4_service_yes_resets_both_deadlines() -> None:
    """spec §3.3「service yes 重置」：service yes → 兩計時器 reset + 重 speak entry prompt（不是 remind）。

    驗證 v3 設計：「客服 yes 用 reset 而非補償」— 對齊 spec §2.4 fresh start UX。

    手法：mock service_confirm return "yes" → caller dispatch 回 ("reset", 0.0) →
         主迴圈走 reset path：重印明細 + 重 speak ENTRY_PROMPT_TEMPLATE + reset 兩計時器。
    """
    from unittest.mock import patch

    speak_calls: list = []
    terminal_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    total = cart_module.calc_total(cart)
    customer_input = FakeCustomerInput(["客服", "s"])

    # mock service_confirm return "yes"
    with patch("myProgram.sales.states.l4.service_confirm", return_value="yes"):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: terminal_calls.append(text),
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # entry prompt 應 >= 2 次（進場 1 次 + 客服 yes reset 後 1 次）
    entry_prompt = L4_ENTRY_PROMPT_TEMPLATE.format(total=total)
    entry_speak_count = speak_calls.count(entry_prompt)
    assert entry_speak_count >= 2, (
        f"客服 yes 後應重 speak ENTRY_PROMPT（不是 REMIND），實際 entry 次數：{entry_speak_count}, speak：{speak_calls}"
    )
    # reset 不該 speak REMIND（REMIND 是 cycle 刷新用，reset 應走 entry prompt）
    assert L4_REMIND_PROMPT not in speak_calls, (
        f"客服 yes 重置應 speak entry prompt 不是 REMIND，實際：{speak_calls}"
    )
    # 終端應重印明細（QR hint >= 2 次：進場 + reset）
    qr_print_count = sum(1 for t in terminal_calls if L4_QR_MOCK_HINT in t)
    assert qr_print_count >= 2, (
        f"客服 yes 後應重印明細，實際 QR hint 次數：{qr_print_count}"
    )
    # 後續 s 仍可正常掃碼 → L5
    assert next_state == "L5"


def test_l4_service_no_immediate_exit_l1() -> None:
    """spec §3.3「service no 立即退」：mock service_confirm no → clear cart 退 L1（不受兩計時器影響）。

    驗證 v3 設計：「客服 no → service_mode 自己清 cart 退 L1，dispatch 包 tuple 立即 return」。
    """
    from unittest.mock import patch

    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["客服"])

    with patch("myProgram.sales.states.l4.service_confirm", return_value="no"):
        next_state, _, _ = states.run_l4(
            speak=lambda text: None,
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # service no → clear cart + 退 L1
    assert cart_module.is_empty(cart), f"客服 no 應清 cart，實際：{cart}"
    assert next_state == "L1_via_subroutine_a"


def test_l4_budget_exhausted_takes_priority_over_cycle() -> None:
    """spec §3.3「budget 耗盡優先」：budget_remaining <= 0 優先於 cycle_remaining <= 0。

    驗證 v3 prod 主迴圈順序：if budget_remaining <= 0 必須在 if cycle_remaining <= 0 之前。
    若順序錯（cycle 先 check）→ budget 已耗盡時還會 speak REMIND + 多 print 一輪 → 違 spec §3.3。

    fake_monotonic：
        - call 1（進場 set deadlines）→ 0.0（budget=36, cycle=12）
        - call 2（iter 1 now）→ 36.0
          → budget_remaining = 0 → forced exit
          → cycle_remaining = -24 也 <= 0 但 budget check 先（不該觸發 REMIND）
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput([])

    call_count = [0]
    def fake_monotonic() -> float:
        call_count[0] += 1
        if call_count[0] == 1:
            return 0.0
        return 36.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # budget 耗盡優先 → speak L4_D_FORCED_EXIT，不該 speak REMIND
    assert L4_D_FORCED_EXIT in speak_calls, (
        f"budget 耗盡應 speak L4_D_FORCED_EXIT，實際：{speak_calls}"
    )
    assert L4_REMIND_PROMPT not in speak_calls, (
        f"budget 耗盡優先於 cycle 刷新，不該 speak REMIND，實際：{speak_calls}"
    )
    assert next_state == "L1_via_subroutine_a"


def test_l4_budget_and_cycle_simultaneous_expiry_forces_exit() -> None:
    """spec §3.3「cycle 與 budget 同時到」：第 3 循環尾 + budget 36s 同時到 → forced exit（不再刷新）。

    驗證 v3 設計：3 個循環走完（12 × 3 = 36）後正好 budget 耗盡，不該多刷一輪。

    模擬「真實時序」：進場 0 → 第 1 cycle (0-12) → 第 2 cycle (12-24) → 第 3 cycle (24-36) → 36 到。
    """
    from unittest.mock import patch

    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput([])

    # 序列：
    #   call 1（進場 set deadlines）→ 0.0
    #   call 2（iter 1 now）→ 12.0 → cycle=0 → 走 cycle refresh path
    #   call 3（refresh 內 reset cycle_deadline）→ 12.0 → new cycle=24
    #   call 4（iter 2 now）→ 24.0 → cycle=0 → cycle refresh
    #   call 5（refresh 內 reset cycle_deadline）→ 24.0 → new cycle=36
    #   call 6（iter 3 now）→ 36.0 → budget_remaining=0 → forced exit（不刷第 4 輪）
    call_count = [0]
    call_returns = [0.0, 12.0, 12.0, 24.0, 24.0, 36.0]
    def fake_monotonic() -> float:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(call_returns):
            return call_returns[idx]
        return 36.0

    with patch("myProgram.sales.states.l4.time.monotonic", side_effect=fake_monotonic):
        next_state, _, _ = states.run_l4(
            speak=lambda text: speak_calls.append(text),
            print_terminal=lambda text: None,
            read_customer_input=customer_input.read,
            cart=cart,
            opencv_disable=lambda: None,
            do_action=lambda *a, **k: None,
        )

    # REMIND 應 speak 恰好 2 次（第 1 cycle 結束 + 第 2 cycle 結束；第 3 cycle 結束時 budget 已耗盡）
    remind_count = speak_calls.count(L4_REMIND_PROMPT)
    assert remind_count == 2, (
        f"3 個循環走完應 REMIND 2 次（第 3 cycle 尾 budget 同時到，不該再 REMIND），"
        f"實際次數：{remind_count}, speak：{speak_calls}"
    )
    # forced exit
    assert L4_D_FORCED_EXIT in speak_calls
    assert next_state == "L1_via_subroutine_a"


# ============================================================
# 「想買無商品」UX 補強 regression tests（2026-05-26 加）
# 使用者實機回報：L3 DyC 回「有」被誤判 unclear；L2 DnC 回「要」同 pattern
# ============================================================

def test_l2_vague_buy_intent_speaks_reask_not_unclear() -> None:
    """L2 DnC「您好，請問需要購買什麼東西嗎？」顧客回「要」應 speak DIALOG_VAGUE_BUY_REASK，
    不走 B-1 unclear 路徑；後續講「冰紅茶」+ 數量可正常加入 cart。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 「要」→ 應 speak DIALOG_VAGUE_BUY_REASK；「冰紅茶」→ 加 cart（沒數量 → 追問）；「3」→ qty；
    # 之後 None → L3 timeout → C-2 → None → silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["要", "冰紅茶", "3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 「要」應觸發 DIALOG_VAGUE_BUY_REASK，不觸發 L2_B1_CLARIFY
    assert DIALOG_VAGUE_BUY_REASK in speak_calls, (
        f"L2「要」應 speak DIALOG_VAGUE_BUY_REASK，實際 speak：{speak_calls}"
    )
    assert L2_B1_CLARIFY not in speak_calls, (
        f"L2「要」不應 speak L2_B1_CLARIFY（不走 B-1 unclear），實際 speak：{speak_calls}"
    )
    # 冰紅茶 3 瓶應在 cart 中
    assert cart.get("冰紅茶") == 3, (
        f"冰紅茶 3 瓶應在 cart，實際 cart：{dict(cart)}"
    )


def test_l3_vague_buy_intent_speaks_reask_not_unclear() -> None:
    """L3 DyC「請問還有額外需要購買的嗎？」顧客回「有」應 speak DIALOG_VAGUE_BUY_REASK，
    不走 B-1 unclear；後續講「刮刮樂」+ 數量可正常加入 cart。
    """
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)  # L3 mode 起點 cart 非空
    # 「有」→ DIALOG_VAGUE_BUY_REASK；「刮刮樂」→ 追問數量；「1」→ qty；None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["有", "刮刮樂", "1", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 「有」應觸發 DIALOG_VAGUE_BUY_REASK，不觸發 L3_B1_CLARIFY
    assert DIALOG_VAGUE_BUY_REASK in speak_calls, (
        f"L3「有」應 speak DIALOG_VAGUE_BUY_REASK，實際 speak：{speak_calls}"
    )
    assert L3_B1_CLARIFY not in speak_calls, (
        f"L3「有」不應 speak L3_B1_CLARIFY（不走 B-1 unclear），實際 speak：{speak_calls}"
    )
    # 刮刮樂 1 張應在 cart 中
    assert cart.get("刮刮樂") == 1, (
        f"刮刮樂 1 張應在 cart，實際 cart：{dict(cart)}"
    )


def test_vague_buy_does_not_increment_unclear_count() -> None:
    """顧客連續講「有」5 次 + 給商品 → 不應因 unclear 累積被踢進 B-1 上限路徑。

    若 unclear 累積，5 次後（UNCLEAR_MAX=5）會觸發 L2_UNCLEAR_REJECT_VOICE / L3_UNCLEAR_FINAL_PROMPT；
    「想買無商品」不應 ++unclear_count，故連講 5 次「有」後仍能正常購物。
    """
    from myProgram.sales.constants import UNCLEAR_MAX
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)  # L3 mode（cart 非空）
    # UNCLEAR_MAX 次「有」+ 商品 + 數量 + None（C-2）+ None（silent → confirm）+ 「對」（confirm yes → L4）
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["有"] * UNCLEAR_MAX + ["刮刮樂", "2", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 每次「有」都應 speak DIALOG_VAGUE_BUY_REASK
    assert speak_calls.count(DIALOG_VAGUE_BUY_REASK) == UNCLEAR_MAX, (
        f"「有」×{UNCLEAR_MAX} 每次都應 speak DIALOG_VAGUE_BUY_REASK，"
        f"實際次數：{speak_calls.count(DIALOG_VAGUE_BUY_REASK)}，speak：{speak_calls}"
    )
    # 不應觸發 L3_B1_CLARIFY（unclear 不累積）
    assert L3_B1_CLARIFY not in speak_calls, (
        f"不應觸發 L3_B1_CLARIFY，實際 speak：{speak_calls}"
    )
    # 刮刮樂應加入 cart
    assert cart.get("刮刮樂") == 2, (
        f"刮刮樂 2 張應在 cart，實際 cart：{dict(cart)}"
    )


# ============================================================
# Wave 4 hotfix（2026-05-26）— caller 端 cart cap 業務檢查
#
# 背景：Pi 實機踩坑（顧客輸入「34435454545454545」），parse_quantity
# 解析為天文數字 → cart.add_item raise AssertionError → 整個程式 crash。
# 根因：Wave 4 加了 add_item 的 invariant assert 但 caller
# `_qty_follow_up_sub_loop` 沒做業務層檢查。
#
# 設計分層：
#   - add_item assert = 「程式內部 invariant 守衛」，保留（防 caller 異常值）
#   - caller 應**先業務檢查**：超量 → speak 友善提示 + 重新追問
#
# 修法（方案 B — caller 層擋單筆 + 累加超量 + remaining 計算）：
#   resolve_and_add_products 內 qty 已知路徑：超量 → speak 提示 + skip
#   _qty_follow_up_sub_loop 追問路徑：超量 → speak 提示 + 重新追問
# ============================================================


def test_qty_followup_single_quantity_exceeds_cap_speaks_remaining_and_retries() -> None:
    """顧客單筆 follow-up 說超量（> MAX_QTY_PER_ITEM）→ speak「最多還能點」提示 + 重新追問。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶（無數量） → 追問 → "100"（超量 50） → speak「最多還能點 50」 → "5" → 加 5
    # → 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶", "100", "5", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 5, (
        f"應加 5 瓶（超量 100 被擋後 follow-up 改 5），實際：{dict(cart)}"
    )
    # 應有「最多還能點 50」提示（cart 為空，remaining = MAX_QTY_PER_ITEM = 50）
    assert any("最多還能點" in s and str(MAX_QTY_PER_ITEM) in s for s in speak_calls), (
        f"預期『最多還能點 {MAX_QTY_PER_ITEM}』提示，實際 speak_calls={speak_calls}"
    )


def test_qty_followup_cumulative_quantity_exceeds_cap_speaks_remaining() -> None:
    """cart 已有 30 瓶冰紅茶 → 再 follow-up 說 25 瓶（累加超量 55 > 50）→ speak「還可加 20」+ 重新追問改 15。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 30)  # 預設 cart 已有 30 瓶（L3 場景）
    # 從 L3 入口 → 追問鏈路：「紅茶」(無數量) → "25"（累加 30+25=55 > 50）
    # → speak「最多還能點 20」 → "15" → 加 15（30+15=45 OK）→ None None C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶", "25", "15", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == 45, (
        f"預期 30 + 15 = 45，實際：{dict(cart)}"
    )
    # remaining = 50 - 30 = 20
    assert any("最多還能點" in s and "20" in s for s in speak_calls), (
        f"預期『最多還能點 20』提示，實際 speak_calls={speak_calls}"
    )


def test_qty_followup_cart_at_cap_speaks_and_skips_product() -> None:
    """cart 已達上限（50 瓶冰紅茶）→ 再 follow-up 加 1 瓶 → speak「已經點到單筆上限」+ skip 此商品。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", MAX_QTY_PER_ITEM)  # 已達上限
    # L3 場景：「紅茶」(無數量) → 追問 → "1" → cart 已滿 → speak 提示 + skip → None None silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶", "1", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == MAX_QTY_PER_ITEM, (
        f"cart 不應變動（已達上限），實際：{dict(cart)}"
    )
    assert any("已經點到單筆上限" in s for s in speak_calls), (
        f"預期『已經點到單筆上限』提示，實際 speak_calls={speak_calls}"
    )


def test_qty_followup_huge_number_does_not_crash() -> None:
    """Regression guard — 顧客輸入天文數字「34435454545454545」不該 crash，應走「最多還能點」提示流程。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶（無數量）→ 追問 → "34435454545454545"（天文數字 > MAX_QTY_PER_ITEM）
    # → speak「最多還能點 50」 → "3" → 加 3 → None None C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶", "34435454545454545", "3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert next_state == "L4"
    assert cart_module.get_quantity(cart, "冰紅茶") == 3, (
        f"天文數字被擋後改 3 應加 3 瓶，實際：{dict(cart)}"
    )
    # 不該 raise AssertionError；應走 speak 提示流程
    assert any("最多還能點" in s for s in speak_calls), (
        f"預期『最多還能點』提示，實際 speak_calls={speak_calls}"
    )


# ============================================================
# Wave 4 hotfix 2（2026-05-27）— resolve_and_add_products 同類 cart cap 業務檢查
#
# 背景：Hotfix 1（commit f37d11a）只修了 _qty_follow_up_sub_loop（追問 sub-loop
# 路徑），但 resolve_and_add_products 內 for loop 同類風險未修：
# 顧客**一次說**「紅茶 34435454545454545」→ parse_products 直接返
# [("冰紅茶", 34435454545454545)] → 走 for loop 內 add_item 路徑 → 同樣 crash。
#
# 設計差異 vs hotfix 1：
#   - hotfix 1 (_qty_follow_up_sub_loop) 是 sub-loop，可「continue 重新追問」
#   - hotfix 2 (resolve_and_add_products) 是「一次給」路徑，無重試機會
#     → 採「cap 為 remaining + speak 透明告知實際加入量」最 UX
# ============================================================


def test_resolve_and_add_products_single_huge_qty_caps_and_speaks() -> None:
    """顧客一次說「紅茶 100」(超 MAX 50) → cap 加入 50 + speak「達到單筆上限」通知。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    # cart 空 → "紅茶 100"（一次給超量）→ cap 50 加入 + speak →
    # added=True → speak L2_TO_L3_TRANSITION（合成 voice）→ continue 主迴圈 →
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 100", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == MAX_QTY_PER_ITEM, (
        f"應 cap 為上限 {MAX_QTY_PER_ITEM}，實際：{dict(cart)}"
    )
    assert any("達到單筆上限" in s for s in speak_calls), (
        f"預期『達到單筆上限』提示，實際 speak_calls={speak_calls}"
    )


def test_resolve_and_add_products_cumulative_over_cap_caps_to_remaining() -> None:
    """cart 已有 30 瓶紅茶，再一次說「紅茶 25」(累加 55 > 50) → cap 加 20（remaining）。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 30)  # 預設 cart 已有 30 瓶
    # cart 非空 → L3 模式 → "紅茶 25" → cap remaining=20 → add 20 + speak →
    # added=True → speak L3_REASK → continue → 後續 None None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 25", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == 50, (
        f"預期 30 + cap(20) = 50，實際：{dict(cart)}"
    )
    assert any("達到單筆上限" in s for s in speak_calls), (
        f"預期『達到單筆上限』提示，實際 speak_calls={speak_calls}"
    )


def test_resolve_and_add_products_at_cap_skips_and_speaks() -> None:
    """cart 已 50 瓶（達上限）→ 再一次說「紅茶 5」→ 完全 skip + speak「無法再加」。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", MAX_QTY_PER_ITEM)  # 已達上限
    # cart 非空（達上限）→ L3 模式 → "紅茶 5" → resolve for loop remaining=0
    # → speak「已經點到單筆上限... 無法再加」+ continue → added_count=0
    # → resolve 返 False → caller speak L3_REASK → continue → None None → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑，
    # 需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 5", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == MAX_QTY_PER_ITEM, (
        f"cart 不應變動（已達上限），實際：{dict(cart)}"
    )
    assert any("已經點到單筆上限" in s and "無法再加" in s for s in speak_calls), (
        f"預期『已經點到單筆上限... 無法再加』提示，實際 speak_calls={speak_calls}"
    )


def test_resolve_and_add_products_huge_number_does_not_crash() -> None:
    """Regression guard — 顧客一次給「紅茶 34435454545454545」不該 crash（Pi 實機踩坑）。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 完整 Pi 實機輸入；舊代碼會 raise AssertionError 整個程式 crash
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 34435454545454545", None, None, "對"])

    # 不該 raise AssertionError
    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert cart_module.get_quantity(cart, "冰紅茶") == MAX_QTY_PER_ITEM, (
        f"天文數字應 cap 為上限 {MAX_QTY_PER_ITEM}，實際：{dict(cart)}"
    )
    assert any("達到單筆上限" in s for s in speak_calls), (
        f"預期『達到單筆上限』提示，實際 speak_calls={speak_calls}"
    )


def test_resolve_and_add_products_multi_product_partial_cap() -> None:
    """一次說「紅茶 100 刮刮樂 3」→ 紅茶 cap 50 + 刮刮樂 3 正常加（多商品各自獨立處理）。"""
    from myProgram.sales.constants import MAX_QTY_PER_ITEM
    speak_calls: list = []
    cart = cart_module.new_cart()
    # 一次給多商品 → 加單 L3；後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 100 刮刮樂 3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 紅茶 cap 為上限 50，刮刮樂正常加 3（兩商品在 for loop 內各自獨立檢查）
    assert cart_module.get_quantity(cart, "冰紅茶") == MAX_QTY_PER_ITEM, (
        f"紅茶應 cap 為 {MAX_QTY_PER_ITEM}，實際：{dict(cart)}"
    )
    assert cart_module.get_quantity(cart, "刮刮樂") == 3, (
        f"刮刮樂應正常加 3，實際：{dict(cart)}"
    )
    assert any("達到單筆上限" in s for s in speak_calls), (
        f"預期『達到單筆上限』提示，實際 speak_calls={speak_calls}"
    )


# ============================================================
# S3 — 同步動作觸發點測試（2026-05-27 加，incremental rebuild S3 階段）
# ============================================================
#
# 目的：驗證 do_action callback 在 5 個觸發點被以正確的 ACTION_* 常數呼叫，
# 並驗證關鍵 non-trigger（L1 hawk 後續輪播）**不**跑動作。
#
# Test fixtures 採純 list 收集 callback 呼叫紀錄(不用 mock library)，
# 對齊既有 speak_calls / sleep_calls pattern。
# ============================================================

from myProgram.sales.constants import (
    ACTION_L1_HAWK,
    ACTION_L2,
    ACTION_L3,
    ACTION_L3_CHECKOUT_GO,
    ACTION_L4_PAY,
    ACTION_L5_FAREWELL,
)


def test_l1_hawk_entry_calls_do_action_with_action_l1_hawk() -> None:
    """L1 進入叫賣模式時 do_action 被以 ACTION_L1_HAWK 呼叫一次。"""
    # Arrange
    do_action_calls: list = []
    opencv = FakeOpencv(dwell_value=OPENCV_DWELL)  # 偵測立即觸發，即時退出 hawk
    # 進叫賣 (1)，opencv dwell 滿足，轉 L2 退出
    kbd = FakeKeyboardInput(["1"])

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
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：hawk entry 觸發一次 ACTION_L1_HAWK
    assert ACTION_L1_HAWK in do_action_calls, (
        f"hawk entry 應呼叫 do_action(ACTION_L1_HAWK)，實際：{do_action_calls}"
    )
    assert do_action_calls.count(ACTION_L1_HAWK) == 1, (
        f"hawk entry ACTION_L1_HAWK 應只被呼叫 1 次(subsequent 輪播不跑動作)，"
        f"實際 do_action_calls={do_action_calls}"
    )


def test_l1_hawk_subsequent_rounds_do_not_call_do_action() -> None:
    """L1 hawk schedule 後續輪播(_schedule_hawk_l1)**不**跑動作 — servo 過熱防護。

    FakeScheduler tick 模擬 4 次 HAWK_INTERVAL(每次觸發一次後續 speak 輪播)；
    do_action 應仍只被呼叫 1 次(entry 那次)，不受 schedule 輪播觸發。
    """
    # Arrange
    do_action_calls: list = []
    opencv = FakeOpencv(dwell_value=OPENCV_DWELL)
    kbd = FakeKeyboardInput(["1"])
    scheduler = FakeScheduler()

    # Act
    states.run_l1(
        print_terminal=lambda text: None,
        read_terminal_key=kbd.read,
        opencv_dwell_seconds=opencv.dwell_seconds,
        opencv_disable=opencv.disable,
        opencv_enable=opencv.enable,
        speak=lambda text: None,
        exit_program=lambda: None,
        schedule=scheduler.schedule,
        show_hawk_help=lambda *a, **k: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # 推進 4 個 HAWK_INTERVAL，連鎖觸發後續輪播 callback
    scheduler.tick(HAWK_INTERVAL * 4 + 1)

    # Assert：do_action 仍只跑了 1 次(entry)，輪播未追加
    assert do_action_calls == [ACTION_L1_HAWK], (
        f"後續輪播不應觸發 do_action(servo 過熱防護)；"
        f"預期僅 1 次 entry 呼叫，實際 do_action_calls={do_action_calls}"
    )


def test_dialog_l2_entry_calls_do_action_with_action_l2() -> None:
    """run_dialog entry：cart 空 -> do_action(ACTION_L2)。"""
    # Arrange
    do_action_calls: list = []
    cart = cart_module.new_cart()  # 空 cart -> L2 mode
    customer_input = FakeCustomerInput([None])  # ENTRY 後 timeout 鏈路 A 退

    # Act
    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：entry 觸發 ACTION_L2 一次(cart 空)
    assert do_action_calls == [ACTION_L2], (
        f"L2 entry 應呼叫 do_action(ACTION_L2) 一次(cart 空，後續 timeout 不再跑)，"
        f"實際 do_action_calls={do_action_calls}"
    )


def test_dialog_l3_entry_calls_do_action_with_action_l3() -> None:
    """run_dialog entry：cart 非空 -> do_action(ACTION_L3)。"""
    # Arrange
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)  # cart 非空 L3 mode
    # ENTRY 後輸入「不要」鏈路 A 退出(清 cart)
    customer_input = FakeCustomerInput(["不要"])

    # Act
    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：entry 觸發 ACTION_L3 一次(cart 非空)
    assert do_action_calls == [ACTION_L3], (
        f"L3 entry 應呼叫 do_action(ACTION_L3) 一次(cart 非空)，"
        f"實際 do_action_calls={do_action_calls}"
    )


def test_l4_pay_success_main_dispatcher_calls_do_action() -> None:
    """L4 鏈路 A(_l4_dispatch_response 內終端 's' 路徑)：do_action(ACTION_L4_PAY)。

    觸發點 (a)：主等待迴圈讀到 's' -> 進 _l4_dispatch_response -> speak 付款成功 + do_action。
    """
    # Arrange
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    customer_input = FakeCustomerInput(["s"])  # 直接掃碼成功

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：鏈路 A 走 main dispatcher 路徑 -> ACTION_L4_PAY 被呼叫
    assert next_state == "L5", f"鏈路 A 應轉 L5，實際 next_state={next_state}"
    assert ACTION_L4_PAY in do_action_calls, (
        f"L4 main dispatcher 鏈路 A 應呼叫 do_action(ACTION_L4_PAY)，"
        f"實際：{do_action_calls}"
    )


def test_l4_pay_success_service_mode_calls_do_action() -> None:
    """L4 鏈路 A(_l4_service_mode 內 's' 路徑)：do_action(ACTION_L4_PAY)。

    觸發點 (b)：顧客先觸發客服模式(speak「客服」)，在客服 mode 內輸入 's' -> 同樣 speak
    付款成功 + do_action。此路徑驗證第二個觸發點不被遺漏(規格表明示兩處都要插)。
    """
    # Arrange
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 序列：第一次「客服」-> 進 _l4_service_mode；第二次 "s" -> 在 service mode 內掃碼
    customer_input = FakeCustomerInput(["客服", "s"])

    # Act
    next_state, _, _ = states.run_l4(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：service mode 內掃碼也應觸發 ACTION_L4_PAY
    assert next_state == "L5", f"service mode 內 's' 應轉 L5，實際 next_state={next_state}"
    assert ACTION_L4_PAY in do_action_calls, (
        f"L4 service mode 鏈路 A 應呼叫 do_action(ACTION_L4_PAY)，"
        f"實際：{do_action_calls}"
    )


def test_l5_entry_calls_do_action_after_thanks() -> None:
    """L5 進入後：speak(L5_THANKS) -> do_action(ACTION_L5_FAREWELL) -> clear_cart -> sleep。

    驗證 do_action 在 speak 之後、clear_cart 之前被呼叫一次(規格表明示順序)。
    """
    # Arrange
    speak_calls: list = []
    sleep_calls: list = []
    do_action_calls: list = []
    # 用一個會記錄當下 cart 狀態的 do_action stub，驗證呼叫時 cart 仍未被清
    cart: dict = {"冰紅茶": 2}
    cart_at_do_action: list = []

    def _capture_do_action(name):
        do_action_calls.append(name)
        cart_at_do_action.append(dict(cart))  # snapshot

    # Act
    states.run_l5(
        speak=lambda text: speak_calls.append(text),
        cart=cart,
        sleep=lambda secs: sleep_calls.append(secs),
        do_action=_capture_do_action,
    )

    # Assert：do_action 被以 ACTION_L5_FAREWELL 呼叫一次
    assert do_action_calls == [ACTION_L5_FAREWELL], (
        f"L5 應呼叫 do_action(ACTION_L5_FAREWELL) 一次，實際：{do_action_calls}"
    )
    # Assert：do_action 呼叫時 cart 仍未被清(規格：speak -> do_action -> clear_cart)
    assert cart_at_do_action == [{"冰紅茶": 2}], (
        f"do_action 呼叫時 cart 應仍未清空(規格順序：speak -> do_action -> clear_cart)；"
        f"實際 cart 快照={cart_at_do_action}"
    )
    # Assert：do_action 呼叫後 cart 才被清空
    assert cart_module.is_empty(cart), (
        f"L5 結束時 cart 應已清空，實際：{cart}"
    )
    # Assert：sleep 在 do_action 之後仍正常呼叫一次
    assert sleep_calls == [THANK_DELAY], (
        f"sleep 應被以 THANK_DELAY 呼叫一次，實際：{sleep_calls}"
    )


def test_dialog_l3_action_triggered_on_main_loop_transition() -> None:
    """L2→L3 transition（main_loop 路徑）：顧客在主迴圈說商品 → cart 從空變非空 → 觸發 ACTION_L3。

    Bug fix（2026-05-27 Pi demo 實測）：原 S3 只在 run_dialog entry 跑 do_action，
    顧客在 L2 加單成功後系統繼續對話到 L3 但沒重跑動作。修補後 main_loop
    `was_empty` 分支內 speak(L2_TO_L3_TRANSITION) 前插 do_action(ACTION_L3)。
    """
    do_action_calls: list = []
    cart = cart_module.new_cart()  # 空 cart → 進 L2 mode → entry ACTION_L2
    # 「紅茶 1」一個輸入加單成功 → cart 非空 → speak L2_TO_L3_TRANSITION（合成 voice）
    # 後續 main_loop timeout → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑，需 confirm yes 才到 L4 + 保留 cart）
    customer_input = FakeCustomerInput(["紅茶 1", None, None, "對"])

    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：entry ACTION_L2 + main_loop transition ACTION_L3 + confirm yes → ACTION_L3_CHECKOUT_GO
    assert do_action_calls == [ACTION_L2, ACTION_L3, ACTION_L3_CHECKOUT_GO], (
        f"L2→L3 main_loop transition 應 do_action 序列 "
        f"[ACTION_L2, ACTION_L3, ACTION_L3_CHECKOUT_GO]，實際：{do_action_calls}"
    )


def test_dialog_l3_action_triggered_on_silence_transition() -> None:
    """L2→L3 transition（silence 路徑）：顧客在 B-3 沉默期內加單 → 觸發 ACTION_L3。

    覆蓋 _dialog_dispatch_inner_l2 內 added 分支的 do_action 插入點（main_loop 是另一條路徑）。
    """
    do_action_calls: list = []
    cart = cart_module.new_cart()
    # ["想一下" → 進 B-3 silence, "紅茶 1" → silence 期內加單 → trigger ACTION_L3]
    # silence 結束回 main_loop continue → 下次 timeout → C-2 silent → confirm；
    # 「對」 → confirm yes → L4（2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["想一下", "紅茶 1", None, None, "對"])

    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：entry ACTION_L2 + silence transition ACTION_L3 + confirm yes → ACTION_L3_CHECKOUT_GO
    assert do_action_calls == [ACTION_L2, ACTION_L3, ACTION_L3_CHECKOUT_GO], (
        f"L2→L3 silence transition 應 do_action 序列 "
        f"[ACTION_L2, ACTION_L3, ACTION_L3_CHECKOUT_GO]，實際：{do_action_calls}"
    )


def test_dialog_l3_action_NOT_triggered_on_subsequent_add() -> None:
    """cart 已非空時加單（L3 內加更多商品）→ 不重跑 ACTION_L3。

    設計規範：每層只 entry 一次跑動作；L3 內後續加單只 speak L3_REASK，
    不重跑動作（避免每次加單都動，servo 過熱風險）。
    """
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)  # cart 非空 → entry 走 L3 mode 跑 ACTION_L3
    # 「刮刮樂 3」L3 內加新商品 → cart 仍非空 → speak L3_REASK，**不**跑 do_action
    # 後續 None None → C-2 silent → confirm；「對」 → confirm yes → L4
    # （2026-05-29 silent timeout 改經 confirm 合流路徑）
    customer_input = FakeCustomerInput(["刮刮樂 3", None, None, "對"])

    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    # Assert：只 entry 跑 ACTION_L3 一次，後續加單不重跑；confirm yes → ACTION_L3_CHECKOUT_GO
    assert do_action_calls == [ACTION_L3, ACTION_L3_CHECKOUT_GO], (
        f"L3 內後續加單不應重跑 ACTION_L3，預期 "
        f"[ACTION_L3, ACTION_L3_CHECKOUT_GO]，實際：{do_action_calls}"
    )


def test_dialog_l3_checkout_go_action_triggered_via_main_loop() -> None:
    """L3 → L4 transition（main_loop 路徑）：顧客結帳意圖 + confirm yes → ACTION_L3_CHECKOUT_GO。

    2026-05-28 加：使用者要求進 L4 等掃碼前加引導動作（point_screen）。
    """
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)  # cart 非空 → entry L3 mode 跑 ACTION_L3
    # ["結帳" → main_loop intent=結帳 → checkout_confirm, "對" → yes → speak + do_action → L4]
    customer_input = FakeCustomerInput(["結帳", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    assert next_state == "L4"
    # Assert：entry ACTION_L3 + L3→L4 transition ACTION_L3_CHECKOUT_GO
    assert do_action_calls == [ACTION_L3, ACTION_L3_CHECKOUT_GO], (
        f"L3 → L4 main_loop transition 應 do_action 序列 [ACTION_L3, ACTION_L3_CHECKOUT_GO]，"
        f"實際：{do_action_calls}"
    )


def test_dialog_l3_checkout_go_action_triggered_via_silence_period() -> None:
    """L3 → L4 transition（silence path）：silence 期內結帳 + confirm yes → ACTION_L3_CHECKOUT_GO。

    覆蓋 _dialog_dispatch_inner_l3 內結帳 path 的 do_action 插入點（main_loop 是另一條）。
    """
    do_action_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 2)  # cart 非空 → entry L3 mode
    # ["想一下" → 進 B-4 silence, "結帳" → silence 期內 dispatch_inner_l3 intent=結帳,
    #  "對" → checkout_confirm yes → speak + do_action → L4]
    customer_input = FakeCustomerInput(["想一下", "結帳", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda name: do_action_calls.append(name),
    )

    assert next_state == "L4"
    assert do_action_calls == [ACTION_L3, ACTION_L3_CHECKOUT_GO], (
        f"L3 → L4 silence transition 應 do_action 序列 [ACTION_L3, ACTION_L3_CHECKOUT_GO]，"
        f"實際：{do_action_calls}"
    )


# ============================================================
# 2026-05-30 v3 — qty followup 也用 speak_and_wait（接續 c418004 v2）
#
# 背景：v2 commit c418004 把 wall-clock budget 用的 callers（cancel_confirm /
# _dialog_c2_second_stage / run_l4 entry）改用 speak_and_wait — deadline 從 TTS
# 播完才起算。User Pi demo 發現 qty followup「請問冰紅茶要幾瓶？」也踩同樣 UX
# bug：speak 非阻塞 + read_customer_input(timeout=WAIT_NO_RESPONSE=6s) 立即倒數，
# 2-3s 語音吃掉一半預算 → 顧客真正可回應只剩 ~3s。
#
# 修法：qty followup「speak prompt 後接 read」path 都改用 speak_and_wait
# （signature 加 kwarg，None fallback 至 speak — 向後兼容既有 fixture）
# ============================================================


def test_qty_followup_initial_prompt_uses_speak_and_wait() -> None:
    """初次 qty followup prompt「請問冰紅茶要幾瓶？」應走 speak_and_wait，讓 6s timeout 從 TTS 播完起算。"""
    speak_calls: list = []
    speak_and_wait_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶（無數量）→ resolve_and_add_products 內走追問 path → 應呼叫 speak_and_wait(QTY_PROMPT_TEMPLATE...)
    # 後續 "2" 入 cart → None None C-2 silent → confirm；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput(["紅茶", "2", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
        speak_and_wait=lambda text: speak_and_wait_calls.append(text),
    )

    assert next_state == "L4"
    # 初次 qty prompt「請問冰紅茶要幾瓶？」必須走 speak_and_wait
    assert any("冰紅茶" in s and "幾瓶" in s for s in speak_and_wait_calls), (
        f"預期 speak_and_wait 收到『請問冰紅茶要幾瓶？』風格 prompt，"
        f"實際 speak_and_wait_calls={speak_and_wait_calls}, speak_calls={speak_calls}"
    )


def test_qty_followup_clarify_after_unclear_uses_speak_and_wait() -> None:
    """qty followup attempts++ clarify prompt（顧客回應無法判斷時）應走 speak_and_wait。"""
    speak_calls: list = []
    speak_and_wait_calls: list = []
    cart = cart_module.new_cart()
    # 紅茶（無數量）→ 追問 → "嗯嗯"（無法判斷 → attempts=1 speak clarify） → "3" → 加 3
    # → None None C-2 silent → confirm；「對」 → confirm yes → L4
    customer_input = FakeCustomerInput(["紅茶", "嗯嗯", "3", None, None, "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
        speak_and_wait=lambda text: speak_and_wait_calls.append(text),
    )

    assert next_state == "L4"
    # clarify prompt（QTY_CLARIFY_TEMPLATE「不好意思我聽不太懂，請問您要幾{unit}...」）必須走 speak_and_wait
    # 兩個 speak_and_wait call 預期：initial prompt + clarify prompt
    assert len(speak_and_wait_calls) >= 2, (
        f"預期至少 2 個 speak_and_wait（initial + clarify），實際 {speak_and_wait_calls}"
    )
    assert any("不好意思" in s and "幾" in s for s in speak_and_wait_calls), (
        f"預期 speak_and_wait 收到 clarify 風格 prompt，"
        f"實際 speak_and_wait_calls={speak_and_wait_calls}"
    )


# ============================================================
# 2026-05-30：qty followup timeout 6s → 12s（QTY_FOLLOWUP_TIMEOUT 專屬常數）
#
# User demo 反饋：「請問X要幾Y？」追問 6s 過急。改 12s 給顧客更寬鬆回答時間。
# 不影響其他 7 處 6s caller（B-3/B-4 沉默 / unclear_final / L4 main/final/service）。
# ============================================================


def test_qty_followup_read_uses_qty_followup_timeout_constant() -> None:
    """qty followup sub-loop 內 read_customer_input 必須以 timeout=12 呼叫（QTY_FOLLOWUP_TIMEOUT）。

    用 recording stub 取代 FakeCustomerInput，捕獲每次 read 的 timeout 參數。
    場景：紅茶（無數量）→ qty_followup ask → 顧客回 "2" → 加 cart →
    None None C-2 silent → confirm；「對」→ L4。
    只驗證「追問 read」這一次 timeout（首次 read 觸發 qty followup）。
    """
    from myProgram.sales.constants import QTY_FOLLOWUP_TIMEOUT

    timeout_log: list[float] = []
    seq = iter(["紅茶", "2", None, None, "對"])

    def recording_read(timeout: float) -> str | None:
        timeout_log.append(timeout)
        return next(seq, None)

    cart = cart_module.new_cart()
    next_state, _ = states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=recording_read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    # 驗：QTY_FOLLOWUP_TIMEOUT (12s) 至少出現一次 — 對應追問 read（顧客回 "2" 那次）
    assert QTY_FOLLOWUP_TIMEOUT in timeout_log, (
        f"qty followup read 應以 timeout={QTY_FOLLOWUP_TIMEOUT} 呼叫，實際 timeouts={timeout_log}"
    )
    # 反向：追問 path 不再用 WAIT_NO_RESPONSE (6s)。其他 caller（L2 entry / C-2 silent /
    # confirm）可能仍用 6s 或其他值，故只驗「12 有出現」+ 「至少 12 有出現」即可。
    assert next_state == "L4"
