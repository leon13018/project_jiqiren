# 叫賣循環修復（間距自上一句播完起算）+ schedule 死抽象移除 — SDD spec

**日期：** 2026-06-20
**類型：** 行為修復（叫賣輪播實機失效）＋ 新增 TTS 非阻塞原語 ＋ 跨檔死抽象移除（重構）
**範圍：** 完整版（跨 5 prod 檔 + 5 test 檔 + 4 docstring；含行為變更 + 新 worker 方法 + callback 簽名 swap）

---

## §1 背景與動機

使用者觀察：「機器人叫賣沒有真的循環叫賣」。實機只喊第 1 句就停。

**根因（測試綠燈但 production 壞掉的 wiring 落差）**：

- `l1._run_l1_hawk` 進場喊 `HAWK_SLOGANS[0]`，後續 5 句靠 `_schedule_hawk_l1()` →
  `schedule(HAWK_INTERVAL, _on_due)` 排程播放（每 12s 一句、`% 6` 輪替）。
- 唯一的 production 實作 `main.py` 的 `schedule` callback 是**故意 no-op**——只印警告就跳過，
  從不執行 `fn`（原註解：「單線程不能背景跑」）。→ 實機只喊第 1 句。
- 單元測試卻過：測試注入的 `FakeScheduler.tick()` 會真的觸發排程 callback。**抽象在測試裡是活的、
  在 production 是死的**——沒有任何測試走 production 的實際循環路徑，故 bug 長期未被回歸網抓到。

grep 全 `myProgram/` 確認：`schedule` 整套抽象**只有叫賣輪播**在消費
（`main → logic.run → machine.L1State → run_l1 → _run_l1_hawk → _schedule_hawk_l1`），
其餘各層只把它往下傳、自己不用。

**使用者裁決**（2026-06-20）：
1. 修循環時連 `schedule` 死抽象端到端移除。
2. **每句間距改成「上一句 TTS 播完後」才起算 HAWK_INTERVAL**（非舊版自 enqueue/排程當下起算）。

---

## §2 設計核心 + 行為規約

**正解：讓 hawk 自己的 polling loop 驅動輪播，並用「TTS 已播完」閘門 + `time.monotonic()` 間距計時。**
不做真排程器（背景 timer thread 戳進業務邏輯 → 違反單線程、引入 race）。hawk polling loop 本就以
0.1s cadence 在跑（`read_terminal_key(timeout=0.1)` 等 OpenCV / 按鍵），加兩個判斷即可。

### 新增 TTS 非阻塞原語 `tts.is_idle()`

「上一句播完才起算間距」需要 hawk loop 查詢「TTS 是否播完當前句」。但 hawk loop **不可**用阻塞的
`wait_idle`（max_wait=30s 與 0.1s polling cadence 衝突會卡死 loop + OpenCV 失效，既有設計例外）。
故在 `tts.py` 加**非阻塞瞬讀** `is_idle()`：

```python
# TtsWorker method
def is_idle(self) -> bool:
    """非阻塞查詢 worker 是否閒置（_pending == 0），立即返回不等待。"""
    with self._cv:
        return self._pending == 0

# module-level
def is_idle() -> bool:
    return _worker.is_idle()
```

安全性：靠既有 R1-race-free 的 `_pending` 計數（`say()` 原子 inc pending 再 put queue → `speak()`
返回後 pending 必 ≥ 1；worker `on_done` finally dec）。`with self._cv` 僅瞬間持 mutex 讀一個 int，
不 `wait`、不阻塞。`_pending==0` ⟺ 當前所有句 synth+play+ALSA-drain 全完成（on_done 在 `_process`
之後才 dec）。合成失敗也會 dec（on_done 在 finally）→ is_idle 仍正確回 True（失敗句跳過、繼續輪播）。

### hawk loop 接 `tts_is_idle` callback（取代被移除的 `schedule`）

`l1.py` 是純業務邏輯、**禁 import tts/worker**（Windows 可測性 + worker 隔離）→ 經 callback 注入。
`main.py` 新增 `tts_is_idle` callback（lazy import tts，對齊既有 speak callback pattern），threaded
`main → logic.run → machine.L1State → run_l1 → _run_l1_hawk`。**callback dict：移 `schedule` + 加
`tts_is_idle` → 仍 14 鍵**。

