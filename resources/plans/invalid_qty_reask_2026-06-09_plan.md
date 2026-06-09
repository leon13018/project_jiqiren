# 無效數量重問鏈 invalid_qty_reask — Implementation Plan

> **For agentic workers:** sales-coder 依 SDD 執行，每 step 一原子動作、TDD。Spec（WHAT）：`resources/specs/invalid_qty_reask_2026-06-09_spec.md`。

**Goal:** 把 over_limit_reask 一般化為 invalid_qty_reask，讓「數量為 0」比照「超上限」進重問鏈（同系統值、不同提示詞），修掉 qty=0 三路徑不一致 + 假性「已加入購物車」。

**Architecture:** (1) 全套 rename over_limit→invalid_qty；(2) pending `list`→`dict{product:reason}`、formatter 依 reason 分組、`_apply_quantities` 重分類；(3) 偵測點 qty==0 funnel 進鏈。沿用 12s/2reset/二選一 6s/客服暫停/control 往上傳。

**Tech Stack:** Python 3.11、pytest、callback 注入、`time.monotonic` wall-clock。

---

## Task 1：全套機械改名（over_limit → invalid_qty）

> 純改名，值 / 行為不變 → 既有 407 測試改名引用後應全綠。**逐檔 Edit，禁用 Write 整檔覆寫**（保 BOM 無關，但避免漏行）。

**Files:** timing.py / shared.py / keywords.py / `_over_limit_reask.py`(→rename) / `_l2_l3_qty_followup.py` / `l2_l3_dialog.py` / `test_over_limit_reask.py`(→rename) / `test_states.py` / `test_constants.py`

- [ ] **Step 1：rename 常數（timing / shared / keywords）**

依 spec §2.2 對照表，把三個 constants 檔內的識別字與 `__all__` 全部改名：
- timing.py：`OVER_LIMIT_REASK_TIMEOUT`→`INVALID_QTY_REASK_TIMEOUT`、`OVER_LIMIT_MAX_RESETS`→`INVALID_QTY_MAX_RESETS`、`OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT`→`INVALID_QTY_CANCEL_CONFIRM_TIMEOUT`（值不變）。
- shared.py：`OVER_LIMIT_REASK_SINGLE_TEMPLATE`→`INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE`、`OVER_LIMIT_REASK_MULTI_TEMPLATE`→`INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE`、`OVER_LIMIT_UNCLEAR_PREFIX`→`INVALID_QTY_UNCLEAR_PREFIX`、`OVER_LIMIT_CANCEL_CONFIRM_PROMPT`→`INVALID_QTY_CANCEL_CONFIRM_PROMPT`、`OVER_LIMIT_TIMEOUT_REENTER_PREFIX`→`INVALID_QTY_TIMEOUT_REENTER_PREFIX`、`OVER_LIMIT_CANCEL_REENTER_PREFIX`→`INVALID_QTY_CANCEL_REENTER_PREFIX`（**內容此 step 不變**，中性化留 Task 2）。
- keywords.py：`KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER`→`KEYWORDS_INVALID_QTY_CANCEL_TRIGGER`、`KEYWORDS_OVER_LIMIT_CONTINUE`→`KEYWORDS_INVALID_QTY_CONTINUE`、`KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT`→`KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT`、`KEYWORDS_OVER_LIMIT_EXIT`→`KEYWORDS_INVALID_QTY_EXIT`、`KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT`→`KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT`。

- [ ] **Step 2：rename helper 檔 + 函式**

`git mv myProgram/sales/states/_over_limit_reask.py myProgram/sales/states/_invalid_qty_reask.py`，檔內：
- `over_limit_reask`→`invalid_qty_reask`、`over_limit_cancel_confirm`→`invalid_qty_cancel_confirm`、`_format_over_limit_prompt`→`_format_invalid_qty_prompt`。
- import 區所有 `OVER_LIMIT_*`→對應 `INVALID_QTY_*`（含 OVERLIMIT template）。
- docstring/註解內「超量重問」可保留語意，但符號名一律新名。

