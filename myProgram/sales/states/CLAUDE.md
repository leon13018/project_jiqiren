# myProgram/sales/states/ — 本層導引

> **本層檔案結構索引在 `.claude/code_map.md`——任何「states 裡的檔在哪 / 結構」務必第一優先讀它。**（葉層，無子目錄）

L0–L5 各層對話狀態 + 跨層流程子模組（底線前綴 `_` = 跨層 confirm / followup helper）。

- 改本層 `.py` → 走 SDD + 對照 skill 的 `sales-dialog-design.md`（對話狀態機 / 跨層流程 / 錢包保守 / confirm 設計）；改後跑 `python -m pytest tests/sales/`。
