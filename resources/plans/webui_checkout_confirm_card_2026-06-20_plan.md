# WebUI 結帳前確認卡片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 點「結帳」後先彈確認卡片（商品明細＋總計＋確認/返回），確認後才出 QR；demo / live 兩模式一致；live 為機器人加「繼續點餐（保留購物車）」路徑配合語音確認。

**Architecture:** 三層改動——(C) `sales/states/l2_l3_dialog.py` 在 `_dialog_checkout_confirm` 加 `KG_C2_CONTINUE` 分支回新 sentinel `"continue_keep_cart"`、`checkout_flow` 收到此 sentinel 時 speak `L3_C2_CONTINUE_ACK` 並 `return None`（不清 cart、回主迴圈）；(B) `web/commands.py` 加 `{type:"resume"}` → token `"繼續"`；(A) `webui/app.js` 加 `confirm` overlay + `ConfirmSheet` + `OrderSummary` 共用 helper + 事件流。後端 `web/{app,display,bus,server}.py` 與 DisplayState phase **零改**。

**Tech Stack:** Python 3.11（sales / web，純 stdlib transport，pytest 可在 Windows 跑）；buildless JS（無打包 / 無測試框架，`node --check` + 筆電 by-eye 驗收）。

## Global Constraints

- **繁體中文**：所有新增註解 / 字串 / commit message 繁中。
- **設計契約**：`resources/specs/webui_checkout_confirm_card_2026-06-20_design.md`（WHAT；本 plan 是 HOW）。
- **重用既有文案**：「返回購物車繼續點餐」ack 直接重用 `L3_C2_CONTINUE_ACK = "好的，請繼續選購，請問還要買什麼呢？"`（`l3_text.py:99`，`l2_l3_dialog.py:65` 已 import）——**不新增 constant**（YAGNI；免動 `test_constants`）。
- **重用既有 keyword**：`KG_C2_CONTINUE`（含 strict-short「繼續」，`l2_l3_dialog.py:73` 已 import）——**零新 keyword / 零新 import**。
- **命令名**：前端送 `{type:"resume"}`；transport 映射 token **`"繼續"`**。
- **新 sentinel**：`_dialog_checkout_confirm` 回 `"continue_keep_cart"`（既有四態 + 此一態）。
- **後端零改**：不新增 DisplayState phase（維持 `standby/ordering/checkout/thankyou`）；confirm 由前端本地 `_awaitingConfirm` 驅動。
- **worktree**：三檔皆在 `myProgram/` 下 → 全程在同一 worktree。**不用 `git add -A`**（明列檔名）。commit 帶 `Co-Authored-By: Claude <Model Tier> <noreply@anthropic.com>`。
- **不動 vendor / 不在 Windows 裝依賴 / 不 import vendor SDK**（紅線）。

## 執行治理（dispatch / review 路徑）

| Task | 檔 | 類型 | 實作者 | 審查 |
|---|---|---|---|---|
| 1 | `sales/states/l2_l3_dialog.py` + `tests/sales/test_states.py` | `.py` → **觸發 SDD** | sales-coder | 三段：spec-reviewer + code-quality-reviewer |
| 2 | `web/commands.py` + `tests/web/test_commands.py` | `.py` → **觸發 SDD** | sales-coder | 三段（可與 Task 1 同一輪 reviewer 合審） |
| 3 | `webui/app.js` | `.js`（中型）→ dispatch「中小以上必派 sales-coder，不論檔案類型」 | sales-coder | 非 `.py` 不走三段；主 agent Read 對照 + 筆電 by-eye |

> 順序：Task 1（語意基礎）→ Task 2（token 接通）→ Task 3（前端）。三 Task 同一 worktree、各自 commit。

---

## Task 1: Sales 對話「繼續點餐」路徑

**Files:**
- Modify: `myProgram/sales/states/l2_l3_dialog.py`（`_dialog_checkout_confirm` 加分支 ~758 行後；`checkout_flow` 加分支 ~358 行後；兩處 docstring 補述）
- Test: `tests/sales/test_states.py`（新增 2 測試）

**Interfaces:**
- Produces: `_dialog_checkout_confirm(io, cart)` 新增回傳值 `"continue_keep_cart"`（顧客在結帳確認講「繼續」keyword）。`checkout_flow()` 收到 `"continue_keep_cart"` → speak `L3_C2_CONTINUE_ACK` + `return None`（不清 cart）。
- Consumes（既有）：`KG_C2_CONTINUE.matches(response)`、`L3_C2_CONTINUE_ACK`、`self.io.speak`、`cart_module`。

