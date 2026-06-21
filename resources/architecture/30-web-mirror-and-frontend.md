# 30 · Web 顯示鏡像與前端（web 交互狀態機）

> 機器人狀態怎麼即時鏡像到瀏覽器、觸控怎麼回送、前端 phase→畫面怎麼切。涵蓋 `myProgram/web/`（transport）+ `myProgram/webui/`（前端）。以實際 code 為準（2026-06-21）。

> 設計定位：`web/` 是與 `sales/` 業務邏輯**分離的 transport 層**。`sales/` 只多呼叫一個注入的 `display` 回呼，**不知道 web 存在**。

---

## 1. 資料流總覽（下行鏡像 + 上行命令）

```
下行（狀態鏡像）：
  sales/ display(phase, cart, paid)        ← SalesMachine 在每個狀態點 emit（見 20 §5）
    └→ web/display.make_web_display          算 total，組成 {phase,cart,total,paid} dict
        └→ web/bus.EventBus.publish          存 last_state + 排程廣播到 async loop
            └→ web/app.py /ws/state          ws.send_json 推所有 client
                └→ webui/app.js ws.onmessage applyState → render() 切畫面

上行（觸控命令）：
  webui/app.js sendCommand({type:…})       觸控按鈕 → WS 送結構化命令
    └→ web/app.py /ws/state receive          ws.receive_text
        └→ web/commands.to_token             命令 dict → 對話既有 token 字串
            └→ input_reader.inject            put 進共用 input queue
                └→ 主線程 read_* 取用         對話層零改動、零新意圖碼
```

關鍵原則：**phase-driven**。前端畫面切換只由後端 emit 的 phase 驅動，觸控只「請求」、不本地樂觀改畫面——因為觸發也可能來自語音或自動結帳（非 UI）。

---

## 2. Transport 層（`myProgram/web/`）

| 檔 | 角色 | Windows 可 pytest？ |
|---|---|---|
| `bus.py` | `EventBus`：同步機器人線程 → async loop 廣播橋 | ✅ 純 stdlib（asyncio）|
| `display.py` | `display` callback web 版：`(phase,cart,paid)` → publish dict | ✅ 純 stdlib（只 import sales 常數）|
| `commands.py` | 觸控上行命令 → 對話既有 token（純映射）| ✅ 純 stdlib |
| `models.py` | Pydantic DTO（前後端契約）| ❌ Pi-only（import pydantic）|
| `app.py` | FastAPI 路由 + StaticFiles | ❌ Pi-only（import fastapi）|
| `server.py` | uvicorn 背景執行緒生命週期 | ❌ Pi-only（import uvicorn）|

Pi-only 三檔在 Windows 只能 `ast.parse`（語法檢查），真驗在 Pi。

### 2.1 `EventBus`（`bus.py`）— 跨執行緒模型橋接

機器人在**同步**主線程跑，uvicorn 在**另一條 thread 的 async loop** 跑。EventBus 橋接兩者：

```python
publish(state)   # 機器人線程呼叫：存 last_state + asyncio.run_coroutine_threadsafe(_broadcast, loop)（loop 未綁時只存）
bind_loop(loop)  # uvicorn startup 時綁 async loop
last_state()     # /api/state 與 WS 連上時取 snapshot
add/remove_client(ws)
_broadcast       # async：對每個 client ws.send_json，send 失敗的標記為 dead 移除
```

設計要點：
- **`publish` 在 loop 未綁時只存 `last_state` 不廣播**——讓早期 menu emit（瀏覽器還沒連、server 還沒起）不丟失，瀏覽器之後連上經 `/api/state` 取最後快照。
- `run_coroutine_threadsafe` 是跨執行緒把 coroutine 丟進 async loop 的標準手法（同步線程不能直接 await）。
- broadcast 對 dead client 容錯（send 失敗即移除，不拖垮）。

### 2.2 `display.py` — sales 與 web 的接縫

```python
def make_web_display(bus):
    def display(phase, cart, paid=0):
        try:
            total = sum(PRODUCTS[name]["實際"] * qty for name, qty in cart.items())
            bus.publish({"phase": phase, "cart": dict(cart), "total": total, "paid": paid})
        except Exception:
            pass   # web 掛了機器人照常服務客人，display 不得拖垮對話線程
    return display
```

