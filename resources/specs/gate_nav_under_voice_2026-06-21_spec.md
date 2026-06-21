# 導航輸出歸 SALES_VOICE gate（Option A）— Mini SDD spec（2026-06-21）

- **檔**：`myProgram/main.py`（`TerminalSim.print_terminal` + `_VOICE` 註解）+ `tests/sales/test_main_read_callbacks.py`（反轉導航測試）+ `.claude/skills/project-01-workflow/reference/sales-tts-ux.md`（doc）
- **改前**：`SALES_VOICE` 只 gate echo（`[語音]`/`[動作]`/`[模擬提示]`）；`print_terminal` 導航（選單 / L4 結帳明細 / SERVICE_PHONE / q-confirm / prompts）**恆顯示**。Pi demo（`--web --hawk`、SALES_VOICE 關）下 L4 結帳明細仍印終端 = 雜訊。
- **改後**：`TerminalSim.print_terminal` 加 `if _VOICE:` gate → **所有 print_terminal 導航一併歸 SALES_VOICE**（Option A，使用者選定）。`SALES_VOICE=0`（預設）→ 終端只剩啟動/退出行（`[模式]`/`[webui]`/`[系統]`，純 `print`）+ 錯誤 `⚠️`（tts/action `_print_failure`，純 `print` 不受影響）；`=1` → echo + 導航全顯示。
- **Why**：demo 走 web UI / 語音，終端導航（尤其 L4 結帳明細）與 web 鏡像重複、是雜訊；使用者要「正常不印任何東西」。Option A = 單一旗標控終端 verbosity，預設靜默。
- **取捨（使用者已接受）**：鍵盤選單操作（keyboard-on + 無 --hawk）需 `SALES_VOICE=1` 才看得到選單/prompts（否則 print_terminal 被 gate）。demo 路徑 `--web --hawk` 不受影響（選單本就不顯示）。
- **Out of scope**：不動 echo gate（已 SALES_VOICE）/ 錯誤 ⚠️（恆顯示）/ 啟動退出行（純 print）/ countdown / SALES_KEYBOARD / --hawk。不刪任何輸出（gate 非刪，SALES_VOICE=1 可復現）。
- **驗證**：
  - `py -3.14 -m pytest tests/sales/ tests/stt/ -q` → 全綠。反轉 `test_print_terminal_navigation_kept_when_voice_off` → `_hidden_when_voice_off`（_VOICE=False → 不印）+ 加 `test_print_terminal_shown_when_voice_on`（_VOICE=True → 印）。sales/ 各層 L4/dialog 測試**不受影響**（注入 lambda print_terminal stub、非 TerminalSim production callback）。
  - Pi：`python3.11 -m myProgram --web --hawk` → L4 結帳走到時終端**不印**明細（web 仍顯示）；`SALES_VOICE=1 …` → 明細照印。