- [ ] **Step 1: 寫 failing 測試（主迴圈 path + C-2 path）**

在 `tests/sales/test_states.py` 末尾新增（`FakeCustomerInput` 與 `L3_C2_CONTINUE_ACK` 已於檔頭 import）：

```python
# ============================================================
# L3-C-CONFIRM-CONTINUE（2026-06-20 加：結帳確認卡片「返回購物車」）
### Scenario: 結帳確認子狀態顧客講「繼續」→ 保留 cart、回主迴圈續點餐
# ============================================================

def test_l3_checkout_confirm_continue_keeps_cart_and_resumes() -> None:
    """主迴圈結帳 path：確認時「繼續」→ speak L3_C2_CONTINUE_ACK、cart 不清、回主迴圈；
    再次「結帳」→「對」可正常進 L4（證明 cart 完整保留 + 重入迴圈）。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 結帳 → confirm → 繼續（返回）→ 結帳 → 對（yes）→ L4
    customer_input = FakeCustomerInput(["結帳", "繼續", "結帳", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_C2_CONTINUE_ACK in speak_calls, (
        f"確認時講「繼續」應 speak L3_C2_CONTINUE_ACK，實際：{speak_calls}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"「繼續」不應清 cart，實際：{dict(cart)}"
    )
    assert next_state == "L4", f"後續再結帳確認應進 L4，實際：{next_state!r}"


def test_c2_checkout_confirm_continue_keeps_cart() -> None:
    """C-2 path（silent timeout → confirm）：確認時「繼續」→ 同樣保留 cart、回主迴圈。"""
    speak_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # None → DyC 第一段；None → C-2 第二段 timeout → confirm；繼續 → 返回；結帳 → 對 → L4
    customer_input = FakeCustomerInput([None, None, "繼續", "結帳", "對"])

    next_state, _ = states.run_dialog(
        speak=lambda text: speak_calls.append(text),
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
    )

    assert L3_C2_CONTINUE_ACK in speak_calls, (
        f"C-2 confirm 講「繼續」應 speak L3_C2_CONTINUE_ACK，實際：{speak_calls}"
    )
    assert cart_module.get_quantity(cart, "冰紅茶") == 1, (
        f"C-2「繼續」不應清 cart，實際：{dict(cart)}"
    )
    assert next_state == "L4", f"後續再結帳確認應進 L4，實際：{next_state!r}"
```

> 若 `cart_module.get_quantity` 簽名不符（sales-coder 先 grep `myProgram/sales/cart.py` 確認），改用等價斷言 `dict(cart) == {"冰紅茶": 1}`。

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `python -m pytest tests/sales/test_states.py::test_l3_checkout_confirm_continue_keeps_cart_and_resumes tests/sales/test_states.py::test_c2_checkout_confirm_continue_keeps_cart -v`
Expected: FAIL（現「繼續」在 confirm 內走 unclear path → 達上限清 cart，cart 變空 / next_state 非 L4）。

- [ ] **Step 3: `_dialog_checkout_confirm` 加 CONTINUE 分支**

在 `myProgram/sales/states/l2_l3_dialog.py` 的 `_dialog_checkout_confirm` 內，`if KG_CONFIRM_YES.matches(response): return "yes"`（~757-758 行）**之後**、`unclear_count += 1`（~759 行）**之前**插入：
```python
        # 2026-06-20：結帳確認卡片「返回購物車」→ 顧客講「繼續」（KG_C2_CONTINUE strict-short）
        # → 保留 cart、回主迴圈續點餐（沿用 C-2 CONTINUE 語意，零新 keyword）
        if KG_C2_CONTINUE.matches(response):
            return "continue_keep_cart"
```
並在該函式 docstring 的 Returns 區塊（~721-729 行）補一行：
```python
        "continue_keep_cart" — 顧客在 confirm 內講「繼續」（KG_C2_CONTINUE）；caller 保留 cart、回主迴圈
```

- [ ] **Step 4: `checkout_flow` 處理新 sentinel**

在 `checkout_flow`（~342-361 行）的 `if result == "cancel_to_l1": return self.exit_a()`（~356-358 行）**之後**、`_handle_checkout_confirm_result(...)`（~359-360 行）**之前**插入：
```python
        if result == "continue_keep_cart":
            # 顧客在結帳確認卡片按「返回購物車」→ 不清 cart、回主迴圈繼續點餐
            self.io.speak(L3_C2_CONTINUE_ACK)
            return None
```
並把 docstring（~343-348 行）對應補一行說明 `"continue_keep_cart" → speak ack + return None（不清 cart）`。

