# tests/ — 本層導引

> **本層檔案結構索引在 `.claude/code_map.md`——任何「tests 裡的檔在哪 / 結構」務必第一優先讀它。**
> 深入子目錄（`sales/` / `spec/`）→ 讀 `<子目錄>/.claude/code_map.md`（若無，以本層 code_map 說明為準）。

pytest 測試：sales 業務邏輯回歸網 + spec 測試。

- 改 `tests/sales/*` 與對應 prod code 走**同一 SDD spec**（見 `project-01-workflow` skill）。
- 改 `tests/sales/*` 後須跑 `python -m pytest tests/sales/`（Stop hook 會守一次提醒）。
