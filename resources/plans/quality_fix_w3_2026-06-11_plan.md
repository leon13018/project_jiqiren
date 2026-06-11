# quality_fix_w3 實作計畫（plan — HOW）

> **執行者**：sales-coder。對應 spec：`resources/specs/quality_fix_w3_2026-06-11_spec.md`。
> 規約：#5-#8 純重構（綠 → 改 → 綠 → commit）；#9 TDD（RED → GREEN → commit）。每 task 一 commit；pytest 預期值不符即停下回報。

**Goal**：5 項中價值精簡，#5-#8 行為零改變、#9 新增 `cart.remaining_capacity` helper 並替換 5 處 inline 運算。

---

## Task 0：基線驗證

- [ ] **Step 0.1**：`python -m pytest tests/sales/` → 預期 `502 passed`。

---

## Task 1（#5）：`run_l1` 兩處改直接 return

**Files**：Modify `myProgram/sales/states/l1.py`

- [ ] **Step 1.1：Read worktree 內 `l1.py`**

- [ ] **Step 1.2：`enter_hawk_immediately` 分支（約 97-112 行）**

舊：

```python
    if enter_hawk_immediately:
        # subroutine_a 後續路徑：跳過主選單，直接進 hawk（連續叫賣不中斷）
        result = _run_l1_hawk(
            print_terminal=print_terminal,
            read_terminal_key=read_terminal_key,
            opencv_dwell_seconds=opencv_dwell_seconds,
            opencv_enable=opencv_enable,
            speak=speak,
            do_action=do_action,
            exit_program=exit_program,
            schedule=schedule,
            show_hawk_help=show_hawk_help,
        )
        if result == "L2":
            return "L2"
        return None
```

新（kwargs 一字不動；回傳域 = {"L2", None} 直接透傳）：

```python
    if enter_hawk_immediately:
        # subroutine_a 後續路徑：跳過主選單，直接進 hawk（連續叫賣不中斷）
        # _run_l1_hawk 回傳域 = {"L2", None}，直接透傳（原恆等映射移除）
        return _run_l1_hawk(
            print_terminal=print_terminal,
            read_terminal_key=read_terminal_key,
            opencv_dwell_seconds=opencv_dwell_seconds,
            opencv_enable=opencv_enable,
            speak=speak,
            do_action=do_action,
            exit_program=exit_program,
            schedule=schedule,
            show_hawk_help=show_hawk_help,
        )
```

- [ ] **Step 1.3：主迴圈 `elif key == "1":` 分支（約 157-170 行）**

舊：

```python
        elif key == "1":
            result = _run_l1_hawk(
                print_terminal=print_terminal,
                read_terminal_key=read_terminal_key,
                opencv_dwell_seconds=opencv_dwell_seconds,
                opencv_enable=opencv_enable,
                speak=speak,
                do_action=do_action,
                exit_program=exit_program,
                schedule=schedule,
                show_hawk_help=show_hawk_help,
            )
            if result == "L2":
                return "L2"
            return None
```

新：

```python
        elif key == "1":
            # _run_l1_hawk 回傳域 = {"L2", None}，直接透傳（原恆等映射移除）
            return _run_l1_hawk(
                print_terminal=print_terminal,
                read_terminal_key=read_terminal_key,
                opencv_dwell_seconds=opencv_dwell_seconds,
                opencv_enable=opencv_enable,
                speak=speak,
                do_action=do_action,
                exit_program=exit_program,
                schedule=schedule,
                show_hawk_help=show_hawk_help,
            )
```

- [ ] **Step 1.4**：`python -m pytest tests/sales/` → `502 passed`
- [ ] **Step 1.5**：

```bash
git add myProgram/sales/states/l1.py
git commit -m "refactor(sales): return _run_l1_hawk result directly in run_l1"
git branch --contains HEAD
```

---

## Task 2（#6）：刪 l4 客服分支死碼

**Files**：Modify `myProgram/sales/states/l4.py`

- [ ] **Step 2.1：Read worktree 內 `l4.py`**

- [ ] **Step 2.2：`_l4_dispatch_response` 客服分支（約 291-301 行）**

舊：