> `_handle_checkout_confirm_result` 的 `else: raise AssertionError` 不會收到 `"continue_keep_cart"`（已在 caller 攔截）→ **無需改**該 helper。

- [ ] **Step 5: 跑新測試確認 PASS**

Run: `python -m pytest tests/sales/test_states.py::test_l3_checkout_confirm_continue_keeps_cart_and_resumes tests/sales/test_states.py::test_c2_checkout_confirm_continue_keeps_cart -v`
Expected: 2 passed。

- [ ] **Step 6: 跑全 sales 回歸（守既有 confirm 行為）**

Run: `python -m pytest tests/sales/ -v --tb=short`
Expected: 全 passed（既有 yes/no/timeout/cancel/亂答上限 confirm 測試不變；Stop hook 亦守）。

- [ ] **Step 7: Commit**

```bash
git add myProgram/sales/states/l2_l3_dialog.py tests/sales/test_states.py
git commit -m "feat(sales): 結帳確認加「繼續點餐」路徑（返回購物車保留 cart）"
```

---

## Task 2: Transport `resume` 命令 → 「繼續」token

**Files:**
- Modify: `myProgram/web/commands.py`（加 `_RESUME_TOKEN` 常數 ~17 行；`to_token` 加 `resume` 分支 ~39 行後）
- Test: `tests/web/test_commands.py`（新增 2 測試）

**Interfaces:**
- Produces: `to_token({"type": "resume"})` → `"繼續"`。
- Consumes（既有）：`to_token` dispatch 結構、`PRODUCTS`（不變）。

- [ ] **Step 1: 寫 failing 測試**

在 `tests/web/test_commands.py` 末尾新增：
```python
def test_resume_maps_to_continue_token():
    assert to_token({"type": "resume"}) == "繼續"


def test_resume_token_matches_c2_continue_keyword():
    # 守 token 語意：resume 產出的字串須被 sales C-2 CONTINUE keyword group 命中
    # （結帳確認卡片「返回購物車」→ _dialog_checkout_confirm 走 continue_keep_cart）
    from myProgram.sales.constants import KG_C2_CONTINUE
    assert KG_C2_CONTINUE.matches(to_token({"type": "resume"}))
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `python -m pytest tests/web/test_commands.py::test_resume_maps_to_continue_token tests/web/test_commands.py::test_resume_token_matches_c2_continue_keyword -v`
Expected: FAIL（`resume` 未知 → `to_token` 回 None）。

- [ ] **Step 3: `commands.py` 加 resume 映射**

在 `myProgram/web/commands.py` 的 `_CONFIRM_TOKEN = "正確"`（~17 行）**之後**插入：
```python
# 結帳確認卡片「返回購物車」→ 顧客「繼續」意圖（對齊 sales KG_C2_CONTINUE strict-short「繼續」）。
_RESUME_TOKEN = "繼續"
```
在 `to_token` 內 `if ctype == "confirm": return _CONFIRM_TOKEN`（~38-39 行）**之後**插入：
```python
    if ctype == "resume":
        return _RESUME_TOKEN
```

- [ ] **Step 4: 跑測試確認 PASS + web 回歸**

Run: `python -m pytest tests/web/ -v --tb=short`
Expected: 全 passed（含新 2 測試 + 既有 commands/bus/display）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/web/commands.py tests/web/test_commands.py
git commit -m "feat(web): resume 觸控命令 → 繼續 token（結帳卡片返回購物車）"
```

---

## Task 3: 前端結帳前確認卡片（`webui/app.js`）

**Files:**
- Modify: `myProgram/webui/app.js`（新增 `OrderSummary` / `ConfirmSheet`；`App.openConfirm`；`renderVals.showConfirm`；`render()` 掛載；`CheckoutSheet` 改用 `OrderSummary`；`CartInner` 移除就地確認按鈕；`bindEvents` demo/live 事件；demo 預覽切換器加「確認」）

**Interfaces:**
- Produces: `OrderSummary(v)`（商品明細列 + 總計，回 HTML 字串）；`ConfirmSheet(v)`（確認卡片 HTML）；`App.openConfirm()`（設 `overlay:"confirm"`）。
- Consumes（既有）：`Button` / `IconButton` / `esc`、`v.cartRows` / `v.totalLabel` / `v.checkoutLabel`、`App._live` / `App._awaitingConfirm` / `App.sendCommand` / `App.setState` / `App.openCheckout` / `App.closeOverlay`。

