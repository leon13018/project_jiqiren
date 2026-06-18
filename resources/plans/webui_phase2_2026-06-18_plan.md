# WebUI Phase 2 — 觸控雙向（結構化逐筆注入）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 client 瀏覽器觸控（喚醒 / 點餐 / 結帳 / 確認 / 付款）經 WS 上行注入機器人既有 input queue，完成語音或觸控雙模態互動閉環，且螢幕仍純鏡像機器人真實 cart。

**Architecture:** 與 Phase 1 `display` 下行對稱的上行 seam。觸控 → WS 上行 JSON 命令 → `web/commands.to_token()` 純映射成既有對話 token → `on_input`（=`input_reader.inject`）→ 既有單一 input queue → 對話狀態機照常處理（**零新對話碼**）+ 機器人語音 ack + emit display → 螢幕鏡像更新。

**Tech Stack:** Python 3.11（FastAPI WS receive，Pi-only）、純 stdlib 映射（Windows-TDD）、buildless JS（前端，Pi 視覺驗收）。

## Global Constraints

> 以下每條為專案紅線 / spec 全域要求，**每個 task 隱含適用**（值逐字照抄）：

- **繁體中文**：所有程式碼註解、字串輸出、文件、commit message、markdown 內中文一律繁中（成果在中國台灣展示）。
- **Windows 禁裝依賴**：`pip` / `npm` / `apt` 一律不在本機裝（pytest 已全域裝為例外）。`fastapi` / `uvicorn` / `pydantic` Windows 裝不了。
- **可測性切分**：`web/commands.py` 純 stdlib（不 import fastapi/pydantic）→ Windows pytest 全覆蓋；`web/app.py` / `web/server.py` import fastapi/uvicorn → **Pi-only，Windows 只能 `ast.parse` 驗語法**，真驗在 Pi。
- **不改廠商 SDK**：`myProgram/vendor/*` 🔒 禁改。
- **不用 `git add -A` / `git add .`**：每次 commit 明確列檔名。
- **零新對話碼**：觸控走既有 NLU / cart / confirm 流程，不得新增對話層意圖 / state。
- **add-only 約束**：機器人對話無「刪除 / 減量單品」customer 路徑（`cart.減` 未接任何輸入）→ 觸控亦無減量；live 模式購物車欄唯讀（無 `−` 鈕），點餐用本地預選 stepper + 加入（送 add-N）。語音同樣不能減量 → 對等成立。
- **token membership**：`commands.py` 的結帳 / 確認 token 必須是對應 keyword 常數集（`KEYWORDS_C2_CHECKOUT` / `KEYWORDS_CONFIRM_YES`）的成員，由 test 守 membership 防漂移。
- **Iron Law**：沒跑 `python -m pytest tests/` 全綠不得宣告完成。
- **結構變動更新 code_map**：新增檔案 → 同步更新該層 `.claude/code_map.md`（Stop hook 守）。

---

## File Structure

| 檔案 | 動作 | 職責 |
|---|---|---|
| `myProgram/web/commands.py` | Create | 純映射：結構化命令 dict → 對話 token 字串；非法→None。Windows-TDD。 |
| `tests/web/test_commands.py` | Create | `to_token` 全行為 + token membership + 回 parse_products 反解 guard。 |
| `myProgram/web/app.py` | Modify | `create_app(bus, on_input)`；WS `receive_text` → `to_token` → `on_input`。Pi-only。 |
| `myProgram/web/server.py` | Modify | `start(bus, on_input, host, port)` 透傳。Pi-only。 |
| `myProgram/main.py` | Modify | `_run_wiring` web 分支：`on_input = input_reader.inject` 注入 `start`。 |
| `tests/stt/test_main_wireup.py` | Modify | 更新既有 web start 簽章測試 + 新增 on_input 接線斷言。 |
| `myProgram/webui/app.js` | Modify | live 模式觸控改送 WS 上行命令（取代 Phase 1 停用）+ 本地預選 stepper + 確認 gate。前端，Pi 視覺驗收。 |
| `myProgram/web/.claude/code_map.md` | Modify | 加 `commands.py` 索引。 |
| `tests/.claude/code_map.md` | Modify | 加 `test_commands.py` 索引。 |
| `resources/pineedtodo/2026-06-18_webui_phase2_verify.md` | Create | Pi 端整合驗收指示。 |
| `resources/changelogs/changelog_2026-06-18_webui.md` 等 | Modify | 收尾文件（Task 6）。 |

