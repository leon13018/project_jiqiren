# 圖③ Web phase 交互狀態機 — 畫圖 spec

> 來源:digest `30-web-mirror-and-frontend.md`(當索引)+ **實讀** `web/{bus,display,app,commands,models}.py`、`webui/{app.js,index.html}`、`sales/states/machine.py`、`sales/states/l2_l3_dialog.py`(2026-06-22 逐檔核對)。圖①②theme 為基準。

> ✅ **已交付（2026-06-22 Wave A）**：`03-web-phase-state-machine.{html,png,svg}` 三式同名。最終版面：emit 源左 / 5 phase 縱列中（checkout_confirm 縮排子 phase）/ 上行回路 6 命令右 / phase 驅動金弧閉環主角 / 白 emit 平行 bus，**以交付 html 為準**。

## 主題一句話

機器人後端在每個對話/機台節點 **emit 一個 phase**(`standby / ordering / checkout_confirm / checkout / thankyou`),經 EventBus → WS 廣播到瀏覽器;前端 `applyState` 把 phase **折成 standby + overlay 兩個正交維度**切畫面。觸控命令(wake / order / checkout / confirm / pay…)只「上行請求」、**不本地樂觀改畫面** —— 因為同一個 phase 也可能由**語音**或**沉默自動結帳**觸發(非 UI)。**畫面切換的唯一權威是後端 phase**,這是本圖核心。

## ★ 核對過的硬事實(實讀碼,推翻 / 補足 digest)

### 1. phase 不是「5 個機台狀態」——是「4 個機台進場 phase + 2 個 dialog 內 emit」(關鍵)

`machine.py:29` 的 `_PHASE_BY_STATE` 只映 **4** 個機台狀態:
```python
_PHASE_BY_STATE = {"l1":"standby", "dialog":"ordering", "l4":"checkout", "l5":"thankyou"}
```
`machine._emit`(machine.py:180)在**進每層時**發這 4 個。**`checkout_confirm` 不在表內、沒有對應機台狀態。**

另外兩個 phase 由 **dialog 機台狀態「內部」** 直接呼叫 `io.display(...)` 發出(machine 不參與):
- `l2_l3_dialog.py:595` — `display("ordering", cart)`:dialog 主迴圈每輪處理完重發 ordering + 最新 cart(購物車逐項長出的增量鏡像)。
- `l2_l3_dialog.py:735` — `display("checkout_confirm", cart)`:在 `_dialog_checkout_confirm()` 進場時發。**碼註解原文(l2_l3_dialog.py:732-733)**:「進結帳確認 → emit checkout_confirm phase(此步在 dialog 機台狀態內,machine 不會發 phase);語音 / 沉默自動結帳 / UI 三種觸發皆經此」。

→ **畫圖含義**:`checkout_confirm` 必須畫成「dialog 內的子 phase」,**不是與 ordering/checkout 平起平坐的機台狀態**。這正是 digest §4 說「後端 checkout_confirm ↔ 前端 confirm overlay」「ordering ↔ 無 overlay」卻沒解釋的底層機制。狀態機圖若把 5 phase 畫成 5 個平行框 = **失真**。

### 2. paid 只在 thankyou(l5)帶,其餘 phase 為 0

`machine._emit`(machine.py:192):`paid = calc_total(self.cart) if current=="l5" else 0`,在 L5 清 cart 前算。前端 `applyState`(app.js:275):`paidTotal = s.paid || this.state.paidTotal`(falsy 時保留上一筆)。

### 3. 後端 phase(5 Literal)= 前後端契約

`models.py:15`:`phase: Literal["standby","ordering","checkout_confirm","checkout","thankyou"]`。WS 推的 dict = `{phase, cart, total, paid}`(`display.py:9`,total 後端算)。

### 4. 前端 phase → 畫面(applyState,app.js:271-276 逐字)

```js
this.state.cart     = s.cart || {};
this.state.standby  = s.phase === "standby";
this.state.overlay  = s.phase === "checkout_confirm" ? "confirm"
                    : s.phase === "checkout"         ? "checkout"
                    : s.phase === "thankyou"         ? "thankyou" : null;
this.state.paidTotal = s.paid || this.state.paidTotal;
```

| 後端 phase | standby | overlay | 顯示畫面(template) |
|---|---|---|---|
| `standby` | **true** | null | `Standby()` 全屏歡迎(歡迎光臨／輕觸螢幕) |
| `ordering` | false | **null** | 點餐主畫面 `Menu`+`CartRail`(cart 空/非空 → empty/filled) |
| `checkout_confirm` | false | `"confirm"` | `ConfirmSheet()` 確認卡(明細 + 確認結帳/返回) |
| `checkout` | false | `"checkout"` | `CheckoutSheet()` 結帳卡(QR + 我已完成付款) |
| `thankyou` | false | `"thankyou"` | `ThankYou()` 全屏謝謝惠顧(帶 paid) |

