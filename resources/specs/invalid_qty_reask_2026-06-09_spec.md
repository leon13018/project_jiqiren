# 無效數量重問鏈 invalid_qty_reask — SDD spec（2026-06-09）

> WHAT 契約。HOW step-by-step 見 `resources/plans/invalid_qty_reask_2026-06-09_plan.md`。
> 本功能**一般化**前一輪 `over_limit_reask`（spec `over_limit_reask_2026-06-09_spec.md`）：把「超上限」與「數量為 0」統一成同一條重問鏈，per-product 帶 reason。對話狀態機領域記錄於收尾更新 skill `sales-dialog-design.md`。

---

## 1. 背景與動機

顧客講「0」這種無意義數量時，L2/L3 三條數量處理路徑行為不一致：

| 路徑 | qty=0 現行 | 問題 |
|---|---|---|
| 直接給（`resolve_and_add_products` Pass 1）| `add_item(.,0)` silent skip，但 `added_count += 1` | **假性「已加入購物車」**——cart 沒東西卻播「好的，已加入」 |
| 追問（`_qty_follow_up_sub_loop`）| 同上 silent skip + `return True`（accepted）| 同樣假性已加入 |
| 超量重問 loop（`_apply_quantities`）| `0 < qty` 不成立 → 留 pending、用**超量**文案重問 | 訊息錯（明明是 0、卻說「最多只能選購 N」）|

根因：`cart.add_item` 對 `qty <= 0` 設計為 silent skip（內部 invariant 防護），caller 卻在 skip 後仍當成功計數。

**訴求**：把「0 數量」比照「超上限」處理——進重問鏈問到合法數量才加入，**沿用 over_limit 的全部系統值**（budget 12s / 最多 2 reset / 二選一 6s），只是提示詞依「無效原因」不同。涵蓋三情境：
- **情境1**：問要買什麼 → 顧客「紅茶0杯」。
- **情境2**：顧客「紅茶」→ 系統追問幾瓶 → 顧客「0瓶」。
- **情境3**：問要買什麼 → 顧客「紅茶 刮刮樂0」（刮刮樂0、紅茶缺數量）。

**負數 out-of-scope**：`parse_quantity` 用 `re.findall(r"\d+")`，負號被忽略——「我要-1瓶」解析成 qty=1 正常加入，負數實際進不了系統；STT 也產不出負號。不加負號偵測（YAGNI）。

---

## 2. 設計核心 + 行為規約

### 2.1 一般化模型

把 `over_limit_reask` 鏈一般化為 **`invalid_qty_reask`**：`pending` 從 `list[str]` 改為 **`dict[str, str]`**（`product → reason`，`reason ∈ {"over_limit", "zero"}`，dict 保插入序）。loop 機制（12s budget / 最多 2 reset / 客服暫停補償 / 否定→二選一 / 亂答不重置 / 保守 default / control 往上傳）**完全沿用**，唯一差異：**prompt formatter 依 reason 分組**、**`_apply_quantities` 重新分類 reason**。

### 2.2 全套 rename（趁功能新、避免永久誤名；值不變）

| 舊 | 新 |
|---|---|
| 檔 `myProgram/sales/states/_over_limit_reask.py` | `_invalid_qty_reask.py` |
| `over_limit_reask` | `invalid_qty_reask` |
| `over_limit_cancel_confirm` | `invalid_qty_cancel_confirm` |
| `_format_over_limit_prompt` | `_format_invalid_qty_prompt` |
| `OVER_LIMIT_REASK_TIMEOUT` / `_MAX_RESETS` / `_CANCEL_CONFIRM_TIMEOUT`（timing）| `INVALID_QTY_REASK_TIMEOUT` / `INVALID_QTY_MAX_RESETS` / `INVALID_QTY_CANCEL_CONFIRM_TIMEOUT` |
| `OVER_LIMIT_REASK_SINGLE_TEMPLATE` / `_MULTI_TEMPLATE`（shared）| `INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE` / `INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE` |
| `OVER_LIMIT_UNCLEAR_PREFIX` | `INVALID_QTY_UNCLEAR_PREFIX` |
| `OVER_LIMIT_CANCEL_CONFIRM_PROMPT` | `INVALID_QTY_CANCEL_CONFIRM_PROMPT`（內容中性化，見 §2.5） |
| `OVER_LIMIT_TIMEOUT_REENTER_PREFIX` | `INVALID_QTY_TIMEOUT_REENTER_PREFIX`（內容不變） |
| `OVER_LIMIT_CANCEL_REENTER_PREFIX` | `INVALID_QTY_CANCEL_REENTER_PREFIX`（內容中性化） |
| `KEYWORDS_OVER_LIMIT_CANCEL_TRIGGER` | `KEYWORDS_INVALID_QTY_CANCEL_TRIGGER` |
| `KEYWORDS_OVER_LIMIT_CONTINUE(_STRICT_SHORT)` | `KEYWORDS_INVALID_QTY_CONTINUE(_STRICT_SHORT)` |
| `KEYWORDS_OVER_LIMIT_EXIT(_STRICT_SHORT)` | `KEYWORDS_INVALID_QTY_EXIT(_STRICT_SHORT)` |
| 測試 `test_over_limit_reask.py` | `test_invalid_qty_reask.py` |

