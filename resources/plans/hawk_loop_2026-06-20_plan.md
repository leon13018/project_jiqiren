# 叫賣循環修復（間距自上一句播完起算）+ schedule 死抽象移除 — plan（HOW，step-by-step）

> 對應 spec：`resources/specs/hawk_loop_2026-06-20_spec.md`。
> 環境：worktree `.claude/worktrees/hawk-loop/`，branch `worktree-hawk-loop`，首 commit 是 spec/plan doc（不改）。
> 測試指令：`py -3.14 -m pytest tests/sales/ -q`（快速）／ 收尾 `py -3.14 -m pytest tests/ -q`（全量）。
> ⚠️ PATH 的 `python` 是無 pytest 的 Python 3.12；**務必用 `py -3.14`**。
> Wave 6：每改完一步即跑 pytest，不累積；任何 fail 必停回報；commit 前 `git diff --stat` + `git status` 自檢。

---

## Step 0 — 先列再做（Wave 6 第 1 招）

實作前再 grep 對齊清單（spec §3 已列）：
- `schedule` in `myProgram/`：main.py / logic.py / machine.py / l1.py。
- `schedule=` in `tests/`：test_states.py(~20) / test_logic.py:39 / test_machine.py:48 / test_terminal_sim.py:27。
- docstring `schedule`：tests/spec/{L0,L1,L2,L5}_*_scenarios.py。
return thinking 內列實際命中清單。

---

## 階段 C1 — TTS 非阻塞原語 `is_idle()`

### Step C1-1 [RED] 新增 is_idle worker 測試
檔：`tests/sales/test_tts_worker.py`，仿既有 `_make_worker`/monkeypatch（wait_idle 系列）pattern 新增：
- `test_is_idle_true_when_no_pending`：新建 worker（fake synth/popen）、未 say → `worker.is_idle() is True`。
- `test_is_idle_false_while_processing`：say + worker hang 在 popen.wait（同 R1 regression test 的 hang seam）→ `worker.is_idle() is False`，且**立即返回**（不阻塞 / 不等 max_wait）。
- 跑 `py -3.14 -m pytest tests/sales/test_tts_worker.py -q` → **預期 FAIL**（is_idle 尚未實作 → AttributeError）。記 FAIL 證據。

### Step C1-2 [GREEN] tts.py 加 is_idle
檔：`myProgram/tts.py`。
- `TtsWorker` 加方法（放 wait_idle 附近）：
  ```python
  def is_idle(self) -> bool:
      """非阻塞查詢 worker 是否閒置（_pending == 0），立即返回不等待。

      給 L1 hawk polling loop 用：hawk 不可呼叫阻塞的 wait_idle（max_wait=30s 與
      0.1s polling cadence 衝突），但叫賣輪播需「上一句播完才起算間距」→ 用本方法
      非阻塞瞬讀。只在 _cv mutex 下讀一個 int，立即返回。
      """
      with self._cv:
          return self._pending == 0
  ```
- module-level（放 wait_idle 對外 API 附近）：
  ```python
  def is_idle() -> bool:
      """對外 API：非阻塞查詢 TTS 是否已播完當前所有句（_pending==0）。"""
      return _worker.is_idle()
  ```
- 跑 C1-1 兩測試 → **預期 PASS**。

### Step C1-3 跑全量 sales + commit C1
- `py -3.14 -m pytest tests/sales/ -q` → 全綠（≥ 611：baseline 609 + 新 2）。
- 自檢 `git diff --stat` + `git status`。
- `git add myProgram/tts.py tests/sales/test_tts_worker.py`
- commit：`feat(tts): add non-blocking is_idle() query`。
- `git branch --contains <SHA>` 驗落 `worktree-hawk-loop`。

---

## 階段 C2 — 叫賣循環修復 + schedule→tts_is_idle 端到端 swap

> C2 是跨檔簽名 swap（schedule 移除 + tts_is_idle 新增，同批 callsite）+ l1 行為變更。
> 一個 sales-coder dispatch 內按下列序做，每改完一檔即跑 pytest。

### Step C2-1 [RED] 新增 l1 循環 + idle-gating 測試
檔：`tests/sales/test_states.py`，新增兩測試（此步 run_l1 還沒改簽名 → 先以**目標新簽名**寫，會 RED）：
- `test_l1_hawk_cycles_slogans_via_poll_loop`：
  - `speak_calls=[]`；`opencv = FakeOpencv`（前面多圈 dwell=0，**推進足夠多圈以觀察至少一次 wrap**——即 `HAWK_SLOGANS[0]` 在 entry 之後再次出現，約需喊出 ≥7 句 ≈ 14+ 圈——再回 OPENCV_DWELL 結束）；`kbd=FakeKeyboardInput([""]*大量)`；`tts_is_idle=lambda: True`。注意每喊一句約耗 2 圈（一圈設 gap_deadline、一圈到期），FakeOpencv 觸發門檻要算進去。
  - `fake_monotonic`：closure 每呼叫 `+= HAWK_INTERVAL`（每圈到期 → 每圈喊一句）：
    ```python
    _t=[0.0]
    def fake_monotonic(): _t[0]+=HAWK_INTERVAL; return _t[0]
    ```
  - `with patch("myProgram.sales.states.l1.time.monotonic", side_effect=fake_monotonic): states.run_l1(..., tts_is_idle=..., enter_hawk_immediately=True)`。
  - Assert：`speak_calls[0]==HAWK_SLOGANS[0]`；後續依序 `[1][2][3][4][5]` 再 wrap `[0]`（用 `len(HAWK_SLOGANS)` 非寫死 6）。
