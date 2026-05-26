"""意圖識別（S1 v2）— 純函式，可單獨單測。

職責：
    - 6 步判定優先序（規格書 L0「關鍵字白名單」段）
    - 數量解析（阿拉伯優先，中文映射，預設 1）
    - 各層共用的 classify_intent / parse_quantity 純函式

設計原則：
    - 無 IO、無 print、無副作用
    - 輸入字串 → 輸出意圖字串
    - 純函式，適合 BDD/TDD 切入點

注意：
    商品實體解析（parse_products）已於 2026-05-26 P7 搬至
    myProgram/sales/product_parser.py。
    本模組保留 _KEYWORDS_ICED_TEA / _KEYWORDS_SCRATCH 供 classify_intent
    內部商品意圖識別使用；product_parser 由此 import 這兩個 keyword set。
"""

import re

# ============================================================
# 關鍵字白名單（依規格書 L0_共通.md）
# ============================================================

# REJECT substring 集（移除「沒/没」單字 → 移到 strict-short，避免「沒了/沒問題」誤命中）
# 「没」是簡體變體（U+6CA1，不同於繁體「沒」U+6C92）— 使用者 Windows IME 是簡體
_KEYWORDS_REJECT = [
    "不要", "不用", "不想", "不買", "不了", "沒有", "沒了", "不買了",
    "不买", "不想买", "不买了", "没有",  # 簡體變體
]

# REJECT strict-short 集（「沒/没」單字僅在完全等於時視為 reject，避免「沒了/沒問題」誤命中）
_KEYWORDS_REJECT_STRICT_SHORT = ["沒", "没"]

# L3 嚴格 reject 詞：L3 (normal mode) 中只有命中這幾個明確「整單作廢」意圖才視為拒絕
# 短詞 _KEYWORDS_REJECT (「不要」/「不用」/「不想」/「不買」) 在 L3 視為「不追加」→ 結帳
# 2026-05-25 加：使用者實測 L3 顧客講「不用」本意「不需要加購」（同 no/nope）。
# 2026-05-26 P4 補：「全部取消/都不要/整單取消/取消」等常見整單作廢表達 + 簡體變體
# L2/L4 mode 不受影響，仍視一般 _KEYWORDS_REJECT 為拒絕。
# 「取消」雖 substring 較短，但 L3 STRICT 是「整單作廢」的安全門，
# 顧客在 L3 講「取消」幾乎一定意指整單，false positive 風險低。
_KEYWORDS_REJECT_L3_STRICT = [
    # 繁體
    "我不要了", "不想買了", "取消購買", "退出", "不買了",
    "全部取消", "全部不要", "都不要", "都取消", "整單取消", "取消",
    # 簡體變體（使用者 Windows IME 是簡體，實機踩過簡體輸入）
    "整单取消", "不想买了", "取消购买", "不买了",
]

_KEYWORDS_THINK = ["等等", "等一下", "稍等", "想想", "考慮", "想一下", "hold on", "wait"]

# CHECKOUT substring 集（移除「no/nope/好了」短詞/歧義詞，避免 strict yes/no 子狀態衝突）
# 「沒了/沒有了」保留：包含較長的詞，substring match 不易誤命中其他情境
# 「no/nope/好了」移除：短詞，應由各 mode 呼叫端自行處理（l2/l4 mode 有 no→拒絕邏輯）
_KEYWORDS_CHECKOUT = [
    "結帳", "買單", "付款", "就這樣", "可以了",
    "沒了", "沒有了", "夠了",
    "结账", "买单", "付款", "就这样", "可以了", "没了", "没有了", "够了",  # 簡體變體
]

_KEYWORDS_SERVICE = ["客服", "聯絡", "聯繫", "contact", "服務"]

