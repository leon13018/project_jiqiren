"""商品實體解析（從 nlu.py 拉出，2026-05-26 P7）。

職責：
    - 多商品 + 數量解析（統一 token-parser，2026-06-15 重寫）
    - 商品 keyword → 標準商品名 mapping

設計原則：
    - 純函式（無 IO / 無 callback）
    - 數量解析委派 nlu.parse_quantity / nlu.find_quantity_spans
    - sales/ 內 caller（dialog / qty_followup）由此 import parse_products，
      不再從 nlu 拿

對外 public API：
    - parse_products(text) -> list[tuple[str, int | None]]
      回傳 (product_name, qty_or_None) 依出現順序排列

2026-06-15 統一 token-parser 重寫（spec unified_product_parser）：
    原 4 拼湊機制（sticky-right / ② leading / Phase B split / ① window）無法 compose
    「任意順序 + 多商品 + garbled 品名/數量」。改為 token 化（精確商品 + 數量 +
    garbled 品名 span）後鄰近綁定的統一解法。dedup 規則 1/2/3 原樣保留。
    _PRODUCT_PHONETIC_CANDIDATES / _product_group 由 l2_l3_dialog 移入此檔
    （破循環 import — parse_products 內需用 garbled 品名糾錯）。
"""

from myProgram.sales.nlu import parse_quantity, find_quantity_spans
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


# ============================================================
# garbled 品名拼音糾錯候選（2026-06-15 從 l2_l3_dialog 移入，破循環 import）：
# 商品名整個被 ASR 聽歪（刮樂/尬尬樂→刮刮樂、茶→紅茶）→ 在商品候選域拼音近音糾錯。
# 候選須全部可被 parse_products 解析（_product_group 依賴）；擴充候選時務必確認。
# l2_l3_dialog ② 出口改 import 此二者（移出後）。
# ============================================================
_PRODUCT_PHONETIC_CANDIDATES = ("冰紅茶", "紅茶", "刮刮樂")


def _product_group(s):
    """候選分組鍵：同商品多 surface（冰紅茶 / 紅茶 皆指冰紅茶）不互壓歧義閥 margin。

    防線（2026-06-14 採納反思 product-group-unguarded-empty-parse）：候選若不可
    parse_products（回空 list）→ 回原字串 fallback，避免 `[0]` IndexError 炸 session。
    """
    result = parse_products(s)
    return result[0][0] if result else s


def _find_product_spans(text: str) -> list:
    """精確商品 span：沿用 _PRODUCT_KEYWORDS_PRE 比對 + 重疊去重。

    Returns:
        [(start, end, product), ...]（未排序；caller 與其他 token 一起排）。
    """
    text_lower = text.lower()
    found: list = []        # (start, end, product)
    occupied: list = []     # 已被佔據的字元位置區間 [(start, end), ...]
    for kw_lower, kw_len, product in _PRODUCT_KEYWORDS_PRE:
        pos = 0
        while True:
            idx = text_lower.find(kw_lower, pos)
            if idx == -1:
                break
            end = idx + kw_len
            # 與既有 occupied 重疊 → 跳過（避免「冰紅茶」被「紅茶」二度算）
            overlaps = any(not (end <= os or idx >= oe) for os, oe in occupied)
            if not overlaps:
                found.append((idx, end, product))
                occupied.append((idx, end))
            pos = end
    return found


def _remaining_gaps(text: str, spans: list) -> list:
    """扣掉已佔用 span 後的剩餘連續區段（gap）。

    Args:
        spans: [(start, end), ...]（商品 span + 數量 span 的位置）。

    Returns:
        [(start, end, substring), ...]，跳過純空白 gap（strip 後為空）。
    """
    occupied = sorted((s, e) for s, e in spans)
    gaps: list = []
    cursor = 0
    for s, e in occupied:
        if s > cursor:
            seg = text[cursor:s]
            if seg.strip():
                gaps.append((cursor, s, seg))
        cursor = max(cursor, e)
    if cursor < len(text):
        seg = text[cursor:]
        if seg.strip():
            gaps.append((cursor, len(text), seg))
    return gaps


