# WebUI 結帳前確認卡片 設計（Design Spec）

**日期：** 2026-06-20
**狀態：** 設計已與使用者敲定 → 轉 writing-plans
**對應：** 前端 webui Phase 0+1+2 ✅（`roadmaps/html_ui_plan.md`）；本案在「結帳 → QR」之間插入一張**確認卡片**，配合機器人語音的結帳確認環節。橫跨前端 / transport / sales 對話三層。

---

## 目標（Goal）

點「結帳」後，先彈出一張**商品明細＋價格確認卡片**（兩鈕：確認結帳 / 返回購物車），**確認後才出 QR 掛碼卡**——而非現在直接彈掃碼視窗。讓畫面節奏對齊機器人語音「您即將結帳，總共 X，正確嗎？」的確認環節。

**現況問題**：
- **demo 模式**（`?demo=1`）：點結帳 → `openCheckout()` → 直接 `CheckoutSheet`（內含 QR），**沒有確認步驟**。
- **live 模式**（機器人 WS 驅動）：點結帳 → 送 `checkout` 命令 + 購物車側欄就地換成「確認金額正確」按鈕（**非彈窗卡片**）→ 確認後機器人進 `checkout` phase 才出 QR。

兩模式的「確認」體驗不一致，且都不是使用者要的**彈出式確認卡片**。

---

## 範圍（Scope）

**In：**
- `myProgram/webui/app.js`：新增 `confirm` overlay + `ConfirmSheet` 元件 + 事件流（demo / live）；移除側欄就地「確認金額正確」按鈕。少量 `app.css`（若需要過場動畫，沿用既有 `wf-fade` / `wf-sheet`）。
- `myProgram/web/commands.py`：新增 `{type:"resume"}` 命令 → token `"繼續"`。
- `myProgram/sales/states/l2_l3_dialog.py`：`_dialog_checkout_confirm` + `checkout_flow` 加「繼續點餐（保留購物車回 L3）」路徑（**走 SDD**）。
- `myProgram/sales/constants/`：新增（或重用）回點餐 ack 文案。
- 測試：`tests/web/`（commands 映射）、`tests/sales/`（繼續點餐路徑）。

**Out（不做）：**
- `web/display.py` / `web/app.py` / `web/server.py` / `web/bus.py`：**零改**。confirm 期間機器人 phase 仍 `ordering`，繼續點餐後仍 `ordering`；前端確認卡片由本地 `_awaitingConfirm` 旗號驅動，不需要新 phase。
- 不新增 DisplayState phase（維持 `standby / ordering / checkout / thankyou` 四態）。
- 不改 QR 掛碼卡（`CheckoutSheet`）本身的內容與「我已完成付款」流程。
- 不動既有 cancel / cancel_confirm（清購物車退 L1）語意——「返回購物車」是**保留購物車**的獨立新路徑，不等於取消。

---

## 決策（已與使用者敲定）

| 決策 | 選擇 | 理由 |
|---|---|---|
| 適用模式 | **demo + live 統一** | demo 是 live 的鏡像預覽，兩者一致，展示時看到的就是真實流程。 |
| 卡片動作 | **確認結帳 + 返回購物車 兩鈕** | 對齊語音「正確嗎」的「是 / 我還要逛」兩種顧客意圖。 |
| live「返回購物車」 | **加機器人「繼續點餐」路徑（保留購物車）** | 機器人目前在語音 confirm 閘只支援「確認→L4」或「取消→清購物車退 L1」，無「保留購物車回點餐」。新增此路徑語意最正確、兩模式真正一致；沿用 C-2 既有 CONTINUE 機制（`KG_C2_CONTINUE` + `main_loop` 重入），零新意圖架構。 |
| 前端結構 | **兩張獨立 overlay**（confirm / checkout） | 各 template 只一件事、最好除錯；商品明細抽共用 helper 消除重複。 |
| 新 phase？ | **不加** | confirm 是 `ordering` 內的本地 affordance，沿用既有 `_awaitingConfirm` 模式（disconnect_reset 設計已用此旗號），後端零改。 |

---

## 架構 / 元件 / 資料流

### 新流程（兩模式一致）

```
點「結帳」 ─▶ [確認卡片 ConfirmSheet]  商品明細＋總計
                  ├─ 確認結帳 ─▶ [QR 掛碼卡 CheckoutSheet] ─▶ 付款 ─▶ 謝謝惠顧
                  └─ 返回購物車 ─▶ 關卡片、保留購物車、回點餐畫面

overlay 狀態：null → confirm → checkout(QR) → thankyou
```

