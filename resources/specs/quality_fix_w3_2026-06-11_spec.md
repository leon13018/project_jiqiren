# quality_fix_w3 — 代碼質檢修復 Wave 3（中價值 #5-#9）spec

## 1. 背景與動機

2026-06-11 質檢 review 的中價值精簡項，5 項各自獨立、低風險：

- **#5**：`l1.py` `run_l1` 兩處 hawk 呼叫後的結果映射是恆等式（`_run_l1_hawk` 只回 `"L2" | None`，`if result == "L2": return "L2"; return None` ≡ `return result`），且現寫法會默默吞掉未來的非法回傳值（遮 bug）。
- **#6**：`l4.py` `_l4_dispatch_response` 客服分支的 `paused_at` / `pause_duration` 算完從未使用（客服路徑不是 exit 就是 reset——reset 覆蓋補償，spec §2.4），死碼。
- **#7**：`l2_l3_dialog.py` `_dialog_unclear_final_confirmation` 內 `DialogSession(io, cart).exit_a()` 拋棄式建構 ×4。
- **#8**：`tts.py` `speak_and_wait` 重複 `speak` 的 print+say 兩行，print 字面雙來源。
- **#9**：`MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)` 剩餘容量運算式散落 5 處（`_l2_l3_qty_followup.py` ×2、`_invalid_qty_reask.py` ×3），語意應歸 cart 模組。

W1（`60a826b`）/ W2（`ccc6f44`）已 merge；本 wave 基於其上。

## 2. 設計核心 + 行為規約

**鐵則：行為零改變**——`tests/sales/` 既有 502 測試零修改全綠；#9 新增 1 個 helper 測試 → 預期總數 **503 passed**。

### #5：`run_l1` 兩處改直接 return

兩處（`enter_hawk_immediately` 分支、主迴圈 `key == "1"` 分支）的
`result = _run_l1_hawk(...)` + `if result == "L2": return "L2"` + `return None`
→ `return _run_l1_hawk(...)`。等價：`_run_l1_hawk` 回傳域 = `{"L2", None}`（line 253 / 263 兩個 return 點），恆等映射。kwargs 原樣保留。

### #6：刪 l4 客服分支死碼

`_l4_dispatch_response` 客服分支刪 `paused_at = time.monotonic()` 與 `pause_duration = time.monotonic() - paused_at` 兩行（變數零讀取）。docstring 優先序 4 的「（量測耗時）」字樣同步改為「（reset 覆蓋補償，不量測）」。`time` import 保留（run_l4 / 拒絕分支仍用）。

### #7：`_dialog_unclear_final_confirmation` session 建一次

函式開頭建 `session = DialogSession(io, cart)`，4 處 `DialogSession(io, cart).exit_a()` 改 `session.exit_a()`。等價：`__init__` 純存引用、`exit_a` 只用 io+cart，建構次數無可觀察差異。函式簽名不變（測試經 `run_dialog` 驅動）。

### #8：`speak_and_wait` 委派 `speak`

```python
print(f"[語音] {text}")
_worker.say(text)
return _worker.wait_idle(max_wait=max_wait)
```
→
```python
speak(text)
return _worker.wait_idle(max_wait=max_wait)
```
等價：`speak(text)` 本體即 print+say 同兩行。簽名與 docstring 不動（`test_tts_worker.py:305` 驗簽名 default 30.0，不受影響；無測試選擇性 mock `tts.speak`——已 grep 驗證）。

### #9：新增 `cart.remaining_capacity` + 替換 5 處

`cart.py` 新增（走 TDD——先寫 failing test）：

```python
def remaining_capacity(cart: Cart, product: str) -> int:
    """回傳該商品距單筆上限（MAX_QTY_PER_ITEM）的剩餘可加數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱

    Returns:
        MAX_QTY_PER_ITEM - 既有數量（不存在時既有量為 0，即回上限值）
    """
    return MAX_QTY_PER_ITEM - get_quantity(cart, product)
```

