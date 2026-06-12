"""test_cart.py — 測試 myProgram/sales/cart.py。

對應 BDD scenarios：
    - L0-CART-001：新建 cart 為空容器
    - L0-CART-002：加入單一商品後 cart 含該商品與數量
    - L0-CART-003：重複加入同商品時數量累加而非 append 新條目
    - L0-CART-004：單品總額正確計算（含九折）
    - L0-CART-005：多品總額正確計算
    - L0-CART-006：清空 cart 後容器為空

Wave 4 cart 邊界防護（B6 / B20 / C11）：
    - CART-B6-001：未知商品 raise AssertionError
    - CART-B20-001：qty 超上限 (> 50) raise AssertionError
    - CART-B20-002：qty 等於上限 (= 50) 正常加入
    - CART-B6-002：qty = 0 → silent skip，cart 仍空
    - CART-B6-003：qty 負數 → silent skip，cart 仍空
"""

import pytest

import myProgram.sales.cart as cart_module
from myProgram.sales.cart import new_cart, add_item, remaining_capacity
from myProgram.sales.constants import MAX_QTY_PER_ITEM


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


# ============================================================
# Wave 4 cart 邊界防護（B6 / B20 / C11）
# ============================================================

## CART-B6-001
### Scenario: add_item 對不在 PRODUCTS 內的商品 raise AssertionError
### Given 一個空 cart
### When 嘗試加入「珍珠奶茶」（非 PRODUCTS 商品）×1
### Then raise AssertionError，錯誤訊息含「未知商品」
def test_add_item_未知商品_raises_assertion() -> None:
    """add_item 對不在 PRODUCTS 內的商品 raise AssertionError（防 typo / NLU bug）。"""
    c = new_cart()
    with pytest.raises(AssertionError, match="未知商品"):
        add_item(c, "珍珠奶茶", 1)


## CART-B20-001
### Scenario: add_item 對 qty > MAX_QTY_PER_ITEM raise AssertionError
### Given 一個空 cart
### When 嘗試加入冰紅茶 ×51（超出 MAX_QTY_PER_ITEM = 50）
### Then raise AssertionError，錯誤訊息含「數量超上限」
def test_add_item_qty_超上限_raises_assertion() -> None:
    """add_item 對 qty > MAX_QTY_PER_ITEM raise AssertionError（防天文數字 / STT 雜訊）。"""
    c = new_cart()
    with pytest.raises(AssertionError, match="數量超上限"):
        add_item(c, "冰紅茶", 51)


## CART-B20-002
### Scenario: qty == MAX_QTY_PER_ITEM (50) 應正常加入（邊界值）
### Given 一個空 cart
### When 加入冰紅茶 ×50（恰好等於 MAX_QTY_PER_ITEM）
### Then cart 為 {冰紅茶: 50}，不 raise
def test_add_item_qty_等於上限_passes() -> None:
    """qty == MAX_QTY_PER_ITEM (50) 應通過，邊界值。"""
    c = new_cart()
    add_item(c, "冰紅茶", 50)
    assert c == {"冰紅茶": 50}


## CART-B6-002
### Scenario: qty == 0 → silent skip，cart 仍空
### Given 一個空 cart
### When 加入冰紅茶 ×0（Wave 3 parse_quantity 可能合法回 0）
### Then cart 仍為空，不 raise（silent skip）
def test_add_item_qty_零_silent_skip() -> None:
    """qty == 0（Wave 3 parse_quantity 可能合法回 0）→ silent skip 不加入 cart，不 raise。"""
    c = new_cart()
    add_item(c, "冰紅茶", 0)
    assert c == {}  # cart 仍空


## CART-B6-003
### Scenario: qty < 0 → silent skip，cart 仍空
### Given 一個空 cart
### When 嘗試加入冰紅茶 ×(-1)（解析異常負數）
### Then cart 仍為空，不 raise（silent skip）
def test_add_item_qty_負數_silent_skip() -> None:
    """qty < 0（防解析異常）→ silent skip，不 raise。"""
    c = new_cart()
    add_item(c, "冰紅茶", -1)
    assert c == {}


