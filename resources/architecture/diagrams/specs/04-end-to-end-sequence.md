# 圖④ 端到端時序圖（一輪互動）— 畫圖 spec + 畫圖計畫

> 來源：`00-system-overview.md §5` 骨架 + 實讀核對（2026-06-22 逐檔）：
> `main.py`（read_customer_input / _run_wiring）、`web/commands.py`（token 映射）、
> `web/server.py`/`web/app.py`/`web/bus.py`/`web/display.py`（WS transport + emit 鏈）、
> `sales/states/machine.py`（`_emit` + `_PHASE_BY_STATE`）、`l1.py`（hawk wake）、
> `l2_l3_dialog.py`（checkout_confirm 子 phase emit）、`l4.py`（QR + pay）、`l5.py`（thankyou）、
> `constants/products.py`（冰紅茶 30→九折27/瓶）。

## 主題一句話
一輪完整互動（顧客觸控喚醒 → 點一瓶冰紅茶 → 結帳確認 → 掃碼付款 → 致謝 → 回叫賣）跨
**6 條泳道**（前端 / WS·transport / 主線程 / STT / TTS / Action）依時間由上而下。核心真相＝
**phase-driven**：前端每次換畫面都由後端 `display(phase)` emit 驅動，觸控 / 語音只「請求」、
不本地樂觀改畫面。

## 核對過的碼事實（權威 — 一定照這個畫，別自行加減訊息）

### 下行 phase emit 鏈（每個 `display(...)` 都走這條，畫成同一種金線）
`SalesMachine` / dialog 內呼叫注入的 `display(phase,cart,paid)` → `web/display.make_web_display`
算 `total` → `bus.publish`（存 `last_state` + `asyncio.run_coroutine_threadsafe(_broadcast, loop)`）
→ uvicorn async loop 內 `_broadcast` → `ws.send_json` → 前端 `applyState`+`render`。
> publish 在主線程呼叫、_broadcast 在 uvicorn 線程跑（跨執行緒橋）；時序圖用「主線程→WS→前端」表現即可。

### 上行觸控命令鏈（每個觸控都走這條）
前端 `sendCommand({type})` → WS `/ws/state` `receive_text` → `commands.to_token` → `on_input`
（= `input_reader.inject`，put 進**與鍵盤 / STT 共用的單一 input queue**）→ 主線程 `read_*` 取。
- `to_token` 映射（`web/commands.py` 逐字）：`wake→"t"` · `order{item,qty}→f"{item}{qty}"`（item∈PRODUCTS、qty 正整數）
  · `checkout→"結帳"` · `confirm→"正確"` · `resume→"繼續"` · `pay→"s"`。
- `wake`/`pay` ＝模擬硬體觸發點（目前無真掃碼器）。

### 機台 phase 映射（`machine.py:29`）
`_PHASE_BY_STATE = {l1:"standby", dialog:"ordering", l4:"checkout", l5:"thankyou"}`，
`_emit` 在**進每層時**（invariant 後、state.run 前）發；`paid` 僅 l5 帶 `calc_total`。
⚠️ **`checkout_confirm` 不在此表** —— 它在 dialog 機台狀態**內**由 `_dialog_checkout_confirm`
直接 `io.display("checkout_confirm", dict(cart))` 發（`l2_l3_dialog.py:734`）；語音 / 沉默自動結帳 /
UI 三種觸發皆經此。**別把它畫成 machine 的平行 phase**。

### 一輪訊息序列（精確，逐行；冰紅茶 1 瓶 = 27 元）
分 6 個 phase 帶（band），金線 = `display(phase)` 下行（每帶開頭那一發）：

**帶0 · PHASE standby（起點）** — 機器人在 L1 hawk 叫賣；先前 `_emit("l1")`→`display("standby",{},0)`
→ 前端 Standby 全屏歡迎「輕觸螢幕，開始點餐」。顧客靠近、觸控。

**帶1 · WAKE（觸控喚醒）**
1. 前端：觸控「開始點餐」→ `sendCommand({type:"wake"})`
2. WS：`receive_text` → `to_token` = `"t"` → `inject("t")` → input queue
3. 主線程：L1 hawk `read_terminal_key(0.1)` 取 `"t"` → 回 `"L2"` → SalesMachine `l1→dialog`