- [ ] **Step 3：rename callers**

- `_l2_l3_qty_followup.py`：`from ...states._over_limit_reask import over_limit_reask` → `from ...states._invalid_qty_reask import invalid_qty_reask`；內文 `over_limit_reask(...)` → `invalid_qty_reask(...)`（兩處：resolve Pass 1.5、followup funnel）。
- `l2_l3_dialog.py`：import 的 `OVER_LIMIT_TIMEOUT_REENTER_PREFIX` / `OVER_LIMIT_CANCEL_REENTER_PREFIX` → `INVALID_QTY_*`；control 處理區的常數引用同步改名。

- [ ] **Step 4：rename 測試**

`git mv tests/sales/test_over_limit_reask.py tests/sales/test_invalid_qty_reask.py`，檔內 import / 呼叫改新名。`test_states.py` / `test_constants.py` 內所有 `over_limit` 識別字 / 常數引用改新名（用 Grep 找 `over_limit|OVER_LIMIT` 逐一改；測試函式名可保留語意但引用符號改新名）。

- [ ] **Step 5：跑見全綠（純改名不改行為）**

Run: `python -m pytest tests/sales/ -q`
Expected: `407 passed`（與改名前一致；任何 fail = 漏改某引用，grep `over_limit|OVER_LIMIT` 補）。
驗證無殘留：`grep -rn "over_limit\|OVER_LIMIT" myProgram/ tests/` 應只剩 docstring/註解語意字（無符號引用）。

- [ ] **Step 6：Commit**

```bash
git add myProgram/sales/constants/timing.py myProgram/sales/constants/shared.py myProgram/sales/constants/keywords.py myProgram/sales/states/_invalid_qty_reask.py myProgram/sales/states/_l2_l3_qty_followup.py myProgram/sales/states/l2_l3_dialog.py tests/sales/test_invalid_qty_reask.py tests/sales/test_states.py tests/sales/test_constants.py
git commit -m "refactor(sales): rename over_limit_reask to invalid_qty_reask"
```

---

## Task 2：一般化 pending→dict{reason} + formatter 分組 + zero 文案 + 中性化

> over-limit 既有行為**逐字等價保留**（初始皆 reason="over_limit"）；本 task 加 zero 基礎建設但**尚未接偵測點**（Task 3 才接），故新增的 zero 單元測試直接測 helper。

**Files:** `shared.py` / `_invalid_qty_reask.py` / `_l2_l3_qty_followup.py` / `test_invalid_qty_reask.py` / `test_constants.py`

- [ ] **Step 1：加 zero template + 中性化既有兩文案（shared.py）**

`__all__` 加 `"INVALID_QTY_ZERO_TEMPLATE"`；新增：
```python
# zero 數量重問（2026-06-09；invalid_qty 一般化）。{items}「冰紅茶0瓶」/「冰紅茶0瓶、刮刮樂0張」；{products}「冰紅茶」/「冰紅茶和刮刮樂」
INVALID_QTY_ZERO_TEMPLATE: str = "不好意思，系統不接受{items}這種數量，請重新說您想要的{products}的數量。"
```
並中性化（一般化後也涵蓋 zero，「超量」字眼改中性）：
```python
INVALID_QTY_CANCEL_CONFIRM_PROMPT: str = "請問您是想取消這些商品然後繼續交易，還是想直接退出交易？"
INVALID_QTY_CANCEL_REENTER_PREFIX: str = "好的已為您取消這些商品，"
```

- [ ] **Step 2：寫 failing tests（formatter 分組 + dict pending）**

