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

from myProgram.sales.constants import PRODUCTS

# Cart 型別定義：商品名 → 數量
Cart = dict  # dict[str, int]


def new_cart() -> Cart:
    """建立並回傳一個空購物車。"""
    return {}


def add_item(cart: Cart, product: str, qty: int) -> None:
    """加入商品到購物車，同商品累加數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱（需存在於 PRODUCTS）
        qty: 數量（正整數）
    """
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
