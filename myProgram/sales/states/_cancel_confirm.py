"""跨 L2/L3/L4 通用「取消交易」確認 6s 子狀態 helper（2026-05-29 加；W3 facade 化）。

User 要求 L2/L3/L4 任何 read 點偵測到 cancel intent 後進 6s confirm（不再直接退 L1）。
cancel_confirm 現為 facade，委派 _timed_confirm.CancelConfirm 單例執行 wall-clock 骨架
（行為規約：NO 先於 YES、亂答不重置、timeout/silent→取消，見 _timed_confirm）。

對應 is_cancel_intent helper：caller 端先用 is_cancel_intent 偵測 reject intent，
再 call cancel_confirm 取得是否真要取消。
"""

# 保留 import time：既有測試（CANCEL-CONFIRM-004）經本模組屬性 patch 全域時鐘；迴圈本體已搬 _timed_confirm
import time  # noqa: F401

from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.nlu import classify_intent
from myProgram.sales.states._timed_confirm import CANCEL_CONFIRM


def cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> bool:
    """跨層共用 cancel confirm 6s 子狀態（facade，委派 CANCEL_CONFIRM 單例）。

    Args:
        speak: callback(text: str) — 語音播放（非阻塞）
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        speak_and_wait: callback(text: str) — 同步阻塞 speak（為 None 時 fallback 到
            speak）；production wire-up 必傳，讓 6s budget 從 TTS 播完起算。

    Returns:
        True — 確認取消（YES keyword 命中 / silent timeout / 亂答耗盡 budget）
        False — 顧客 NO（NO keyword 命中）

    行為規約見 _timed_confirm.CancelConfirm（NO 先於 YES、亂答不重置、silent→取消）。
    """
    io = DialogIO(speak=speak, read_customer_input=read_customer_input, speak_and_wait=speak_and_wait)
    return CANCEL_CONFIRM.run(io)


def is_cancel_intent(response: str) -> bool:
    """簡單 wrapper：response 是否為「拒絕」intent（cross-L 通用偵測）。

    給 inner read 點（qty_followup / checkout_confirm 等）用，這些 read 點原本沒走
    classify_intent 主路徑（或走 normal/l3 mode 嚴格 reject 太狹隘）。

    用 mode="l4" 抓得最廣（含 _KEYWORDS_REJECT 通用 reject + strict-short）—
    L3 mode 嚴格 reject 只認 _KEYWORDS_REJECT_L3_STRICT，對 cross-L cancel 太狹隘
    （漏掉「不要」「不用」這類短詞）。
    """
    return classify_intent(response, mode="l4") == "拒絕"
