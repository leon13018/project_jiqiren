# 超量重問狀態鏈 over_limit_reask — SDD spec（2026-06-09）

> WHAT 契約。HOW step-by-step 見 `resources/plans/over_limit_reask_2026-06-09_plan.md`。
> 對話狀態機領域設計見 skill `reference/sales-dialog-design.md`（本功能將於收尾 append 進該檔）。

---

## 1. 背景與動機

Pi 實機測試輸出（顧客一句「紅茶343434」）：

```
[語音] 冰紅茶已加入 50 瓶，已達到單筆上限 50 瓶，您剛才要的 343434 瓶超過上限
[動作] L3
[語音] 好的，已加入購物車，請問還有額外需要購買的嗎？
```

**問題**：顧客數量超過商品單筆上限（`MAX_QTY_PER_ITEM=50`）時，系統**直接幫顧客 cap 成 50 瓶並加入購物車**，違反顧客本意（顧客沒同意買 50，只是念錯/口誤/STT 雜訊）。

現況 cap 行為散落兩處：
- `resolve_and_add_products`（顧客一句話含商品+數量）— `_l2_l3_qty_followup.py:118-127`
- `_qty_follow_up_sub_loop`（追問數量時顧客答超量）— `_l2_l3_qty_followup.py:209-217`

**訴求**：數量超量時不該自動 cap，應**進一個重問狀態鏈，問到顧客講出正確數量才加入**；顧客可在此鏈路否定（取消超量商品 / 退出交易）。

涵蓋三情境（顧客語句 → 期望行為）：
- **情境1** 「紅茶100刮刮樂3434」（多商品同時超量）→ 合併一個 loop，一次列出兩商品上限，顧客一次重講全部數量。
- **情境2** 「紅茶刮刮樂33」（刮刮樂33、紅茶缺數量）→ 系統問紅茶幾瓶，顧客答「100」（超量）→ 進重問鏈。
- **情境3** 「紅茶刮刮樂33434」（刮刮樂33434 超量、紅茶缺數量）→ **先**提示刮刮樂超量並重問，**後**再追問缺數量的紅茶。

---

## 2. 設計核心 + 行為規約

### 2.1 元件（對齊既有 `_cancel_confirm` / `_service_confirm` 風格：callback 注入、不 import 廠商 SDK、對 cart in-place）

新檔 `myProgram/sales/states/_over_limit_reask.py`，兩個 public helper + 兩個 module-private formatter：

| 符號 | 簽名 | 回傳 |
|---|---|---|
| `over_limit_reask` | `(pending: list[str], cart, speak, print_terminal, read_customer_input, speak_and_wait=None) -> str` | `"resolved"` / `"reenter_timeout"` / `"reenter_cancel"` / `"exit_l1"` |
| `over_limit_cancel_confirm` | `(speak, read_customer_input, speak_and_wait=None) -> str` | `"cancel_overlimit"` / `"exit"` |
| `_format_over_limit_prompt` | `(pending, cart) -> str` | 重問 prompt 字串 |
| `_join_names` | `(names: list[str]) -> str` | 商品名連接（「、」+ 末「和」） |

### 2.2 即時提交模型（**不做 staging 結構**）

有效數量**立即** `cart_module.add_item` 進 cart（與現有 in-range 即時加入一致）；`over_limit_reask` 只在 `pending`（仍超量商品名 list）上迴圈。各終端路徑 cart 結果：

| 終端 | 已加入的有效商品 | 仍超量商品 |
|---|---|---|
| `resolved`（全部進範圍）| 留 cart | 已全部解決 |
| `reenter_timeout`（超時 / 客服 NO）| 留 cart | 丟棄 |
| `reenter_cancel`（二選一選「取消超量繼續」）| 留 cart | 丟棄 |
| `exit_l1`（二選一選「退出」）| caller 走 `_dialog_exit_a` 清 cart | 丟棄 |

> 「保留已 OK、只丟超量」由「有效即加 + pending 只含超量」自然達成，無需 staging。`exit_l1` 由 `_dialog_exit_a` 統一清 cart（cart 非空時）。

### 2.3 `over_limit_reask` 行為（12s budget + 最多 2 reset）

計時常數：`OVER_LIMIT_REASK_TIMEOUT=12`、`OVER_LIMIT_MAX_RESETS=2`（總等待最多 `12×3=36s`，**僅在有 reset 時**）。