- [ ] **Step 1: 新增 `OrderSummary(v)` 共用 helper**

在 `CheckoutSheet(v)`（~488 行）**之前**插入（明細列 + 總計，搬自 `CheckoutSheet` 既有 `line` + 總計區塊，供兩卡共用）：
```js
// 商品明細列 + 總計（ConfirmSheet 與 CheckoutSheet 共用，消除重複）
function OrderSummary(v) {
  const line = (l) => `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 0;border-bottom:0.5px solid var(--separator);">
    <span style="font-size:15px;">${esc(l.name)} <span style="color:var(--text-secondary);font-variant-numeric:tabular-nums;">× ${l.qty}</span></span>
    <span style="font-family:var(--font-display);font-weight:700;font-variant-numeric:tabular-nums;">${l.lineLabel}</span></div>`;
  return `<div style="display:flex;flex-direction:column;margin:8px 0 2px;border-top:0.5px solid var(--separator);">${v.cartRows.map(line).join("")}</div>
    <div style="display:flex;align-items:baseline;justify-content:space-between;padding:14px 0 18px;">
      <span style="font-family:var(--font-display);font-size:18px;font-weight:700;">總計</span>
      <span style="font-family:var(--font-display);font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;">${v.totalLabel}</span>
    </div>`;
}
```

- [ ] **Step 2: `CheckoutSheet` 改用 `OrderSummary`（DRY）**

把 `CheckoutSheet` 內的明細 `line` 定義 + 明細 div + 總計 div（~489-491 行的 `const line=...` 與 ~503-507 行兩個區塊）替換為單行 `${OrderSummary(v)}`。即 `CheckoutSheet` 開頭刪掉 `const line = (l) => ...;` 那行（QR 的 `const qr = ...` 保留），中段：
```js
      <div style="display:flex;flex-direction:column;margin:8px 0 2px;border-top:0.5px solid var(--separator);">${v.cartRows.map(line).join("")}</div>
      <div style="display:flex;align-items:baseline;justify-content:space-between;padding:14px 0 18px;">
        <span style="font-family:var(--font-display);font-size:18px;font-weight:700;">總計</span>
        <span style="font-family:var(--font-display);font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;">${v.totalLabel}</span>
      </div>
```
換成：
```js
      ${OrderSummary(v)}
```

- [ ] **Step 3: 新增 `ConfirmSheet(v)`**

在 `CheckoutSheet(v)` 之後插入（卡片 chrome 對齊 CheckoutSheet；遮罩/X/兩鈕一律 `back` 表示「返回」，`confirm` 表示「確認」；無 `close`——dismiss 語意統一走 `back`）：
```js
// 結帳前確認卡片：商品明細 + 總計 + 確認結帳 / 返回購物車。
// 遮罩、X、返回鈕統一 act="back"（demo→關卡片回購物車；live→送 resume 繼續點餐）。
function ConfirmSheet(v) {
  return `<div class="wf-fade" data-act="back" style="position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;
    padding:24px;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);">
    <div class="wf-sheet" data-act="stop" style="width:min(560px,100%);max-height:90vh;overflow:auto;background:var(--glass-tint-thick);
      backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));-webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
      border:0.5px solid var(--glass-border);border-radius:var(--radius-2xl);box-shadow:var(--glass-shadow-raised);padding:22px 26px 30px;color:var(--text-primary);">
      <div style="width:40px;height:5px;border-radius:999px;background:var(--text-quaternary);margin:0 auto 18px;"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
        <h3 style="margin:0;font-family:var(--font-display);font-size:24px;font-weight:700;letter-spacing:-0.3px;">請確認訂單</h3>
        ${IconButton({ icon: "ph ph-x", label: "返回購物車", act: "back" })}
      </div>
      <p style="margin:2px 0 0;font-size:14px;color:var(--text-secondary);">請確認以下餐點與金額，確認後將顯示付款 QR 條碼。</p>
      ${OrderSummary(v)}
      <div style="display:flex;flex-direction:column;gap:10px;">
        ${Button({ label: "確認結帳", icon: "ph-bold ph-check", variant: "primary", size: "lg", block: true, act: "confirm" })}
        ${Button({ label: "返回購物車", icon: "ph-bold ph-arrow-left", variant: "glass", size: "lg", block: true, act: "back" })}
      </div>
    </div>
  </div>`;
}
```

