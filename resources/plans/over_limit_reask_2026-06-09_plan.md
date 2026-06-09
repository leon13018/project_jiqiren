# 超量重問狀態鏈 over_limit_reask — Implementation Plan

> **For agentic workers:** 本 plan 由 sales-coder 依 SDD 執行。每 step 一原子動作（2-5 分鐘），TDD Red-Green-Refactor。Spec（WHAT）：`resources/specs/over_limit_reask_2026-06-09_spec.md`。

**Goal:** 數量超量時不再自動 cap，改進「重問狀態鏈」問到正確數量才加入；含 12s+2reset 倒數、客服暫停、「取消超量 vs 退出」二選一。

**Architecture:** 新 helper `_over_limit_reask.py`（2 public + 2 private）；`resolve_and_add_products` 改 2-pass 編排 + 3-tuple return；`_qty_follow_up_sub_loop` funnel + 3-tuple return；`l2_l3_dialog.py` 3 caller 處理 `control`。即時提交模型（有效即加、pending 只含超量），無 staging。

**Tech Stack:** Python 3.11、pytest、純函式 + callback 注入、`time.monotonic` wall-clock。

---

## Task 1：新增常數（timing / shared / keywords）

**Files:**
- Modify: `myProgram/sales/constants/timing.py`
- Modify: `myProgram/sales/constants/shared.py`
- Modify: `myProgram/sales/constants/keywords.py`
- Test: `tests/sales/test_constants.py`

- [ ] **Step 1：寫 failing test（新常數存在且值正確）**

加到 `tests/sales/test_constants.py`：
```python
def test_over_limit_constants_present_and_valued() -> None:
    from myProgram.sales.constants import (
        OVER_LIMIT_REASK_TIMEOUT, OVER_LIMIT_MAX_RESETS,
        OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT,
        OVER_LIMIT_REASK_SINGLE_TEMPLATE, OVER_LIMIT_REASK_MULTI_TEMPLATE,
        OVER_LIMIT_UNCLEAR_PREFIX, OVER_LIMIT_CANCEL_CONFIRM_PROMPT,
        OVER_LIMIT_TIMEOUT_REENTER_PREFIX, OVER_LIMIT_CANCEL_REENTER_PREFIX,
        KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER, KEYWORDS_OVER_LIMIT_CONTINUE,
        KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT,
        KEYWORDS_OVER_LIMIT_EXIT, KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT,
    )
    assert OVER_LIMIT_REASK_TIMEOUT == 12
    assert OVER_LIMIT_MAX_RESETS == 2
    assert OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT == 6
    assert "{product}" in OVER_LIMIT_REASK_SINGLE_TEMPLATE
    assert "{products}" in OVER_LIMIT_REASK_MULTI_TEMPLATE and "{details}" in OVER_LIMIT_REASK_MULTI_TEMPLATE
    assert "退出" in KEYWORDS_OVER_LIMIT_EXIT
    assert "繼續" in KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT
```

- [ ] **Step 2：跑見 FAIL**

Run: `python -m pytest tests/sales/test_constants.py::test_over_limit_constants_present_and_valued -v`
Expected: FAIL（ImportError）

- [ ] **Step 3：加 timing 常數**

`timing.py` `__all__` 追加 `"OVER_LIMIT_REASK_TIMEOUT", "OVER_LIMIT_MAX_RESETS", "OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT"`，檔尾加：
```python
# 超量重問狀態鏈（2026-06-09 加；spec over_limit_reask）
# 數量超量 → 進重問 loop：12s budget，答了數量仍超量可重置最多 2 次（總 12×3=36s）。
OVER_LIMIT_REASK_TIMEOUT: int = 12
OVER_LIMIT_MAX_RESETS: int = 2
# 「取消超量商品 vs 退出交易」二選一 6s（對齊 CANCEL_CONFIRM_TIMEOUT；無 reset，保守 default 保 cart）
OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT: int = 6
```

- [ ] **Step 4：加 shared 文案**

