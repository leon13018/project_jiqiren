"""關鍵字集常數（P8 拆分自 constants.py）。

包含：
    KEYWORDS_CONFIRM_YES / KEYWORDS_CONFIRM_YES_STRICT_SHORT
    KEYWORDS_CONFIRM_NO  / KEYWORDS_CONFIRM_NO_STRICT_SHORT
    HAWK_SLOGANS（叫賣話術）
    KEYWORDS_ICED_TEA / KEYWORDS_SCRATCH（商品 keyword；2026-05-26 Wave 6 從 nlu.py 搬移）
    CHINESE_DIGIT_MAP（中文數字映射；2026-05-26 Wave 6 從 nlu.py 搬移，資料層歸資料層）
"""

# C17 (2026-05-26 Wave 7a)：HAWK_SLOGANS 含價格 slogan 改 f-string 從 PRODUCTS 取，
# 避免改價時漏改文案。底線命名（module-private alias）避免 wildcard re-export 污染。
from myProgram.sales.constants.products import PRODUCTS as _PRODUCTS
# W1 oop_w1：KeywordGroup 雙集封裝（類別本體在 keyword_group.py，本檔只建配對實例）
from myProgram.sales.keyword_group import KeywordGroup

__all__ = [
    "HAWK_SLOGANS",
    "KEYWORDS_CONFIRM_YES",
    "KEYWORDS_CONFIRM_YES_STRICT_SHORT",
    "KEYWORDS_CONFIRM_NO",
    "KEYWORDS_CONFIRM_NO_STRICT_SHORT",
    "KEYWORDS_C2_CONTINUE",
    "KEYWORDS_C2_CONTINUE_STRICT_SHORT",
    "KEYWORDS_C2_CHECKOUT",
    "KEYWORDS_C2_CHECKOUT_STRICT_SHORT",
    "KEYWORDS_C2_CANCEL",
    "KEYWORDS_C2_CANCEL_STRICT_SHORT",
    "KEYWORDS_L4_ACK_OR_WAIT",
    "KEYWORDS_L4_ACK_SHORT",
    "KEYWORDS_WANT_TO_BUY_VAGUE",
    "KEYWORDS_WANT_TO_BUY_SHORT",
    "KEYWORDS_ICED_TEA",
    "KEYWORDS_SCRATCH",
    "CHINESE_DIGIT_MAP",
    "KEYWORDS_CANCEL_CONFIRM_YES",
    "KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT",
    "KEYWORDS_CANCEL_CONFIRM_NO",
    "KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT",
    "KEYWORDS_L4_C_CONFIRM_YES",
    "KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT",
    "KEYWORDS_L4_C_CONFIRM_NO",
    "KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT",
    "KEYWORDS_INVALID_QTY_CANCEL_TRIGGER",
    "KEYWORDS_INVALID_QTY_CONTINUE",
    "KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT",
    "KEYWORDS_INVALID_QTY_EXIT",
    "KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT",
    # W1 oop_w1：11 個 KeywordGroup 配對實例
    "KG_CONFIRM_YES",
    "KG_CONFIRM_NO",
    "KG_C2_CONTINUE",
    "KG_C2_CHECKOUT",
    "KG_C2_CANCEL",
    "KG_CANCEL_CONFIRM_YES",
    "KG_CANCEL_CONFIRM_NO",
    "KG_L4_C_CONFIRM_YES",
    "KG_L4_C_CONFIRM_NO",
    "KG_INVALID_QTY_CONTINUE",
    "KG_INVALID_QTY_EXIT",
]

# ============================================================
# 6 組叫賣術語（依 mod 6 輪替）
# ============================================================

