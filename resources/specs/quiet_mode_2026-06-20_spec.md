# 安靜模式 SALES_QUIET（藏機器人 echo、保留導航/錯誤）— Mini SDD spec

**日期：** 2026-06-20
**類型：** 使用者要求的終端輸出 toggle（小改動：3 檔各加 env 旗標 + gate echo print + capsys 測試）

## 動機
`python3.11 -m myProgram --web` demo 時，終端的機器人狀態 echo（語音/動作/opencv/模擬）跟 web 鏡像 UI +
實體機器人重複、是雜訊。使用者要求一個 env 旗標 `SALES_QUIET=1` 藏掉這些 echo，但**保留終端導航**
（選單 / `進入叫賣模式` / prompts）與**錯誤行**（⚠️），讓商家仍能用終端打 1/c/q 操作、出錯仍看得到。

## 設計
- **Env 旗標 `SALES_QUIET`**：預設 `0` = 現狀全顯示（不改行為）；`=1` = 藏 echo。opt-in 隱藏（echo 一直預設可見、debug 有用）。
- 每個模組**各自讀** `SALES_QUIET`（沿用 `STT_TTS_TIMING` 在 tts/stt 各自讀的 precedent，不新增跨模組 import）：module-level `_QUIET = bool(int(os.environ.get("SALES_QUIET", "0")))`，放各檔現有 env 旗標 / 常數區。
- gate 方式：`if not _QUIET: print(...)`（或等效），只包**正常 echo**、**不包**錯誤與導航。

## 改檔範圍（line 號以 main HEAD 04bd31d 為基準，sales-coder 先 re-grep 確認精確行）

| 檔 | 新增旗標 | **Gate（藏）** | **保留（不動）** |
|---|---|---|---|
| `myProgram/main.py` | `_QUIET`（放 `_SHOW_COUNTDOWN` 旁） | `show_hawk_help` 的 `>>> [模擬提示]`（~:103）；`read_terminal_key` 的兩條 `[模擬]`（~:139/142）；`opencv_enable/disable/mute_opencv` 三條 `[opencv]`（~:199/204/228） | `print_terminal`（~:95，螢幕文字＝選單/進入提示/prompts）；開場小抄（~:393-403）；`[webui]`（~:367/374）；`[系統]`（~:192/307/412） |
| `myProgram/tts.py` | `_QUIET`（放 VOICE/常數區附近） | 正常 `[語音] {text}`（`speak()`，~:434） | `[語音] ⚠️` 失敗（`_print_failure` ~:114-117、wait_idle 警示 ~:377）；`[語音][計時]`（~:124，已由 STT_TTS_TIMING gated） |
| `myProgram/action.py` | `_QUIET` | 正常 `[動作] {name}`（`do()` ~:137） | `[動作] ⚠️` 失敗（~:93-96） |

> **hide/keep 邊界是本 spec 核心**：只藏「正常狀態 echo」；錯誤 `⚠️`、導航 `print_terminal`、開場小抄、退出訊息一律**保留**。

## Out of scope
- 不藏導航（`print_terminal` 螢幕文字 / 選單 / `進入叫賣模式` / prompts）、不藏錯誤 ⚠️、不藏開場小抄 / `[webui]` / `[系統]`。
- 不動 countdown toggle（`SALES_SHOW_COUNTDOWN` 已獨立、預設隱藏；quiet 模式下 countdown 仍預設隱藏，無互動）。
- 不動 STT `[語音辨識]` echo（使用者本次未提；保持現狀）。
- 不改任何計時 / 行為，純抑制 print。

## 測試（capsys + monkeypatch module `_QUIET` seam）
> **隔離 gotcha**：`tts.speak()` / `action.do()` 都是「caller thread 立即 print → 再 `_worker.say/do` enqueue」。
> 測 print gate **必先 monkeypatch `_worker.say` / `_worker.do` 為 no-op**，否則 worker daemon thread 會真去
> 合成（edge_tts 網路）/ 真 dispatch（action worker 首次 lazy import vendor → Windows ImportError），其 async
> 失敗印行會污染 capsys、測試 flaky。gate 只測 caller-thread 那行 print，不要牽動 worker。

- `tests/sales/test_main_read_callbacks.py`（或 test_terminal_sim.py）：
  - `_QUIET=True` → `show_hawk_help()` 不印 `[模擬提示]`；`read_terminal_key` 觸發的 `[模擬]`、`opencv_enable/disable/mute_opencv` 的 `[opencv]` 不印；`print_terminal("進入叫賣模式")` **仍印**（導航保留）。
  - `_QUIET=False`（預設）→ 上述照印（行為不變）。
- `tests/sales/test_tts_worker.py`：monkeypatch `tts._worker.say` no-op + `tts._QUIET=True` → `tts.speak("x")` capsys 無 `[語音] x`；直接呼 `_print_failure(...)` **仍印** `[語音] ⚠️`（驗錯誤不被 gate）。`_QUIET=False` → `[語音] x` 印。
- action gate（無既有 test_action 檔）：在 `test_main_read_callbacks.py` 或新 `tests/sales/test_action.py` 加；monkeypatch `action._worker.do` no-op + `action._QUIET=True` → `action.do("x")` capsys 無 `[動作] x`；`_QUIET=False` → 印。失敗行 `_print_failure`/⚠️ 不被 gate（可不另測，gate 明顯只包正常 print）。
- seam：`monkeypatch.setattr("myProgram.<mod>._QUIET", True/False)`，對齊 `_SHOW_COUNTDOWN` / `_EARLY_MIC` patch pattern。

## 驗證
- `py -3.14 -m pytest tests/ -q` 全綠（baseline 701；+新測試）。
- Pi：`SALES_QUIET=1 python3.11 -m myProgram --web` → 進叫賣後無 `[語音]`/`[動作]`/`[opencv]`/`[模擬]`/`[模擬提示]`，但 `進入叫賣模式`/選單仍在；故意餵錯（如缺 mpg123）⚠️ 仍印。預設（不設旗標）→ 全顯示如舊。

## 文件
- 更新 skill `reference/sales-tts-ux.md`（或合適 reference）註明 `SALES_QUIET=1` 藏 echo、保留導航/錯誤。主 agent 收尾改。

## Commit（git add 明列，禁 -A；結尾 Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>）
- `feat(output): add SALES_QUIET env flag to hide robot-echo terminal lines`（main/tts/action + 測試一個 commit，或 prod/test 視 sales-coder）。
