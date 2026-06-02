# myProgram/sales/ — code_map（本層索引）

> 本層索引：只列 `myProgram/sales/` 直接子項目，一行一項。顆粒：細。
> 下沉：深入任何子目錄 → 讀 `<子目錄>/.claude/code_map.md`（不存在則以本層說明為準）。

## 子目錄
- `states/` — L0–L5 各層對話狀態 + 跨層流程子模組（`_cancel_confirm` / `_service_confirm` / `_l2_l3_qty_followup`）。
- `constants/` — 各層文案與常數（`l1`–`l5_text` / `keywords` / `products` / `actions` / `timing` / `shared`）。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `logic.py` — 主控狀態機：驅動 L0–L5 流程、調度各 state、串接 NLU / 購物車 / callback。
- `nlu.py` — 意圖辨識（規則匹配，純函式）。
- `product_parser.py` — 商品與數量解析。
- `cart.py` — 購物車（加 / 減 / 清空 / 結算，純函式）。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
