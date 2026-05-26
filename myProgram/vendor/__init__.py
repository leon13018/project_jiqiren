"""廠商 SDK 隔離資料夾 — Hiwonder TonyPi SDK。

⛔ 禁止修改本資料夾內任何 .py 內容（hook 強制 block）。
廠商檔含 Pi-only 路徑（/home/pi/TonyPi/...）與底層庫 import
（pigpio / RPi.GPIO / BusServoCmd / PWMServo / smbus2），改了破壞硬體通訊。

只能 Read 引用、import 使用：
    from myProgram.vendor import ActionGroupControl as Act
    from myProgram.vendor import Board

S1 階段（純單線程 chat 模擬）不 import 廠商 SDK；S3+ 接動作層才用。
"""
