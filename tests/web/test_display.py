from myProgram.web.bus import EventBus
from myProgram.web.display import make_web_display


def test_web_display_builds_dict_with_total():
    bus = EventBus()
    disp = make_web_display(bus)
    disp("ordering", {"冰紅茶": 2, "刮刮樂": 1})          # 27×2 + 180×1 = 234
    st = bus.last_state()
    assert st == {"phase": "ordering", "cart": {"冰紅茶": 2, "刮刮樂": 1}, "total": 234, "paid": 0}


def test_web_display_thankyou_carries_paid():
    bus = EventBus()
    make_web_display(bus)("thankyou", {"冰紅茶": 2}, paid=54)
    assert bus.last_state()["paid"] == 54


def test_web_display_unknown_product_does_not_raise():
    # spec 錯誤處理：web 算 total 遇未知商品名也不得拖垮對話執行緒（吞例外）。
    bus = EventBus()
    make_web_display(bus)("ordering", {"不存在的商品": 3})   # 不 raise；publish 被跳過
    assert bus.last_state() is None