`shared.py` `__all__` 追加 6 個 key，檔尾加：
```python
# 超量重問狀態鏈文案（2026-06-09 加；spec over_limit_reask）
# {remaining} = MAX_QTY_PER_ITEM - cart 既有量（cart 空時即 50）
OVER_LIMIT_REASK_SINGLE_TEMPLATE: str = "{product}目前最多只能選購 {remaining} {unit}，請重新說您想要的數量。"
# {products}「冰紅茶和刮刮樂」；{details}「50 瓶、50 張」（per-product remaining+unit 以「、」連）
OVER_LIMIT_REASK_MULTI_TEMPLATE: str = "{products}目前最多只能各選購 {details}，請重新說您想要的數量。"
OVER_LIMIT_UNCLEAR_PREFIX: str = "不好意思，系統無法判斷您的回復。"
OVER_LIMIT_CANCEL_CONFIRM_PROMPT: str = "請問您是想取消超量的商品然後繼續交易，還是想直接退出交易？"
# reenter prefix 以全形「，」結尾，與當前層 entry prompt 合成單句 speak（UX pacing）
OVER_LIMIT_TIMEOUT_REENTER_PREFIX: str = "由於您沒回應購買數量，請重新進選購，"
OVER_LIMIT_CANCEL_REENTER_PREFIX: str = "好的已為您取消超量的商品，"
```

- [ ] **Step 5：加 keywords 集**

`keywords.py` `__all__` 追加 5 個 key，檔尾加（完整內容見 spec §2.8）：
```python
# 超量重問狀態鏈 keyword（2026-06-09 加；spec over_limit_reask）
# 進二選一的廣義否定 trigger（補 is_cancel_intent 漏接的 bare「取消」「退出」）
KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER: list = [
    "取消", "不買", "不買了", "不要了", "不想買", "不想要了", "算了", "放棄", "退出",
    "不买", "不买了", "不想买", "不想要了", "放弃",
]
# 二選一 CONTINUE（取消超量商品繼續）— caller 先 check（保守：任何 取消/繼續 → 保 cart）
KEYWORDS_OVER_LIMIT_CONTINUE: list = [
    "取消超量", "取消超過", "取消超量的商品", "取消超過的商品", "取消商品",
    "繼續交易", "繼續購買", "繼續", "取消",
    "继续交易", "继续",
]
KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT: list = ["繼續", "取消", "继续"]
# 二選一 EXIT（退出交易）— caller 後 check（純 退出/離開 才退）
KEYWORDS_OVER_LIMIT_EXIT: list = [
    "退出", "直接退出", "退出交易", "直接退出交易", "離開", "离开",
]
KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT: list = ["退出", "離開", "离开"]
```

- [ ] **Step 6：跑見 PASS**

Run: `python -m pytest tests/sales/test_constants.py::test_over_limit_constants_present_and_valued -v`
Expected: PASS

- [ ] **Step 7：Commit**

```bash
git add myProgram/sales/constants/timing.py myProgram/sales/constants/shared.py myProgram/sales/constants/keywords.py tests/sales/test_constants.py
git commit -m "feat(sales): add over-limit re-ask state-chain constants"
```

---

## Task 2：`over_limit_cancel_confirm` helper（二選一，6s）

**Files:**
- Create: `myProgram/sales/states/_over_limit_reask.py`
- Test: `tests/sales/test_over_limit_reask.py`

- [ ] **Step 1：寫 failing tests**

新檔 `tests/sales/test_over_limit_reask.py`：
```python
"""over_limit_reask / over_limit_cancel_confirm 單元測試（2026-06-09）。"""
from myProgram.sales.states._over_limit_reask import (
    over_limit_reask, over_limit_cancel_confirm,
)
from myProgram.sales import cart as cart_module


class FakeInput:
    """依序回傳腳本中的回應；耗盡後回 None（模擬 timeout）。"""
    def __init__(self, scripted):
        self._items = list(scripted)
    def read(self, timeout):
        return self._items.pop(0) if self._items else None


def test_cancel_confirm_exit_keyword_returns_exit() -> None:
    speaks = []
    assert over_limit_cancel_confirm(
        speak=speaks.append, read_customer_input=FakeInput(["退出"]).read,
    ) == "exit"

def test_cancel_confirm_continue_keyword_returns_cancel_overlimit() -> None:
    assert over_limit_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput(["取消超量的商品繼續交易"]).read,
    ) == "cancel_overlimit"

def test_cancel_confirm_silent_defaults_cancel_overlimit() -> None:
    # silent（read 回 None）→ 保守保 cart
    assert over_limit_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput([]).read,
    ) == "cancel_overlimit"

def test_cancel_confirm_continue_checked_before_exit() -> None:
    # 「不想退出，繼續」含「退出」與「繼續」→ CONTINUE 先 check → cancel_overlimit
    assert over_limit_cancel_confirm(
        speak=lambda t: None, read_customer_input=FakeInput(["不想退出，繼續"]).read,
    ) == "cancel_overlimit"

def test_cancel_confirm_gibberish_then_exit() -> None:
    # 亂答不終結、不重置 → 再講退出 → exit
    speaks = []
    assert over_limit_cancel_confirm(
        speak=speaks.append, read_customer_input=FakeInput(["天氣真好", "退出"]).read,
    ) == "exit"
    assert any("無法判斷" in s for s in speaks)
```