### A. 前端（`webui/app.js`）

**新增 overlay 狀態 `"confirm"`**；`renderVals` 加：
```js
showConfirm: this.state.overlay === "confirm" || (this._live && this._awaitingConfirm),
```
- demo：由 `overlay === "confirm"` 驅動。
- live：由本地 `_awaitingConfirm` 驅動（機器人 phase 仍 `ordering`，不混入 robot 的 overlay 鏡像）。

**新 template `ConfirmSheet(v)`**：沿用 `CheckoutSheet` 玻璃 chrome（`wf-fade` 遮罩 + `wf-sheet` 卡 + 拖拉把手 + 標題列 + IconButton 關閉），主體為商品明細 + 總計，底部兩鈕：
- 「確認結帳」`Button({ variant:"primary", icon:"ph-bold ph-check", act:"confirm" })`
- 「返回購物車」`Button({ variant:"glass", icon:"ph-bold ph-arrow-left", act:"back" })`

**抽共用 helper `OrderLines(v)`**：把 `CheckoutSheet` 內的商品明細 `line()` 列渲染抽出，`ConfirmSheet` 與 `CheckoutSheet` 共用（消除重複，對齊 karpathy 只在真重複時抽）。

**`render()`** 加一行：`${v.showConfirm ? ConfirmSheet(v) : ""}`（置於 `CheckoutSheet` 之前或之後皆可，z-index 互斥不重疊）。

**事件分派（`bindEvents`）**：

| act | demo（`!_live`） | live（`_live`） |
|---|---|---|
| `checkout` | `App.openConfirm()`（overlay `"confirm"`） | `sendCommand({type:"checkout"})` + `_awaitingConfirm=true; render()`（顯示卡片） |
| `confirm` | `App.openCheckout()`（overlay `"checkout"` = QR） | `sendCommand({type:"confirm"})` + `_awaitingConfirm=false; render()`（關卡片，等機器人 emit `checkout` phase 出 QR） |
| `back`（新） | `App.closeOverlay()`（回購物車，cart 不變） | `sendCommand({type:"resume"})` + `_awaitingConfirm=false; render()`（關卡片，等機器人 emit `ordering` phase） |

- 新增 `App.openConfirm() { this.setState({ overlay: "confirm" }); }`。
- demo switch 新增 `case "confirm"` 與 `case "back"`；live switch 新增 `case "back"`（`confirm` 已存在）。
- **移除** `CartInner` 內 `v.awaitingConfirm ? Button(確認金額正確...) : Button(結帳...)` 的三元分支，側欄按鈕**永遠**是「結帳」（確認改由 popup 卡片承擔）。
- demo 背景點擊：`ConfirmSheet` 外層 `data-act="close"` + 內層 `data-act="stop"`（沿用 `CheckoutSheet`）；demo `close` → 回購物車。live 的 `close` 在 live switch 不處理（既有行為，overlay 由機器人驅動）→ live 點背景不關卡片，只能按鈕，符合機器人主導。

**demo 預覽切換器**：`reviewOptions` 加 `["confirm", "確認"]`；`setView` 加 `else if (v === "confirm") ...overlay:"confirm"`；`currentView` 加 `overlay === "confirm" ? "confirm"` 判斷（預覽 parity）。

### B. Transport（`web/commands.py`）

新增命令型別 → token（純映射，沿用既有風格）：
```python
if ctype == "resume":
    return _RESUME_TOKEN          # = "繼續"
```
- `_RESUME_TOKEN = "繼續"`：對齊 sales 端 `KG_C2_CONTINUE` 的 strict-short「繼續」（單字嚴格相等才命中，防 substring 誤命中「繼續努力」等）。
- 其餘命令（wake/pay/checkout/confirm/order）不動。

### C. Sales 對話「繼續點餐」路徑（`sales/states/l2_l3_dialog.py`，**走 SDD**）

**`_dialog_checkout_confirm`**：在亂答累加（`unclear_count += 1`）**之前**、`KG_CONFIRM_YES` 檢查**之後**，加一條分支：
```python
if KG_C2_CONTINUE.matches(response):     # 已於檔頭 import（line 73），零新 import / 零新 keyword
    return "continue_keep_cart"           # 新 string sentinel
```
（`"繼續"` 不會命中前面的 `"1"/"2"/is_cancel_intent/CONFIRM_NO/CONFIRM_YES`，放此處安全。）

