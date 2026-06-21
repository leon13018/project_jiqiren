# 反轉安靜模式：SALES_QUIET → SALES_VOICE（預設隱藏 echo）— SDD spec（2026-06-21）

## 1. 背景與動機
現況（`quiet_mode_2026-06-20_spec.md`）：env `SALES_QUIET=1` 藏終端機器人 echo（`[語音]`/`[動作]`/`[模擬提示]`），**預設 0 = 全顯示**。
使用者要求**反轉預設並改名**：`python3.11 -m myProgram --web` **預設不顯示**語音 echo；要顯示時設 `SALES_VOICE=1`。理由：demo 走 web UI + 觸控，終端 echo 與 web 鏡像/實體機器人重複，平時是雜訊，預設關掉更乾淨；偶爾 debug 才開。

## 2. 設計核心 + 行為規約
- **Env 旗標改名 + 反轉**：`SALES_QUIET` → `SALES_VOICE`；module-level `_QUIET` → `_VOICE`。
  - `_VOICE = bool(int(os.environ.get("SALES_VOICE", "0")))`
  - gate 由 `if not _QUIET:` → **`if _VOICE:`**（預設 `_VOICE=0` → **隱藏**；`=1` → 顯示）。
- **gate 範圍不變**（與舊 SALES_QUIET 同一組，只反轉預設 + 改名）：`SALES_VOICE=1` 顯示 `[語音]`（tts）+ `[動作]`（action）+ `[模擬提示]`（main show_hawk_help）整組。
- **保留不 gate**（與舊一致）：錯誤 `⚠️` 失敗行、導航 `print_terminal`（選單 / `進入叫賣模式` / prompts）、`[webui]`/`[系統]` — 這些不受 `_VOICE` 影響，恆顯示。
- 各模組仍**各自讀** env（不新增跨模組 import）。純抑制 print，不改任何計時 / 行為。

## 3. 改檔範圍（高層；step 移 plan.md）
| 檔 | 改動 |
|---|---|
| `myProgram/main.py` | `_QUIET`→`_VOICE`（env `SALES_VOICE`）；`show_hawk_help` 的 `if not _QUIET:`→`if _VOICE:`（:93）；註解改寫為「SALES_VOICE=1 顯示…，預設 0 隱藏」+ 移除已 stale 的 `[模擬]` 提及（現只 gate `[模擬提示]`） |
| `myProgram/tts.py` | `_QUIET`→`_VOICE`；`speak()` 的 `if not _QUIET:`→`if _VOICE:`（:439）；註解改寫 |
| `myProgram/action.py` | `_QUIET`→`_VOICE`；`do()` 的 `if not _QUIET:`→`if _VOICE:`（:144）；註解改寫 |
| `tests/sales/test_main_read_callbacks.py` | `_QUIET`→`_VOICE` patch；翻轉語意：`*_hidden_when_quiet`→`*_hidden_by_default`（`_VOICE=False`→不印）、`*_shown_when_not_quiet`→`*_shown_when_voice_on`（`_VOICE=True`→印）、`*_navigation_kept_when_quiet`→`*_navigation_kept_when_voice_off`（`_VOICE=False` 導航仍印） |
| `tests/sales/test_tts_worker.py` | 同上翻轉：`test_speak_echo_hidden_when_quiet`→`_by_default`、`_shown_when_not_quiet`→`_when_voice_on`、`test_failure_line_not_gated_by_quiet`→`_by_voice`（`_VOICE=False` 仍印 ⚠️） |
| `tests/sales/test_action.py` | 同上翻轉：`test_action_echo_hidden_when_quiet`→`_by_default`、`_shown_when_not_quiet`→`_when_voice_on` |

## 4. Out of scope
- **不改 gate 範圍**（仍是 `[語音]`+`[動作]`+`[模擬提示]` 整組；不拆成只 gate `[語音]`）。
- **不動歷史檔**：`resources/specs/quiet_mode_2026-06-20_spec.md`、`resources/changelogs/changelog_2026-06-20_touch_ux_startup.md`、`resources/changelog.md`（歷史記錄，保留 SALES_QUIET 字樣）。
- 不動 `SALES_SHOW_COUNTDOWN` / `STT_*` 等其他旗標、不動錯誤 ⚠️ / 導航 / `[webui]` / `[系統]`。
- 不改任何計時 / 對話行為。
- **doc 更新（reference/sales-tts-ux.md + roadmap.md 現況描述）由主 agent 收尾改**（階段 3c），不在 sales-coder 範圍。

## 5. 規範與參考
- 派 **sales-coder**（opus，預載 karpathy + TDD）。最小機械式 rename + 反轉，不重構鄰近、不新增抽象。
- 繁中產出。
- 刪除/改名驗證 `grep -i`：`SALES_QUIET`/`_QUIET` 在 `myProgram/` + `tests/` 須**零殘留**（歷史 changelog / 舊 spec 不算，本次不動）。

## 6. 測試指令 + 預期結果
- `py -3.14 -m pytest tests/sales/ tests/stt/test_main_wireup.py -q` → 全綠、無 FAIL/ERROR。測試數不變（同數量、語意翻轉）。
- 行為驗證重點：`_VOICE=False`（預設）→ echo 不印、導航/⚠️ 仍印；`_VOICE=True` → echo 印。
- Pi：`python3.11 -m myProgram --web`（不設旗標）→ 進叫賣後無 `[語音]`/`[動作]`/`[模擬提示]`，選單/`進入叫賣模式` 仍在；`SALES_VOICE=1 python3.11 -m myProgram --web` → echo 全顯示。

## 7. Commit 規範
- worktree 首 commit：spec + plan doc。
- 實作 commit：3 prod + 3 test，`git add` 明列、禁 `-A`。
- message：`feat(output): invert SALES_QUIET to SALES_VOICE (echo hidden by default)` + 繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
[現況] 預設顯示 echo；SALES_QUIET=1 → if not _QUIET → 藏
[目標] 預設隱藏 echo；SALES_VOICE=1 → if _VOICE → 顯示
        gate 組不變（語音/動作/模擬提示）；⚠️/導航/webui/系統 恆顯示
```
