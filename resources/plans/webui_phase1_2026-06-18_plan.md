# WebUI Phase 1 — FastAPI 顯示鏡像後端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 本專案走 **SDD + worktree**：動 `myProgram/{sales,main}.py` 的 task 一律派 **sales-coder** subagent 實作 + 三段 reviewer（spec-reviewer / code-quality / Iron Law）；純新增 `myProgram/web/` 與 `app.js` 可主 agent 自寫但仍先 invoke `karpathy-guidelines`。Steps 用 checkbox（`- [ ]`）追蹤。對應設計 spec：`resources/specs/webui_phase1_2026-06-18_design.md`。

**Goal:** 讓 Pi 上的機器人主程式把點餐/購物車/結帳/感謝即時狀態，透過 FastAPI（REST 快照 + WebSocket 推送）鏡像到同 wifi client 筆電瀏覽器的 Glaze UI（顧客語音點一項 → 畫面購物車就長一項）。

**Architecture:** 機器人 process 內多一條 uvicorn 背景執行緒跑 FastAPI app；`sales/` 在狀態/購物車變動點呼叫新注入的 `display(phase, cart, paid)` 回呼 → web 版建純 dict → `EventBus`（`asyncio.run_coroutine_threadsafe` 橋接同步機器人執行緒 → async loop）→ WS 廣播給瀏覽器。前端從 demo 切換器改為 WS client 驅動 render。

**Tech Stack:** Python 3.11 + FastAPI + 純 `uvicorn`（非 `uvicorn[standard]`）+ Pydantic（後端）；既有 `sales/` 狀態機（無框架）；前端 buildless ES（`fetch` + `WebSocket`）。

## Global Constraints

（每個 task 隱含遵守；數值逐字取自 spec 與專案紅線）