- [ ] **Step 2：跑見 FAIL**

Run: `python -m pytest tests/sales/test_over_limit_reask.py -v`
Expected: FAIL（ModuleNotFoundError `_over_limit_reask`）

- [ ] **Step 3：建檔 + 實作 `over_limit_cancel_confirm`（+ module header / imports）**

`myProgram/sales/states/_over_limit_reask.py`：
```python
"""超量重問狀態鏈（2026-06-09 加；spec resources/specs/over_limit_reask_2026-06-09_spec.md）。

數量超量 → 不自動 cap，進重問 loop 問到正確數量才加入。對齊 _cancel_confirm /
_service_confirm 風格：callback 注入、不 import 廠商 SDK、對 cart in-place。即時提交
模型——有效數量立即 add_item，pending list 只含仍超量商品名。

兩 public helper：
    over_limit_reask        — 重問主 loop（12s budget + 最多 2 reset）
    over_limit_cancel_confirm — 「取消超量商品 vs 退出交易」二選一（6s，保守 default 保 cart）
"""

import time

from myProgram.sales.constants import (
    PRODUCTS,
    MAX_QTY_PER_ITEM,
    OVER_LIMIT_REASK_TIMEOUT,
    OVER_LIMIT_MAX_RESETS,
    OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT,
    OVER_LIMIT_REASK_SINGLE_TEMPLATE,
    OVER_LIMIT_REASK_MULTI_TEMPLATE,
    OVER_LIMIT_UNCLEAR_PREFIX,
    OVER_LIMIT_CANCEL_CONFIRM_PROMPT,
    KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER,
    KEYWORDS_OVER_LIMIT_CONTINUE,
    KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT,
    KEYWORDS_OVER_LIMIT_EXIT,
    KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT,
)
from myProgram.sales.nlu import (
    has_quantity, parse_quantity, classify_intent,
    contains_any, equals_strict_short,
)
from myProgram.sales.product_parser import parse_products
from myProgram.sales import cart as cart_module
from myProgram.sales.states._cancel_confirm import is_cancel_intent
from myProgram.sales.states._service_confirm import service_confirm


def over_limit_cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> str:
    """「取消超量商品繼續 vs 退出交易」二選一 6s 子狀態。

    Returns:
        "cancel_overlimit" — 取消超量商品、保留其他、繼續（CONTINUE keyword / silent / 亂答耗盡）
        "exit"             — 退出交易（純 EXIT keyword）

    check 順序 CONTINUE 先於 EXIT：保守原則，任何含「取消/繼續」→ 保 cart；
    唯純「退出/離開」才 exit。timeout / silent / 亂答耗盡 → cancel_overlimit（保 cart）。
    """
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    _speak_blocking(OVER_LIMIT_CANCEL_CONFIRM_PROMPT)
    deadline = time.monotonic() + OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "cancel_overlimit"
        response = read_customer_input(timeout=remaining)
        if response is None:
            return "cancel_overlimit"
        if (contains_any(response, KEYWORDS_OVER_LIMIT_CONTINUE)
                or equals_strict_short(response, KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT)):
            return "cancel_overlimit"
        if (contains_any(response, KEYWORDS_OVER_LIMIT_EXIT)
                or equals_strict_short(response, KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT)):
            return "exit"
        _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + OVER_LIMIT_CANCEL_CONFIRM_PROMPT)
```

- [ ] **Step 4：跑見 PASS（cancel_confirm 子集）**

Run: `python -m pytest tests/sales/test_over_limit_reask.py -k cancel_confirm -v`
Expected: 5 PASS

- [ ] **Step 5：Commit（與 Task 3 helper 一起 commit，先暫存或等 Task 3 完成）**

> 註：本檔尚缺 `over_limit_reask` + formatter，import 會被 Task 3 補完才整檔可用；Task 2/3 合併為一個 commit（見 Task 3 Step 末）。

---

## Task 3：`over_limit_reask` 主 loop + formatter

**Files:**
- Modify: `myProgram/sales/states/_over_limit_reask.py`
- Test: `tests/sales/test_over_limit_reask.py`

- [ ] **Step 1：寫 failing tests（核心行為矩陣）**

