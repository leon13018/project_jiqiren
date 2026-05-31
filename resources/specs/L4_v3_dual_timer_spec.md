# L4 v3：雙獨立計時器設計 — SDD 規格書

> **狀態**：規劃中（2026-05-31 提出）
> **Supersedes**：當前 v2（commit `46c0b52` 以降）的 L4 主等待迴圈設計
> **不取代**：`L4.md` 原規格書 — 本 v3 只重設計「計時器 + 主迴圈」，鏈路 A/B/C 退出語意 + 客服 helper 行為 + cancel_confirm helper 行為**完全不變**

---

## 1. 背景與動機

### 1.1 當前 v2 設計（commit `5710826` 為止）

| 項目 | 值 |
|---|---|
| `L4_TOTAL_BUDGET` | 30s（單一 wall-clock budget） |
| `L4_PROMPT_INTERVAL` | 12s（「沒回應」才觸發重 speak `L4_REMIND_PROMPT`） |
| 亂答 / ack | 不重置 budget；下次 `read` 仍用 `min(12s, remaining)` |
| QR 視覺刷新 | 無此概念 |

### 1.2 Pi demo 觀察到的不對齊

從 user 提供的 transcript：
```
timeout = 12 / 11 / 10
亂打 → [語音] 不好意思我聽不太懂
timeout = 12 / 11 / 10 / 9 / 8     ← 視覺上「重置」12s 倒數
好的 → [語音] 好的，請您方便時掃碼付款即可
timeout = 12 / 11 / 10 / 9 / 8     ← 再次「重置」
亂打 timeout = 7
...
timeout = 3 / 2 / 1 → [語音] 請您掃碼付款 → [語音] 已取消這次交易
```

**問題：**
1. 雖然真正的 `L4_TOTAL_BUDGET` 沒重置，但 ack speak 後新的 `read_customer_input(timeout=12)` 重新從 12 倒數，視覺上像「循環倒數被打斷重來」
2. 沒有「無條件每 12s 刷新 QR」概念 — 循環只在「真的 silent」時觸發 remind
3. 總 budget 30s 不是循環時間的倍數 → 倒數視覺不連續（最後一輪只剩 6s）

### 1.3 v3 設計核心

**兩個獨立 wall-clock 計時器，與子鏈路狀態完全解耦：**

| 計時器 | 秒數 | 行為 |
|---|---|---|
| **總 budget** | 36s | 耗盡 → forced exit（speak `L4_D_FORCED_EXIT` + clear cart + 退 L1） |
| **QR 刷新循環** | 12s | 每循環開頭：重印終端結帳區塊 + 重 speak `L4_REMIND_PROMPT`（「請您掃碼付款」） |

**關係：** 36 = 12 × 3，總 budget 期間共 3 個循環。進入 L4 算第 1 個循環開頭（entry prompt + 結帳明細 = 第 1 次刷新）。

---

## 2. 行為規約

### 2.1 進入 L4

1. `opencv_disable()`（防呆，dialog 已關過）
2. 計算總額 → `_l4_print_entry_detail(cart, total, print_terminal)` ＝ **第 1 次循環刷新（視覺面）**
3. `speak_and_wait(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))` — 首次帶完整總金額語音
4. TTS 播完返回 → **同時起 budget deadline + 循環 deadline**
   ```python
   now = time.monotonic()
   budget_deadline = now + L4_TOTAL_BUDGET           # 36s
   cycle_deadline  = now + L4_QR_REFRESH_INTERVAL    # 12s
   ```

### 2.2 主等待迴圈每次 iteration