- **本機禁裝依賴** 🔒：fastapi / uvicorn / **pydantic** 在 Windows 裝不了 → 凡 import 它們的程式碼 **Windows 無法 pytest**。對策：`bus` + `display`→dict 映射全走**純 stdlib dict**（Windows-TDD）；Pydantic / FastAPI / uvicorn 殼留 **Pi 驗**。
- **不改 vendor/** 🔒、**不 import 廠商 SDK**（`sales/` / `web/` 皆不碰）、**繁中產出**、**`git add` 明列檔名禁 `-A`/`.`** 🔒。
- **動 `myProgram/{sales,main}.py` 必走 SDD**：spec（已寫）→ 本 plan → 派 sales-coder → 三段審 → Iron Law（沒跑 `python -m pytest tests/` 通過不得宣告完成）。
- **既有 621 測試零行為改變**：`display` 預設 `None` + emit 點 guard；no-op display 下全綠。
- **互動模式 A**：瀏覽器被動鏡像，live 模式觸控停用；觸控→機器人雙向是 Phase 2。
- **流程**：動 `myProgram/` → 走 **worktree 5 階段**；新增 `myProgram/web/` → 更新 `myProgram/.claude/code_map.md` + 建 `web/.claude/code_map.md`。Pi 端裝依賴 → pineedtodo。
- **port 8137**、啟動旗號 **`--web`**（spec open question 已採此預設）。

---

## File Structure

```
myProgram/web/                    # 新 transport 套件（與 sales/ 分離）
├── __init__.py                   # 套件標記
├── bus.py                        # EventBus（純 stdlib dict + asyncio 橋）← Windows-TDD
├── display.py                    # make_web_display(bus) → display 回呼建 dict ← Windows-TDD
├── models.py                     # Pydantic DTO（Product/DisplayState/Snapshot）← Pi-only
├── app.py                        # FastAPI app（/api/state + /ws/state + StaticFiles）← Pi-only
├── server.py                     # uvicorn 背景執行緒 start/stop ← Pi-only
├── CLAUDE.md                     # 薄導引（指回 root）
└── .claude/code_map.md           # 本層索引

myProgram/sales/dialog_io.py      # +display 欄位（DialogIO）
myProgram/sales/states/machine.py # +狀態進場 emit（phase 轉移 + paid）
myProgram/sales/states/l2_l3_dialog.py  # run_dialog +display 參數；DialogSession.main_loop +per-turn emit
myProgram/sales/logic.py          # run() +display=None 參數
myProgram/main.py                 # --web 佈線（啟 server thread + 注入 web display）

myProgram/webui/app.js            # WS client 驅動 render（取代 demo 切換器當主驅動）

tests/sales/...                   # 既有 machine/dialog 測試 +display spy；既有 stub +display kwarg
tests/web/test_bus.py             # 新：EventBus（Windows-TDD）
tests/web/test_display.py         # 新：make_web_display→dict 映射（Windows-TDD）

resources/requirements/raspberry_pi_setup.md   # +fastapi/uvicorn
resources/pineedtodo/2026-06-18_webui_phase1_deps_verify.md  # 新：Pi 裝依賴 + 整合驗收
```

職責邊界：`bus.py`=廣播/橋（無業務、無 pydantic）；`display.py`=cart→dict（無 pydantic）；`models.py`=契約（pydantic）；`app.py`=路由；`server.py`=執行緒生命週期。`sales/` 只多呼叫一個注入回呼，不知道 web 存在。

---

## Task 1：`display` 回呼 no-op seam（穿線，零 emit、零行為改變）

把 `display` 回呼從 `main.py` 穿到 `DialogSession`，全程 no-op（不 emit），確認 621 測試全綠。先打通管線、後加 emit（Task 2/3），讓「穿線」與「行為」分兩個 reviewer gate。

**Files:**
- Modify: `myProgram/sales/dialog_io.py`（+`display` 欄位）
- Modify: `myProgram/sales/logic.py`（`run()` +`display=None`，放進 callbacks dict）
- Modify: `myProgram/sales/states/machine.py`（`DialogState.run` 傳 `display=cb.get("display")` 給 `run_dialog`）
- Modify: `myProgram/sales/states/l2_l3_dialog.py`（`run_dialog` +`display=None` 參數 → `DialogIO(display=display)`）
- Modify: `myProgram/main.py`（terminal 模式傳 `display=` no-op lambda）
- Test: `tests/sales/`（既有 `run_dialog` / machine stub 更新接受 `display` kwarg）

**Interfaces:**
- Produces: callback `display(phase: str, cart: dict[str,int], paid: int = 0) -> None`，由 `logic.run(..., display=None)` 注入；`DialogIO.display: Callable = None`；`SalesMachine.callbacks["display"]`（可缺，emit 點用 `.get` guard）。

- [ ] **Step 1: `DialogIO` 加 `display` 欄位**

`myProgram/sales/dialog_io.py` dataclass 末欄加（frozen dataclass，預設 None 對齊其餘可選 callback）：

```python
    speak_and_wait: Callable = None
    display: Callable = None        # web 顯示鏡像 emit；終端模式 no-op / None（guard 於 caller）
```

- [ ] **Step 2: 跑既有 dialog 測試確認沒壞**

Run: `python -m pytest tests/sales/ -q`
Expected: PASS（純加可選欄位，無 caller 變動）。

- [ ] **Step 3: `run_dialog` 收 `display` 並入 `DialogIO`**

`l2_l3_dialog.py` `run_dialog` 簽名末加 `display=None`，建 `io` 時帶入：

```python
def run_dialog(
    speak, print_terminal, read_customer_input, cart, think_count: int = 0,
    *, opencv_disable, do_action, speak_and_wait=None, display=None,
) -> tuple:
    io = DialogIO(
        speak=speak, read_customer_input=read_customer_input,
        print_terminal=print_terminal, do_action=do_action,
        speak_and_wait=speak_and_wait, display=display,
    )
```

- [ ] **Step 4: `DialogState.run` 把 `display` 傳進 `run_dialog`（machine.py）**

`machine.py` `DialogState.run` 的 `states.run_dialog(...)` 呼叫末加（`.get` 防測試 callback 無此鍵）：

```python
            speak_and_wait=cb["speak_and_wait"],
            display=cb.get("display"),
        )
```

- [ ] **Step 5: `logic.run` 加 `display=None` 參數 + 入 callbacks dict**

`logic.py` `run(...)` 簽名末加 `display=None`；`callbacks = dict(...)` 末加 `display=display,`。

- [ ] **Step 6: 更新 machine/dialog 測試 stub 接受 `display`**

既有 `test_machine` 對 `states.run_dialog` 的 monkeypatch stub 是 keyword-only 嚴格簽名 → 加 `display=None` 參數（grep `def.*run_dialog` 於 `tests/sales/`，逐一補）。直接呼叫 `run_dialog` 的 `test_logic` / dialog 測試不傳 `display`（走預設 None）。

- [ ] **Step 7: `main.py` terminal 模式傳 no-op display**

`main.py` `main()` 內 `logic.run(**callbacks)` 改為注入 no-op（web 模式 Task 6 覆寫）：

```python
    _noop_display = lambda *a, **k: None
    logic.run(**callbacks, display=_noop_display)
```

- [ ] **Step 8: 全測試綠（零行為改變）**

Run: `python -m pytest tests/ -q`
Expected: PASS（621 + 既有；display 全程 None/no-op，無 emit）。

- [ ] **Step 9: Commit**

```bash
git add myProgram/sales/dialog_io.py myProgram/sales/logic.py myProgram/sales/states/machine.py myProgram/sales/states/l2_l3_dialog.py myProgram/main.py tests/sales/<改到的測試檔>
git commit -m "feat(web): display 回呼 no-op seam 穿線（machine→dialog，零行為改變）"
```

---

## Task 2：machine 狀態進場 emit（standby/ordering/checkout/thankyou + paid）

`SalesMachine.run()` 每進新層 emit phase 轉移 + 當前 cart 快照；`l5` 進場帶 `paid = calc_total(cart)`（清 cart 前）。

**Files:**
- Modify: `myProgram/sales/states/machine.py`
- Test: `tests/sales/test_machine.py`（spy display）

**Interfaces:**
- Consumes: `display(phase, cart, paid)`（Task 1）。
- Produces: emit phase ∈ {`standby`(l1), `ordering`(dialog), `checkout`(l4), `thankyou`(l5)}；`thankyou` 帶 `paid`。

- [ ] **Step 1: 寫失敗測試**

`tests/sales/test_machine.py` 新增（用既有 machine 測試的 stub 機制，stub 各 `run_*` 控制 transition，spy display）：

```python
def test_machine_emits_phase_on_state_entry(monkeypatch):
    calls = []
    cb = _make_callbacks(monkeypatch)           # 既有 helper：14 callback stub
    cb["display"] = lambda phase, cart, paid=0: calls.append((phase, dict(cart), paid))
    # stub: l1→dialog→l4→l5→l1(terminate)
    _stub_states(monkeypatch, l1="L2", dialog="L4", l4="L5", l5_then_stop=True)
    SalesMachine(cb, {"冰紅茶": 2}).run()       # 給非空 cart 跑到 l4/l5
    phases = [c[0] for c in calls]
    assert phases[:4] == ["standby", "ordering", "checkout", "thankyou"]
    assert calls[3][2] == 54                     # paid = 2×27（thankyou 帶 paid）
```

（依 `test_machine.py` 既有 fixture 命名微調；重點：斷言進場 emit 順序 + paid。）

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/sales/test_machine.py::test_machine_emits_phase_on_state_entry -v`
Expected: FAIL（machine 尚未 emit）。

- [ ] **Step 3: machine.py 加進場 emit**

`machine.py` 頂部加映射常數；`SalesMachine.run()` 進場（invariant 檢查後、`state.run` 前）emit：

```python
_PHASE_BY_STATE = {"l1": "standby", "dialog": "ordering", "l4": "checkout", "l5": "thankyou"}

    def _emit(self, current: str) -> None:
        disp = self.callbacks.get("display")
        if disp is None:
            return
        paid = cart_module.calc_total(self.cart) if current == "l5" else 0
        disp(_PHASE_BY_STATE[current], dict(self.cart), paid)
```

`run()` 迴圈內，invariant 檢查之後、`result = state.run(self)` 之前插入 `self._emit(current)`。

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/sales/test_machine.py -v`
Expected: PASS。

- [ ] **Step 5: 全測試綠**

Run: `python -m pytest tests/ -q`
Expected: PASS（既有測試多數 callback 無 `display` 鍵 → `.get` 回 None → 不 emit；零行為改變）。

- [ ] **Step 6: Commit**

```bash
git add myProgram/sales/states/machine.py tests/sales/test_machine.py
git commit -m "feat(web): machine 狀態進場 emit phase 轉移 + thankyou paid"
```

---

## Task 3：dialog 每輪 emit（購物車逐項長出的增量鏡像）

`DialogSession.main_loop()` 每處理完一輪 `_dispatch`（cart 可能變動）emit `ordering` + 最新 cart。

**Files:**
- Modify: `myProgram/sales/states/l2_l3_dialog.py`
- Test: `tests/sales/`（dialog 測試 spy display）

**Interfaces:**
- Consumes: `DialogIO.display`（Task 1）。
- Produces: 每輪顧客回應處理後 emit `("ordering", dict(cart))`。

- [ ] **Step 1: 寫失敗測試**

於 dialog 測試檔（`tests/sales/test_l2_l3_dialog.py` 或對應）新增：餵「冰紅茶兩瓶」→「結帳」序列，spy display，斷言加單那輪 emit `("ordering", {"冰紅茶":2})`：

```python
def test_dialog_emits_cart_each_turn():
    calls = []
    cart = {}
    io_inputs = iter(["冰紅茶兩瓶", "1"])         # 加單 → checkout confirm yes（依既有測試輸入慣例調整）
    # 用既有 run_dialog 測試 harness（fake speak/read），display=spy
    run_dialog(
        speak=lambda *_: None, print_terminal=lambda *_: None,
        read_customer_input=lambda timeout=None: next(io_inputs, None),
        cart=cart, opencv_disable=lambda: None, do_action=lambda *_: None,
        display=lambda phase, c, paid=0: calls.append((phase, dict(c))),
    )
    assert ("ordering", {"冰紅茶": 2}) in calls
```

（實際輸入序列對齊既有 dialog 測試的加單→結帳 pattern；重點：加單後該輪 emit 帶正確 cart。）

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/sales/test_l2_l3_dialog.py::test_dialog_emits_cart_each_turn -v`
Expected: FAIL。

- [ ] **Step 3: main_loop 加 per-turn emit**

`l2_l3_dialog.py` `DialogSession.main_loop()` 迴圈內，`_dispatch` 回非 tuple（未退出）後、`continue` 前 emit：

```python
            result = self._dispatch(response, in_main_loop=True)
            if isinstance(result, tuple):
                return result
            if self.io.display is not None:
                self.io.display("ordering", dict(self.cart))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/sales/test_l2_l3_dialog.py -v`
Expected: PASS。

- [ ] **Step 5: 全測試綠**

Run: `python -m pytest tests/ -q`
Expected: PASS（既有 dialog 測試 `io.display` 為 None → guard 跳過）。

- [ ] **Step 6: Commit**

```bash
git add myProgram/sales/states/l2_l3_dialog.py tests/sales/test_l2_l3_dialog.py
git commit -m "feat(web): dialog 每輪 emit ordering+cart（增量購物車鏡像）"
```

---

## Task 4：`myProgram/web/` 套件骨架 + `bus.py` + `display.py`（純 stdlib，Windows-TDD）

建 web 套件骨架 + 事件匯流排 + display→dict 映射（皆不 import pydantic/fastapi → Windows 可 pytest）。

**Files:**
- Create: `myProgram/web/__init__.py`、`myProgram/web/bus.py`、`myProgram/web/display.py`、`myProgram/web/CLAUDE.md`、`myProgram/web/.claude/code_map.md`
- Modify: `myProgram/.claude/code_map.md`（加 `web/` 子目錄條目）
- Test: `tests/web/test_bus.py`、`tests/web/test_display.py`（新增 `tests/web/__init__.py`）

**Interfaces:**
- Produces:
  - `EventBus`：`publish(state: dict)`（機器人執行緒）、`last_state() -> dict|None`、`add_client(ws)`/`remove_client(ws)`、`bind_loop(loop)`、`async _broadcast(state)`。
  - `make_web_display(bus) -> callable`：回 `display(phase, cart, paid=0)`，建 `{"phase","cart","total","paid"}` dict（`total = Σ PRODUCTS[name]["實際"]×qty`）→ `bus.publish`。

- [ ] **Step 1: 寫 bus 失敗測試**

`tests/web/test_bus.py`：

```python
import asyncio
from myProgram.web.bus import EventBus

def test_publish_sets_last_state_without_loop():
    bus = EventBus()
    bus.publish({"phase": "ordering", "cart": {"冰紅茶": 2}, "total": 54, "paid": 0})
    assert bus.last_state()["cart"] == {"冰紅茶": 2}      # loop 未綁 → 只存 last-known，不爆

def test_broadcast_sends_to_clients_and_drops_dead():
    bus = EventBus()
    sent, dead = [], object()
    class OkWS:
        async def send_json(self, s): sent.append(s)
    class DeadWS:
        async def send_json(self, s): raise RuntimeError("closed")
    ok, bad = OkWS(), DeadWS()
    bus.add_client(ok); bus.add_client(bad)
    asyncio.run(bus._broadcast({"phase": "standby"}))
    assert sent == [{"phase": "standby"}]
    assert bad not in bus._clients and ok in bus._clients     # 斷線者剔除
```

- [ ] **Step 2: 跑確認失敗**

Run: `python -m pytest tests/web/test_bus.py -v`
Expected: FAIL（`myProgram.web.bus` 不存在）。

- [ ] **Step 3: 實作 `web/__init__.py` + `web/bus.py`**

`web/__init__.py`：空（套件標記，注釋一行說明 transport 層）。
`web/bus.py`：

```python
"""EventBus：橋接同步機器人執行緒 → uvicorn async loop 的 WS 廣播（純 stdlib，無 pydantic）。"""
import asyncio


class EventBus:
    def __init__(self) -> None:
        self._state: dict | None = None
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop) -> None:
        self._loop = loop

    def last_state(self) -> dict | None:
        return self._state

    def add_client(self, ws) -> None:
        self._clients.add(ws)

    def remove_client(self, ws) -> None:
        self._clients.discard(ws)

    def publish(self, state: dict) -> None:
        """機器人執行緒呼叫：存 last-known + 排程廣播到 async loop（loop 未綁時只存）。"""
        self._state = state
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._broadcast(state), self._loop)

    async def _broadcast(self, state: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(state)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
```

- [ ] **Step 4: 跑 bus 測試通過**

Run: `python -m pytest tests/web/test_bus.py -v`
Expected: PASS。

- [ ] **Step 5: 寫 display 失敗測試**

`tests/web/test_display.py`：

```python
from myProgram.web.bus import EventBus
from myProgram.web.display import make_web_display

def test_web_display_builds_dict_with_total():
    bus = EventBus()
    disp = make_web_display(bus)
    disp("ordering", {"冰紅茶": 2, "刮刮樂": 1})          # 27×2 + 180×1 = 234
    st = bus.last_state()
    assert st == {"phase": "ordering", "cart": {"冰紅茶": 2, "刮刮樂": 1}, "total": 234, "paid": 0}

def test_web_display_thankyou_carries_paid():
    bus = EventBus()
    make_web_display(bus)("thankyou", {"冰紅茶": 2}, paid=54)
    assert bus.last_state()["paid"] == 54
```

- [ ] **Step 6: 跑確認失敗**

Run: `python -m pytest tests/web/test_display.py -v`
Expected: FAIL（`web.display` 不存在）。

- [ ] **Step 7: 實作 `web/display.py`**

```python
"""display 回呼 web 版：把 (phase, cart, paid) 建成 WS 推送 dict（含後端算的 total）。純 stdlib。"""
from myProgram.sales.constants import PRODUCTS


def make_web_display(bus):
    def display(phase: str, cart: dict, paid: int = 0) -> None:
        try:
            total = sum(PRODUCTS[name]["實際"] * qty for name, qty in cart.items())
            bus.publish({"phase": phase, "cart": dict(cart), "total": total, "paid": paid})
        except Exception:
            pass   # spec 錯誤處理：web 掛了機器人照常服務客人，display 不得拖垮對話執行緒
    return display
```

（測試 `test_web_display_builds_dict_with_total` 仍綠：正常路徑無例外。可另加一條餵未知商品名斷言不 raise。）

- [ ] **Step 8: 跑 display 測試通過 + 全測試綠**

Run: `python -m pytest tests/web/ tests/ -q`
Expected: PASS。

- [ ] **Step 9: 寫 `web/CLAUDE.md` + `web/.claude/code_map.md` + 更新 `myProgram/.claude/code_map.md`**

- `web/CLAUDE.md`：薄導引（transport 層、Pi-only deps、指回 root + skill）。
- `web/.claude/code_map.md`：索引 bus/display/models/app/server 各檔職責 + 標註哪些 Pi-only。
- `myProgram/.claude/code_map.md`「子目錄」段加：`web/` — FastAPI 顯示鏡像 transport（bus/display 純 stdlib；models/app/server import fastapi/uvicorn/pydantic = Pi-only）。

- [ ] **Step 10: Commit**

```bash
git add myProgram/web/__init__.py myProgram/web/bus.py myProgram/web/display.py myProgram/web/CLAUDE.md myProgram/web/.claude/code_map.md myProgram/.claude/code_map.md tests/web/__init__.py tests/web/test_bus.py tests/web/test_display.py
git commit -m "feat(web): web 套件骨架 + EventBus + display→dict 映射（純 stdlib Windows-TDD）"
```

---

## Task 5：`web/models.py` + `web/app.py` + `web/server.py`（Pydantic/FastAPI/uvicorn，Pi-only）

FastAPI 殼：DTO + 路由 + uvicorn 背景執行緒。**import fastapi/uvicorn/pydantic → Windows 無法 pytest**，本 task 程式於 Windows 寫好、**Pi 端驗**（Task 8 整合）。

**Files:**
- Create: `myProgram/web/models.py`、`myProgram/web/app.py`、`myProgram/web/server.py`

**Interfaces:**
- Consumes: `EventBus`（Task 4）、`PRODUCTS`。
- Produces: `create_app(bus) -> FastAPI`、`server.start(bus, host="0.0.0.0", port=8137) -> (server, thread)`、`server.stop(server)`。

- [ ] **Step 1: `web/models.py`（Pydantic DTO）**

```python
"""前後端契約 DTO（Pydantic）。僅在 FastAPI 邊界用 → Windows 不可 import（pydantic 未裝）。"""
from typing import Literal
from pydantic import BaseModel


class Product(BaseModel):
    name: str
    unit: str
    price_now: int
    price_orig: int


class DisplayState(BaseModel):
    phase: Literal["standby", "ordering", "checkout", "thankyou"]
    cart: dict[str, int]
    total: int
    paid: int = 0


class Snapshot(BaseModel):
    catalog: list[Product]
    state: DisplayState
```

- [ ] **Step 2: `web/app.py`（FastAPI 路由 + StaticFiles）**

```python
"""FastAPI app：/api/state（快照）+ /ws/state（推送）+ 出 webui 靜態檔。Pi-only（import fastapi）。"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from myProgram.sales.constants import PRODUCTS
from myProgram.web.models import Product, DisplayState, Snapshot

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"
_STANDBY = {"phase": "standby", "cart": {}, "total": 0, "paid": 0}


def _catalog() -> list:
    return [Product(name=n, unit=d["單位"], price_now=d["實際"], price_orig=d["原價"])
            for n, d in PRODUCTS.items()]


def create_app(bus) -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    async def _bind_loop() -> None:
        bus.bind_loop(asyncio.get_running_loop())   # 綁 uvicorn loop 供 run_coroutine_threadsafe

    @app.get("/api/state", response_model=Snapshot)
    def get_state() -> Snapshot:
        st = bus.last_state() or _STANDBY
        return Snapshot(catalog=_catalog(), state=DisplayState(**st))

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket) -> None:
        await ws.accept()
        bus.add_client(ws)
        try:
            await ws.send_json(bus.last_state() or _STANDBY)
            while True:
                await ws.receive_text()              # 模式 A：忽略 client 訊息，只維持連線
        except WebSocketDisconnect:
            pass
        finally:
            bus.remove_client(ws)

    # StaticFiles 掛 "/" 必須最後（greedy）；前面的 /api、/ws 路由先註冊先匹配
    app.mount("/", StaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")
    return app
```

- [ ] **Step 3: `web/server.py`（uvicorn 背景執行緒）**

```python
"""uvicorn 背景執行緒生命週期。Pi-only（import uvicorn）。非主執行緒 → 關 signal handler。"""
import threading

import uvicorn

from myProgram.web.app import create_app


def start(bus, host: str = "0.0.0.0", port: int = 8137):
    server = uvicorn.Server(uvicorn.Config(create_app(bus), host=host, port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None      # 非主執行緒不可裝 signal handler
    thread = threading.Thread(target=server.run, name="webui-server", daemon=True)
    thread.start()
    return server, thread


def stop(server) -> None:
    server.should_exit = True
```

- [ ] **Step 4: Windows 靜態檢查（不執行 — 無法 import）**

Run: `python -c "import ast; [ast.parse(open(f, encoding='utf-8').read()) for f in ['myProgram/web/models.py','myProgram/web/app.py','myProgram/web/server.py']]"`
Expected: 無語法錯誤（Windows 只能 parse、不能 import/run；真驗在 Pi Task 8）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/web/models.py myProgram/web/app.py myProgram/web/server.py
git commit -m "feat(web): FastAPI DTO + 路由 + uvicorn 背景執行緒（Pi-only，待 Pi 驗）"
```

---

## Task 6：`main.py` `--web` 佈線（啟 server + 注入 web display）

**Files:**
- Modify: `myProgram/main.py`
- Test: `tests/test_main_wireup.py`（web 模式 factory 可 patch、terminal 模式不 import web）

**Interfaces:**
- Consumes: `EventBus` / `make_web_display` / `server.start`（lazy import，僅 `--web`）。
- Produces: `--web` → web display + server thread；無旗號 → no-op display（Task 1）、不 import web。

- [ ] **Step 1: 寫測試（terminal 不 import web；web 模式呼叫 server.start）**

```python
def test_terminal_mode_does_not_import_web(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["myprogram"])
    # 跑 main 的佈線分支（用既有 main 測試 harness，stub logic.run 攔 display）
    captured = {}
    monkeypatch.setattr(logic, "run", lambda **kw: captured.update(kw))
    main_module._run_wiring()                       # 抽出的純佈線函式（見 Step 2）
    assert callable(captured["display"])
    assert "myProgram.web.server" not in sys.modules

def test_web_mode_starts_server(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["myprogram", "--web"])
    started = {}
    fake_bus = object()
    monkeypatch.setitem(sys.modules, "myProgram.web.server",
                        types.SimpleNamespace(start=lambda bus, port=8137: started.setdefault("p", port) or (object(), object())))
    # ...（patch bus/display lazy import；斷言 started["p"] == 8137 且 display 為 web 版）
```

（依 `test_main_wireup.py` 既有 harness 調整；重點：旗號分流 + lazy import 隔離。）

- [ ] **Step 2: main.py 抽佈線 + `--web` 分支**

`main()` 內把「組 callbacks + 決定 display + （web）啟 server + logic.run」抽成 `_run_wiring()`，分流：

```python
def _run_wiring():
    web_mode = "--web" in sys.argv
    state = _S1State()
    callbacks = _build_callbacks(state)
    web_server = web_srv = None
    if web_mode:
        from myProgram.web.bus import EventBus
        from myProgram.web.display import make_web_display
        from myProgram.web import server as web_server
        bus = EventBus()
        display_cb = make_web_display(bus)
        web_srv, _ = web_server.start(bus, port=8137)
        print("[webui] FastAPI 已啟動 → http://0.0.0.0:8137/（同 wifi 連 raspberrypi.local:8137）")
    else:
        display_cb = lambda *a, **k: None
    try:
        logic.run(**callbacks, display=display_cb)
    finally:
        if web_server is not None and web_srv is not None:
            web_server.stop(web_srv)
```

`main()` 的 `try: logic.run(...)` 段改呼叫 `_run_wiring()`；finally 的 worker shutdown 鏈不變。**缺依賴 graceful**：`--web` 但 import 失敗 → catch `ImportError` → 印明確訊息 + 退回 no-op display 繼續跑（不讓機器人開不了機）。

- [ ] **Step 3: 跑測試通過**

Run: `python -m pytest tests/test_main_wireup.py -v`
Expected: PASS。

- [ ] **Step 4: 全測試綠**

Run: `python -m pytest tests/ -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add myProgram/main.py tests/test_main_wireup.py
git commit -m "feat(web): main.py --web 佈線（啟 server + 注入 web display；lazy import 隔離）"
```

---

## Task 7：前端 `app.js` 改為 WS client 驅動

**Files:**
- Modify: `myProgram/webui/app.js`

**Interfaces:**
- Consumes: `GET /api/state` → `{catalog, state}`；`WS /ws/state` → `{phase, cart, total, paid}`。
- Produces: live 模式由後端狀態驅動 render；`?demo=1` 保留現有 demo 切換器 + 本機觸控。

- [ ] **Step 1: catalog 化商品 + 呈現表**

`App.products()` 改讀 `App._catalog`；ingest `/api/state` 的 catalog 時做 **snake→camel 映射**（後端 Pydantic 出 `price_now`/`price_orig`，前端內部用 `priceNow`/`priceOrig`）：`catalog.map(c => ({id:c.name, name:c.name, unit:c.unit, priceNow:c.price_now, priceOrig:c.price_orig, ...presentation[c.name]}))`，name 當 id。新增 name→{icon,tone} 呈現表（搬現有 `bingcha`/`guagua` 的 icon/tone，改 key 為「冰紅茶」/「刮刮樂」）。`renderVals`/`Menu`/`CartInner` 改用 name 當 id（cart key 為商品名）。`?demo=1` 時 fallback 現有 hardcode catalog。

- [ ] **Step 2: WS client + phase→view 映射**

`DOMContentLoaded`：若非 `?demo=1` →

```js
async function connectLive() {
  const r = await fetch("/api/state"); const { catalog, state } = await r.json();
  App._catalog = catalog;
  applyState(state); App.render();
  const ws = new WebSocket(`ws://${location.host}/ws/state`);
  ws.onmessage = (e) => { applyState(JSON.parse(e.data)); App.render(); };
  ws.onclose = () => { showReconnecting(); setTimeout(connectLive, backoff()); };
}
function applyState(s) {                       // phase → App.state
  App.state.cart = s.cart;
  App.state.standby  = s.phase === "standby";
  App.state.overlay  = s.phase === "checkout" ? "checkout" : s.phase === "thankyou" ? "thankyou" : null;
  App.state.paidTotal = s.paid || App.state.paidTotal;
}
```

- [ ] **Step 3: live 模式停用觸控 + demo flag 保留**

`bindEvents` 的 `add`/`inc`/`dec` 在 live 模式（非 `?demo=1`）early-return（WS 權威）；`?demo=1` 維持現有 `setView` 切換器 + 本機觸控（開發工具）。`ReviewSwitcher` 只在 `?demo=1` 顯示。

- [ ] **Step 4: 手動驗證（Windows，serve.py + 假 WS 或 ?demo=1）**

`?demo=1` 開現有 serve.py 預覽：demo 切換器 + 觸控仍正常（無回歸）。live 模式真驗在 Pi（Task 8，需 FastAPI 跑）。

- [ ] **Step 5: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "feat(web): app.js WS client 驅動 render（catalog 化 + phase→view + live 觸控停用 + ?demo=1 保留）"
```

---

## Task 8：Pi 依賴安裝 + 端到端整合驗收（pineedtodo）

**Files:**
- Modify: `resources/requirements/raspberry_pi_setup.md`（+fastapi/uvicorn）
- Create: `resources/pineedtodo/2026-06-18_webui_phase1_deps_verify.md`

- [ ] **Step 1: requirements 加 fastapi/uvicorn**

`raspberry_pi_setup.md` 新依賴段加：`fastapi`、純 `uvicorn`（非 `uvicorn[standard]` — 避 uvloop/httptools C 擴充 Pi wheel 風險）。

- [ ] **Step 2: 寫 pineedtodo（Pi 端步驟）**

`2026-06-18_webui_phase1_deps_verify.md` 內容：
1. **裝依賴**：`cd /home/pi/Desktop/project_jiqiren && python3.11 -m pip install fastapi uvicorn`（**失敗 → 回報，評估降級**：websockets-only / SSE；勿擅自 `uvicorn[standard]`）。
2. **驗 import**：`python3.11 -c "import fastapi, uvicorn, pydantic; print('ok')"`。
3. **起機器人 web 模式**：`python3.11 -m myProgram --web`（終端印 `[webui] FastAPI 已啟動` 即成功）。
4. **client 筆電**連 `http://raspberrypi.local:8137`（解析不到用 Pi IP）→ 走一輪：待機 → 對機器人點「冰紅茶兩瓶」→ **畫面購物車即時長出冰紅茶 ×2** → 結帳（QR）→ 感謝（顯示已付金額）。
5. **斷線重連**：關掉 server 再開，瀏覽器自動「重新連線中」→ 恢復。
6. **回報**：(1) 依賴裝成功？ (2) 即時鏡像各階段對不對？ (3) 延遲體感？ (4) 放行 Phase 2（觸控雙向）？

- [ ] **Step 3: Commit（merge 進 main 觸發 Stop hook sync Pi）**

```bash
git add resources/requirements/raspberry_pi_setup.md resources/pineedtodo/2026-06-18_webui_phase1_deps_verify.md
git commit -m "docs(web): Phase 1 Pi 依賴 + 整合驗收 pineedtodo"
```

- [ ] **Step 4: 收尾**：worktree 5 階段 merge 進 main + push（Stop hook 自動 sync Pi）→ 使用者跑 pineedtodo 驗收。

---

## 驗證方式總表

| Task | Windows pytest | Pi 驗 |
|---|---|---|
| 1 穿線 | ✅ `pytest tests/`（621 綠） | — |
| 2 machine emit | ✅ spy display | — |
| 3 dialog emit | ✅ spy display | — |
| 4 bus/display | ✅ `tests/web/`（純 stdlib） | — |
| 5 FastAPI 殼 | ⚠️ 只 `ast.parse`（pydantic/fastapi 不可 import） | ✅ Task 8 |
| 6 main --web | ✅ 佈線 seam（lazy import 隔離） | ✅ Task 8 |
| 7 前端 | ⚠️ `?demo=1` 無回歸 | ✅ live 模式 Task 8 |
| 8 整合 | — | ✅ 端到端 |

**Iron Law**：Task 1-4、6 宣告完成前必跑對應 `pytest` 通過；Task 5、7、8 的真驗在 Pi（pineedtodo 回報）。