**Interfaces（跨 task 契約）：**
- `commands.to_token(cmd: dict) -> str | None`（Task 1 產出 → Task 2 消費）。
- `create_app(bus, on_input) -> FastAPI`（Task 2 改簽章 → Task 2 server 消費）。
- `server.start(bus, on_input, host="0.0.0.0", port=8137) -> (server, thread)`（Task 2 → Task 3 main 消費）。
- 前端上行命令 schema（Task 1 對應 / Task 4 產出）：`{"type":"wake"}` / `{"type":"order","item":<PRODUCTS key>,"qty":<正整數>}` / `{"type":"checkout"}` / `{"type":"confirm"}` / `{"type":"pay"}`。

---

## Task 1: `web/commands.py` 純映射 + 測試（Windows-TDD）

**Files:**
- Create: `myProgram/web/commands.py`
- Test: `tests/web/test_commands.py`
- Modify: `myProgram/web/.claude/code_map.md`、`tests/.claude/code_map.md`

**Interfaces:**
- Produces: `to_token(cmd: dict) -> str | None`。

- [ ] **Step 1: 寫失敗測試**

`tests/web/test_commands.py`：
```python
"""web/commands.to_token 純映射行為（Windows pytest；不 import fastapi/pydantic）。"""
from myProgram.web.commands import to_token
from myProgram.sales.constants import KEYWORDS_C2_CHECKOUT, KEYWORDS_CONFIRM_YES
from myProgram.sales.product_parser import parse_products


def test_wake_maps_to_c():
    assert to_token({"type": "wake"}) == "c"


def test_pay_maps_to_s():
    assert to_token({"type": "pay"}) == "s"


def test_order_builds_product_qty_token():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": 3}) == "冰紅茶3"


def test_order_token_parses_back_to_product_qty():
    """守 token 格式：產出的字串必須被既有 product_parser 正解回 (商品, 數量)。"""
    token = to_token({"type": "order", "item": "刮刮樂", "qty": 2})
    assert parse_products(token) == [("刮刮樂", 2)]


def test_checkout_token_is_member_of_keyword_set():
    assert to_token({"type": "checkout"}) in KEYWORDS_C2_CHECKOUT


def test_confirm_token_is_member_of_keyword_set():
    assert to_token({"type": "confirm"}) in KEYWORDS_CONFIRM_YES


def test_unknown_type_returns_none():
    assert to_token({"type": "bogus"}) is None


def test_missing_type_returns_none():
    assert to_token({}) is None


def test_non_dict_returns_none():
    assert to_token("冰紅茶3") is None
    assert to_token(None) is None
    assert to_token(["order"]) is None


def test_order_invalid_product_returns_none():
    assert to_token({"type": "order", "item": "珍奶", "qty": 2}) is None


def test_order_missing_item_or_qty_returns_none():
    assert to_token({"type": "order", "qty": 2}) is None
    assert to_token({"type": "order", "item": "冰紅茶"}) is None


def test_order_nonpositive_qty_returns_none():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": 0}) is None
    assert to_token({"type": "order", "item": "冰紅茶", "qty": -1}) is None


def test_order_non_int_qty_returns_none():
    assert to_token({"type": "order", "item": "冰紅茶", "qty": "3"}) is None
    # bool 是 int 子型別（True==1）→ 須明確擋掉，避免 {"qty": true} 變成 "冰紅茶1"
    assert to_token({"type": "order", "item": "冰紅茶", "qty": True}) is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/web/test_commands.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'myProgram.web.commands'`。