def parse_products(text: str) -> list:
    """多商品 / 數量統一 token-parser（2026-06-15 重寫，spec unified_product_parser §2.1）。

    從顧客輸入找出**所有**商品 mention（精確 + garbled 品名），定位所有數量段，
    依位置鄰近綁定，回 (product_name, qty_or_None) 依出現順序。

    八步（spec §2.1）：
        1. 精確商品 span（_PRODUCT_KEYWORDS_PRE + 重疊去重）。
        2. 數量 span（find_quantity_spans；數量字集與商品字天然不重疊）。
        3. garbled 品名 span：扣商品 + 數量後的剩餘 gap，phonetic_match 商品候選域
           命中即 garbled 商品；未命中 gap 收進 unused_gaps（graceful：無 pypinyin→None）。
        4. 排序所有 token（商品[精確/garbled] + 數量）依 start。
        5. 鄰近綁定：每個數量綁「最近的前一個未綁商品」；無則「最近的後一個未綁商品」。
        6. garbled 數量（保 ①）：仍未綁商品 → 緊鄰未用 gap（先右後左）對該商品單位的
           合法量詞域 phonetic_match → 命中即綁（含 2.0 tie-break，解 紅茶食品→×10）。
        7. 組 raw：商品依位置序，各帶綁定 qty 或 None。
        8. per-product dedup：原樣 port 規則 1/2/3。

    Returns:
        list of (product_name, qty_or_None) tuples，依出現順序排列。
        qty: int（含顯式 0）或 None（沒解析到 → caller 進 QTY 追問）。無商品 → []。

        **Per-product dedup 規則（2026-05-25 加；2026-05-26 Wave 7a C22 規則 3 改覆寫）：**
        1. 同商品全部都**沒**數量 → 合併成一個 (product, None)（只追問一次）
        2. 同商品**至少一個有**數量 → 只保留有數量的 entries，無數量的丟棄
        3. 同商品**全部都有**數量 → 只保留**最後一個**帶 qty entry（覆寫；
           顧客修正語意 — 「紅茶 2 紅茶 3」= 改成 3 瓶，非累加 5 瓶）

    範例：
        "紅茶 1 刮刮樂 2"          → [("冰紅茶", 1), ("刮刮樂", 2)]
        "五張刮刮樂三瓶紅茶"        → [("刮刮樂", 5), ("冰紅茶", 3)]
        "三瓶紅茶兩張刮刮樂"        → [("冰紅茶", 3), ("刮刮樂", 2)]
        "紅茶 刮刮樂"              → [("冰紅茶", None), ("刮刮樂", None)]
        "今天天氣很好"             → []
        # Dedup 規則
        "刮刮樂 刮刮樂"            → [("刮刮樂", None)]   # 規則 1：合一
        "刮刮樂 3 刮刮樂"          → [("刮刮樂", 3)]      # 規則 2：丟無數量
        "紅茶 2 紅茶 3"           → [("冰紅茶", 3)]      # 規則 3：覆寫為最後一個 qty
    """
    if not text:
        return []

    # 1. 精確商品 span
    product_spans = _find_product_spans(text)

    # 2. 數量 span（值已 parse_quantity；數量字集與商品字不重疊）
    qty_spans = find_quantity_spans(text)

    # 3. garbled 品名 span：扣商品 + 數量後的剩餘 gap，phonetic_match 商品候選域。
    occupied_spans = [(s, e) for s, e, _ in product_spans] + [
        (s, e) for s, e, _ in qty_spans
    ]
    garbled_spans: list = []     # (start, end, product)
    unused_gaps: list = []       # (start, end) 未命中商品的 gap，留給 step 6 數量糾錯
    for gs, ge, seg in _remaining_gaps(text, occupied_spans):
        corrected = phonetic_match(
            seg.strip(), _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group
        )
        if corrected is not None:
            garbled_spans.append((gs, ge, _product_group(corrected)))
        else:
            unused_gaps.append((gs, ge))

    if not product_spans and not garbled_spans:
        return []

    # 4. 排序所有 token（商品 + 數量）依 start。
    #    商品 token：(start, end, 'PROD', product)；數量 token：(start, end, 'QTY', value)。
    prod_tokens = [
        (s, e, "PROD", p) for s, e, p in (product_spans + garbled_spans)
    ]
    qty_tokens = [(s, e, "QTY", v) for s, e, v in qty_spans]
    tokens = sorted(prod_tokens + qty_tokens, key=lambda t: t[0])

    # 商品綁定狀態：依出現位置序的商品索引 → [start, end, product, qty]
    products = [
        [s, e, p, None]
        for s, e, kind, p in tokens
        if kind == "PROD"
    ]

    def _bind_qty(qty_start: int, value) -> None:
        """數量綁「最近的前一個未綁商品」；無則「最近的後一個未綁商品」（spec step 5）。"""
        # 前一個未綁商品（start < qty_start，取最靠近者 = start 最大者）
        prev = [p for p in products if p[0] < qty_start and p[3] is None]
        if prev:
            target = max(prev, key=lambda p: p[0])
        else:
            # 後一個未綁商品（start > qty_start，取最靠近者 = start 最小者）
            nxt = [p for p in products if p[0] > qty_start and p[3] is None]
            if not nxt:
                return
            target = min(nxt, key=lambda p: p[0])
        target[3] = value

    # 5. 鄰近綁定：依位置序逐數量綁定。
    for s, _e, kind, v in tokens:
        if kind == "QTY":
            _bind_qty(s, v)

    # 6. garbled 數量（保 ①）：仍未綁商品 → 緊鄰未用 gap（先右後左）對該商品單位
    #    合法量詞域 phonetic_match → 命中即綁（含 2.0 tie-break，解 紅茶食品→×10）。
    used_gaps: set = set()
    for p in products:
        if p[3] is not None:
            continue
        unit = PRODUCTS[p[2]]["單位"]
        # 緊鄰右 gap（gap.start == product.end），其次緊鄰左 gap（gap.end == product.start）
        adj = None
        for i, (gs, ge) in enumerate(unused_gaps):
            if i in used_gaps:
                continue
            if gs == p[1]:
                adj = i
                break
        if adj is None:
            for i, (gs, ge) in enumerate(unused_gaps):
                if i in used_gaps:
                    continue
                if ge == p[0]:
                    adj = i
                    break
        if adj is None:
            continue
        gs, ge = unused_gaps[adj]
        corrected = phonetic_match(
            text[gs:ge].strip(), [w + unit for w in QTY_NUMBER_WORDS]
        )
        if corrected is not None:
            p[3] = parse_quantity(corrected)
            used_gaps.add(adj)

    # 7. 組 raw：商品依位置序 (product, qty)。
    raw: list = [(p[2], p[3]) for p in products]

    # 8. Per-product dedup pass（原樣 port 規則 1/2/3，見 docstring）。
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