**帶2 · ORDERING（進點餐 + 點冰紅茶）**
4. 主線程（進 dialog）：`_emit("dialog")` → `display("ordering",{},0)` 【金】
5. WS：`bus.publish`→`run_coroutine_threadsafe`→`_broadcast`→`ws.send_json`
6. 前端：`applyState`→點餐主畫面（Menu＋空 CartRail）
7. 主線程（dialog entry）：`do_action(ACTION_L2 揮手)`→Action queue→vendor SDK；
   `speak(L2_ENTRY_PROMPT)`→TTS queue→edge-tts/快取→mpg123
8. 點餐（語音示範「我要一瓶冰紅茶」）：主線程 `read_customer_input(timeout)` 編排
   `stt.prearm()`→`tts.wait_idle()`→`stt.arm()`；STT 泳道：`arecord -c6 抽ch0`→Deepgram Nova-3 WS
   →`speech_final`→`_normalize`→`inject("我要一瓶冰紅茶")`→主線程取；`finally stt.disarm()`
   〔旁註：觸控點餐 = `{type:"order",item:"冰紅茶",qty:1}`→`"冰紅茶1"`→同一 inject queue（呼應圖① producer 端零分流）〕
9. 主線程：`parse_products`→`resolve_and_add_products`→`cart.add_item("冰紅茶",1)`
10. 主線程（main_loop 末）：`display("ordering",{"冰紅茶":1})` 【金】→WS→前端：購物車長出 冰紅茶×1（syncCart 局部更新）

**帶3 · CHECKOUT_CONFIRM（結帳 → 確認卡片）**
11. 結帳：觸控 `{type:"checkout"}`→`"結帳"`（或語音「結帳」）→inject→主線程取
12. 主線程：`classify_intent="結帳"`→`L3Policy.on_checkout_main`→`checkout_flow`→`_dialog_checkout_confirm`：
    `display("checkout_confirm",cart)` 【金 ★ dialog 內直發，非 machine】→WS→前端：ConfirmSheet 確認卡片
    （明細 + 確認結帳 / 返回購物車）；`speak(L3_CHECKOUT_CONFIRM 明細語音)`
13. 確認：觸控 `{type:"confirm"}`→`"正確"`（或 `"1"`）→inject→主線程取→`_dialog_checkout_confirm` 回 `"yes"`
14. 主線程：`checkout_flow "yes"`→`speak(L3_C1_CHECKOUT_GO)`＋`do_action(ACTION_L3_CHECKOUT_GO 指向螢幕)`
    →回 `("L4",0)`→SalesMachine `dialog→l4`

**帶4 · CHECKOUT（QR 等掃碼）**
15. 主線程（進 l4）：`_emit("l4")`→`display("checkout",cart,0)` 【金】→WS→前端：CheckoutSheet QR 條碼（我已完成付款）
16. 主線程（run_l4 entry）：`_l4_print_entry_detail`（終端明細）＋`speak_blocking(L4_ENTRY_PROMPT「總額 27 元」)`；
    v3 雙計時器（36s 總 budget / 12s QR 刷新循環）
17. 掃碼付款：觸控 `{type:"pay"}`→`"s"`→inject→主線程 `read_customer_input` 取 `"s"`
18. 主線程：`_l4_dispatch_response "s"`→`_l4_pay_success`：`speak(L4_A_PAY_SUCCESS_FAREWELL 付款成功+致謝)`
    ＋`do_action(ACTION_L4_PAY 鞠躬)`→回 `("L5",0,0)`→SalesMachine `l4→l5`

**帶5 · THANKYOU（致謝 → 回叫賣）**
19. 主線程（進 l5）：`_emit("l5")`→`paid=calc_total=27`→`display("thankyou",cart,paid=27)` 【金】→WS→前端：ThankYou 全屏謝謝惠顧
20. 主線程（run_l5）：`do_action(ACTION_L5_FAREWELL 揮手送客)`→`clear_cart`→`sleep(THANK_DELAY=3s)`→回 `("L1_enter_hawk",0,0)`→`l5→l1`
21. 主線程（進 l1）：`_emit("l1")`→`display("standby",{},0)` 【金】→WS→前端：回 Standby 全屏歡迎；L1 再進 hawk 連續叫賣（迴圈回帶0）