### `_run_l1_hawk` 新虛擬碼

```
print_terminal(L1_HAWK_ENTRY_PROMPT)
show_hawk_help()
opencv_enable()
do_action(ACTION_L1_HAWK)                      # entry only（servo 過熱防護，不變式保留）
speak(HAWK_SLOGANS[0])                          # 進場立即第 1 句
hawk_index = 1
gap_deadline = None        # None＝正在等當前句播完；非 None＝正在數 HAWK_INTERVAL 間距

while True:
    if opencv_dwell_seconds() >= OPENCV_DWELL:   # 顧客偵測優先
        return "L2"
    if gap_deadline is None:
        if tts_is_idle():                        # 上一句播完了 → 開始算間距
            gap_deadline = time.monotonic() + HAWK_INTERVAL
    elif time.monotonic() >= gap_deadline:       # 間距到 → 喊下一句、回「等播完」態
        speak(HAWK_SLOGANS[hawk_index % len(HAWK_SLOGANS)])
        hawk_index += 1
        gap_deadline = None
    key = read_terminal_key(timeout=0.1)
    if key == "q":
        if _handle_q_press(exit_program, print_terminal):
            continue
        return None
    if key != "":                                # 空 read("")＝polling timeout，不 reset（S6 hot fix 保留）
        _reset_q_confirm()
```

> `gap_deadline is None` 隱式編碼兩態：**等播完**（None）↔ **數間距**（非 None）。喊完下一句即回 None，
> 下一圈又先等該句播完——保證**每句間距都自播完起算**（使用者要的語意）。

### 行為不變式（必須保留 / 達成）

1. **進場立即第 1 句**＋ `do_action(ACTION_L1_HAWK)` 一次（不變）。
2. **每句自「上一句播完」起算 HAWK_INTERVAL(12s) 才喊下一句**，`% len(HAWK_SLOGANS)`(=6) 輪替：
   `0 →(播完+12s)→ 1 → 2 → 3 → 4 → 5 → 0 …`（**本次修復核心**：實機真循環 + 新間距語意）。
3. **輪播不跑 do_action**（servo 過熱防護不變式；`test_l1_hawk_subsequent_rounds_do_not_call_do_action` 守）。
4. **OpenCV dwell ≥ OPENCV_DWELL 任何時刻中斷 → return "L2"**，且 check 排在喊話 / 等播完判斷之前。
5. **q 兩次退出**語意不變；polling 空 read `""` **不** reset confirm（既有 2026-05-28 S6 hot fix）。
6. `speak` 仍非阻塞 enqueue；hawk loop **不**呼叫阻塞 `wait_idle`（既有設計例外，
   `test_read_terminal_key_does_not_call_wait_idle` 守）；改用非阻塞 `tts_is_idle()`。

### 注意（透明說明，非本次改值）

新間距語意下，每句之間是**整整 12s 靜默**（舊版自 enqueue 起算的 12s 含 ~5s 播放 → 實際靜默 ~7s）。
即叫賣節奏會比舊版稀疏。**本次不改 `HAWK_INTERVAL` 值（維持 12）**；若 Pi 實測覺得太疏，屬後續
by-ear 調值（使用者裁量），另開 mini spec 改常數即可。

### 順手修正（refactor 中發現的 latent 耦合）

舊 `_schedule_hawk_l1` 寫死 `HAWK_SLOGANS[hawk_index % 6]`——magic number `6` 與 `HAWK_SLOGANS`
長度隱性耦合。新版改 `% len(HAWK_SLOGANS)` 去耦（karpathy：別寫死可推導常數）。

---

## §3 改檔範圍（高層；step-by-step 見 plan.md）

