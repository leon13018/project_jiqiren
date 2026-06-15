# 結帳收尾語音合併 — plan（HOW / step-by-step TDD）

> **For agentic workers:** 由 **sales-coder** 執行；步驟 Red→Green→Refactor。
> Spec：[../specs/farewell_voice_merge_2026-06-15_spec.md](../specs/farewell_voice_merge_2026-06-15_spec.md)。
> **現 589 測試是回歸網，每步後跑 `python -m pytest tests/sales/` 保綠。**

**Goal**：把結帳收尾兩拍語音（L4「付款成功」+ L5「謝謝光臨，歡迎再來」）合成單句，由 L4 鏈路 A 播放；動作 bow→wave_hand 順序不變。

**Architecture**：新增合併常數 `L4_A_PAY_SUCCESS_FAREWELL`，L4 `_l4_pay_success` 改播它；L5 `run_l5` 移除 speak（含 `speak` 參數）只留 wave_hand+clear_cart+sleep；`L5State` 同步不再傳 speak；移除 `L4_A_PAY_SUCCESS`/`L5_THANKS` 死常數。

> ⚠️ **必須單一 commit**：若只改 L4（播合併句）而 L5 仍 speak L5_THANKS，會變「…謝謝光臨歡迎再來」**講兩次**——中間態是壞的。故 RED 全部測試 → GREEN 全部 prod → 一次 commit，無中間 commit。

---

## Part A（RED）— 把所有測試改成合併後的期望，跑紅

> 目標：先讓測試表達新行為（L4 播合併常數、L5 不 speak、prewarm 枚舉含新常數），跑 `python -m pytest tests/sales/` 應大量 FAIL（常數不存在 / run_l5 仍收 speak / L5 仍 speak）。

- [ ] **A.1 `tests/sales/test_states.py` import 區**
  - 第 48 行 `L4_A_PAY_SUCCESS,` → `L4_A_PAY_SUCCESS_FAREWELL,`
  - 第 73 行 `L5_THANKS,` → **刪除整行**

- [ ] **A.2 `tests/sales/test_states.py` L4 鏈路 A speak 斷言（三處）**
  3425、4191、5389 行附近，`assert L4_A_PAY_SUCCESS in speak_calls` → `assert L4_A_PAY_SUCCESS_FAREWELL in speak_calls`（連同 f-string 訊息內 `L4_A_PAY_SUCCESS` 字樣一併改名）。

- [ ] **A.3 `tests/sales/test_states.py` L5 行為兩處測試改為「L5 不 speak」**
  - L5-ENTRY-002 測試（~4371-4389）：原斷言 `assert L5_THANKS in speak_calls`。新行為 L5 不再 speak → 改為斷言 **run_l5 期間無 speak 呼叫**（spy speak 收集清單應為空），且 do_action 收到 `ACTION_L5_FAREWELL`。
  - L5 序列測試（6555-6572，原註解「speak(L5_THANKS) -> do_action -> clear_cart -> sleep」）：改為驗 `do_action(ACTION_L5_FAREWELL) -> clear_cart -> sleep`，移除 speak 斷言。
  - **所有 `states.run_l5(...)` 呼叫點（4380、4409、4442、6572）移除 `speak=...` 這個 kwarg**（run_l5 即將去掉該參數）。

- [ ] **A.4 `tests/sales/test_tts_worker.py`（prewarm 枚舉，491/496）**
  ```python
  from myProgram.sales.constants import L4_A_PAY_SUCCESS_FAREWELL, QTY_PROMPT_TEMPLATE
  ...
  assert L4_A_PAY_SUCCESS_FAREWELL in texts
  ```
  （把原 `L5_THANKS` 換成新合併常數——驗證 prewarm 自動枚舉涵蓋新句。）

- [ ] **A.5 `tests/sales/test_main_read_callbacks.py`（127 行樣本字串）**
  該行 `speak(L5_THANKS)` 是「speak callback 非阻塞 enqueue」測試的樣本字串。改用仍存在的常數 `L4_A_PAY_SUCCESS_FAREWELL`，並同步更新該檔 import（原從 constants import `L5_THANKS` 改為 `L4_A_PAY_SUCCESS_FAREWELL`）。

- [ ] **A.6 run_l5 stub 簽名（移除 speak 參數）**
  - `tests/sales/test_logic.py:253`：`def stub_run_l5(*, speak, cart, sleep, do_action):` → `def stub_run_l5(*, cart, sleep, do_action):`
  - `tests/sales/test_machine.py:164`：同上改法。
  - `tests/perf/bench_sales.py:136`：`states.run_l5(speak=_noop, cart=cart, sleep=_noop, do_action=_noop)` → `states.run_l5(cart=cart, sleep=_noop, do_action=_noop)`