- **total 由後端算**（單一事實來源，前端不重算金額）。
- 整段 try/except：**web 故障不得影響機器人服務客人**（spec 級錯誤處理）。
- 這個 `display` 就是 `20 §5` 列的注入 callback；終端模式則為 no-op lambda（完全不 import web）。

### 2.3 DTO 契約（`models.py`）

```python
class Product(BaseModel):      name; unit; price_now; price_orig
class DisplayState(BaseModel): phase: Literal["standby","ordering","checkout_confirm","checkout","thankyou"]; cart: dict[str,int]; total: int; paid: int = 0
class Snapshot(BaseModel):     catalog: list[Product]; state: DisplayState
```

`phase` 的 5 個 Literal 值是前後端契約核心（見 §4 映射表）。

### 2.4 路由（`app.py`）

| 路由 | 方法 | 行為 |
|---|---|---|
| `/api/state` | GET | 回 `Snapshot`（catalog + 當前 state，無狀態時回 `_STANDBY` 預設）|
| `/ws/state` | WS | accept 後先送一筆 `last_state`，之後迴圈 `receive_text` 收上行命令；斷線 finally 移除 client |
| `/`（greedy mount，**必須最後註冊**）| — | `_NoCacheStaticFiles` 出 `webui/` 靜態檔（覆寫 header 加 `Cache-Control: no-cache, no-store`）|

- `startup` event 綁 uvicorn loop 給 EventBus（`bus.bind_loop(asyncio.get_running_loop())`）。
- WS 上行：`commands.to_token(json.loads(raw))` → 非 None 才 `on_input(token)`（= `input_reader.inject`）；壞 JSON / 非 dict → 忽略不拖垮連線。
- StaticFiles 掛 `/` 必須**最後**（greedy），否則蓋掉 `/api`、`/ws` 路由。

### 2.5 `server.py` — uvicorn 背景執行緒

```python
start(bus, on_input, host="0.0.0.0", port=8137)
  → uvicorn.Server(...); server.install_signal_handlers = lambda: None  # 非主執行緒不可裝 signal handler
  → daemon thread 跑 server.run；回 (server, thread)
stop(server) → server.should_exit = True
```

由 `main._run_wiring` 的 `webui-boot` 背景 thread 呼叫 `start`（笨重 import 不擋 menu）；程式退出時 `main` finally 在 boot.join 後呼叫 `stop`。

### 2.6 上行命令映射（`commands.py`）

把瀏覽器結構化命令翻成「對話既有 read 路徑會處理的字串」→ 對話層零新意圖碼：

| 命令 dict | token | 對話端如何消費 |
|---|---|---|
| `{type:"wake"}` | `"t"` | `read_terminal_key` 認 't' → L1 hawk→L2 |
| `{type:"order",item,qty}` | `f"{item}{qty}"` | 走 `parse_products`（item 須 ∈ PRODUCTS、qty 正整數，否則回 None）|
| `{type:"checkout"}` | `"結帳"` | L3 主迴圈 dispatch 走 `_KEYWORDS_CHECKOUT` |
| `{type:"confirm"}` | `"正確"` | `_dialog_checkout_confirm` 走 `KG_CONFIRM_YES` |
| `{type:"resume"}` | `"繼續"` | 對齊 `KG_C2_CONTINUE` strict-short |
| `{type:"pay"}` | `"s"` | `read_customer_input` 認 's' → L4→L5（模擬掃碼）|

⚠️ **token 字選錯陷阱**：「結帳」(帳) ≠ C-2 子狀態的「結賬」(賬)，選錯主路徑會落 unclear（2026-06-19 Pi 實測修正）；token 對齊「實際消費路徑」的字，有 test 守行為防漂移。`wake`/`pay` 是模擬硬體觸發點（目前無真掃碼器），未來接真硬體改這兩個映射即可，對話層不受影響。

---

## 3. 前端（`myProgram/webui/`）

### 3.1 技術基底

- **Buildless 靜態**：無打包、無框架 runtime、無測試框架。`index.html`（24 行殼）依序 link 6 個 token CSS + Phosphor 圖示 CDN + `app.css`，body 只有 `<div id="app">` + `<script src="app.js">`。
- **單檔邏輯 `app.js`**（~729 行）三層：元件層（回 HTML 字串的小函式）/ 狀態層（`App` 物件 = DCLogic，移植自設計稿）/ 版面層（template 函式）。
- **渲染**：`innerHTML` 字串拼接 + `data-act` 事件委派；所有使用者文字經 `esc()` HTML 轉義。
- **雙模式**：`App._live = !location.search.has("demo")`。`?demo=1` → demo（本機假資料 + 切換器 + 觸控直接改 state）；否則 → **live**（預設，WS 鏡像，觸控只送命令）。

