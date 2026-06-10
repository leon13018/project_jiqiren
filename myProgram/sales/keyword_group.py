"""KeywordGroup — keyword 雙集封裝（W1 oop_w1 第一個 OOP 構件）。

動機：sales/ 各 confirm 子狀態 dispatch 普遍出現
    `contains_any(x, KW) or equals_strict_short(x, KW_STRICT)` 雙呼叫 pattern——
substring 比對集負責長詞安全命中，嚴格相等集（strict-short）負責短單字（如「好/取消/繼續」），
**防短詞 substring 誤命中**（如「好」會中「好亂」、「取消」會中「取消會議」）。
本檔把比對原語（contains_any / equals_strict_short）與雙集封裝（KeywordGroup）集中，
讓 11 個呼叫點改用 `KG_X.matches(text)` 單一語意。

import 鏈（無循環）：keyword_group 只 import stdlib →
constants/keywords.py import KeywordGroup 建實例 → nlu.py re-export 原語。
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
    """keyword 雙集封裝：substring 比對集 + 嚴格相等集（防短詞 substring 誤命中）。"""
    substrings: tuple
    strict_short: tuple = ()

    def matches(self, text: str) -> bool:
        return contains_any(text, self.substrings) or equals_strict_short(text, self.strict_short)
