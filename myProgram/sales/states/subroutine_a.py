"""L0 共通子例程 A：「交易完緩衝」（2026-05-25 重構，方案 A）。

對應規格書：resources/plans/業務程式邏輯規劃/L0_共通.md「共通子例程」段

歷史變更：原規格「回 L1 叫賣」（mute 12s → unmute + 自動播叫賣輪播），
使用者實機回報後修訂為「只 mute 12s，不 unmute、不自動叫賣」 — 避免主選單時
被自動拉開 OpenCV / 被背景叫賣聲干擾。商家須明確按 1 或 2 進叫賣模式才會啟動。

剩餘職責：給「同一顧客剛離開又走回相機範圍」一個 12s 緩衝，避免立刻被拉進 dialog。
"""

from myProgram.sales.constants import OPENCV_MUTE


def run_subroutine_a(
    mute_opencv,
) -> None:
    """子例程 A：交易完緩衝 — 屏蔽 OpenCV `OPENCV_MUTE`（12s）秒，期間不偵測。

    步驟（依規格書 L0_共通.md「子例程 A」段，2026-05-25 簡化）：
        1. 立即屏蔽 OpenCV 偵測 OPENCV_MUTE 秒
        2. 12s 後不做任何事（不再 unmute / 不再叫賣）—
           主選單期間 OpenCV 保持關閉狀態，商家主動選叫賣才會重新 enable。

    Args:
        mute_opencv: callback(seconds: float) — 屏蔽 OpenCV 偵測
    """
    mute_opencv(OPENCV_MUTE)
