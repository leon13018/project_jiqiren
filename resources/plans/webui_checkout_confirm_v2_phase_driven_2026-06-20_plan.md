# WebUI 結帳確認卡片 v2（phase 驅動）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven / executing-plans，task-by-task。Steps 用 checkbox 追蹤。

**Goal:** 修 v1 bug——語音 /「沉默自動結帳」/「結帳意圖短語」觸發結帳確認時確認卡片不跳；改成機器人 emit `checkout_confirm` phase 驅動卡片，三種觸發皆生效。

**Architecture:** 後端在進結帳確認子狀態時發 `checkout_confirm` phase；前端 `applyState` 把它映成確認卡片 overlay，並**移除** v1 的前端本地旗號 `_awaitingConfirm`（回歸 live「觸控只送命令、狀態等 emit」哲學）。

**Tech Stack:** Python（sales 純 stdlib 可 pytest；models.py 為 Pi-only pydantic 不可 Windows import）；buildless JS（`node --check` + Pi by-ear）。

## Global Constraints

- **繁體中文**：新增註解 / 字串 / commit 繁中。
- **根因 / 設計**：見 spec `resources/specs/webui_checkout_confirm_card_2026-06-20_design.md` §v2 變更。
- **新 phase**：DisplayState 加 `"checkout_confirm"`（介於 ordering 與 checkout）。
- **emit 點**：`_dialog_checkout_confirm` 進入時 `io.display("checkout_confirm", dict(cart))`（`DialogIO.display` 既有 dialog_io.py:25；2-arg 呼叫，paid 預設 0，對齊 main_loop:602 既有 emit 風格）。
- **移除** `_awaitingConfirm`：app.js 全 7 處（grep 確認無遺漏）。
- **demo 不動**：demo 走 overlay（openConfirm/openCheckout/closeOverlay），非 WS，不受 phase 改動影響。
- **後端 transport 其餘零改**：`display.py`/`bus.py`/`app.py`/`server.py` phase 透傳，不動。
- **worktree**（`myProgram/` 下）：純 git worktree add 從 local HEAD + `EnterWorktree({path})`；收尾 `git -C` 或 ExitWorktree。**不用 `git add -A`**。commit 帶 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 執行治理

| Task | 檔 | 類型 | 審查 |
|---|---|---|---|
| 1 | `sales/states/l2_l3_dialog.py` + `tests/sales/test_states.py` | `.py` SDD | 三段 reviewer |
| 2 | `web/models.py` | `.py` SDD（Pi-only，ast.parse 驗） | 三段 reviewer（併 Task1） |
| 3 | `webui/app.js` | `.js` | 主 agent 審 + node check + Pi by-ear |

順序：Task 1 → 2 → 3，同一 worktree，各自 commit。

---

## Task 1: sales 發 `checkout_confirm` phase

**Files:**
- Modify: `myProgram/sales/states/l2_l3_dialog.py`（`_dialog_checkout_confirm` 進入處，現 ~731-734 行）
- Test: `tests/sales/test_states.py`（新增 1 測試）

**Interfaces:**
- Produces: `_dialog_checkout_confirm` 進入時呼叫 `io.display("checkout_confirm", dict(cart))`（若 `io.display` 非 None）。
- Consumes（既有）：`io.display`（`DialogIO.display`）、`L3_CHECKOUT_CONFIRM_TEMPLATE`、`_build_order_summary`。

- [ ] **Step 1: 寫 failing 測試**

在 `tests/sales/test_states.py` 末尾新增（`FakeCustomerInput` / `cart_module` 已 import）：
```python
# ============================================================
# L3-C-CONFIRM-PHASE（2026-06-20 v2：進結帳確認 emit checkout_confirm）
### Scenario: 進結帳語音確認子狀態 → emit display("checkout_confirm", cart) 讓前端跳卡片
# ============================================================

def test_checkout_confirm_emits_checkout_confirm_phase() -> None:
    """語音/自動/UI 三種結帳觸發都會經 _dialog_checkout_confirm；進入時須 emit
    checkout_confirm phase（前端靠此顯示確認卡片，非靠 UI 本地旗號）。"""
    display_calls: list = []
    cart = cart_module.new_cart()
    cart_module.add_item(cart, "冰紅茶", 1)
    # 「結帳」→ checkout_flow → _dialog_checkout_confirm（emit checkout_confirm）→「對」→ L4
    customer_input = FakeCustomerInput(["結帳", "對"])

    states.run_dialog(
        speak=lambda text: None,
        print_terminal=lambda text: None,
        read_customer_input=customer_input.read,
        cart=cart,
        think_count=0,
        opencv_disable=lambda: None,
        do_action=lambda *a, **k: None,
        display=lambda phase, c, paid=0: display_calls.append((phase, dict(c))),
    )

    phases = [p for (p, _c) in display_calls]
    assert "checkout_confirm" in phases, (
        f"進結帳確認應 emit checkout_confirm phase，實際：{phases}"
    )
    # emit 時 cart 應含商品（顧客看明細確認）
    cc = next((c for (p, c) in display_calls if p == "checkout_confirm"), None)
    assert cc == {"冰紅茶": 1}, f"checkout_confirm emit 的 cart 應含明細，實際：{cc}"
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `python -m pytest tests/sales/test_states.py::test_checkout_confirm_emits_checkout_confirm_phase -v`
Expected: FAIL（現無 checkout_confirm emit；phases 只有 ordering / 無）。
（若本機 `python` 無 pytest，用 `py -3.14 -m pytest`，見 v1 執行紀錄。）

- [ ] **Step 3: `_dialog_checkout_confirm` 加 emit**

`myProgram/sales/states/l2_l3_dialog.py`，把 `_dialog_checkout_confirm` 進入段（現 ~731-734）：
```python
    summary = _build_order_summary(cart)
    prompt = L3_CHECKOUT_CONFIRM_TEMPLATE.format(summary=summary)
    io.speak(prompt)
    unclear_count = 0
