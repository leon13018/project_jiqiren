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
    # text 與兩個候選皆完全相同分（1.0）→ top1-top2 = 0 < AMBIGUITY_MARGIN → None
    pinyin = {"甲": ("j", "ia"), "乙": ("y", "i")}
    assert phonetic_match("甲乙", ["甲乙", "甲乙"], to_pinyin=lambda ch: pinyin[ch]) is None


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
    # text=「甲乙」2 字；候選「甲乙丙」3 字，前 2 字完全相同（命中 2）
    # similarity = 2 / max(2,3) = 2/3 ≈ 0.667 < 0.75 → None
    pinyin = {"甲": ("j", "ia"), "乙": ("y", "i"), "丙": ("b", "ing")}
    assert phonetic_match("甲乙", ["甲乙丙"], to_pinyin=lambda ch: pinyin[ch]) is None


# ============================================================
# 介音不等價（守 Phase A 邊界）：(g,ua) vs (g,a) → 不命中（介音留 Phase B）
# ============================================================

def test_phonetic_match_medial_not_equivalent() -> None:
    # 韻母 ua / a 不在 _FINAL_EQUIV → 不等價 → 命中數 0 → similarity 0 → None
    pinyin = {"瓜": ("g", "ua"), "嘎": ("g", "a")}
    assert phonetic_match("瓜", ["嘎"], to_pinyin=lambda ch: pinyin[ch]) is None


# ============================================================
# graceful no-op：to_pinyin=None 且 pypinyin 不可用（Windows）→ None
# ============================================================

def test_phonetic_match_graceful_without_pypinyin() -> None:
    # 不注入 to_pinyin → 走 _default_to_pinyin lazy import pypinyin；
    # Windows 未裝 → ImportError → 整體靜默回 None（caller 落回既有 reprompt）。
    # （此測試依賴 pypinyin 未安裝；Pi 裝後此 path 改走真演算法，由 Part 1 注入式測試覆蓋。）
    assert phonetic_match("商品", QTY) is None