```python
_speak_blocking = speak_and_wait or speak
resets_left = OVER_LIMIT_MAX_RESETS
_speak_blocking(_format_over_limit_prompt(pending, cart))
deadline = monotonic() + OVER_LIMIT_REASK_TIMEOUT
while True:
    remaining = deadline - monotonic()
    if remaining <= 0:
        return "reenter_timeout"
    response = read_customer_input(timeout=remaining)
    if response is None:
        return "reenter_timeout"

    # (1) 否定 → 二選一（先於數量 / 客服判定）
    if is_cancel_intent(response) or contains_any(response, KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER):
        if over_limit_cancel_confirm(speak, read_customer_input, speak_and_wait) == "exit":
            return "exit_l1"
        return "reenter_cancel"

    # (2) 客服 → _service_confirm（計時暫停 + 補償）
    if classify_intent(response, "normal") == "客服":
        paused = monotonic()
        result = service_confirm(speak, print_terminal, read_customer_input,
                                 speak_and_wait, allow_scan=False)
        deadline += monotonic() - paused            # 凍結子狀態耗時
        if result == "yes":
            _speak_blocking(_format_over_limit_prompt(pending, cart))   # 不計 reset
            continue
        return "reenter_timeout"                     # NO / silent

    # (3) 數量答案
    if has_quantity(response):
        _apply_quantities(response, pending, cart)   # 有效者 add_item + 從 pending 移除
        if not pending:
            return "resolved"
        if resets_left > 0:                          # 答了數量但仍超量 → reset（最多 2 次）
            resets_left -= 1
            deadline = monotonic() + OVER_LIMIT_REASK_TIMEOUT
        _speak_blocking(_format_over_limit_prompt(pending, cart))   # 只列仍超量者
        continue

    # (4) 亂答（無數量 / 非客服 / 非否定）→ 提示，不重置
    _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + _format_over_limit_prompt(pending, cart))
    continue
```

**`_apply_quantities(response, pending, cart)`**（in-place 改 pending / cart）：
- `len(pending) == 1`：`qty = parse_quantity(response)`；`remaining = MAX - get_quantity(cart, p)`；`0 < qty <= remaining` → `add_item` + `pending.remove(p)`。
- `len(pending) >= 1`（多商品 / 顧客重講帶商品名）：`for product, qty in parse_products(response)`：`product in pending and qty is not None and 0 < qty <= remaining` → `add_item` + `pending.remove(product)`。
- 兩分支可合併：先試 `parse_products`；若 `len(pending)==1` 且仍未解決且 `has_quantity` → 用 `parse_quantity` 補單商品（顧客報 bare number「30」）。

**reset 語意**：reset 只由「答了數量但仍有超量」觸發（含部分修正：紅茶40 OK、刮刮樂仍超 → 仍算一次 reset 並只重列刮刮樂）。亂答不 reset；沉默不 reset（沉默直接 timeout）。resets 用盡後再超量答案 → 重 speak 但 deadline 不重置，續用現有倒數至歸零 → `reenter_timeout`。

### 2.4 `over_limit_cancel_confirm` 行為（6s，無 reset，保守 default）

```python
_speak_blocking = speak_and_wait or speak
_speak_blocking(OVER_LIMIT_CANCEL_CONFIRM_PROMPT)
deadline = monotonic() + OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT     # 6
while True:
    remaining = deadline - monotonic()
    if remaining <= 0:
        return "cancel_overlimit"                  # 保守：保 cart
    response = read_customer_input(timeout=remaining)
    if response is None:
        return "cancel_overlimit"
    # CONTINUE 先 check（含「取消」「繼續」）— 任何 取消/繼續 提及 → 保守保 cart
    if contains_any(response, KEYWORDS_OVER_LIMIT_CONTINUE) \
       or equals_strict_short(response, KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT):
        return "cancel_overlimit"
    # EXIT 後 check（純「退出」「離開」才退）
    if contains_any(response, KEYWORDS_OVER_LIMIT_EXIT) \
       or equals_strict_short(response, KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT):
        return "exit"
    # 亂答 → 提示 + 重 prompt，不重置
    _speak_blocking(OVER_LIMIT_UNCLEAR_PREFIX + OVER_LIMIT_CANCEL_CONFIRM_PROMPT)
```