```
改為（在 speak 前 emit phase，讓卡片隨語音同時出現）：
```python
    summary = _build_order_summary(cart)
    prompt = L3_CHECKOUT_CONFIRM_TEMPLATE.format(summary=summary)
    # WebUI v2：進結帳確認 → emit checkout_confirm phase（此步在 dialog 機台狀態內，
    # machine 不會發 phase）；語音 / 沉默自動結帳 / UI 三種觸發皆經此 → 前端據此跳確認卡片。
    if io.display is not None:
        io.display("checkout_confirm", dict(cart))
    io.speak(prompt)
    unclear_count = 0
```

- [ ] **Step 4: 跑新測試確認 PASS + 全 sales 回歸**

Run: `python -m pytest tests/sales/ -v --tb=short`
Expected: 全 passed（含新測試；既有 confirm 行為不變）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/sales/states/l2_l3_dialog.py tests/sales/test_states.py
git commit -m "fix(sales): 進結帳確認 emit checkout_confirm phase（修語音/自動結帳不跳卡片）"
```

---

## Task 2: DisplayState 加 `checkout_confirm` phase

**Files:**
- Modify: `myProgram/web/models.py:15`

**Interfaces:**
- Produces: `DisplayState.phase` 接受 `"checkout_confirm"`。

> models.py 為 Pi-only（import pydantic，Windows 不可 import）→ **無 Windows pytest**；驗證用 `ast.parse` 語法 + Pi runtime。

- [ ] **Step 1: 改 Literal**

把 `myProgram/web/models.py:15`：
```python
    phase: Literal["standby", "ordering", "checkout", "thankyou"]
```
改為：
```python
    phase: Literal["standby", "ordering", "checkout_confirm", "checkout", "thankyou"]
```

- [ ] **Step 2: 語法驗證**

Run: `python -c "import ast; ast.parse(open('myProgram/web/models.py', encoding='utf-8').read()); print('models.py syntax OK')"`
Expected: `models.py syntax OK`。

- [ ] **Step 3: Commit**

```bash
git add myProgram/web/models.py
git commit -m "feat(web): DisplayState 加 checkout_confirm phase（結帳確認鏡像）"
```

---

## Task 3: 前端 phase 驅動確認卡片，移除 `_awaitingConfirm`

**Files:**
- Modify: `myProgram/webui/app.js`（5 處：field 142 / resetToWelcome 207 / applyState 276-279 / showConfirm 346 / bindEvents live 637-648）

**Interfaces:**
- Consumes（既有）：`applyState`、`renderVals`、`sendCommand`、overlay `"confirm"` + `ConfirmSheet`（v1 已建）。
- 移除：`App._awaitingConfirm`（全 7 處）。

- [ ] **Step 1: 移除 `_awaitingConfirm` field**

刪 `app.js:142`：
```js
  _awaitingConfirm: false,   // 已送 checkout、等機器人問「正確嗎」→ 顯示 [確認金額] affordance
```

- [ ] **Step 2: `resetToWelcome` 移除清旗號行**

`app.js` resetToWelcome（現 ~206-209），把：
```js
  resetToWelcome() {
    this._awaitingConfirm = false;                      // 清掉「確認金額」本地 affordance（若斷在結帳兩拍中途）
    this.setState({ standby: true, overlay: null });    // setState 內 render() → 顯示 Standby() 歡迎畫面
  },
```
改為：
```js
  resetToWelcome() {
    this.setState({ standby: true, overlay: null });    // setState 內 render() → 顯示 Standby() 歡迎畫面（overlay:null 一併收掉確認卡片）
  },
```

- [ ] **Step 3: `applyState` 映 checkout_confirm + 移除清旗號**

