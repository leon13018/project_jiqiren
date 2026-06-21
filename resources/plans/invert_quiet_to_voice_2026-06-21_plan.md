# 反轉 SALES_QUIET → SALES_VOICE — plan（step-by-step）

> 對應 spec：`resources/specs/invert_quiet_to_voice_2026-06-21_spec.md`。機械式 rename + 反轉布林；最後 pytest 全綠 + grep -i 驗零殘留。

## Step 1 — prod 三檔（各自 rename + 反轉 + 註解）
對 `main.py` / `tts.py` / `action.py` 各做：
1.1 env def：`_QUIET = bool(int(os.environ.get("SALES_QUIET", "0")))` → `_VOICE = bool(int(os.environ.get("SALES_VOICE", "0")))`。
1.2 gate：`if not _QUIET:` → `if _VOICE:`（main.py:93 show_hawk_help / tts.py:439 speak / action.py:144 do）。
1.3 註解改寫（繁中）：「SALES_QUIET=1 藏…，預設 0 全顯示」→「SALES_VOICE=1 顯示終端機器人 echo（demo 預設隱藏，與 web 鏡像/實體機器人重複；偶爾 debug 才開），預設 0 = 隱藏；錯誤 ⚠️ 與導航不受此旗標影響恆顯示」。main.py 註解順手移除已 stale 的 `[模擬]` 提及（現只 gate `[模擬提示]`）。

## Step 2 — test_main_read_callbacks.py（main gate）
2.1 區塊頂註解 `# SALES_QUIET：…` → `# SALES_VOICE：預設隱藏 echo、=1 才顯示`。
2.2 `test_show_hawk_help_hidden_when_quiet` → rename `test_show_hawk_help_hidden_by_default`；patch `_VOICE=False`（預設）；斷言**不印** `[模擬提示]`。
2.3 `test_show_hawk_help_shown_when_not_quiet` → rename `test_show_hawk_help_shown_when_voice_on`；patch `_VOICE=True`；斷言**印** `[模擬提示]`。
2.4 `test_print_terminal_navigation_kept_when_quiet` → rename `test_print_terminal_navigation_kept_when_voice_off`；patch `_VOICE=False`；斷言 `進入叫賣模式` 仍印（導航不受旗標影響）。
2.5 patch seam 全部 `myProgram.main._QUIET` → `myProgram.main._VOICE`；docstring 同步翻轉語意。

## Step 3 — test_tts_worker.py（tts gate）
3.1 `test_speak_echo_hidden_when_quiet` → `_hidden_by_default`；`tts_module._VOICE=False`；無 `[語音] x`。
3.2 `test_speak_echo_shown_when_not_quiet` → `_shown_when_voice_on`；`_VOICE=True`；印 `[語音] x`。
3.3 `test_failure_line_not_gated_by_quiet` → `_not_gated_by_voice`；`_VOICE=False`；`_print_failure` 仍印 `[語音] ⚠️`（錯誤不受旗標影響）。
3.4 保留 monkeypatch `tts._worker.say` no-op 的隔離（spec gotcha：別牽動 worker）。

## Step 4 — test_action.py（action gate）
4.1 `test_action_echo_hidden_when_quiet` → `_hidden_by_default`；`action_module._VOICE=False`；無 `[動作] x`。
4.2 `test_action_echo_shown_when_not_quiet` → `_shown_when_voice_on`；`_VOICE=True`；印 `[動作] x`。
4.3 patch seam `_QUIET`→`_VOICE`；docstring/檔頭 docstring 同步。

## Step 5 — 驗證（Iron Law）
5.1 `py -3.14 -m pytest tests/sales/ tests/stt/test_main_wireup.py -q` → 全綠、無 FAIL/ERROR、數量不變。
5.2 grep -i 零殘留：`grep -rni "SALES_QUIET\|_QUIET" myProgram/ tests/` → 0（歷史 changelog/舊 spec 不在此範圍、不動）。
5.3 `git branch --contains <SHA>` 驗落 worktree-*。

## Step 6 — commit
- `git add myProgram/main.py myProgram/tts.py myProgram/action.py tests/sales/test_main_read_callbacks.py tests/sales/test_tts_worker.py tests/sales/test_action.py`
- message 見 spec §7。

## 主 agent 收尾（不在 sales-coder 範圍）
- 階段 3c：更新 `reference/sales-tts-ux.md` + `roadmap.md` 的 SALES_QUIET 現況描述為 SALES_VOICE（反轉語意）。
