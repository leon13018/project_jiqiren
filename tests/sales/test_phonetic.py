"""test_phonetic.py — 測試 myProgram/sales/phonetic.py 拼音近音比對核心。

Phase A 範圍（spec resources/specs/pinyin_correction_phaseA_2026-06-14_spec.md）：
    - 聲韻母模糊比對（平翹舌 + 前後鼻音）
    - 歧義安全閥（top1 達閾值 + top1-top2 margin 足夠才修正）
    - pypinyin 注入 seam（to_pinyin DI），graceful no-op（缺依賴回 None）

測試一律注入 fake `to_pinyin`，不碰真 pypinyin（Windows 未裝）。
"""

from myProgram.sales.phonetic import phonetic_match


# ============================================================
# 共用 fake to_pinyin（注入式，不碰真 pypinyin）
# ============================================================
# 每字對應 (聲母, 韻母)；模擬台灣國語 ASR 痛點：
#   「商品」(sh-ang / p-in) ≈ 「三瓶」(s-an / p-ing)
#   平翹舌（sh→s）+ 前後鼻音（ang→an、ing→in）雙重混淆
_FAKE = {
    "商": ("sh", "ang"), "品": ("p", "in"),
    "一": ("", "i"), "兩": ("l", "iang"), "三": ("s", "an"), "四": ("s", "i"),
    "五": ("", "u"), "六": ("l", "iu"), "七": ("q", "i"), "八": ("b", "a"),
    "九": ("j", "iu"), "十": ("sh", "i"), "瓶": ("p", "ing"), "張": ("zh", "ang"),
}


def fake(ch):
    return _FAKE[ch]


QTY = ["一瓶", "兩瓶", "三瓶", "四瓶", "五瓶", "六瓶", "七瓶", "八瓶", "九瓶", "十瓶"]


# ============================================================
# 核心案例：問數量 context 真實痛點
# 「商品」被 ASR 聽成，實際顧客說「三瓶」→ 拼音近音應糾回「三瓶」
# ============================================================

def test_phonetic_match_corrects_shangpin_to_sanping() -> None:
    assert phonetic_match("商品", QTY, to_pinyin=fake) == "三瓶"


# ============================================================
# 單位變體（張）：刮刮樂 context 候選為「N張」
# ============================================================

def test_phonetic_match_handles_zhang_unit_variant() -> None:
    # 「商張」(sh-ang / zh-ang) ≈ 「三張」(s-an / zh-ang)：平翹舌 + 前後鼻音
    qty_zhang = ["一張", "兩張", "三張", "四張", "五張"]
    assert phonetic_match("商張", qty_zhang, to_pinyin=fake) == "三張"


# ============================================================
# 歧義安全閥：兩候選並列同分 → margin 不足 → None
# ============================================================

def test_phonetic_match_returns_none_when_ambiguous() -> None:
    # text 與兩個**相異** group 候選皆完全相同分（1.0）→ top1-top2 = 0 < AMBIGUITY_MARGIN → None
    # 2026-06-14：原用兩個字面相同候選 ["甲乙","甲乙"]，group-aware top-2 視同組不互壓
    #   → 不再構成歧義（同一答案）。改用相異候選（乙/丙 皆與甲音同）保留「跨組同分→歧義」原意。
    pinyin = {"甲": ("j", "ia"), "乙": ("j", "ia"), "丙": ("j", "ia")}
    assert phonetic_match("甲", ["乙", "丙"], to_pinyin=lambda ch: pinyin[ch]) is None


# ============================================================
# 無夠近：所有候選皆低於 SIMILARITY_THRESHOLD → None
# ============================================================

def test_phonetic_match_returns_none_when_no_candidate_close_enough() -> None:
    # 「八九」與所有候選每字聲韻母皆不等價（命中數 0）→ similarity 0 < 0.75 → None
    assert phonetic_match("八九", QTY, to_pinyin=fake) is None


# ============================================================
# 聲母平翹舌等價：s↔sh、z↔zh、c↔ch、n↔l、f↔h 各一對命中（韻母相同）
# ============================================================

def test_phonetic_match_initial_equivalences() -> None:
    pairs = {
        ("s", "sh"): {"甲": ("s", "a"), "乙": ("sh", "a")},
        ("z", "zh"): {"甲": ("z", "a"), "乙": ("zh", "a")},
        ("c", "ch"): {"甲": ("c", "a"), "乙": ("ch", "a")},
        ("n", "l"): {"甲": ("n", "a"), "乙": ("l", "a")},
        ("f", "h"): {"甲": ("f", "a"), "乙": ("h", "a")},
    }
    for pinyin in pairs.values():
        # 「甲」與唯一候選「乙」聲母模糊等價、韻母相同 → similarity 1.0 → 命中「乙」
        assert phonetic_match("甲", ["乙"], to_pinyin=lambda ch: pinyin[ch]) == "乙"


# ============================================================
# 韻母前後鼻音等價：in↔ing、en↔eng、an↔ang 各一對命中（聲母相同）
# ============================================================