替換點（行為等價，逐處原式即此定義展開）：
1. `_l2_l3_qty_followup.py` Pass 1：`existing = ...` + `remaining = MAX_QTY_PER_ITEM - existing` 兩行 → `remaining = cart_module.remaining_capacity(cart, product)`（`existing` 無其他讀取）。
2. `_l2_l3_qty_followup.py` `_qty_follow_up_sub_loop`：同上兩行 → 一行。
3. `_invalid_qty_reask.py` `_format_invalid_qty_prompt` 單商品分支。
4. `_invalid_qty_reask.py` `_format_invalid_qty_prompt` 多商品 genexp 內。
5. `_invalid_qty_reask.py` `_classify_into_pending`。

import 整理（orphan 原則）：`_invalid_qty_reask.py` 替換後 `MAX_QTY_PER_ITEM` 零使用 → 自 import 清單移除；`_l2_l3_qty_followup.py` 仍用於 `AT_CAP_NOTICE_TEMPLATE.format(max_qty=...)` ×2 → 保留。

新測試 `tests/sales/test_cart.py` 加 1 個 function（3 assert：空 cart 回 50 / 加 3 後回 47 / 達上限回 0）。

## 3. 改檔範圍（高層）

| 檔 | 項 | 行數估 |
|---|---|---|
| `myProgram/sales/states/l1.py` | #5 | -8 |
| `myProgram/sales/states/l4.py` | #6 | -2±doc |
| `myProgram/sales/states/l2_l3_dialog.py` | #7 | ±5 |
| `myProgram/tts.py` | #8 | -2 |
| `myProgram/sales/cart.py` + `myProgram/sales/states/_l2_l3_qty_followup.py` + `myProgram/sales/states/_invalid_qty_reask.py` + `tests/sales/test_cart.py` | #9 | +20/-8 |

## 4. Out of scope

W4（#10-#13）各項；review 判定刻意設計 7 項；任何文案 / timeout / 行為變更；`_dialog_unclear_final_confirmation` 簽名（保持 io+cart，不改收 session）。

## 5. 規範與參考

派 **sales-coder**（#8 涉 tts.py worker）；plan 已給各項新舊碼。背景：review 報告 #5-#9 段。

## 6. 測試指令 + 預期結果

- #9 的 RED 步驟：`python -m pytest tests/sales/test_cart.py -q` 先 FAIL（`remaining_capacity` 不存在）。
- 每 commit 後：`python -m pytest tests/sales/` → #5-#8 各 commit 後 **502 passed**；#9 commit 後 **503 passed**。

## 7. Commit 規範（5 個獨立 commit，依序）

1. `refactor(sales): return _run_l1_hawk result directly in run_l1`（add：`myProgram/sales/states/l1.py`）
2. `refactor(sales): drop dead pause measurement in L4 service branch`（add：`myProgram/sales/states/l4.py`）
3. `refactor(sales): reuse single DialogSession in unclear final confirmation`（add：`myProgram/sales/states/l2_l3_dialog.py`）
4. `refactor(tts): delegate speak_and_wait print+say to speak`（add：`myProgram/tts.py`）
5. `feat(sales): add cart.remaining_capacity and replace 5 inline computations`（add：`myProgram/sales/cart.py myProgram/sales/states/_l2_l3_qty_followup.py myProgram/sales/states/_invalid_qty_reask.py tests/sales/test_cart.py`）

body 繁中 + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；禁 `-A`/`.`。

## 8. 流程鳥瞰

```
worktree quality-fix-w3 → spec+plan commit → sales-coder（5 commits，#9 走 TDD RED→GREEN）
→ 主 agent Iron Law（pytest 503 + branch + diff 對照）→ spec-reviewer → code-quality-reviewer
→ ExitWorktree(keep) → ff-merge → push → cleanup
```