# 商品關鍵字含簡體變體（2026-05-26 加）— 使用者 Windows 系統地區設為簡體，
# 偶爾會直接打簡體商品名（如「红茶」）；其他類別（YES/NO/拒絕/結帳）暫不支援簡體
# 2026-05-26 P4：移除短詞「tea」（substring 過短，「matter/retake/outreach」含 tea 易誤命中）
# 改為「iced tea」/「black tea」更具體英文，減少 STT noise 誤命中
_KEYWORDS_ICED_TEA = [
    "紅茶", "冰紅茶", "红茶", "冰红茶",      # 繁簡
    "hong cha", "iced tea", "black tea",      # 拼音 + 具體英文
]

# 2026-05-26 P4：補「彩卷」（常見錯字）、「樂透/乐透」「即時樂/即时乐」常用同義
# 避免 demo 場景顧客講「樂透」「彩卷」fall through 到 unclear
_KEYWORDS_SCRATCH = [
    "刮刮樂", "刮刮乐", "刮刮", "彩券", "彩卷",  # 「卷」是常見錯字
    "樂透", "乐透", "即時樂", "即时乐",            # 常用同義
    "lottery", "scratch",
]

# 僅 L4 客服模式內生效
_KEYWORDS_CONTINUE = ["繼續", "接著", "繼續買", "繼續交易", "continue"]

_KEYWORDS_EXIT = ["退出", "取消", "離開", "算了", "不買了", "exit"]