加到 `tests/sales/test_invalid_qty_reask.py`（import `_format_invalid_qty_prompt`, `invalid_qty_reask`）：
```python
def test_format_prompt_zero_single() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "zero"}, cart)
    assert "不接受" in s and "冰紅茶0瓶" in s and "請重新說" in s

def test_format_prompt_overlimit_single_unchanged() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "over_limit"}, cart)
    assert "最多只能選購 50 瓶" in s

def test_format_prompt_mixed_reasons_concatenated() -> None:
    from myProgram.sales.states._invalid_qty_reask import _format_invalid_qty_prompt
    cart = cart_module.new_cart()
    s = _format_invalid_qty_prompt({"冰紅茶": "zero", "刮刮樂": "over_limit"}, cart)
    assert "冰紅茶0瓶" in s and "不接受" in s          # zero 句
    assert "刮刮樂" in s and "最多只能選購" in s         # over 句

def test_reask_dict_overlimit_resolved_still_works() -> None:
    # over-limit 行為等價回歸：dict pending 單商品 over_limit → 重答 5 → resolved
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "over_limit"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["5"]).read)
    assert r == "resolved" and cart_module.get_quantity(cart, "冰紅茶") == 5

def test_reask_zero_then_valid_resolved() -> None:
    # zero pending → 顧客重答合法 7 → resolved（reason 機制驗證）
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "zero"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["7"]).read)
    assert r == "resolved" and cart_module.get_quantity(cart, "冰紅茶") == 7

def test_reask_zero_answer_again_stays_pending_reenter() -> None:
    # zero pending → 顧客又答 0（reset）→ 再 silent → reenter_timeout，未加入
    cart = cart_module.new_cart()
    r = invalid_qty_reask({"冰紅茶": "zero"}, cart, speak=lambda t: None,
                          print_terminal=lambda t: None, read_customer_input=FakeInput(["0"]).read)
    assert r == "reenter_timeout" and cart_module.is_empty(cart)
```

- [ ] **Step 3：跑見 FAIL**

Run: `python -m pytest tests/sales/test_invalid_qty_reask.py -k "format_prompt or dict_overlimit or zero" -v`
Expected: FAIL（formatter 還是舊單一/多版本、不認 dict reason；`INVALID_QTY_ZERO_TEMPLATE` 未被使用）。

- [ ] **Step 4：改 `_invalid_qty_reask.py` 一般化**

1. import 加 `INVALID_QTY_ZERO_TEMPLATE`。
2. `_format_invalid_qty_prompt(pending, cart)` 改為 dict + 依 reason 分組（完整 code 見 spec §2.4）。
3. `_apply_quantities(response, pending, cart)` 改為 dict + `_classify_into_pending`（完整 code 見 spec §2.6）。
4. `invalid_qty_reask(pending, ...)`：型別 `pending: dict`；`if not pending: return "resolved"`（dict 空為 falsy，沿用）；其餘 loop 不變（case (3) `_apply_quantities` 後 `if not pending: resolved`、否則 reset/reprompt）。
5. `invalid_qty_cancel_confirm` 不變（只是 prompt 常數已中性化）。

- [ ] **Step 5：改 callers 構造 dict（行為等價）**

`_l2_l3_qty_followup.py`：
- Pass 1：`over_pending: list` → `invalid_pending: dict = {}`；超量分支 `invalid_pending[product] = "over_limit"`（**此 step 還沒加 qty==0 分支**，Task 3 才加）；`if invalid_pending: n = len(invalid_pending); control = invalid_qty_reask(invalid_pending, ...)`。
- funnel（followup `qty > remaining`）：`invalid_qty_reask({product: "over_limit"}, ...)`。

- [ ] **Step 6：跑見 PASS（新 formatter/zero 測試 + 既有全綠）**

Run: `python -m pytest tests/sales/ -q`
Expected: `N passed`（≥ 407 + 新增 6，0 failed）。over-limit 既有整合測試必須仍綠（行為等價）。

- [ ] **Step 7：Commit**

```bash
git add myProgram/sales/constants/shared.py myProgram/sales/states/_invalid_qty_reask.py myProgram/sales/states/_l2_l3_qty_followup.py tests/sales/test_invalid_qty_reask.py
git commit -m "refactor(sales): generalize reask pending to per-product reason"
```

---

## Task 3：偵測 qty==0 接入兩路徑（情境1/2/3 + 假性加入回歸）