def test_phonetic_match_final_equivalences() -> None:
    pairs = {
        ("in", "ing"): {"甲": ("p", "in"), "乙": ("p", "ing")},
        ("en", "eng"): {"甲": ("p", "en"), "乙": ("p", "eng")},
        ("an", "ang"): {"甲": ("p", "an"), "乙": ("p", "ang")},
    }
    for pinyin in pairs.values():
        # 「甲」與唯一候選「乙」韻母模糊等價、聲母相同 → similarity 1.0 → 命中「乙」
        assert phonetic_match("甲", ["乙"], to_pinyin=lambda ch: pinyin[ch]) == "乙"


# ============================================================
# 完全相同字 → 相似度 1.0 命中
# ============================================================

def test_phonetic_match_exact_match_hits() -> None:
    # 「三瓶」對候選 QTY 含「三瓶」本身 → 完全相同（1.0），且明顯勝其他 → 命中
    assert phonetic_match("三瓶", QTY, to_pinyin=fake) == "三瓶"


# ============================================================
# 空輸入守衛：空 text → None；空 candidates → None
# ============================================================

def test_phonetic_match_empty_text_returns_none() -> None:
    assert phonetic_match("", QTY, to_pinyin=fake) is None


def test_phonetic_match_empty_candidates_returns_none() -> None:
    assert phonetic_match("商品", [], to_pinyin=fake) is None


# ============================================================
# 長度不等降分：text 2 字 vs candidate 3 字、僅 2 字命中 → 2/3 < 0.75 → None
# ============================================================

def test_phonetic_match_length_mismatch_lowers_score_to_none() -> None:
    # text=「甲乙」2 字；候選「丙丁戊」3 字，前 2 字音同（丙≡甲、丁≡乙，命中 2）
    # similarity = 2 / max(2,3) = 2/3 ≈ 0.667 < 0.75 → None
    # 2026-06-14：原候選用「甲乙丙」，「甲乙」恰為其字元子串 → 觸發 Phase B 子串 fallback
    #   翻成命中。本案原意測「長度不等降分→None」非子串，改用相異字（音同位同但字元不構成
    #   子串）保留原意，與 Phase B 子串規則解耦。
    pinyin = {"甲": ("j", "ia"), "乙": ("y", "i"),
              "丙": ("j", "ia"), "丁": ("y", "i"), "戊": ("b", "ing")}
    assert phonetic_match("甲乙", ["丙丁戊"], to_pinyin=lambda ch: pinyin[ch]) is None


# ============================================================
# 介音等價（2026-06-14 Phase B 翻轉）：(g,ua) ≡ (g,a)（介音 ua→a）→ 命中
# 解「尬(g,a)≡刮(g,ua)」痛點；Phase A 此處原斷言不等價，Phase B 補介音等價後翻轉。
# ============================================================

def test_phonetic_match_medial_equivalent() -> None:
    # 韻母 ua canon 後等價於 a（_FINAL_EQUIV "ua":"a"）→ 聲母同、韻母等價 →
    # similarity 1.0 → 命中唯一候選「嘎」。
    pinyin = {"瓜": ("g", "ua"), "嘎": ("g", "a")}
    assert phonetic_match("瓜", ["嘎"], to_pinyin=lambda ch: pinyin[ch]) == "嘎"


def test_phonetic_match_medial_equivalences_three_classes() -> None:
    """介音脫落三類等價：ua↔a、uo↔o、ie↔e（聲母相同）各一對命中。"""
    pairs = {
        ("ua", "a"): {"甲": ("g", "ua"), "乙": ("g", "a")},
        ("uo", "o"): {"甲": ("d", "uo"), "乙": ("d", "o")},
        ("ie", "e"): {"甲": ("l", "ie"), "乙": ("l", "e")},
    }
    for pinyin in pairs.values():
        assert phonetic_match("甲", ["乙"], to_pinyin=lambda ch: pinyin[ch]) == "乙"


# ============================================================
# ② 引擎擴展（2026-06-14 Phase B，spec §2.2）：疊字去重 / group_key / 子串
# 問商品 context fake：冰紅茶 / 紅茶 / 刮刮樂 三候選。
# ============================================================

_FAKE_B = {
    "冰": ("b", "ing"), "紅": ("h", "ong"), "茶": ("ch", "a"),
    "刮": ("g", "ua"), "樂": ("l", "e"), "尬": ("g", "a"), "宏": ("h", "ong"),
}


def fakeB(ch):
    return _FAKE_B[ch]


def grpB(s):
    return {"冰紅茶": "T", "紅茶": "T", "刮刮樂": "L"}[s]


PROD = ["冰紅茶", "紅茶", "刮刮樂"]


# --- (a) 疊字去重：比對前 collapse 連續重複字，命中回 original ---

def test_phonetic_match_dedup_dropped_repeat_char() -> None:
    """「刮樂」(=刮刮樂少一字)：text 與候選去重後（刮刮樂→刮樂）逐位相同 → 命中 original 刮刮樂。"""
    assert phonetic_match("刮樂", ["刮刮樂", "紅茶"], to_pinyin=fakeB) == "刮刮樂"


