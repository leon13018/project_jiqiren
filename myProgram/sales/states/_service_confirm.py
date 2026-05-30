"""跨 L2/L3/L4 通用「客服進入點」確認 12s 子狀態 helper（2026-05-31 加；對齊 _cancel_confirm.py 對稱）。

User 要求 L4 客服 confirm pattern 推廣到 L2/L3 — 顧客講「客服」不再直接「印電話 + 重 speak entry」，
改為一次性 12s 決策子狀態：

    - print SERVICE_PHONE（終端顯示客服電話）
    - speak L4_C_CONFIRM_PROMPT_TEMPLATE「請問是否繼續交易？{seconds}秒後將自動取消交易。」
    - 一次性 L4_C_CONFIRM_TIMEOUT=12s wall-clock 決策
    - YES keyword → return "yes"（caller 回主迴圈）
    - NO keyword / silent / 12s 耗盡 → return "no"（caller 清 cart 退 L1）
    - 終端 "s"（僅 L4 caller 開 allow_scan=True）→ return "scan"（caller 進 L5）
    - 亂答 → speak L4_UNCLEAR_NOTICE + continue（不重置 12s budget，對齊主迴圈設計）

設計沿革：上輪 L4 二次重構（commit 2141e7e）建立 _l4_service_mode pattern；本輪抽 helper 讓
L2/L3 三個客服進入點（_dialog_main_loop / _dialog_dispatch_inner_l2 / _dialog_dispatch_inner_l3）
也用同一機制（user 反饋「L2/L3 客服都改和 L4 相同」）。

跟 _cancel_confirm.py 對稱（語意 inverse）：
    - cancel_confirm 問「是否取消」silent=取消（保守 default）
    - service_confirm 問「是否繼續」silent=取消（保守 default）
    - 兩者都「保守 default 取消」— UX 一致
"""

import time

from myProgram.sales.constants import (
    SERVICE_PHONE,
    L4_C_CONFIRM_TIMEOUT,
    L4_C_CONFIRM_PROMPT_TEMPLATE,
    L4_UNCLEAR_NOTICE,
    KEYWORDS_L4_C_CONFIRM_YES,
    KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT,
    KEYWORDS_L4_C_CONFIRM_NO,
    KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT,
)
from myProgram.sales.nlu import contains_any, equals_strict_short


def service_confirm(
    speak,
    print_terminal,
    read_customer_input,
    speak_and_wait=None,
    *,
    allow_scan: bool = False,
) -> str:
    """共用客服 confirm 12s 子狀態。

    Args:
        speak: callback(text: str) — 語音播放（非阻塞）
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        speak_and_wait: optional 阻塞 speak callback — wall-clock budget 從 TTS 播完才起算
            （production wire-up 必傳；None fallback 走 speak，不阻塞）
        allow_scan: 是否允許終端 "s" fast path（僅 L4 caller 傳 True；L2/L3 傳 False）

    Returns:
        "yes" — 顧客 YES keyword，caller 回主迴圈
        "no"  — 顧客 NO keyword / silent / 12s 耗盡，caller 清 cart 退 L1
        "scan" — 顧客終端 "s"（僅 allow_scan=True 才返回），caller 進 L5 處理
    """
    # print 電話 + speak_and_wait prompt 後算 deadline — 顧客拿到完整 12s budget
    # （不被 TTS 合成 / 播放時間吃掉）
    print_terminal(SERVICE_PHONE)
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    _speak_blocking(L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT))

    deadline = time.monotonic() + L4_C_CONFIRM_TIMEOUT
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "no"

        response = read_customer_input(timeout=remaining)
        if response is None:
            return "no"

        # 終端 "s" fast path（僅 L4 caller 啟用）
        if allow_scan and response == "s":
            return "scan"

        # NO 必須先 check（防「不繼續」substring 含「繼續」strict_short 誤命中 YES）
        if (
            contains_any(response, KEYWORDS_L4_C_CONFIRM_NO)
            or equals_strict_short(response, KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT)
        ):
            return "no"

        if (
            contains_any(response, KEYWORDS_L4_C_CONFIRM_YES)
            or equals_strict_short(response, KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT)
        ):
            return "yes"

        # 亂答 → speak unclear notice + continue（不重置 12s budget，對齊主迴圈設計）
        speak(L4_UNCLEAR_NOTICE)