### Prod（5 檔）
1. **`myProgram/tts.py`**：新增 `TtsWorker.is_idle()`（非阻塞瞬讀 `_pending==0`）+ module-level `is_idle()`。純加法、無既有 caller 動。
2. **`myProgram/sales/states/l1.py`**（核心）
   - 頂層 `import time`。
   - `_run_l1_hawk`：簽名 `schedule` → `tts_is_idle`；entry 後改設 `hawk_index=1` + `gap_deadline=None`；polling loop 內加「等播完→起算間距→到期喊下一句」段（見 §2 虛擬碼）。
   - **移除 `_schedule_hawk_l1` 整個函式**。
   - `run_l1`：簽名 `schedule` → `tts_is_idle`（簽名 + 2 處 `_run_l1_hawk(...)` call site + Args docstring）；模組頂 docstring callback 清單同步。
3. **`myProgram/sales/states/machine.py`**：`L1State.run` 內 `schedule=cb["schedule"],` → `tts_is_idle=cb["tts_is_idle"],`。
4. **`myProgram/sales/logic.py`**：`run()` 簽名 `schedule` → `tts_is_idle`；callbacks dict 同步 swap。
5. **`myProgram/main.py`**：移除 `TerminalSim.schedule` 方法；新增 `TerminalSim.tts_is_idle`（lazy import tts → `return tts.is_idle()`）；`callbacks()` dict 內 `"schedule"` → `"tts_is_idle"`（仍 14 鍵）；class docstring「14 個 bound methods」維持 14（鍵集內容變、數量不變）。

### Tests（5 檔，連動）
6. **`tests/sales/test_tts_worker.py`**：新增 is_idle 測試（仿既有 `_make_worker`/monkeypatch pattern）——pending=0→True；say 後 worker 處理中→False；**斷言非阻塞**（pending>0 時 is_idle 立即返回、不像 wait_idle 阻塞）。
7. **`tests/sales/test_states.py`**：全部 `schedule=` callsite（~20）改為 `tts_is_idle=`（多數注入 `lambda: True`）；**移除 `FakeScheduler` class**；**改寫** `test_l1_hawk_subsequent_rounds_do_not_call_do_action` 用 `fake_monotonic` + `tts_is_idle=lambda: True` 驅動（取代 `scheduler.tick`），保留 `do_action == [ACTION_L1_HAWK]`；**新增** 循環正向測試 + idle-gating 測試（見下）。
8. **`tests/sales/test_logic.py:39`**：`schedule=lambda *a, **k: None,` → `tts_is_idle=lambda: True,`。
9. **`tests/sales/test_machine.py:48`**：同上 swap。
10. **`tests/sales/test_terminal_sim.py`**：`EXPECTED_KEYS` 內 `"schedule"`（:27）→ `"tts_is_idle"`（仍 14 鍵；`..._exact_14_keys` 兩測試名 + 計數斷言不變）。

### Docstring cleanup（stale-after-removal，純文件正確性，低風險）
11. **`tests/spec/{L0_common,L1_mode_select,L2_first_order,L5_thanks}_scenarios.py`**：docstring 內 `schedule` 提及移除/改寫（無實 `schedule=` 呼叫）。

### 新增測試（回歸守門，production 路徑）— in `tests/sales/test_states.py`
- `test_l1_hawk_cycles_slogans_via_poll_loop`（對應 module docstring 既列 L0-SUB-A-003/004）：
  `tts_is_idle=lambda: True` + `fake_monotonic` 推進每圈到期 → 斷言 `speak` 收 `HAWK_SLOGANS[0],[1],[2]…` **依序** + 超過 6 輪 `% len` wrap 回 `[0]`；OpenCV 觸發 "L2" 結束。**會抓到原 production bug**（走真實 loop，非 FakeScheduler 假路徑）。
- `test_l1_hawk_waits_for_tts_idle_before_counting_gap`：`tts_is_idle` 前 N 次回 False（模擬播放中）後回 True → 斷言**在 idle 回 True 前不喊下一句**（間距自播完起算）。

---

## §4 Out of scope（明示不動）

- 不引入真排程器 / `threading.Timer` / 背景 thread（**明確反對**；維持純單線程）。
- **不改 `HAWK_INTERVAL`(=12) 值**（新間距語意造成的稀疏屬後續 by-ear 調值）；不改 `HAWK_SLOGANS` 文案。
- 不改 `tts.py` 既有任何方法（synth/play/wait_idle/prefetch/shutdown）—— is_idle 純加法。
- 不改 do_action 不變式（輪播仍不跑動作）。
- 不動 OpenCV mute/dwell、q-confirm、standby、service 三鏈路任何行為。
- 不動 subroutine_a / dialog(L2/L3) / L4 / L5 / webui / web 鏡像。

