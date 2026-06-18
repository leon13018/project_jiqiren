# WebUI Phase 2 — 觸控雙向（結構化逐筆注入）設計（Design Spec）

**日期：** 2026-06-18
**狀態：** 設計已與使用者敲定 → 轉 writing-plans 產 SDD 計畫
**對應：** roadmap `roadmaps/html_ui_plan.md` 階段路線 Phase 2；前置 Phase 0 + Phase 1 ✅（`changelogs/changelog_2026-06-18_webui.md`）
**前置 seam：** Phase 1 的 `display` 下行回呼（robot→瀏覽器）；本階段補**上行**（瀏覽器→robot），與 display 對稱。

---

## 目標（Goal）

讓 client 筆電瀏覽器的**觸控**能驅動機器人對話流程：顧客在 UI 點商品 / 去結帳 / 確認 / 付款 / 開始點餐 → 透過 WS 上行 → 注入機器人既有的單一 input queue（`input_reader.inject`，STT 已用的同一 seam）→ 對話狀態機**照常處理 + 機器人開口 ack + emit display** → 螢幕鏡像更新。完成「語音 **或** 觸控」雙模態互動閉環。

**互動模式由 A（顯示鏡像）進化到可觸控操作**，但**螢幕仍是機器人真實 cart 的鏡像**（單一事實來源 = robot）。

---

## 範圍（Scope）

**In：**
- 新 `myProgram/web/commands.py`（純 stdlib 映射：結構化 command dict → 既有對話 token 字串）。
- `web/app.py` WS handler 把 `receive_text`（Phase 1 丟棄）改為「解析命令 → `on_input(token)`」；`create_app(bus, on_input)`。
- `web/server.py` `start(bus, on_input, ...)` 透傳。
- `main.py` `_run_wiring` web 分支：`on_input = input_reader.inject` 注入。
- `webui/app.js`：live 模式觸控**改為送 WS 上行命令**（取代 Phase 1 的「一律停用」）；`sendCommand` 連線中才送、斷線 no-op。

**Out（不在 Phase 2）：**
- 商家主選單觸控（1/2/3/q／r —— 操作員留在 Pi 端鍵盤；首次進 hawk 為一次性 setup）。
- 真 OpenCV / 真掃碼器接線（`wake="c"` / `pay="s"` 維持 `TerminalSim` 模擬觸發點）。
- 「機器人說話中／聆聽中」忙碌指示燈（靠語音 ack 當回饋）。
- display DTO 加「等待確認」微狀態信號（用前端本地按鈕 affordance 解掉，不動 Phase 1 emit）。
- 多商品批次提交（方案 C，已否決）。
- 對話層任何新邏輯（觸控走既有 NLU / cart / confirm 流程，**零新對話碼**）。

---

## 決策摘要（已與使用者敲定）

| 決策 | 選擇 | 理由 |
|---|---|---|
| 觸控職權範圍 | **全模態對等**（喚醒 / 點餐 / 結帳 / 付款都能純觸控完成） | 完整雙向閉環；demo 展示力最強。 |
| 命令獲類型與 UX | **方案 A：結構化逐筆注入** | 前端送結構化意圖、後端映射 token、逐筆走對話輪流節奏。零新對話碼、WS 契約乾淨、文法留後端、螢幕純鏡像。 |
| 注入機制 | **單一 `inject` seam**（`read_terminal_key` 與 `read_customer_input` 共用同一 `input_reader` queue） | 喚醒（`"c"`）、點餐、結帳、付款全走同一條 inject；STT 已驗證此 seam。 |
| 命令映射落點 | **`web/commands.py` 純函式**（Windows-TDD） | 對齊 `display.py` 的純映射 + Pi-only 接線切分。 |
| 數量輸入 | **stepper 本地累加完才送一次** | 不產生 +1 spam，避開單 queue latest-wins drain 丟筆。 |

---

## 架構總覽：對稱雙向 seam

