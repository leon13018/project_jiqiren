"""意圖識別（S1 v2）— 純函式，可單獨單測。

職責：
    - 6 步判定優先序（規格書 L0「關鍵字白名單」段）
    - 數量解析（阿拉伯優先，中文映射，預設 1）
    - 各層共用的 classify_intent / parse_quantity 純函式

設計原則：
    - 無 IO、無 print、無副作用
    - 輸入字串 → 輸出意圖字串
    - 純函式，適合 BDD/TDD 切入點
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
# L2/L4 mode 不受影響，仍視一般 _KEYWORDS_REJECT 為拒絕。
_KEYWORDS_REJECT_L3_STRICT = ["我不要了", "不想買了", "取消購買", "退出", "不買了"]

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
_KEYWORDS_ICED_TEA = ["紅茶", "冰紅茶", "红茶", "冰红茶", "hong cha", "tea"]

_KEYWORDS_SCRATCH = ["刮刮樂", "刮刮乐", "刮刮", "彩券", "lottery", "scratch"]

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


# ============================================================
# 多商品解析（2026-05-25 加；B 方案 multi-product + 數量黏住對應商品）
# ============================================================

_PRODUCT_KEYWORD_TO_NAME: list = [
    # (keyword, product_name) — 順序：先試長詞後短詞，避免「冰紅茶」被「紅茶」短匹配吃掉
    # 商品關鍵字含簡體變體（2026-05-26 加；其他類別暫不支援簡體）
    ("冰紅茶", "冰紅茶"),
    ("冰红茶", "冰紅茶"),
    ("hong cha", "冰紅茶"),
    ("紅茶", "冰紅茶"),
    ("红茶", "冰紅茶"),
    ("tea", "冰紅茶"),
    ("刮刮樂", "刮刮樂"),
    ("刮刮乐", "刮刮樂"),
    ("彩券", "刮刮樂"),
    ("lottery", "刮刮樂"),
    ("scratch", "刮刮樂"),
    ("刮刮", "刮刮樂"),
]


def parse_products(text: str) -> list:
    """多商品解析（B 方案 — 2026-05-25 加）。

    從顧客輸入找出**所有**商品 mention，依出現順序排序，
    並把每個商品**後方視窗內**的數量黏住該商品（sticky-right）。

    視窗範圍：商品 keyword 結束位置 → 下個商品 keyword 起始位置（或文字結尾）。

    Args:
        text: 顧客輸入字串

    Returns:
        list of (product_name, qty_or_None) tuples，依出現順序排列。
        qty: int（有解析到）或 None（沒解析到 → caller 進 QTY 追問）
        無商品 → 返 []

        **Per-product dedup 規則（2026-05-25 加，使用者實機回報後修正）：**
        1. 同商品全部都**沒**數量 → 合併成一個 (product, None)（只追問一次）
        2. 同商品**至少一個有**數量 → 只保留有數量的 entries，無數量的丟棄
        3. 同商品**全部都有**數量 → 全部保留各自為獨立 entry（caller 累加）

    範例：
        "紅茶 1 刮刮樂 2"     → [("冰紅茶", 1), ("刮刮樂", 2)]
        "紅茶 刮刮樂"          → [("冰紅茶", None), ("刮刮樂", None)]
        "紅茶 1 刮刮樂"        → [("冰紅茶", 1), ("刮刮樂", None)]
        "想要紅茶 2 跟刮刮樂 1 謝謝" → [("冰紅茶", 2), ("刮刮樂", 1)]
        "今天天氣很好"         → []
        # Dedup 規則
        "刮刮樂 刮刮樂"        → [("刮刮樂", None)]              # 規則 1：合一
        "刮刮樂 3 刮刮樂"      → [("刮刮樂", 3)]                 # 規則 2：丟無數量
        "紅茶 2 紅茶 3"        → [("冰紅茶", 2), ("冰紅茶", 3)]  # 規則 3：累加 5 瓶
    """
    if not text:
        return []

    text_lower = text.lower()

    # 1. 找所有商品 keyword 出現位置（含重疊去重 — 「冰紅茶」涵蓋「紅茶」就跳過短的）
    found: list = []  # (start, end, product_name)
    occupied: list = []  # 已被佔據的字元位置區間 [(start, end), ...]

    for keyword, product in _PRODUCT_KEYWORD_TO_NAME:
        kw_lower = keyword.lower()
        pos = 0
        while True:
            idx = text_lower.find(kw_lower, pos)
            if idx == -1:
                break
            end = idx + len(keyword)
            # 若此區間與既有 occupied 重疊 → 跳過（避免「冰紅茶」被「紅茶」二度算）
            overlaps = any(not (end <= os or idx >= oe) for os, oe in occupied)
            if not overlaps:
                found.append((idx, end, product))
                occupied.append((idx, end))
            pos = end

    if not found:
        return []

    # 2. 依出現順序排序
    found.sort(key=lambda x: x[0])

    # 3. 對每個商品，視窗 = (keyword 結束) → (下個商品 keyword 起始)，找數量
    raw: list = []
    for i, (_start, end, product) in enumerate(found):
        window_end = found[i + 1][0] if i + 1 < len(found) else len(text)
        window = text[end:window_end]
        qty = _parse_quantity_in_window(window)
        raw.append((product, qty))

    # 4. Per-product dedup pass（見 docstring「Per-product dedup 規則」段）
    products_with_qty = {p for p, q in raw if q is not None}
    deduped: list = []
    seen_missing: set = set()
    for product, qty in raw:
        if product in products_with_qty:
            # 該商品有任何 qty 帶值 entry → 只保留有 qty 的（規則 2 + 3）
            if qty is not None:
                deduped.append((product, qty))
        else:
            # 該商品全部 None → 只保留首次（規則 1）
            if product not in seen_missing:
                deduped.append((product, None))
                seen_missing.add(product)

    return deduped


def _parse_quantity_in_window(window: str) -> int:
    """從一段視窗文字（單一商品的 qty 區間）解析數量。

    跟 parse_quantity 邏輯一致，但**沒命中時返 None**（讓 caller 進追問）
    而非預設 1。

    Returns:
        int qty 或 None（窗內無數字）。
    """
    arabic_matches = re.findall(r"\d+", window)
    for m in arabic_matches:
        n = int(m)
        if n > 0:
            return n
    for char, value in _CHINESE_DIGIT_MAP.items():
        if char in window:
            return value
    return None
