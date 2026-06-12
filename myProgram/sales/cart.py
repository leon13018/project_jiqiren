"""購物車資料模型（S1 v2）。

職責：
    - Cart 資料結構：dict[str, int]（商品名 → 數量）
    - new_cart / add_item / get_quantity / calc_total / clear_cart / is_empty 操作
    - 同商品累加數量（不 append 新條目）

設計原則：
    - 純資料模型，無 IO
    - 未來上資料庫時，這層介面不變，底層改 Repository Pattern 即可
    - 依 PRODUCTS 計算實際價（九折）
"""

from typing import Literal, TypeAlias

from myProgram.sales.constants import PRODUCTS, MAX_QTY_PER_ITEM

# Cart 型別定義：商品名 → 數量
Cart: TypeAlias = dict[str, int]

# classify_qty 回傳值封閉集（對齊 nlu.Intent 的 Literal 風格；typo 由 type checker 守）
QtyVerdict: TypeAlias = Literal["at_cap", "zero", "over_limit", "ok"]


def new_cart() -> Cart:
    """建立並回傳一個空購物車。"""
    return {}


def add_item(cart: Cart, product: str, qty: int) -> None:
    """加入商品到購物車，同商品累加數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱（必須存在於 PRODUCTS，否則 raise AssertionError）
        qty: 數量
            - qty > MAX_QTY_PER_ITEM → raise AssertionError（防天文數字）
            - qty <= 0 → silent skip（不加入也不 raise；對應 Wave 3
              parse_quantity 可能合法回 0 的情境，caller 不必預先 if qty > 0:）
            - 0 < qty <= MAX_QTY_PER_ITEM → 正常加入 cart
    """
    assert product in PRODUCTS, f"未知商品: {product!r}"
    assert qty <= MAX_QTY_PER_ITEM, (
        f"數量超上限: {product} ×{qty} > {MAX_QTY_PER_ITEM}（單筆訂單防護）"
    )
    if qty <= 0:
        return  # silent skip（顧客明確說 0 / 解析異常負數）
    cart[product] = cart.get(product, 0) + qty


def get_quantity(cart: Cart, product: str) -> int:
    """查詢商品在購物車內的數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱

    Returns:
        數量，不存在時回傳 0
    """
    return cart.get(product, 0)


def remaining_capacity(cart: Cart, product: str) -> int:
    """回傳該商品距單筆上限（MAX_QTY_PER_ITEM）的剩餘可加數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱

    Returns:
        MAX_QTY_PER_ITEM - 既有數量（商品不存在時既有量為 0，即回上限值）
    """
    return MAX_QTY_PER_ITEM - get_quantity(cart, product)


def classify_qty(cart: Cart, product: str, qty: int) -> QtyVerdict:
    """數量四分類（perf_w3 F-6 收斂三處手寫副本）。

    判定順序即優先序（對齊 Pass 1 既有行序）：
        "at_cap"     — 該商品 cart 內已達單筆上限（remaining <= 0），與 qty 無關
        "zero"       — qty == 0（顧客明確說 0）
        "over_limit" — qty > 剩餘可加量，或 qty < 0（防衛上游異常負數）
        "ok"         — 0 < qty <= 剩餘可加量
    純分類不動 cart；動作（add / pending / funnel / speak）由 caller 決定。
    """
    remaining = remaining_capacity(cart, product)
    if remaining <= 0:
        return "at_cap"
    if qty == 0:
        return "zero"
    if qty < 0 or qty > remaining:
        return "over_limit"
    return "ok"


def calc_total(cart: Cart) -> int:
    """計算購物車總額（依各商品實際價相加）。

    Args:
        cart: 購物車 dict

    Returns:
        總額（整數元）
    """
    total = 0
    for product, qty in cart.items():
        unit_price = PRODUCTS[product]["實際"]
        total += unit_price * qty
    return total


def clear_cart(cart: Cart) -> None:
    """清空購物車（原地清除）。

    Args:
        cart: 購物車 dict
    """
    cart.clear()


def is_empty(cart: Cart) -> bool:
    """判斷購物車是否為空。

    Args:
        cart: 購物車 dict

    Returns:
        True 表示無任何商品，False 表示有商品
    """
    return len(cart) == 0
