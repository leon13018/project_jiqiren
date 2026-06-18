"""display 回呼 web 版：把 (phase, cart, paid) 建成 WS 推送 dict（含後端算的 total）。純 stdlib。"""
from myProgram.sales.constants import PRODUCTS


def make_web_display(bus):
    def display(phase: str, cart: dict, paid: int = 0) -> None:
        try:
            total = sum(PRODUCTS[name]["實際"] * qty for name, qty in cart.items())
            bus.publish({"phase": phase, "cart": dict(cart), "total": total, "paid": paid})
        except Exception:
            pass   # spec 錯誤處理：web 掛了機器人照常服務客人，display 不得拖垮對話執行緒
    return display
