"""L0-L5 各層鏈路實作（S1 v2，2026-05-25 拆 states/ 子資料夾）。

對應規格書：resources/plans/業務程式邏輯規劃/

本 package 採子模組拆分（B4 refactor）：
    - subroutine_a.py — L0 共通子例程 A（「回 L1 叫賣」）
    - l1.py           — L1 商家模式選擇（叫賣 / 待機 / 客服）
    - l2.py           — L2 詢問需求（顧客互動 — 初次點單）
    - l3.py           — L3 詢問額外需求（顧客互動 — 加單迴圈）
    - l4.py           — L4 印金額 + 等掃碼（結帳層）
    - l5.py           — L5 謝謝惠顧（致謝層）

對外介面（caller 直接 `from myProgram.sales import states` 然後用 `states.run_l?`）：
    - states.run_subroutine_a
    - states.run_l1 / states.run_l2 / states.run_l3 / states.run_l4 / states.run_l5

設計原則（選項 C，沿用 L0-L5 各層 docstring 規範）：
    - **嚴格不 import 廠商 SDK**（ActionGroupControl / Board / pigpio / smbus2 等）
    - 純邏輯 + callback 注入：caller（myProgram.py 入口層）負責 wire-up
      真實 terminal / TTS / OpenCV / 廠商動作
    - 業務邏輯可完整在 Windows 跑 pytest（107 tests）

return shape（B1+B7 推遲 — 各層不一致由入口層處理）：
    - run_subroutine_a → None
    - run_l1 → str | None ("L2" / None)
    - run_l2 / run_l3 → tuple[str, int]（next_state, next_think_count）
    - run_l4 / run_l5 → tuple[str, int, int]（next_state, next_loop_count, next_unclear_count）
"""

from myProgram.sales.states.subroutine_a import run_subroutine_a
from myProgram.sales.states.l1 import run_l1
from myProgram.sales.states.l2 import run_l2
from myProgram.sales.states.l3 import run_l3
from myProgram.sales.states.l4 import run_l4
from myProgram.sales.states.l5 import run_l5

__all__ = [
    "run_subroutine_a",
    "run_l1",
    "run_l2",
    "run_l3",
    "run_l4",
    "run_l5",
]