**`checkout_flow`**：在 `"yes"` / `"cancel_to_l1"` 之後、`_handle_checkout_confirm_result` 之前，加：
```python
if result == "continue_keep_cart":
    self.io.speak(L3_CHECKOUT_RESUME_ACK)   # 新文案（或重用 L3_C2_CONTINUE_ACK，SDD 階段定）
    return None                              # 不清 cart、不進 _handle_checkout_confirm_result、不 do_action L4
```
- `return None` 後：
  - **主迴圈 dispatch caller**（`_dispatch` checkout 分支）：None → 主迴圈 continue（cart 保留）。
  - **C-2 caller**（`_c2_checkout_via_confirm`）：`checkout_flow` 回 None → 回 `main_loop()`（cart 保留）。
  - **兩個 call site 都須驗證**「保留 cart + 重入主迴圈」，SDD plan 列為驗收點。
- speak ack 沿用 C-2 CONTINUE 教訓（2026-05-30：不 speak ack 會讓顧客失上下文 → 沉默 → 被 timeout 抓回）。

**文案**：新增 `L3_CHECKOUT_RESUME_ACK`（如「好的，您可以繼續點餐。」）置於對應 `l3_text.py`；或重用 `L3_C2_CONTINUE_ACK`（語境：從 confirm 回點餐 vs 從 C-2 回點餐略異 → 傾向新增專屬文案，SDD 階段定）。

### live 端到端時序（驗收用）

```
顧客點「結帳」 ─▶ WS送 checkout ─▶ commands→"結帳" ─▶ inject ─▶ L3 dispatch→checkout_flow
   └─前端 _awaitingConfirm=true → ConfirmSheet 彈出（phase 仍 ordering）
機器人 speak「正確嗎」（_dialog_checkout_confirm 等待）
顧客點「返回購物車」 ─▶ WS送 resume ─▶ commands→"繼續" ─▶ inject
   └─前端 _awaitingConfirm=false → 關卡片
_dialog_checkout_confirm 讀到"繼續" → KG_C2_CONTINUE → "continue_keep_cart"
   └─ checkout_flow speak ack + return None → 主迴圈續聽點餐（cart 保留）
   └─ 機器人續 emit ordering phase → 前端 applyState 維持點餐畫面（cart 完整）
（或）顧客點「確認結帳」 ─▶ WS送 confirm ─▶ "正確" ─▶ "yes" → L4 → emit checkout phase → 前端出 QR
```

---

## 錯誤處理 / 邊緣

- **live 斷線於 confirm 卡片中途**：`resetToWelcome()` 已清 `_awaitingConfirm` + overlay → 回歡迎畫面（既有 disconnect_reset 行為，零額外處理）。
- **機器人因 timeout / 亂答上限離開 confirm**：機器人自行清 cart 退場（既有錢包保守邏輯），emit 對應 phase → 前端 `applyState` 接手，本地 `_awaitingConfirm` 被 `applyState`（phase ≠ ordering 時清旗號）清掉 → 卡片自然消失。**不需前端特別處理**。
- **demo「返回購物車」**：`closeOverlay()` 純前端，cart state 不動 → 回購物車畫面、明細完整。
- **`"繼續"` token 誤命中防護**：strict-short 單字相等（`KG_C2_CONTINUE`），不會被「繼續努力」等 substring 誤觸；且只在 `_dialog_checkout_confirm` 迴圈內生效，不影響其他層。
- **確認卡片與 QR 卡互斥**：`overlay` 單值，confirm / checkout 不同時 render；live 由 `_awaitingConfirm`（ordering 期）與 `checkout` phase（QR 期）時間上互斥。
- **空購物車點結帳**：側欄「結帳」按鈕只在 `hasItems` 時出現（既有），confirm 卡片不會在空車時被觸發。

---

## 測試

- **`web/commands.py`** → `tests/web/` pytest（Windows 可跑，純 stdlib）：`{type:"resume"}` → `"繼續"`；壞型別 / 缺欄位 → None。
- **`sales` 繼續點餐路徑** → `tests/sales/` pytest（Stop hook 守）：
  - `_dialog_checkout_confirm` 讀到「繼續」→ 回 `"continue_keep_cart"`。
  - `checkout_flow` 收到 `"continue_keep_cart"` → speak ack、**cart 未清**、return None、未 do_action L4。
  - 兩 call site（主迴圈 / C-2）皆保留 cart 並重入主迴圈。
  - 既有 confirm 行為（yes/no/timeout/cancel/亂答上限）回歸不變。
