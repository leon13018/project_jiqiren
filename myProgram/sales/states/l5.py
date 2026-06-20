"""L5：謝謝惠顧（致謝層）。

對應規格書：resources/plans/業務程式邏輯規劃/L5.md

最簡單一層：無顧客互動 / 無分支 / 無 dispatcher。
純序列：do_action → clear_cart → sleep → return
（2026-06-15 結帳收尾語音合併後 L5 不再 speak，致謝語音已併入 L4 鏈路 A。）
"""

from myProgram.sales.constants import THANK_DELAY, ACTION_L5_FAREWELL
from myProgram.sales import cart as cart_module


def run_l5(
    cart,
    sleep,
    do_action,
) -> tuple:
    """L5 致謝層：最簡單一層，純序列動作，無顧客互動。

    進入時動作（2026-06-15 結帳收尾語音合併後）：
        1. do_action(ACTION_L5_FAREWELL) — 揮手送客（致謝語音已併入 L4 鏈路 A
           的 L4_A_PAY_SUCCESS_FAREWELL 單句，L5 不再 speak）
        2. 清空 cart（交易完成重置）
        3. sleep THANK_DELAY 秒（純等待，不接受任何顧客輸入）
        4. 回 L1 直接 hawk 連續叫賣（return ("L1_enter_hawk", 0, 0)）

    Args:
        cart: 購物車 dict（L5 內清空）
        sleep: callback(seconds: float) — 純等待 seconds 秒（不接受任何顧客輸入）
        do_action: callback(name: str) — 同步阻塞跑廠商動作組。L5 在 clear_cart
            之前觸發 ACTION_L5_FAREWELL（揮手送客），阻塞至動作播完才 clear_cart
            + sleep，確保顧客看到完整揮手後再進入致謝靜默期。

    Returns:
        ("L1_enter_hawk", 0, 0)
    """
    # S3：揮手送客動作（在 clear_cart 之前 — 規格表明示順序）
    do_action(ACTION_L5_FAREWELL)

    # ENTRY-003：清空 cart（交易完成）
    cart_module.clear_cart(cart)

    # A-001：純等待 THANK_DELAY 秒（不接受任何顧客輸入）後回 L1 直接 hawk
    sleep(THANK_DELAY)
    return ("L1_enter_hawk", 0, 0)