> rename 為**純機械改名**（值 / 行為不變）→ 既有 407 測試 rename 後應仍全綠。

### 2.3 新增 zero 文案（`shared.py`）

```python
# 單/多商品共用（join 處理 1 vs 多）：
#   {items}   = 「冰紅茶0瓶」/「冰紅茶0瓶、刮刮樂0張」（per-product「{product}0{unit}」以「、」連）
#   {products}= 「冰紅茶」/「冰紅茶和刮刮樂」（_join_names）
INVALID_QTY_ZERO_TEMPLATE: str = "不好意思，系統不接受{items}這種數量，請重新說您想要的{products}的數量。"
```

### 2.4 prompt formatter（依 reason 分組）— `_format_invalid_qty_prompt(pending: dict, cart) -> str`

```python
zero_products = [p for p, r in pending.items() if r == "zero"]
over_products = [p for p, r in pending.items() if r == "over_limit"]
parts = []
if zero_products:
    items = "、".join(f"{p}0{PRODUCTS[p]['單位']}" for p in zero_products)
    parts.append(INVALID_QTY_ZERO_TEMPLATE.format(items=items, products=_join_names(zero_products)))
if over_products:
    if len(over_products) == 1:
        p = over_products[0]; unit = PRODUCTS[p]["單位"]
        remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)
        parts.append(INVALID_QTY_OVERLIMIT_SINGLE_TEMPLATE.format(product=p, remaining=remaining, unit=unit))
    else:
        products = _join_names(over_products)
        details = "、".join(f"{MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, p)} {PRODUCTS[p]['單位']}" for p in over_products)
        parts.append(INVALID_QTY_OVERLIMIT_MULTI_TEMPLATE.format(products=products, details=details))
return "".join(parts)
```
- **混合 reason**（一句裡有 0 也有超量，如「紅茶0刮刮樂9999」）→ zero 句 + over 句**串接成一個 speak**（各句以「。」自結）。
- over-limit 句的 single/multi 由 **over_products 數量**決定（非 total pending）。

### 2.5 「超量」字眼中性化（一般化後也涵蓋 zero）

```python
INVALID_QTY_CANCEL_CONFIRM_PROMPT: str = "請問您是想取消這些商品然後繼續交易，還是想直接退出交易？"
INVALID_QTY_CANCEL_REENTER_PREFIX: str = "好的已為您取消這些商品，"
INVALID_QTY_TIMEOUT_REENTER_PREFIX: str = "由於您沒回應購買數量，請重新進選購，"   # 不變（reason-agnostic）
INVALID_QTY_UNCLEAR_PREFIX: str = "不好意思，系統無法判斷您的回復。"                # 不變
```
> 已知微妙：case (4) 亂答 speak `UNCLEAR_PREFIX + formatted_prompt`；若 pending 含 zero-reason，formatted_prompt 以「不好意思，系統不接受…」開頭 → 出現「不好意思…不好意思…」輕微重複。屬「亂答 + zero pending」巢狀邊緣，**接受**（不為此拆 case，保持 loop 統一）。

### 2.6 `_apply_quantities(response, pending: dict, cart)` 重分類

```python
def _classify_into_pending(product, qty, pending, cart):
    remaining = MAX_QTY_PER_ITEM - cart_module.get_quantity(cart, product)
    if 0 < qty <= remaining:
        cart_module.add_item(cart, product, qty); del pending[product]
    elif qty == 0:
        pending[product] = "zero"
    else:  # qty > remaining
        pending[product] = "over_limit"

parsed = parse_products(response); parsed_names = {p for p, _ in parsed}
for product, qty in parsed:
    if product in pending and qty is not None:
        _classify_into_pending(product, qty, pending, cart)
# bare-number fallback（單 pending、response 無任何商品名 → 真 bare number 如「30」/「0」）
if len(pending) == 1 and not parsed_names and has_quantity(response):
    product = next(iter(pending))
    _classify_into_pending(product, parse_quantity(response), pending, cart)
```
- 重答有效 → add + del；重答仍 0 → reason 設 zero；重答仍超量 → reason 設 over_limit。**任一商品 reason 改變或仍 pending = 「答了數量但仍無效」→ 觸發 reset**（沿用既有：case (3) `has_quantity` 後若 `pending` 非空就 reset，最多 2 次）。`if not pending: resolved`。
- bare-number guard `not parsed_names` 沿用（防多 pending 時只報一名商品的數字誤套，over_limit 既有回歸測試守護）。

