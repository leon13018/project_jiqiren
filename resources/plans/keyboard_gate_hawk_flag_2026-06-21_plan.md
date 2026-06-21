# --hawk flag + SALES_KEYBOARD gate + 啟動防呆 — plan（step-by-step）

> 對應 spec：`resources/specs/keyboard_gate_hawk_flag_2026-06-21_spec.md`。TDD：先 failing test（RED）→ 最小 prod（GREEN）→ commit。

## Step 1 — machine.py（start_hawk 初始化 enter_hawk_immediately）
1.1 RED：`tests/sales/test_machine.py` 加 `test_start_hawk_true_first_l1_enters_hawk_immediately`：`SalesMachine(callbacks, cart, start_hawk=True)`，monkeypatch `states.run_l1` 捕 `enter_hawk_immediately` kwarg + 回 None，跑 `.run()`，斷言首次 run_l1 收 `enter_hawk_immediately=True`。加 `test_start_hawk_default_false_shows_menu`（不傳→首次 False）。跑見 FAIL。
1.2 GREEN：`SalesMachine.__init__` 加 `start_hawk: bool = False`；`self.enter_hawk_immediately = start_hawk`。docstring 註記。跑 PASS。

## Step 2 — logic.py（start_hawk 穿到 SalesMachine）
2.1 RED：`tests/sales/test_logic.py` 加 `test_run_start_hawk_passed_to_machine`：monkeypatch `logic.SalesMachine` 捕 `start_hawk`（stub .run() no-op），呼 `logic.run(**minimal_callbacks, start_hawk=True)`，斷言收 `start_hawk=True`。跑 FAIL。
2.2 GREEN：`logic.run` 加 `start_hawk: bool = False`；`SalesMachine(..., start_hawk=start_hawk)`。docstring 更新。跑 PASS。

## Step 3 — main.py（--hawk 解析 + 啟動防呆）
3.1 RED：`tests/stt/test_main_wireup.py`：
   - **先更新既有 --web/terminal 佈線測試**：`test_terminal_mode_*` argv → `["myprogram","--hawk"]`；4 個 `test_web_mode_*` argv → `["myprogram","--web","--hawk"]`（否則被防呆擋 → 這些測試本就該跑 valid 啟動）。
   - 加 `test_hawk_flag_passes_start_hawk_true`（argv 有 --hawk → captured start_hawk=True）+ `test_no_hawk_with_keyboard_on_passes_start_hawk_false`（argv 無 --hawk + `monkeypatch.setenv("SALES_KEYBOARD","1")` → logic.run 被呼、start_hawk=False）。
   - 加 `test_no_mode_flag_keyboard_off_aborts`（argv 無 --hawk + 無 SALES_KEYBOARD → `_run_wiring` 印防呆訊息 + **不**呼 logic.run；capsys 驗訊息含「SALES_KEYBOARD」/「--hawk」）。
   跑見 FAIL。
3.2 GREEN：`_run_wiring` 開頭：`start_hawk = "--hawk" in sys.argv`；`keyboard_on = bool(int(os.environ.get("SALES_KEYBOARD","0")))`；`if not start_hawk and not keyboard_on: print(防呆訊息); return`。`logic.run(**callbacks, display=display_cb, start_hawk=start_hawk)`。docstring 註明 --hawk + 防呆。跑 PASS。
   - 注意 capture helper `_capture_logic_run` 仍攔 logic.run；防呆測試需確認 captured 為空（logic.run 未被呼）。

## Step 4 — input_reader.py（SALES_KEYBOARD gate）
4.1 RED：`tests/sales/test_input_reader.py` 加 `test_keyboard_disabled_does_not_read_source_but_inject_works`：`InputReader(source=FakeByteSource([b"x\n"]), keyboard_enabled=False)`；短暫等待後 source 未被讀（`reader._q` 不含 "x"，可 `qsize()==0`）；`reader.inject("web")`→`reader.read(0.1)=="web"`。加 `test_keyboard_enabled_reads_source`（=True → 讀到 source，既有行為）。跑 FAIL（無 keyboard_enabled）。
4.2 GREEN：`import os`；`_KEYBOARD = bool(int(os.environ.get("SALES_KEYBOARD","0")))`（檔頭 import 後）；`InputReader.__init__(self, source=None, *, keyboard_enabled=True)`：`if keyboard_enabled:` 才啟 thread；singleton `_reader = InputReader(keyboard_enabled=_KEYBOARD)`。docstring/註解說明 gate + 預設 True 理由。跑 PASS（既有 8 test 預設 True 不變）。

## Step 5 — 驗證（Iron Law）
5.1 `py -3.14 -m pytest tests/sales/ tests/stt/ -q` → 全綠、無 FAIL/ERROR。
5.2 `git branch --contains <SHA>` 驗落 worktree-*。
5.3 抽查：`grep -n "start_hawk" myProgram/`（main/logic/machine 串接）；`grep -n "SALES_KEYBOARD" myProgram/`（main 防呆 + input_reader gate 兩處）。

## Step 6 — commit
- `git add myProgram/main.py myProgram/sales/logic.py myProgram/sales/states/machine.py myProgram/input_reader.py tests/stt/test_main_wireup.py tests/sales/test_machine.py tests/sales/test_logic.py tests/sales/test_input_reader.py`
- message 見 spec §7。

## 主 agent 收尾（不在 sales-coder 範圍）
- 更新 reference（`sales-tts-ux.md` 或合適處）+ 視需要 roadmap：`--hawk` 進場 flag + `SALES_KEYBOARD` gate + 啟動防呆 + Ctrl+C 退出。
