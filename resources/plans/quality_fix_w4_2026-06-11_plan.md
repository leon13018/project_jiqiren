# quality_fix_w4 實作計畫（plan — HOW）

> **執行者**：sales-coder。對應 spec：`resources/specs/quality_fix_w4_2026-06-11_spec.md`。
> 純重構規約：綠 → 改 → 綠 → commit；每 task 一 commit；任一步 pytest 不是 `503 passed` 即停下回報。

**Goal**：#10-#13 低價值清理，行為零改變（#12 含 2 個測試檔的 assert 伴隨調整，無測試函式增刪）。

---

## Task 0：基線驗證

- [ ] **Step 0.1**：`python -m pytest tests/sales/` → 預期 `503 passed`。

---

## Task 1（#10）：nlu REJECT KeywordGroup 化 + 共享 cross-L cancel 清單

**Files**：Modify `myProgram/sales/nlu.py`

- [ ] **Step 1.1：Read worktree 內 `nlu.py`**

- [ ] **Step 1.2：import 補 `KeywordGroup`**

舊：

```python
from myProgram.sales.keyword_group import contains_any, equals_strict_short
```

新：

```python
from myProgram.sales.keyword_group import KeywordGroup, contains_any, equals_strict_short
```

- [ ] **Step 1.3：抽共享清單 + 兩清單改串接**

在 REJECT 區塊註解（`# REJECT substring 集（移除「沒/没」單字…`）**之前**插入：

```python
# 2026-05-29 cross-L cancel 意圖明確 phrase（user 列表擴充）——
# _KEYWORDS_REJECT 與 _KEYWORDS_REJECT_L3_STRICT 共用（雙清單平行維護收斂）。
# 會被 DialogSession._dispatch()（主迴圈與沉默期語境共用）偵測到後，
# 經 cancel_confirm gate 才真正退 L1
_KEYWORDS_CROSS_L_CANCEL = [
    "取消交易", "退出交易", "我想取消交易", "我要取消交易",
    "取消交易吧", "我想要取消交易",
    "取消这次交易", "退出这次交易",  # 簡體
]
```

原 REJECT 區塊頭註解中的 4 行 cross-L 說明（`# 2026-05-29 加：cross-L cancel 意圖明確 phrase…` 至 `#   經 cancel_confirm gate 才真正退 L1`）已併入上方新註解 → 自原位置移除。

`_KEYWORDS_REJECT` 尾端 4 行（`# 2026-05-29 cross-L cancel 擴充` + 8 片語 3 行）刪除，結尾改：

```python
    "不买", "不想买", "不买了",  # 簡體變體
    "没有额外",                    # 簡體變體（「不需要」繁簡同字不另列）
] + _KEYWORDS_CROSS_L_CANCEL  # cross-L cancel 擴充（共享清單）
```

`_KEYWORDS_REJECT_L3_STRICT` 尾端 5 行（`# 2026-05-29 cross-L cancel 擴充（user 列表）…` 兩行註解 + 8 片語 3 行）刪除，結尾改：

```python
    "不要買了", "不想買",
    "不要买了", "不想买",  # 簡體
] + _KEYWORDS_CROSS_L_CANCEL  # cross-L 明確 phrase（「取消/退出」substring 已涵蓋，明示共享清單提升可讀性）
```

- [ ] **Step 1.4：建 `_KG_REJECT` + 替換兩處判定式**

`_KEYWORDS_REJECT_STRICT_SHORT = [...]` 之後加：

```python
# REJECT 雙集配對（兩處判定式共用；對齊 W1 oop_w1 KG_* 慣例）
_KG_REJECT = KeywordGroup(tuple(_KEYWORDS_REJECT), tuple(_KEYWORDS_REJECT_STRICT_SHORT))
```

`classify_intent` 內兩處（normal mode 與通用優先序；前後註解不動）：

舊（兩處同型，回傳值各為 `"結帳"` / `"拒絕"`）：

```python
if contains_any(text, _KEYWORDS_REJECT) or equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT):
```

新：

```python
if _KG_REJECT.matches(text):
```

- [ ] **Step 1.5**：`python -m pytest tests/sales/` → `503 passed`
- [ ] **Step 1.6**：

```bash
git add myProgram/sales/nlu.py
git commit -m "refactor(sales): dedupe nlu REJECT matching via KeywordGroup + shared cross-L cancel list"
git branch --contains HEAD
```

---

## Task 2（#11）：抽 `_match_tens`

**Files**：Modify `myProgram/sales/nlu.py`

