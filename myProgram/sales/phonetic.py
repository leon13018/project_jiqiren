"""拼音近音糾錯核心（Phase A）。

職責：在 NLU 放棄出口，對「合法詞域極小」的 context（如問數量 {一瓶…十瓶}）
做本地拼音近音比對 — 雲端 ASR 對短中文詞 + 系統性平翹舌 / 前後鼻音混淆不可靠，
但我們握有 context，可用聲韻母模糊比對兜底，避免顧客被迫重講。

Phase A 範圍（spec resources/specs/pinyin_correction_phaseA_2026-06-14_spec.md）：
    - 聲韻母模糊等價：平翹舌（sh/s、ch/c、zh/z、l/n、h/f）+ 前後鼻音（ing/in、eng/en、ang/an）
    - 逐位相似度 + 歧義安全閥（top1 達閾值 + top1-top2 margin 足夠才修正）
    - pypinyin 注入 seam（to_pinyin DI）+ graceful no-op（缺依賴回 None）
    疊字去重 / 介音等價 / 不同字數子串規則 → Phase B（只服務問商品 context）。

⛔ 紅線：**頂層禁 import pypinyin**（Windows 未裝，頂層 import 必 ImportError 破壞
全 import）。只能在 `_default_to_pinyin` 函式內 lazy import。
"""

# 閾值常數（初值，Pi 實測調校）：
# 2 音節候選須兩字皆模糊命中（similarity=1.0）才達標；Phase A 偏保守避免誤糾。
SIMILARITY_THRESHOLD = 0.75
# top-1 須明顯勝 top-2（margin 足夠）才修正，否則退回 reprompt。
AMBIGUITY_MARGIN = 0.25

# 聲母模糊等價（平翹舌 + 常見混淆）：正規化後相等即視為同聲母。
_INITIAL_EQUIV = {"sh": "s", "ch": "c", "zh": "z", "l": "n", "h": "f"}
# 韻母模糊等價（前後鼻音）：正規化後相等即視為同韻母。
_FINAL_EQUIV = {"ing": "in", "eng": "en", "ang": "an"}


def _canon_initial(initial):
    """聲母正規化：平翹舌 / 常見混淆映射為同一 canonical 形式。"""
    return _INITIAL_EQUIV.get(initial, initial)


def _canon_final(final):
    """韻母正規化：前後鼻音映射為同一 canonical 形式。"""
    return _FINAL_EQUIV.get(final, final)


def _syllable_equiv(a, b):
    """兩音節 (聲母, 韻母) 模糊等價：聲母 canon 後相等 且 韻母 canon 後相等。"""
    i1, f1 = a
    i2, f2 = b
    return _canon_initial(i1) == _canon_initial(i2) and _canon_final(f1) == _canon_final(f2)


def _default_to_pinyin(char):
    """production 預設取音器：lazy import pypinyin 取單字 (聲母, 韻母)。

    ⛔ 紅線：pypinyin 只能在此函式內 lazy import（頂層禁，Windows 未裝）。
    strict=False 處理零聲母（y/w）。
    """
    import pypinyin

    initial = pypinyin.pinyin(char, style=pypinyin.Style.INITIALS, strict=False)[0][0]
    final = pypinyin.pinyin(char, style=pypinyin.Style.FINALS, strict=False)[0][0]
    return initial, final


def phonetic_match(text, candidates, *, to_pinyin=None):
    """對 text 在 candidates 中找拼音近音命中（歧義安全閥保護）。

    Args:
        text: ASR 輸出（可能被平翹舌 / 前後鼻音混淆）。
        candidates: 合法候選詞 list（如 {一瓶…十瓶}）。
        to_pinyin: 取音器 callback `char -> (聲母, 韻母)`；None 用 production lazy pypinyin。

    Returns:
        命中時回該 candidate 原字串；空輸入 / pypinyin 不可用 / 歧義 / 無夠近 → None。
    """
    # 守衛：空 text 或空 candidates → None
    if not text or not candidates:
        return None

    get_pinyin = to_pinyin or _default_to_pinyin

    # 取音段包 try/except ImportError：pypinyin 不可用（如 Windows 未裝）→ 整體回 None
    # （graceful no-op：糾錯層缺依賴時靜默退回 caller 既有 reprompt，既有測試零衝擊）。
    try:
        text_syllables = [get_pinyin(ch) for ch in text]
        candidate_syllables = [[get_pinyin(ch) for ch in cand] for cand in candidates]
    except ImportError:
        return None

    scores = []
    for cand_syl in candidate_syllables:
        hits = sum(
            1
            for i in range(min(len(text_syllables), len(cand_syl)))
            if _syllable_equiv(text_syllables[i], cand_syl[i])
        )
        # 長度不等自然降分（分母取較長者），無需子串特例。
        similarity = hits / max(len(text_syllables), len(cand_syl))
        scores.append(similarity)

    ranked = sorted(scores, reverse=True)
    top1 = ranked[0]
    top2 = ranked[1] if len(ranked) > 1 else 0.0

    # 歧義安全閥：top1 達閾值 且 top1 明顯勝 top2（margin 足夠）才修正。
    if top1 >= SIMILARITY_THRESHOLD and (top1 - top2) >= AMBIGUITY_MARGIN:
        return candidates[scores.index(top1)]
    return None