- [ ] **Step 3: 實作 `commands.py`**

`myProgram/web/commands.py`：
```python
"""觸控上行命令 → 對話狀態機既有消費的 token 字串（純映射，Windows-TDD）。

職責：把瀏覽器送來的結構化命令 dict 翻成「機器人既有 read 路徑會處理的字串」，
經 web/app.py 的 WS receive 餵 input_reader.inject —— 對話層零改動、零新意圖碼。

純 stdlib（無 fastapi / pydantic / 副作用）；只 import sales 常數取 token 與商品驗證。
非法 / 未知命令一律回 None（caller 忽略，不 raise）。
"""
from myProgram.sales.constants import (
    PRODUCTS,
    KEYWORDS_C2_CHECKOUT,
    KEYWORDS_CONFIRM_YES,
)

# 結帳 / 確認 token：取自既有 keyword 集的代表字（test 守 membership，避免日後漂移）。
# 「結賬」∈ KEYWORDS_C2_CHECKOUT（C-2 三選一 CHECKOUT 路徑）；
# 「正確」∈ KEYWORDS_CONFIRM_YES（_dialog_checkout_confirm 的 YES）。
_CHECKOUT_TOKEN = "結賬"
_CONFIRM_TOKEN = "正確"
# 模擬硬體觸發點（TerminalSim 約定，非 sales 領域常數）：
#   wake = 模擬 OpenCV 偵測顧客（read_terminal_key 認 'c' → L1 hawk→L2）
#   pay  = 模擬掃碼付款（read_customer_input 認 's' → L4→L5）
# 本專案目前無真 OpenCV / 掃碼器 → 這兩個就是實際觸發點。未來接真硬體時改這兩個
# 映射（與領域 token 解耦），對話層不受影響。
_WAKE_TOKEN = "c"
_PAY_TOKEN = "s"


def to_token(cmd):
    """結構化觸控命令 dict → token 字串；非法 / 未知 / 非 dict → None。"""
    if not isinstance(cmd, dict):
        return None
    ctype = cmd.get("type")
    if ctype == "wake":
        return _WAKE_TOKEN
    if ctype == "pay":
        return _PAY_TOKEN
    if ctype == "checkout":
        return _CHECKOUT_TOKEN
    if ctype == "confirm":
        return _CONFIRM_TOKEN
    if ctype == "order":
        item = cmd.get("item")
        qty = cmd.get("qty")
        if item not in PRODUCTS:
            return None
        # bool 是 int 子型別 → 明確排除，避免 True 被當 1
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            return None
        return f"{item}{qty}"
    return None
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/web/test_commands.py -v`
Expected: PASS（全部）。

- [ ] **Step 5: 更新 code_map**

`myProgram/web/.claude/code_map.md` —— 在「檔案（純 stdlib，Windows 可 pytest）」段 `display.py` 後加一行：
```markdown
- `commands.py` — `to_token(cmd: dict) -> str | None`：觸控上行結構化命令 → 對話既有消費的 token 字串（wake→`c`、order→`{品名}{數量}`、checkout/confirm→keyword 集代表字、pay→`s`）；非法→None。只 import sales 常數，無 fastapi/pydantic。
```

`tests/.claude/code_map.md` —— 在 `tests/web/` 段加一行：
```markdown
- `tests/web/test_commands.py` — `to_token` 映射全行為（各命令→token、未知/非法→None、結帳/確認 token membership、order token 反解 parse_products）。
```

- [ ] **Step 6: Commit**

```bash
git add myProgram/web/commands.py tests/web/test_commands.py myProgram/web/.claude/code_map.md tests/.claude/code_map.md
git commit -m "feat(web): Phase 2 commands.to_token 觸控上行命令→對話 token 純映射"
```

---

## Task 2: `web/app.py` + `web/server.py` 上行接線（Pi-only）