加到 `tests/sales/test_over_limit_reask.py`（`冰紅茶` 單位「瓶」上限 50、`刮刮樂`「張」上限 50）：
```python
def test_reask_single_resolved_adds_to_cart() -> None:
    cart = cart_module.new_cart()
    # pending 冰紅茶，顧客重答 "5" → 加 5 → resolved
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["5"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 5

def test_reask_multi_combined_prompt_and_resolve() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 兩商品同時超量；首 prompt 應合併列出；顧客一次重講 → 全加入
    r = over_limit_reask(
        ["冰紅茶", "刮刮樂"], cart, speak=speaks.append, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["紅茶40刮刮樂30"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 40
    assert cart_module.get_quantity(cart, "刮刮樂") == 30
    assert any("冰紅茶和刮刮樂" in s and "各選購" in s for s in speaks)

def test_reask_partial_fix_keeps_ok_reprompts_remaining() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 紅茶40(OK) 刮刮樂9999(仍超) → reset 重列刮刮樂 → "30" → 全加入
    r = over_limit_reask(
        ["冰紅茶", "刮刮樂"], cart, speak=speaks.append, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["紅茶40刮刮樂9999", "30"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 40
    assert cart_module.get_quantity(cart, "刮刮樂") == 30

def test_reask_silent_returns_reenter_timeout() -> None:
    cart = cart_module.new_cart()
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput([]).read,
    )
    assert r == "reenter_timeout"
    assert cart_module.is_empty(cart)

def test_reask_cancel_intent_then_continue_returns_reenter_cancel() -> None:
    cart = cart_module.new_cart()
    # 「不買了」→ 二選一 → 「取消超量商品繼續」→ reenter_cancel
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["不買了", "取消超量的商品繼續"]).read,
    )
    assert r == "reenter_cancel"

def test_reask_cancel_intent_then_exit_returns_exit_l1() -> None:
    cart = cart_module.new_cart()
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["不買了", "退出"]).read,
    )
    assert r == "exit_l1"

def test_reask_gibberish_does_not_reset_and_prompts() -> None:
    cart = cart_module.new_cart()
    speaks = []
    # 亂答一次 → speak 不明白 → 再答 "5" → resolved
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=speaks.append, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["天氣真好", "5"]).read,
    )
    assert r == "resolved"
    assert any("無法判斷" in s for s in speaks)

def test_reask_service_yes_reprompts_then_resolve() -> None:
    cart = cart_module.new_cart()
    # 客服 → service_confirm YES → 重 prompt → "5" → resolved
    # （service_confirm YES keyword「繼續」/「好的」；NO keyword「不繼續」等）
    r = over_limit_reask(
        ["冰紅茶"], cart, speak=lambda t: None, print_terminal=lambda t: None,
        read_customer_input=FakeInput(["客服", "繼續", "5"]).read,
    )
    assert r == "resolved"
    assert cart_module.get_quantity(cart, "冰紅茶") == 5
```

- [ ] **Step 2：跑見 FAIL**

Run: `python -m pytest tests/sales/test_over_limit_reask.py -v`
Expected: 新 8 test FAIL（`over_limit_reask` 未定義 / NameError）

- [ ] **Step 3：實作 formatter + `over_limit_reask`（接在 Task 2 檔內 `over_limit_cancel_confirm` 之後）**

