# 移除 OpenCV 偵測、改觸控「開始點餐」('t') 觸發 L2 — SDD spec

**日期：** 2026-06-20
**類型：** 大型重構（移除整套 OpenCV 模擬層 + 換觸發來源 + 連帶死碼/命名清理）
**範圍：** 完整版（9 prod 檔 + 刪 1 檔 + 17 test 檔，612 處 opencv 相關引用）

---

## §1 背景與動機

使用者決定**取消 OpenCV 偵測**，改為「顧客觸控螢幕『開始點餐』→ 進 L2」；終端用按鍵 **`t`** 模擬該觸控。

**現況架構（關鍵）**：觸控→對話**已經抽象化**——`web/commands.py` 把觸控 `{"type":"wake"}` 映射成 token `"c"`（`_WAKE_TOKEN`），注入 input queue 後 `main.read_terminal_key` 認 `'c'` → 設 `opencv_dwell` → `l1._run_l1_hawk` 輪詢 `opencv_dwell_seconds() >= OPENCV_DWELL` → 回 `"L2"`。OpenCV + `'c'` 鍵 + dwell/mute 就是「模擬硬體偵測」那一層；commands.py 註解早寫明「未來接真硬體改這兩個映射」。webui「開始點餐」按鈕（app.js:626 `exitStandby`）已送 `{type:"wake"}`。

**本質**：把 OpenCV 模擬層整個拆掉，hawk loop 直接讀 `'t'` → L2，web 觸控 token 從 `"c"` 改 `"t"`。

**使用者裁決（2026-06-20）**：① OpenCV **全移除**（dwell/mute/enable/disable callbacks + `_S1State` opencv 欄位 + `OPENCV_DWELL`/`OPENCV_MUTE` 常數 + subroutine A 緩衝 + 各層 `opencv_disable` 防呆）；② 連帶 `_S1State`（移除後空殼）與 `Transition.via_subroutine_a`（更名 `enter_hawk`）一起清理；③ `'s'`/掃碼付款（L4→L5）**維持不變**。

---

## §2 設計核心 + 行為規約

**觸發方案**：hawk loop 直接讀 `'t'` 鍵 → 回 `"L2"`（沿用既有 `'q'` 鍵處理 pattern，最小、不新增 callback、不新增偵測抽象）。

### `_run_l1_hawk` 新虛擬碼（移除 opencv，加 't'）
```
print_terminal(L1_HAWK_ENTRY_PROMPT)
show_hawk_help()                               # 文字改：'t' = 開始點餐 → 轉 L2；'q' = 退出
do_action(ACTION_L1_HAWK)
speak(HAWK_SLOGANS[0]); hawk_index = 1; gap_deadline = None

while True:
    # 叫賣輪播（idle-gated monotonic，不變，見 hawk_loop spec）
    if gap_deadline is None:
        if tts_is_idle(): gap_deadline = time.monotonic() + HAWK_INTERVAL
    elif time.monotonic() >= gap_deadline:
        speak(HAWK_SLOGANS[hawk_index % len(HAWK_SLOGANS)]); hawk_index += 1; gap_deadline = None
    key = read_terminal_key(timeout=0.1)
    if key == "q":
        if _handle_q_press(...): continue
        return None
    if key == "t":                             # 觸控「開始點餐」（web wake → token "t" 同路徑）
        return "L2"
    if key not in ("", "t"):                    # 真實非 q/t 鍵才 reset confirm（空 read polling 不 reset）
        _reset_q_confirm()
```
> 移除：`opencv_enable()`（entry）、`opencv_dwell_seconds() >= OPENCV_DWELL` 觸發判斷。其餘（slogan 輪播、q-confirm、polling cadence）不變。

### read_terminal_key（main.py）
移除 `'c'` 特判整段（mute/dwell 設定）。`'t'` 不需特判——`normalize` 後原樣 return，hawk loop 自己比 `key == "t"`。其他 caller（主選單 `'1'/'2'/'3'`、standby `'r'`）不受影響。

