"""web/commands.to_token 純映射行為（Windows pytest；不 import fastapi/pydantic）。"""
from myProgram.web.commands import to_token
from myProgram.sales.constants import KEYWORDS_CONFIRM_YES
from myProgram.sales.product_parser import parse_products
from myProgram.sales.nlu import classify_intent


def test_wake_maps_to_c():
    assert to_token({"type": "wake"}) == "c"


def test_pay_maps_to_s():
    assert to_token({"type": "pay"}) == "s"


def test_order_builds_product_qty_token():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": 3}) == "冰紅茶3"


def test_order_token_parses_back_to_product_qty():
    """守 token 格式：產出的字串必須被既有 product_parser 正解回 (商品, 數量)。"""
    token = to_token({"type": "order", "item": "刮刮樂", "qty": 2})
    assert parse_products(token) == [("刮刮樂", 2)]


def test_checkout_token_triggers_l3_checkout_intent():
    # 驗實際消費路徑：L3 主迴圈 classify_intent(token,"normal") 須判「結帳」。
    # （原測試驗 membership in KEYWORDS_C2_CHECKOUT —— 那是 C-2 子狀態才比對的集，
    #  非主迴圈 dispatch 走的路徑，故漏抓「結賬/賬」對主路徑無效的 bug。）
    assert classify_intent(to_token({"type": "checkout"}), "normal") == "結帳"


def test_confirm_token_is_member_of_keyword_set():
    assert to_token({"type": "confirm"}) in KEYWORDS_CONFIRM_YES


def test_unknown_type_returns_none():
    assert to_token({"type": "bogus"}) is None


def test_missing_type_returns_none():
    assert to_token({}) is None


def test_non_dict_returns_none():
    assert to_token("冰紅茶3") is None
    assert to_token(None) is None
    assert to_token(["order"]) is None


def test_order_invalid_product_returns_none():
    assert to_token({"type": "order", "item": "珍奶", "qty": 2}) is None


def test_order_missing_item_or_qty_returns_none():
    assert to_token({"type": "order", "qty": 2}) is None
    assert to_token({"type": "order", "item": "冰紅茶"}) is None


def test_order_nonpositive_qty_returns_none():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": 0}) is None
    assert to_token({"type": "order", "item": "冰紅茶", "qty": -1}) is None


def test_order_non_int_qty_returns_none():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": "3"}) is None
    # bool 是 int 子型別（True==1）→ 須明確擋掉，避免 {"qty": true} 變成 "冰紅茶1"
    assert to_token({"type": "order", "item": "冰紅茶", "qty": True}) is None