def _contains_any(text: str, keywords: list) -> bool:
    """大小寫不敏感 substring match — 任一 keyword 出現在 text 內即命中。"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _equals_strict_short(text: str, keywords: list) -> bool:
    """嚴格相等比對（去頭尾空白 + 大小寫不敏感） — 給短單字 keyword 用，避免 substring 誤命中。"""
    return text.strip().lower() in [kw.lower() for kw in keywords]


def normalize_input(raw: str, max_length: int = 200) -> str:
    """IO 邊界統一 normalize — 對顧客語音 / 商家鍵盤輸入做最小消毒。

    處理：
    1. 截斷上限長度（預設 200 字），防 STT 雜訊 / 異常超長輸入造成 log 污染 + 比對緩慢
    2. 移除控制字元（\\x00-\\x08, \\x0b, \\x0c, \\x0e-\\x1f, \\x7f）— 保留 \\t / \\n / \\r
       由 caller .strip() 處理（避免破壞語意空白）
    3. 全形數字 → 半形（０-９ → 0-9），給 `response == "1" / "2" / "s"` 比對用
       Python re 模組的 \\d 預設匹配 Unicode digits（含全形）OK，但 == 字串比對不會自動轉

    用法（IO 邊界一次套用，sales/ 內部不必再次 normalize）：
        raw = input(...).strip()
        raw = normalize_input(raw)

    Args:
        raw: 原始輸入字串
        max_length: 截斷上限（預設 200；對話 use case 足夠）

    Returns:
        normalized 字串
    """
    # 1. 截斷
    text = raw[:max_length]
    # 2. 移除控制字元（保留 \t \n \r — 對話本身可能含換行）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # 3. 全形數字 → 半形
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return text


def classify_intent(text: str, mode: str = "normal") -> str:
    """對顧客輸入做意圖分類（層別語意感知）。

    優先序（先命中先返回）：
        L4 客服模式：繼續交易 → 退出交易（含 no/nope）→ 通用
        L2 / L4 模式：no / nope → 拒絕（覆寫 CHECKOUT 預設）→ 通用
        通用 / L3：拒絕 → 想一下 → 結帳（含 no/nope 當「沒了、不追加」）→ 客服 → 商品 → 無法判斷

    Args:
        text: 顧客輸入字串
        mode:
            - "normal"（預設，L3 用）：no / nope → 結帳意圖（語意「沒了，不追加」）
            - "l2"：no / nope → 拒絕（語意「不要 / 不需要」→ L2-A 退出）
            - "l4"：no / nope → 拒絕（語意「不要了 / 取消」→ L4-B 取消交易）
            - "l4_service"：含繼續/退出判定，no/nope → 退出交易

    Returns:
        意圖字串，例：「拒絕」 / 「想一下」 / 「結帳」 / 「客服」 /
                      「商品:冰紅茶」 / 「商品:刮刮樂」 / 「繼續交易」 / 「退出交易」 / 「無法判斷」
    """
    # L4 客服模式專用：繼續交易 / 退出交易（最高優先；含 no/nope 視為退出）
    if mode == "l4_service":
        # 否定 guard：排在 CONTINUE 前，避免「不繼續/不要繼續」substring 誤命中「繼續」
        if any(neg in text for neg in ["不繼續", "不要繼續", "別繼續", "停止"]):
            return "退出交易"
        if _contains_any(text, _KEYWORDS_CONTINUE):
            return "繼續交易"
        if _contains_any(text, _KEYWORDS_EXIT):
            return "退出交易"
        if _equals_strict_short(text, ["no", "nope"]):
            return "退出交易"

    # L2 / L4 模式：no / nope 強制視為拒絕（覆寫 _KEYWORDS_CHECKOUT 內的預設）
    # 2026-05-25 使用者實測層別語意：L2「沒需求」/ L4「不要了」皆是拒絕，只 L3「沒了」是結帳
    if mode in ("l2", "l4"):
        if _equals_strict_short(text, ["no", "nope"]):
            return "拒絕"

    # L3 (normal mode) 嚴格 reject 判定：只有命中 _KEYWORDS_REJECT_L3_STRICT 才視為拒絕
    # 一般 _KEYWORDS_REJECT 短詞「不要 / 不用 / 不想 / 不買」在 L3 視為「不追加」→ 結帳
    # 2026-05-25 加：使用者實測 L3 顧客講「不用」本意「不需要加購」（同 no/nope 在 L3 的處理）
    if mode == "normal":
        if _contains_any(text, _KEYWORDS_REJECT_L3_STRICT):
            return "拒絕"
        if _contains_any(text, _KEYWORDS_REJECT) or _equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT):
            return "結帳"

    # 通用優先序（L2/L4 走這 — L3 已在上面 early return）
    if _contains_any(text, _KEYWORDS_REJECT) or _equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT):
        return "拒絕"
    if _contains_any(text, _KEYWORDS_THINK):
        return "想一下"
    if _contains_any(text, _KEYWORDS_CHECKOUT):
        return "結帳"
    if _contains_any(text, _KEYWORDS_SERVICE):
        return "客服"
    if _contains_any(text, _KEYWORDS_ICED_TEA):
        return "商品:冰紅茶"
    if _contains_any(text, _KEYWORDS_SCRATCH):
        return "商品:刮刮樂"

    return "無法判斷"


# ============================================================
# 中文數字映射（含異體字）
# ============================================================

_CHINESE_DIGIT_MAP: dict = {
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


def has_quantity(text: str) -> bool:
    """判斷文字內是否含可解析的數量（阿拉伯或中文數字）。

    供 L2 / L3 鏈路 C 判定：若顧客講商品但未含數量，呼叫端追問「您要幾瓶/張？」。
    parse_quantity 對「無數量」會 fallback 為 1 — 本函數存在意義就是「區分顯式 1 vs 預設 1」。

    Returns:
        True 含數量；False 無。
    """
    if re.search(r"\d+", text):
        return True
    return any(char in text for char in _CHINESE_DIGIT_MAP)


def parse_quantity(text: str) -> int:
    """從顧客輸入解析商品數量。

    判定規則（依優先序）：
        1. 阿拉伯數字優先（re.findall 取第一個 >0 整數）
        2. 中文數字映射（依 _CHINESE_DIGIT_MAP）
        3. 以上皆無命中 → 預設 1

    Args:
        text: 顧客輸入字串

    Returns:
        數量整數，最小為 1
    """
    # 阿拉伯數字優先
    arabic_matches = re.findall(r"\d+", text)
    for m in arabic_matches:
        n = int(m)
        if n > 0:
            return n

    # 中文數字映射
    for char, value in _CHINESE_DIGIT_MAP.items():
        if char in text:
            return value

    # 預設
    return 1

