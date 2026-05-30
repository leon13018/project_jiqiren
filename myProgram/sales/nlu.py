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
    商品 keyword（KEYWORDS_ICED_TEA / KEYWORDS_SCRATCH）與中文數字映射（CHINESE_DIGIT_MAP）
    已於 2026-05-26 Wave 6 搬至 myProgram/sales/constants/keywords.py（資料層歸資料層）。
"""

import re
from typing import Literal

from myProgram.sales.constants import (
    KEYWORDS_L4_ACK_OR_WAIT,
    KEYWORDS_L4_ACK_SHORT,
    KEYWORDS_WANT_TO_BUY_VAGUE,
    KEYWORDS_WANT_TO_BUY_SHORT,
    KEYWORDS_ICED_TEA,
    KEYWORDS_SCRATCH,
    CHINESE_DIGIT_MAP,
)

# ============================================================
# 關鍵字白名單（依規格書 L0_共通.md）
# ============================================================

# REJECT substring 集（移除「沒/没」單字、「沒有/沒了/不了/没有」→ 移到 strict-short，
# 避免「沒有問題」「等不了」「受不了」等口語被 substring 誤命中）
# HP-1 / C5：「沒有 / 沒了 / 不了 / 没有」從 substring 集移出，改 strict-short
# 2026-05-29 加：cross-L cancel 意圖明確 phrase（user 列表擴充）
#   「我想取消交易」「取消交易」「我要取消交易」「退出交易」
#   會被 _dialog_main_loop / _dialog_dispatch_inner_l2 偵測到後，
#   經 cancel_confirm gate 才真正退 L1
_KEYWORDS_REJECT = [
    "不要", "不用", "不想", "不買", "不買了",
    # 2026-05-30 加（Pi demo L3「請問還有額外需要購買的嗎？」NLU gap 修補）
    # 「不需要」cover「不需要」/「我不需要」/「不需要了」3 個用語（繁簡同字）
    # 「沒有額外」cover「沒有額外需要購買的」（「沒有」單字仍由 strict_short 處理，
    #   避免「沒有問題」這類複合口語被 substring 誤命中）
    # FP 驗證：L3 mode → 結帳 / L2 mode → 拒絕 cancel_confirm gate，三 mode 行為皆合理
    "不需要", "沒有額外",
    "不买", "不想买", "不买了",  # 簡體變體
    "没有额外",                    # 簡體變體（「不需要」繁簡同字不另列）
    # 2026-05-29 cross-L cancel 擴充
    "取消交易", "退出交易", "我想取消交易", "我要取消交易",
    "取消交易吧", "我想要取消交易",
    "取消这次交易", "退出这次交易",  # 簡體
]

# REJECT strict-short 集（只在 text.strip() 完全等於時命中，避免 substring 誤命中）
# HP-1：加入「沒有 / 沒了 / 不了 / 没有」— 僅完整詞才觸發 reject，不影響複合口語
_KEYWORDS_REJECT_STRICT_SHORT = ["沒", "没", "沒有", "沒了", "不了", "没有"]

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
    # 2026-05-30 加（Pi demo 8-keyword sweep）：L3 mode 顧客講「不要買了」「不想買」
    # 原本被通用 _KEYWORDS_REJECT substring「不要」「不想」命中 → mode="normal"
    # 視為「結帳」→ 觸發 confirm「您即將結帳... 正確嗎？」UX 怪；
    # 補入 L3_STRICT → 視為「拒絕」→ 進 cancel_confirm gate 由 user 確認意圖
    "不要買了", "不想買",
    "不要买了", "不想买",  # 簡體
    # 2026-05-29 cross-L cancel 擴充（user 列表）— 明確「取消交易 / 退出交易」phrase
    # 在 L3 strict reject 也應命中（雖然「取消」substring 已命中，明示 phrase 提升可讀性）
    "取消交易", "退出交易", "我想取消交易", "我要取消交易",
    "取消交易吧", "我想要取消交易",
    "取消这次交易", "退出这次交易",  # 簡體
]

_KEYWORDS_THINK = ["等等", "等一下", "稍等", "想想", "考慮", "想一下", "hold on", "wait"]

# CHECKOUT substring 集（移除「no/nope/好了」短詞/歧義詞，避免 strict yes/no 子狀態衝突）
# 「沒了/沒有了」保留：包含較長的詞，substring match 不易誤命中其他情境
# 「no/nope/好了」移除：短詞，應由各 mode 呼叫端自行處理（l2/l4 mode 有 no→拒絕邏輯）
# C12 (2026-05-26)：加入「沒事/沒問題」— L3 normal mode 語意「沒別的了，去結帳」
_KEYWORDS_CHECKOUT = [
    "結帳", "買單", "付款", "就這樣", "可以了",
    "沒了", "沒有了", "夠了", "沒事", "沒問題",
    "结账", "买单", "付款", "就这样", "可以了", "没了", "没有了", "够了", "没事", "没问题",  # 簡體變體
]

_KEYWORDS_SERVICE = ["客服", "聯絡", "聯繫", "contact", "服務"]

# 僅 L4 客服模式內生效
_KEYWORDS_CONTINUE = ["繼續", "接著", "繼續買", "繼續交易", "continue"]

_KEYWORDS_EXIT = ["退出", "取消", "離開", "算了", "不買了", "exit"]


def contains_any(text: str, keywords: list) -> bool:
    """大小寫不敏感 substring match — 任一 keyword 出現在 text 內即命中。"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def equals_strict_short(text: str, keywords: list) -> bool:
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


