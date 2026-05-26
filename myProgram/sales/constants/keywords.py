"""關鍵字集常數（P8 拆分自 constants.py）。

包含：
    KEYWORDS_CONFIRM_YES / KEYWORDS_CONFIRM_YES_STRICT_SHORT
    KEYWORDS_CONFIRM_NO  / KEYWORDS_CONFIRM_NO_STRICT_SHORT
    HAWK_SLOGANS（叫賣話術）
    KEYWORDS_ICED_TEA / KEYWORDS_SCRATCH（商品 keyword；2026-05-26 Wave 6 從 nlu.py 搬移）
    CHINESE_DIGIT_MAP（中文數字映射；2026-05-26 Wave 6 從 nlu.py 搬移，資料層歸資料層）
"""

__all__ = [
    "HAWK_SLOGANS",
    "KEYWORDS_CONFIRM_YES",
    "KEYWORDS_CONFIRM_YES_STRICT_SHORT",
    "KEYWORDS_CONFIRM_NO",
    "KEYWORDS_CONFIRM_NO_STRICT_SHORT",
    "KEYWORDS_L4_ACK_OR_WAIT",
    "KEYWORDS_L4_ACK_SHORT",
    "KEYWORDS_WANT_TO_BUY_VAGUE",
    "KEYWORDS_WANT_TO_BUY_SHORT",
    "KEYWORDS_ICED_TEA",
    "KEYWORDS_SCRATCH",
    "CHINESE_DIGIT_MAP",
]

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

# ============================================================
# L4 結帳等掃碼期間顧客的「等待 / 安撫」詞（2026-05-26 加；使用者實機 UX 修補）
# L4 mode 專屬 — 同詞在 L2/L3 confirm 上下文有不同語意（如「好」在 C-2 = YES），
# 不應跨 mode 共享。
# ============================================================

# substring 集：較長的詞，substring match 安全
KEYWORDS_L4_ACK_OR_WAIT: list = [
    # 肯定 / 安撫類（長詞）
    "好的", "好啦", "好的沒問題", "沒問題", "沒事", "嗯嗯",
    # 等待類（HP-4 / C2：補入「等等」單詞，顧客找手機掃碼最常脫口的表達）
    "等等我", "等等", "等我", "稍等", "等一下", "馬上", "來了", "找一下",
    # 英文
    "okay",
    # 簡體變體
    "没问题", "没事", "稍等", "等一下", "马上", "来了", "找一下",
]

# strict-short 集：短單字 / 短英文，完全相等才算（避免 substring 誤命中：
# 「好」 substring 會中「好亂/好像」；「ok」會中「joker/poker」之類）
KEYWORDS_L4_ACK_SHORT: list = ["好", "嗯", "ok"]

# ============================================================
# L2 (DnC) / L3 (DyC) 顧客講肯定詞但未指定具體商品名的辨識（2026-05-26 加）
# 使用者實機回報：L3「請問還有額外需要購買的嗎？」顧客回「有」被誤判 unclear → UX 補強
# L2 + L3 通用 — 搭配 nlu.py classify_intent 內的 l2/normal mode 專屬分支使用
# ============================================================

# substring 集：較長詞，substring match 安全
KEYWORDS_WANT_TO_BUY_VAGUE: list = [
    # 繁體
    "想買", "想要", "需要", "我要", "我想",
    "還要", "還想", "想加買",
    # C18 (2026-05-26)：「好了/對了/好啊」— L2/L3 顧客肯定回應但未指定商品
    "好了", "對了", "好啊",
    # 簡體
    "想买", "还要", "还想", "想加买",
    "好了", "对了",  # 簡體（「好啊」繁簡相同）
]

# strict-short 集：短單字防 substring 誤命中（如「沒有」含「有」substring，「不要」含「要」substring）
# 「沒有」「不要」已在 REJECT / CHECKOUT 分支被攔截（排在「想買無商品」之前）
KEYWORDS_WANT_TO_BUY_SHORT: list = ["有", "要"]

# ============================================================
# 商品 keyword（2026-05-26 Wave 6 從 nlu.py 搬移；資料層歸資料層）
# 原底線命名（module-private）改為公開常數。
# ============================================================

# 冰紅茶關鍵字含簡體變體（2026-05-26 加）— 使用者 Windows 系統地區設為簡體，
# 偶爾會直接打簡體商品名（如「红茶」）；其他類別（YES/NO/拒絕/結帳）暫不支援簡體
# 2026-05-26 P4：移除短詞「tea」（substring 過短，「matter/retake/outreach」含 tea 易誤命中）
# 改為「iced tea」/「black tea」更具體英文，減少 STT noise 誤命中
KEYWORDS_ICED_TEA: list = [
    "紅茶", "冰紅茶", "红茶", "冰红茶",      # 繁簡
    "hong cha", "iced tea", "black tea",      # 拼音 + 具體英文
]

# 2026-05-26 P4：補「彩卷」（常見錯字）、「樂透/乐透」「即時樂/即时乐」常用同義
# 避免 demo 場景顧客講「樂透」「彩卷」fall through 到 unclear
KEYWORDS_SCRATCH: list = [
    "刮刮樂", "刮刮乐", "刮刮", "彩券", "彩卷",  # 「卷」是常見錯字
    "樂透", "乐透", "即時樂", "即时乐",            # 常用同義
    "lottery", "scratch",
]

# ============================================================
# 中文數字映射（含異體字）（2026-05-26 Wave 6 從 nlu.py 搬移；資料層歸資料層）
# ============================================================

CHINESE_DIGIT_MAP: dict = {
    "一": 1, "壹": 1,
    "兩": 2, "二": 2, "貳": 2,
    "三": 3, "參": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陸": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
    "十": 10, "拾": 10,
}