### 2.7 偵測點（qty==0 funnel 進鏈，鏡像超量）

**前置修正（2026-06-09b，user 核准）— `product_parser._parse_quantity_in_window` 透出明確 0**：原 `if n > 0` 守門使「紅茶0」window「0」回 `None`（被當缺數量 → 走追問，非重問鏈），Pass 1 的 `if qty == 0` 永不可達。改為比照 `nlu.parse_quantity` B16——arabic 全為 0 時回 0（非 None）：
```python
arabic_matches = re.findall(r"\d+", window)
if arabic_matches:
    for m in arabic_matches:
        n = int(m)
        if n > 0:
            return n
    return 0          # 明確 0（同 parse_quantity B16）；非「缺數量」
compound = _parse_compound_chinese(window)
if compound is not None and compound > 0:
    return compound
for char, value in CHINESE_DIGIT_MAP.items():
    if char in window:
        return value
return None
```
於是 `parse_products("紅茶0")` → `[(冰紅茶, 0)]`、`parse_products("紅茶 刮刮樂0")` → `[(冰紅茶, None), (刮刮樂, 0)]`，Pass 1 的 `if qty == 0` 可達。`test_product_parser.py` 無任何斷言 X0→None，回歸風險低；修正後與 `parse_quantity` 一致。

**`resolve_and_add_products` Pass 1**（`_l2_l3_qty_followup.py`）：
```python
invalid_pending = {}  # product -> reason（取代原 over_pending list）
for product, qty in products:
    if qty is None: missing.append(product); continue
    existing = cart_module.get_quantity(cart, product); remaining = MAX_QTY_PER_ITEM - existing
    unit = PRODUCTS[product]["單位"]
    if remaining <= 0:
        speak(f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加"); continue   # at-cap 不變
    if qty == 0:
        invalid_pending[product] = "zero"; continue          # 新
    if qty > remaining:
        invalid_pending[product] = "over_limit"; continue
    cart_module.add_item(cart, product, qty); added_count += 1
if invalid_pending:
    n = len(invalid_pending)
    control = invalid_qty_reask(invalid_pending, cart, speak, print_terminal, read_customer_input, speak_and_wait)
    if control == "resolved": added_count += n
    else: return added_count > 0, cancel_notices, control
# Pass 2 missing 追問（不變）
```

**`_qty_follow_up_sub_loop`**（has_quantity 分支）：
```python
existing = cart_module.get_quantity(cart, product); remaining = MAX_QTY_PER_ITEM - existing
if remaining <= 0:
    speak(f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加"); return False, None, None  # at-cap 不變
if qty == 0 or qty > remaining:
    reason = "zero" if qty == 0 else "over_limit"
    control = invalid_qty_reask({product: reason}, cart, speak, print_terminal, read_customer_input, speak_and_wait)
    if control == "resolved": return True, None, None
    if control == "exit_l1": return False, None, "exit_l1"
    return False, None, control
cart_module.add_item(cart, product, qty); return True, None, None
```

### 2.8 沿用 / 不動

- 計時值（12/2/6）、loop 主結構、`invalid_qty_cancel_confirm`（CONTINUE 先於 EXIT、保守 default）、客服暫停補償、否定→二選一、control 4 sentinel（resolved/reenter_timeout/reenter_cancel/exit_l1）、3 caller 處理（`l2_l3_dialog.py` exit_l1→`_dialog_exit_a`、reenter→speak prefix+entry）——**全沿用**，僅常數改名 + pending 改 dict。
- `cart.add_item` 的 qty≤0 silent skip 防護**不動**（內部 invariant 保留；只是 caller 不再依賴它吃掉 0，改在進 cart 前攔成 invalid_pending）。
- `MAX_QTY_PER_ITEM`、at-cap skip 行為、`do_action` / `main.py` wire-up、`_cancel_confirm`/`_service_confirm`、C-2/L4 — 全不動。

---

## 3. 改檔範圍（高層；step-by-step 見 plan）

