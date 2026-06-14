"""商品實體解析（從 nlu.py 拉出，2026-05-26 P7）。

職責：
    - 多商品 + 數量區間綁定解析
    - 商品 keyword → 標準商品名 mapping

設計原則：
    - 純函式（無 IO / 無 callback）
    - 數量解析委派 nlu.parse_quantity(window, default=None)
      （W1 oop_w1：原 _parse_quantity_in_window 與 parse_quantity 合併，用 default 區分 fallback）
    - sales/ 內 caller（dialog / qty_followup）由此 import parse_products，
      不再從 nlu 拿

對外 public API：
    - parse_products(text) -> list[tuple[str, int | None]]
      回傳 (product_name, qty_or_None) 依出現順序排列
"""

from myProgram.sales.nlu import parse_quantity
from myProgram.sales.phonetic import phonetic_match
from myProgram.sales.constants import PRODUCTS, QTY_NUMBER_WORDS

# ============================================================
# 商品 keyword → 標準商品名映射（從 nlu.py 移過來）
# ============================================================

# (keyword, product_name) — 順序：先試長詞後短詞，避免「冰紅茶」被「紅茶」短匹配吃掉
# 2026-05-26 P4：移除「tea」短詞（substring 過短易誤命中）；補 iced tea / black tea
_PRODUCT_KEYWORD_TO_NAME: list = [
    ("冰紅茶", "冰紅茶"),
    ("hong cha", "冰紅茶"),
    ("iced tea", "冰紅茶"),
    ("black tea", "冰紅茶"),
    ("紅茶", "冰紅茶"),
    # 2026-05-26 P4：補「彩卷」錯字 + 「樂透」「即時樂」同義詞
    ("刮刮樂", "刮刮樂"),
    ("即時樂", "刮刮樂"),
    ("樂透", "刮刮樂"),
    ("彩券", "刮刮樂"),
    ("彩卷", "刮刮樂"),
    ("lottery", "刮刮樂"),
    ("scratch", "刮刮樂"),
    ("刮刮", "刮刮樂"),
]

# 預算 (kw_lower, kw_len, product)（perf_w1 F-3）：keyword 為 frozen 常數，
# 每呼叫重算 lower / len 是浪費。原表保留為單一事實來源。
_PRODUCT_KEYWORDS_PRE: list = [
    (keyword.lower(), len(keyword), product)
    for keyword, product in _PRODUCT_KEYWORD_TO_NAME
]


def parse_products(text: str) -> list:
    """多商品解析（B 方案 — 2026-05-25 加；2026-05-26 P7 移至 product_parser）。

    從顧客輸入找出**所有**商品 mention，依出現順序排序，
    並把每個商品**後方視窗內**的數量黏住該商品（sticky-right）。

    視窗範圍：商品 keyword 結束位置 → 下個商品 keyword 起始位置（或文字結尾）。

    Args:
        text: 顧客輸入字串

    Returns:
        list of (product_name, qty_or_None) tuples，依出現順序排列。
        qty: int（有解析到）或 None（沒解析到 → caller 進 QTY 追問）
        無商品 → 返 []

        **Per-product dedup 規則（2026-05-25 加，使用者實機回報後修正；
        2026-05-26 Wave 7a C22 規則 3 改覆寫）：**
        1. 同商品全部都**沒**數量 → 合併成一個 (product, None)（只追問一次）
        2. 同商品**至少一個有**數量 → 只保留有數量的 entries，無數量的丟棄
        3. 同商品**全部都有**數量 → 只保留**最後一個**帶 qty entry（覆寫；
           顧客修正語意 — 「紅茶 2 紅茶 3」= 改成 3 瓶，非累加 5 瓶）

    範例：
        "紅茶 1 刮刮樂 2"     → [("冰紅茶", 1), ("刮刮樂", 2)]
        "紅茶 刮刮樂"          → [("冰紅茶", None), ("刮刮樂", None)]
        "紅茶 1 刮刮樂"        → [("冰紅茶", 1), ("刮刮樂", None)]
        "想要紅茶 2 跟刮刮樂 1 謝謝" → [("冰紅茶", 2), ("刮刮樂", 1)]
        "今天天氣很好"         → []
        # Dedup 規則
        "刮刮樂 刮刮樂"        → [("刮刮樂", None)]   # 規則 1：合一
        "刮刮樂 3 刮刮樂"      → [("刮刮樂", 3)]      # 規則 2：丟無數量
        "紅茶 2 紅茶 3"        → [("冰紅茶", 3)]      # 規則 3：覆寫為最後一個 qty
    """
    if not text:
        return []

    text_lower = text.lower()

    # 1. 找所有商品 keyword 出現位置（含重疊去重 — 「冰紅茶」涵蓋「紅茶」就跳過短的）
    found: list = []  # (start, end, product_name)
    occupied: list = []  # 已被佔據的字元位置區間 [(start, end), ...]

    for kw_lower, kw_len, product in _PRODUCT_KEYWORDS_PRE:
        pos = 0
        while True:
            idx = text_lower.find(kw_lower, pos)
            if idx == -1:
                break
            end = idx + kw_len
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
        qty = parse_quantity(window, default=None)
        # ① 內嵌數量拼音糾錯（2026-06-14 Phase B，spec §2.1）：
        # 視窗解不出數量、但有實質內容時（如「紅茶商品」的「商品」=「三瓶」聽歪），
        # 在該 product 單位的合法量詞域 {一X…十X} 做拼音近音糾錯。
        # phonetic_match graceful（Windows 無 pypinyin → None）→ ① no-op，行為同今天。
        if qty is None and window.strip():
            unit = PRODUCTS[product]["單位"]
            corrected = phonetic_match(
                window.strip(), [w + unit for w in QTY_NUMBER_WORDS]
            )
            if corrected is not None:
                qty = parse_quantity(corrected)
        raw.append((product, qty))

    # 4. Per-product dedup pass（見 docstring「Per-product dedup 規則」段）
    products_with_qty = {p for p, q in raw if q is not None}
    deduped: list = []
    seen_missing: set = set()
    for product, qty in raw:
        if product in products_with_qty:
            # 該商品有任何 qty 帶值 entry → 只保留有 qty 的（規則 2 + 3）
            # C22 (2026-05-26 Wave 7a)：規則 3「全部都有 qty」改覆寫 —
            # 顧客修正語意「紅茶 2 紅茶 3」應視為改成 3 瓶（非累加 5 瓶）
            # 實作：先移除同商品既有 entry，再 append 新的，保留最後一個 qty
            if qty is not None:
                deduped = [(p, q) for p, q in deduped if p != product]
                deduped.append((product, qty))
        else:
            # 該商品全部 None → 只保留首次（規則 1）
            if product not in seen_missing:
                deduped.append((product, None))
                seen_missing.add(product)

    return deduped
