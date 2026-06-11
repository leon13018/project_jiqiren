"""跨層共用文案與設定值。

放這裡的常數：被 2+ L 層引用（避免歸到單一 L 層造成誤導）。
規範對應 review A7 — 2026-05-26 Wave 6 新增。
"""

__all__ = [
    "SERVICE_PHONE",
    "DIALOG_VAGUE_BUY_REASK",
    "CANCEL_CONFIRM_PROMPT",
    "CANCEL_DECLINED_NOTICE",
    "PRODUCT_CANCELLED_NOTICE_TEMPLATE",
    "MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE",
    "INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE",
    "INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE",
    "INVALID_QTY_ZERO_TEMPLATE",
    "INVALID_QTY_UNCLEAR_PREFIX",
    "INVALID_QTY_CANCEL_CONFIRM_PROMPT",
    "INVALID_QTY_TIMEOUT_REENTER_PREFIX",
    "INVALID_QTY_CANCEL_REENTER_PREFIX",
]

# 客服電話（L1 客服模式 / L4 客服模式 / qty followup 客服 trigger 等）
# 原位置：l1_text.py（Wave 6 移出 — 跨多層使用，應歸 shared）
SERVICE_PHONE: str = "0900-XXX-XXX"

# L2 (DnC) / L3 (DyC) 通用 — 顧客講肯定詞但無具體商品名 → 溫和引導
# 原位置：l3_text.py（Wave 6 移出 — L2 dispatch 也 import 使用，跨層性質應放 shared）
# 2026-05-30 反轉 Wave 7a C23：移除價格列表（user 反饋過於冗長，顧客已被 hawk slogans 告知價格）
DIALOG_VAGUE_BUY_REASK: str = "好的，請告訴我您想買的商品。"

# Cross-L cancel confirm 子狀態文案（2026-05-29 加）
# 跨 L2/L3/L4 任何 read 點偵測 cancel intent 後進 6s confirm
CANCEL_CONFIRM_PROMPT: str = "您是否想取消這次交易？6 秒後系統將自動取消"
CANCEL_DECLINED_NOTICE: str = "好的，繼續為您服務"

# qty_followup 4 個 skip 分支統一通知文案（2026-05-29 加）
# 對應 _qty_follow_up_sub_loop 內 timeout / 拒絕 / 結帳-as-skip / attempts cap 四路徑
# UX：speak 該通知 + caller 端 L2/L3 reask 構成完整「商品已取消、對話繼續」訊息
PRODUCT_CANCELLED_NOTICE_TEMPLATE: str = "商品{product}已幫您取消"

# 多商品（N>=2）cancel notice 用 count 格式取代逐項列名（2026-05-30 加）
# Pi demo 反饋：multi-product 逐項列「商品X，商品Y，...」太冗長 → 改 count
# N==1 仍用 PRODUCT_CANCELLED_NOTICE_TEMPLATE 保留商品名（顧客需知哪個被取消）
# 切換邏輯見 myProgram/sales/states/_l2_l3_qty_followup.py::format_cancel_prefix
MULTI_PRODUCT_CANCELLED_NOTICE_TEMPLATE: str = "有{count}項商品已幫您取消"

# 無效數量重問狀態鏈文案（2026-06-09 加；spec invalid_qty_reask）
# {remaining} = MAX_QTY_PER_ITEM - cart 既有量（cart 空時即 50）
INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE: str = "{product}目前最多只能選購 {remaining} {unit}，請重新說您想要的數量。"
# {products}「冰紅茶和刮刮樂」；{details}「50 瓶、50 張」（per-product remaining+unit 以「、」連）
INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE: str = "{products}目前最多只能各選購 {details}，請重新說您想要的數量。"
# zero 數量重問（2026-06-09；invalid_qty 一般化）。
# {items}「冰紅茶0瓶」/「冰紅茶0瓶、刮刮樂0張」（per-product「{product}0{unit}」以「、」連）
# {products}「冰紅茶」/「冰紅茶和刮刮樂」（_join_names）
INVALID_QTY_ZERO_TEMPLATE: str = "不好意思，系統不接受{items}這種數量，請重新說您想要的{products}的數量。"
INVALID_QTY_UNCLEAR_PREFIX: str = "不好意思，系統無法判斷您的回復。"
# 2026-06-09 一般化後也涵蓋 zero，「超量」字眼中性化
INVALID_QTY_CANCEL_CONFIRM_PROMPT: str = "請問您是想取消這些商品然後繼續交易，還是想直接退出交易？"
# reenter prefix 以全形「，」結尾，與當前層 entry prompt 合成單句 speak（UX pacing）
INVALID_QTY_TIMEOUT_REENTER_PREFIX: str = "由於您沒回應購買數量，請重新進選購，"
INVALID_QTY_CANCEL_REENTER_PREFIX: str = "好的已為您取消這些商品，"