```
┌─ 機器人 process（python -m myProgram --web）──────────────────────────────┐
│  主執行緒: logic.run → SalesMachine（L1→dialog→L4→L5）                      │
│      read_terminal_key / read_customer_input ──┐                          │
│                                                 ├─ 皆從同一 input_reader   │
│  worker: tts / action / input_reader / stt      │   queue 取（read）        │
│  worker: uvicorn（FastAPI app, 0.0.0.0:8137）   │                          │
│                                                 ▼                          │
│  ▼ 下行（Phase 1）                        ▲ 上行（Phase 2 新增）             │
│  display(phase,cart,paid)→bus→WS送瀏覽器   on_input(token)=input_reader.inject │
│                                            ▲                               │
└────────────────────────────────────────────┼─────────────────────────────┘
        WS push（下行 DisplayState）           │ WS receive（上行命令 JSON）
                          同 wifi client 筆電瀏覽器（app.js）
                  觸控 → sendCommand(JSON) ──上行──┘   ；onmessage(DisplayState) → render
```

**核心原則：螢幕永遠鏡像機器人回送的真實 cart**。觸控只送「意圖」、不本地改 cart；cart 一律等機器人 emit 的 display state 才變（避免 optimistic state 與 robot 背離）。觸控與語音真正對等（同一條 inject queue）。

---

## 元件（沿用 Phase 1 可測性切分）

### 1. `myProgram/web/commands.py`（全新，純 stdlib，**Windows-TDD**）

純映射函式，無 fastapi / pydantic / 業務副作用：

```python
def to_token(cmd: dict) -> str | None:
    """結構化觸控命令 → 對話狀態機既有消費的 token 字串；非法/未知 → None（忽略）。"""
```

| 上行命令 dict | → token 字串 | 機器人端既有處理 |
|---|---|---|
| `{"type": "wake"}` | `"c"` | `read_terminal_key` → 模擬 OpenCV dwell → L1 hawk→L2 |
| `{"type": "order", "item": <PRODUCTS key>, "qty": <int>}` | `f"{item}{qty}"`（如 `"冰紅茶3"`） | `read_customer_input` → `product_parser` 加 cart |
| `{"type": "checkout"}` | 結賬 token（取自 `constants/keywords` CHECKOUT 字集） | C-2 三選一 CHECKOUT 路徑 |
| `{"type": "confirm"}` | 確認 token（CONFIRM-YES 字集，如「正確」） | `_dialog_checkout_confirm` |
| `{"type": "pay"}` | `"s"` | L4 掃碼模擬 → L5 |

- **品名驗證**：`order` 的 `item` 必須是 `PRODUCTS` 的 key，否則 `None`（防呆）。
- **數量驗證**：`qty` 須為正整數；非法 → `None`（上限交由既有 `invalid_qty_reask` 鏈處理，commands 層不重複）。
- **token 來源**：結賬 / 確認 token 取自 `sales.constants`（不寫死中文，跟既有 keyword 集同步）；`wake="c"` / `pay="s"` 是 `TerminalSim` 模擬約定。
- **sim-token 耦合註記**：`"c"`（模擬 OpenCV）/ `"s"`（模擬掃碼）非 sales 領域常數，是 wire-up 層約定。本專案目前無真 OpenCV / 掃碼器 → 這兩個就是實際觸發點，接受耦合並加註解；未來接真硬體時改這兩個映射（與 sales 領域 token 解耦）。

### 2. `web/app.py` WS handler（改，Pi-only）

- `create_app(bus, on_input)` 多收一個 `on_input: Callable[[str], None]`。
- WS `/ws/state` 的 `receive_text` 由 Phase 1 的「忽略」改為：
  ```python
  raw = await ws.receive_text()
  try:
      token = commands.to_token(json.loads(raw))
  except Exception:
      token = None            # 壞 JSON / 非 dict → 忽略
  if token is not None:
      on_input(token)         # = input_reader.inject（thread-safe queue.put）
  ```
- `on_input` 由 uvicorn loop 執行緒呼叫、`input_reader` queue 由機器人主執行緒讀 → `queue.Queue` 本身 thread-safe，無需加鎖。
- 下行 broadcast（`bus._broadcast`）與本上行 `receive_text` 在同一 WS 並行 send/receive —— Phase 1 已用此型態（receive 當時只是丟棄），不引入新並行風險。

