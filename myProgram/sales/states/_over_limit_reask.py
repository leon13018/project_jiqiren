"""超量重問狀態鏈（2026-06-09 加；spec resources/specs/over_limit_reask_2026-06-09_spec.md）。

數量超量 → 不自動 cap，進重問 loop 問到正確數量才加入。對齊 _cancel_confirm /
_service_confirm 風格：callback 注入、不 import 廠商 SDK、對 cart in-place。即時提交
模型——有效數量立即 add_item，pending list 只含仍超量商品名。

兩 public helper：
    over_limit_reask        — 重問主 loop（12s budget + 最多 2 reset）
    over_limit_cancel_confirm — 「取消超量商品 vs 退出交易」二選一（6s，保守 default 保 cart）
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    MAX_QTY_PER_ITEM,
    OVER_LIMIT_REASK_TIMEOUT,
    OVER_LIMIT_MAX_RESETS,
    OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT,
    OVER_LIMIT_REASK_SINGLE_TEMPLATE,
    OVER_LIMIT_REASK_MULTI_TEMPLATE,
    OVER_LIMIT_UNCLEAR_PREFIX,
    OVER_LIMIT_CANCEL_CONFIRM_PROMPT,
    KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER,
    KEYWORDS_OVER_LIMIT_CONTINUE,
    KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT,
    KEYWORDS_OVER_LIMIT_EXIT,
    KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT,
)
from myProgram.sales.nlu import (
    has_quantity, parse_quantity, classify_intent,
    contains_any, equals_strict_short,
)
from myProgram.sales.product_parser import parse_products
from myProgram.sales import cart as cart_module
from myProgram.sales.states._cancel_confirm import is_cancel_intent
from myProgram.sales.states._service_confirm import service_confirm


def over_limit_cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> str:
    """「取消超量商品繼續 vs 退出交易」二選一 6s 子狀態。

    Returns:
        "cancel_overlimit" — 取消超量商品、保留其他、繼續（CONTINUE keyword / silent / 亂答耗盡）
        "exit"             — 退出交易（純 EXIT keyword）

    check 順序 CONTINUE 先於 EXIT：保守原則，任何含「取消/繼續」→ 保 cart；
    唯純「退出/離開」才 exit。timeout / silent / 亂答耗盡 → cancel_overlimit（保 cart）。
    """
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    _speak_blocking(OVER_LIMIT_CANCEL_CONFIRM_PROMPT)
    deadline = time.monotonic() + OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "cancel_overlimit"
        response = read_customer_input(timeout=remaining)
        if response is None:
            return "cancel_overlimit"
        if (contains_any(response, KEYWORDS_OVER_LIMIT_CONTINUE)
                or equals_strict_short(response, KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT)):
            return "cancel_overlimit"
        if (contains_any(response, KEYWORDS_OVER_LIMIT_EXIT)
                or equals_strict_short(response, KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT)):
            return "exit"
        _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + OVER_LIMIT_CANCEL_CONFIRM_PROMPT)


def _join_names(names: list) -> str:
    """商品名連接：1 個直接回；≥2 個用「、」連、末項前用「和」。"""
    if len(names) == 1:
        return names[0]
    return "、".join(names[:-1]) + "和" + names[-1]


def _format_over_limit_prompt(pending: list, cart) -> str:
    """組超量重問 prompt。remaining = MAX_QTY_PER_ITEM - cart 既有量（cart 空時即 50）。"""
    if len(pending) == 1:
        p = pending[0]
        unit = PRODUCTS[p]["單位"]
        remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)
        return OVER_LIMIT_REASK_SINGLE_TEMPLATE.format(product=p, remaining=remaining, unit=unit)
    products = _join_names(pending)
    details = "、".join(
        f"{MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)} {PRODUCTS[p]['單位']}"
        for p in pending
    )
    return OVER_LIMIT_REASK_MULTI_TEMPLATE.format(products=products, details=details)


def _apply_quantities(response: str, pending: list, cart) -> None:
    """把 response 內可解析數量 apply 到 pending 商品（in-place 改 pending / cart）。

    有效（0 < qty <= remaining）→ add_item + 從 pending 移除；超量 / <=0 → 留在 pending。
    多 pending 用 parse_products（需商品名）；單 pending 額外接受 bare number（parse_quantity）。
    """
    parsed = parse_products(response)
    parsed_names = {product for product, _ in parsed}
    for product, qty in parsed:
        if product in pending and qty is not None:
            remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
            if 0 < qty <= remaining:
                cart_module.add_item(cart, product, qty)
                pending.remove(product)
    # 單 pending 且顧客報 bare number（response 無提及該商品名 → parse_products 未 cover）。
    # 若 response 已含商品名（parsed_names 命中），則上方已處理，不可用 parse_quantity
    # 把句中其他數字（如另一商品的超量值）誤套到 bare-number fallback。
    if len(pending) == 1 and pending[0] not in parsed_names and has_quantity(response):
        product = pending[0]
        qty = parse_quantity(response)
        remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
        if 0 < qty <= remaining:
            cart_module.add_item(cart, product, qty)
            pending.remove(product)


def over_limit_reask(
    pending: list,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    speak_and_wait=None,
) -> str:
    """超量重問主 loop（12s budget + 最多 OVER_LIMIT_MAX_RESETS 次 reset）。

    Args:
        pending: 仍超量商品名 list（in-place 縮減；有效答案 add_item 後移除）。

    Returns:
        "resolved"        — pending 全部進範圍（皆已 add_item 進 cart）
        "reenter_timeout" — 倒數歸零 / silent / 客服 NO（caller 重 speak entry + continue）
        "reenter_cancel"  — 否定 → 二選一選「取消超量商品繼續」
        "exit_l1"         — 否定 → 二選一選「退出」（caller 走 _dialog_exit_a）
    """
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    resets_left = OVER_LIMIT_MAX_RESETS
    _speak_blocking(_format_over_limit_prompt(pending, cart))
    deadline = time.monotonic() + OVER_LIMIT_REASK_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "reenter_timeout"
        response = read_customer_input(timeout=remaining)
        if response is None:
            return "reenter_timeout"

        # (1) 否定 → 二選一
        if (is_cancel_intent(response)
                or contains_any(response, KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER)):
            if over_limit_cancel_confirm(speak, read_customer_input, speak_and_wait) == "exit":
                return "exit_l1"
            return "reenter_cancel"

        # (2) 客服 → service_confirm（暫停 + 補償）
        if classify_intent(response, "normal") == "客服":
            paused = time.monotonic()
            result = service_confirm(
                speak=speak, print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                speak_and_wait=speak_and_wait, allow_scan=False,
            )
            deadline += time.monotonic() - paused
            if result == "yes":
                _speak_blocking(_format_over_limit_prompt(pending, cart))
                continue
            return "reenter_timeout"

        # (3) 數量答案
        if has_quantity(response):
            _apply_quantities(response, pending, cart)
            if not pending:
                return "resolved"
            if resets_left > 0:
                resets_left -= 1
                deadline = time.monotonic() + OVER_LIMIT_REASK_TIMEOUT
            _speak_blocking(_format_over_limit_prompt(pending, cart))
            continue

        # (4) 亂答 → 提示，不重置
        _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + _format_over_limit_prompt(pending, cart))