**Files:** `myProgram/sales/product_parser.py` / `_l2_l3_qty_followup.py` / `test_product_parser.py` / `test_states.py` / `test_invalid_qty_reask.py`

> **前置（spec §2.7 前置修正）**：`parse_products` 目前對「紅茶0」回 `(冰紅茶, None)`（`_parse_quantity_in_window` 的 `n > 0` 守門吃掉 0），Pass 1 `if qty == 0` 不可達。本 task 先修 parser 透出明確 0，再接偵測點。

- [ ] **Step 0a：寫 parser failing test（明確 0 應回 0）**

加到 `tests/sales/test_product_parser.py`：
```python
def test_parse_products_explicit_zero_surfaces_zero() -> None:
    """明確的 0 應回 qty=0（非 None），與 nlu.parse_quantity B16 一致。"""
    assert product_parser.parse_products("紅茶0") == [("冰紅茶", 0)]
    assert product_parser.parse_products("紅茶0杯") == [("冰紅茶", 0)]
    assert product_parser.parse_products("紅茶 刮刮樂0") == [("冰紅茶", None), ("刮刮樂", 0)]
```

- [ ] **Step 0b：跑見 FAIL**

Run: `python -m pytest "tests/sales/test_product_parser.py::test_parse_products_explicit_zero_surfaces_zero" -v`
Expected: FAIL（現回 `(冰紅茶, None)`）。

- [ ] **Step 0c：修 `_parse_quantity_in_window`（product_parser.py）**

把 arabic 段改為（完整見 spec §2.7 前置修正）：arabic_matches 非空但全為 0 → `return 0`（不再 fall-through 成 None）。其餘（複合中文 / 單字中文 / None）不變。

- [ ] **Step 0d：跑見 PASS（parser test + 既有 parser 測試全綠）**

Run: `python -m pytest tests/sales/test_product_parser.py -v`
Expected: 全 PASS（既有無 X0→None 斷言，不回歸）。

- [ ] **Step 1：寫 failing tests（情境1/2/3 + 假性加入回歸）**

加到 `tests/sales/test_states.py`：
```python
def test_zero_qty_scenario1_direct_single() -> None:
    """情境1：紅茶0杯 → 進重問鏈（不假性加入）→ 重答 5 → 加 5。"""
    speaks: list = []; cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶0", "5", None, None, "對"])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None)
    assert cart_module.get_quantity(cart, "冰紅茶") == 5
    assert any("不接受" in s and "冰紅茶0瓶" in s for s in speaks)

def test_zero_qty_no_false_added_notice() -> None:
    """回歸：紅茶0 後立即沉默退出 → 不該播『已加入購物車』、cart 空。"""
    speaks: list = []; cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶0", None, None, None, None])
    states.run_dialog(speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None)
    assert cart_module.is_empty(cart)
    assert not any("已加入購物車" in s for s in speaks)

def test_zero_qty_scenario2_followup() -> None:
    """情境2：紅茶（缺量）→ 追問 → 0瓶 → 進重問鏈 → 5 → 加 5。"""
    speaks: list = []; cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶", "0瓶", "5", None, None, "對"])
    states.run_dialog(speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None)
    assert cart_module.get_quantity(cart, "冰紅茶") == 5
    assert any("不接受" in s for s in speaks)

def test_zero_qty_scenario3_zero_first_then_missing() -> None:
    """情境3：紅茶 刮刮樂0 → 先重問刮刮樂(0) → 解決 → 再追問紅茶數量。"""
    speaks: list = []; cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶 刮刮樂0", "刮刮樂5", "3", None, None, "對"])
    states.run_dialog(speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None)
    assert cart_module.get_quantity(cart, "刮刮樂") == 5
    assert cart_module.get_quantity(cart, "冰紅茶") == 3
```
加到 `tests/sales/test_invalid_qty_reask.py`（funnel 單元，直接測 resolve）：
```python
def test_resolve_mixed_zero_and_overlimit_one_loop() -> None:
    """直接給『紅茶0刮刮樂9999』→ 合併進同一鏈，混合 reason → 重答全部 → 全加入。"""
    from myProgram.sales.states._l2_l3_qty_followup import resolve_and_add_products
    cart = cart_module.new_cart(); speaks = []
    added, _notices, control = resolve_and_add_products(
        [("冰紅茶", 0), ("刮刮樂", 9999)], cart, speak=speaks.append,
        print_terminal=lambda t: None, read_customer_input=FakeInput(["紅茶4刮刮樂3"]).read,
        classify_intent_mode="l2")
    assert control is None and added is True
    assert cart_module.get_quantity(cart, "冰紅茶") == 4
    assert cart_module.get_quantity(cart, "刮刮樂") == 3
```