**check 順序 = CONTINUE 先於 EXIT**（保守原則：任何含「取消/繼續」→ 留 cart；唯有純「退出/離開」才 `exit`。對齊 cancel_confirm「NO 先 check」防呆精神 + skill `sales-dialog-design.md`「confirm ambiguous 一律保守」鐵則）。timeout / 沉默 / 亂答耗盡 → `cancel_overlimit`（保 cart）。

### 2.5 `resolve_and_add_products` 兩階段編排（**取代** cap 邏輯）

return 契約：`(added: bool, cancel_notices: list[str], control: str | None)`（新增第 3 元素 `control ∈ {None, "reenter_timeout", "reenter_cancel", "exit_l1"}`）。

```python
added_count = 0; cancel_notices = []; over_pending = []; missing = []
# Pass 1：分類直接給數量者（in-range 即時加入；超量收進 over_pending；缺數量排入 missing）
for product, qty in products:
    if qty is None:
        missing.append(product); continue
    existing = get_quantity(cart, product); remaining = MAX - existing
    unit = PRODUCTS[product]["單位"]
    if remaining <= 0:
        speak(f"{product}已經點到單筆上限 {MAX} {unit}，無法再加")   # 保留既有 at-cap skip
        continue
    if qty > remaining:
        over_pending.append(product); continue
    add_item(cart, product, qty); added_count += 1
# Pass 1.5：合併超量重問（情境1）；先於 missing 追問（情境3）
if over_pending:
    n = len(over_pending)
    control = over_limit_reask(over_pending, cart, speak, print_terminal,
                               read_customer_input, speak_and_wait)
    if control == "resolved":
        added_count += n
    else:
        return (added_count > 0, cancel_notices, control)      # reenter/exit 冒泡，跳過 missing
# Pass 2：缺數量追問（情境2 在此內部 funnel）
for product in missing:
    unit = PRODUCTS[product]["單位"]
    _speak_blocking(QTY_PROMPT_TEMPLATE.format(product=product, unit=unit))
    accepted, cancel_notice, control = _qty_follow_up_sub_loop(...)
    if control is not None:
        return (added_count > 0, cancel_notices, control)
    if accepted:
        added_count += 1
    elif cancel_notice is not None:
        cancel_notices.append(cancel_notice)
return (added_count > 0, cancel_notices, None)
```

> `at-cap`（`remaining <= 0`）保留既有「無法再加」skip+speak（重問「最多選購 0」無意義）；只有 `remaining > 0` 的真超量才進重問鏈。

### 2.6 `_qty_follow_up_sub_loop` funnel（情境2）

return 契約：`(accepted: bool, cancel_notice: str | None, control: str | None)`（新增第 3 元素）。其唯一 caller 是 `resolve_and_add_products`。

追問內顧客答超量（`remaining > 0 and qty > remaining`）→ **不再 cap，改 funnel 進 `over_limit_reask([product])`**：
```python
if qty > remaining:
    control = over_limit_reask([product], cart, speak, print_terminal,
                               read_customer_input, speak_and_wait)
    if control == "resolved":
        return True, None, None       # 已在 loop 內 add_item
    if control == "exit_l1":
        return False, None, "exit_l1"
    return False, None, control        # reenter_timeout / reenter_cancel
```
`remaining <= 0`（cart 已達上限）保留既有「已經點到單筆上限…無法再加」skip → `return False, None, None`。其餘既有分支（timeout / 拒絕 / 結帳-as-skip / attempts cap / 客服）回傳 `control=None`（行為不變，只多帶第 3 元素）。

### 2.7 三個 caller 處理 control（`l2_l3_dialog.py`）

`_dialog_main_loop`（商品分支）/ `_dialog_dispatch_inner_l2` / `_dialog_dispatch_inner_l3` 解包改 3-tuple，新增 control 處理（**先於**既有 added/notices 邏輯）：
```python
added, cancel_notices, control = resolve_and_add_products(...)
if control == "exit_l1":
    return _dialog_exit_a(speak, cart)
if control in ("reenter_timeout", "reenter_cancel"):
    prefix = (OVER_LIMIT_TIMEOUT_REENTER_PREFIX if control == "reenter_timeout"
              else OVER_LIMIT_CANCEL_REENTER_PREFIX)
    entry = L2_ENTRY_PROMPT if cart_module.is_empty(cart) else L3_ENTRY_PROMPT
    speak(prefix + entry)                 # 合成單一 speak（UX pacing）
    <continue / return None>              # 不再跑既有 added/notices speak
# control is None → 既有行為（speak transition/reask + continue / return None）
```
- 「回當前層入口」= 重 speak `L2_ENTRY_PROMPT`（cart 空）或 `L3_ENTRY_PROMPT`（cart 非空），與 timeout/cancel prefix 合成單句（避免兩段 speak 的 ALSA drain 停頓，對齊 `L2_TO_L3_TRANSITION` 哲學）。
- `_dialog_main_loop` 用 `continue`；兩個 `_dialog_dispatch_inner_*` 用 `return None`。
- **不在 over-limit reenter 觸發 `do_action(ACTION_L3)`**（L2→L3 transition 動作）：此為邊緣重入路徑，主迴圈下一輪會以正確 cart 狀態運作；避免將 `do_action` callback 穿進 `resolve_and_add_products`（YAGNI）。

