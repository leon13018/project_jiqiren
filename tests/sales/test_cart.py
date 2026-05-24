"""test_cart.py — 測試 myProgram/sales/cart.py。

對應 BDD scenarios：
    - L0-CART-001：新建 cart 為空容器
    - L0-CART-002：加入單一商品後 cart 含該商品與數量
    - L0-CART-003：重複加入同商品時數量累加而非 append 新條目
    - L0-CART-004：單品總額正確計算（含九折）
    - L0-CART-005：多品總額正確計算
    - L0-CART-006：清空 cart 後容器為空
"""

import myProgram.sales.cart as cart_module


# ============================================================
# L0-CART-001
# ============================================================

## L0-CART-001
### Scenario: 新建 cart 為空容器
### Given 呼叫 cart 工廠新建一個 cart
### When 檢查內容
### Then cart 為空（無任何商品）
def test_cart_new_is_empty() -> None:
    c = cart_module.new_cart()
    assert cart_module.is_empty(c)


# ============================================================
# L0-CART-002
# ============================================================

## L0-CART-002
### Scenario: 加入單一商品後 cart 含該商品與數量
### Given 一個空 cart
### When 加入冰紅茶 ×1
### Then cart 為 {冰紅茶: 1}
def test_cart_add_single_product() -> None:
    c = cart_module.new_cart()
    cart_module.add_item(c, "冰紅茶", 1)
    assert cart_module.get_quantity(c, "冰紅茶") == 1


# ============================================================
# L0-CART-003
# ============================================================

## L0-CART-003
### Scenario: 重複加入同商品時數量累加而非 append 新條目
### Given cart 已有冰紅茶 ×1
### When 再加入冰紅茶 ×1
### Then cart 為 {冰紅茶: 2}（同商品累加，不新增條目）
def test_cart_add_same_product_accumulates_quantity() -> None:
    c = cart_module.new_cart()
    cart_module.add_item(c, "冰紅茶", 1)
    cart_module.add_item(c, "冰紅茶", 1)
    assert cart_module.get_quantity(c, "冰紅茶") == 2


# ============================================================
# L0-CART-004
# ============================================================

## L0-CART-004
### Scenario: 單品總額正確計算（含九折）
### Given cart 為 {冰紅茶: 2}
### When 計算總額
### Then 總額為 54 元（27 × 2）
def test_cart_total_single_product_correct() -> None:
    c = cart_module.new_cart()
    cart_module.add_item(c, "冰紅茶", 2)
    assert cart_module.calc_total(c) == 54


# ============================================================
# L0-CART-005
# ============================================================

## L0-CART-005
### Scenario: 多品總額正確計算
### Given cart 為 {冰紅茶: 1, 刮刮樂: 1}
### When 計算總額
### Then 總額為 207 元（27 + 180）
def test_cart_total_multiple_products_correct() -> None:
    c = cart_module.new_cart()
    cart_module.add_item(c, "冰紅茶", 1)
    cart_module.add_item(c, "刮刮樂", 1)
    assert cart_module.calc_total(c) == 207


# ============================================================
# L0-CART-006
# ============================================================

## L0-CART-006
### Scenario: 清空 cart 後容器為空
### Given cart 為 {冰紅茶: 2, 刮刮樂: 1}
### When 清空 cart
### Then cart 為空（無任何商品）
def test_cart_clear_empties_container() -> None:
    c = cart_module.new_cart()
    cart_module.add_item(c, "冰紅茶", 2)
    cart_module.add_item(c, "刮刮樂", 1)
    cart_module.clear_cart(c)
    assert cart_module.is_empty(c)