**Files:**
- Modify: `myProgram/web/app.py`（`create_app` 簽章 + WS receive）
- Modify: `myProgram/web/server.py`（`start` 簽章透傳）

**Interfaces:**
- Consumes: `commands.to_token`（Task 1）。
- Produces: `create_app(bus, on_input)`、`server.start(bus, on_input, host="0.0.0.0", port=8137)`。

> **可測性**：兩檔 import fastapi/uvicorn，Windows 無法 pytest/import → 本 task 驗證 = `ast.parse` 語法 + 人工對照；真 import/行為驗證在 Task 5（Pi 整合）。

- [ ] **Step 1: 改 `app.py` 的 `create_app` 簽章 + WS receive 路由**

`myProgram/web/app.py` 頂部 import 區加 `import json`（與既有 `import asyncio` 同區）+ `from myProgram.web import commands`（與既有 `from myProgram.web.models import ...` 同區）。

把 `def create_app(bus) -> FastAPI:` 改為 `def create_app(bus, on_input) -> FastAPI:`，並把 WS handler 內的純忽略迴圈：
```python
            while True:
                await ws.receive_text()              # 模式 A：忽略 client 訊息，只維持連線
```
改為：
```python
            while True:
                raw = await ws.receive_text()        # Phase 2：上行觸控命令
                try:
                    token = commands.to_token(json.loads(raw))
                except Exception:
                    token = None                     # 壞 JSON / 非 dict → 忽略（不拖垮連線）
                if token is not None:
                    on_input(token)                  # = input_reader.inject（queue.put，thread-safe）
```
（`on_input` 由 uvicorn loop 執行緒呼叫、queue 由機器人主執行緒讀 → `queue.Queue` thread-safe，無需鎖。）

- [ ] **Step 2: 改 `server.py` 的 `start` 簽章透傳 `on_input`**

`myProgram/web/server.py`：
```python
def start(bus, on_input, host: str = "0.0.0.0", port: int = 8137):
    server = uvicorn.Server(uvicorn.Config(create_app(bus, on_input), host=host, port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None      # 非主執行緒不可裝 signal handler
    thread = threading.Thread(target=server.run, name="webui-server", daemon=True)
    thread.start()
    return server, thread
```

- [ ] **Step 3: Windows 語法驗證（無法 import，只 ast.parse）**

Run:
```bash
python -c "import ast; ast.parse(open('myProgram/web/app.py', encoding='utf-8').read()); ast.parse(open('myProgram/web/server.py', encoding='utf-8').read()); print('ast ok')"
```
Expected: 印 `ast ok`（無 SyntaxError）。

- [ ] **Step 4: Commit**

```bash
git add myProgram/web/app.py myProgram/web/server.py
git commit -m "feat(web): Phase 2 WS receive 路由觸控命令→on_input（app/server 透傳，Pi-only）"
```

---

## Task 3: `main.py` 注入 `on_input = input_reader.inject` + 更新 wireup 測試（Windows-TDD）

**Files:**
- Modify: `myProgram/main.py`（`_run_wiring` web 分支）
- Test: `tests/stt/test_main_wireup.py`（更新既有 + 新增）

**Interfaces:**
- Consumes: `server.start(bus, on_input, port=8137)`（Task 2）。

- [ ] **Step 1: 更新既有 web 測試簽章 + 新增 on_input 接線測試（先讓測試反映新契約 → 失敗）**

`tests/stt/test_main_wireup.py`：把既有 `test_web_mode_starts_server_on_port_8137_with_web_display` 內的：
```python
    def fake_start(bus, port=8137):
        started["bus"] = bus
        started["port"] = port
        return object(), object()   # (server, thread)
```
改為（加 `on_input` 位置參數，其餘不變）：
```python
    def fake_start(bus, on_input, port=8137):
        started["bus"] = bus
        started["port"] = port
        return object(), object()   # (server, thread)
```