- [ ] **Step 2.1：`_CHINESE_UNIT_CHARS` 定義之後、`_parse_compound_chinese` 之前插入**

```python
def _match_tens(text: str) -> int | None:
    """匹配「[X]十Y」十位 pattern；命中回 tens*10+units，未命中回 None。

    共用：_parse_compound_chinese 十位分支 / _parse_tens_part（原兩份相同 regex + 計算）。
    """
    m = re.search(rf"([{_CHINESE_UNIT_CHARS}])?[十拾]([{_CHINESE_UNIT_CHARS}])?", text)
    if m is None:
        return None
    tens = CHINESE_DIGIT_MAP.get(m.group(1), 1)
    units_val = CHINESE_DIGIT_MAP.get(m.group(2), 0)
    return tens * 10 + units_val
```

- [ ] **Step 2.2：`_parse_compound_chinese` 十位分支替換**

舊：

```python
    # 「十」位
    m = re.search(rf"([{units}])?[十拾]([{units}])?", text)
    if m:
        tens_char = m.group(1)
        units_char = m.group(2)
        tens = CHINESE_DIGIT_MAP.get(tens_char, 1)
        units_val = CHINESE_DIGIT_MAP.get(units_char, 0)
        return tens * 10 + units_val

    return None
```

新（命中回值 / 未命中回 None——與原控制流逐字等價）：

```python
    # 「十」位（共用 _match_tens）
    return _match_tens(text)
```

（`units = _CHINESE_UNIT_CHARS` local 仍供「百」位 regex 使用，保留。）

- [ ] **Step 2.3：`_parse_tens_part` 十位段替換**

舊：

```python
    units = _CHINESE_UNIT_CHARS
    m = re.search(rf"([{units}])?[十拾]([{units}])?", text)
    if m:
        tens = CHINESE_DIGIT_MAP.get(m.group(1), 1)
        u = CHINESE_DIGIT_MAP.get(m.group(2), 0)
        return tens * 10 + u
```

新：

```python
    tens_val = _match_tens(text)
    if tens_val is not None:
        return tens_val
```

（其後「純個位」fallback 迴圈與 `return 0` 不動。）

- [ ] **Step 2.4**：`python -m pytest tests/sales/` → `503 passed`
- [ ] **Step 2.5**：

```bash
git add myProgram/sales/nlu.py
git commit -m "refactor(sales): extract _match_tens for compound Chinese numeral parsing"
git branch --contains HEAD
```

---

## Task 3（#12）：刪零效果 strict_short 子集 + 測試伴隨調整

**Files**：Modify `myProgram/sales/constants/keywords.py`、`tests/sales/test_keyword_group.py`、`tests/sales/test_constants.py`

- [ ] **Step 3.1：Read 三檔**

- [ ] **Step 3.2：`keywords.py` 刪兩常數**

刪除兩行定義：

```python
KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT: list = ["繼續", "取消", "继续"]
```

```python
KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT: list = ["退出", "離開", "离开"]
```

`__all__` 移除 `"KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT",` 與 `"KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT",` 兩項。

KG 建構改單參：

舊：

```python
KG_INVALID_QTY_CONTINUE = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_CONTINUE), tuple(KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT))
KG_INVALID_QTY_EXIT = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_EXIT), tuple(KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT))
```

新：

```python
# strict_short 省略：原兩集（繼續/取消/继续、退出/離開/离开）全為對應 substring 集子集，
# equals_strict_short 命中必蘊含 contains_any 命中 → 零行為效果（quality_fix_w4 移除）
KG_INVALID_QTY_CONTINUE = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_CONTINUE))
KG_INVALID_QTY_EXIT = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_EXIT))
```

- [ ] **Step 3.3：`test_keyword_group.py` 調整**

import 清單移除 `    KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT,` 與 `    KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT,` 兩行。

兩個 wired 測試的 strict_short assert 改寫：

舊：

```python
    assert KG_INVALID_QTY_CONTINUE.strict_short == tuple(KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT)
```

新：

```python
    # strict_short 已移除（原集全為 substring 子集，零行為效果，quality_fix_w4）
    assert KG_INVALID_QTY_CONTINUE.strict_short == ()
```

（`KG_INVALID_QTY_EXIT` 同型改 `== ()`。substrings assert 兩行不動。）

- [ ] **Step 3.4：`test_constants.py` 調整**

`test_invalid_qty_constants_present_and_valued` import 段：

舊：

