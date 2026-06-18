"""觸控上行命令 → 對話狀態機既有消費的 token 字串（純映射，Windows-TDD）。

職責：把瀏覽器送來的結構化命令 dict 翻成「機器人既有 read 路徑會處理的字串」，
經 web/app.py 的 WS receive 餵 input_reader.inject —— 對話層零改動、零新意圖碼。

純 stdlib（無 fastapi / pydantic / 副作用）；只 import sales 常數取 token 與商品驗證。
非法 / 未知命令一律回 None（caller 忽略，不 raise）。
"""
from myProgram.sales.constants import PRODUCTS

# 結帳 / 確認 token：對齊「實際消費路徑」的字（test 守行為，避免日後漂移）。
# 「結帳」→ classify_intent(.,"normal")="結帳"：L3 主迴圈 dispatch 走 nlu._KEYWORDS_CHECKOUT
#   （「結帳/帳」）；不是 C-2 子狀態的 KEYWORDS_C2_CHECKOUT（「結賬/賬」）——帳≠賬，
#   選錯字主路徑會落 unclear（2026-06-19 Pi 實測修正）。
# 「正確」∈ KEYWORDS_CONFIRM_YES（_dialog_checkout_confirm 走 KG_CONFIRM_YES 的 YES）。
_CHECKOUT_TOKEN = "結帳"
_CONFIRM_TOKEN = "正確"
# 模擬硬體觸發點（TerminalSim 約定，非 sales 領域常數）：
#   wake = 模擬 OpenCV 偵測顧客（read_terminal_key 認 'c' → L1 hawk→L2）
#   pay  = 模擬掃碼付款（read_customer_input 認 's' → L4→L5）
# 本專案目前無真 OpenCV / 掃碼器 → 這兩個就是實際觸發點。未來接真硬體時改這兩個
# 映射（與領域 token 解耦），對話層不受影響。
_WAKE_TOKEN = "c"
_PAY_TOKEN = "s"


def to_token(cmd):
    """結構化觸控命令 dict → token 字串；非法 / 未知 / 非 dict → None。"""
    if not isinstance(cmd, dict):
        return None
    ctype = cmd.get("type")
    if ctype == "wake":
        return _WAKE_TOKEN
    if ctype == "pay":
        return _PAY_TOKEN
    if ctype == "checkout":
        return _CHECKOUT_TOKEN
    if ctype == "confirm":
        return _CONFIRM_TOKEN
    if ctype == "order":
        item = cmd.get("item")
        qty = cmd.get("qty")
        if item not in PRODUCTS:
            return None
        # bool 是 int 子型別 → 明確排除，避免 True 被當 1
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            return None
        return f"{item}{qty}"
    return None
