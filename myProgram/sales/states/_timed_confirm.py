"""TimedConfirm 計時確認多型家族（W3 oop_w3；Template Method）。

cancel_confirm（6s）/ service_confirm（24s）/ invalid_qty_cancel_confirm（6s）三者共用
同一 wall-clock 骨架，只差提示文案、秒數、keyword 分類、保守 default、亂答行為、進場動作。
本家族以 Template Method 把骨架收成唯一一份（TimedConfirm.run），差異下放子類別覆寫點
（classify / on_timeout / on_enter / on_unclear）。三個對外 facade（_cancel_confirm /
_service_confirm / _invalid_qty_reask）委派給對應模組級單例。

不入家族（傘狀 §9 既定）：invalid_qty_reask 主迴圈、_dialog_c2_second_stage、
_dialog_checkout_confirm、_dialog_unclear_final_confirmation — 形狀不同（reset 鏈 /
每次重 prompt 重置 timeout / 多元終端分支），硬塞會讓基底長滿 if。
"""

import time
from abc import ABC, abstractmethod

from myProgram.sales.constants import (
    CANCEL_CONFIRM_TIMEOUT,
    CANCEL_CONFIRM_PROMPT,
    KG_CANCEL_CONFIRM_YES,
    KG_CANCEL_CONFIRM_NO,
    SERVICE_PHONE,
    L4_C_CONFIRM_TIMEOUT,
    L4_C_CONFIRM_PROMPT_TEMPLATE,
    L4_UNCLEAR_NOTICE,
    KG_L4_C_CONFIRM_YES,
    KG_L4_C_CONFIRM_NO,
    INVALID_QTY_CANCEL_CONFIRM_TIMEOUT,
    INVALID_QTY_CANCEL_CONFIRM_PROMPT,
    INVALID_QTY_UNCLEAR_PREFIX,
    KG_INVALID_QTY_CONTINUE,
    KG_INVALID_QTY_EXIT,
)


class TimedConfirm(ABC):
    """計時確認子狀態 Template Method。

    共用骨架：on_enter → speak_blocking(prompt) → wall-clock 迴圈
    （超時 / 沉默 → on_timeout；classify 命中 → return；亂答 → on_unclear，不重置 deadline）。

    wall-clock deadline 從 speak_blocking(prompt) 播完才起算（不變式 #4）；亂答只呼叫
    on_unclear hook，不重算 deadline（避免無限延長）。
    """

    prompt: str        # 子類別 class attr
    timeout: float     # 子類別 class attr

    def run(self, io):
        self.on_enter(io)
        io.speak_blocking(self.prompt)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self.on_timeout()
            response = io.read_customer_input(timeout=remaining)
            if response is None:
                return self.on_timeout()
            outcome = self.classify(response)
            if outcome is not None:        # ⚠️ 必須 is not None——False 是合法結果（CancelConfirm NO）
                return outcome
            self.on_unclear(io)

    @abstractmethod
    def classify(self, response: str):
        """keyword → 結果；None = 亂答（續迴圈）。"""

    @abstractmethod
    def on_timeout(self):
        """超時 / 沉默的保守 default（不變式 #1）。"""

    def on_enter(self, io):
        """進場 hook，預設 no-op。"""

    def on_unclear(self, io):
        """亂答 hook，預設 silent（純消耗預算，不重置 deadline）。"""


class CancelConfirm(TimedConfirm):
    """取消交易確認 6s（保守 default = 取消）。NO 先於 YES（防「不要取消」誤命中）。"""

    prompt = CANCEL_CONFIRM_PROMPT
    timeout = CANCEL_CONFIRM_TIMEOUT

    def classify(self, response):
        if KG_CANCEL_CONFIRM_NO.matches(response):
            return False
        if KG_CANCEL_CONFIRM_YES.matches(response):
            return True
        return None

    def on_timeout(self):
        return True


class ServiceConfirm(TimedConfirm):
    """客服進入點確認 24s（保守 default = 取消 "no"）。

    allow_scan=True（僅 L4）啟用終端 "s" fast path，行序最先（不變式 #2 scan 維持最先）。
    亂答 → speak L4_UNCLEAR_NOTICE（非阻塞），不重置 budget。
    """

    prompt = L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=L4_C_CONFIRM_TIMEOUT)
    timeout = L4_C_CONFIRM_TIMEOUT

    def __init__(self, allow_scan: bool = False):
        self.allow_scan = allow_scan

    def classify(self, response):
        if self.allow_scan and response == "s":
            return "scan"
        if KG_L4_C_CONFIRM_NO.matches(response):
            return "no"
        if KG_L4_C_CONFIRM_YES.matches(response):
            return "yes"
        return None

    def on_timeout(self):
        return "no"

    def on_enter(self, io):
        io.print_terminal(SERVICE_PHONE)

    def on_unclear(self, io):
        io.speak(L4_UNCLEAR_NOTICE)


class InvalidQtyCancelConfirm(TimedConfirm):
    """「取消無效數量商品繼續 vs 退出交易」二選一 6s（保守 default = 保 cart）。

    CONTINUE 先於 EXIT：任何含「取消/繼續」→ 保 cart；唯純「退出/離開」才 exit。
    亂答 → speak_blocking 帶 INVALID_QTY_UNCLEAR_PREFIX 重播 prompt。
    """

    prompt = INVALID_QTY_CANCEL_CONFIRM_PROMPT
    timeout = INVALID_QTY_CANCEL_CONFIRM_TIMEOUT

    def classify(self, response):
        if KG_INVALID_QTY_CONTINUE.matches(response):
            return "cancel_overlimit"
        if KG_INVALID_QTY_EXIT.matches(response):
            return "exit"
        return None

    def on_timeout(self):
        return "cancel_overlimit"

    def on_unclear(self, io):
        io.speak_blocking(INVALID_QTY_UNCLEAR_PREFIX + self.prompt)


# 模組級單例（皆無可變狀態，安全共用）
CANCEL_CONFIRM = CancelConfirm()
SERVICE_CONFIRM = ServiceConfirm(allow_scan=False)
SERVICE_CONFIRM_SCAN = ServiceConfirm(allow_scan=True)
INVALID_QTY_CANCEL_CONFIRM = InvalidQtyCancelConfirm()
