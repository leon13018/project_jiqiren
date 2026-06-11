"""KeywordGroup — keyword 雙集封裝＋比對原語（W1 oop_w1；2026-06-12 perf_w1 搬入 constants/）。

substring 比對集負責長詞安全命中，嚴格相等集（strict-short）負責短單字
（如「好/取消/繼續」），**防短詞 substring 誤命中**（「好」中「好亂」、「取消」中「取消會議」）。

定位：純值原語（只 import stdlib），屬資料層——本層 keywords.py 以 KeywordGroup
建 KG_* 配對實例；nlu / states 經 `.matches` 消費。搬入理由：消除
constants（資料層）→ sales/（邏輯層）的唯一反向 import（findings F-9a）。
"""

from dataclasses import dataclass


def contains_any(text: str, keywords: list) -> bool:
    """大小寫不敏感 substring match — 任一 keyword 出現在 text 內即命中。"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def equals_strict_short(text: str, keywords: list) -> bool:
    """嚴格相等比對（去頭尾空白 + 大小寫不敏感） — 給短單字 keyword 用，避免 substring 誤命中。"""
    return text.strip().lower() in [kw.lower() for kw in keywords]


@dataclass(frozen=True)
class KeywordGroup:
    """keyword 雙集封裝：substring 比對集 + 嚴格相等集（防短詞 substring 誤命中）。

    perf_w1 F-1：keyword 為 frozen 常數，建構時預先小寫化（tuple / frozenset），
    熱路徑 matches 不再每呼叫重算 kw.lower() 或重建 list。
    等價性：text.strip().lower() == text.lower().strip()（lower 不增減空白）；
    eq / repr 只看 dataclass 欄位，預算屬性不影響既有斷言。
    """
    substrings: tuple
    strict_short: tuple = ()

    def __post_init__(self):
        # frozen dataclass 加非欄位屬性須走 object.__setattr__
        object.__setattr__(self, "_substrings_lower",
                           tuple(kw.lower() for kw in self.substrings))
        object.__setattr__(self, "_strict_short_lower",
                           frozenset(kw.lower() for kw in self.strict_short))

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return (any(kw in text_lower for kw in self._substrings_lower)
                or text_lower.strip() in self._strict_short_lower)