```python
def _join_names(names: list) -> str:
    """商品名連接：1 個直接回；≥2 個用「、」連、末項前用「和」。"""
    if len(names) == 1:
        return names[0]
    return "、".join(names[:-1]) + "和" + names[-1]


def _format_over_limit_prompt(pending: list, cart) -> str:
    """組超量重問 prompt。remaining = MAX_QTY_PER_ITEM - cart 既有量（cart 空時即 50）。"""
    if len(pending) == 1:
        p = pending[0]
        unit = PRODUCTS[p]["單位"]
        remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)
        return OVER_LIMIT_REASK_SINGLE_TEMPLATE.format(product=p, remaining=remaining, unit=unit)
    products = _join_names(pending)
    details = "、".join(
        f"{MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)} {PRODUCTS[p]['單位']}"
        for p in pending
    )
    return OVER_LIMIT_REASK_MULTI_TEMPLATE.format(products=products, details=details)


def _apply_quantities(response: str, pending: list, cart) -> None:
    """把 response 內可解析數量 apply 到 pending 商品（in-place 改 pending / cart）。

    有效（0 < qty <= remaining）→ add_item + 從 pending 移除；超量 / <=0 → 留在 pending。
    多 pending 用 parse_products（需商品名）；單 pending 額外接受 bare number（parse_quantity）。
    """
    for product, qty in parse_products(response):
        if product in pending and qty is not None:
            remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
            if 0 < qty <= remaining:
                cart_module.add_item(cart, product, qty)
                pending.remove(product)
    # 單 pending 且顧客報 bare number（parse_products 無商品名 → 上面未命中）
    if len(pending) == 1 and has_quantity(response):
        product = pending[0]
        qty = parse_quantity(response)
        remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
        if 0 < qty <= remaining:
            cart_module.add_item(cart, product, qty)
            pending.remove(product)


def over_limit_reask(
    pending: list,
    cart,
    speak,
    print_terminal,
    read_customer_input,
    speak_and_wait=None,
) -> str:
    """超量重問主 loop（12s budget + 最多 OVER_LIMIT_MAX_RESETS 次 reset）。

    Args:
        pending: 仍超量商品名 list（in-place 縮減；有效答案 add_item 後移除）。

    Returns:
        "resolved"        — pending 全部進範圍（皆已 add_item 進 cart）
        "reenter_timeout" — 倒數歸零 / silent / 客服 NO（caller 重 speak entry + continue）
        "reenter_cancel"  — 否定 → 二選一選「取消超量商品繼續」
        "exit_l1"         — 否定 → 二選一選「退出」（caller 走 _dialog_exit_a）
    """
    _speak_blocking = speak_and_wait if speak_and_wait is not None else speak
    resets_left = OVER_LIMIT_MAX_RESETS
    _speak_blocking(_format_over_limit_prompt(pending, cart))
    deadline = time.monotonic() + OVER_LIMIT_REASK_TIMEOUT

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "reenter_timeout"
        response = read_customer_input(timeout=remaining)
        if response is None:
            return "reenter_timeout"

        # (1) 否定 → 二選一
        if (is_cancel_intent(response)
                or contains_any(response, KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER)):
            if over_limit_cancel_confirm(speak, read_customer_input, speak_and_wait) == "exit":
                return "exit_l1"
            return "reenter_cancel"

        # (2) 客服 → service_confirm（暫停 + 補償）
        if classify_intent(response, "normal") == "客服":
            paused = time.monotonic()
            result = service_confirm(
                speak=speak, print_terminal=print_terminal,
                read_customer_input=read_customer_input,
                speak_and_wait=speak_and_wait, allow_scan=False,
            )
            deadline += time.monotonic() - paused
            if result == "yes":
                _speak_blocking(_format_over_limit_prompt(pending, cart))
                continue
            return "reenter_timeout"

        # (3) 數量答案
        if has_quantity(response):
            _apply_quantities(response, pending, cart)
            if not pending:
                return "resolved"
            if resets_left > 0:
                resets_left -= 1
                deadline = time.monotonic() + OVER_LIMIT_REASK_TIMEOUT
            _speak_blocking(_format_over_limit_prompt(pending, cart))
            continue

        # (4) 亂答 → 提示，不重置
        _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + _format_over_limit_prompt(pending, cart))
```

- [ ] **Step 4：跑見 PASS（整檔）**

Run: `python -m pytest tests/sales/test_over_limit_reask.py -v`
Expected: 全 PASS（13 test）

- [ ] **Step 5：Commit（Task 2 + 3 合併）**

```bash
git add myProgram/sales/states/_over_limit_reask.py tests/sales/test_over_limit_reask.py
git commit -m "feat(sales): add over_limit_reask + over_limit_cancel_confirm helper"
```

---

## Task 4：`_qty_follow_up_sub_loop` funnel + 3-tuple return（情境2）

**Files:**
- Modify: `myProgram/sales/states/_l2_l3_qty_followup.py`
- Test: `tests/sales/test_states.py`

- [ ] **Step 1：寫 failing test（情境2 — followup 答超量 funnel 進重問鏈）**

加到 `tests/sales/test_states.py`：
```python
def test_qty_followup_over_limit_funnels_into_reask_loop() -> None:
    """情境2：紅茶缺數量 → 追問 → 答 100（超量）→ 進重問鏈 → 改 5 → 加 5。"""
    speaks: list = []
    cart = cart_module.new_cart()
    # 「紅茶」(缺量) → 追問 → "100"(超量) → over_limit_reask prompt → "5" → 加 5
    #  → resolve_and_add_products 返 added → L2_TO_L3_TRANSITION → None None → C-2 → 「對」 → L4
    customer_input = FakeCustomerInput(["紅茶", "100", "5", None, None, "對"])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 5
    assert any("最多只能選購" in s for s in speaks)
```

- [ ] **Step 2：跑見 FAIL**

