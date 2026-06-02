# tests/ — code_map（本層索引）

> 只索引 `tests/` 這一層的直接子項目；中顆粒描述。深入 `sales/` / `spec/` → 讀其 `.claude/code_map.md`（若無，以本層說明為準）。

## 目錄
- `sales/` — sales 業務邏輯的 pytest 回歸網（對應 `myProgram/sales/`，數百個測試；改 sales prod code 必跑）。
- `spec/` — spec / 行為層測試。
- `.claude/` — 本層 CC 配置：`code_map.md`(本檔)。

## 單一檔案
- `conftest.py` — pytest 共用 fixtures / 設定。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
