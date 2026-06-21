# 模式入口啟動提示行 — Mini SDD spec（2026-06-21）

- **檔**：`myProgram/main.py`（`_run_wiring`，guard 後 / web 設定前）+ `tests/stt/test_main_wireup.py`（capsys 測試）
- **改前**：`--hawk` 啟動時終端無任何模式標示（剛移除每次進場的「進入叫賣模式」；現只 web 模式有 `[webui]` 啟動提示）。
- **改後**：`_run_wiring` 在啟動防呆通過後加：
  ```python
  if start_hawk:
      print("[模式] 叫賣模式")
  ```
  一次性啟動標示，對齊 `[webui] FastAPI 已啟動 …` 風格（bracketed label + 內容）。未來新模式在各自 flag 分派印對應行（不建 map，YAGNI）。
- **Why**：使用者要求——用 `--模式` flag 啟動時，像 `--web` 的 `[webui]` 提示一樣，於**一開始**標示進入了哪個模式。與已移除的「每次進 hawk 印『進入叫賣模式』」不同：本行只在 `_run_wiring` 啟動時印一次（非每次 hawk 進場）。
- **Out of scope**：不動 `_run_l1_hawk`（每次進場邏輯）、不動 `[webui]`/guard/`--hawk` 串接機制、不建 mode→name map（只 hawk）。
- **驗證**：
  - `py -3.14 -m pytest tests/stt/test_main_wireup.py tests/sales/ -q` → 全綠（新增 1 capsys 測試）。
  - 新測試：`argv=["myprogram","--hawk"]` → `_run_wiring`（logic.run stubbed）→ capsys 含 `[模式]`。
  - Pi：`python3.11 -m myProgram --web --hawk` → 啟動印 `[模式] 叫賣模式`（一次）+ `[webui] …`；進 hawk 後不再重印。