```python
    # 優先序 4：客服 → service_confirm（24s 獨立 budget）
    if intent == "客服":
        paused_at = time.monotonic()
        result = _l4_service_mode(io=io, cart=cart)
        pause_duration = time.monotonic() - paused_at
        if isinstance(result, tuple):
            # service_mode 已決定退出（scan → L5 / no → L1），無需補償
            return (result, 0.0)
        # result is None → 客服 yes「繼續」→ caller 重置兩計時器（fresh start）
        # 不用 pause_duration（reset 覆蓋補償，spec §2.4 對齊 v2 行為）
        return ("reset", 0.0)
```

新：

```python
    # 優先序 4：客服 → service_confirm（24s 獨立 budget；不量測耗時——
    # 兩出口不是退出就是 reset，reset 覆蓋補償（spec §2.4），補償永不適用）
    if intent == "客服":
        result = _l4_service_mode(io=io, cart=cart)
        if isinstance(result, tuple):
            # service_mode 已決定退出（scan → L5 / no → L1），無需補償
            return (result, 0.0)
        # result is None → 客服 yes「繼續」→ caller 重置兩計時器（fresh start）
        return ("reset", 0.0)
```

- [ ] **Step 2.3：docstring 優先序 4 行（約 248-251 行）**

舊：

```python
        4. 客服意圖 → service_confirm（量測耗時）
            yes → "reset"（主迴圈重置兩計時器，不用 pause_duration）
            no → 清 cart 退 L1
            scan → 進 L5（鏈路 A）
```

新：

```python
        4. 客服意圖 → service_confirm（不量測耗時——reset 覆蓋補償）
            yes → "reset"（主迴圈重置兩計時器）
            no → 清 cart 退 L1
            scan → 進 L5（鏈路 A）
```

- [ ] **Step 2.4**：`python -m pytest tests/sales/` → `502 passed`
- [ ] **Step 2.5**：

```bash
git add myProgram/sales/states/l4.py
git commit -m "refactor(sales): drop dead pause measurement in L4 service branch"
git branch --contains HEAD
```

---

## Task 3（#7）：unclear final confirmation 的 session 建一次

**Files**：Modify `myProgram/sales/states/l2_l3_dialog.py`（`_dialog_unclear_final_confirmation`）

- [ ] **Step 3.1：Read worktree 內 `l2_l3_dialog.py` 目標函式段**

- [ ] **Step 3.2：函式體開頭加一行 + 4 處替換**

在 `io.speak(L3_UNCLEAR_FINAL_PROMPT)` 之前插入：

```python
    session = DialogSession(io, cart)  # exit_a 共用（原 4 處拋棄式建構收一）
```

4 處 `return DialogSession(io, cart).exit_a()` 全改 `return session.exit_a()`（timeout / 終端 "1" / cancel_confirm YES / unclear 上限四個出口；前後註解不動）。

- [ ] **Step 3.3**：`python -m pytest tests/sales/` → `502 passed`
- [ ] **Step 3.4**：

```bash
git add myProgram/sales/states/l2_l3_dialog.py
git commit -m "refactor(sales): reuse single DialogSession in unclear final confirmation"
git branch --contains HEAD
```

---

## Task 4（#8）：`speak_and_wait` 委派 `speak`

**Files**：Modify `myProgram/tts.py`

- [ ] **Step 4.1：Read worktree 內 `tts.py` 模組級函式段**

- [ ] **Step 4.2：`speak_and_wait` 函式體（docstring 不動）**

舊：

```python
    print(f"[語音] {text}")
    _worker.say(text)
    return _worker.wait_idle(max_wait=max_wait)
```

新（`speak(text)` 本體即同兩行，print 字面單一來源）：

```python
    speak(text)
    return _worker.wait_idle(max_wait=max_wait)
```

- [ ] **Step 4.3**：`python -m pytest tests/sales/` → `502 passed`
- [ ] **Step 4.4**：

```bash
git add myProgram/tts.py
git commit -m "refactor(tts): delegate speak_and_wait print+say to speak"
git branch --contains HEAD
```

---

## Task 5（#9）：`cart.remaining_capacity` + 替換 5 處（TDD）

**Files**：Modify `myProgram/sales/cart.py`、`myProgram/sales/states/_l2_l3_qty_followup.py`、`myProgram/sales/states/_invalid_qty_reask.py`；Test `tests/sales/test_cart.py`