- [ ] **Step 4: `App.openConfirm()` + `renderVals.showConfirm` + `render()` 掛載**

(a) 在 `App` 的 `openCheckout() { this.setState({ overlay: "checkout" }); },`（~230 行）**之前**插入：
```js
  openConfirm() { this.setState({ overlay: "confirm" }); },
```
(b) 在 `renderVals` 的 `showCheckout: this.state.overlay === "checkout",`（~344 行）**之前**插入：
```js
      showConfirm: this.state.overlay === "confirm" || (this._live && this._awaitingConfirm),
```
並**移除**已不再使用的 `awaitingConfirm: this._awaitingConfirm,`（~350 行；CartInner 改後成 dead，`showConfirm` 用的是實例欄位 `this._awaitingConfirm` 而非此 copy）。
(c) 在 `render()` 的 `${v.showCheckout ? CheckoutSheet(v) : ""}`（~363 行）**之前**插入：
```js
      ${v.showConfirm ? ConfirmSheet(v) : ""}
```

- [ ] **Step 5: `CartInner` 永遠顯示「結帳」按鈕（移除就地確認）**

把 `CartInner` 內（~460-462 行）：
```js
        ${v.awaitingConfirm
          ? Button({ label: "確認金額正確", icon: "ph-bold ph-check", variant: "primary", size: "lg", block: true, act: "confirm" })
          : Button({ label: v.checkoutLabel, icon: "ph-bold ph-qr-code", variant: "primary", size: "lg", block: true, act: "checkout" })}
```
換成：
```js
        ${Button({ label: v.checkoutLabel, icon: "ph-bold ph-qr-code", variant: "primary", size: "lg", block: true, act: "checkout" })}
```

- [ ] **Step 6: `bindEvents` demo 分支事件**

把 demo switch 內 `case "checkout": App.openCheckout(); break;`（~626 行）替換為：
```js
      case "checkout": App.openConfirm(); break;
      case "confirm": App.openCheckout(); break;
      case "back": App.closeOverlay(); break;
```
（`close` case 保留原樣供 `CheckoutSheet` 用。）

- [ ] **Step 7: `bindEvents` live 分支事件**

在 live switch 的 `case "confirm": ... break;`（~612-615 行）**之後**插入：
```js
        case "back":
          App.sendCommand({ type: "resume" });             // 返回購物車 → 機器人「繼續點餐」保留 cart
          App._awaitingConfirm = false; App.render();      // 立即關卡片回點餐畫面（cart 由既有鏡像保留）
          break;
```
（`case "confirm"` 維持原樣**不加 render** —— 不 render 則確認卡片留到機器人 emit `checkout` phase 由 QR 卡直接接替，無「點餐頁閃一下」。）

- [ ] **Step 8: demo 預覽切換器加「確認」狀態**

(a) `renderVals` 的 `currentView`（~330 行）把 `... : this.state.overlay === "checkout" ? "checkout"` 前面加上 confirm 判斷：
```js
    const currentView = this.state.standby ? "standby" : this.state.overlay === "confirm" ? "confirm" : this.state.overlay === "checkout" ? "checkout" : this.state.overlay === "thankyou" ? "placed" : (count === 0 ? "empty" : "filled");
```
(b) `reviewOptions`（~331 行）在 `["checkout", "結帳"]` 之前加 `["confirm", "確認"]`：
```js
    const reviewOptions = [["filled", "含商品"], ["empty", "空購物車"], ["confirm", "確認"], ["checkout", "結帳"], ["placed", "完成"], ["standby", "待機"]].map((...) => {
```
(c) `setView`（~250-256 行）在 `else if (v === "checkout") ...` **之前**加：
```js
    else if (v === "confirm") this.setState((s) => ({ cart: Object.keys(s.cart).length ? s.cart : { bingcha: 2, guagua: 1 }, overlay: "confirm", standby: false }));
```

- [ ] **Step 9: 語法驗證**

Run（worktree 內）：`node --check myProgram/webui/app.js`
Expected: 無輸出（語法 OK）。

- [ ] **Step 10: 程式碼自檢（無 JS 測試框架）**