並在該函式後新增測試：
```python
def test_web_mode_wires_on_input_to_input_reader_inject(monkeypatch):
    """`--web`：server.start 收到 on_input = input_reader.inject（觸控上行注入 seam）。"""
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    captured = _capture_logic_run(monkeypatch)

    injected = []
    fake_input = types.SimpleNamespace(inject=lambda t: injected.append(t))
    monkeypatch.setitem(sys.modules, "myProgram.input_reader", fake_input)
    import myProgram
    monkeypatch.setattr(myProgram, "input_reader", fake_input, raising=False)

    started = {}

    def fake_start(bus, on_input, port=8137):
        started["on_input"] = on_input
        started["port"] = port
        return object(), object()

    fake_server = types.SimpleNamespace(start=fake_start, stop=lambda srv: None)
    monkeypatch.setitem(sys.modules, "myProgram.web.server", fake_server)

    main_module._run_wiring()

    assert started["port"] == 8137
    started["on_input"]("c")          # 等同呼叫 input_reader.inject("c")
    assert injected == ["c"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/stt/test_main_wireup.py -v`
Expected: 新測試 `test_web_mode_wires_on_input_to_input_reader_inject` FAIL（main 還沒傳 on_input → `fake_start` 收到的位置參數錯位 / TypeError）；既有 display 測試因簽章已改可能也需 main 端配合。

- [ ] **Step 3: 改 `main.py` `_run_wiring` web 分支注入 on_input**

`myProgram/main.py` 的 `_run_wiring` 內，把：
```python
            from myProgram.web import server as web_server
            bus = EventBus()
            display_cb = make_web_display(bus)
            web_srv, _ = web_server.start(bus, port=8137)
```
改為：
```python
            from myProgram.web import server as web_server
            from myProgram import input_reader
            bus = EventBus()
            display_cb = make_web_display(bus)
            # on_input：觸控上行 seam —— WS 收到的命令經 commands.to_token → 注入既有 input queue
            #（與鍵盤 / STT 共用單一 queue；read_terminal_key 的 'c' 與 read_customer_input 皆讀此）
            web_srv, _ = web_server.start(bus, input_reader.inject, port=8137)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/stt/test_main_wireup.py -v`
Expected: PASS（含既有 display 測試 + 新 on_input 測試 + graceful fallback 測試）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/main.py tests/stt/test_main_wireup.py
git commit -m "feat(main): Phase 2 web 分支注入 on_input=input_reader.inject（觸控上行佈線）"
```

---

## Task 4: 前端 `app.js` live 模式觸控上行（Pi 視覺驗收）

**Files:**
- Modify: `myProgram/webui/app.js`

**Interfaces:**
- Produces: 上行命令 JSON（對應 Task 1 schema）。

> **無 JS 單元測試框架**（buildless，對齊 Phase 0/1）→ 本 task 驗證 = 程式碼自檢 + Task 5 Pi 視覺驗收。所有改動限 live 分支；`?demo=1` 既有 Phase 0 行為一律不動。

- [ ] **Step 1: 加 live 上行狀態 + sendCommand（`App` 物件內）**

在 `App` 物件加欄位（與既有 `_live` / `_catalog` 同區）：
```js
  _ws: null,                 // 現行 WebSocket（sendCommand 用；connectLive 設定 / onclose 清）
  _pending: {},              // 商品 id → 本地預選數量（live 點餐用；送出後歸 1）
  _awaitingConfirm: false,   // 已送 checkout、等機器人問「正確嗎」→ 顯示 [確認金額] affordance
```
在 `App` 物件加方法（與既有 method 同區）：
```js
  // live 上行：連線中才送（斷線 no-op，保留 Phase 1「斷線不動作、不卡死頁」修正）。
  sendCommand(cmd) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(cmd));
    }
  },
  pendingQty(id) { return this._pending[id] || 1; },
  setPending(id, n) {
    this._pending[id] = Math.max(1, Math.min(MAX_QTY, n));
    this.syncCart();   // 只局部重畫 act-<id>（pending stepper 在那）
  },