---

## §5 規範與參考

- **派 `sales-coder`**（frontmatter 預載 karpathy + TDD + 本 skill；不必 prompt 塞 summary）。
- **時鐘 seam**：`patch("myProgram.sales.states.l1.time.monotonic", side_effect=fake_monotonic)`，對齊既有 l4 tests（`tests/sales/test_states.py` 內 `fake_monotonic` pattern，如 :4264 / :5330 / :5466）。
- **tts is_idle worker test seam**：仿 `tests/sales/test_tts_worker.py` 既有 `_make_worker` + monkeypatch fake synth/popen pattern（wait_idle 系列測試風格）。
- **Wave 6 六招**（跨檔簽名 swap + 連動 test）：先列再做 / 每改完跑 pytest / commit 前自檢 / `-v --tb=short` / 規格衝突 test 必停 / 任何 fail 必停。
- **reuse 不動**：`_handle_q_press` / `_reset_q_confirm`（q-confirm 機制）；`_pending`/`_cv`（is_idle 復用，不新增同步原語）。
- 繁中產出、Linux 路徑、不改 vendor、不用 `git add -A`（CLAUDE.md 紅線，sales-coder 原生載入）。

---

## §6 測試指令 + 預期結果

- **指令**：`py -3.14 -m pytest tests/ -q`（本機 pytest 在 Python 3.14；PATH 的 `python` 是無 pytest 的 3.12）。
- **Baseline（改前實測）**：`tests/` = **694 passed**（其中 `tests/sales/` = 609）。
- **預期（改後）**：**全綠、0 failed / 0 error**。schedule plumbing swap 不刪測試案例，新增約 3-4 個測試（is_idle worker test ×1-2、l1 循環測試 ×1、idle-gating ×1）→ 預期 **≈ 697-698 passed**（sales-coder TDD 拆分可能更多）。
- **主 agent 驗收準則（Iron Law）**：全綠 + 數量 ≥ 697 + 新循環測試（slogan 依序 + mod wrap）+ idle-gating 測試存在。

---

## §7 Commit 規範

建議拆 **2 個邏輯 commit**（各自須 pytest 全綠；git add 明列檔名，禁 `-A`）：

- **C1 — TTS 非阻塞原語**：`feat(tts): add non-blocking is_idle() query`
  - `myProgram/tts.py` + `tests/sales/test_tts_worker.py`（純加法，獨立全綠）
- **C2 — 叫賣循環修復 + schedule→tts_is_idle swap**：`fix(l1): cycle hawk slogans gated on tts idle, replace dead schedule plumbing`
  - `l1.py` + `machine.py` + `logic.py` + `main.py`
  - `tests/sales/test_states.py`（swap callsite + 移 FakeScheduler + 新循環/idle-gating 測試 + 改寫 do_action 測試）+ `test_logic.py` + `test_machine.py` + `test_terminal_sim.py`
  - `tests/spec/{L0,L1,L2,L5}_*_scenarios.py`（docstring）

> 允許 sales-coder 在「各 commit 全綠」前提下微調切分。commit message 結尾
> `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

## §8 流程鳥瞰

```
[現況] entry speak[0] → _schedule_hawk_l1 → schedule()=no-op → 🔇 永不循環
                                                  └ 測試 FakeScheduler.tick 假驅動（綠燈騙過）

[修後] entry speak[0] + gap_deadline=None
       polling loop ──每圈──▶ opencv? ─yes→ L2
                              gap=None 且 tts_is_idle()? ─yes→ gap=now+12   （上一句播完才起算）
                              gap≠None 且 到期? ─yes→ speak[i%6] + i++ + gap=None   ✅ 實機真循環
                              read_key(0.1) → q×2 退出

       新原語  tts.is_idle()（非阻塞瞬讀 _pending==0）
       callback  main.tts_is_idle → logic → machine → run_l1 → hawk loop
       移除      schedule 全鏈（main→logic→machine→run_l1→_schedule_hawk_l1）；dict 鍵 schedule→tts_is_idle（仍 14）
```
