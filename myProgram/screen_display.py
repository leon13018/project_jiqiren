#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
import tkinter as tk
from PIL import ImageTk
import qrcode

class POSScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("叫賣機器人收款助手")
        self.root.geometry("600x400")
        self.root.configure(bg='white')
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._q = queue.Queue()      # 唯一執行緒安全的通道
        self.root.after(50, self._poll_queue)  # 排入 mainloop 後啟動輪詢

        self.title_label = tk.Label(self.root, font=("微軟正黑體", 24, "bold"), bg='white')
        self.order_label = tk.Label(self.root, font=("微軟正黑體", 18), bg='white')
        self.price_label = tk.Label(self.root, font=("微軟正黑體", 36, "bold"), fg="red", bg='white')
        self.qr_label    = tk.Label(self.root, bg='white')
        self.hint_label  = tk.Label(self.root, font=("微軟正黑體", 14), bg='white')

        for w in (self.title_label, self.order_label, self.price_label,
                  self.qr_label, self.hint_label):
            w.pack(pady=10)

        self._qr_image = None
        self.show_welcome()

    def schedule(self, func):
        """子執行緒呼叫這裡：只寫 queue，絕不碰 tkinter。"""
        self._q.put(func)

    def _poll_queue(self):
        """主執行緒每 50ms 清空 queue 並執行 UI 更新。"""
        try:
            while True:
                self._q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)   # 只由主執行緒自己排程自己

    def show_welcome(self):
        self.title_label.config(text="歡迎光臨")
        self.order_label.config(text="請說出您想購買的商品")
        self.price_label.config(text="應付：0 元")
        self.qr_label.config(image='')
        self.hint_label.config(text="冰紅茶 27元 | 刮刮樂 180元（全場九折）")
        self._qr_image = None

    def update_order(self, items, total_price, payment_url=""):
        order_text = "訂單：\n" + "\n".join(
            f"  {i['name']} x{i['qty']}  {i['price']}元" for i in items
        ) if items else "尚無商品"

        self.title_label.config(text="訂單已確認")
        self.order_label.config(text=order_text)
        self.price_label.config(text=f"應付：{total_price} 元")

        if payment_url:
            qr = qrcode.make(payment_url).resize((200, 200))
            self._qr_image = ImageTk.PhotoImage(qr)
            self.qr_label.config(image=self._qr_image)
            self.hint_label.config(text="請掃描 QR Code 付款")
        else:
            self.qr_label.config(image='')
            self._qr_image = None
            self.hint_label.config(text="請掃碼付款（展示模式）")

    def close(self):
        self.root.destroy()
