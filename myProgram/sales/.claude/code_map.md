# myProgram/sales/ — code_map（本層索引）

> 只索引 `myProgram/sales/` 這一層的直接子項目；細顆粒描述。深入 `states/` / `constants/` → 讀其 `.claude/code_map.md`（若無，以本層說明為準）。

## 目錄
- `states/` — L0–L5 各層對話狀態 + 跨層流程模組（取消確認 `_cancel_confirm`、服務確認 `_service_confirm`、L2/L3 數量追問 `_l2_l3_qty_followup` 等）。
- `constants/` — 各層文案與常數（`l1`–`l5_text` 文案、`keywords` 關鍵字、`products` 商品、`actions` 動作、`timing` 計時、`shared` 共用）。
- `.claude/` — 本層 CC 配置：`code_map.md`(本檔)。

## 單一檔案
- `logic.py` — 主控狀態機：驅動 L0–L5 流程、調度各 state、串接 NLU / 購物車 / callback。
- `nlu.py` — 意圖辨識（規則匹配，純函式）。
- `product_parser.py` — 商品與數量解析。
- `cart.py` — 購物車（加 / 減 / 清空 / 結算，純函式）。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
