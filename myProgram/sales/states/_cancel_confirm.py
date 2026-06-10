"""跨 L2/L3/L4 通用「取消交易」確認 6s 子狀態 helper（2026-05-29 加）。

User 要求 L2/L3/L4 任何 read 點偵測到 cancel intent 後進 6s confirm（不再直接退 L1）。
timeout / 亂答耗盡 budget → YES（取消），跟 _dialog_c2_second_stage 相同 wall-clock pattern。

設計：
    - speak CANCEL_CONFIRM_PROMPT + wall-clock budget CANCEL_CONFIRM_TIMEOUT (6s)
    - YES keyword 命中立即 return True
    - NO keyword 先 check（避免「不要取消」substring 含「取消」誤命中 YES）
    - 亂答消耗 budget 不重置（避免無限延長）
    - budget 耗盡 / silent → True（user 字面 promise「6 秒後系統將自動取消」）

對應 is_cancel_intent helper：caller 端先用 is_cancel_intent 偵測 reject intent，
再 call cancel_confirm 取得是否真要取消。
"""

import time

from myProgram.sales.constants import (
    CANCEL_CONFIRM_TIMEOUT,
    CANCEL_CONFIRM_PROMPT,
    KG_CANCEL_CONFIRM_YES,
    KG_CANCEL_CONFIRM_NO,
)
from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.nlu import classify_intent


def cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> bool:
    """跨層共用 cancel confirm 6s wall-clock budget 子狀態。

    Args:
        speak: callback(text: str) — 語音播放（非阻塞）
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        speak_and_wait: callback(text: str) — 同步阻塞 speak（2026-05-30 v2 加）。
            為 None 時 fallback 到 speak（向後兼容既有測試）；production wire-up
            必須傳真實 callback，讓 6s budget 從 TTS 播完起算（不被 synth/play
            時間吃掉）— 這是 user 已對齊的「從 speak 播完起算」semantic。

    Returns:
        True — 確認取消（YES keyword 命中 / silent timeout / 亂答耗盡 budget）
        False — 顧客 NO（NO keyword 命中）

    設計：跟 _dialog_c2_second_stage 相同 wall-clock pattern：
        - NO 先 check（保守：避免「不要取消」誤命中 YES「取消」substring）
        - YES/NO keyword 命中立即 return
        - 亂答消耗 budget 不重置（避免無限延長）
        - budget 耗盡 / silent → True（user 字面 promise）
    """
    # W2：凍結簽名不動，體內建 io 束（fallback 三元式改用 io.speak_blocking）
    io = DialogIO(speak=speak, read_customer_input=read_customer_input, speak_and_wait=speak_and_wait)
    # 2026-05-30 v2：speak_and_wait CANCEL_CONFIRM_PROMPT 後算 deadline — 顧客拿到
    # 完整 CANCEL_CONFIRM_TIMEOUT (6s) budget，而非「6s 減 prompt 播放時間」
    io.speak_blocking(CANCEL_CONFIRM_PROMPT)
    deadline = time.monotonic() + CANCEL_CONFIRM_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # 倒數歸零（亂答耗盡 budget）→ 取消
            return True

        response = io.read_customer_input(timeout=remaining)
        if response is None:
            # silent（read 直接 timeout）→ 取消
            return True

        # NO 先 check（保守：避免「不要取消」誤命中 YES「取消」substring）
        if KG_CANCEL_CONFIRM_NO.matches(response):
            return False

        if KG_CANCEL_CONFIRM_YES.matches(response):
            return True

        # 亂答 → continue 消耗 budget（不重置 deadline，不 speak 提示）
        continue


def is_cancel_intent(response: str) -> bool:
    """簡單 wrapper：response 是否為「拒絕」intent（cross-L 通用偵測）。

    給 inner read 點（qty_followup / checkout_confirm 等）用，這些 read 點原本沒走
    classify_intent 主路徑（或走 normal/l3 mode 嚴格 reject 太狹隘）。

    用 mode="l4" 抓得最廣（含 _KEYWORDS_REJECT 通用 reject + strict-short）—
    L3 mode 嚴格 reject 只認 _KEYWORDS_REJECT_L3_STRICT，對 cross-L cancel 太狹隘
    （漏掉「不要」「不用」這類短詞）。
    """
    return classify_intent(response, mode="l4") == "拒絕"
