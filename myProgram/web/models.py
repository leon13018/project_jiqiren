"""前後端契約 DTO（Pydantic）。僅在 FastAPI 邊界用 → Windows 不可 import（pydantic 未裝）。"""
from typing import Literal

from pydantic import BaseModel


class Product(BaseModel):
    name: str
    unit: str
    price_now: int
    price_orig: int


class DisplayState(BaseModel):
    phase: Literal["standby", "ordering", "checkout", "thankyou"]
    cart: dict[str, int]
    total: int
    paid: int = 0


class Snapshot(BaseModel):
    catalog: list[Product]
    state: DisplayState