## thesis / 主角（boldness 集中一處）
**下行 phase emit（金）** —— 7 發 `display(phase)`（standby→ordering→ordering+cart→checkout_confirm→checkout→thankyou→standby）
做成貫穿時間軸、落在「前端」生命線上的暖金箭頭（`.hawk` + `ah-hawk`）：點明「畫面只在機器人 emit phase 時才變」。
其餘訊息（上行觸控請求 / 內部 worker 派工 / STT pipeline）一律安靜 `.flow` 白線。⚠️ `checkout_confirm` 那發要視覺標 ★（dialog 內直發、非 machine 平行 phase）。

## 視覺色彩語意（共用 theme + legend，6 列）
泳道頭卡用色編碼角色：藍=前端（render client）/ 紫=WS·transport（EventBus＋commands＋WS）/ 綠=主線程（SalesMachine＋TerminalSim callback）/ 青=STT(每輪)/ 橘=TTS / 灰=Action·vendor。
金（`--arrow-hawk`）= phase emit 下行（主角，非泳道色）。

## 版面（時序圖；畫大沒關係）
- `.stage` 約 **2040 × 2160**（時序圖天生高；寬容 6 泳道 + 訊息標籤）；DPR 每次實測。
- 標題列頂置中（`FIG.04`）。
- **6 條泳道**：頂部 6 張彩色 head 卡（眉標 eyebrow 標角色 + name mono + meta），各往下拉一條垂直**生命線**（lifeline，細直線到底）。泳道由左到右：前端 | WS | 主線程 | STT | TTS | Action（讓主流 前端↔WS↔主線程 三線相鄰、最少交叉）。
- **5 個 phase 帶**（帶1–5；帶0 起點可併進帶1 頂或做薄起始列）：每帶一條極淡水平背景帶 + 左緣眉標徽章 `PHASE standby/ordering/checkout_confirm/checkout/thankyou`（編碼真實 phase 序，呼應圖②③）。
- **訊息**＝泳道間水平 / 斜箭頭，依序由上而下排，標籤 mono（函式 / token / 語音字）落線中段清空處 + 深色 halo。金 phase emit 一律「主線程→WS→前端」三段、或直接主線程→前端粗金弧（擇一最乾淨者）。
- legend 收一上角空位、note 收另一角；皆 ≥30px 不碰任何卡 / 生命線。

## 邊清單（先卡片＋生命線層截圖修版面，再加 SVG 箭頭層）
- 上行（白 `.flow`）：wake/order/checkout/confirm/pay 五發觸控 → WS → 主線程；STT pipeline（arecord→Deepgram→inject）；dialog 內 speak→TTS、do_action→Action 派工。
- 下行（金 `.hawk`+`ah-hawk`）：7 發 `display(phase)` → WS → 前端。
- 自迴圈尾：帶5 末「迴圈回帶0」用一條細虛線 / 標註回指帶0（連續叫賣），別畫成糾纏大弧。
> 路由鐵則：金線與白線分屬不同 lane、最少交叉；標籤不壓生命線 / 不壓 head 卡；STT 四段走 STT 泳道內側垂直 lane。

## note（角落，填「所以呢」3 點）
- **phase-driven**：前端 7 次換畫面全由後端 `display(phase)` 驅動；觸控只送命令、不本地樂觀改畫面（觸發也可能來自語音 / 自動結帳）。
- **單一 input queue**：wake/order/checkout/confirm/pay 觸控 token 與 STT `speech_final` 注入**同一** queue，主線程 `read_*` 單一消費（呼應圖①）。
- **`checkout_confirm` 是 dialog 內子 phase**：machine `_PHASE_BY_STATE` 只有 standby/ordering/checkout/thankyou 四個；確認卡片這發由 `_dialog_checkout_confirm` 直發。

## 自檢必裁區（render-pipeline §5；先全圖再局部）
① 全圖：6 泳道生命線到底不斷、5 phase 帶不互疊、無大片死空白。② 每發金 phase emit 箭頭頭真觸前端生命線、與白線不糾纏、頭色＝金（GetPixel 線中段 vs 箭頭頭比色）。③ STT 泳道四段（arecord→Deepgram→speech_final→inject）標籤不溢、不壓生命線。④ 訊息標籤 mono 不被卡 / 線蓋住、不溢框。⑤ checkout_confirm ★ 標記清楚。⑥ 四角無黑邊（2× 匯出 GetPixel）。