### 2.8 文案 / keyword（繁中）

**`constants/shared.py`**（跨層）：
```python
OVER_LIMIT_REASK_SINGLE_TEMPLATE = "{product}目前最多只能選購 {remaining} {unit}，請重新說您想要的數量。"
OVER_LIMIT_REASK_MULTI_TEMPLATE  = "{products}目前最多只能各選購 {details}，請重新說您想要的數量。"
OVER_LIMIT_UNCLEAR_PREFIX        = "不好意思，系統無法判斷您的回復。"
OVER_LIMIT_CANCEL_CONFIRM_PROMPT = "請問您是想取消超量的商品然後繼續交易，還是想直接退出交易？"
OVER_LIMIT_TIMEOUT_REENTER_PREFIX = "由於您沒回應購買數量，請重新進選購，"
OVER_LIMIT_CANCEL_REENTER_PREFIX  = "好的已為您取消超量的商品，"
```
- `{products}` 範例「冰紅茶和刮刮樂」（`_join_names`）；`{details}` 範例「50 瓶、50 張」（per-product `{remaining} {unit}`，以「、」連）。
- reenter prefix 以全形「，」結尾，直接 `prefix + entry_prompt` 合成單句。

**`constants/timing.py`**：
```python
OVER_LIMIT_REASK_TIMEOUT: int = 12
OVER_LIMIT_MAX_RESETS: int = 2
OVER_LIMIT_CANCEL_CONFIRM_TIMEOUT: int = 6
```

**`constants/keywords.py`**（風格對齊既有 substring + strict_short 分離）：
```python
# 進二選一的否定 trigger（over_limit_reask 內，is_cancel_intent 漏接的廣義否定補強）
KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER = [
    "取消", "不買", "不買了", "不要了", "不想買", "不想要了", "算了", "放棄", "退出",
    "不买", "不买了", "不想买", "不想要了", "放弃", "退出",   # 簡體
]
# 二選一：CONTINUE（取消超量繼續）— 先 check，保守保 cart
KEYWORDS_OVER_LIMIT_CONTINUE = [
    "取消超量", "取消超過", "取消超量的商品", "取消超過的商品", "取消商品",
    "繼續交易", "繼續購買", "繼續", "取消",
    "取消超量", "继续交易", "继续", "取消",   # 簡體
]
KEYWORDS_OVER_LIMIT_CONTINUE_STRICT_SHORT = ["繼續", "取消", "继续"]
# 二選一：EXIT（退出交易）— 後 check，純退出/離開才退
KEYWORDS_OVER_LIMIT_EXIT = [
    "退出", "直接退出", "退出交易", "直接退出交易", "離開", "离开",
]
KEYWORDS_OVER_LIMIT_EXIT_STRICT_SHORT = ["退出", "離開", "离开"]
```
全部加進對應檔 `__all__`。

---

## 3. 改檔範圍（高層；step-by-step 見 plan）

| 檔 | 改動類型 | 估計 |
|---|---|---|
| `myProgram/sales/states/_over_limit_reask.py` | **新增** 2 public + 2 private helper | ~130 行 |
| `myProgram/sales/states/_l2_l3_qty_followup.py` | 改 `resolve_and_add_products`（2-pass + 3-tuple return）、`_qty_follow_up_sub_loop`（funnel + 3-tuple return） | ~60 行異動 |
| `myProgram/sales/states/l2_l3_dialog.py` | 3 caller 解包 3-tuple + control 處理 | ~40 行異動 |
| `myProgram/sales/constants/timing.py` | +3 常數 + `__all__` | ~8 行 |
| `myProgram/sales/constants/shared.py` | +6 文案 + `__all__` | ~10 行 |
| `myProgram/sales/constants/keywords.py` | +4 keyword 集 + `__all__` | ~25 行 |
| `tests/sales/test_over_limit_reask.py` | **新增** 單元測試 | 新檔 |
| `tests/sales/test_states.py` | **重寫** 7 個 cap 測試為新行為 + 新增情境1/2/3 整合測試 | 異動 |
| `tests/sales/test_constants.py` | 新常數值斷言 | 少量 |
| `myProgram/sales/states/.claude/code_map.md` | 列出新檔（階段 3b） | 1 行 |

