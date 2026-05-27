"""L5：謝謝惠顧（致謝層）。

對應規格書：resources/plans/業務程式邏輯規劃/L5.md

最簡單一層：無顧客互動 / 無分支 / 無 dispatcher。
純序列：speak → clear_cart → sleep → return
"""

from myProgram.sales.constants import THANK_DELAY, L5_THANKS, ACTION_L5_FAREWELL
from myProgram.sales import cart as cart_module


def run_l5(
    speak,
    cart,
    sleep,
    do_action,
) -> tuple:
    """L5 致謝層：最簡單一層，純序列動作，無顧客互動。

    進入時動作（依規格書 L5.md）：
        1. speak 致謝語音（L5_THANKS）
        2. do_action(ACTION_L5_FAREWELL) — S3 同步揮手送客（2026-05-27 加）
        3. 清空 cart（交易完成重置）
        4. sleep THANK_DELAY 秒（純等待，不接受任何顧客輸入）
        5. 套用子例程 A 回 L1（return ("L1_via_subroutine_a", 0, 0)）

    Args:
        speak: callback(text: str) — 語音播放
        cart: 購物車 dict（L5 內清空）
        sleep: callback(seconds: float) — 純等待 seconds 秒（不接受任何顧客輸入）
            設計沿革：原本 L5 接 sleep；B2 refactor 一度改為 read_customer_input 並標
            「忽略輸入當 sleep 用」想統一 callback 集合，但 chat-driven S1 wire-up
            把 read_customer_input 實作為 blocking input()，違反規格「致謝期間不接受
            顧客輸入」本意 → 2026-05-25 revert B2 恢復獨立 sleep callback。S1 wire-up
            用真 time.sleep；S4+ 上 threading 時可改 worker thread sleep 不阻塞主迴圈。
        do_action: callback(name: str) — 同步阻塞跑廠商動作組（S3 加，2026-05-27）。
            L5 在 speak L5_THANKS 之後、clear_cart 之前觸發 ACTION_L5_FAREWELL
            （揮手送客）。同步阻塞至動作播完才 clear_cart + sleep，確保顧客看到
            完整揮手動作後再進入致謝靜默期。

    Returns:
        ("L1_via_subroutine_a", 0, 0)
        （沿用 L4 三態 return tuple shape，loop_count + unclear_count reset 為 0）
    """
    # ENTRY-002：speak 致謝語音
    speak(L5_THANKS)

    # S3：speak 致謝後跑揮手送客動作（在 clear_cart 之前 — 規格表明示順序）
    do_action(ACTION_L5_FAREWELL)

    # ENTRY-003：清空 cart（交易完成）
    cart_module.clear_cart(cart)

    # A-001：純等待 THANK_DELAY 秒（不接受任何顧客輸入）後套用子例程 A
    sleep(THANK_DELAY)
    return ("L1_via_subroutine_a", 0, 0)
