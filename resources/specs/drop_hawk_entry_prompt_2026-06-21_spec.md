# 移除 hawk 進場「進入叫賣模式」終端 print — SDD spec（2026-06-21）

## 1. 背景與動機
`_run_l1_hawk` 進場印 `print_terminal(L1_HAWK_ENTRY_PROMPT)`（"進入叫賣模式"）。Pi 實測 `--web --hawk` 下，這是終端唯一可見輸出（SALES_VOICE 預設關、echo 全藏）；每次進 hawk（含 web 觸控/逾時回 hawk 的 cycle）印一次，使用者要求**不再印**。demo 走 web UI，終端這行是雜訊（同橫幅移除性質）。

## 2. 設計核心 + 行為規約
- 移除 `_run_l1_hawk` 內 `print_terminal(L1_HAWK_ENTRY_PROMPT)`（含上方 `# 印進入提示` 註解）。
- `L1_HAWK_ENTRY_PROMPT` 移除後成孤兒（僅此一處 prod 使用）→ 連帶移除常數 + import + `__all__`（全清，無死碼）。
- **行為不變**：hawk 進場仍 `show_hawk_help()`（[模擬提示]，SALES_VOICE gated）+ `do_action(ACTION_L1_HAWK)`（揮手）+ `speak(HAWK_SLOGANS[0])`（叫賣）；只少印那一行導航文字。輪播 / 'q' / 't' 轉 L2 全不變。
- 結果：`--web --hawk` + SALES_VOICE 關 → 進 hawk 終端完全無輸出（乾淨，狀態看 web UI）。

## 3. 改檔範圍（高層；step 移 plan.md）
| 檔 | 改動 |
|---|---|
| `myProgram/sales/states/l1.py` | 刪 `_run_l1_hawk` 的 `# 印進入提示` + `print_terminal(L1_HAWK_ENTRY_PROMPT)`；import 移除 `L1_HAWK_ENTRY_PROMPT` |
| `myProgram/sales/constants/l1_text.py` | 刪 `L1_HAWK_ENTRY_PROMPT` 常數 + 上方註解 + `__all__` 條目 |
| `myProgram/main.py` | `:47` SALES_VOICE 註解導航舉例移除「/ 進入叫賣模式」；`:91` `show_hawk_help` docstring 移除對 `L1_HAWK_ENTRY_PROMPT` / 「印完 entry prompt 後」的提及（改述「進場時顯式呼叫，取代早期 magic-string 偵測」）|
| `tests/sales/test_states.py` | `test_l1_c_hawk_mode_starts_immediately_without_mute_buffer`：刪 Assert 1（印「叫賣」進入提示，~178-180）+ 其註解；保留 Assert 2（立即 speak HAWK_SLOGANS[0]）。`test_l1_hawk_entry_calls_do_action_*` docstring 的「進入叫賣模式時」語意保留（非斷言 print） |
| `tests/spec/L1_mode_select_scenarios.py` | L1-C-001 `### Then` 去「終端印「進入叫賣模式」」、保留「立即播第 1 組叫賣術語」 |
| `tests/sales/test_main_read_callbacks.py` | `test_print_terminal_navigation_kept_when_voice_off` 的範例字串 `"進入叫賣模式"` → 改成仍存在的導航字串（如 `"請選擇模式"`）——因該字串已非 app 輸出，續用會誤導；測試意圖（print_terminal 不被 SALES_VOICE gate）不變 |

## 4. Out of scope
- 不動 hawk 進場的 `do_action` / `show_hawk_help` / `speak(slogan)` 與輪播邏輯、不動 'q'/'t' 行為。
- 不動歷史檔：`resources/specs/{hawk_loop,touch_trigger,quiet_mode}_*`、`resources/reviews/*`、`resources/plans/業務程式邏輯規劃/L1.md`、`changelogs/*`（保留歷史 L1_HAWK_ENTRY_PROMPT/進入叫賣模式 字樣）。
- 不動 SALES_VOICE/SALES_KEYBOARD/--hawk 等既有機制。
- doc 更新（如 reference 提及）由主 agent 收尾視需要。

## 5. 規範與參考
- 派 sales-coder（opus，預載 karpathy + TDD）。最小外科式刪除 + 連帶孤兒清理。
- 繁中產出。刪除驗證 `grep -i "L1_HAWK_ENTRY_PROMPT"` 於 `myProgram/` + `tests/` → 零殘留（歷史 resources/ 不算）。

## 6. 測試指令 + 預期結果
- `py -3.14 -m pytest tests/sales/ tests/stt/ -q` → 全綠、無 FAIL/ERROR。測試數不變（改斷言/範例，非增減 test 函式）。
- Pi：`python3.11 -m myProgram --web --hawk` → 進 hawk 終端**不再印「進入叫賣模式」**（SALES_VOICE 關時終端全靜；機器人仍揮手 + 叫賣 + web 鏡像照常）。

## 7. Commit 規範
- worktree 首 commit：spec + plan doc。
- 實作 commit：prod（l1.py + l1_text.py + main.py）+ tests，`git add` 明列、禁 `-A`（可分 commit）。
- message：`refactor(l1): drop hawk-entry terminal prompt (進入叫賣模式)` + 繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
[現況] 進 hawk → print「進入叫賣模式」+ show_hawk_help + do_action(揮手) + speak(slogan)
[目標] 進 hawk → show_hawk_help + do_action(揮手) + speak(slogan)（少印那行；常數+孤兒清掉）
```