### 3. `web/server.py`（改，Pi-only）

- `start(bus, on_input, host="0.0.0.0", port=8137)` 透傳 `on_input` 給 `create_app`。

### 4. `main.py _run_wiring`（改，wire-up）

- web 分支內：`from myProgram import input_reader` → `on_input = input_reader.inject` → `web_server.start(bus, on_input, port=8137)`。
- 缺依賴 / 啟動失敗 graceful 分支不變（Phase 1 既有）。

### 5. `webui/app.js`（改，前端）

- **取代 Phase 1 停用**：Phase 1 hardening 的 `if (App._live && act !== "adGoto") return;`（一律停用 live 觸控）→ 改為「live 模式把該 act 轉成結構化命令並 `sendCommand`，**不**本地 setState」。`?demo=1` 仍走本地 setState（開發工具）。
- **`sendCommand(cmd)`**：連線中（WS open）才 `ws.send(JSON.stringify(cmd))`；斷線 → no-op（保留 Phase 1「斷線右上角顯示重新連線中、不跳轉」修正）。
- **act → 命令映射**（前端）：
  - 「開始點餐」（welcome 頁，連線中）→ `{type:"wake"}`；導航**仍由機器人回送的 phase 驅動**（不本地跳轉，延續 Phase 1 修正）。
  - 商品 stepper 累加 + 加入 → `{type:"order", item, qty}`。
  - 「去結帳」→ `{type:"checkout"}`；送出後**本地**把按鈕換成「確認金額」affordance（純按鈕狀態，不碰 cart）。
  - 「確認金額」→ `{type:"confirm"}`。
  - 「付款」（checkout 頁）→ `{type:"pay"}`。
- **cart 顯示仍純鏡像**：stepper 的數量是本地預選 UI；提交後的 cart 一律等機器人 emit 的 DisplayState 才更新（與 Phase 1 渲染路徑一致）。

---

## 資料流（含結帳兩拍 choreography）

1. **喚醒**：welcome [開始點餐]（連線中）→ `{wake}` → `"c"` → L1 hawk→L2 → robot emit `ordering` → 螢幕跳點餐頁（導航由機器人驅動）。
   - *前提*：`"c"` 僅 hawk 模式有效。首次開機顯示商家主選單，操作員在 Pi 按 `1` 進 hawk（一次性 setup）；之後每輪交易結束自動回 hawk。
2. **點餐**：stepper 累加數量 → [加入] → `{order,冰紅茶,3}` → `"冰紅茶3"` → product_parser 加 cart → robot 語音 ack + emit cart → 螢幕長出該列。
3. **結帳（兩拍）**：[去結帳] → `{checkout}` → 結賬 token → robot 問「總共X元，正確嗎」；前端本地換按鈕為 [確認金額] → [確認] → `{confirm}` → 正確 token → 進 L4 → emit `checkout`（QR）。
4. **付款**：checkout 頁 [付款] → `{pay}` → `"s"` → L5 → emit `thankyou`。

---

## 衝突 / 邊緣處理

- **語音 + 觸控同時**：兩者進同一 queue，`input_reader.read` 的 latest-wins drain 自然序列化。demo 為單一顧客、實際不會真同步；可接受丟其一。輪流節奏（做一個動作 → 等機器人 ack → 做下一個）與語音對話一致。
- **無 +1 spam**：數量在 stepper 本地累加完才送一次 → 不產生多筆 race。
- **斷線**：`sendCommand` 連線中才送、斷線一律 no-op（右上角「重新連線中」）→ 完整保留 Phase 1「斷線卡歡迎頁、不跳轉」修正。
- **喚醒前提**：見資料流 1（hawk 模式 / 一次性 setup）。
- **非法 / 未知命令**：`to_token` 回 `None` 即忽略（壞 JSON、非 dict、未知 type、非法品名 / 數量都不 raise）。
- **graceful**：上行處理全程吞例外（鏡像 `display.py` 哲學）—— web 殼出錯絕不拖垮對話執行緒。