```python
while True:
    now = time.monotonic()
    budget_remaining = budget_deadline - now
    cycle_remaining  = cycle_deadline  - now

    # 1. budget 耗盡 → forced exit
    if budget_remaining <= 0:
        return _l4_exit_d_forced(speak, cart)

    # 2. 循環到期 → 重印 + 重 speak L4_REMIND_PROMPT → 起下一個循環
    #    （不影響 budget_deadline）
    if cycle_remaining <= 0:
        _l4_print_entry_detail(cart, total, print_terminal)
        speak(L4_REMIND_PROMPT)
        cycle_deadline = time.monotonic() + L4_QR_REFRESH_INTERVAL
        continue

    # 3. read，timeout = min(circle_remaining, budget_remaining)
    response = read_customer_input(timeout=min(cycle_remaining, budget_remaining))

    if response is None:
        # silent → 直接 continue（下次 iteration 由 cycle_deadline 判斷是否該刷新）
        continue

    # 4. 有回應 → dispatch
    result = _l4_dispatch_response(...)
    if isinstance(result, tuple):
        return result
    if result is None:
        # 客服 yes 繼續 → 重置兩計時器 + 重印 + 重 speak entry prompt（fresh start）
        _l4_print_entry_detail(cart, total, print_terminal)
        speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
        now = time.monotonic()
        budget_deadline = now + L4_TOTAL_BUDGET
        cycle_deadline  = now + L4_QR_REFRESH_INTERVAL
        continue
    # "ack" → 不重置任何計時器，繼續主迴圈
    continue
```

### 2.3 子鏈路（不影響兩計時器）

| 輸入 | 動作 | 計時器影響 |
|---|---|---|
| `s`（終端掃碼） | speak `L4_A_PAY_SUCCESS` + `do_action(ACTION_L4_PAY)` → L5 | n/a（退出 L4） |
| 等待安撫 intent | speak `L4_ACK_GENTLE`（「好的，請您方便時掃碼付款即可」） | **完全不影響** |
| 亂答（unclear / 想一下 / 結帳 / 商品 / 無法判斷） | speak `L4_UNCLEAR_NOTICE`（「不好意思我聽不太懂」） | **完全不影響** |
| 拒絕 intent | 進 `cancel_confirm` 6s 子狀態（見 2.4） | 子狀態期間 **暫停**，退出後 **補償** |
| 客服 intent | 進 `service_confirm` 24s 子狀態（見 2.4） | 子狀態期間 **暫停**，退出後 **補償** |

### 2.4 子狀態暫停 / 恢復（pause / compensate）

進入 `cancel_confirm` / `service_confirm` 子狀態前後：

```python
# 進入子狀態前
paused_at = time.monotonic()

# 呼叫 helper（內部有自己的獨立 wall-clock）
result = cancel_confirm(...) / service_confirm(...)

# 退出子狀態後：兩 deadline 都加上實際耗時（補回「凍結」時間）
pause_duration = time.monotonic() - paused_at
budget_deadline += pause_duration
cycle_deadline  += pause_duration
```

**Cancel confirm 結果處理：**
- YES → `_l4_exit_b`（speak `L4_B_CANCEL_THANKS` + clear cart + 退 L1）
- NO → speak `CANCEL_DECLINED_NOTICE` → **補償時間** → 回主迴圈

**Service confirm 結果處理：**
- "yes"（繼續） → **重置兩計時器**（fresh start，覆蓋補償；見 2.2 第 4 點）
- "scan" → speak `L4_A_PAY_SUCCESS` + `do_action(ACTION_L4_PAY)` → L5（鏈路 A）
- "no" → clear cart + 退 L1

**為何「客服 yes」用 reset 而非補償：** 客服繼續後，user 心智需要「fresh 36s 倒數」感受到「客服打完了，重新開始 QR 流程」；補償會讓 user 看到「客服只暫停了一下」失去重置感。對齊 v2 現行行為（line 130-136）。

---

## 3. 改檔範圍

### 3.1 `myProgram/sales/constants/timing.py`

| 動作 | 內容 |
|---|---|
| **改值** | `L4_TOTAL_BUDGET: 30 → 36` |
| **改名 + 語意** | `L4_PROMPT_INTERVAL: 12` → `L4_QR_REFRESH_INTERVAL: 12`（語意從「沒回應重提示間隔」改為「無條件循環刷新間隔」） |
| **註解更新** | 兩個常數的 docstring 反映新設計 + 引用本 spec |
| **`__all__`** | 跟著改名 |

**註解範例（新值）：**
```python
# L4 結帳場景全程 wall-clock 預算（2026-05-31 v3 雙計時器設計：30 → 36）
# 36 = L4_QR_REFRESH_INTERVAL × 3，總 budget 期間共 3 個 QR 刷新循環。
# 從進入 L4 entry prompt 播完起算；達 0 → forced exit。
# 客服繼續返回會 reset；cancel_confirm / 客服子狀態期間暫停 + 補償。
# 詳見 resources/specs/L4_v3_dual_timer_spec.md
L4_TOTAL_BUDGET: int = 36

# L4 QR 視覺刷新循環間隔（2026-05-31 v3 加；取代 L4_PROMPT_INTERVAL）
# 每循環開頭：重印結帳區塊 + 重 speak L4_REMIND_PROMPT（無條件，不論顧客是否回應）。
# 模擬「QR code 每 12s 重新生成」的 UX。子鏈路 ack 不影響此循環。
L4_QR_REFRESH_INTERVAL: int = 12
```