### web 觸發（webui app.js 不動）
`web/commands.py`：`_WAKE_TOKEN = "t"`（原 `"c"`）。「開始點餐」→ `{type:"wake"}` → `to_token` → `"t"` → 注入 → `read_terminal_key` 回 `"t"` → hawk → L2。

### 移除 cascade（行為保留論證）
- **subroutine A（`l0_subroutine_a.py`）**：唯一作用是 `mute_opencv(OPENCV_MUTE)`。OpenCV 移除後無自動偵測可 debounce → mute 無意義 → **刪檔**。machine 的 `run_subroutine_a` 調用移除、保留 `enter_hawk_immediately = True`（交易後仍直接回 hawk，可觀察行為不變）。
- **各層 `opencv_disable` 防呆**（l1 menu/service/standby、l2_l3_dialog entry、l4 entry）：無偵測可關 → 全 no-op 移除，行為不變。
- **`Transition.via_subroutine_a` → `enter_hawk`**：subroutine A 刪除後該旗標只代表「下輪 L1 直接 hawk」，更名達意（machine.py dataclass 欄位 + Dialog/L4/L5 State 的 setter 同步）。
- **`_S1State`**：移除 opencv 三欄位（`opencv_enabled`/`opencv_dwell`/`opencv_mute_until`）後為空 → **整個刪除**；`TerminalSim(state)` → `TerminalSim()`、`_build_callbacks(state)` → `_build_callbacks()`、`_run_wiring` 不再建 state。

### 行為不變式（保留）
1. L1 主選單 `1=叫賣/2=待機/3=客服/q=退出`、standby `'r'`、service 流程不變（只少了 opencv_disable 副作用）。
2. hawk 叫賣輪播（idle-gated 12s、mod 6）不變；q 兩次退出、polling 空 read 不 reset 不變。
3. dialog(L2/L3)/L4/L5/cart/NLU/L4 budget 完全不動。
4. `'s'`/掃碼付款（read_customer_input 認 's' → L4→L5）不變；`_PAY_TOKEN="s"` 不動。
5. webui app.js 不動（已送 `{type:"wake"}`）。

---

## §3 改檔範圍（prod 高層；exact test 列舉由 sales-coder Wave 6「先列再做」grep）

### Prod（8 改 + 1 刪）
1. **`myProgram/sales/constants/timing.py`**：移除 `OPENCV_DWELL` / `OPENCV_MUTE` 定義 + `__all__` 條目 + module docstring 提及。
2. **`myProgram/sales/states/l1.py`**：`_run_l1_hawk` 移 `opencv_enable`/`opencv_dwell_seconds` 參數 + dwell 觸發 → 加 `key=="t": return "L2"`；`run_l1`/`_run_l1_service`/`_run_l1_standby` 移 `opencv_disable`/`opencv_enable`/`opencv_dwell_seconds` 參數 + `opencv_disable()` 呼叫；移 `OPENCV_DWELL` import；module + 各 docstring callback 清單同步；`show_hawk_help` 對應（text 在 main.py）。
3. **`myProgram/sales/states/l0_subroutine_a.py`**：**刪檔**。
4. **`myProgram/sales/states/machine.py`**：`L1State.run` 移 `opencv_dwell_seconds`/`opencv_disable`/`opencv_enable`；`DialogState`/`L4State` 移 `opencv_disable`；移 `run_subroutine_a(mute_opencv=...)` 調用（留 `enter_hawk_immediately=True`）；`Transition.via_subroutine_a` → `enter_hawk`（欄位 + 所有 setter/reader）；移 subroutine_a 相關 docstring。
5. **`myProgram/sales/logic.py`**：`run()` 移 `opencv_dwell_seconds`/`opencv_disable`/`opencv_enable`/`mute_opencv` 參數 + callbacks dict 條目。
6. **`myProgram/sales/states/l2_l3_dialog.py`**：移 `opencv_disable` 參數 + entry 呼叫。
7. **`myProgram/sales/states/l4.py`**：移 `opencv_disable` 參數 + entry 呼叫。
8. **`myProgram/main.py`**：移 `TerminalSim.opencv_enable/opencv_disable/opencv_dwell_seconds/mute_opencv` 四方法；移 `_S1State`（空殼）+ `TerminalSim(state)`→`TerminalSim()` + `_build_callbacks`/`_run_wiring` 對應；`read_terminal_key` 移 `'c'` 特判段；`callbacks()` dict 移 4 個 opencv 鍵（**14 → 10 鍵**）；class docstring「14 → 10」；開場小抄 `'c'`→`'t'` 文字；`show_hawk_help` 文字改 `'t' = 開始點餐（模擬觸控）→ 轉 L2；'q' = 退出`。
9. **`myProgram/web/commands.py`**：`_WAKE_TOKEN = "t"`（原 `"c"`）+ 註解（wake = 模擬觸控「開始點餐」→ 't' → L1 hawk→L2）。
10. **next_state 魔法字串契約 `"L1_via_subroutine_a"` → `"L1_enter_hawk"`**（2026-06-20 補正，使用者裁決一併更名；因已刪除的 subroutine A 而命名）：橫跨 `l2_l3_dialog.py`（run_dialog 回傳）/ `l4.py`（run_l4 回傳）/ `l5.py`（run_l5 回傳）/ `logic.py`（docstring shape 註）/ `machine.py`（State 子類別 `if next_state == "L1_via_subroutine_a"` 消費）/ `states/__init__.py`（若有）。**純 magic-string 改名、零邏輯**（不碰 NLU/cart/L4 budget/L5 序列）。`tts.py:12` 一句歷史 opencv docstring 註解一併清（純文字）。
> 注意 `via_subroutine_a`（machine dataclass 欄位，#4）與 `"L1_via_subroutine_a"`（next_state 字串契約，#10）是**兩個不同的東西**——前者 grep `via_subroutine_a` 的真欄位、後者是 `L1_via_subroutine_a` 字串；本次兩者都改名（→ `enter_hawk` / `"L1_enter_hawk"`）才能真 grep 清零。

