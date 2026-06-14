# myProgram/sales/ — code_map（本層索引）

> 顆粒：細。

## 子目錄
- `states/` — L0–L5 各層對話狀態 + 跨層流程子模組（`_cancel_confirm` / `_service_confirm` / `_l2_l3_qty_followup`）。
- `constants/` — 各層文案與常數（`l1`–`l5_text` / `keywords` / `products` / `actions` / `timing` / `shared` / `keyword_group`）。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `logic.py` — `run` facade：組 callbacks + 建 `SalesMachine`（主迴圈本體在 `states/machine.py`，OOP 重構 W5）。
- `nlu.py` — 意圖辨識（規則匹配，純函式；比對經 `constants/keyword_group.py` 的 `KeywordGroup`）。
- `dialog_io.py` — `DialogIO` callback 束（speak / read / print / act + `speak_blocking`；states 私有函式統一收 io 單參，OOP 重構 W2）。
- `product_parser.py` — 商品與數量解析。
- `phonetic.py` — 拼音近音糾錯（聲韻母模糊比對 + 歧義安全閥，純函式；掛 NLU 放棄出口兜底 ASR 平翹舌 / 前後鼻音混淆，pypinyin 注入 seam + 缺依賴 graceful no-op。Phase A 只掛問數量）。
- `cart.py` — 購物車（加 / 減 / 清空 / 結算 / `classify_qty` 數量四分類，純函式）。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