### 3.2 `myProgram/sales/states/l4.py`

| 改動 | 細節 |
|---|---|
| **Module docstring** | 改述 v3 設計（雙計時器 + 循環刷新 + 子狀態暫停補償） |
| **import** | `L4_PROMPT_INTERVAL` → `L4_QR_REFRESH_INTERVAL` |
| **`run_l4` 主迴圈** | 重寫為 2.2 規約版本（雙 deadline + 循環刷新邏輯） |
| **`_l4_dispatch_response`** | cancel_confirm / service 呼叫前後加 pause / 補償 block；不重置任何 deadline |
| **`_l4_service_mode`** | 「yes」回 `None` 給 caller（caller 負責 reset），保持簽名 |
| **`_l4_print_entry_detail`** | 不變（QR 刷新呼叫此函式） |
| **`_l4_exit_d_forced`** / `_l4_exit_b` | 不變 |
| **可選新 helper** | 若 pause / 補償 邏輯散在多處 → 抽 `_l4_pause_compensate(*deadlines, paused_at) -> tuple`；若只 cancel_confirm + service 兩處 → 內聯即可（sales-coder 自決，依 karpathy「3 行重複才抽 helper」原則） |

### 3.3 `tests/sales/test_states_l4.py`（或對應檔，sales-coder 確認檔名）

**需更新（既有測試）：**
- 「budget 30s」相關 assertion → 36s
- 「沒回應 12s remind」相關 → 「12s 無條件循環刷新」
- 「ack 不重置 budget」保留語意但 assert 新行為（兩計時器都不重置）

**需新增：**
| 測試 | 期望 |
|---|---|
| QR 循環刷新基本 | 12s 內無輸入 → `_l4_print_entry_detail` + `L4_REMIND_PROMPT` 都被呼叫 1 次（不是「沒回應」才觸發） |
| 多次循環刷新 | 24s 內無輸入 → 兩次刷新 |
| ack 不重置 cycle | 第 1 秒亂答 + 第 11 秒 silent → 第 12 秒仍觸發循環刷新（cycle deadline 沒被推後） |
| ack 不重置 budget | 整個 36s 內每 5s 亂答 → 第 36s 仍觸發 forced exit |
| cancel_confirm NO 補償 | mock cancel_confirm 耗 3s + NO → 補償後 budget / cycle deadline 都 +3s |
| service yes 重置 | mock service_confirm yes → 兩計時器 reset + 重 speak entry prompt（不是 remind prompt） |
| service no 立即退 | mock service_confirm no → clear cart + 退 L1（不受兩計時器影響） |
| budget 耗盡優先 | budget 剩 2s + cycle 剩 5s → 2s 後 forced exit（不等 cycle） |
| cycle 與 budget 同時到 | budget 36s + 第 3 循環尾 → 期望 forced exit（不再刷新） |

---

## 4. Out of scope（本輪明確不動）

- `_cancel_confirm.py` / `_service_confirm.py` 內部邏輯（這些 helper 本身正確，行為不變）
- L2 / L3 / qty_followup 使用同 helper 的行為（本設計只動 L4 主迴圈）
- TTS / action / OpenCV / wire-up 層（純 sales/ 業務邏輯改）
- 規格書 `L4.md` 原文（v3 與 v2 的差異全寫在本 spec doc，原文保留）
- BDD spec 階段（這是既有業務邏輯重設計，不新增 BDD scenario，沿用既有測試框架更新）
- 其他常數（`CANCEL_CONFIRM_TIMEOUT` / `L4_C_CONFIRM_TIMEOUT` / 其他 L4 prompt 字串）

---

## 5. 規範與參考

### 5.1 派發與準則
- **派發目標**：`sales-coder` subagent（規模屬「中大」改動，符合 [[dispatch-threshold-by-change-size]]）
- **預載 SKILL**（frontmatter，無需 prompt 重塞）：
  - `andrej-karpathy-skills:karpathy-guidelines` — surgical / verifiable / no over-engineering
  - `test-driven-development` — Red-Green-Refactor + Iron Law
