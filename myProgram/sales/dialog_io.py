"""DialogIO — 對話層 IO callback 束物件（W2 oop_w2）。

sales 對話側私有函式原本各自手傳 5-8 個 IO callback；本物件把它們束成單一 io，
私有函式一律收 io 單參。speak_blocking 取代 8 處 `_speak_blocking = ... if ... else ...`
fallback 三元式，語意一字不差。
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DialogIO:
    """對話層 IO callback 束。只裝 IO，不裝業務狀態（cart / 計數器仍獨立傳）。

    print_terminal / do_action / speak_and_wait 預設 None：confirm 類子狀態只持有
    部分 callback（如 cancel_confirm 無 print_terminal），允許部分注入；
    缺欄位的子狀態不得使用該欄位。production 完整 wire-up 由 run_* facade 全欄注入。
    """
    speak: Callable
    read_customer_input: Callable
    print_terminal: Callable = None
    do_action: Callable = None
    speak_and_wait: Callable = None

    def speak_blocking(self, text: str) -> None:
        """阻塞 speak（wall-clock budget 用）——取代 8 處 fallback 三元式，語意一字不差。"""
        (self.speak_and_wait if self.speak_and_wait is not None else self.speak)(text)
