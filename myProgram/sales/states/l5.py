"""L5：謝謝惠顧（致謝層）。

對應規格書：resources/plans/業務程式邏輯規劃/L5.md

最簡單一層：無顧客互動 / 無分支 / 無 dispatcher。
純序列：mute_opencv → speak → clear_cart → read_customer_input（當純等待）→ return
"""

from myProgram.sales.constants import THANK_DELAY, L5_THANKS
from myProgram.sales import cart as cart_module


def run_l5(
    speak,
    do_action,
    mute_opencv,
    cart,
    read_customer_input,
) -> tuple:
    """L5 致謝層：最簡單一層，純序列動作，無顧客互動。

    進入時動作（依規格書 L5.md）：
        1. 立即啟動 OpenCV mute THANK_DELAY 秒（致謝屏蔽期）
        2. speak 致謝語音（L5_THANKS）
        3. 清空 cart（交易完成重置）
        4. 等 THANK_DELAY 秒（read_customer_input 當純等待用，忽略結果）
        5. 套用子例程 A 回 L1（return ("L1_via_subroutine_a", 0, 0)）

    Args:
        speak: callback(text: str) — 語音播放
        do_action: callback(name: str) — 動作（規格 TBD，stub no-op）
        mute_opencv: callback(seconds: float) — 屏蔽 OpenCV 偵測
        cart: 購物車 dict（L5 內清空）
        read_customer_input: callback(timeout: float) -> str | None
            B 類 refactor (2026-05-25)：原本 L5 接 sleep callback，改沿用 L2-L4 的
            read_customer_input(timeout=THANK_DELAY) 統一 callback 集合（B2）。
            L5 規格寫「3s 期間不接受任何顧客輸入」— 即使 read 收到回應也忽略，
            純當 sleep 用。

    Returns:
        ("L1_via_subroutine_a", 0, 0)
        （沿用 L4 三態 return tuple shape，loop_count + unclear_count reset 為 0）
    """
    # ENTRY-001：進入時立即屏蔽 OpenCV THANK_DELAY 秒
    mute_opencv(THANK_DELAY)

    # ENTRY-002：speak 致謝語音
    speak(L5_THANKS)

    # ENTRY-003：清空 cart（交易完成）
    cart_module.clear_cart(cart)

    # A-001：等 THANK_DELAY 秒（read_customer_input 當純等待，忽略回應）後套用子例程 A
    read_customer_input(timeout=THANK_DELAY)
    return ("L1_via_subroutine_a", 0, 0)