- **強制規範**（SubagentStart hook 注入，無需 prompt 重塞）：
  - 廠商 SDK 禁改 / 繁中產出 / `git add` 明列檔名 / commit message Co-Authored-By
- **prompt 需自行塞**：
  - 本 spec doc 路徑（讓 sales-coder 完整讀）
  - 任務特化：哪些 commit 拆分、test 檔具體名、既有測試怎麼找

### 5.2 相關 memory
- [[l4-ack-wallclock-budget-design]] — v2 簡化背景（本輪 supersede；commit 後 update memory 註記 v3 取代）
- [[speak-and-wait-architecture]] — `speak_and_wait` callback 用法（進場 prompt 必用）
- [[countdown-print-design]] — 終端 countdown 打印（"timeout = N" / "wait = N" 語意）— **本 v3 設計下，read 用 `min(cycle, budget)` timeout，countdown 打印需保持原 `timeout = N` 語意**
- [[service-confirm-unified]] / [[cancel-confirm-cross-l]] — 子狀態 helper 規約（本輪不動 helper）
- [[sdd-workflow]] — 本輪採用的 SDD 流程

### 5.3 歷史 commit
- v2 起點：`5c9fb1e feat(service-confirm): L4_C_CONFIRM_TIMEOUT 12s -> 24s`（2026-05-31）
- v2 對齊：`46c0b52 refactor(qty-followup): align service entry to _service_confirm helper`
- latest main：`5710826 docs(CLAUDE): record 2026-05-30/31 session memory pointers`

---

## 6. 測試指令

```bash
python -m pytest tests/sales/ -v
```

**預期結果：** 全部 336 個現有 sales/ tests 仍綠 + 本輪新增 L4 雙計時器 tests 全綠。

**Sales-coder 須回報：**
- 修改前 / 後測試數量對比
- 新增測試數量明細（依 3.3 表）
- pytest 最終輸出尾端 5-10 行摘要

---

## 7. Commit 規範

**推薦拆分（sales-coder 自決，2 commit）：**

Commit 1（constants）：
```
refactor(L4 constants): rename L4_PROMPT_INTERVAL -> L4_QR_REFRESH_INTERVAL

- L4_TOTAL_BUDGET 30 -> 36 (= 12 × 3 cycles)
- Semantic change: 無條件循環刷新間隔（v3 雙計時器設計）
- See resources/specs/L4_v3_dual_timer_spec.md
```

Commit 2（states + tests）：
```
refactor(L4 main loop): dual-timer design (v3)

- Budget 36s + QR refresh 12s cycle, two independent wall-clocks
- Sub-state pause/compensate for cancel_confirm + service_confirm
- Sub-routine acks (好的 / 亂答 / cancel NO) no longer touch any timer
- QR refresh now unconditional per 12s (was: only on no-response)
- Service yes still resets both timers (fresh start)
- Spec: resources/specs/L4_v3_dual_timer_spec.md
```

或單 commit 包全部（sales-coder 自決，commit message 可參考 commit 2 + 補 constants 改動）。

**`git add` 範圍（明列）：**
```
git add myProgram/sales/constants/timing.py \
        myProgram/sales/states/l4.py \
        tests/sales/test_states_l4.py
```
（若改名 test 檔需新增 / 刪除舊 → 對應加進 `git add`）

主 agent 階段 3a（pineedtodo）/ 3b（projectStructure）會額外處理本 spec 檔的 add，與 sales-coder commit 拆開。

---

## 8. 流程鳥瞰

```
[已完成] 主對話 user 對齊（5 個 ambiguity） → 寫此 spec
   ↓
[此 spec 待 user 審查 approval]
   ↓
[approval 後] 主 agent commit 此 spec doc（worktree 內首 commit）
   ↓
[派 sales-coder] prompt 指向此 spec + 任務特化規則
   ↓
sales-coder 依 spec 改 constants / l4.py / tests + commit
   ↓
主 agent 審查（讀 worktree 內檔 + 跑 pytest）
   ↓
階段 3b projectStructure 更新（新 spec 檔加進結構樹 + 職責表）
   ↓
ff-merge + push + sync + cleanup
```
