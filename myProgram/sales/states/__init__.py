"""L0-L5 各層鏈路實作（S1 v2，2026-05-25 拆 states/ 子資料夾；同日合併 L2/L3 為 dialog）。

對應規格書：resources/plans/業務程式邏輯規劃/

本 package 採子模組拆分：
    - subroutine_a.py — L0 共通子例程 A（「回 L1 叫賣」）
    - l1.py           — L1 商家模式選擇（叫賣 / 待機 / 客服）
    - dialog.py       — L2/L3 合一對話層（cart 狀態驅動；2026-05-25 B 方案重構）
    - l4.py           — L4 印金額 + 等掃碼（結帳層）
    - l5.py           — L5 謝謝惠顧（致謝層）

對外介面：
    - states.run_subroutine_a
    - states.run_l1 / states.run_dialog / states.run_l4 / states.run_l5

設計原則：
    - **嚴格不 import 廠商 SDK**（選項 C）
    - 純邏輯 + callback 注入
    - 業務邏輯可完整在 Windows 跑 pytest

return shape：
    - run_subroutine_a → None
    - run_l1 → str | None ("L2" / None)
    - run_dialog → tuple[str, int]（next_state ∈ {"L4", "L1_via_subroutine_a"}, next_think_count）
    - run_l4 / run_l5 → tuple[str, int, int]（next_state, next_loop_count, next_unclear_count）

歷史：L2/L3 原本是兩個獨立函式（run_l2 / run_l3），2026-05-25 改為 cart-state-driven 統一
dialog 層（B 方案）。Why：原架構「L2→L3」transition 是動作驅動，未來加刪除商品功能時 cart
被清空在 L3 內仍會問「還需要什麼東西嗎？」違和。改成 cart 狀態決定 prompt + 行為，未來
延伸時自然一致。
"""

from myProgram.sales.states.subroutine_a import run_subroutine_a
from myProgram.sales.states.l1 import run_l1
from myProgram.sales.states.dialog import run_dialog
from myProgram.sales.states.l4 import run_l4
from myProgram.sales.states.l5 import run_l5

__all__ = [
    "run_subroutine_a",
    "run_l1",
    "run_dialog",
    "run_l4",
    "run_l5",
]