### 3.2 元件結構

- **5 個元件**（回 HTML 字串）：`Button`（primary/glass）、`IconButton`、`Badge`、`QuantityStepper`（−/數字/+）、`AdBanner`（廣告輪播，`translateX` 滑動）。第 6 個次要元件 `ActionArea`（商品卡行動區，live/demo 行為分流）。
- **DCLogic = `App` 物件**（狀態層）：`state` + `setState`（直接重畫）、`products()`（live 回後端 catalog / demo 回 hardcode）、`renderVals()`（攤平 state 成 view model）、所有 overlay handler、`ingestCatalog` / `applyState`、`qrCells`、廣告 `showAd`。
- **版面層**（template）：`TopBar` / `Menu` / `CartRail` / `CartInner` / `OrderSummary` / `ConfirmSheet` / `CheckoutSheet` / `ThankYou` / `Standby` / `ReviewSwitcher`。

### 3.3 前端內部 state

```js
state = { cart:{id:qty}, overlay:null, standby:false, paidTotal:0, reviewOpen:false, adIndex:0 }
```

畫面由兩個正交維度決定：`standby`（布林，全屏歡迎覆蓋層）+ `overlay`（`null | "confirm" | "checkout" | "thankyou"`）。`render()` 整頁重畫，依序疊：背景光暈 → TopBar → body-grid(Menu+CartRail) → 條件覆蓋層 → demo 切換器。

---

## 4. ★ Web 交互狀態機：後端 phase → 前端畫面

後端 `DisplayState.phase`（5 個 Literal）由前端 `applyState` 折成 standby + overlay：

| 後端 phase | 前端 state | 顯示畫面 |
|---|---|---|
| `"standby"` | `standby=true` | **Standby** 全屏歡迎（「歡迎光臨／輕觸螢幕，開始點餐」）|
| `"ordering"` | overlay=null, standby=false | **點餐主畫面**（Menu + CartRail，依 cart 空 / 非空顯示 empty / filled）|
| `"checkout_confirm"` | overlay=`"confirm"` | **ConfirmSheet** 確認卡片（商品明細 + 確認結帳 / 返回）|
| `"checkout"` | overlay=`"checkout"` | **CheckoutSheet** 結帳卡片（QR 條碼 + 我已完成付款）|
| `"thankyou"` | overlay=`"thankyou"` | **ThankYou** 全屏謝謝惠顧（`paid` 帶入 `paidTotal`，falsy 時保留上一筆）|

⚠️ **名稱不對齊**：後端 `checkout_confirm` ↔ 前端 overlay `confirm`；後端 `ordering` ↔ 前端「無 overlay」。`cart` 由後端直接覆寫（WS 權威）。

**覆蓋層 z-index**：TopBar(30) < Confirm/Checkout 遮罩(60) < ThankYou(70) < Standby(80) < ReviewSwitcher(90) < ws-reconnect 角標(200)。過場：`.wf-fade`（淡入）/ `.wf-sheet`（由下升起）。

---

## 5. 前端 ↔ 後端通訊（兩段式 + 斷線韌性）

核心在 `connectLive()`：

1. **初始 snapshot**：`fetch("/api/state")` → `{catalog, state}`。`ingestCatalog` 把後端 snake_case（`price_now`）轉前端 camelCase、用 `name` 當 id、補 `presentation` 表的 icon/tone；`applyState(state)` + `render()`。
2. **WS 下行**：`new WebSocket("ws://"+location.host+"/ws/state")`，`onmessage` → `applyState(JSON.parse) + render()`；連上即先收一筆 `last_state`。
3. **WS 上行**：`sendCommand(cmd)` 僅 `readyState===OPEN` 才送（斷線 no-op）。
4. **斷線處理**：`onclose` → 清 `_ws`、`resetToWelcome()`（立即回 standby 不凍結）、顯示「重新連線中…」角標、**指數退避重連**（1s 起 ×2 上限 10s）；拿到 snapshot 即重設退避；初次連不上也先顯示歡迎畫面不卡空白。

### `syncCart` 局部更新（效能關鍵）

購物車 +/− 時**不整頁 render**（避免重建多個 `backdrop-blur` 玻璃容器在 Pi / 低端裝置卡頓），只換三塊 innerHTML：`#tb-cart`（TopBar 購物車區）、每張卡的 `#act-<id>`、`#cart-inner`。玻璃容器本身不重建。

