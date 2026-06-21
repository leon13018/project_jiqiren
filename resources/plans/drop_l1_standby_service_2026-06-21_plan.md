# 移除 L1 待機 / 客服模式 — plan（step-by-step）

> 對應 spec：`resources/specs/drop_l1_standby_service_2026-06-21_spec.md`。刪除型任務：prod 與 test 同步改，最後一次 pytest 全綠 + grep -i 驗 orphan。

## Step 1 — `l1_text.py` 常數
1.1 `L1_MENU_BANNER`：刪去 `"  2 — 待機模式\n"` 與 `"  3 — 客服模式\n"` 兩行；其餘（分隔線 / 「請選擇模式」/ 「1 — 叫賣模式」/ q 提示 / `"> "`）保留。
1.2 刪 `L1_STANDBY_ENTRY_PROMPT` 常數定義（含上方註解 `# L1 待機模式進入提示`）。
1.3 `__all__` 移除 `"L1_STANDBY_ENTRY_PROMPT"`。
（`L1_HAWK_ENTRY_PROMPT` 與檔頭 SERVICE_PHONE 註解保留。）

## Step 2 — `l1.py` 程式碼
2.1 `from myProgram.sales.constants import (...)`：移除 `L1_STANDBY_ENTRY_PROMPT`、`SERVICE_PHONE` 兩名（保留 HAWK_SLOGANS / HAWK_INTERVAL / L1_MENU_BANNER / L1_HAWK_ENTRY_PROMPT / ACTION_L1_HAWK）。
2.2 `run_l1` 主迴圈：刪 `if key == "3": _run_l1_service(...) ... continue` 分支與 `elif key == "2": result = _run_l1_standby(...) ...` 分支；保留 `key == "1"` 分支（改 `elif key == "1"` → `if key == "1"`，因前面分支已移除）。末尾「其他鍵重印選單」註解更新（移除「q/1/2/3」列舉為「q/1」）。
2.3 刪整個 `_run_l1_service` 函式。
2.4 刪整個 `_run_l1_standby` 函式。
2.5 docstring / 註解更新：
   - module docstring 第 1 行「商家模式選擇層（叫賣 / 待機 / 客服）」→「（叫賣）」。
   - module docstring callback 列表移除已不用者（保留 print_terminal/read_terminal_key/speak/exit_program/tts_is_idle/show_hawk_help/do_action）。
   - line 27 區塊註解「三鏈路（主選單 / standby / hawk）共用」→「兩鏈路（主選單 / hawk）共用」。
   - `run_l1` docstring「分派三個鏈路（叫賣 / 待機 / 客服）」→「分派叫賣鏈路」。
   - line 114 內層 loop 註解「客服 / 待機 sub-routine 返回」相關描述更新（移除 standby/service 提及）。

## Step 3 — `tests/sales/test_states.py`
3.1 `test_l1_entry_prints_mode_select_menu`：斷言改為 `assert "1" in all_output`（叫賣）+ `assert "q" in all_output`；新增 `assert "待機" not in all_output` 與 `assert "客服" not in all_output`（驗證已移除）；移除原 `"2"`/`"3"` 斷言；更新上方 scenario 註解「選單只含 1 叫賣 + q」。
3.2 刪 `test_l1_a_service_mode_prints_phone_and_returns_to_menu`（含其上方 L1-A 區塊註解）。
3.3 刪 `test_l1_b_standby_mode_prints_prompt_and_stays_idle` / `test_l1_b_standby_r_returns_to_menu` / `test_l1_b_standby_q_exits_program`（含 L1-B 區塊註解）。
（`test_l1_c_hawk_non_q_keys_ignored` 用 `["1","1","2","3","x","q","q"]` 保留不動——驗 hawk 內 2/3 被忽略，行為不變。）

## Step 4 — `tests/spec/L1_mode_select_scenarios.py`
4.1 L1-ENTRY-001 `### Then` 描述：「選單含三個選項（1 叫賣 / 2 待機 / 3 客服）」→「選單含一個選項（1 叫賣）與 q 退出提示」。
4.2 刪 L1-A 區塊（客服，`test_l1_a_service_mode_prints_phone_and_returns_to_menu`）。
4.3 刪 L1-B 區塊（待機，三個 `test_l1_b_standby_*`）。
4.4 檔頭 docstring 若列模式（「商家模式選擇」描述）視情況微調，不強制。

## Step 5 — 驗證（Iron Law）
5.1 `py -3.14 -m pytest tests/sales/ tests/spec/ tests/stt/test_main_wireup.py -q` → 全綠、無 FAIL/ERROR。
5.2 grep -i 驗 orphan（須零；排除 web phase `"standby"` 與 L4 客服 confirm）：
   - `grep -rni "_run_l1_standby\|_run_l1_service\|L1_STANDBY" myProgram/ tests/` → 0
   - `grep -rni "待機" myProgram/ tests/` → 僅可能殘留處人工確認非 L1（預期 0）
   - l1.py 內 `grep -ni "待機\|standby\|客服" ` → 0
5.3 主 agent `git branch --contains <SHA>` 驗落 worktree-*。

## Step 6 — commit
- `git add myProgram/sales/states/l1.py myProgram/sales/constants/l1_text.py tests/sales/test_states.py tests/spec/L1_mode_select_scenarios.py`
- commit message 見 spec §7。
```
