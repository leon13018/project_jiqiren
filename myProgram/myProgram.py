#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

# ── 商品目錄 ───────────────────────────────────────────────────
PRODUCTS = {
    "冰紅茶": {
        "price":    30,
        "discount": 0.9,
        "keywords": ["紅茶", "冰紅茶", "hong cha", "tea", "red tea"],
    },
    "刮刮樂": {
        "price":    200,
        "discount": 0.9,
        "keywords": ["刮刮樂", "刮刮", "彩券", "lottery", "scratch"],
    },
}

# ── 意圖關鍵字 ─────────────────────────────────────────────────
CHECKOUT_KEYWORDS = [
    "結帳", "買單", "付款", "掃碼", "不用了", "再見", "掰掰",
    "不用", "不要", "夠了", "就這樣", "沒有了", "好了",
    "no", "nope", "done",
]

PRICE_KEYWORDS = ["多少", "幾元", "幾錢", "價格", "price", "how much", "貴不貴"]

THINKING_KEYWORDS = ["想一下", "等一下", "等等", "考慮", "想想", "稍等", "wait", "hold on"]

YES_KEYWORDS = ["是", "yes", "ok", "好", "對", "繼續", "確認"]

QTY_MAP = {
    "一": 1, "兩": 2, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


# ── 辨識工具 ───────────────────────────────────────────────────
def detect_product(text: str):
    lower = text.lower()
    for name, info in PRODUCTS.items():
        if any(kw.lower() in lower for kw in info["keywords"]):
            return name
    return None


def detect_qty(text: str):
    m = re.search(r"\d+", text)
    if m:
        return int(m.group())
    m = re.search(r"[一兩二三四五六七八九十]", text)
    if m:
        return QTY_MAP.get(m.group(), 1)
    return None


def item_price(name: str, qty: int) -> int:
    p = PRODUCTS[name]
    return round(p["price"] * qty * p["discount"])


# ── 結帳流程 ───────────────────────────────────────────────────
def do_checkout(items: list):
    if not items:
        print("好的，歡迎下次光臨！")
        return
    total = sum(item["price"] for item in items)
    print("─" * 30)
    for item in items:
        print(f"  {item['name']} ×{item['qty']} = {item['price']} 元")
    print("─" * 30)
    print(f"總共 {total} 元，這邊掃碼付款喔！")
    print("謝謝惠顧，歡迎再度光臨！")


# ── 顧客服務流程 ───────────────────────────────────────────────
def customer_session():
    items           = []
    pending_product = None

    print("歡迎光臨！冰紅茶27元、刮刮樂180元，全場九折。")

    while True:
        text = input("顧客說：").strip()
        if not text:
            continue

        lower = text.lower()

        if any(kw in lower for kw in CHECKOUT_KEYWORDS):
            break

        if any(kw in lower for kw in PRICE_KEYWORDS):
            print("冰紅茶27元、刮刮樂180元，全場九折喔！")
            pending_product = None
            continue

        if any(kw in text for kw in THINKING_KEYWORDS):
            print("好的，慢慢想，需要再叫我！")
            continue

        product = detect_product(text)
        qty     = detect_qty(text)

        if product and qty:
            price = item_price(product, qty)
            items.append({"name": product, "qty": qty, "price": price})
            pending_product = None
            print(f"好的，{product}×{qty}，共{price}元！請問還需要其他嗎？")

        elif product and not qty:
            pending_product = product
            print(f"好的，{product}要幾個？")

        elif qty and pending_product:
            price = item_price(pending_product, qty)
            items.append({"name": pending_product, "qty": qty, "price": price})
            print(f"好的，{pending_product}×{qty}，共{price}元！請問還需要其他嗎？")
            pending_product = None

        else:
            print("請問要冰紅茶還是刮刮樂呢？")

    do_checkout(items)


# ── 主程式 ─────────────────────────────────────────────────────
def main():
    print("=" * 40)
    print("指令：y = 開始顧客流程，q = 退出")
    print("=" * 40)

    while True:
        cmd = input("輸入 y 開始顧客流程, q 退出: ").strip().lower()
        if cmd == 'q':
            break
        if cmd == 'y':
            customer_session()

    print("程式結束。")


if __name__ == "__main__":
    main()