---

## 6. 兩條靜態檔上菜路徑

**同一份前端碼，兩個 server，皆 no-cache：**

| 路徑 | 啟動 | 提供 | 用途 |
|---|---|---|---|
| `webui/serve.py` | `python3.11 myProgram/webui/serve.py [port]` | **只**靜態檔（無 API / WS）| 筆電純看 UI，配 `?demo=1` |
| `web/app.py`（FastAPI）| `python -m myProgram --web` | 靜態檔 + `/api/state` + `/ws/state` | 真機 live 鏡像 |

`serve.py` 是純 stdlib `SimpleHTTPRequestHandler` 子類，`end_headers` 加 no-cache header（避免迭代時看到舊 app.js）；服務本檔所在 webui 目錄（不受工作目錄影響）。前端用 `?demo=1` 區分模式，與哪個 server 出檔無關。

---

## 7. Glaze 設計語彙（`tokens/`）

`index.html` 逐檔 link 6 個 `:root` CSS 變數檔，是**視覺單一事實來源**（改視覺先動 token，別在 app.js/css 寫死）：

| token 檔 | 內容 |
|---|---|
| `colors.css` | Apple iOS 系統色（sRGB）+ OKLCH 衍生品牌色（`--brand: oklch(0.68 0.15 235)` 海藍）；**深色為主題**（`--bg-base:#000`）|
| `typography.css` | Apple iOS 字級體系（光學尺寸）；`--font-text` / `--font-display` 堆疊（SF Pro→Inter→Noto Sans TC fallback）|
| `spacing.css` | 8pt 基準間距 + 圓角（`--radius-capsule:999px`）|
| `effects.css` | Liquid Glass 材質：blur ladder + `--glass-saturate:180%` + tint / shadow + 流體漸層 + `.glass*` utility |
| `motion.css` | durations + Apple spring 緩動 + keyframes + reduced-motion 關閉 |
| `fonts.css` | 只「載入」字型：`@import` Google Fonts（Inter + Noto Sans TC）；SF Pro 不打包 |

**CDN**：Phosphor Icons 2.1.1（unpkg）+ Google Fonts（Inter + Noto Sans TC）。皆標「Phase 0 CDN，後續在地化」。

---

## 8. 值得記住的設計決策 / gotcha

1. **Pi 4 渲染限制（最關鍵）**：Pi 4 自帶瀏覽器跑不動前端（GPU + Chromium < 111 不支援 OKLCH，而 `colors.css` 大量用 OKLCH）→ **demo 由 client 筆電 / 手機渲染、Pi 只當 server**。加新 CSS 特性前先顧 demo 渲染環境相容性。
2. **phase-driven，禁前端樂觀旗號**（live）：overlay / 卡片狀態一律等機器人 emit phase 才變；觸控只送 WS 命令、不改本機鏡像 cart。除錯先 `curl /api/state` 隔離前後端。
3. **後端不拖垮機器人**：`make_web_display` 整段 try/except；前端斷線也降級回歡迎畫面不卡死。
4. **`syncCart` 局部更新** 避免玻璃 backdrop 重算卡頓。
5. **廣告輪播 timer start-once**：不在 `render()` 重設倒數，否則點餐互動會一直把倒數歸零。
6. **偽 QR 非真條碼**（`qrCells`）：確定性 hash（FNV-1a + xorshift）生成 21×21 視覺佔位，無真付款語義；seed = `"GLAZE|"+total+"|"+JSON.stringify(cart)`。
7. **catalog 命名橋接**：後端 `name` 當前端 id；snake_case→camelCase 在 ingest 時轉；icon/tone 留前端 `presentation` 表，後端 catalog 只給資料。
8. **`_STANDBY` 預設快照**：機器人還沒 emit 過任何狀態時，`/api/state` 與 WS 連上都回 standby，前端開頁即見歡迎畫面。
9. **MAX_QTY=50** 對齊 sales `MAX_QTY_PER_ITEM`，前端 clamp，後端 `commands.to_token` 也驗 qty>0 與 item∈PRODUCTS（雙重防線）。

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-06-21 | 初版：web transport（EventBus / DTO / 路由 / 上行命令）+ 前端 phase→UI 映射、兩段式資料、syncCart、雙 server、Glaze tokens、Pi 渲染限制。|