# ============================================================
# remaining_capacity（quality_fix_w3 #9）
# ============================================================

## CART-REMCAP-001
### Scenario: remaining_capacity = MAX_QTY_PER_ITEM - 既有量
### Given 一個 cart
### When 查詢某商品距單筆上限的剩餘可加數量
### Then 空 cart 回上限值、加量後遞減、達上限回 0
def test_remaining_capacity_tracks_max_qty_per_item() -> None:
    """remaining_capacity = MAX_QTY_PER_ITEM - 既有量；空 cart 回上限、達上限回 0。"""
    cart = new_cart()
    assert remaining_capacity(cart, "冰紅茶") == MAX_QTY_PER_ITEM
    add_item(cart, "冰紅茶", 3)
    assert remaining_capacity(cart, "冰紅茶") == MAX_QTY_PER_ITEM - 3
    add_item(cart, "冰紅茶", MAX_QTY_PER_ITEM - 3)
    assert remaining_capacity(cart, "冰紅茶") == 0


# ============================================================
# perf_w3 F-6：classify_qty 四分類（收斂三處手寫副本的新 helper）
# ============================================================

## CART-CQ-001
### Scenario: 空 cart、合法數量 → "ok"
### Given 一個空 cart
### When 對冰紅茶分類 qty=3（在剩餘容量內）
### Then 回傳 "ok"
def test_classify_qty_ok() -> None:
    c = new_cart()
    assert cart_module.classify_qty(c, "冰紅茶", 3) == "ok"


## CART-CQ-002
### Scenario: qty == 0 → "zero"（顧客明確說 0）
### Given 一個空 cart
### When 對冰紅茶分類 qty=0
### Then 回傳 "zero"
def test_classify_qty_zero() -> None:
    c = new_cart()
    assert cart_module.classify_qty(c, "冰紅茶", 0) == "zero"


## CART-CQ-003
### Scenario: qty 超過剩餘容量 → "over_limit"
### Given cart 內冰紅茶已加到剩餘容量僅 2（MAX_QTY_PER_ITEM - 2）
### When 對冰紅茶分類 qty=3（超過剩餘 2）
### Then 回傳 "over_limit"
def test_classify_qty_over_limit() -> None:
    c = new_cart()
    add_item(c, "冰紅茶", MAX_QTY_PER_ITEM - 2)
    assert cart_module.classify_qty(c, "冰紅茶", 3) == "over_limit"


## CART-CQ-004
### Scenario: cart 已達上限 → "at_cap" 最高優先（與 qty 無關，含 qty==0）
### Given cart 內冰紅茶已達單筆上限（remaining == 0）
### When 對冰紅茶分別分類 qty=0 與 qty=1
### Then 兩者皆回傳 "at_cap"（at_cap 優先於 zero，與 qty 無關）
def test_classify_qty_at_cap_overrides_zero() -> None:
    c = new_cart()
    add_item(c, "冰紅茶", MAX_QTY_PER_ITEM)
    assert cart_module.classify_qty(c, "冰紅茶", 0) == "at_cap"
    assert cart_module.classify_qty(c, "冰紅茶", 1) == "at_cap"


## CART-CQ-005
### Scenario: 邊界 — qty 恰等於剩餘容量 → "ok"
### Given cart 內冰紅茶已加到剩餘容量恰為 5（MAX_QTY_PER_ITEM - 5）
### When 對冰紅茶分類 qty=5（恰等於剩餘容量）
### Then 回傳 "ok"（邊界值在範圍內）
def test_classify_qty_boundary_exact_remaining() -> None:
    c = new_cart()
    add_item(c, "冰紅茶", MAX_QTY_PER_ITEM - 5)
    assert cart_module.classify_qty(c, "冰紅茶", 5) == "ok"