### Tests（17 檔，~612 處；類別指引，sales-coder 逐檔 grep 清零 opencv/mute/subroutine_a/dwell/FakeOpencv/_S1State）
- **`tests/sales/test_states.py`**（~426）：移除 `FakeOpencv` class；所有 `run_l1(...)` callsite 移 `opencv_*` 參數；**刪除**純 opencv 行為測試（dwell 門檻、brief detection filter、mute、subroutine-A 緩衝、`'c'` 觸發）；把「`'c'`/dwell → L2」測試**改寫**為「`'t'` → L2」。
- **`tests/sales/test_logic.py`**（~61）：`logic.run(...)` 移 4 個 opencv callback kwargs。
- **`tests/sales/test_main_read_callbacks.py`**（~32）：移 `'c'`/opencv 相關；`_S1State()` → 無參數建構調整。
- **`tests/sales/test_machine.py`**（~30）：移 opencv callbacks + subroutine_a stub；`via_subroutine_a` → `enter_hawk`。
- **`tests/sales/test_terminal_sim.py`**（8）：`EXPECTED_KEYS` 移 4 opencv 鍵（**14→10**）+ 測試名 `exact_14_keys`→`exact_10_keys`；`_S1State` 移除適配。
- **`tests/sales/test_constants.py`**（5）：刪 `OPENCV_DWELL`/`OPENCV_MUTE` 測試。
- **`tests/sales/test_mode_policy.py`**（2）、**`tests/stt/test_main_wireup.py`**（2）：opencv 引用清理。
- **`tests/web/test_commands.py`**（1）：wake token 斷言 `"c"`→`"t"`。
- **`tests/spec/{L0,L1,L2,L3,L4,L5}_*_scenarios.py`**（~37）：opencv/mute/subroutine-A scenario + docstring 清理；L1 的 `'c'`→`'t'` 觸發 scenario 改寫。
- **`tests/conftest.py`**（1）：opencv 引用（若有）清理。
- **`tests/perf/bench_sales.py`**（2026-06-20 補正，spec 原漏）：`opencv_disable=_noop` 等 opencv callback（移除 logic.run 參數後會壞）+ `"L1_via_subroutine_a"` 字串 → 清理 / 改 `"L1_enter_hawk"`。

