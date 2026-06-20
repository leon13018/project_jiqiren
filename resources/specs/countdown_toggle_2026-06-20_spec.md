# 倒數印行 env toggle（預設隱藏）— Mini SDD spec

**日期：** 2026-06-20
**類型：** 使用者要求的終端輸出 toggle（超級小：單檔一個 print 閘 + 一條測試 + 文件）

## 動機
`python3.11 -m myProgram --web` 跑時終端每秒印 `timeout = N` / `wait = N` 倒數行，使用者要求預設隱藏、
需要時用 env 變數開（仿 STT_* debug toggle）。兩種倒數行都走 `main._tick_countdown`，一個閘點全覆蓋。

## 改動

### 1. `myProgram/main.py` — 新增 module-level 旗標（接在 `_EARLY_MIC`（:38）後）
```python
# 倒數印行 toggle（env 旗標）：預設 0 = 隱藏 read_customer_input 的 `timeout = N` 與
# sleep 的 `wait = N` 每秒倒數行（demo 終端乾淨）；=1 才印（debug 視覺時間感）。
# 計時行為不受此旗標影響——只抑制視覺印行，等待秒數一秒不差。
_SHOW_COUNTDOWN = bool(int(os.environ.get("SALES_SHOW_COUNTDOWN", "0")))
```

### 2. `myProgram/main.py` — `_tick_countdown` 閘住 print（:67）
- **改前**：`        print(f"{label} = {ticks}")`
- **改後**：
  ```python
          if _SHOW_COUNTDOWN:
              print(f"{label} = {ticks}")
  ```
- docstring 首句「每秒對齊整秒邊界倒數印 `{label} = N`」補一句：印行受 `_SHOW_COUNTDOWN`（env `SALES_SHOW_COUNTDOWN`）控制、預設不印；計時不受影響。

### 3. `tests/sales/test_main_read_callbacks.py` — 新增 toggle 測試（capsys）
- `test_tick_countdown_hidden_by_default`：`_SHOW_COUNTDOWN` 預設 False（或 monkeypatch 設 False）→ 跑 `_tick_countdown`（注入立即 break 的 wait_tick 讓它至少一圈印過點）→ capsys 無 `=` 倒數行。
- `test_tick_countdown_shown_when_flag_on`：monkeypatch `myProgram.main._SHOW_COUNTDOWN=True` → 跑一圈 → capsys 含 `timeout = ` / 對應 `label = N`。
- seam：monkeypatch `myProgram.main._SHOW_COUNTDOWN`（module attr），對齊既有 `_MIC_OPEN_DELAY_SEC` 的 patch pattern。

## Out of scope
- 不藏其他終端輸出（`[語音]` / `[opencv]` / `[模擬]` 等）— 只藏兩種每秒倒數行。
- 不改計時 / timeout / sleep 等待行為（純抑制印行）。
- 不改 toggle 為 CLI 旗標（採 env var，使用者已選）。

## 驗證
- `py -3.14 -m pytest tests/ -q` 全綠（baseline 699；+2 新測試 → 預期 701）。
- Pi：`python3.11 -m myProgram --web` → 無倒數行；`SALES_SHOW_COUNTDOWN=1 python3.11 -m myProgram --web` → 倒數行照印。

## 文件（非 myProgram code，主 agent 改）
- skill `reference/sales-tts-ux.md` Countdown 段註明：倒數預設隱藏、`SALES_SHOW_COUNTDOWN=1` 開啟。

## Commit
- `feat(main): hide per-second countdown lines behind SALES_SHOW_COUNTDOWN env flag`
- git add 明列：`myProgram/main.py tests/sales/test_main_read_callbacks.py`（doc 另 commit 或同 commit 視收尾）。
- 結尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
