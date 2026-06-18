"""DialogIO — 對話層 IO callback 束物件。

sales 對話側私有函式 / 子狀態把 5-8 個 IO callback 束成單一 io，收 io 單參。
speak_blocking 提供阻塞 speak（speak_and_wait 缺時 fallback speak），供 wall-clock
budget 子狀態（_timed_confirm 家族等）從 TTS 播完才起算 timeout。
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
    display: Callable = None        # web 顯示鏡像 emit；終端模式 no-op / None（guard 於 caller）

    def speak_blocking(self, text: str) -> None:
        """阻塞 speak（wall-clock budget 用）——取代 8 處 fallback 三元式，語意一字不差。"""
        (self.speak_and_wait if self.speak_and_wait is not None else self.speak)(text)