- **`app.js`** → 無 JS 單元框架（buildless，對齊 Phase 0/1/2）→ **筆電 by-eye 實測**：
  - demo：結帳 → 確認卡片 → 確認結帳 → QR；結帳 → 返回購物車 → 回購物車（明細完整）。
  - 預覽切換器「確認」狀態正確顯示卡片。
- **live robot 路徑** → **Pi 實機 by-ear**：語音「正確嗎」時點「返回購物車」→ 機器人續聽點餐、cart 還在；點「確認結帳」→ 出 QR。

---

## 範圍外 / 後續

- 確認卡片 ↔ QR 卡之間若想要更細緻的 morph 過場 → 視 demo 體感再議（目前沿用既有 `wf-fade` 淡入即可，YAGNI）。
- 「返回購物車」在 live 是否要 robot speak 一句更貼切的回點餐提示（vs 重用 C-2 ack）→ SDD 文案階段定。
- 確認卡片是否顯示折扣 / 原價小計等更多明細 → 目前對齊 QR 卡明細（品名 ×數量 + 小計 + 總計），不擴充。

---

## v2 變更（2026-06-20，Pi 實測後修正）：confirm 改機器人 phase 驅動

**狀態：** v1 上線後 Pi by-ear 實測發現 bug → 根因調查 → 與使用者敲定改法 → 走 SDD。

### 現象 / 根因
Pi live 實測：顧客在 L3 講「這樣就好了」（結帳意圖短語 → 走結帳）進入機器人語音確認「…正確嗎？」，但**畫面沒跳確認卡片**。

根因（證據）：v1 設計把 live 確認卡片綁在前端本地旗號 `_awaitingConfirm`，而它**只在使用者點 UI「結帳」按鈕時才被設 true**。但結帳確認（`_dialog_checkout_confirm`）整段跑在 **dialog 機台狀態內**（`machine._PHASE_BY_STATE` 只在進層 emit，dialog→`ordering`），**沒有任何「機器人正在等結帳確認」的訊號**。語音 /「沉默 6 秒 C-2 自動結帳」/「結帳意圖短語」這些**非 UI 觸發**路徑下，前端收不到訊號 → 卡片永不出現。前端光憑 DisplayState（phase/cart/total）無法區分「ordering 等加單」vs「ordering 等結帳確認」→ **後端非發訊號不可**。

**v1「後端零改」假設錯誤**：只 cover「UI 按鈕發起結帳」，cover 不到語音 / 自動結帳（而語音正是本功能主場景）。

### 修正設計（phase 驅動，取代本地旗號）
1. **sales（`l2_l3_dialog.py`）**：`_dialog_checkout_confirm` 進入時 `io.display("checkout_confirm", dict(cart))` 發訊號（`DialogIO.display` 既有，dialog_io.py:25）。離開各路徑既有 emit 自然收掉卡片：yes→L4 emit `checkout`；繼續 / timeout / no→main_loop emit `ordering`；cancel→退 L1 emit `standby`。
2. **web（`models.py`）**：DisplayState phase Literal 加 `"checkout_confirm"`（`/api/state` 快照驗證需要；WS push 走 raw dict 不驗但仍需契約一致）。
3. **webui（`app.js`）**：`applyState` 把 `checkout_confirm`→overlay `"confirm"`；`showConfirm` 簡化為 `overlay === "confirm"`（demo/live 統一）；**移除整個 `_awaitingConfirm` 機制**（field / resetToWelcome / applyState 清旗號 / 3 處 bindEvents）；live 的 `checkout`/`confirm`/`back` 改回「純送命令、不動本地狀態」——回歸 live 既有「觸控只送命令、狀態等機器人 emit」哲學（`_awaitingConfirm` 本就是違反此哲學的 pre-existing 異物）。

**效果**：語音 / 自動結帳 / UI 按鈕三種觸發都跳卡片；demo 不受影響（走 overlay 非 WS）。代價：反轉 v1「後端零改」→ 後端 sales + models 也動（走 SDD 三段）。

### 測試
- sales（`tests/sales/`，可跑）：`run_dialog` 注入 display callback，餵結帳意圖 → 斷言 display 收到 `("checkout_confirm", cart)`。
- models（Pi-only pydantic，Windows 不可 import）：`ast.parse` 語法 + Pi runtime；無 Windows 單元測試。
- app.js：`node --check` + Pi by-ear 重驗（語音「這樣就好了」→ 跳卡片）。
