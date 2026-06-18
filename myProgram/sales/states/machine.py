"""SalesMachine — L1→dialog→L4→L5 主迴圈的 State pattern 實作（W5，2026-06-10）。

職責：
    - 把 logic.py 主迴圈的字串 tuple 魔法值（("L4", 0) / ("L1_via_subroutine_a", …)）+
      if/elif 調度鏈，改寫成教科書 State pattern：State(ABC) 子類別 + Transition + SalesMachine。
    - tuple 魔法值死在各 State.run 內部（各 states.run_* 對外回傳 shape 不變——它們被測試直接呼叫）。

設計約束：
    - **mock seam = `myProgram.sales.states` 模組屬性**：所有 run_* / run_subroutine_a 一律
      晚綁定 `states.run_*(...)`（模組屬性呼叫），禁 `from ... import run_l1` 捕引用
      （test_machine / test_logic 用 monkeypatch.setattr(states_module, "run_*", stub) 替換）。
    - kwargs 逐字照抄現行 logic.py 各呼叫點（測試 stub 嚴格 keyword-only）。
    - cart invariant fail-fast（A4-c）：每進新層 assert（進場 + 轉移分支）；訊息格式原樣保留。

層狀態判定原則（2026-05-25 B 方案敲定）：
    - L1 ↔ dialog ↔ L4 ↔ L5 由「世界狀態」決定（非動作歷史）
    - dialog 內部 cart 狀態決定模式：cart 空 = 詢問需求；cart 非空 = 詢問加單 / 結帳
    - 未來加刪除商品時 cart 變空，dialog 下一輪自動回詢問需求模式（無需額外 transition）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from myProgram.sales import states
from myProgram.sales import cart as cart_module


# 機台層 → web 顯示 phase 映射（display 回呼用；終端模式 display 為 None 不觸發）。
_PHASE_BY_STATE = {"l1": "standby", "dialog": "ordering", "l4": "checkout", "l5": "thankyou"}


@dataclass(frozen=True)
class Transition:
    """狀態轉移結果——取代主迴圈的字串 tuple 魔法值。"""
    next_state: str                 # "dialog" / "l4" / "l5" / "l1"
    via_subroutine_a: bool = False  # True = 先跑子例程 A + 下輪 L1 直接 hawk


class State(ABC):
    """機台狀態基底。entry_invariant + entry_ctx 供 machine 進場前 fail-fast 檢查（A4-c）。"""
    entry_invariant: str   # "empty" / "nonempty"
    entry_ctx: str         # assert 訊息用語境字串（原樣保留）

    @abstractmethod
    def run(self, machine) -> "Transition | None": ...   # None = 程式終止（run_l1 的 None）


def _assert_cart_empty(cart, ctx: str) -> None:
    """A4-c：fail-fast assert cart 應為空。違反 → 系統 bug，立刻爆。"""
    if not cart_module.is_empty(cart):
        raise AssertionError(
            f"Cart invariant 違反 [{ctx}]：應為空但 cart={dict(cart)}"
        )


def _assert_cart_nonempty(cart, ctx: str) -> None:
    """A4-c：fail-fast assert cart 應非空。違反 → 系統 bug，立刻爆。"""
    if cart_module.is_empty(cart):
        raise AssertionError(
            f"Cart invariant 違反 [{ctx}]：應非空但 cart 為空"
        )


class L1State(State):
    """L1 商家模式選擇（叫賣 / 待機 / 客服）。

    L1 入口流程：
    - 首次進 L1：顯示主選單，商家選 1/2/3
    - subroutine_a 後續 L1：跳過主選單直接進 hawk（連續叫賣，2026-05-26 加）
      涵蓋 4 個出口：dialog reject / dialog timeout / L4 cancel / L5 完成
    """
    entry_invariant = "empty"
    entry_ctx = "進 L1"

    def run(self, machine) -> "Transition | None":
        cb = machine.callbacks
        result = states.run_l1(
            print_terminal=cb["print_terminal"],
            read_terminal_key=cb["read_terminal_key"],
            opencv_dwell_seconds=cb["opencv_dwell_seconds"],
            opencv_disable=cb["opencv_disable"],
            opencv_enable=cb["opencv_enable"],
            speak=cb["speak"],
            do_action=cb["do_action"],
            exit_program=cb["exit_program"],
            schedule=cb["schedule"],
            show_hawk_help=cb["show_hawk_help"],
            enter_hawk_immediately=machine.enter_hawk_immediately,
        )
        machine.enter_hawk_immediately = False  # 消費後 reset；下次需重設才會跳選單
        if result is None:
            return None
        # result == "L2" — 進 dialog 層
        return Transition("dialog")


class DialogState(State):
    """dialog 對話層（L2/L3 合一，2026-05-25 B 方案）。"""
    entry_invariant = "empty"
    entry_ctx = "進 dialog"

    def run(self, machine) -> "Transition | None":
        cb = machine.callbacks
        next_state, _think = states.run_dialog(
            speak=cb["speak"],
            print_terminal=cb["print_terminal"],
            read_customer_input=cb["read_customer_input"],
            cart=machine.cart,
            think_count=0,
            opencv_disable=cb["opencv_disable"],
            do_action=cb["do_action"],
            speak_and_wait=cb["speak_and_wait"],
            display=cb.get("display"),
        )
        if next_state == "L1_via_subroutine_a":
            _assert_cart_empty(machine.cart, "dialog 退出後（dialog A 已視情況清 cart）")
            return Transition("l1", via_subroutine_a=True)
        # next_state == "L4"
        return Transition("l4")


class L4State(State):
    """L4 印金額 + 等掃碼（結帳層）。"""
    entry_invariant = "nonempty"
    entry_ctx = "進 L4"

    def run(self, machine) -> "Transition | None":
        cb = machine.callbacks
        next_state, _, _ = states.run_l4(
            speak=cb["speak"],
            print_terminal=cb["print_terminal"],
            read_customer_input=cb["read_customer_input"],
            cart=machine.cart,
            opencv_disable=cb["opencv_disable"],
            do_action=cb["do_action"],
            speak_and_wait=cb["speak_and_wait"],
        )
        if next_state == "L1_via_subroutine_a":
            # L4 非 L5 路徑必清 cart（_l4_exit_to_l1 兩呼叫點 / _l4_service_mode 退出三條
            # 皆 clear_cart；掃碼 → L5 走 elif 分支由 L5 自身 clear，不踩此 assert）
            # （2026-05-26 P3.C 修訂：原「L4-B/C/D 已清 cart」漏列 _l4_service_mode 掃碼→L5 路徑）
            _assert_cart_empty(machine.cart, "L4 非掃碼退出後（L4 三條清 cart 路徑）")
            return Transition("l1", via_subroutine_a=True)
        # next_state == "L5"
        return Transition("l5")


class L5State(State):
    """L5 謝謝惠顧（致謝層，從 L4-A 帶 cart）。"""
    entry_invariant = "nonempty"
    entry_ctx = "進 L5（從 L4-A 帶 cart）"

    def run(self, machine) -> "Transition | None":
        cb = machine.callbacks
        states.run_l5(
            cart=machine.cart,
            sleep=cb["sleep"],
            do_action=cb["do_action"],
        )  # 回傳值無條件忽略（L5 後恆走 subroutine_a 回 L1）
        _assert_cart_empty(machine.cart, "L5 退出後（L5 應已清 cart）")
        return Transition("l1", via_subroutine_a=True)


class SalesMachine:
    """L1→dialog→L4→L5 主迴圈：持 cart + callbacks + enter_hawk 旗號；每次進狀態先驗 cart invariant。

    等價性（invariant 檢查時點 vs 現行 logic）：進每層前 assert 放主迴圈進場、
    「L1_via_subroutine_a 返回後」assert 放各 State 的轉移分支——時序與現行逐一對應：
    dialog/L4 退出 assert 在 sub_a 之前、L5 後 assert 在 sub_a 之前。
    子例程 A 簡化（2026-05-25：只 mute 12s 緩衝，不再 unmute / 不再叫賣）。
    """
    def __init__(self, callbacks: dict, cart):
        self.callbacks = callbacks          # logic.run 收到的 callback（含 speak_and_wait）
        self.cart = cart
        self.enter_hawk_immediately = False
        self._states = {
            "l1": L1State(),
            "dialog": DialogState(),
            "l4": L4State(),
            "l5": L5State(),
        }

    def _emit(self, current: str) -> None:
        """進每層時 emit phase 轉移 + cart 快照給 web display 回呼（終端模式 display=None 不觸發）。

        cart 傳 dict 拷貝避免跨執行緒看到後續突變；paid 僅 l5（thankyou）帶
        calc_total（在 L5 清 cart 前算）。
        """
        disp = self.callbacks.get("display")
        if disp is None:
            return
        paid = cart_module.calc_total(self.cart) if current == "l5" else 0
        disp(_PHASE_BY_STATE[current], dict(self.cart), paid)

    def run(self) -> None:
        current = "l1"
        while True:
            state = self._states[current]
            if state.entry_invariant == "empty":
                _assert_cart_empty(self.cart, state.entry_ctx)
            elif state.entry_invariant == "nonempty":
                _assert_cart_nonempty(self.cart, state.entry_ctx)
            else:
                raise ValueError(
                    f"未知 entry_invariant：{state.entry_invariant!r}"
                    f"（state={type(state).__name__}）"
                )
            self._emit(current)            # 進場 emit phase（invariant 後、state.run 前）
            result = state.run(self)
            if result is None:
                return None
            if result.via_subroutine_a:
                states.run_subroutine_a(mute_opencv=self.callbacks["mute_opencv"])  # 晚綁定
                self.enter_hawk_immediately = True
            current = result.next_state