---

## 測試策略

> **本機禁裝依賴紅線**：fastapi / uvicorn / pydantic 在 Windows 裝不了。對策同 Phase 1：純映射邏輯（`commands.py`）走 stdlib dict → Windows-TDD；import fastapi 的接線（`app.py` / `server.py`）留 Pi 驗。

- **Windows pytest（純 stdlib，不 import fastapi/pydantic）**：
  - `tests/web/test_commands.py`：每種 command → 正確 token（wake→`"c"`、order→`"冰紅茶3"`、checkout→結賬 token、confirm→確認 token、pay→`"s"`）；未知 type / 壞 dict / 非法品名 / 非法數量 → `None`；token 取自 constants（不寫死）。
  - main.py：`_run_wiring` web 分支可 patch（不觸發 uvicorn import）；`on_input` 正確接到 `input_reader.inject`。
- **Pi-only（import fastapi/uvicorn）**：`app.py` WS receive 接線、`server.py` 透傳 → `ast.parse` 靜態 + Pi 實機驗收（觸控走完 喚醒→點→結→付，螢幕鏡像正確、語音 ack 正常）。
- **既有測試**：上行 seam 是**加法**、對話層零改 → 現有 635 測試不受影響（`create_app` 多收 `on_input` 為新參數，Phase 1 的 app/server 測試若有需同步傳入 stub）。
- **Iron Law**：沒跑 `python -m pytest tests/` 通過不得宣告完成。

---

## Pi 依賴

- **零新依賴**：完全沿用 Phase 1 已裝的 `fastapi` + 純 `uvicorn`（上行只是用既有 WS 的 receive 方向 + 純 stdlib 映射）。`requirements/raspberry_pi_setup.md` 無需新增。

---

## 風險與緩解

| 風險 | 緩解 |
|---|---|
| 結帳兩拍 token 與既有 keyword 集不符（結賬 / 正確命中錯路徑） | `commands.py` token 取自 `constants/keywords` 同一字集；writing-plans 對照 `sales-dialog-design.md` C-2 / `_dialog_checkout_confirm` 確認 token。 |
| 喚醒 `"c"` 在非 hawk 狀態無效、使用者困惑 | spec 註明一次性 setup；前端斷線/未喚醒時 UI 給明確狀態（重新連線中 / 等待開始）。 |
| 跨執行緒注入（uvicorn loop → 機器人 queue） | `queue.Queue.put` thread-safe，無需鎖；STT inject 已驗證同模式。 |
| 前端 live 觸控誤改本地 state 造成與 robot 背離 | live 模式一律只 `sendCommand`、不 setState；cart 只認機器人 emit。 |
| 多 client 同時送命令 | queue thread-safe；demo 單顯示為主，不做 per-session（沿用 Phase 1）。 |

---

## 範圍外 / 後續

- **真 OpenCV / 掃碼器**：接真硬體時 `wake` / `pay` 映射改為真觸發、與 sim token 解耦。
- **忙碌 / 聆聽指示**：若 demo 體感需要，再加 robot→瀏覽器的「說話中 / 聆聽中」信號。
- **商家端遠端控制**：目前主選單留 Pi 鍵盤，未來可加受控的商家面板。

---

## 開放問題（writing-plans 前確認）

1. **結賬 / 確認 token 取哪個字**：writing-plans 對照 `constants/keywords.py` 取「最不會誤命中」的代表字（如結賬用 CHECKOUT strict 字、確認用 CONFIRM-YES 字「正確」）；commands.py 引用常數而非寫死。
2. **前端 act 名稱對應**：現有 `app.js` 的 `data-act` 值（add/inc/dec/adGoto/checkout…）逐一對應到上行命令，由 writing-plans 依現行 app.js 實際 act 名落定。
3. **`create_app` 既有 Pi-only 測試**：若 Phase 1 已有 app/server 的 Pi 驗腳本，writing-plans 同步補 `on_input` stub 參數。