Run: `python -m pytest "tests/sales/test_states.py::test_qty_followup_over_limit_funnels_into_reask_loop" -v`
Expected: FAIL（舊 cap 行為：加 50 而非 5；且無「最多只能選購」字串）

- [ ] **Step 3：改 `_qty_follow_up_sub_loop`**

`_l2_l3_qty_followup.py`：
1. import 區加：`from myProgram.sales.states._over_limit_reask import over_limit_reask`
2. signature 不變（callback 同），但 docstring Returns 改為 3-tuple；返回值全部補第 3 元素。
3. 超量分支（原 line 213-217）改：
```python
            if qty > remaining:
                # 2026-06-09：不再 cap，funnel 進 over_limit_reask（單商品）
                control = over_limit_reask(
                    [product], cart, speak, print_terminal,
                    read_customer_input, speak_and_wait,
                )
                if control == "resolved":
                    return True, None, None
                if control == "exit_l1":
                    return False, None, "exit_l1"
                return False, None, control     # reenter_timeout / reenter_cancel
```
4. 其餘 `return` 全加第 3 元素 `None`：
   - `return False, cancel_notice` → `return False, cancel_notice, None`（timeout / 拒絕 / 結帳 / attempts cap / 客服 NO）
   - `return False, None`（cart at-cap skip）→ `return False, None, None`
   - `return True, None`（正常加入）→ `return True, None, None`

- [ ] **Step 4：改 `resolve_and_add_products` 接 3-tuple + control 冒泡**

同檔 `resolve_and_add_products`：
1. docstring Returns 改 3-tuple（見 spec §2.5）。
2. 重構 for loop 為 **Pass 1 / Pass 1.5 / Pass 2**（完整 code 見 spec §2.5；import `over_limit_reask`）。
3. Pass 2 內：
```python
        accepted, cancel_notice, control = _qty_follow_up_sub_loop(
            product=product, unit=unit, speak=speak, print_terminal=print_terminal,
            read_customer_input=read_customer_input,
            classify_intent_mode=classify_intent_mode, cart=cart,
            speak_and_wait=speak_and_wait,
        )
        if control is not None:
            return added_count > 0, cancel_notices, control
        if accepted:
            added_count += 1
        elif cancel_notice is not None:
            cancel_notices.append(cancel_notice)
```
4. 所有 `return added_count > 0, cancel_notices` → 補第 3 元素（見 spec §2.5；正常結尾 `return added_count > 0, cancel_notices, None`）。

> 註：本 step 同時改 `resolve_and_add_products` 的 return arity，會讓 `l2_l3_dialog.py` 既有解包（2-tuple）報錯——Task 5 修。為讓 Task 4 test 能跑，本 step 後**先不跑全 suite**，待 Task 5 完成再整跑。

- [ ] **Step 5：跑見 PASS（單一 test，繞過尚未更新的 caller）**

> 因 `run_dialog` caller 尚未改（Task 5），此 test 暫時仍會因解包 error 失敗。**將 Task 4 Step 1 的 test 與 Task 5 合併驗證**——本 step 標記為「實作完成、待 Task 5 整合跑綠」。先 commit code、不宣告綠。

- [ ] **Step 6：Commit（與 Task 5 合併為一個邏輯 commit；此處先不獨立 commit，見 Task 5 Step 末）**

---

## Task 5：`l2_l3_dialog.py` 三 caller 處理 control

**Files:**
- Modify: `myProgram/sales/states/l2_l3_dialog.py`
- Test: `tests/sales/test_states.py`

- [ ] **Step 1：寫 failing tests（情境1 / 情境3 / reenter / exit）**