`app.js` applyState（現 273-280），把：
```js
  applyState(s) {
    this.state.cart = s.cart || {};
    this.state.standby = s.phase === "standby";
    this.state.overlay = s.phase === "checkout" ? "checkout" : s.phase === "thankyou" ? "thankyou" : null;
    this.state.paidTotal = s.paid || this.state.paidTotal;
    // 離開 ordering（機器人進 L4 / 退場 / standby）→ 清掉本地「確認金額」affordance，防殘留。
    if (s.phase !== "ordering") this._awaitingConfirm = false;
  },
```
改為：
```js
  applyState(s) {
    this.state.cart = s.cart || {};
    this.state.standby = s.phase === "standby";
    this.state.overlay = s.phase === "checkout_confirm" ? "confirm" : s.phase === "checkout" ? "checkout" : s.phase === "thankyou" ? "thankyou" : null;
    this.state.paidTotal = s.paid || this.state.paidTotal;
  },
```

- [ ] **Step 4: `showConfirm` 簡化為純 overlay**

`app.js:346`，把：
```js
      showConfirm: this.state.overlay === "confirm" || (this._live && this._awaitingConfirm),
```
改為：
```js
      showConfirm: this.state.overlay === "confirm",
```

- [ ] **Step 5: live bindEvents 改純送命令**

`app.js` live switch（現 637-648），把：
```js
        case "checkout":
          App.sendCommand({ type: "checkout" });
          App._awaitingConfirm = true; App.render();                       // 本地顯示「確認金額」affordance
          break;
        case "confirm":
          App.sendCommand({ type: "confirm" });
          App._awaitingConfirm = false;                                    // robot 進 L4 → emit checkout 接手畫面
          break;
        case "back":
          App.sendCommand({ type: "resume" });             // 返回購物車 → 機器人「繼續點餐」保留 cart
          App._awaitingConfirm = false; App.render();      // 立即關卡片回點餐畫面（cart 由既有鏡像保留）
          break;
```
改為（純送命令，卡片開關一律等機器人 emit phase——對齊 live「狀態等 emit」哲學）：
```js
        case "checkout": App.sendCommand({ type: "checkout" }); break;     // 機器人進確認 → emit checkout_confirm → 跳卡片
        case "confirm": App.sendCommand({ type: "confirm" }); break;       // 機器人進 L4 → emit checkout → QR 接替
        case "back": App.sendCommand({ type: "resume" }); break;           // 機器人繼續點餐 → emit ordering → 收卡片
```

- [ ] **Step 6: grep 確認 `_awaitingConfirm` 全清**

Run: `grep -n "_awaitingConfirm" myProgram/webui/app.js || echo "clean: no _awaitingConfirm left"`
Expected: `clean: no _awaitingConfirm left`。

- [ ] **Step 7: 語法驗證**

Run: `node --check myProgram/webui/app.js`
Expected: 無輸出。

- [ ] **Step 8: 人工自檢**

1. `applyState`：`checkout_confirm`→overlay `"confirm"`、`checkout`→`"checkout"`、`thankyou`→`"thankyou"`、其餘→null；無 `_awaitingConfirm`。
2. `showConfirm` 純 `overlay === "confirm"`（demo openConfirm 設 overlay；live applyState 設 overlay）。
3. live `checkout`/`confirm`/`back` 純 `sendCommand`、無本地狀態改動 / 無 render。
4. demo switch（checkout→openConfirm / confirm→openCheckout / back→closeOverlay）未動。
5. `ConfirmSheet` / `OrderSummary` / 預覽切換器「確認」（v1 已建）未動。

- [ ] **Step 9: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "fix(webui): 確認卡片改 checkout_confirm phase 驅動，移除 _awaitingConfirm 本地旗號"
```

---

## Pi by-ear 重驗（收尾後）

Pi `python3.11 -m myProgram --web` + 筆電連線：
- L3 講「**這樣就好了**」（或「結帳」/ 沉默 6 秒自動結帳）→ 機器人語音「…正確嗎？」**同時筆電跳確認卡片**。
- 卡片點「確認結帳」→ 機器人進 L4 → 轉 QR；點「返回購物車」→ 機器人「請繼續選購」→ 卡片收掉、cart 還在。
- demo（`?demo=1` / 點 UI 結帳鈕）行為不變。

---

## Self-Review

**1. Spec coverage（§v2）：** sales emit checkout_confirm → Task 1 ✓；models Literal → Task 2 ✓；app.js applyState 映射 + 移除 _awaitingConfirm + live 純送命令 + showConfirm 簡化 → Task 3 Step 1-5 ✓；demo 不動 → Task 3 Step 4 自檢 ✓；後端其餘零改 → Files 僅列 models.py ✓。
**2. Placeholder scan：** 每 step 確切 code + 指令 + 預期；models.py 無 Windows test 已明確改用 ast.parse（非 placeholder）。
**3. Type consistency：** phase 字串 `"checkout_confirm"`（Task1 emit ↔ Task2 Literal ↔ Task3 applyState 映射 ↔ Task1 測試斷言）四處一致；overlay `"confirm"`（applyState 產 ↔ showConfirm 消費 ↔ v1 ConfirmSheet）一致；`_awaitingConfirm` 全移除（Step 6 grep 守）。
