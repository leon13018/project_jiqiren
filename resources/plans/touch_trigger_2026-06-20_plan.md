# 移除 OpenCV、改 't' 觸控觸發 L2 — plan（HOW，分 wave）

> 對應 spec：`resources/specs/touch_trigger_2026-06-20_spec.md`。
> worktree `.claude/worktrees/touch-trigger/`，branch `worktree-touch-trigger`，首 commit 是 spec/plan doc（不改）。
> pytest：`py -3.14 -m pytest tests/sales/ -q`（快）／ 收尾 `py -3.14 -m pytest tests/ -q`（全量）。⚠️ PATH 的 `python` 無 pytest。
> Wave 6：先 grep 列清單 / 每改一檔即跑 pytest / commit 前自檢 / `-v --tb=short` / 規格衝突 test 必停 / 任何 fail 必停。

---

## Step 0 — 先列再做（Wave 6 第 1 招，每 wave 開工前）
grep 受影響清單，thinking 內列、return 含：
- `grep -rn "opencv\|OPENCV\|mute_opencv\|opencv_dwell\|opencv_enable\|opencv_disable\|FakeOpencv\|_S1State\|via_subroutine_a\|run_subroutine_a\|OPENCV_DWELL\|OPENCV_MUTE" myProgram/ tests/`
- `grep -rn "_WAKE_TOKEN\|wake" myProgram/web/ tests/web/`

---

## 階段 Wave A — 加 't'（touch 開始點餐）觸發（additive，opencv 暫共存）

### A-1 [RED] 新增 't'→L2 + wake token "t" 測試
- `tests/sales/test_states.py`：`test_l1_hawk_t_key_triggers_l2`——FakeKeyboardInput 餵 `["t"]`、`tts_is_idle=lambda: True`、run_l1(enter_hawk_immediately=True) → 斷言回 `"L2"`。（此時 run_l1 仍有 opencv 參數，照常傳 FakeOpencv / lambda。）
- `tests/web/test_commands.py`：把 wake 斷言改 `to_token({"type":"wake"}) == "t"`（**會 RED**，現值 "c"）。
- 跑 → 預期兩者 FAIL。

### A-2 [GREEN] l1 hawk 加 't' 分支 + web token + 文字
- `l1.py` `_run_l1_hawk` polling loop：在 q 處理後加
  ```python
  if key == "t":
      return "L2"
  ```
  並把 `if key != "":` 的 reset 條件改成 `if key not in ("", "t"):`（'t' 已消費、不該 reset confirm；對齊 'q' 不 reset 的精神）。**保留** opencv_dwell 觸發（Wave A 共存）。
- `web/commands.py`：`_WAKE_TOKEN = "t"` + 註解更新（wake = 觸控「開始點餐」→ 't'）。
- `main.py`：開場小抄 `'c'` 那行 + `show_hawk_help` 文字改 't'（"叫賣模式：'t' = 開始點餐（模擬觸控）→ 轉 L2；'q' = 退出程式"）。
- 跑 A-1 兩測試 → PASS；跑全量 `tests/` → 全綠（opencv 'c' 測試仍綠，因 opencv 還在）。

### A-3 commit Wave A
- `git add myProgram/sales/states/l1.py myProgram/main.py myProgram/web/commands.py tests/sales/test_states.py tests/web/test_commands.py`
- `feat(l1): add 't' (touch 開始點餐) trigger to hawk → L2`
- `git branch --contains <SHA>` 驗落 worktree。

---

## 階段 Wave B — 移除 OpenCV 模擬層（大；可再切子 commit）

> 簽名移除跨 main↔logic↔machine↔l1↔dialog↔l4 耦合，需一致落地。建議順序：先改 prod 簽名→連動修 test→跑綠。
> 子 commit 切法（各須全綠）建議：B1 sales business logic（constants/l1/machine/logic/dialog/l4 + 刪 subroutine_a + 對應 sales/spec test）；B2 wire-up（main.py opencv callbacks/_S1State/'c' + test_terminal_sim/test_main_read_callbacks）。但若一次改完跑綠更穩也可單 commit。

### B-1 常數 + subroutine_a
- `constants/timing.py`：刪 `OPENCV_DWELL` / `OPENCV_MUTE`（定義 + `__all__` + docstring）。
- 刪 `myProgram/sales/states/l0_subroutine_a.py`（`git rm`）。
- `tests/sales/test_constants.py`：刪 OPENCV_DWELL/MUTE 測試。