⚠️ **名稱不對齊**(畫圖要標出):後端 `checkout_confirm` ↔ 前端 overlay 值 `"confirm"`;後端 `ordering` ↔ 前端「**無 overlay**」(不是某個 overlay 名)。

### 5. 上行觸控命令 → token(commands.to_token,commands.py 逐項核對)

| 觸控命令 dict(app.js sendCommand) | token | 對話端消費路徑 | UI 來源(bindEvents,app.js:624-638) |
|---|---|---|---|
| `{type:"wake"}` | `"t"` | `read_terminal_key` 't' → L1 hawk→dialog | `exitStandby`(歡迎頁輕觸) |
| `{type:"order",item,qty}` | `f"{item}{qty}"` | `parse_products`(item∈PRODUCTS、qty 正整數,否則 None) | `add`(加入購物車) |
| `{type:"checkout"}` | `"結帳"` | L3 主迴圈 dispatch `_KEYWORDS_CHECKOUT` | `checkout`(購物車結帳鈕) |
| `{type:"confirm"}` | `"正確"` | `_dialog_checkout_confirm` KG_CONFIRM_YES | `confirm`(確認卡「確認結帳」) |
| `{type:"resume"}` | `"繼續"` | KG_C2_CONTINUE strict-short | `back`(確認卡「返回購物車」) |
| `{type:"pay"}` | `"s"` | `read_customer_input` 's' → L4→L5(模擬掃碼) | `place`(結帳卡「我已完成付款」) |

→ **上行路徑(app.py:49-55)**:WS `receive_text` → `commands.to_token(json.loads(raw))` → 非 None 才 `on_input(token)`(= `input_reader.inject`,put 進共用 input queue)→ 主線程 `read_*` 取用。**對話層零新意圖碼**(命令翻成既有 token 字串)。

→ **畫圖含義**:上行只到 input queue,**不直接改畫面**。畫面要等主線程吃了 token、機台/dialog 轉態、再 emit 新 phase 下行回來。這個「上行請求 → 後端決策 → 下行 phase → 才換畫面」的環,就是「phase-driven、禁前端樂觀」的視覺主張。

### 6. 觸控只是「三種觸發之一」(本圖 thesis 的證據)

`checkout_confirm` 由 `_dialog_checkout_confirm` 發,而進這函數的路徑(l2_l3_dialog.py):
- C-1:顧客**語音**講「結帳」keyword(`KG_C2_CHECKOUT` / 主迴圈 CHECKOUT)。
- C-2:**沉默自動結帳** —— `c2_second_stage` 倒數歸零 / read timeout → `_c2_checkout_via_confirm`(l2_l3_dialog.py:633-640)。
- UI:觸控 `{type:"checkout"}` → token「結帳」→ 同一條主迴圈 path。
→ 三條路殊途同歸到同一個 `display("checkout_confirm")`。**這就是「不能前端樂觀」的硬理由**:UI 不是唯一觸發源。

### 7. 斷線韌性(下行的反面,畫成 note 不畫主流程)

`connectLive`(app.js:697):`fetch("/api/state")` 拿 snapshot → `ingestCatalog`+`applyState` → 開 WS;`onclose` → `resetToWelcome()`(立即回 standby 不凍結)+「重新連線中」角標 + 指數退避(1s×2 上限 10s)。`/api/state` 在機器人沒 emit 過時回 `_STANDBY` 預設(app.py:14,39)。

### 8. EventBus 跨執行緒橋(下行的傳輸,畫成上游小節點)

`bus.publish`(bus.py:23)機器人**同步線程**呼叫:存 `last_state` + `run_coroutine_threadsafe(_broadcast, loop)`;loop 未綁(server 沒起)時**只存不廣播**(早期 menu emit 不丟,瀏覽器之後連上經 `/api/state` 取)。`_broadcast` 對 dead client 容錯移除。

## 色彩語意(本圖專用,配 legend)

phase 是本圖主角 → 用顏色編碼「畫面類別」:
- **藍 = standby**(待機歡迎,全屏)
- **綠 = ordering**(點餐主畫面,dialog 常駐態 + cart 增量鏡像)
- **青 = checkout_confirm**(確認閘 overlay;dialog 內子 phase —— 與圖②「confirm 閘=青」一致)
- **橘 = checkout**(結帳 QR overlay)
- **紫 = thankyou**(致謝 overlay,帶 paid)
- **灰 = transport / 上行命令 / input queue / 外部**(EventBus、WS、commands、瀏覽器觸控)

> 與圖①②色彩語意呼應:青=confirm 閘(圖②同)、紫=通訊/終態語境、灰=transport·外部。

## signature / 主角(frontend-design thesis)

