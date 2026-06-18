# WebUI Phase 1 — FastAPI 顯示鏡像後端 設計（Design Spec）

**日期：** 2026-06-18
**狀態：** 設計待使用者複審 → approved 後轉 writing-plans 產 SDD 計畫
**對應：** roadmap `roadmaps/html_ui_plan.md` 階段路線 Phase 1；前置 Phase 0 ✅（`changelogs/changelog_2026-06-18_webui.md`）
**前置契約：** `architecture/frontend-backend-contract.md`（本 spec 落實其 FastAPI + WS 願景；契約部分網路/拓樸內容仍適用）

---

## 目標（Goal）

讓 Raspberry Pi 上跑的機器人主程式（`python -m myProgram` 點餐狀態機），把**點餐 / 購物車 / 結帳 / 感謝**的即時狀態，透過 **FastAPI（REST 初始快照 + WebSocket 事件推送）** 推給同 wifi 的 client 筆電瀏覽器，讓 Phase 0 的 Glaze 玻璃 UI **即時鏡像**機器人對話進度（顧客語音點一項 → 畫面購物車就長一項）。

**互動模式 A（顯示鏡像）**：瀏覽器是被動顯示端，WS 狀態權威；觸控加/減在 live 模式停用（觸控→機器人雙向留 Phase 2）。

---

## 範圍（Scope）

**In：**
- 新 `myProgram/web/` transport 套件（FastAPI app + DTO + 事件匯流排 + uvicorn 背景執行緒啟動）。
- `sales/` 新增 `display` 事件回呼（第 15 個 callback），在狀態 / 購物車變動點 emit；終端模式 no-op。
- `main.py` web 模式佈線（啟動 web server 執行緒、注入 `display`→bus）。
- `app.js` 前端：WS client 收狀態 → render；`phase`→view 映射；商品改由後端 catalog 餵（前端只留 name→{icon,tone} 呈現表）。
- Windows pytest 涵蓋純邏輯（DTO / bus / display 映射）；Pi 端 fastapi/uvicorn 安裝 + 實機整合驗收（pineedtodo）。

**Out（不在 Phase 1）：**
- 觸控 / 任何 client→機器人回傳（Phase 2 雙向事件注入）。
- 真 QR 金流串接（QR 維持前端依金額生成的 demo 條碼）。
- Pi 自帶瀏覽器相容（OKLCH→sRGB fallback）——Phase 0 已裁決 demo 走 client 筆電。
- 資料庫（商品仍兩個，記憶體 dict）。

---

## 決策摘要（已與使用者敲定）

| 決策 | 選擇 | 理由 |
|---|---|---|
| 傳輸層 | **FastAPI + uvicorn**（process 內背景執行緒） | 契約原訂；REST + WS + Pydantic 契約驗證、架構正規、學習價值。代價：Pi 新依賴 + 實機驗 build。 |
| 模組落點 | **`myProgram/web/`**（獨立 transport 套件） | 與 `sales/` 分離，業務碼不知道 web 存在（分層解耦）。 |
| 增量大小 | **一個完整 live mirror 增量** | 購物車明細才是畫面重點，拆步第一步畫面是空的。 |
| 狀態觀測 | **事件回呼 `display` 穿透 `sales/`**（非輪詢） | 純事件驅動、零輪詢延遲。代價：blast radius 進 621 測試核心較大（使用者明確接受）。 |
| 觸控 | live 模式**停用**（純鏡像） | 模式 A；雙向留 Phase 2。 |

---

## 架構總覽

```
┌─ 機器人 process（python -m myProgram --web）─────────────────────────┐
│  主執行緒: logic.run → SalesMachine（L1→dialog→L4→L5 狀態機）         │
│      每進新層 / 每次 cart 變動 → 呼叫 display(phase, cart, paid)       │
│  worker 執行緒: tts / action / input / stt                           │
│  ★ 新 worker 執行緒: uvicorn（FastAPI app, 0.0.0.0:8137）            │
│                                                                      │
│  display callback（web 版）──push──▶ web/bus（執行緒安全）            │
│                                  └─ run_coroutine_threadsafe ─▶ WS   │
└──────────────────────────────────────────────┬───────────────────────┘
                                  WS push / REST snapshot │
                              同 wifi client 筆電瀏覽器（app.js）
                              fetch /api/state（初始）+ WS /ws/state（增量）
```

**關鍵橋接**：`display` 由**同步機器人執行緒**呼叫，要送到 **uvicorn async loop** 管理的 WS 連線 → 用 `asyncio.run_coroutine_threadsafe(bus.broadcast(state), loop)`（標準 sync→async 跨執行緒橋）。這是 Phase 1 主要技術風險點。

---

## 元件

### 1. `myProgram/web/` 套件（全新，不動既有 .py）