- [ ] **A.7 spec 場景敘述檔對齊（`tests/spec/`）**
  `tests/spec/L5_thanks_scenarios.py`、`tests/spec/L4_checkout_scenarios.py` 多為 `###` 敘述。檢查是否有**可執行**斷言引用 `L5_THANKS` / 「L5 speak 致謝」；有則改成合併後行為，純敘述文字一併更新（L5 致謝語音已併入 L4 鏈路 A）。無可執行斷言則只改敘述。

- [ ] **A.8 跑紅**
  Run: `python -m pytest tests/sales/`
  Expected: FAIL（`ImportError: cannot import name 'L4_A_PAY_SUCCESS_FAREWELL'` + run_l5 多傳 speak 等）。確認是「新行為尚未實作」而非測試寫錯。

---

## Part B（GREEN）— prod code 改成合併後行為

- [ ] **B.1 `myProgram/sales/constants/l4_text.py`**
  - `__all__` 內 `"L4_A_PAY_SUCCESS",` → `"L4_A_PAY_SUCCESS_FAREWELL",`
  - 第 29-30 行整段替換：
  ```python
  # L4 鏈路 A 掃碼成功＋致謝合一句語音（2026-06-15 合併原 L4_A_PAY_SUCCESS「付款成功」
  # 與 L5_THANKS「謝謝光臨，歡迎再來」為單句，消除 L4→L5 語音邊界 + 免疫 ALSA drain 尾截。
  # 14 字 → tts._pick_rate 落中句 +6%（已確認接受）。不加結尾「。」match house style。）
  L4_A_PAY_SUCCESS_FAREWELL: str = "付款成功，謝謝光臨，歡迎再來"
  ```

- [ ] **B.2 `myProgram/sales/constants/l5_text.py`**（L5_THANKS 變死常數 → 移除）
  整檔替換為：
  ```python
  """L5 文字常數（P8 拆分自 constants.py）。

  包含 L5（致謝離場）對話層的字串常數。

  2026-06-15：L5_THANKS「謝謝光臨，歡迎再來」已併入 L4_A_PAY_SUCCESS_FAREWELL
  （結帳收尾語音合一句），L5 不再獨立 speak；本模組暫無常數。
  """

  __all__: list = []
  ```

- [ ] **B.3 `myProgram/sales/states/l4.py`**
  - import（第 39 行）：`L4_A_PAY_SUCCESS,` → `L4_A_PAY_SUCCESS_FAREWELL,`
  - `_l4_pay_success`（246-250）整段替換：
  ```python
  def _l4_pay_success(io) -> tuple:
      """鏈路 A 共同體：付款成功＋致謝合一句 speak + 鞠躬動作 + 進 L5（終端 "s" 與客服 "scan" 共用）。"""
      io.speak(L4_A_PAY_SUCCESS_FAREWELL)
      io.do_action(ACTION_L4_PAY)
      return ("L5", 0, 0)
  ```

- [ ] **B.4 `myProgram/sales/states/l5.py`**（移除 speak 參數 + speak 呼叫 + import）
  - import（第 9 行）：`from myProgram.sales.constants import THANK_DELAY, L5_THANKS, ACTION_L5_FAREWELL` → `from myProgram.sales.constants import THANK_DELAY, ACTION_L5_FAREWELL`
  - `run_l5` 函式整段替換（移除 `speak` 參數、`speak(L5_THANKS)` 行、更新 docstring）：
  ```python
  def run_l5(
      cart,
      sleep,
      do_action,
  ) -> tuple:
      """L5 致謝層：最簡單一層，純序列動作，無顧客互動。

      進入時動作（2026-06-15 結帳收尾語音合併後）：
          1. do_action(ACTION_L5_FAREWELL) — 揮手送客（致謝語音已併入 L4 鏈路 A
             的 L4_A_PAY_SUCCESS_FAREWELL 單句，L5 不再 speak）
          2. 清空 cart（交易完成重置）
          3. sleep THANK_DELAY 秒（純等待，不接受任何顧客輸入）
          4. 套用子例程 A 回 L1（return ("L1_via_subroutine_a", 0, 0)）

      Args:
          cart: 購物車 dict（L5 內清空）
          sleep: callback(seconds: float) — 純等待 seconds 秒（不接受任何顧客輸入）
          do_action: callback(name: str) — 同步阻塞跑廠商動作組。L5 在 clear_cart
              之前觸發 ACTION_L5_FAREWELL（揮手送客），阻塞至動作播完才 clear_cart
              + sleep，確保顧客看到完整揮手後再進入致謝靜默期。

      Returns:
          ("L1_via_subroutine_a", 0, 0)
      """
      # S3：揮手送客動作（在 clear_cart 之前 — 規格表明示順序）
      do_action(ACTION_L5_FAREWELL)

      # ENTRY-003：清空 cart（交易完成）
      cart_module.clear_cart(cart)

      # A-001：純等待 THANK_DELAY 秒（不接受任何顧客輸入）後套用子例程 A
      sleep(THANK_DELAY)
      return ("L1_via_subroutine_a", 0, 0)
  ```

