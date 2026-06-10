"""跨 L2/L3/L4 通用「客服進入點」確認 24s 子狀態 helper（2026-05-31 加；W3 facade 化）。

User 要求 L4 客服 confirm pattern 推廣到 L2/L3 — 顧客講「客服」改為一次性 24s 決策子狀態。
service_confirm 現為 facade，依 allow_scan 委派 _timed_confirm.SERVICE_CONFIRM_SCAN（L4）/
SERVICE_CONFIRM（L2/L3）單例執行 wall-clock 骨架（行為規約：scan 最先、NO 先於 YES、
亂答 speak L4_UNCLEAR_NOTICE 不重置、timeout/silent→"no"，見 _timed_confirm）。

跟 _cancel_confirm.py 對稱（語意 inverse）：兩者都「保守 default 取消」— UX 一致。
"""

# 保留 import time：既有測試（SERVICE-CONFIRM-008）經本模組屬性 patch 全域時鐘；迴圈本體已搬 _timed_confirm
import time  # noqa: F401

from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.states._timed_confirm import SERVICE_CONFIRM, SERVICE_CONFIRM_SCAN


def service_confirm(
    speak,
    print_terminal,
    read_customer_input,
    speak_and_wait=None,
    *,
    allow_scan: bool = False,
) -> str:
    """共用客服 confirm 24s 子狀態（facade，依 allow_scan 委派對應單例）。

    Args:
        speak: callback(text: str) — 語音播放（非阻塞）
        print_terminal: callback(text: str) — 印終端
        read_customer_input: callback(timeout: float) -> str | None — 等顧客回應
        speak_and_wait: optional 阻塞 speak callback — wall-clock budget 從 TTS 播完才起算
            （production wire-up 必傳；None fallback 走 speak，不阻塞）
        allow_scan: 是否允許終端 "s" fast path（僅 L4 caller 傳 True；L2/L3 傳 False）

    Returns:
        "yes" — 顧客 YES keyword，caller 回主迴圈
        "no"  — 顧客 NO keyword / silent / 24s 耗盡，caller 清 cart 退 L1
        "scan" — 顧客終端 "s"（僅 allow_scan=True 才返回），caller 進 L5 處理
    """
    io = DialogIO(
        speak=speak, read_customer_input=read_customer_input,
        print_terminal=print_terminal, speak_and_wait=speak_and_wait,
    )
    return (SERVICE_CONFIRM_SCAN if allow_scan else SERVICE_CONFIRM).run(io)