- **`models.py`** — Pydantic DTO（見「DTO / 契約」）。
- **`bus.py`** — `EventBus`：持目前 `DisplayState`（last-known，給新連線初始快照）+ 已連線 WS 集合；`publish(state)`（機器人執行緒呼叫，經 `run_coroutine_threadsafe` 排到 loop 廣播）+ `broadcast()`（async，送所有 WS，斷線者剔除）。
- **`app.py`** — FastAPI app：
  - `GET /` + 靜態檔：`StaticFiles` 掛 `myProgram/webui/`（出 index.html / app.js / tokens…）。
  - `GET /api/state` → `Snapshot{ catalog, state }`（catalog 由 `sales/constants/products.py` `PRODUCTS` 建；state = bus last-known）。
  - `WS /ws/state` → accept 後先送 last-known，再 subscribe bus，逐筆 `send_json(DisplayState)`；斷線清理。
- **`server.py`** — `start(bus) -> thread`：在背景執行緒跑 `uvicorn.Server(config).run()`（`install_signal_handlers=False`，非主執行緒）；`stop()` 優雅關閉，併入 main() finally 的 worker shutdown 鏈。
- **`__init__.py`**、**`.claude/code_map.md`**（新層索引）、**`CLAUDE.md`**（薄導引指回 root）。

### 2. `display` 事件回呼 seam（動 `sales/` → SDD）

- **callback 契約**：`display(phase: str, cart: dict[str, int], paid: int = 0) -> None`
  - `phase ∈ {"standby","ordering","checkout","thankyou"}`；`cart` = 商品名→數量快照（傳 `dict(cart)` 拷貝，避免跨執行緒看到後續突變）；`paid` 僅 thankyou 帶。
  - **終端模式**：no-op（`TerminalSim.display` 空實作，保留純終端輸出乾淨）。
  - **web 模式**：`WebSim.display` 建 `DisplayState`（total 由 cart×PRODUCTS 實際價算）→ `bus.publish(state)`。
- **注入**：`logic.run(..., display=...)` 多收一個 callback，放進 callbacks dict 傳給 `SalesMachine`；`SalesMachine` 與相關 state 在變動點呼叫。
- **emit 點**（writing-plans 細化確切行；原則如下）：
  1. `machine.py SalesMachine.run()`：每進新層 emit phase 轉移（`l1`→standby、`dialog`→ordering、`l4`→checkout、`l5`→thankyou）。涵蓋大多數 view 變化 + 邊界 cart 快照。
  2. `states` dialog 層 + `_l2_l3_qty_followup`：每次顧客一輪確認加入 cart 後 emit（ordering + 最新 cart）→ **購物車逐項長出來的增量鏡像**。
  3. `l5`：emit thankyou 時 `paid = calc_total(cart)`（在 L5 清 cart 前算）。
  4. cart 清空（dialog reject / L4 cancel）→ 機台轉 `l1` 的 emit 自然帶空 cart → standby。
- **不變量**：emit 純附加、不改任何既有回傳 shape / 控制流；既有 621 測試行為零改變（display 預設 no-op stub 即可全綠）。

### 3. 前端 `app.js` 改造

- **連線**：`DOMContentLoaded` → `fetch('/api/state')` 拿 `{catalog, state}` → 存 catalog（name→{unit,priceNow,priceOrig}）→ 首次 render → 開 `new WebSocket('ws://'+location.host+'/ws/state')` → `onmessage` 把 `DisplayState` 映射進 `App.state` 後 render。斷線 → 指數退避重連 + 頁面角落「重新連線中」提示。
- **phase→view 映射**：`standby`→`{standby:true}`；`ordering`→`{standby:false, overlay:null}`（empty/filled 由 cart count 衍生）；`checkout`→`{overlay:"checkout"}`；`thankyou`→`{overlay:"thankyou", paidTotal: state.paid}`。
- **商品來源**：`products()` 改讀後端 catalog（name 當 id）；新增 name→{icon,tone} **呈現表**（Glaze 視覺留前端，後端只給資料）。現有 hardcode 商品退為 `?demo=1` fallback。
- **live 模式觸控停用**：`bindEvents` 的 add/inc/dec 在 live 模式略過（WS 權威）；`?demo=1` 保留 demo 切換器 + 本機觸控當開發工具。

### 4. 啟動模式與 process 模型

- **模式選擇**：`python -m myProgram --web`（或 `MYPROGRAM_WEB=1`）→ main.py 用 `WebSim`（含 web `display`）+ 啟 `web.server`；無旗號 = 現行 `TerminalSim`（display no-op）、不啟 server、零行為改變。
- **執行緒**：uvicorn 背景執行緒隨 worker 一起起；main() finally shutdown 鏈加 `web.server.stop()`。`display` 於機器人主執行緒同步呼叫（極輕：建 model + `run_coroutine_threadsafe` 排程即返回，不阻塞對話）。

---

## DTO / 契約（`web/models.py`）

