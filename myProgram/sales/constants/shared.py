"""跨層共用文案與設定值。

放這裡的常數：被 2+ L 層引用（避免歸到單一 L 層造成誤導）。
規範對應 review A7 — 2026-05-26 Wave 6 新增。
"""

# C23 (2026-05-26 Wave 7a)：DIALOG_VAGUE_BUY_REASK 加價格資訊；
# 用 f-string 從 PRODUCTS 取，避免改價時漏改文案。
# 底線命名（module-private alias）避免 wildcard re-export 污染。
from myProgram.sales.constants.products import PRODUCTS as _PRODUCTS

__all__ = ["SERVICE_PHONE", "DIALOG_VAGUE_BUY_REASK"]

# 客服電話（L1 客服模式 / L4 客服模式 / qty followup 客服 trigger 等）
# 原位置：l1_text.py（Wave 6 移出 — 跨多層使用，應歸 shared）
SERVICE_PHONE: str = "0900-XXX-XXX"

# L2 (DnC) / L3 (DyC) 通用 — 顧客講肯定詞但無具體商品名 → 溫和引導
# 原位置：l3_text.py（Wave 6 移出 — L2 dispatch 也 import 使用，跨層性質應放 shared）
# 2026-05-26 Wave 7a C23：加價格資訊，讓顧客知道單價方便決策
DIALOG_VAGUE_BUY_REASK: str = (
    f"好的，請告訴我您想買的商品 — "
    f"冰紅茶（{_PRODUCTS['冰紅茶']['實際']} 元/瓶）"
    f"或刮刮樂（{_PRODUCTS['刮刮樂']['實際']} 元/張）"
)
