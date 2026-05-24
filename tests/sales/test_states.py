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
from myProgram.sales.constants import HAWK_SLOGANS, HAWK_INTERVAL, OPENCV_MUTE


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