- [ ] **Step 2：跑見 FAIL**

Run: `python -m pytest "tests/sales/test_states.py::test_zero_qty_scenario1_direct_single" "tests/sales/test_states.py::test_zero_qty_no_false_added_notice" -v`
Expected: FAIL（現 qty=0 走 add_item silent skip + 假性 added → 播「已加入」、cart 空但被當加入）。

- [ ] **Step 3：接入偵測點（`_l2_l3_qty_followup.py`）**

- Pass 1：在 `if qty > remaining:` **之前**插入 `if qty == 0: invalid_pending[product] = "zero"; continue`（完整見 spec §2.7）。
- followup funnel：把 `if qty > remaining:` 改為 `if qty == 0 or qty > remaining:`，`reason = "zero" if qty == 0 else "over_limit"`，`invalid_qty_reask({product: reason}, ...)`（完整見 spec §2.7）。

- [ ] **Step 4：跑見 PASS**

Run: `python -m pytest tests/sales/ -q`
Expected: `N passed`（含新 5 測試）、0 failed。

- [ ] **Step 5：Commit**

```bash
git add myProgram/sales/product_parser.py myProgram/sales/states/_l2_l3_qty_followup.py tests/sales/test_product_parser.py tests/sales/test_states.py tests/sales/test_invalid_qty_reask.py
git commit -m "feat(sales): re-ask on zero quantity across L2/L3 paths"
```

---

## Task 4：docs（code_map + sales-dialog-design）

**Files:** `myProgram/sales/states/.claude/code_map.md` / skill `reference/sales-dialog-design.md`

- [ ] **Step 1：更新 states code_map**

把 `_over_limit_reask` 條目改為 `_invalid_qty_reask` — 「無效數量重問狀態鏈：超上限 / 數量為0 統一重問 loop（12s+2reset）+ 取消/退出二選一」。

- [ ] **Step 2：更新 sales-dialog-design.md**

「超量重問狀態鏈 over_limit_reask」段 → rename 標題為「無效數量重問鏈 invalid_qty_reask」，補：pending 帶 reason（over_limit/zero）、zero 提示詞、qty==0 偵測點（Pass1 + funnel）、混合 reason 串接、中性化「取消這些商品」、負數 out-of-scope。目錄同步改名。

- [ ] **Step 3：Commit**

```bash
git add myProgram/sales/states/.claude/code_map.md .claude/skills/project-01-workflow/reference/sales-dialog-design.md
git commit -m "docs: document invalid_qty_reask generalization"
```

---

## Self-Review 對照

- spec §2.2 rename → Task 1；§2.3/2.4/2.5/2.6 一般化 + zero 文案 + 中性化 → Task 2；§2.7 偵測點 → Task 3；§3 docs → Task 4。
- 情境1→Task3 scenario1；情境2→scenario2；情境3→scenario3；混合 reason→resolve_mixed；假性加入回歸→no_false_added。
- 型別一致：`invalid_qty_reask(pending: dict)` 全程 dict；4 sentinel 不變；resolve/funnel 3-tuple 不變。
- over-limit 行為等價：Task 1 純改名跑綠 407、Task 2 dict 化後既有整合測試仍綠。
- No placeholder：核心 code 在 spec §2.4/2.6/2.7 完整；rename 為機械對照表；代表性測試齊全。