- [ ] **Step 5.1：Read 四檔**（worktree 路徑）

- [ ] **Step 5.2（RED）：`tests/sales/test_cart.py` 加測試**（import 風格對齊該檔既有寫法；若 `MAX_QTY_PER_ITEM` 未 import 則補）

```python
def test_remaining_capacity_tracks_max_qty_per_item():
    """remaining_capacity = MAX_QTY_PER_ITEM - 既有量；空 cart 回上限、達上限回 0。"""
    cart = new_cart()
    assert remaining_capacity(cart, "冰紅茶") == MAX_QTY_PER_ITEM
    add_item(cart, "冰紅茶", 3)
    assert remaining_capacity(cart, "冰紅茶") == MAX_QTY_PER_ITEM - 3
    add_item(cart, "冰紅茶", MAX_QTY_PER_ITEM - 3)
    assert remaining_capacity(cart, "冰紅茶") == 0
```

（函式取用形式——直接 import 或 `cart_module.` 前綴——以該測試檔既有慣例為準，上方以直接 import 形式示意。）

- [ ] **Step 5.3（RED 驗證）**：`python -m pytest tests/sales/test_cart.py -q` → 預期 **FAIL**（`remaining_capacity` 不存在：ImportError 或 AttributeError）

- [ ] **Step 5.4（GREEN）：`cart.py` 在 `get_quantity` 之後加**

```python
def remaining_capacity(cart: Cart, product: str) -> int:
    """回傳該商品距單筆上限（MAX_QTY_PER_ITEM）的剩餘可加數量。

    Args:
        cart: 購物車 dict
        product: 商品名稱

    Returns:
        MAX_QTY_PER_ITEM - 既有數量（商品不存在時既有量為 0，即回上限值）
    """
    return MAX_QTY_PER_ITEM - get_quantity(cart, product)
```

- [ ] **Step 5.5**：`python -m pytest tests/sales/test_cart.py -q` → PASS

- [ ] **Step 5.6：替換 5 處 inline 運算**

`_l2_l3_qty_followup.py` 兩處（Pass 1 與 `_qty_follow_up_sub_loop`；前後註解不動；`existing` 變數無其他讀取一併刪）：

舊（兩處同型，縮排各依區塊）：

```python
existing = cart_module.get_quantity(cart, product)
remaining = MAX_QTY_PER_ITEM - existing
```

新：

```python
remaining = cart_module.remaining_capacity(cart, product)
```

`_invalid_qty_reask.py` 三處：

```python
# _format_invalid_qty_prompt 單商品分支
remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)
# → remaining = cart_module.remaining_capacity(cart, p)

# _format_invalid_qty_prompt 多商品 genexp 內
f"{MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)} {PRODUCTS[p]['單位']}"
# → f"{cart_module.remaining_capacity(cart, p)} {PRODUCTS[p]['單位']}"

# _classify_into_pending
remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
# → remaining = cart_module.remaining_capacity(cart, product)
```

- [ ] **Step 5.7：import 整理（orphan 原則）**

`_invalid_qty_reask.py`：替換後 `MAX_QTY_PER_ITEM` 符號零使用 → 自 `from myProgram.sales.constants import (...)` 清單移除（用 Grep 確認該檔內零殘留後再刪）。
`_l2_l3_qty_followup.py`：仍用於 `AT_CAP_NOTICE_TEMPLATE.format(max_qty=MAX_QTY_PER_ITEM, ...)` ×2 → **保留**。

- [ ] **Step 5.8**：`python -m pytest tests/sales/` → **`503 passed`**（+1 = 新 helper 測試）

- [ ] **Step 5.9**：

```bash
git add myProgram/sales/cart.py myProgram/sales/states/_l2_l3_qty_followup.py myProgram/sales/states/_invalid_qty_reask.py tests/sales/test_cart.py
git commit -m "feat(sales): add cart.remaining_capacity and replace 5 inline computations"
git branch --contains HEAD
```

---

## 完成回報

4-status + 5 個 commit SHA + 各階段 pytest 末行（含 Task 5 RED 證據）+ TaskList 摘要。
