# myProgram/sales/constants/ — code_map（本層索引，葉層）

> 顆粒：最細。純資料常數，無邏輯。

## 子目錄
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
**各層文案（TTS / 顯示字串）**
- `l1_text.py` — L1 文案（叫賣標語 `HAWK_SLOGANS` 等）。
- `l2_text.py` — L2 文案（問需求等）。
- `l3_text.py` — L3 文案（加單 / C-2 結帳提示 `L3_C2_WARNING_TEMPLATE` 等）。
- `l4_text.py` — L4 文案（金額 / 掃碼提示 `L4_REMIND_PROMPT` 等）。
- `l5_text.py` — L5 文案（致謝 `L5_THANKS` 等）。

**其他常數**
- `keywords.py` — NLU 規則匹配關鍵字（`KEYWORDS_C2_*` / `KEYWORDS_CONFIRM_*` / strict-short 等）+ `KG_*` KeywordGroup 配對實例（類別在 `sales/keyword_group.py`）。
- `products.py` — 商品清單與價格。
- `actions.py` — 機器人動作組常數（動作組名稱，如 `ACTION_L5_FAREWELL`）。
- `timing.py` — 計時 / budget 常數（`HAWK_INTERVAL` / `L4_TOTAL_BUDGET` / `THANK_DELAY` 等秒數）。
- `shared.py` — 跨層共用常數。

**套件 / 導引**
- `__init__.py` — 套件標記（re-export 各常數，供 `from myProgram.sales.constants import ...`）。
- `CLAUDE.md` — 本層導引。