| 檔 | 改動 | 估計 |
|---|---|---|
| `myProgram/sales/constants/timing.py` | 3 常數改名（值不變）+ `__all__` | rename |
| `myProgram/sales/constants/shared.py` | 6 常數改名 + 2 個內容中性化 + **新增** `INVALID_QTY_ZERO_TEMPLATE` + `__all__` | ~改名+3 行 |
| `myProgram/sales/constants/keywords.py` | 5 keyword 集改名 + `__all__` | rename |
| `myProgram/sales/product_parser.py` | `_parse_quantity_in_window` 明確 0 回 0（§2.7 前置修正，2026-06-09b 加） | ~3 行 |
| `myProgram/sales/states/_over_limit_reask.py` → `_invalid_qty_reask.py` | 改名 + pending→dict + formatter 分組 + `_apply_quantities` 重分類 + zero | 核心 |
| `myProgram/sales/states/_l2_l3_qty_followup.py` | import 改名 + Pass1 invalid_pending(dict) + funnel reason | ~30 行 |
| `myProgram/sales/states/l2_l3_dialog.py` | import 改名（reenter prefix）；control 邏輯不變 | rename |
| `tests/sales/test_over_limit_reask.py` → `test_invalid_qty_reask.py` | 改名 + 擴充 zero/mixed/funnel/假性加入回歸 | 改名+新增 |
| `tests/sales/test_states.py` | 既有 over-limit 整合測試改名引用 + 新增 zero 情境1/2/3 + 假性加入回歸 | 新增 |
| `tests/sales/test_constants.py` | 常數斷言改名 + zero template 斷言 | rename+1 |
| `myProgram/sales/states/.claude/code_map.md` | rename 條目 | 1 行 |
| skill `reference/sales-dialog-design.md` | 段落 rename + 加 zero（收尾） | doc |

---

## 4. Out of scope

- **負數**（`-1瓶` parser 解成 1，進不來；不加偵測）。
- **中文「零」**（不在 CHINESE_DIGIT_MAP、`has_quantity` 為 False → 走缺數量追問，非本題）。
- `MAX_QTY_PER_ITEM` 值、`cart.add_item` qty≤0 skip 防護、at-cap skip 行為、`do_action`/`main.py`、`_cancel_confirm`/`_service_confirm`、C-2/L4。
- over_limit 既有行為**不得回歸**（rename 後逐字等價，only reason-tag）。

---

## 5. 規範與參考

- 派 **sales-coder**（frontmatter 預載 karpathy-guidelines + TDD）。
- base：前一輪 `over_limit_reask`（已 merge，commit 鏈 e758077..3862d6a + df9e5c8）；本輪一般化之。
- reuse：`_cancel_confirm.is_cancel_intent`、`_service_confirm.service_confirm`、`nlu.{has_quantity,parse_quantity,classify_intent,contains_any,equals_strict_short}`、`product_parser.parse_products`、`cart_module.{add_item,get_quantity}`、`PRODUCTS`、`MAX_QTY_PER_ITEM`。
- 領域鐵則：skill `sales-dialog-design.md`「confirm ambiguous 保守」「跨層 helper callback 注入」「即時提交無 staging」。

---

## 6. 測試指令 + 預期結果

```
python -m pytest tests/sales/
```
- rename 後既有 407 應全綠（純改名）；加 zero 行為後新增 zero 單/多/混合/followup-funnel/假性加入回歸 + 情境1/2/3 整合，**預期 `N passed`（N > 407）、0 failed**。
- Iron Law：宣告完成前主 agent 親跑、`git branch --contains <SHA>` 驗落 worktree。

---

## 7. Commit 規範

worktree `worktree-invalid-qty-reask`，建議拆：
1. `refactor(sales): rename over_limit_reask to invalid_qty_reask`（純機械改名，全檔 + tests + docs；跑綠 407）
2. `refactor(sales): generalize reask pending to per-product reason`（pending→dict + formatter 分組 + _apply 重分類 + zero template + 中性化文案；over-limit 行為不變）
3. `feat(sales): re-ask on zero quantity across L2/L3 paths`（Pass1 + funnel 偵測 qty==0 + zero 情境/假性加入回歸測試）
4. `docs: document invalid_qty_reask generalization`（code_map + sales-dialog-design）

- commit message 英文標題 + 繁中 body 可，結尾 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。
- `git add` **明列檔名**（禁 `-A`/`.`）。

---

## 8. 流程鳥瞰

```
顧客語句 → parse_products
   │ Pass1 直接數量：in-range 即加 / qty==0 → invalid_pending[zero] / 超量 → invalid_pending[over_limit] / 缺數量 → missing / at-cap skip
   │
   ├ invalid_pending 非空 → invalid_qty_reask(dict{product:reason}, 12s+2reset)
   │     prompt 依 reason 分組：zero「不接受 X0Y 這種數量」+ over「最多只能選購 N」（混合串接）
   │     重答：valid→add+del / 仍0→reason=zero / 仍超→reason=over_limit；空→resolved
   │     否定→二選一(6s,中性「取消這些商品」) / 客服→暫停補償 / 亂答→不重置
   │     resolved→全加入續 Pass2；reenter_*/exit_l1→caller speak prefix+entry / 退 L1
   │
   └ Pass2 missing 追問 → 答 0 或超量 → funnel invalid_qty_reask({product:reason}) → 同上冒泡
```
