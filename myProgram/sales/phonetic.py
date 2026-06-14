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
# 韻母模糊等價（前後鼻音 + 2026-06-14 Phase B 介音脫落）：正規化後相等即視為同韻母。
# 介音 ua→a / uo→o / ie→e：解「尬(g,a)≡刮(g,ua)」ASR 介音脫落痛點。
# 問數量候選韻母無一含 ua/uo/ie → 對 Phase A / ① 數量候選 inert（零影響）。
_FINAL_EQUIV = {
    "ing": "in", "eng": "en", "ang": "an",
    "ua": "a", "uo": "o", "ie": "e",
}


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


def _dedup_chars(text):
    """連續重複字 collapse（2026-06-14 Phase B 疊字去重）：刮刮樂→刮樂、尬尬樂→尬樂。

    解 ASR 對疊字商品名漏字 / 多字（刮樂≈刮刮樂）。idempotent（已去重者再呼叫不變）。
    只 collapse 相鄰相同字，非相鄰重複保留（如「茶紅茶」不變）。
    """
    if not text:
        return text
    out = [text[0]]
    for ch in text[1:]:
        if ch != out[-1]:
            out.append(ch)
    return "".join(out)


def phonetic_match(text, candidates, *, to_pinyin=None, group_key=None):
    """對 text 在 candidates 中找拼音近音命中（歧義安全閥保護）。

    Args:
        text: ASR 輸出（可能被平翹舌 / 前後鼻音 / 介音脫落 / 疊字漏字混淆）。
        candidates: 合法候選詞 list（如 {一瓶…十瓶} 或 {冰紅茶, 紅茶, 刮刮樂}）。
        to_pinyin: 取音器 callback `char -> (聲母, 韻母)`；None 用 production lazy pypinyin。
        group_key: 候選分組 callback `candidate -> group`（2026-06-14 Phase B 加）。
            同 group 多 surface（如 冰紅茶 / 紅茶 同指一商品）不互壓歧義閥 margin，
            且子串 fallback 以 group 唯一性判定。None = identity（每候選自成一組）→
            退化為 Phase A 行為（問數量 / ① 數量候選不受影響）。

    Returns:
        命中時回該 candidate 原字串；空輸入 / pypinyin 不可用 / 歧義 / 無夠近 → None。

    執行序（spec §2.2）：守衛 → 取音（try/except ImportError→None）→ 疊字去重 →
        similarity（聲韻母 + 介音 + 鼻音 + 平翹舌）→ group-aware 歧義閥 → 命中回 original；
        否則不同字數子串 fallback（group-aware）；否則 None。
    """
    # 守衛：空 text 或空 candidates → None
    if not text or not candidates:
        return None

    get_pinyin = to_pinyin or _default_to_pinyin
    groups = [(group_key(cand) if group_key else cand) for cand in candidates]

    # 疊字去重（命中仍回 original candidate；deduped 只用於比對 / 子串）
    text_dd = _dedup_chars(text)
    cand_dd = [_dedup_chars(cand) for cand in candidates]

    # 取音段包 try/except ImportError：pypinyin 不可用（如 Windows 未裝）→ 整體回 None
    # （graceful no-op：糾錯層缺依賴時靜默退回 caller 既有 reprompt，既有測試零衝擊）。
    try:
        text_syllables = [get_pinyin(ch) for ch in text_dd]
        candidate_syllables = [[get_pinyin(ch) for ch in cand] for cand in cand_dd]
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

    best_idx = max(range(len(scores)), key=lambda i: scores[i])
    top1 = scores[best_idx]
    # group-aware top-2：只取「與 top-1 不同 group」者最高分（同商品多 surface 不互壓）。
    # group_key=None 時各候選自成 group → 退化為原 top-2（Phase A 行為不變）。
    other_group = [s for i, s in enumerate(scores) if groups[i] != groups[best_idx]]
    top2 = max(other_group) if other_group else 0.0

    # 歧義安全閥：top1 達閾值 且 top1 明顯勝其他 group（margin 足夠）才修正。
    if top1 >= SIMILARITY_THRESHOLD and (top1 - top2) >= AMBIGUITY_MARGIN:
        return candidates[best_idx]

    # 不同字數子串 fallback（group-aware）：similarity 無 winner 時，找 deduped(text)
    # 是 deduped(候選) 子串者；命中候選同屬唯一 group → 回該組 similarity 最高者；
    # 跨多 group / 無命中 → None。解「茶 ⊂ 紅茶/冰紅茶（皆同商品組）」。
    sub_idx = [i for i in range(len(candidates))
               if text_dd != cand_dd[i] and text_dd in cand_dd[i]]
    if sub_idx:
        sub_groups = {groups[i] for i in sub_idx}
        if len(sub_groups) == 1:
            return candidates[max(sub_idx, key=lambda i: scores[i])]
    return None