Intent = Literal[
    "拒絕",
    "想一下",
    "結帳",
    "客服",
    "商品:冰紅茶",
    "商品:刮刮樂",
    "繼續交易",
    "退出交易",
    "等待安撫",
    "想買無商品",
    "無法判斷",
]


def classify_intent(text: str, mode: str = "normal") -> Intent:
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
        # 否定 guard（regex）：排在 CONTINUE 前，避免「不繼續/不要繼續/我不想繼續」
        # substring 誤命中「繼續」→ 繼續交易。
        # HP-2：擴充涵蓋「不|別|沒|休 + 0-5 中文字 + 繼續」pattern。
        # 例：「我不想繼續」「沒打算繼續」「不準備繼續了」
        if re.search(r"[不別沒休][一-龥]{0,5}繼續", text):
            return "退出交易"
        if "停止" in text:
            return "退出交易"
        if contains_any(text, _KEYWORDS_CONTINUE):
            return "繼續交易"
        if contains_any(text, _KEYWORDS_EXIT):
            return "退出交易"
        if equals_strict_short(text, ["no", "nope"]):
            return "退出交易"

    # L4 mode 專屬：等待安撫 → 顧客禮貌肯定 / 找手機掃碼（2026-05-26 加；使用者實機 UX 修補）
    # 必須先於 L2/L4 共用的 no/nope 拒絕判定，因為「好/嗯/ok」strict-short 不應被
    # 任何其他分支吃掉；其他 mode 不命中，避免污染 L2 詢問需求 / L3 confirm context 的「好」語意
    if mode == "l4":
        if equals_strict_short(text, KEYWORDS_L4_ACK_SHORT):
            return "等待安撫"
        if contains_any(text, KEYWORDS_L4_ACK_OR_WAIT):
            return "等待安撫"

    # L2 / L4 模式：no / nope 強制視為拒絕（覆寫 _KEYWORDS_CHECKOUT 內的預設）
    # 2026-05-25 使用者實測層別語意：L2「沒需求」/ L4「不要了」皆是拒絕，只 L3「沒了」是結帳
    if mode in ("l2", "l4"):
        if equals_strict_short(text, ["no", "nope"]):
            return "拒絕"

    # L3 (normal mode) 嚴格 reject 判定：只有命中 _KEYWORDS_REJECT_L3_STRICT 才視為拒絕
    # 一般 _KEYWORDS_REJECT 短詞「不要 / 不用 / 不想 / 不買」在 L3 視為「不追加」→ 結帳
    # 2026-05-25 加：使用者實測 L3 顧客講「不用」本意「不需要加購」（同 no/nope 在 L3 的處理）
    if mode == "normal":
        if contains_any(text, _KEYWORDS_REJECT_L3_STRICT):
            return "拒絕"
        if contains_any(text, _KEYWORDS_REJECT) or equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT):
            return "結帳"

    # 通用優先序（L2/L4 走這 — L3 已在上面 early return）
    if contains_any(text, _KEYWORDS_REJECT) or equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT):
        return "拒絕"
    if contains_any(text, _KEYWORDS_THINK):
        return "想一下"
    if contains_any(text, _KEYWORDS_CHECKOUT):
        return "結帳"
    if contains_any(text, _KEYWORDS_SERVICE):
        return "客服"
    if contains_any(text, KEYWORDS_ICED_TEA):
        return "商品:冰紅茶"
    if contains_any(text, KEYWORDS_SCRATCH):
        return "商品:刮刮樂"

    # 2026-05-26 加：L2 (DnC) / L3 (DyC) normal mode 顧客講肯定詞但無具體商品名
    # 必須在所有具體 keyword check 之後，避免吃掉「沒有」(REJECT) / 「不要」(REJECT/CHECKOUT)
    # 等先決判定。strict-short「有/要」防 substring 誤命中「沒有」「不要」
    # （後者已在上方 REJECT / CHECKOUT 分支被攔截）
    if mode in ("l2", "normal"):
        if equals_strict_short(text, KEYWORDS_WANT_TO_BUY_SHORT):
            return "想買無商品"
        if contains_any(text, KEYWORDS_WANT_TO_BUY_VAGUE):
            return "想買無商品"

    return "無法判斷"