加到 `tests/sales/test_states.py`：
```python
def test_scenario1_multi_over_limit_combined_reask() -> None:
    """情境1：紅茶100刮刮樂3434 → 合併重問 → 一次重講 → 全加入。"""
    speaks: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶100刮刮樂3434", "紅茶40刮刮樂30", None, None, "對"])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 40
    assert cart_module.get_quantity(cart, "刮刮樂") == 30
    assert any("各選購" in s for s in speaks)

def test_scenario3_over_limit_first_then_missing_qty_followup() -> None:
    """情境3：紅茶刮刮樂33434 → 先重問刮刮樂超量 → 解決 → 再追問紅茶數量。"""
    speaks: list = []
    cart = cart_module.new_cart()
    # 刮刮樂33434 超量 → 重問 → "刮刮樂5" → 解決 → 追問紅茶 → "3" → 加
    customer_input = FakeCustomerInput(["紅茶刮刮樂33434", "刮刮樂5", "3", None, None, "對"])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert cart_module.get_quantity(cart, "刮刮樂") == 5
    assert cart_module.get_quantity(cart, "冰紅茶") == 3

def test_over_limit_reenter_timeout_respeaks_entry() -> None:
    """超量 → 沉默 timeout → reenter：speak「由於您沒回應…」+ entry，回主迴圈。"""
    speaks: list = []
    cart = cart_module.new_cart()
    # 紅茶100 超量 → 沉默(None)逐步 → reenter_timeout → speak prefix+L2_ENTRY → 之後沉默 → L2 timeout 退
    customer_input = FakeCustomerInput(["紅茶100", None, None, None, None, None, None])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert any("由於您沒回應購買數量" in s for s in speaks)
    assert cart_module.is_empty(cart)

def test_over_limit_exit_returns_to_l1() -> None:
    """超量 → 否定 → 二選一退出 → 回 L1。"""
    speaks: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶100", "不買了", "退出"])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert next_state == "L1_via_subroutine_a"

def test_over_limit_cancel_overlimit_reenters_with_notice() -> None:
    """超量 → 否定 → 二選一取消超量繼續 → speak「好的已為您取消超量的商品」+ entry。"""
    speaks: list = []
    cart = cart_module.new_cart()
    customer_input = FakeCustomerInput(["紅茶100", "不買了", "取消超量的商品繼續", None, None])
    next_state, _ = states.run_dialog(
        speak=lambda t: speaks.append(t), print_terminal=lambda t: None,
        read_customer_input=customer_input.read, cart=cart, think_count=0,
        opencv_disable=lambda: None, do_action=lambda *a, **k: None,
    )
    assert any("好的已為您取消超量的商品" in s for s in speaks)
```

- [ ] **Step 2：改三個 caller**

`l2_l3_dialog.py`：
1. import 區（top constants import）加：`OVER_LIMIT_TIMEOUT_REENTER_PREFIX, OVER_LIMIT_CANCEL_REENTER_PREFIX`。
2. **`_dialog_main_loop` 商品分支**（原 line 757-790）：解包改 `added, cancel_notices, control = resolve_and_add_products(...)`；緊接在 `if added:` 之前插入：
```python
            if control == "exit_l1":
                return _dialog_exit_a(speak, cart)
            if control in ("reenter_timeout", "reenter_cancel"):
                prefix = (OVER_LIMIT_TIMEOUT_REENTER_PREFIX if control == "reenter_timeout"
                          else OVER_LIMIT_CANCEL_REENTER_PREFIX)
                entry = L2_ENTRY_PROMPT if cart_module.is_empty(cart) else L3_ENTRY_PROMPT
                speak(prefix + entry)
                continue
```
3. **`_dialog_dispatch_inner_l2`**（原 line 277-300）：解包改 3-tuple；`if added:` 前插入同樣 control 處理，但結尾用 `return None`（非 continue）：
```python
        added, cancel_notices, control = resolve_and_add_products(...)
        if control == "exit_l1":
            return _dialog_exit_a(speak, cart)
        if control in ("reenter_timeout", "reenter_cancel"):
            prefix = (OVER_LIMIT_TIMEOUT_REENTER_PREFIX if control == "reenter_timeout"
                      else OVER_LIMIT_CANCEL_REENTER_PREFIX)
            entry = L2_ENTRY_PROMPT if cart_module.is_empty(cart) else L3_ENTRY_PROMPT
            speak(prefix + entry)
            return None
```
4. **`_dialog_dispatch_inner_l3`**（原 line 394-407）：解包 `_added, cancel_notices, control = ...`（原本忽略 added 用 `_added`）；同樣 control 處理（`return None` 結尾）。

- [ ] **Step 3：跑見 PASS（情境 + funnel test 全綠）**

Run: `python -m pytest tests/sales/test_over_limit_reask.py "tests/sales/test_states.py::test_scenario1_multi_over_limit_combined_reask" "tests/sales/test_states.py::test_scenario3_over_limit_first_then_missing_qty_followup" "tests/sales/test_states.py::test_over_limit_reenter_timeout_respeaks_entry" "tests/sales/test_states.py::test_over_limit_exit_returns_to_l1" "tests/sales/test_states.py::test_over_limit_cancel_overlimit_reenters_with_notice" "tests/sales/test_states.py::test_qty_followup_over_limit_funnels_into_reask_loop" -v`
Expected: 全 PASS

- [ ] **Step 4：Commit（Task 4 + 5 合併）**

```bash
git add myProgram/sales/states/_l2_l3_qty_followup.py myProgram/sales/states/l2_l3_dialog.py tests/sales/test_states.py
git commit -m "refactor(sales): funnel over-limit into re-ask loop"
```