### B-2 l1.py 去 opencv
- `_run_l1_hawk`：移 `opencv_enable`/`opencv_dwell_seconds` 參數 + entry `opencv_enable()` + `opencv_dwell_seconds()>=OPENCV_DWELL` 判斷（'t' 觸發 Wave A 已加）；移 `OPENCV_DWELL` import。
- `run_l1`：移 `opencv_dwell_seconds`/`opencv_disable`/`opencv_enable` 參數 + 主迴圈 `opencv_disable()` + service/standby 呼叫處的對應；module docstring callback 清單同步。
- `_run_l1_service`：移 `opencv_disable` 參數 + 呼叫。
- `_run_l1_standby`：移 `opencv_disable`/`opencv_enable` 參數 + 呼叫。

### B-3 machine.py
- `Transition.via_subroutine_a` → `enter_hawk`（dataclass 欄位 + 所有 `Transition(..., via_subroutine_a=True)` setter + `result.via_subroutine_a` reader）。
- `L1State.run` 移 `opencv_dwell_seconds`/`opencv_disable`/`opencv_enable`；`DialogState`/`L4State` 移 `opencv_disable`。
- `SalesMachine.run`：`if result.enter_hawk:` 只 `self.enter_hawk_immediately = True`（移 `run_subroutine_a(...)`）；移 `states.run_subroutine_a` 相關 + docstring。

### B-4 logic.py / l2_l3_dialog.py / l4.py
- `logic.py run()`：移 `opencv_dwell_seconds`/`opencv_disable`/`opencv_enable`/`mute_opencv` 參數 + callbacks dict 條目。
- `l2_l3_dialog.py`：移 `opencv_disable` 參數 + entry 呼叫。
- `l4.py`：移 `opencv_disable` 參數 + entry 呼叫。

### B-5 main.py
- 移 `TerminalSim.opencv_enable/opencv_disable/opencv_dwell_seconds/mute_opencv` 四方法。
- 移 `_S1State` class；`TerminalSim.__init__(self)`（不收 state）；`_build_callbacks()`（不收 state）；`_run_wiring` 不建 state。
- `read_terminal_key`：移整段 `'c'` 特判（mute/dwell）。
- `callbacks()` dict：移 4 個 opencv 鍵（→ 10 鍵）；class docstring 14→10。

### B-6 連動 test 清理（逐檔 grep 清零）
- `test_states.py`：移 `FakeOpencv`；run_l1 callsite 去 opencv 參數；刪 dwell/mute/subroutine-A/'c' 行為測試；保留 Wave A 的 't' 測試。
- `test_logic.py`：logic.run 去 4 opencv kwargs。
- `test_machine.py`：去 opencv callbacks + subroutine_a stub；`via_subroutine_a`→`enter_hawk`。
- `test_main_read_callbacks.py`：去 'c'/opencv；`_S1State()`→`TerminalSim()`/`_build_callbacks()` 無參數。
- `test_terminal_sim.py`：`EXPECTED_KEYS` 去 4 opencv（14→10）+ 測試名/計數；`_S1State` 適配。
- `test_mode_policy.py` / `tests/stt/test_main_wireup.py` / `tests/spec/*` / `conftest.py`：opencv/mute/subroutine-A/'c' 引用清理；L1 scenario 'c'→'t'。

### B-7 全量綠 + commit
- `py -3.14 -m pytest tests/ -q` → 全綠。記尾 30 行。
- grep 確認 opencv/_S1State/via_subroutine_a/run_subroutine_a 在 myProgram/ + tests/ **清零**（殘留只允許歷史文件）。
- `git add <明列所有改檔 + git rm l0_subroutine_a.py>`
- `refactor(sales): remove OpenCV detection layer, rename via_subroutine_a→enter_hawk, drop _S1State`
- `git branch --contains <SHA>` 驗。

---

## Handoff（每 wave sales-coder → 主 agent）
首行 4-status + commit SHA + `git branch --contains` + `git diff --stat` + `py -3.14 -m pytest tests/ -q` 尾 30 行 + grep 清零證明（Wave B）+ 規格衝突處理 + 內部 TaskList。
⛔ 不做 closeout（不 ExitWorktree/merge/push/worktree remove）；不 cd 主 checkout。

> **主 agent 派發策略**：Wave A 一個 sales-coder dispatch（小、additive）；Wave B 一個 dispatch（大，Wave 6 嚴管；若回 BLOCKED「太大」再按 B1/B2 拆序列重派）。每 wave 後主 agent Iron Law 自驗（pytest + grep 清零 + branch）。三段 reviewer 在 Wave B 完成後跑（spec-reviewer + code-quality-reviewer，對整體 opencv 移除）。