# 中文「十 / 百」位乘數（B5 / D10 複合數字支援）
_CHINESE_TENS = {"十": 10, "拾": 10, "百": 100, "佰": 100}

# 個位字元集（供複合數字 regex 用）
_CHINESE_UNIT_CHARS = "一壹兩二貳三參四肆五伍六陸七柒八捌九玖"


def _parse_compound_chinese(text: str) -> int | None:
    """解析複合中文數字（「十二 / 二十 / 二十一 / 一百 / 三十五」等）。

    支援 pattern（依優先序）：
        1. X百[Y十Z] — 百位（如「一百」→ 100、「三百五十二」→ 352）
        2. [X]十Y    — 十位（如「十二」→ 12、「二十」→ 20、「二十一」→ 21）

    Returns:
        int 或 None（未命中複合 pattern）。
    """
    units = _CHINESE_UNIT_CHARS

    # 「百」位優先
    m = re.search(rf"([{units}])[百佰]([{units}十拾]*)?", text)
    if m:
        hundreds = CHINESE_DIGIT_MAP.get(m.group(1), 1)
        rest = m.group(2) or ""
        rest_val = _parse_tens_part(rest)
        return hundreds * 100 + rest_val

    # 「十」位
    m = re.search(rf"([{units}])?[十拾]([{units}])?", text)
    if m:
        tens_char = m.group(1)
        units_char = m.group(2)
        tens = CHINESE_DIGIT_MAP.get(tens_char, 1)
        units_val = CHINESE_DIGIT_MAP.get(units_char, 0)
        return tens * 10 + units_val

    return None


def _parse_tens_part(text: str) -> int:
    """解析「百位後的剩餘部分」（十位 + 個位，或純個位）。

    供 _parse_compound_chinese 內部使用。
    """
    if not text:
        return 0
    units = _CHINESE_UNIT_CHARS
    m = re.search(rf"([{units}])?[十拾]([{units}])?", text)
    if m:
        tens = CHINESE_DIGIT_MAP.get(m.group(1), 1)
        u = CHINESE_DIGIT_MAP.get(m.group(2), 0)
        return tens * 10 + u
    # 純個位
    for char, value in CHINESE_DIGIT_MAP.items():
        if char in text:
            return value
    return 0


def has_quantity(text: str) -> bool:
    """判斷文字內是否含可解析的數量（阿拉伯或中文數字）。

    供 L2 / L3 鏈路 C 判定：若顧客講商品但未含數量，呼叫端追問「您要幾瓶/張？」。
    parse_quantity 對「無數量」會 fallback 為 1 — 本函數存在意義就是「區分顯式 1 vs 預設 1」。

    Returns:
        True 含數量；False 無。
    """
    if re.search(r"\d+", text):
        return True
    return any(char in text for char in CHINESE_DIGIT_MAP)


def parse_quantity(text: str) -> int:
    """從顧客輸入解析商品數量。

    判定規則（依優先序）：
        1. 阿拉伯數字優先（re.findall 取第一個非負整數；0 明確回 0）
        2. 複合中文數字（十位 / 百位；如「十二 / 二十 / 一百 / 三十五」）
        3. 單字中文數字 fallback（依 CHINESE_DIGIT_MAP）
        4. 以上皆無命中 → 預設 1

    B16 修正（2026-05-26）：顧客明確說「0 瓶」→ 回 0，不 fallback 為 1。
    若 text 內所有阿拉伯數字皆為 0，視為顧客明確表達「不要」，回 0。

    Args:
        text: 顧客輸入字串

    Returns:
        數量整數（含 0）；無數字時預設 1
    """
    # 阿拉伯數字優先（B16：顯式 0 回 0，不 fallback）
    arabic_matches = re.findall(r"\d+", text)
    if arabic_matches:
        for m in arabic_matches:
            n = int(m)
            if n > 0:
                return n
        # 所有阿拉伯數字皆為 0 → 明確 0
        return 0

    # 複合中文數字（B5 / D10）
    compound = _parse_compound_chinese(text)
    if compound is not None:
        return compound

    # 單字中文數字 fallback
    for char, value in CHINESE_DIGIT_MAP.items():
        if char in text:
            return value

    # 預設
    return 1

