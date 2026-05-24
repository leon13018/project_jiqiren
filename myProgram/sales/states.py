"""L1-L5 各層鏈路實作（S1 v2）。

對應規格書：
    - L0：共通子例程 A（「回 L1 叫賣」）
    - L1-L5：各層鏈路（本輪僅實作 L0 子例程 A，L1-L5 留 TODO）

設計原則：
    - 對外動作以 callback 注入（speak / mute_opencv / unmute_opencv / schedule）
    - 不直接 import 廠商 SDK（ActionGroupControl / Board）
    - 單檔起步，等長到 >300 行再拆 states/ 子資料夾
"""

from myProgram.sales.constants import HAWK_SLOGANS, HAWK_INTERVAL, OPENCV_MUTE


def run_subroutine_a(
    speak,
    mute_opencv,
    unmute_opencv,
    schedule,
) -> None:
    """子例程 A：「回 L1 叫賣」。

    步驟（依規格書 L0_共通.md「子例程 A」段）：
        1. 立即屏蔽 OpenCV 偵測 OPENCV_MUTE（12）秒
        2. OPENCV_MUTE 秒後恢復 OpenCV + 立即播第 1 組叫賣
        3. 後續每 HAWK_INTERVAL（12）秒換下一組，依 mod 6 輪流

    Args:
        speak: callback(text: str) — 語音播放
        mute_opencv: callback(seconds: float) — 屏蔽 OpenCV 偵測
        unmute_opencv: callback() — 恢復 OpenCV 偵測
        schedule: callback(seconds: float, fn) — 排程延遲執行
    """
    # 步驟 1：立即屏蔽 OpenCV
    mute_opencv(OPENCV_MUTE)

    # 步驟 2 + 3：OPENCV_MUTE 秒後恢復並開始叫賣
    _schedule_hawk(
        speak=speak,
        unmute_opencv=unmute_opencv,
        schedule=schedule,
        hawk_index=0,
        delay=OPENCV_MUTE,
        first_call=True,
    )


def _schedule_hawk(
    speak,
    unmute_opencv,
    schedule,
    hawk_index: int,
    delay: float,
    first_call: bool = False,
) -> None:
    """排程下一輪叫賣（遞迴排程）。

    Args:
        speak: 語音 callback
        unmute_opencv: 恢復 OpenCV callback（第一次才呼叫）
        schedule: 排程 callback
        hawk_index: 當前叫賣術語索引（0-based，mod 6 輪替）
        delay: 距下次叫賣的延遲秒數
        first_call: 是否為 OpenCV mute 結束後的第一次叫賣
    """
    def _on_due():
        # 第一次才恢復 OpenCV
        if first_call:
            unmute_opencv()
        # 播放當前索引對應的叫賣術語
        speak(HAWK_SLOGANS[hawk_index % 6])
        # 排程下一輪
        _schedule_hawk(
            speak=speak,
            unmute_opencv=unmute_opencv,
            schedule=schedule,
            hawk_index=hawk_index + 1,
            delay=HAWK_INTERVAL,
            first_call=False,
        )

    schedule(delay, _on_due)
