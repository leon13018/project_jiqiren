"""無效數量重問狀態鏈（2026-06-09 加；spec resources/specs/invalid_qty_reask_2026-06-09_spec.md）。

數量無效（超量 / 為 0）→ 不自動 cap / skip，進重問 loop 問到合法數量才加入。對齊
_cancel_confirm / _service_confirm 風格：callback 注入、不 import 廠商 SDK、對 cart
in-place。即時提交模型——有效數量立即 add_item，pending（dict：product→reason，
reason ∈ {"over_limit","zero"}）只含仍無效商品。

兩 public helper：
    invalid_qty_reask         — 重問主 loop（12s budget + 最多 2 reset）
    invalid_qty_cancel_confirm — 「取消這些商品 vs 退出交易」二選一（6s，保守 default 保 cart）
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    INVALID_QTY_REASK_TIMEOUT,
    INVALID_QTY_MAX_RESETS,
    INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE,
    INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE,
    INVALID_QTY_ZERO_TEMPLATE,
    INVALID_QTY_UNCLEAR_PREFIX,
    KEYWORDS_INVALID_QTY_CANCEL_TRIGGER,
)
from myProgram.sales.nlu import has_quantity, parse_quantity, classify_intent
from myProgram.sales.constants.keyword_group import contains_any
from myProgram.sales.product_parser import parse_products
from myProgram.sales import cart as cart_module
from myProgram.sales.dialog_io import DialogIO
from myProgram.sales.states._cancel_confirm import is_cancel_intent
from myProgram.sales.states._timed_confirm import SERVICE_CONFIRM, INVALID_QTY_CANCEL_CONFIRM


def invalid_qty_cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> str:
    """「取消這些商品繼續 vs 退出交易」二選一 6s 子狀態（facade，委派 INVALID_QTY_CANCEL_CONFIRM 單例）。

    Returns:
        "cancel_overlimit" — 取消無效數量商品、保留其他、繼續（CONTINUE keyword / silent / 亂答耗盡）
        "exit"             — 退出交易（純 EXIT keyword）

    行為規約見 _timed_confirm.InvalidQtyCancelConfirm（CONTINUE 先於 EXIT、亂答帶前綴重播、
    timeout/silent→cancel_overlimit 保 cart）。
    """
    io = DialogIO(speak=speak, read_customer_input=read_customer_input, speak_and_wait=speak_and_wait)
    return INVALID_QTY_CANCEL_CONFIRM.run(io)


def _join_names(names: list) -> str:
    """商品名連接：1 個直接回；≥2 個用「、」連、末項前用「和」。"""
    if len(names) == 1:
        return names[0]
    return "、".join(names[:-1]) + "和" + names[-1]


def _format_invalid_qty_prompt(pending: dict, cart) -> str:
    """組無效數量重問 prompt，依 reason 分組（zero / over_limit）。

    remaining = MAX_QTY_PER_ITEM - cart 既有量（cart 空時即 50）。混合 reason（一句裡
    有 0 也有超量）→ zero 句 + over 句串接成一個 speak（各句以「。」自結）。over-limit 句
    的 single/multi 由 over_products 數量決定（非 total pending）。
    """
    zero_products = [p for p, r in pending.items() if r == "zero"]
    over_products = [p for p, r in pending.items() if r == "over_limit"]
    parts = []
    if zero_products:
        items = "、".join(f"{p}0{PRODUCTS[p]['單位']}" for p in zero_products)
        parts.append(INVALID_QTY_ZERO_TEMPLATE.format(items=items, products=_join_names(zero_products)))
    if over_products:
        if len(over_products) == 1:
            p = over_products[0]
            unit = PRODUCTS[p]["單位"]
            remaining = cart_module.remaining_capacity(cart, p)
            parts.append(INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE.format(product=p, remaining=remaining, unit=unit))
        else:
            products = _join_names(over_products)
            details = "、".join(
                f"{cart_module.remaining_capacity(cart, p)} {PRODUCTS[p]['單位']}"
                for p in over_products
            )
            parts.append(INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE.format(products=products, details=details))
    return "".join(parts)


def _classify_into_pending(product: str, qty: int, pending: dict, cart) -> None:
    """重答後重新分類單一商品：合法→add+del；仍 0→reason=zero；仍超量→reason=over_limit。"""
    verdict = cart_module.classify_qty(cart, product, qty)
    if verdict == "ok":
        cart_module.add_item(cart, product, qty)
        del pending[product]
        return
    # "at_cap" 在 reask 語境不可達（pending 商品於 Pass 1 已保證 remaining>0，
    # 重問期間該商品唯一加量路徑是成功 add — 隨即移出 pending）；
    # 防禦性映射為 "over_limit" 對齊舊 else 分支，不可達態也不改行為
    pending[product] = "over_limit" if verdict == "at_cap" else verdict


def _apply_quantities(response: str, pending: dict, cart) -> None:
    """把 response 內可解析數量 apply 到 pending 商品（in-place 改 pending / cart）。

    對每個提及的 pending 商品重新分類（合法→add+del；仍 0→zero；仍超量→over_limit）。
    多 pending 用 parse_products（需商品名）；單 pending 額外接受 bare number（parse_quantity）。
    """
    parsed = parse_products(response)
    parsed_names = {product for product, _ in parsed}
    for product, qty in parsed:
        if product in pending and qty is not None:
            _classify_into_pending(product, qty, pending, cart)
    # bare-number fallback：唯有 parse_products 完全沒命中任何商品名（response 是真
    # bare number 如「30」/「0」）時，才把 response 當數量套到唯一 pending。若 response 含
    # 任何商品名（parsed_names 非空），上方 loop 已處理；此時不可用 parse_quantity 把
    # 句中其他數字（如顧客只報「刮刮樂5」時的 5）誤套到未被提及的另一 pending 商品。
    if len(pending) == 1 and not parsed_names and has_quantity(response):
        product = next(iter(pending))
        _classify_into_pending(product, parse_quantity(response), pending, cart)


def invalid_qty_reask(
    pending: dict,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    speak_and_wait=None,
) -> str:
    """無效數量重問主 loop（12s budget + 最多 INVALID_QTY_MAX_RESETS 次 reset）。

    Args:
        pending: dict{product: reason}，reason ∈ {"over_limit", "zero"}（in-place 縮減；
            有效答案 add_item 後 del；重答仍無效則更新 reason）。

    Returns:
        "resolved"        — pending 全部進範圍（皆已 add_item 進 cart）
        "reenter_timeout" — 倒數歸零 / silent / 客服 NO（caller 重 speak entry + continue）
        "reenter_cancel"  — 否定 → 二選一選「取消這些商品繼續」
        "exit_l1"         — 否定 → 二選一選「退出」（caller 走 DialogSession.exit_a()）
    """
    # 體內建 io 束（含 print_terminal）：本函式是公開簽名（測試直接呼叫），io 在此收束後使用。
    io = DialogIO(
        speak=speak, read_customer_input=read_customer_input,
        print_terminal=print_terminal, speak_and_wait=speak_and_wait,
    )
    resets_left = INVALID_QTY_MAX_RESETS
    io.speak_blocking(_format_invalid_qty_prompt(pending, cart))
    deadline = time.monotonic() + INVALID_QTY_REASK_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "reenter_timeout"
        response = io.read_customer_input(timeout=remaining)
        if response is None:
            return "reenter_timeout"

        # (1) 否定 → 二選一
        if (is_cancel_intent(response)
                or contains_any(response, KEYWORDS_INVALID_QTY_CANCEL_TRIGGER)):
            if INVALID_QTY_CANCEL_CONFIRM.run(io) == "exit":
                return "exit_l1"
            return "reenter_cancel"

        # (2) 客服 → service_confirm（暫停 + 補償）
        if classify_intent(response, "normal") == "客服":
            paused = time.monotonic()
            result = SERVICE_CONFIRM.run(io)
            deadline += time.monotonic() - paused
            if result == "yes":
                io.speak_blocking(_format_invalid_qty_prompt(pending, cart))
                continue
            return "reenter_timeout"

        # (3) 數量答案
        if has_quantity(response):
            _apply_quantities(response, pending, cart)
            if not pending:
                return "resolved"
            if resets_left > 0:
                resets_left -= 1
                deadline = time.monotonic() + INVALID_QTY_REASK_TIMEOUT
            io.speak_blocking(_format_invalid_qty_prompt(pending, cart))
            continue

        # (4) 亂答 → 提示，不重置
        io.speak_blocking(INVALID_QTY_UNCLEAR_PREFIX + _format_invalid_qty_prompt(pending, cart))