```python
from typing import Literal
from pydantic import BaseModel

class Product(BaseModel):
    name: str          # = PRODUCTS key（"冰紅茶" / "刮刮樂"）
    unit: str          # PRODUCTS[name]["單位"]
    price_now: int     # ["實際"]
    price_orig: int    # ["原價"]

class DisplayState(BaseModel):
    phase: Literal["standby", "ordering", "checkout", "thankyou"]
    cart: dict[str, int]   # 商品名 → 數量
    total: int             # = Σ price_now × qty（後端算，權威）
    paid: int = 0          # 僅 thankyou 帶

class Snapshot(BaseModel):
    catalog: list[Product]
    state: DisplayState
```

`cart` 用 `dict[str,int]` 直接對齊後端 `Cart` 型別；前端用 catalog 補價格/單位/小計、用呈現表補 icon/tone。

---

## 錯誤處理

- **WS 斷線**：前端指數退避重連；後端 broadcast 時 catch 單一連線送失敗 → 剔除該連線、不影響其他。
- **server 執行緒隔離**：uvicorn 執行緒例外不得拖垮機器人主迴圈；`display` 內部 try/except 吞 web 端錯誤（web 掛了機器人照常服務客人）。
- **Pi 缺依賴 graceful**：`--web` 但 fastapi/uvicorn 未裝 → 印明確錯誤訊息並**退回無 web 模式繼續跑**（對齊既有 lazy-import / 缺套件 graceful 慣例），不讓機器人開不了機。
- **跨執行緒 cart 快照**：`display` 一律傳 `dict(cart)` 拷貝，避免 web 執行緒讀到對話中途突變的 cart。

---

## 測試策略

- **Windows pytest（純邏輯，無 uvicorn/Pi）**：
  - `web/models.py` DTO 驗證、`WebSim.display`→`DisplayState` 映射（phase/total/paid 正確）、`bus` publish/last-known/斷線剔除（用 fake WS）。
  - `sales/` emit：在既有 machine/dialog 測試注入 spy `display` stub，斷言「進 l4 emit checkout」「dialog 加單 emit ordering+正確 cart」「l5 emit thankyou+paid」等；既有 621 測試以 no-op display 全綠（零行為改變）。
  - main.py：`_build_callbacks` 不啟 server（lazy）；web 模式 factory 可被 patch。
- **Pi 端整合（實機，pineedtodo）**：裝 fastapi/uvicorn → `python -m myProgram --web` → client 筆電連 `raspberrypi.local:8137` → 走一輪點餐，確認購物車/結帳/感謝即時鏡像 + 斷線重連。
- **Iron Law**：沒跑 `python -m pytest tests/` 通過不得宣告完成（改了 sales/ → Stop hook 守）。

---

## Pi 依賴

- 新增 `fastapi` + `uvicorn`（連帶 starlette / pydantic）→ 記入 `requirements/raspberry_pi_setup.md`。
- **build 風險**（契約標註 `pi-glibc-piwheels-trap`）：Pi 上 `pip install fastapi uvicorn` 可能要 source build / piwheels；**writing-plans 第一個 Pi 任務 = 實機驗證安裝成功**，失敗則回頭評估替代（websockets-only / SSE 降級）。
- 裝**純 `uvicorn`（非 `uvicorn[standard]`）**→ 純 Python asyncio + `h11`，避開 `uvloop`/`httptools` C 擴充的 Pi wheel 風險；spec 不要求 uvloop。

---

## 風險與緩解

| 風險 | 緩解 |
|---|---|
| sync→async 橋（`run_coroutine_threadsafe`）寫錯 → 推不出/卡死 | 先寫 bus + 橋的單元測試（fake loop）；Pi 前先在 Windows 驗 WS 推送。 |
| uvicorn 在非主執行緒（signal handler） | `install_signal_handlers=False`；shutdown 由 main() 主導。 |
| Pi 裝不起 fastapi/uvicorn | writing-plans 首個 Pi 任務先驗安裝；有降級備案。 |
| 動 sales/ 弄壞 621 測試 | display 純附加 no-op 預設；每個 emit 點配 spy 測試；走完整 SDD + 三段審。 |
| WS 推送頻率過高（每 cart 變動） | 對話節奏本來就慢（每輪數秒），頻率低；必要時 bus 端 coalesce。 |

---

## 範圍外 / 後續

- **Phase 2**：觸控→機器人雙向（client 在 UI 加單 → 注入機器人 input queue，類似 STT inject seam）；可能要結構化 command 注入點。
- **真 QR / 金流**：目前 QR 是前端依金額生成的 demo 條碼。
- **多 client 一致性**：目前 broadcast 給所有連線（展場一個顯示為主），未做 per-session。

---

## 開放問題（writing-plans 前確認）

1. **port**：沿用 Phase 0 的 `8137`（FastAPI 取代 serve.py 出靜態），還是換 contract 慣例 `8000`？（建議沿用 8137，pineedtodo / 使用者肌肉記憶已熟。）
2. **`--web` 旗號 vs 環境變數**：CLI 旗號（`python -m myProgram --web`）較顯式，建議用旗號。
3. emit 確切行位置（哪幾個 state 檔）由 writing-plans 逐點定，但本 spec 的 emit 原則已框定。
