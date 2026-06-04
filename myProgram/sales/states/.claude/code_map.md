# myProgram/sales/states/ — code_map（本層索引，葉層）

> 顆粒：最細。

## 子目錄
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
**層狀態（L0–L5）**
- `l0_subroutine_a.py` — L0 共通子例程 A「交易完緩衝」：mute 12s、不自動叫賣（下一步去哪由 `logic.py` 決定）。
- `l1.py` — L1 商家模式選擇層：叫賣（hawk 輪播）/ 待機 / 客服。
- `l2_l3_dialog.py` — L2/L3 統一對話層（**cart 狀態驅動**）：cart 空=L2 問需求；cart 非空=L3 問加單 / 結帳（含 C-2 兩段結帳）。
- `l4.py` — L4 結帳層：印金額 + 等掃碼；v3 雙計時器（36s 總 budget + 12s QR 刷新循環）。
- `l5.py` — L5 致謝層：純序列 speak → clear_cart → sleep（無互動 / 無分支）。

**跨層流程子模組（`_` 前綴）**
- `_cancel_confirm.py` — 取消確認子流程（顧客要取消 → 確認後清 cart 退出）。
- `_service_confirm.py` — 服務確認子流程。
- `_l2_l3_qty_followup.py` — L2/L3 數量追問子流程（商品數量釐清）。

**套件 / 導引**
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