```python
        KEYWORDS_INVALID_QTY_CANCEL_TRIGGER, KEYWORDS_INVALID_QTY_CONTINUE,
        KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT,
        KEYWORDS_INVALID_QTY_EXIT, KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT,
```

新：

```python
        KEYWORDS_INVALID_QTY_CANCEL_TRIGGER, KEYWORDS_INVALID_QTY_CONTINUE,
        KEYWORDS_INVALID_QTY_EXIT,
```

末行 assert：

舊：

```python
    assert "繼續" in KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT
```

新（守護意圖不變——「繼續」必須被辨識，現由 substring 集承擔）：

```python
    assert "繼續" in KEYWORDS_INVALID_QTY_CONTINUE
```

- [ ] **Step 3.5：grep 確認零殘留**：`KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT|KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT` 在 `myProgram/` 與 `tests/` 應 0 命中。

- [ ] **Step 3.6**：`python -m pytest tests/sales/` → `503 passed`（assert 改寫，無函式增刪）
- [ ] **Step 3.7**：

```bash
git add myProgram/sales/constants/keywords.py tests/sales/test_keyword_group.py tests/sales/test_constants.py
git commit -m "refactor(sales): drop no-op INVALID_QTY strict_short subsets"
git branch --contains HEAD
```

---

## Task 4（#13）：l4 兩個微 helper

**Files**：Modify `myProgram/sales/states/l4.py`

- [ ] **Step 4.1：Read worktree 內 `l4.py`**

- [ ] **Step 4.2：加兩 helper**

`run_l4` 之後（`_l4_print_entry_detail` 之前）插入：

```python
def _l4_fresh_deadlines() -> tuple:
    """回傳 (budget_deadline, cycle_deadline)——自此刻起算。

    entry 與客服 reset 兩處共用：兩計時器起算點必須同步（36 = 12 × 3 不變量，
    見 L4_v3_dual_timer_spec），抽單點避免雙處漂移。
    """
    now = time.monotonic()
    return now + L4_TOTAL_BUDGET, now + L4_QR_REFRESH_INTERVAL
```

`_l4_exit_to_l1` 之後插入：

```python
def _l4_pay_success(io) -> tuple:
    """鏈路 A 共同體：付款成功 speak + 鞠躬動作 + 進 L5（終端 "s" 與客服 "scan" 共用）。"""
    io.speak(L4_A_PAY_SUCCESS)
    io.do_action(ACTION_L4_PAY)
    return ("L5", 0, 0)
```

- [ ] **Step 4.3：替換 4 處**

entry（註解行保留）：

```python
    # v3 雙計時器：兩個獨立 wall-clock deadline，從 entry prompt 播完起算
    now = time.monotonic()
    budget_deadline = now + L4_TOTAL_BUDGET
    cycle_deadline = now + L4_QR_REFRESH_INTERVAL
```

→

```python
    # v3 雙計時器：兩個獨立 wall-clock deadline，從 entry prompt 播完起算
    budget_deadline, cycle_deadline = _l4_fresh_deadlines()
```

reset 分支（前兩行 print/speak 與 `continue` 不動）：

```python
            now = time.monotonic()
            budget_deadline = now + L4_TOTAL_BUDGET
            cycle_deadline = now + L4_QR_REFRESH_INTERVAL
            continue
```

→

```python
            budget_deadline, cycle_deadline = _l4_fresh_deadlines()
            continue
```

dispatch 終端 "s"（註解行保留）：

```python
    if response == "s":
        io.speak(L4_A_PAY_SUCCESS)
        io.do_action(ACTION_L4_PAY)
        return (("L5", 0, 0), 0.0)
```

→

```python
    if response == "s":
        return (_l4_pay_success(io), 0.0)
```

service mode "scan"：

```python
    if result == "scan":
        io.speak(L4_A_PAY_SUCCESS)
        io.do_action(ACTION_L4_PAY)
        return ("L5", 0, 0)
```

→

```python
    if result == "scan":
        return _l4_pay_success(io)
```

（主迴圈每輪開頭的 `now = time.monotonic()` 是另一個 local，不受 entry `now` 移除影響。）

- [ ] **Step 4.4**：`python -m pytest tests/sales/` → `503 passed`
- [ ] **Step 4.5**：

```bash
git add myProgram/sales/states/l4.py
git commit -m "refactor(sales): extract L4 fresh-deadlines and pay-success helpers"
git branch --contains HEAD
```

---

## 完成回報

4-status + 4 commit SHA + 各階段 pytest 末行 + TaskList 摘要。