HAWK_SLOGANS: list = [
    "歡迎光臨！冰紅茶冷飲、刮刮樂彩券，全場九折優惠！",
    # C17：含價格 slogan 用 f-string 從 PRODUCTS 取，避免改價漏改文案
    f"夏日炎炎，冰紅茶清涼一夏，只要 {_PRODUCTS['冰紅茶']['實際']} 元！",
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
#
# YES 設計新增（2026-05-29 user 列表擴充）：
#   substring：「沒有錯」— 既有「沒錯」substring 不 cover 三字版（"沒錯" not in "沒有錯"）
# user 列表中下列項已被既有 substring / strict_short 覆蓋（不重複列入）：
#   對/是/好 — strict_short 已有
#   是的/對的/好的/沒錯/正確 — substring 已有
#   沒錯哦/正確哦/非常正確/沒錯正確/正確答案/回答正確/對是的沒有錯 — 含既有 substring，會自動命中
# 跳過「對我」— 疑似 IME 簡轉繁 typo，中文無此說法
KEYWORDS_CONFIRM_YES: list = [
    # 繁體肯定詞
    "對的", "是的", "好的", "好啦", "確認", "確定", "沒錯", "沒有錯", "正確",
    # 2026-05-31 加：「對」+ 語助詞 family（Pi demo「對哦」「對呢」miss 修補）
    # 「對」單字仍在 strict_short 防 substring「不對」「對方」FP；明示加入帶語助詞 phrase 安全
    # 「沒錯/正確 + 語助詞」既有 substring「沒錯」/「正確」已 cover，無需擴展
    "對哦", "對呢", "對啊",
    # 結帳同義詞（繁體）— 顧客在 C-2 說「結帳/買單/付款」= 明確想結帳 = YES
    "結帳", "買單", "買帳", "付款",
    # 簡體變體
    "对的", "是的", "好的", "确认", "确定", "没错", "正确",
    "对哦", "对呢", "对啊",                  # 2026-05-31 簡體變體
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
#
# NO 設計新增（2026-05-29 user 列表擴充）：
#   substring：「怪怪的/是錯的/都錯/全部錯/有錯的」(明確負面 phrase，無 false positive 風險)
#   strict_short：「錯」單字 — 避免「沒錯/不錯/沒有錯」substring 誤命中，只完全等於才 hit NO
#   strict_short：「錯誤」— 同理避免「沒有錯誤/沒錯誤」substring 誤命中（FP 顧客錢包逆向）
#   strict_short：「不」單字 — 完全等於「不」才 hit NO，避免 substring 噪音
# user 列表中下列項已被既有 substring 覆蓋（不重複列入）：
#   不對哦/不是哦/數量不正確/數量不對/都不對 — 都被現有「不對/不正確/不是」substring 命中
KEYWORDS_CONFIRM_NO: list = [
    "不對", "不正確", "不是", "不行", "不要", "不用", "重來", "重新", "wrong",
    "怪怪的", "是錯的", "都錯", "全部錯", "有錯的",
    "不对", "不正确", "不是", "不行", "不要", "不用", "重来", "重新",  # 簡體變體
]

# NO strict-short 集（短單字/短英文，只在完全等於時命中）
KEYWORDS_CONFIRM_NO_STRICT_SHORT: list = ["no", "nope", "n", "否", "錯", "錯誤", "不"]

# ============================================================
# L3 C-2 第二段三選一意圖（2026-05-28 加）
# 取代既有 c2 用 CONFIRM_YES/NO 二元 — 改成「繼續選購 / 結帳 / 取消購買」明確三選一
# 解 Pi demo bug：顧客講「不要」（意圖：不要結帳、繼續逛）被當成「拒絕整單」清 cart
# 設計：單字 token（繼續 / 結 / 取消）substring 風險高（如「結束 / 繼續努力 / 取消會議」非結帳意圖）
#   → 用 strict-short 完全相等才命中
# ============================================================

# 繼續購物 — 顧客想繼續加單，不清 cart 重入 dialog 主迴圈
#
# 2026-05-30 擴 substring（Pi demo「繼續購買」 fall-through 修補）：
# 新增「繼續X」「再X」「想再X」三個 family；strict_short ["繼續"] 純字維持。
# 故意不加「還要」/「我還要」— substring 會誤命中「還要結帳」等
# CHECKOUT 意圖句（dispatch 順序 CONTINUE 在 CHECKOUT 前，FP 會吃掉正確意圖）。
# 故意不加「加買」—「不想加買」 substring 命中 CONTINUE 走錯方向
# （C-2 上下文罕見但 prudent 拒絕）。
KEYWORDS_C2_CONTINUE: list = [
    # 繁體 — 既有
    "繼續選購", "選購商品", "繼續選", "選商品", "先選購",
    # 繁體 — 繼續X類（2026-05-30 加）
    "繼續購買", "繼續買", "繼續加買", "繼續加購", "繼續挑", "繼續逛", "繼續看",
    # 繁體 — 再X類（2026-05-30 加）
    "再買", "再加", "再選", "再來", "再來一個", "再來一張",
    # 繁體 — 想再X類（2026-05-30 加）
    "還想買", "想再買", "我想再買",
    # 簡體變體（2026-05-30 加）
    "继续选购", "继续购买", "继续买", "再买", "再加",
]
KEYWORDS_C2_CONTINUE_STRICT_SHORT: list = ["繼續"]

# 結帳 — 顧客明確想結帳；經 _dialog_checkout_confirm 確認明細再進 L4
KEYWORDS_C2_CHECKOUT: list = [
    "結賬", "直接結賬", "幫我結賬", "進入結賬", "結賬吧", "那就結賬吧",
    "我想直接結賬", "我想要結賬", "先結賬", "我想先結賬好了",
]
KEYWORDS_C2_CHECKOUT_STRICT_SHORT: list = ["結"]

# 取消購買 — 顧客想離開，清 cart + 退 L1 hawk（reuse DialogSession.exit_a() 既有 helper）
#
# 2026-05-30 擴 substring（Pi demo「繼續購買」 fall-through 同類 sweep）：
# 補既有缺漏 — 顧客常講「取消購買」/「我要取消」/「想取消」/「我想取消」
# /「不想要了」這些都 miss（strict_short ["取消"] 純字 equals 不命中複合詞）。
# 既有 dispatch 順序 CANCEL → CONTINUE → CHECKOUT，CANCEL 排第一，
# 新加 substring 命中即刻走 DialogSession.exit_a()（清 cart 退 L1），不會 fall through。
KEYWORDS_C2_CANCEL: list = [
    # 繁體 — 既有
    "幫我取消購買", "幫我取消", "取消吧", "那就取消吧", "取消它",
    # 繁體 — 取消X類（2026-05-30 加）
    "取消購買", "我要取消", "想取消", "我想取消", "不想要了",
    # 簡體變體（2026-05-30 加）
    "取消购买", "我要取消", "想取消", "我想取消", "不想要了",
]
KEYWORDS_C2_CANCEL_STRICT_SHORT: list = ["取消"]

# ============================================================
# L4 結帳等掃碼期間顧客的「等待 / 安撫」詞（2026-05-26 加；使用者實機 UX 修補）
# L4 mode 專屬 — 同詞在 L2/L3 confirm 上下文有不同語意（如「好」在 C-2 = YES），
# 不應跨 mode 共享。
# ============================================================

# substring 集：較長的詞，substring match 安全
# 注意：「等一下」/「稍等」等詞也在 nlu._KEYWORDS_THINK 內（L2/L3 mode 視為「想一下」）。
# 在 L4 mode 內 classify_intent 先檢查本集合（line 170-174），故 L4「等一下」走「等待安撫」分支；
# L2/L3 mode 走 _KEYWORDS_THINK 返「想一下」。同字跨 mode 不同義，由 classify_intent 的
# 判定順序保證正確分流。未來加新 mode 時要主動決定「等一下」這類詞屬 ACK 還是 THINK。
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

# Python 3.7+ dict iteration 依插入順序，本 map 的 key 順序即為查找優先序：
# 例如「兩」排在「二」之前（兩者值都是 2，無實質差異）；「壹」排在「一」之前（同值差異）。
# nlu.parse_quantity 對單字中文數字逐字查找，遇到第一個命中的 key 即返回。
# 變更此 dict 的 key 順序會改變查找優先序，無 unit test 守護 — 變動需謹慎。
# Wave 3 新增的 _parse_compound_chinese 已支援複合（十/百），單字 fallback 才走此 map。
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

# ============================================================
# Cross-L cancel confirm 子狀態 YES / NO 關鍵字（2026-05-29 加）
# 跨 L2/L3/L4 任何 read 點偵測 cancel intent 後進 6s confirm 用。
#
# NO 必須先 check（caller 端固定順序）— 避免「不要取消」substring 含「取消」誤命中 YES。
# YES 含「取消」strict_short：顧客已在 confirm prompt context 內，「取消」獨立詞 = 重複確認；
# NO 含「繼續」/「不要」/「別」短詞 strict_short：明確拒絕取消、繼續交易。
# ============================================================

# YES substring 集（長詞，substring match 安全）
KEYWORDS_CANCEL_CONFIRM_YES: list = [
    # 繁體
    "是的", "沒錯", "沒錯的", "確認取消",
    "我想取消", "是的我想取消", "取消吧", "給我取消",
    "取消這次", "取消這次交易", "取消交易",
    # 簡體
    "我想取消", "取消这次", "取消这次交易", "取消交易",
    # 英文
    "yes cancel", "cancel it",
]

# YES strict-short 集（短詞，完全相等才命中）
# 「取消」單字：在 confirm context 內明確 = 重複確認取消
KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT: list = [
    "是", "對", "對的", "好", "好的", "取消", "yes",
]

# NO substring 集（長詞，substring match 安全）
# 必須先 check（防「不要取消」誤命中 YES「取消」substring）
KEYWORDS_CANCEL_CONFIRM_NO: list = [
    # 繁體
    "不要取消", "不想取消", "別取消", "別給我取消",
    "繼續交易", "我想繼續交易", "給我繼續交易",
    "不取消", "我不想取消",
    # 簡體
    "不要取消", "不想取消", "别取消",
    "继续交易", "我想继续交易",
]

# NO strict-short 集（短詞，完全相等才命中）
KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT: list = [
    "否", "不", "不要", "不想", "我不想", "別", "别", "繼續", "继续", "no",
]

# ============================================================
# L4 客服模式「請問是否繼續交易？」確認子狀態 YES / NO 關鍵字（2026-05-30 加）
# 取代舊版 mode="l4_service" classify_intent 路徑 — user 反饋舊 _KEYWORDS_CONTINUE /
# _KEYWORDS_EXIT 集太狹隘且 prompt 強迫顧客學「退出 / 繼續」術語。
# 設計：跟 KEYWORDS_CONFIRM_YES/NO 風格一致（substring + strict_short 分離），
# user 列出明確「是 / 否 / 不交易 / 取消」等。
#
# NO 必須先 check（caller 端固定順序）— 避免「不繼續交易」substring 含「繼續交易」
# 誤命中 YES。
# YES 含「繼續交易」substring + 「繼續」strict_short（防「繼續努力」substring 誤命中）。
# NO 含「取消交易」/「不繼續」substring + 「取消」/「不要」/「不」strict_short
# （防「沒錯/不錯」substring 誤命中）。
# ============================================================

# YES substring 集（長詞，substring match 安全）
KEYWORDS_L4_C_CONFIRM_YES: list = [
    "是的", "好的", "繼續交易",
]

# YES strict-short 集（短詞，完全相等才命中）
# 「繼續」單字在 service mode confirm context 內明確 = 繼續交易（無「繼續努力」之類 FP）
KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT: list = ["是", "好", "繼續"]

# NO substring 集（長詞，substring match 安全）
# 必須先 check（防「不繼續」substring 含「繼續」strict_short 誤命中 YES）
# user 列：不繼續 / 不交易 / 不要了 / 不交易了 / 不想了 / 不想要了 /
#         取消交易 / 取消吧 / 幫我取消 / 幫我取消交易
KEYWORDS_L4_C_CONFIRM_NO: list = [
    "不繼續", "不交易", "不要了", "不交易了", "不想了", "不想要了",
    "取消交易", "取消吧", "幫我取消", "幫我取消交易",
]

# NO strict-short 集（短詞，完全相等才命中）
# 「不要」單字明確（cart 已有商品，「不要」= 不要這次交易）
# 「不」單字 strict 防「不錯」「不過」substring 誤命中
# 「取消」單字 strict 防「取消購物車」之類 substring noise（雖實際罕見）
KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT: list = ["否", "不要", "不", "取消"]

# ============================================================
# 無效數量重問狀態鏈 keyword（2026-06-09 加；spec invalid_qty_reask）
# ============================================================

# 進二選一的廣義否定 trigger（補 is_cancel_intent 漏接的 bare「取消」「退出」）
KEYWORDS_INVALID_QTY_CANCEL_TRIGGER: list = [
    "取消", "不買", "不買了", "不要了", "不想買", "不想要了", "算了", "放棄", "退出",
    "不买", "不买了", "不想买", "不想要了", "放弃",
]
# 二選一 CONTINUE（取消這些商品繼續）— caller 先 check（保守：任何 取消/繼續 → 保 cart）
KEYWORDS_INVALID_QTY_CONTINUE: list = [
    "取消超量", "取消超過", "取消超量的商品", "取消超過的商品", "取消商品",
    "繼續交易", "繼續購買", "繼續", "取消",
    "继续交易", "继续",
]
KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT: list = ["繼續", "取消", "继续"]
# 二選一 EXIT（退出交易）— caller 後 check（純 退出/離開 才退）
KEYWORDS_INVALID_QTY_EXIT: list = [
    "退出", "直接退出", "退出交易", "直接退出交易", "離開", "离开",
]
KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT: list = ["退出", "離開", "离开"]

# ============================================================
# KeywordGroup 配對實例（W1 oop_w1）
# 每個實例封裝既有「substring 集 + strict-short 集」雙集，呼叫點改用 .matches(text)
# 取代 `contains_any(x, KW) or equals_strict_short(x, KW_STRICT)` 雙呼叫。
# 既有 list 常數全保留（test_constants 直接驗 list），KG_* 只是組合 view。
# ============================================================

KG_CONFIRM_YES = KeywordGroup(tuple(KEYWORDS_CONFIRM_YES), tuple(KEYWORDS_CONFIRM_YES_STRICT_SHORT))
KG_CONFIRM_NO = KeywordGroup(tuple(KEYWORDS_CONFIRM_NO), tuple(KEYWORDS_CONFIRM_NO_STRICT_SHORT))
KG_C2_CONTINUE = KeywordGroup(tuple(KEYWORDS_C2_CONTINUE), tuple(KEYWORDS_C2_CONTINUE_STRICT_SHORT))
KG_C2_CHECKOUT = KeywordGroup(tuple(KEYWORDS_C2_CHECKOUT), tuple(KEYWORDS_C2_CHECKOUT_STRICT_SHORT))
KG_C2_CANCEL = KeywordGroup(tuple(KEYWORDS_C2_CANCEL), tuple(KEYWORDS_C2_CANCEL_STRICT_SHORT))
KG_CANCEL_CONFIRM_YES = KeywordGroup(tuple(KEYWORDS_CANCEL_CONFIRM_YES), tuple(KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT))
KG_CANCEL_CONFIRM_NO = KeywordGroup(tuple(KEYWORDS_CANCEL_CONFIRM_NO), tuple(KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT))
KG_L4_C_CONFIRM_YES = KeywordGroup(tuple(KEYWORDS_L4_C_CONFIRM_YES), tuple(KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT))
KG_L4_C_CONFIRM_NO = KeywordGroup(tuple(KEYWORDS_L4_C_CONFIRM_NO), tuple(KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT))
KG_INVALID_QTY_CONTINUE = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_CONTINUE), tuple(KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT))
KG_INVALID_QTY_EXIT = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_EXIT), tuple(KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT))