---

## §4 Out of scope（明示不動）
- `'s'`/掃碼付款路徑（read_customer_input 's' → L4→L5）、`_PAY_TOKEN`。
- webui `app.js`（已送 `{type:"wake"}`，不改）。
- dialog NLU / 商品解析 / cart / L4 雙計時器 budget / L5 序列 **邏輯**一律不動。（例外：§3#10 的 `"L1_via_subroutine_a"`→`"L1_enter_hawk"` 是純 next_state magic-string 改名、零邏輯影響——L4/L5/dialog「不動」指**邏輯不動**，回傳字串值改名不算動邏輯。）
- 不加任何新觸控功能（只換 wake 觸發來源）。

---

## §5 規範與參考
- **派 `sales-coder`**（opus，frontmatter 預載）；大型跨檔簽名移除 → **Wave 6 六招**必入 prompt；按 plan **分 wave 序列**派發。
- **pytest 用 `py -3.14 -m pytest`**（PATH 的 `python` 無 pytest）。baseline `tests/` = 713 passed。
- reuse：`'t'` 觸發沿用 hawk loop 既有 `'q'` 鍵處理 pattern（同層 if/elif）。
- 繁中、Linux 路徑、不改 vendor、不用 `git add -A`（CLAUDE.md 紅線）。

---

## §6 測試指令 + 預期結果
- **指令**：`py -3.14 -m pytest tests/ -q`。
- **Baseline**：`tests/` = **713 passed**。
- **預期（改後）**：**全綠、0 fail / 0 error**。本變更**刪除**的 opencv 測試多於新增的 't' 測試 → **總數會明顯下降**（屬正常，opencv 行為整批移除）。
- **主 agent 驗收準則（Iron Law）**：全綠 + `grep -ri "opencv\|OPENCV\|mute_opencv\|opencv_dwell\|FakeOpencv\|_S1State\|via_subroutine_a\|run_subroutine_a" myProgram/ tests/` 清零（殘留只允許「歷史 changelog/spec」類非 code 文件）+ web wake token 為 "t" + hawk 't'→L2 測試存在。**不卡特定數字**（刪除型重構數字必降）。

---

## §7 Commit 規範（分 wave；各 commit 全綠；git add 明列，禁 -A）

- **Wave A — 加 't' 觸發（additive，opencv 暫共存）**：
  `feat(l1): add 't' (touch 開始點餐) trigger to hawk → L2`
  - l1.py（hawk 加 `key=="t"` 分支）+ main.py 小抄/show_hawk_help 文字 + web/commands.py `_WAKE_TOKEN`→"t" + 對應測試（'t'→L2、wake token "t"）。此時 opencv 'c' 仍可觸發（不破既有測試）。
- **Wave B — 移除 OpenCV 模擬層（大）**：
  `refactor(sales): remove OpenCV detection layer, rename via_subroutine_a→enter_hawk, drop _S1State`
  - constants/l1/machine/logic/l2_l3_dialog/l4/main + 刪 l0_subroutine_a.py + 全部連動 test 清理。
  - sales-coder 可在「各 commit 全綠」前提下把 Wave B 再切子 commit（如 business-logic 一批、wire-up 一批）。
- commit message 結尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

## §8 流程鳥瞰
```
[現況] 觸控 wake → token "c" → read_terminal_key 'c' → set opencv_dwell
        → hawk loop: opencv_dwell_seconds()>=OPENCV_DWELL → L2
        交易後 → subroutine_a(mute 6s) → enter_hawk

[改後] 觸控 wake → token "t" ┐
        終端按 't'            ┴→ read_terminal_key 回 "t" → hawk loop: key=="t" → L2
        交易後 → enter_hawk（直接，無 mute）
        OpenCV 模擬層（dwell/mute/enable/disable/_S1State/常數/subroutine_a）全移除
        via_subroutine_a → enter_hawk（更名）；callbacks dict 14→10
```
```
Wave A（加 't'，綠）──▶ Wave B（拆 opencv，綠）──▶ reviewer ──▶ 收尾
```
