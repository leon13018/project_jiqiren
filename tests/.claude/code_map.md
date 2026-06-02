# tests/ — code_map（本層索引）

> 本層索引：只列 `tests/` 直接子項目，一行一項。顆粒：中。
> 下沉：深入任何子目錄 → 讀 `<子目錄>/.claude/code_map.md`（不存在則以本層說明為準）。

## 子目錄
- `sales/` — sales 業務邏輯的 pytest 回歸網（對應 `myProgram/sales/`，數百個測試；改 sales prod code 必跑）。
- `spec/` — spec / 行為層測試。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `conftest.py` — pytest 共用 fixtures / 設定。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
