# 移除 hawk 進場「進入叫賣模式」print — plan（step-by-step）

> 對應 spec：`resources/specs/drop_hawk_entry_prompt_2026-06-21_spec.md`。刪除型：prod + test 同步改，最後 pytest 全綠 + grep -i 驗孤兒。

## Step 1 — l1.py
1.1 `_run_l1_hawk`：刪 `# 印進入提示` 註解 + `print_terminal(L1_HAWK_ENTRY_PROMPT)`（函式體第一段）。函式接著 `show_hawk_help()`（B21 註解保留）。
1.2 `from myProgram.sales.constants import (...)`：移除 `L1_HAWK_ENTRY_PROMPT`（保留 HAWK_SLOGANS / HAWK_INTERVAL / L1_MENU_BANNER / ACTION_L1_HAWK）。

## Step 2 — l1_text.py
2.1 刪 `L1_HAWK_ENTRY_PROMPT` 常數定義 + 上方 `# L1 叫賣模式進入提示` 註解。
2.2 `__all__` 移除 `"L1_HAWK_ENTRY_PROMPT"`。

## Step 3 — main.py（stale 參照）
3.1 `:47` SALES_VOICE 註解：`（print_terminal 螢幕文字 / 選單 / 進入叫賣模式）` → `（print_terminal 螢幕文字 / 選單 / prompts）`（移除已刪的「進入叫賣模式」舉例）。
3.2 `:91` `show_hawk_help` docstring：移除「在印完 entry prompt 後顯式呼叫，取代原 print_terminal 內 `if text == L1_HAWK_ENTRY_PROMPT` magic string 偵測」中對已刪常數的依賴 → 改述「進場時顯式呼叫（取代早期 print_terminal magic-string 偵測，已解耦）」。

## Step 4 — tests
4.1 `tests/sales/test_states.py` `test_l1_c_hawk_mode_starts_immediately_without_mute_buffer`：刪 `# Assert 1：印「進入叫賣模式」` + `all_output = "\n".join(printed)` + `assert "叫賣" in all_output, ...`；保留 Assert 2（`len(speak_calls) >= 1` + `speak_calls[0] == HAWK_SLOGANS[0]`）。若 `printed` 變數刪後無其他用途一併移除（避免未用變數）。
4.2 `tests/spec/L1_mode_select_scenarios.py` L1-C-001 `### Then`：「終端印「進入叫賣模式」，立即播第 1 組叫賣術語」→「立即播第 1 組叫賣術語」。
4.3 `tests/sales/test_main_read_callbacks.py` `test_print_terminal_navigation_kept_when_voice_off`：`print_terminal("進入叫賣模式")` + `assert "進入叫賣模式" in ...` 的範例字串改為仍存在的導航字串（如 `"請選擇模式"`）；docstring 同步。測試意圖不變（print_terminal 不被 SALES_VOICE gate）。

## Step 5 — 驗證（Iron Law）
5.1 `py -3.14 -m pytest tests/sales/ tests/stt/ -q` → 全綠、無 FAIL/ERROR、測試數不變。
5.2 `git grep -ni "L1_HAWK_ENTRY_PROMPT" -- myProgram/ tests/` → 0（孤兒清零；resources/ 歷史不算）。
5.3 `git branch --contains <SHA>` 驗落 worktree-*。

## Step 6 — commit
- `git add myProgram/sales/states/l1.py myProgram/sales/constants/l1_text.py myProgram/main.py tests/sales/test_states.py tests/spec/L1_mode_select_scenarios.py tests/sales/test_main_read_callbacks.py`
- message 見 spec §7。