def test_phonetic_match_dedup_with_medial_garble() -> None:
    """「尬尬樂」(=刮刮樂，介音脫落 ua→a)：去重 尬尬樂→尬樂、刮刮樂→刮樂；
    尬(g,a)≡刮(g,ua) 介音等價 + 樂同 → 命中 original 刮刮樂。"""
    assert phonetic_match("尬尬樂", ["刮刮樂", "紅茶"], to_pinyin=fakeB) == "刮刮樂"


# --- (c) group_key：同商品多 surface 不互壓歧義閥 ---

def test_phonetic_match_group_key_same_product_not_suppressed() -> None:
    """「宏茶」(=紅茶) vs 候選 冰紅茶/紅茶（同 group T）+ 刮刮樂（group L）：
    冰紅茶 與 紅茶 同 group 不互壓 margin（group-aware top-2 取不同 group 最高）→ 命中紅茶。"""
    assert phonetic_match("宏茶", PROD, to_pinyin=fakeB, group_key=grpB) == "紅茶"


# --- (d) 不同字數子串 fallback（group-aware）---

def test_phonetic_match_substring_fallback_group_aware() -> None:
    """「茶」⊂「冰紅茶」「紅茶」(皆 group T)：similarity 無 winner →
    group-aware 子串 fallback 唯一 group → 回該組（冰紅茶 / 紅茶 之一）。"""
    assert phonetic_match("茶", PROD, to_pinyin=fakeB, group_key=grpB) in {"冰紅茶", "紅茶"}


def test_phonetic_match_substring_fallback_disabled_without_group_key() -> None:
    """無 group_key（問數量 / ① path，group_key=None）→ 子串 fallback 不啟用 → None。
    保證引擎擴展對 Phase A / ① inert。"""
    assert phonetic_match("茶", PROD, to_pinyin=fakeB) is None


# ============================================================
# graceful no-op：to_pinyin=None 且 pypinyin 不可用（Windows）→ None
# ============================================================

def test_phonetic_match_graceful_without_pypinyin() -> None:
    # 不注入 to_pinyin → 走 _default_to_pinyin lazy import pypinyin；
    # Windows 未裝 → ImportError → 整體靜默回 None（caller 落回既有 reprompt）。
    # （此測試依賴 pypinyin 未安裝；Pi 裝後此 path 改走真演算法，由 Part 1 注入式測試覆蓋。）
    assert phonetic_match("商品", QTY) is None


# ============================================================
# 2.0 完全同音 tie-break（2026-06-15，spec §2.0）
# 歧義閥改用 (模糊相似度, 完全同音數) 排序。完全同音數 = 逐位「聲韻母**未經模糊
# 正規化**即相等」的音節數。sim 平手時 exact 較高者勝（解真歧義「食品→十瓶」）。
# fake 取音器刻意構造 ASR 痛點：食(sh,i) 對 四(s,i)/十(sh,i) sim 皆 1.0，但
#   食≡十 完全同音（exact=1）勝 食≈四 平翹舌（exact=0）。
# ============================================================

# 食=十 同音、食≈四 平翹舌、品≈瓶 前後鼻音 → 食品 對 四瓶/十瓶 sim 皆 1.0
_FK = {
    "食": ("sh", "i"), "品": ("p", "in"), "商": ("sh", "ang"),
    "三": ("s", "an"), "四": ("s", "i"), "十": ("sh", "i"),
    "一": ("", "i"), "兩": ("l", "iang"), "五": ("", "u"), "六": ("l", "iu"),
    "七": ("q", "i"), "八": ("b", "a"), "九": ("j", "iu"), "瓶": ("p", "ing"),
}


def fk(ch):
    return _FK[ch]


QP = [w + "瓶" for w in "一兩三四五六七八九十"]


def test_phonetic_match_exact_homophone_tiebreak_shipin_to_shiping() -> None:
    """「食品」對 四瓶/十瓶 模糊相似度皆 1.0（食≈四 平翹舌、品≈瓶 前後鼻音），
    但食≡十 完全同音（exact=1）> 食≈四（exact=0）→ tie-break 命中十瓶。
    （現況 margin=0 → None；本案為 RED）"""
    assert phonetic_match("食品", QP, to_pinyin=fk) == "十瓶"


def test_phonetic_match_clear_winner_unaffected_by_tiebreak() -> None:
    """「商品」清楚命中三瓶（sim 1.0 明顯勝其他）→ tie-break 不改變既有行為。"""
    assert phonetic_match("商品", QP, to_pinyin=fk) == "三瓶"


def test_phonetic_match_double_tie_still_none() -> None:
    """真雙重平手：兩候選對 text 既 sim 皆 1.0、exact 又皆 0 → 無法區分 → None。
    甲(j,ia)；乙/丙皆(j,ia)（聲韻母與甲完全相同字但屬不同 group）→ sim 1.0、
    exact 1 也相同 → exact 無法 tie-break → None。"""
    pinyin = {"甲": ("j", "ia"), "乙": ("j", "ia"), "丙": ("j", "ia")}
    assert phonetic_match("甲", ["乙", "丙"], to_pinyin=lambda ch: pinyin[ch]) is None