- `test_l1_hawk_waits_for_tts_idle_before_counting_gap`：
  - `tts_is_idle` 用 closure 前 N 次回 False、之後 True（模擬播放中）；fake_monotonic 推進。
  - Assert：idle 回 True 前 `speak_calls` 維持只有 `[0]`（沒喊下一句）；idle True 後且間距到才出現 `[1]`。
- 跑這兩測試 → **預期 FAIL**（run_l1 還沒收 tts_is_idle 參數 / loop 還沒改）。記 FAIL。

### Step C2-2 [GREEN] l1.py 改 idle-gated monotonic 驅動 + 簽名 swap
檔：`myProgram/sales/states/l1.py`。
- 頂層 `import time`。
- `_run_l1_hawk`：簽名 `schedule` → `tts_is_idle`；entry `speak(HAWK_SLOGANS[0])` 後改：
  ```python
  hawk_index = 1
  gap_deadline = None
  ```
  polling loop 內、opencv check 之後、read_key 之前插入（見 spec §2 虛擬碼）：
  ```python
  if gap_deadline is None:
      if tts_is_idle():
          gap_deadline = time.monotonic() + HAWK_INTERVAL
  elif time.monotonic() >= gap_deadline:
      speak(HAWK_SLOGANS[hawk_index % len(HAWK_SLOGANS)])
      hawk_index += 1
      gap_deadline = None
  ```
- **移除 `_schedule_hawk_l1` 整個函式**。
- `run_l1`：簽名 `schedule` → `tts_is_idle`；2 處 `_run_l1_hawk(...)` call site `schedule=schedule` → `tts_is_idle=tts_is_idle`；Args docstring + 模組頂 docstring callback 清單同步。
- 跑 C2-1 兩測試 → **預期 PASS**（但 tests/sales 其他傳 `schedule=` 的會 RED，下一步修）。

### Step C2-3 machine.py / logic.py / main.py swap plumbing
- `machine.py` `L1State.run`：`schedule=cb["schedule"],` → `tts_is_idle=cb["tts_is_idle"],`。
- `logic.py` `run()`：簽名 `schedule` → `tts_is_idle`；callbacks dict `schedule=schedule,` → `tts_is_idle=tts_is_idle,`。
- `main.py`：移除 `TerminalSim.schedule` 方法整段；新增：
  ```python
  def tts_is_idle(self):
      """非阻塞查詢 TTS 是否閒置（hawk 輪播「上一句播完才起算間距」用）。

      lazy import 對齊 speak callback pattern（Windows pytest 不觸發 edge_tts import）。
      """
      from myProgram import tts
      return tts.is_idle()
  ```
  `callbacks()` dict：`"schedule": self.schedule,` → `"tts_is_idle": self.tts_is_idle,`（仍 14 鍵）。class docstring「14 個 bound methods」維持。

### Step C2-4 連動 test 檔 swap
- `tests/sales/test_states.py`：全部 `schedule=...` callsite 改 `tts_is_idle=lambda: True`（grep `schedule` 清零）；**移除 `FakeScheduler` class**；**改寫** `test_l1_hawk_subsequent_rounds_do_not_call_do_action` 用 fake_monotonic + `tts_is_idle=lambda: True` 驅動 ≥4 輪，保留 `do_action_calls == [ACTION_L1_HAWK]`。
- `tests/sales/test_logic.py:39`：`schedule=...` → `tts_is_idle=lambda: True,`。
- `tests/sales/test_machine.py:48`：同上。
- `tests/sales/test_terminal_sim.py`：`EXPECTED_KEYS` 內 `"schedule"` → `"tts_is_idle"`（仍 14；測試名/計數不動）。

### Step C2-5 docstring cleanup（tests/spec）
- `tests/spec/{L0_common,L1_mode_select,L2_first_order,L5_thanks}_scenarios.py`：docstring `schedule` 提及移除/改寫。

### Step C2-6 跑全量 + commit C2
- `py -3.14 -m pytest tests/ -q` → 全綠（≈ 697-698）。記尾 30 行。
- 自檢 `git diff --stat` + `git status`（主 checkout 不該有殘留）。
- `git add myProgram/sales/states/l1.py myProgram/sales/states/machine.py myProgram/sales/logic.py myProgram/main.py tests/sales/test_states.py tests/sales/test_logic.py tests/sales/test_machine.py tests/sales/test_terminal_sim.py tests/spec/L0_common_scenarios.py tests/spec/L1_mode_select_scenarios.py tests/spec/L2_first_order_scenarios.py tests/spec/L5_thanks_scenarios.py`
- commit：`fix(l1): cycle hawk slogans gated on tts idle, replace dead schedule plumbing`。
- `git branch --contains <SHA>` 驗落 worktree。

---

## Handoff 回報（sales-coder → 主 agent）

首行 4-status（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）。附：
- 兩 commit SHA + `git branch --contains` 結果。
- `git diff --stat`（兩 commit 合計）。
- `py -3.14 -m pytest tests/ -q` 尾 30 行（passed 數）。
- 任何規格衝突 test（Wave 6 第 5 招：明顯則更新並列清單，不明顯則停下回報）。
- ⛔ 不做 post-commit closeout（不 ExitWorktree / merge / push / worktree remove）；不 cd 主 checkout。