**主角 = 下行 phase 驅動環**:後端 5 phase 縱列(或弧列)為權威源,一條**粗暖金 `.hawk` 弧**把「上行觸控命令 → input queue → 主線程決策 → emit 新 phase → 下行換畫面」串成閉環,點明「畫面不是觸控直接改的,是繞一圈回來的」。boldness 全集中這條環;其餘(transport 細節、斷線)安靜。

## 版面(1960×1320 基準,沿用圖①②theme;不夠再加寬)

- 標題 `FIG.03` 頂置中 + subtitle(mono):`web phase state machine · 後端 phase 驅動前端畫面`。
- **中央主軸 = 5 phase 卡縱列 / 階梯**(藍 standby → 綠 ordering → 青 checkout_confirm → 橘 checkout → 紫 thankyou),每卡 eyebrow 標 `PHASE <NAME>`,卡內:後端 emit 來源(`machine._emit` / `dialog display`)+ 前端折法(`standby=? overlay=?`)+ 顯示 template 名。
- **checkout_confirm 卡視覺「縮排 / 掛在 ordering 下」** 表達「dialog 內子 phase,非機台狀態」(關鍵差異化,配一個 `dialog 內 emit` 標籤)。
- **左側 = 後端 emit 源**:`machine._emit`(綠,映 4 phase)+ `dialog 內 io.display`(綠虛,發 ordering 增量 + checkout_confirm)→ 箭頭匯入各 phase 卡。
- **上游 transport 帶(灰)**:`EventBus.publish` →(run_coroutine_threadsafe)→ `/ws/state broadcast` → 前端 `applyState`。畫成 phase 卡左側的細鏈(下行傳輸)。
- **右側 = 上行回路(灰)**:6 個觸控命令 chip(wake/order/checkout/confirm/resume/pay)→ `commands.to_token` → `input_reader.inject`(共用 input queue)→ 主線程 → **回到 emit 源**。這條就是主角金弧(閉環)。
- **note(左下或右下空角)**:核心設計 3 條 ——(1)phase-driven 唯一權威、禁前端樂觀;(2)三種觸發(語音/沉默自動/UI)殊途同歸;(3)後端故障/斷線降級回 standby 不卡死。
- **legend 左上**:6 色語意。
- 箭頭標籤壓線中段(圖①慣例);卡內容垂直置中;組件間隙 ≥30px 不相碰;標籤落卡間空白不超進卡。

## 自檢重點(render-pipeline §5)

- 上行 6 chip → commands → queue 的匯聚區(多箭頭收束)。
- 主角金弧閉環不擦過不相關卡、標籤壓自己的線。
- checkout_confirm「縮排掛 ordering」的視覺關係清楚、不被誤讀成獨立機台狀態。
- 每張 phase 卡最長文字(emit 源 + 折法 + template)不溢出 / 不截斷。
- 名稱不對齊標註(checkout_confirm↔confirm、ordering↔無 overlay)看得到。

---

## 畫圖計畫戳記（2026-06-22 重畫；全碼複核完成）

> 本檔上半「★ 核對過的硬事實」+「版面」+「signature」+「自檢重點」**即畫圖計畫**(已夠詳細,實作者直接照畫;座標近似 + lane 規則由 render 迴圈微調)。骨架 + theme 同圖①②。

**鐵則 1 複核(2026-06-22 親讀)**:後端 `machine.py`(_PHASE_BY_STATE 4 phase、_emit、paid 只 l5) + `l2_l3_dialog.py:734`(checkout_confirm 是 dialog 內 io.display 子 phase) + transport `bus.py`(publish/run_coroutine_threadsafe/loop 未綁只存) + `server.py`(uvicorn daemon) + `commands.py`(6 命令→token,**checkout→「結帳」非「結賬」**) + `models.py`(5-Literal 契約) + `display.py`(total 後端算) + `app.py`(/api/state·/ws 上行 inject·_STANDBY·bind_loop) —— **全數對得上**。前端 `app.js:271-276` applyState 折法以 spec 內逐字引用為準。

**畫布**:`.stage` **1960 × 1320**(本圖基準;5 phase 縱軸 + 左 emit 源 + 上游 transport 帶 + 右上行金弧回路 + note/legend)。

**主角**:下行 phase 驅動環(粗暖金 `.hawk` 閉環:上行觸控 → input queue → 主線程決策 → emit 新 phase → 下行換畫面)。

**畫圖必中的 3 個差異化細節**(失真即返工):① `checkout_confirm` 視覺縮排掛 `ordering` 下、標「dialog 內子 phase,非機台狀態」;② 名稱不對齊標註(後端 `checkout_confirm` ↔ 前端 overlay `"confirm"`;後端 `ordering` ↔ 前端「無 overlay」);③ 觸控只是「語音 / 沉默自動 / UI」三觸發源之一(證明「不能前端樂觀」)。