- [ ] **B.5 `myProgram/sales/states/machine.py`**（L5State 不再傳 speak）
  `L5State.run`（148-157）內 `states.run_l5(...)` 移除 `speak=cb["speak"],` 一行：
  ```python
          states.run_l5(
              cart=machine.cart,
              sleep=cb["sleep"],
              do_action=cb["do_action"],
          )  # 回傳值無條件忽略（L5 後恆走 subroutine_a 回 L1）
  ```

- [ ] **B.6 跑綠**
  Run: `python -m pytest tests/sales/`
  Expected: Part A 改過的測試 PASS。若仍有紅：逐條判 (a) 漏改的 `L4_A_PAY_SUCCESS`/`L5_THANKS`/`run_l5(speak=...)` 殘留 callsite（grep `L4_A_PAY_SUCCESS\b`、`L5_THANKS`、`run_l5(` 全 `tests/` 掃）→ 補改；(b) 真 regression → 修 prod。**禁無腦改 assert**。

---

## Part C（全量回歸 + 單一 commit）

- [ ] **C.1 全量綠**
  Run: `python -m pytest tests/sales/`
  Expected: `N passed`（0 failed；N 與改前 589 一致或因斷言重構微調，無新增/刪除測試則仍 589）。

- [ ] **C.2 殘留掃描（宣告完成前）**
  Run（grep 全 repo）：`L4_A_PAY_SUCCESS\b`（不含 `_FAREWELL`）應只在本 plan/spec/changelog 文件出現、**零 code/test 殘留**；`L5_THANKS` 同樣零 code/test 殘留；`run_l5(` 呼叫點皆不含 `speak=`。

- [ ] **C.3 commit（單一）**
  ```
  git add myProgram/sales/constants/l4_text.py myProgram/sales/constants/l5_text.py myProgram/sales/states/l4.py myProgram/sales/states/l5.py myProgram/sales/states/machine.py tests/sales/test_states.py tests/sales/test_tts_worker.py tests/sales/test_main_read_callbacks.py tests/sales/test_logic.py tests/sales/test_machine.py tests/perf/bench_sales.py
  ```
  （若 A.7 動到 `tests/spec/*` 一併明列 add。）
  commit message：
  ```
  refactor(sales): 結帳收尾語音合併為單句「付款成功，謝謝光臨，歡迎再來」（L4 播、L5 去 speak 留揮手）

  - 新增 L4_A_PAY_SUCCESS_FAREWELL，L4 _l4_pay_success 改播合併句
  - L5 run_l5 移除 speak 參數與 speak(L5_THANKS)，只留 wave_hand+clear_cart+sleep；L5State 同步不再傳 speak
  - 移除死常數 L4_A_PAY_SUCCESS / L5_THANKS
  - 消除 L4→L5 語音邊界，附帶免疫「付款成功尾巴被截」ALSA drain
  - 測試斷言同步更新（含 prewarm 枚舉、run_l5 簽名）；589 全綠

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```
  跑 `git -C "<worktree>" branch --contains <SHA>` 驗落 `worktree-farewell-merge`（非 main）。

---

## 收尾（主 agent）

三段審（spec-reviewer + code-quality-reviewer，要求精簡純技術輸出）→ Iron Law 親跑 pytest 看 `N passed` → ff-merge → push（Stop hook 自動 sync Pi）→ 清理 worktree。

**pineedtodo**（push 後寫 `resources/pineedtodo/2026-06-15_farewell_voice_merge.md`）：
- Pi 端 `python3.11 -m myProgram.tts_prewarm`（勿與 demo 同跑）→ dev 端 scp 拉回 → `git add myProgram/tts_cache` commit（合成合併句 mp3 入快取、斷網可播）。
- Pi 複測：結帳成功（終端 `s` 或客服 `scan`）→ 聽到**單句**「付款成功，謝謝光臨，歡迎再來」、動作 bow→wave_hand、之後 3s 靜默回叫賣；確認無「謝謝光臨歡迎再來」講兩次、無尾巴被截。