---

## Task 6：重寫既有 cap 測試為新行為

**Files:**
- Modify: `tests/sales/test_states.py`

- [ ] **Step 1：重寫超量（remaining>0）cap 測試**

下列 4 個測試的期望由「cap 加入 + 達到單筆上限」改為「進重問鏈 + 重答後加正確量」：

| 測試 | 舊期望 | 新期望（改寫） |
|---|---|---|
| `test_qty_followup_single_quantity_exceeds_cap_speaks_remaining_and_retries` | 加 50 + 「最多還能點」 | 已是「重答 5 加 5」語意——改 assert 出現「最多只能選購」（新文案）而非「最多還能點」 |
| `test_qty_followup_cumulative_quantity_exceeds_cap_speaks_remaining` | cap remaining | 重答後加正確量；assert「最多只能選購 20」 |
| `test_resolve_and_add_products_single_huge_qty_caps_and_speaks` | cap 50 + 「達到單筆上限」 | 改：輸入 `["紅茶 100", "5", None, None, "對"]` → 加 5；assert「最多只能選購」 |
| `test_resolve_and_add_products_cumulative_over_cap_caps_to_remaining` | 30+cap20=50 | 改：`["紅茶 25", "10", None, None, "對"]` → 30+10=40；assert「最多只能選購 20」 |
| `test_resolve_and_add_products_multi_product_partial_cap` | 紅茶 cap50 + 刮刮樂3 | 改：`["紅茶 100 刮刮樂 3", "紅茶40", None, None, "對"]` → 刮刮樂3 即加、紅茶進重問→40；assert 刮刮樂3 + 紅茶40 |
| `test_resolve_and_add_products_huge_number_does_not_crash` | cap 50 | 改：`["紅茶 34435454545454545", "3", None, None, "對"]` → 不 crash、加 3 |
| `test_qty_followup_huge_number_does_not_crash` | 重答 3 加 3（已是重答語意）| 維持加 3；assert 改「最多只能選購」 |

> at-cap（`remaining<=0`）兩測試 **不改**：`test_qty_followup_cart_at_cap_speaks_and_skips_product` / `test_resolve_and_add_products_at_cap_skips_and_speaks`（保留「無法再加」skip 行為）。

每個改寫測試：(a) 調整 `FakeCustomerInput` 腳本含「重答正確數量」；(b) assert cart 為正確量（非 cap）；(c) assert speak 含「最多只能選購」（新文案）。逐一改、逐一跑。

- [ ] **Step 2：跑見改寫測試 PASS**

Run: `python -m pytest "tests/sales/test_states.py" -k "exceeds_cap or huge or over_cap or partial_cap" -v`
Expected: 全 PASS（at-cap 兩個維持原樣亦 PASS）

- [ ] **Step 3：Commit**

```bash
git add tests/sales/test_states.py
git commit -m "test(sales): rewrite over-limit cap tests for re-ask behavior"
```

---

## Task 7：全量回歸 + code_map（階段 3b）

**Files:**
- Modify: `myProgram/sales/states/.claude/code_map.md`

- [ ] **Step 1：全量 pytest**

Run: `python -m pytest tests/sales/`
Expected: `N passed`（N > 344）、0 failed。任何 fail → 回對應 Task 修。

- [ ] **Step 2：更新 states code_map**

`myProgram/sales/states/.claude/code_map.md` 子模組清單加：`_over_limit_reask`（超量重問狀態鏈：重問 loop + 取消/退出二選一）。

- [ ] **Step 3：Commit**

```bash
git add myProgram/sales/states/.claude/code_map.md
git commit -m "docs(code_map): list _over_limit_reask"
```

---

## Self-Review 對照

- **Spec §2.3 reask loop** → Task 3；**§2.4 二選一** → Task 2；**§2.5 resolve 2-pass** → Task 4 Step 4；**§2.6 followup funnel** → Task 4 Step 3；**§2.7 caller control** → Task 5；**§2.8 常數** → Task 1。
- **情境1** → Task 5 test scenario1；**情境2** → Task 4 funnel test；**情境3** → Task 5 test scenario3。
- 型別一致：`over_limit_reask` 回傳 4 sentinel 字串全程一致；`resolve_and_add_products` / `_qty_follow_up_sub_loop` 統一 3-tuple。
- No placeholder：核心 helper 完整 code 在 Task 2/3；wiring 完整 code 在 Task 5；測試代表性實例齊全，§2.5/§2.8 完整內容在 spec。
