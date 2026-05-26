"""關鍵字集常數（P8 拆分自 constants.py）。

包含：
    KEYWORDS_CONFIRM_YES / KEYWORDS_CONFIRM_YES_STRICT_SHORT
    KEYWORDS_CONFIRM_NO  / KEYWORDS_CONFIRM_NO_STRICT_SHORT
    HAWK_SLOGANS（叫賣話術）
"""

# ============================================================
# 6 組叫賣術語（依 mod 6 輪替）
# ============================================================

HAWK_SLOGANS: list = [
    "歡迎光臨！冰紅茶冷飲、刮刮樂彩券，全場九折優惠！",
    "夏日炎炎，冰紅茶清涼一夏，只要 27 元！",
    "刮刮樂彩券，刮出好運氣，今天可能就是你的幸運日！",
    "歡迎進來看看，全場商品九折優惠中！",
    "老闆推薦：冰紅茶配刮刮樂，解渴又有趣！",
    "路過別錯過，超值優惠在這裡！",
]

# ============================================================
# Confirm 子狀態 YES / NO keyword
# （2026-05-26 重構：拆 substring 集 + strict-short 集）
# ============================================================

# YES substring 集（長詞，substring match 安全；不含「好/是/對」單字 → 移到 strict-short）
# 加入結帳同義詞（取代舊版 classify_intent==結帳 條件，讓 C-2 第二段「說結帳」仍可觸發 YES）
KEYWORDS_CONFIRM_YES: list = [
    # 繁體肯定詞
    "對的", "是的", "好的", "好啦", "確認", "確定", "沒錯", "正確",
    # 結帳同義詞（繁體）— 顧客在 C-2 說「結帳/買單/付款」= 明確想結帳 = YES
    "結帳", "買單", "買帳", "付款",
    # 簡體變體
    "对的", "是的", "好的", "确认", "确定", "没错", "正确",
    "结账", "买单", "付款",
    # 英文
    "yes", "yeah", "correct", "okay",
]

# YES strict-short 集（短單字，只在 response.strip().lower() 完全等於時命中）
# 理由：「好」substring 會誤命中「好亂/好像不對」；strict-short 消除 false positive
KEYWORDS_CONFIRM_YES_STRICT_SHORT: list = ["好", "是", "對", "对", "嗯", "ok", "y"]

# NO substring 集（長詞或常見短拒絕詞，substring match）
# 移除項目說明：
#   「錯」→ substring 誤命中「沒錯/不錯」（false positive）
#   「改」→ 語意歧義，不代表明確取消
#   「沒有」→ 歧義（"沒有問題" = 沒問題 = 同意）
#   「沒了」→ 在 C-2「是否結帳」語意是「要結帳、沒別的了」而非取消（逆向錯誤）
# 保留「不要/不用」— C-2 上下文顧客說「不要/不用結帳」是明確拒絕，非歧義詞
KEYWORDS_CONFIRM_NO: list = [
    "不對", "不正確", "不是", "不行", "不要", "不用", "重來", "重新", "wrong",
    "不对", "不正确", "不是", "不行", "不要", "不用", "重来", "重新",  # 簡體變體
]

# NO strict-short 集（短單字/短英文，只在完全等於時命中）
KEYWORDS_CONFIRM_NO_STRICT_SHORT: list = ["no", "nope", "n", "否"]