```

- [ ] **Step 2: renderVals 透出 pending + awaitingConfirm**

在 `renderVals()` 內 `products` 的 map 回傳物件加 `pending`（每個商品帶本地預選數量）：把
```js
      return {
        ...it, qty, isInCart: inCart, remaining,
```
改為
```js
      return {
        ...it, qty, isInCart: inCart, remaining, pending: this.pendingQty(it.id),
```
並在 `renderVals` 的 `return { ... }` 物件加一鍵：
```js
      awaitingConfirm: this._awaitingConfirm,
```

- [ ] **Step 3: ActionArea live 分支（本地預選 stepper + 加入鈕）**

在 `ActionArea(row)` 函式**最前面**加 live 分支（demo 既有邏輯整段保留在後）：
```js
function ActionArea(row) {
  if (App._live) {
    // live：本地預選數量 stepper（inc/dec 改 pending，不動 cart）+ 加入鈕（送 order）。
    // 無 morph 動畫（demo 限定）；購物車真實數量由右側欄鏡像。
    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
      ${QuantityStepper({ id: row.id, value: row.pending, size: "lg" })}
      ${Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", act: "add", data: { id: row.id } })}
    </div>`;
  }
  const id = esc(row.id);
  // ...（既有 demo 邏輯原樣保留）
```

- [ ] **Step 4: CartInner live：購物車欄唯讀（無減量 stepper）+ 確認 gate 按鈕**

在 `CartInner(v)` 內，把每列的 `${QuantityStepper({ id: l.id, value: l.qty, size: "sm" })}` 改為條件渲染（live 唯讀顯示數量，無 `−`）：
```js
        ${App._live
          ? `<span style="font-family:var(--font-display);font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;">× ${l.qty}</span>`
          : QuantityStepper({ id: l.id, value: l.qty, size: "sm" })}
```
並把結帳按鈕（`${Button({ label: v.checkoutLabel, ... act: "checkout" })}`）改為依 `awaitingConfirm` 切換：
```js
        ${v.awaitingConfirm
          ? Button({ label: "確認金額正確", icon: "ph-bold ph-check", variant: "primary", size: "lg", block: true, act: "confirm" })
          : Button({ label: v.checkoutLabel, icon: "ph-bold ph-qr-code", variant: "primary", size: "lg", block: true, act: "checkout" })}
```
（`awaitingConfirm` 只在 live 會被設 true；demo 永遠 false → 行為不變。）

- [ ] **Step 5: bindEvents live 路由（取代 Phase 1 一律停用）**

把 `bindEvents` 內 Phase 1 的：
```js
    // live 模式：WS 為鏡像狀態唯一權威 ...
    if (App._live && act !== "adGoto") return;
    switch (act) {
```
改為 live 專屬路由（demo 既有 switch 保留在 else）：
```js
    if (App._live) {
      switch (act) {
        case "exitStandby": App.sendCommand({ type: "wake" }); break;       // 歡迎頁 → 喚醒（斷線時 sendCommand no-op，停留歡迎頁）
        case "inc": App.setPending(id, App.pendingQty(id) + 1); break;      // 本地預選 +1
        case "dec": App.setPending(id, App.pendingQty(id) - 1); break;      // 本地預選 −1（不低於 1）
        case "add":
          App.sendCommand({ type: "order", item: id, qty: App.pendingQty(id) });
          App._pending[id] = 1;                                            // 送出後預選歸 1
          break;
        case "checkout":
          App.sendCommand({ type: "checkout" });
          App._awaitingConfirm = true; App.render();                       // 本地顯示「確認金額」affordance
          break;
        case "confirm":
          App.sendCommand({ type: "confirm" });
          App._awaitingConfirm = false;                                    // robot 進 L4 → emit checkout 接手畫面
          break;
        case "place": App.sendCommand({ type: "pay" }); break;             // 結帳頁「我已完成付款」→ 付款
        case "adGoto": App.showAd(parseInt(t.dataset.idx, 10)); restartAdTimer(); break;
        // close / finish / setView / toggleReview / stop / noop：live 忽略（overlay 由機器人 phase 驅動）
      }
      return;
    }
    switch (act) {
```
（注意：`switch (act) {` 這行原本就在，改完後 demo 分支的 switch 不重複——確認只保留一個 demo switch。）

- [ ] **Step 6: applyState 清 awaitingConfirm + connectLive 綁/解 _ws**

在 `applyState(s)` 末尾加（phase 離開 ordering 時清掉本地確認 affordance，防殘留）：
```js
    if (s.phase !== "ordering") this._awaitingConfirm = false;
```
在 `connectLive()` 內，`const ws = new WebSocket(...)` 後加 `App._ws = ws;`，並把 `ws.onclose` 改為同時清掉 `_ws`：
```js
    ws.onclose = () => { App._ws = null; showReconnecting(); setTimeout(connectLive, nextBackoff()); };
```

- [ ] **Step 7: 程式碼自檢（無 JS 測試框架）**

人工核對：
1. 所有 live 上行只走 `sendCommand`、**不**呼叫本地 setState（cart 只認機器人 emit）。
2. `?demo=1`（`App._live === false`）路徑：ActionArea / CartInner / bindEvents 的 demo 分支與 Phase 0 完全一致（diff 只在新增 live 分支）。
3. 斷線時 `_ws` 為 null → `sendCommand` no-op；歡迎頁點擊不跳轉（Phase 1 修正保留）。

- [ ] **Step 8: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "feat(webui): Phase 2 live 觸控改送 WS 上行命令（預選 stepper+加入 / 結帳兩拍 / 喚醒 / 付款）"
```

---

## Task 5: Pi 整合驗收 pineedtodo（真 import + 端到端觸控）

**Files:**
- Create: `resources/pineedtodo/2026-06-18_webui_phase2_verify.md`

> 本 task 不改 code，只產出 Pi 端驗收指示（Windows 無法驗 fastapi import / WS / 真觸控）。完成後使用者在 Pi 跑、回報結果。

- [ ] **Step 1: 寫 pineedtodo**

`resources/pineedtodo/2026-06-18_webui_phase2_verify.md`：
```markdown
# Pi 驗收 — WebUI Phase 2 觸控雙向（2026-06-18）

> 前置：Phase 1 已驗（fastapi + 純 uvicorn 已裝）。Phase 2 零新依賴。

## 步驟
1. `git pull`（拉 Phase 2 commits）。
2. 在 Pi：`python3.11 -m myProgram --web`（建議帶 `STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10` 避免 STT arecord 噪訊，但 Phase 2 與 STT 無關）。
3. 機器人首次顯示商家主選單 → 在 Pi 鍵盤按 `1` 進叫賣模式（hawk）。**這是一次性 setup**，之後每輪交易結束自動回 hawk。
4. client 筆電瀏覽器連 `http://raspberrypi.local:8137/`（解析不到用 Pi IP）。

## 驗收項（全程**不碰 Pi 鍵盤、不講話**，純筆電觸控）
- [ ] **喚醒**：歡迎頁點「開始點餐」→ 機器人轉 L2 + 螢幕跳點餐頁（且機器人有語音 ack）。
- [ ] **點餐**：商品卡用 − / + 選數量（如冰紅茶 3）→ 點「加入購物車」→ 機器人語音 ack + 右側購物車長出「冰紅茶 ×3」。
- [ ] **多商品**：再選刮刮樂 2 加入 → 購物車兩列正確。
- [ ] **結帳兩拍**：點「結帳」→ 機器人問「總共 X 元，正確嗎」+ 按鈕變「確認金額正確」→ 點它 → 機器人進結帳頁（QR）。
- [ ] **付款**：結帳頁點「我已完成付款」→ 機器人轉感謝頁 + 顯示已付金額。
- [ ] **唯讀購物車**：購物車欄商品只顯示「× N」無減量鈕（符合 add-only）。
- [ ] **斷線**：（Pi 端 Ctrl+C 停 server）→ 筆電右上「重新連線中」+ 歡迎頁點「開始點餐」無反應、不跳轉。重啟 server → 自動重連。
- [ ] **語音/觸控對等**：穿插用語音點一項、觸控點一項 → 兩者都進同一購物車（驗證單 queue）。

## 回報
- 各項 OK / NG；NG 附現象（畫面 / 機器人語音 / 終端 log）。
- 延遲體感。
- 放行 Phase 2 收尾？
```

- [ ] **Step 2: Commit**

```bash
git add resources/pineedtodo/2026-06-18_webui_phase2_verify.md
git commit -m "docs(pineedtodo): Phase 2 Pi 整合驗收指示（端到端觸控）"
```

---

## Task 6: 收尾文件（Pi 驗收通過後）

> **依賴 Task 5 Pi 驗收回報**。驗收 OK 才寫「✅」；NG 先修。

**Files:**
- Modify: `resources/changelogs/changelog_2026-06-18_webui.md`（加 Phase 2 里程碑）
- Modify: `resources/roadmaps/html_ui_plan.md`（Phase 2 標 ✅）
- Modify: `resources/roadmap.md`（現況快照 + 下一步候選更新）

- [ ] **Step 1**：changelog 加「### 2. WebUI Phase 2 — 觸控雙向」里程碑（決策 / 建置 / commits / Pi 驗收結果 / 反思）。
- [ ] **Step 2**：`html_ui_plan.md` 階段表 Phase 2 狀態改 ✅ + 註明 spec/plan/commits/Pi 驗收。
- [ ] **Step 3**：`roadmap.md` 現況快照前端段補 Phase 2 ✅；下一步候選更新（觸控閉環完成 → demo 準備 / 真硬體 / 忙碌指示 等）。
- [ ] **Step 4: Commit**

```bash
git add resources/changelogs/changelog_2026-06-18_webui.md resources/roadmaps/html_ui_plan.md resources/roadmap.md
git commit -m "docs(webui): Phase 2 ✅ 收尾 — changelog + roadmap 階段路線"
```

---

## Self-Review

**1. Spec coverage：**
- commands 純映射 → Task 1 ✓；WS receive 接線 → Task 2 ✓；main on_input 佈線 → Task 3 ✓；前端 live 上行 → Task 4 ✓；測試切分（commands Windows / app-server Pi-only）→ Task 1 + 2 ✓；衝突/斷線/喚醒前提/非法命令/graceful → Task 1（None）+ Task 4（sendCommand 斷線 no-op）+ Task 2（吞例外）+ Task 5 驗收 ✓；零新 Pi 依賴 → 無 requirements task（正確）；繁中/紅線 → Global Constraints ✓。
- spec 開放問題：① 結帳/確認 token → Task 1 用 `結賬`/`正確` + membership 測試守 ✓；② 前端 act 對應 → Task 4 逐一映射既有 data-act ✓；③ create_app 既有 Pi-only 測試 → tests/web 只有 bus/display（Windows），無 create_app 測試 → 無需同步（已用 Glob 確認）✓。

**2. Placeholder scan：** 無 TBD / 「適當處理」/ 無碼步驟。Task 6 文件內容為收尾摘要（依 Pi 結果填），非 code placeholder。

**3. Type consistency：** `to_token(cmd)→str|None`（Task 1）↔ Task 2 `commands.to_token(json.loads(raw))` ✓；`create_app(bus, on_input)`（Task 2）↔ `server.start` 內 `create_app(bus, on_input)` ✓ ↔ Task 3 `start(bus, input_reader.inject, port=8137)` ✓ ↔ 測試 `fake_start(bus, on_input, port=8137)` ✓；前端命令 schema（Task 4 送）↔ Task 1 `to_token` 收（type/item/qty）一致 ✓；商品 id = catalog name = PRODUCTS key（Task 4 `item: id` ↔ Task 1 `item not in PRODUCTS`）✓。
```