---

## 4. Out of scope（明示不動）

- **`MAX_QTY_PER_ITEM` 值**（仍 50）、`cart.add_item` 的 invariant assert（內部守衛保留）。
- **at-cap（remaining<=0）行為**：保留既有「無法再加」skip+speak（不進重問鏈）。
- **`do_action` / `main.py` wire-up**：callback 簽名不變；over-limit reenter 不觸發 transition 動作。
- **既有非超量分支**（timeout / 拒絕 / 結帳-as-skip / attempts cap / 客服）行為不變，僅多帶 `control=None`。
- **`_cancel_confirm` / `_service_confirm` 既有 helper 本身**不改（over-limit 走新的二選一，不污染既有跨層 cancel）。
- **C-2 / L4 / unclear-final** 等其他子狀態不動。
- 顧客在重問鏈內**新增 pending 以外商品**（罕見）→ 忽略，只解決 pending。

---

## 5. 規範與參考

- 派 **sales-coder**（frontmatter 預載 karpathy-guidelines + TDD skill）。
- 既有可 reuse：`_cancel_confirm.is_cancel_intent`、`_service_confirm.service_confirm`、`nlu.{has_quantity,parse_quantity,classify_intent,contains_any,equals_strict_short}`、`product_parser.parse_products`、`cart_module.{add_item,get_quantity}`、`PRODUCTS`、`MAX_QTY_PER_ITEM`。
- pattern 對照：`_cancel_confirm.py`（wall-clock budget + speak_and_wait）、`_service_confirm.py`（24s gate + pause）、`_dialog_c2_second_stage`（亂答不重置倒數）。
- 領域鐵則：skill `sales-dialog-design.md`「confirm ambiguous 保守」「NO/EXIT substring 防呆」「跨層 helper callback 注入」。

---

## 6. 測試指令 + 預期結果

```
python -m pytest tests/sales/
```
- 既有 344 → 重寫 7 個 cap 測試（行為改變，數量持平或微增）+ 新增 `test_over_limit_reask.py` 單元 + 情境1/2/3 整合，**預期 `N passed`（N > 344）、0 failed**。
- Iron Law：宣告完成前主 agent 親跑此指令看 `passed`、`git branch --contains <SHA>` 驗落 `worktree-*`。

---

## 7. Commit 規範

worktree `worktree-over-limit-reask`，建議拆：
1. `feat(sales): add over-limit re-ask state-chain constants`（timing/shared/keywords）
2. `feat(sales): add over_limit_reask + over_limit_cancel_confirm helper`（新檔 + 單元測試）
3. `refactor(sales): funnel over-limit into re-ask loop`（_l2_l3_qty_followup + l2_l3_dialog + 重寫/新增整合測試）
4. `docs(code_map): list _over_limit_reask`（階段 3b）

- commit message：英文標題 + 繁中 body 可，結尾 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。
- `git add` **明列檔名**（禁 `-A`/`.`）。

---

## 8. 流程鳥瞰

```
顧客語句 → parse_products
   │
   ├─ Pass1 直接數量：in-range 即加 / 超量收 over_pending / 缺數量排 missing / at-cap skip
   │
   ├─ over_pending 非空 → over_limit_reask（合併，12s+2reset）
   │      ├ resolved → 全加入，續 Pass2
   │      ├ 客服 → service_confirm（暫停補償）→ yes 重 prompt / no=timeout
   │      ├ 否定 → over_limit_cancel_confirm（6s）→ cancel_overlimit=reenter / exit=exit_l1
   │      ├ reenter_timeout / reenter_cancel → caller speak「prefix+entry」continue
   │      └ exit_l1 → caller _dialog_exit_a 退 L1
   │
   └─ Pass2 missing 追問 → 答超量 funnel 進 over_limit_reask（單商品）→ 同上冒泡
```