人工核對：
1. `OrderSummary` 被 `ConfirmSheet` 與 `CheckoutSheet` 共用；`CheckoutSheet` 已無重複的 `line` / 總計區塊（QR 區塊保留）。
2. `ConfirmSheet` 遮罩 `data-act="back"` + 內層 `data-act="stop"`；X / 返回鈕 / 遮罩皆 `back`；確認鈕 `confirm`。
3. `render()` 同時最多一張卡（`showConfirm` 與 `showCheckout` 互斥：demo overlay 單值；live `_awaitingConfirm`(ordering 期) 與 `checkout` phase 時間互斥）。
4. demo：`checkout→openConfirm`、`confirm→openCheckout`、`back→closeOverlay`（cart 不變）。
5. live：`checkout`→送 checkout + `_awaitingConfirm=true`（既有）顯示卡片；`confirm`→送 confirm + `_awaitingConfirm=false`（不 render，待 QR 接替）；`back`→送 resume + `_awaitingConfirm=false` + render。
6. `CartInner` 永遠是「結帳」鈕；`renderVals` 無殘留 `awaitingConfirm` dead 欄位。
7. `?demo=1` 預覽切換器多「確認」狀態，live（`showReview=!_live`）不顯示切換器。

- [ ] **Step 11: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "feat(webui): 結帳前確認卡片（明細＋總計＋確認/返回），demo/live 統一"
```

---

## Pi / 筆電 by-eye 驗收（worktree 收尾後，非 code）

收尾 merge/push + sync Pi 後：

**demo（`?demo=1`，筆電本機）：**
- 點「結帳」→ 彈確認卡片（明細 + 總計 + 確認結帳 / 返回購物車），**不直接出 QR**。
- 點「確認結帳」→ 出 QR 掛碼卡 → 我已完成付款 → 謝謝惠顧。
- 點「返回購物車」（或 X / 點遮罩）→ 關卡片、回購物車（明細完整）。
- 預覽切換器「確認」→ 正確顯示確認卡片。

**live（Pi `python3.11 -m myProgram --web` + 筆電連線）by-ear + by-eye：**
- 點「結帳」→ 機器人語音「您即將結帳，總共…正確嗎？」+ 筆電彈確認卡片。
- 點「返回購物車」→ 機器人 speak「好的，請繼續選購…」+ 筆電卡片關閉回點餐、**cart 還在**、可繼續加單。
- 點「確認結帳」→ 機器人進 L4 → 筆電卡片接替為 QR 掛碼卡。

> 此驗收列入 worktree 收尾後的 pineedtodo（Pi 端操作）/ 口頭請使用者驗（無 JS 自動測試可代替）。

---

## Self-Review

**1. Spec coverage：**
- design §A 前端 confirm overlay + ConfirmSheet + OrderSummary + 事件 + 移除就地確認 + 預覽「確認」→ Task 3 Step 1-8 ✓
- design §B `resume`→「繼續」token → Task 2 ✓
- design §C `_dialog_checkout_confirm` CONTINUE 分支 + `checkout_flow` 不清 cart + 重用 `L3_C2_CONTINUE_ACK` → Task 1 Step 3-4 ✓
- design §D 後端零改 → Files 未列 web/{app,display,bus,server}.py ✓
- design §E 測試（web/sales pytest + app.js by-eye + Pi by-ear）→ Task 1 Step 5-6 / Task 2 Step 4 / Task 3 Step 9-10 + 驗收段 ✓
- design §F 文案（請確認訂單 / 確認結帳 / 返回購物車）→ Task 3 Step 3 ✓
- design「兩 call site（主迴圈 / C-2）皆保留 cart」→ Task 1 兩測試各覆蓋 ✓

**2. Placeholder scan：** 無 TBD / 「implement later」；每 code step 給確切 code + 確切指令 + 預期輸出。唯一條件式（`get_quantity` 簽名 fallback）已給明確替代斷言，非 placeholder。

**3. Type consistency：** sentinel `"continue_keep_cart"`（Task 1 Step 3 產生 ↔ Step 4 消費 ↔ 兩測試斷言行為）一致；token `"繼續"`（Task 2 `_RESUME_TOKEN` ↔ Task 1 `KG_C2_CONTINUE` 命中 ↔ Task 2 Step 1 第二測試守）一致；`OrderSummary`（Step 1 定義 ↔ Step 2/3 呼叫）、`openConfirm` / `showConfirm` / `overlay:"confirm"` / act `confirm`·`back`（Step 4-8 全程同名）一致；命令 `{type:"resume"}`（app.js Step 7 送 ↔ commands Step 3 接）一致。
