#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
import re
import threading
import time

import ActionGroupControl as Act
import robot_actions as ra
from screen_display import POSScreen
from tts import say

# ── 全域狀態 ───────────────────────────────────────────────────
screen        = POSScreen()
has_customer  = False

MAX_TURNS = 10
PAY_URL   = "https://pay.example.com/demo"

# 雙 queue：input_reader 視 has_customer 分流
cmd_queue      = queue.Queue()   # y / q 指令
customer_queue = queue.Queue()   # 顧客輸入文字

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


# ── Action Worker（中斷式）────────────────────────────────────
class ActionWorker:
    def __init__(self):
        self._q = queue.Queue()
        self._cancel = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def do(self, fn, *args, **kwargs):
        """非阻塞：終止當前動作 + 清空 queue + 入新任務。"""
        self._cancel.set()
        try:
            Act.stopAction()
            Act.stopActionGroup()
        except Exception:
            pass
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put((fn, args, kwargs))

    def _loop(self):
        while True:
            fn, args, kwargs = self._q.get()
            self._cancel.clear()
            try:
                fn(*args, cancel=self._cancel, **kwargs)
            except ra._Cancelled:
                pass
            except Exception as e:
                print(f"[動作] 失敗：{e}")


action_worker = ActionWorker()


# ── Input Reader（永久讀 stdin → 雙 queue 分流）─────────────
def input_reader():
    while True:
        try:
            line = input()
        except EOFError:
            break
        line = line.strip()
        if not line:
            continue
        if has_customer:
            customer_queue.put(line)
        else:
            cmd_queue.put(line)


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


# ── 顧客輸入（從 customer_queue 拿，帶 timeout）─────────────
def get_customer_input(prompt: str, timeout: int = 12) -> str:
    print(prompt, end='', flush=True)
    try:
        return customer_queue.get(timeout=timeout)
    except queue.Empty:
        return ""


# ── 叫賣模式（dialogue 背景循環）────────────────────────────
def hawking_loop():
    while True:
        if not has_customer:
            action_worker.do(ra.action_idle)
            say("來喔！冰紅茶27元、刮刮樂180元，全場九折，走過路過不要錯過！")
            for _ in range(10):
                if has_customer:
                    break
                time.sleep(1)
        else:
            time.sleep(0.3)


# ── 加完商品後的等待邏輯 ──────────────────────────────────────
def wait_after_order(items: list, total: int):
    """回傳 "checkout" / "exit" / 新顧客話"""
    while True:
        response = get_customer_input("顧客說：", timeout=10)

        if not response:
            if not items:
                say("沒聽到你說話，歡迎下次光臨！")
                return "exit"
            say("由於沒有回復，我將幫你進行結賬，請問是嗎？")
            confirm = get_customer_input("顧客說：", timeout=10)
            if not confirm:
                return "checkout"
            if any(kw in confirm.lower() for kw in YES_KEYWORDS):
                return "checkout"
            say("好的，請慢慢想，需要再叫我！")
            continue

        lower = response.lower()

        if any(kw in lower for kw in CHECKOUT_KEYWORDS):
            return "checkout"

        if any(kw in response for kw in THINKING_KEYWORDS):
            say("好的，慢慢想，需要再叫我！")
            continue

        return response


# ── 結帳流程 ───────────────────────────────────────────────────
def do_checkout(items: list, total: int):
    say(f"好的，總共{total}元，這邊掃碼付款喔！")
    screen.schedule(lambda: screen.update_order(items, total, PAY_URL))
    action_worker.do(ra.action_pay)
    time.sleep(3)
    say("謝謝惠顧，歡迎再度光臨！")


# ── 顧客服務流程（dialogue thread）─────────────────────────
def customer_mode():
    global has_customer

    items           = []
    total           = 0
    pending_product = None

    screen.schedule(screen.show_welcome)
    action_worker.do(ra.action_greet)
    say("歡迎光臨！冰紅茶27元、刮刮樂180元，全場九折。請問要什麼？")

    for _ in range(MAX_TURNS):
        user_input = get_customer_input("顧客說：", timeout=12)

        if not user_input:
            if items:
                do_checkout(items, total)
            else:
                say("沒聽到你說話，歡迎下次光臨！")
            break

        lower = user_input.lower()

        if any(kw in lower for kw in CHECKOUT_KEYWORDS):
            if items:
                do_checkout(items, total)
            else:
                say("好的，歡迎下次光臨！")
            break

        if any(kw in user_input for kw in PRICE_KEYWORDS):
            say("冰紅茶27元、刮刮樂180元，全場九折喔！")
            pending_product = None
            continue

        product = detect_product(user_input)
        qty     = detect_qty(user_input)

        if product and qty:
            price = item_price(product, qty)
            items.append({"name": product, "qty": qty, "price": price})
            total = sum(i["price"] for i in items)
            pending_product = None
            action_worker.do(ra.nod_head)
            screen.schedule(lambda it=list(items), t=total: screen.update_order(it, t, ""))
            say(f"好的，{product}×{qty}，共{price}元！請問還需要其他嗎？")
            result = wait_after_order(items, total)
            if result == "checkout":
                do_checkout(items, total)
                break
            elif result == "exit":
                break
            else:
                user_input = result

        elif product and not qty:
            pending_product = product
            say(f"好的，{product}要幾個？")

        elif qty and pending_product:
            price = item_price(pending_product, qty)
            items.append({"name": pending_product, "qty": qty, "price": price})
            total = sum(i["price"] for i in items)
            action_worker.do(ra.nod_head)
            screen.schedule(lambda it=list(items), t=total: screen.update_order(it, t, ""))
            say(f"好的，{pending_product}×{qty}，共{price}元！請問還需要其他嗎？")
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
            say("請問要冰紅茶還是刮刮樂呢？")

    else:
        if items:
            do_checkout(items, total)
        else:
            say("歡迎下次光臨！")

    action_worker.do(ra.look_forward)
    screen.schedule(screen.show_welcome)
    has_customer = False


# ── 指令分派（cmd_queue → y / q）──────────────────────────
def command_dispatcher():
    global has_customer
    while True:
        line = cmd_queue.get()
        cmd = line.lower()
        if cmd == 'q':
            # 切回主線程關閉 tkinter
            screen.root.after(0, screen.close)
            break
        elif cmd == 'y' and not has_customer:
            has_customer = True
            threading.Thread(target=customer_mode, daemon=True).start()


# ── 主程式 ─────────────────────────────────────────────────────
def main():
    print("=" * 40)
    print("指令：y = 偵測到顧客，q = 退出")
    print("=" * 40)

    threading.Thread(target=input_reader, daemon=True).start()
    threading.Thread(target=hawking_loop, daemon=True).start()
    threading.Thread(target=command_dispatcher, daemon=True).start()

    screen.root.mainloop()
    print("程式結束。")


if __name__ == "__main__":
    main()
