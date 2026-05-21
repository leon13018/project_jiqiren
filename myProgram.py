#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import select
import time
import threading
import re
import robot_actions as ra
from screen_display import POSScreen

# ── 全域狀態 ───────────────────────────────────────────────────
screen            = POSScreen()
has_customer      = False
waiting_for_order = False

MAX_TURNS = 10
PAY_URL   = "https://pay.example.com/demo"

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


# ── 語音輸出（之後換 Piper TTS）──────────────────────────────
def speak(text: str):
    print(f"[語音] {text}")


# ── 叫賣模式（後台循環）────────────────────────────────────────
def hawking_loop():
    while True:
        if not has_customer:
            ra.action_idle()
            speak("來喔！冰紅茶27元、刮刮樂180元，全場九折，走過路過不要錯過！")
            for _ in range(10):
                if has_customer:
                    break
                time.sleep(1)
        else:
            time.sleep(0.3)


# ── 讀取顧客輸入（之後換 Whisper.cpp）──────────────────────
def get_customer_input(prompt: str, timeout: int = 12) -> str:
    global waiting_for_order
    result = [None]

    def ask():
        result[0] = input(prompt).strip()

    waiting_for_order = True
    t = threading.Thread(target=ask, daemon=True)
    t.start()
    t.join(timeout=timeout)
    waiting_for_order = False
    return result[0] or ""


# ── 加完商品後的等待邏輯 ──────────────────────────────────────
def wait_after_order(items: list, total: int):
    """
    說完「請問還需要其他嗎？」後呼叫。
    回傳值：
        "checkout" → 進入結帳
        "exit"     → 無商品，退出顧客模式
        str        → 顧客說的話，回到主迴圈繼續處理
    """
    while True:
        response = get_customer_input("顧客說：", timeout=10)

        if not response:
            # 逾時無回應
            if not items:
                speak("沒聽到你說話，歡迎下次光臨！")
                return "exit"
            # 有商品 → 詢問是否結帳
            speak("由於沒有回復，我將幫你進行結賬，請問是嗎？")
            confirm = get_customer_input("顧客說：", timeout=10)
            if not confirm:
                return "checkout"   # 再次逾時 → 直接結帳
            if any(kw in confirm.lower() for kw in YES_KEYWORDS):
                return "checkout"
            else:
                speak("好的，請慢慢想，需要再叫我！")
                continue            # 繼續等待

        lower = response.lower()

        if any(kw in lower for kw in CHECKOUT_KEYWORDS):
            return "checkout"

        if any(kw in response for kw in THINKING_KEYWORDS):
            speak("好的，慢慢想，需要再叫我！")
            continue                # 再等 10 秒

        return response             # 新的點餐輸入，回主迴圈處理


# ── 結帳流程 ───────────────────────────────────────────────────
def do_checkout(items: list, total: int):
    speak(f"好的，總共{total}元，這邊掃碼付款喔！")
    screen.schedule(lambda: screen.update_order(items, total, PAY_URL))
    ra.action_pay()
    time.sleep(3)
    speak("謝謝惠顧，歡迎再度光臨！")


# ── 顧客服務流程 ───────────────────────────────────────────────
def customer_mode():
    global has_customer

    items           = []
    total           = 0
    pending_product = None   # 已知商品，等數量

    screen.schedule(screen.show_welcome)
    ra.action_greet()
    speak("歡迎光臨！冰紅茶27元、刮刮樂180元，全場九折。請問要什麼？")

    for _ in range(MAX_TURNS):
        user_input = get_customer_input("顧客說：", timeout=12)

        # 逾時無輸入
        if not user_input:
            if items:
                do_checkout(items, total)
            else:
                speak("沒聽到你說話，歡迎下次光臨！")
            break

        lower = user_input.lower()

        # ── 結帳意圖 ──────────────────────────────────────────
        if any(kw in lower for kw in CHECKOUT_KEYWORDS):
            if items:
                do_checkout(items, total)
            else:
                speak("好的，歡迎下次光臨！")
            break

        # ── 價格查詢 ──────────────────────────────────────────
        if any(kw in user_input for kw in PRICE_KEYWORDS):
            speak("冰紅茶27元、刮刮樂180元，全場九折喔！")
            pending_product = None
            continue

        product = detect_product(user_input)
        qty     = detect_qty(user_input)

        if product and qty:
            price = item_price(product, qty)
            items.append({"name": product, "qty": qty, "price": price})
            total = sum(i["price"] for i in items)
            pending_product = None
            ra.nod_head()
            screen.schedule(lambda it=items, t=total: screen.update_order(it, t, ""))
            speak(f"好的，{product}×{qty}，共{price}元！請問還需要其他嗎？")
            result = wait_after_order(items, total)
            if result == "checkout":
                do_checkout(items, total)
                break
            elif result == "exit":
                break
            else:
                user_input = result   # 繼續用這個輸入跑下一輪

        elif product and not qty:
            pending_product = product
            speak(f"好的，{product}要幾個？")

        elif qty and pending_product:
            price = item_price(pending_product, qty)
            items.append({"name": pending_product, "qty": qty, "price": price})
            total = sum(i["price"] for i in items)
            ra.nod_head()
            screen.schedule(lambda it=items, t=total: screen.update_order(it, t, ""))
            speak(f"好的，{pending_product}×{qty}，共{price}元！請問還需要其他嗎？")
            pending_product = None
            result = wait_after_order(items, total)
            if result == "checkout":
                do_checkout(items, total)
                break
            elif result == "exit":
                break
            else:
                user_input = result

        else:
            pending_product = None
            speak("請問要冰紅茶還是刮刮樂呢？")

    else:
        # 超過最大輪數
        if items:
            do_checkout(items, total)
        else:
            speak("歡迎下次光臨！")

    ra.look_forward()
    screen.schedule(screen.show_welcome)
    has_customer = False


# ── 主程式 ─────────────────────────────────────────────────────
def main():
    global has_customer

    threading.Thread(target=hawking_loop, daemon=True).start()
    print("=" * 40)
    print("指令：y = 偵測到顧客，q = 退出")
    print("=" * 40)

    while True:
        if not waiting_for_order and select.select([sys.stdin], [], [], 0.05)[0]:
            cmd = sys.stdin.readline().strip().lower()
            if cmd == 'q':
                break
            elif cmd == 'y' and not has_customer:
                has_customer = True
                threading.Thread(target=customer_mode, daemon=True).start()
        else:
            time.sleep(0.05)

        screen.root.update()

    screen.close()
    print("程式結束。")


if __name__ == "__main__":
    main()
