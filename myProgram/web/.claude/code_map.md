# myProgram/web/ — code_map（本層索引）

> 顆粒：中。FastAPI 顯示鏡像 transport 層；`sales/` → 注入 `display` 回呼 → 本層建 dict → WS 廣播給瀏覽器。

## 檔案（純 stdlib，Windows 可 pytest）
- `bus.py` — `EventBus`：橋接同步機器人執行緒 → uvicorn async loop 的 WS 廣播。`publish(state)`（存 last-known + `run_coroutine_threadsafe` 排程廣播）、`last_state()`、`add_client`/`remove_client`、`bind_loop(loop)`、`async _broadcast`（吞斷線 client）。無 pydantic、無業務。
- `display.py` — `make_web_display(bus)` → 回 `display(phase, cart, paid=0)` 回呼：算 `total = Σ PRODUCTS[name]["實際"]×qty`、建 `{phase, cart, total, paid}` dict → `bus.publish`。例外全吞（web 掛了不拖垮對話）。只 import `sales.constants`。
- `commands.py` — `to_token(cmd: dict) -> str | None`：觸控上行結構化命令 → 對話既有消費的 token 字串（wake→`c`、order→`{品名}{數量}`、checkout/confirm→keyword 集代表字、pay→`s`）；非法→None。只 import sales 常數，無 fastapi/pydantic。

## 檔案（Pi-only — import fastapi / uvicorn / pydantic，Windows 不可 import / run，只能 `ast.parse`）
- `models.py` — 前後端契約 Pydantic DTO：`Product` / `DisplayState` / `Snapshot`。
- `app.py` — FastAPI app：`create_app(bus, on_input)` → `/api/state`（快照）+ `/ws/state`（WS 推送下行 + receive 上行：`commands.to_token` → `on_input` 注入既有 input queue，壞 JSON 吞掉）+ StaticFiles 出 `webui/` 靜態檔；startup 綁 uvicorn loop 進 bus。
- `server.py` — uvicorn 背景執行緒生命週期：`start(bus, on_input, host, port=8137) → (server, thread)`、`stop(server)`；非主執行緒 → 關 signal handler。

## 其他
- `CLAUDE.md` — 本層導引。
- `.claude/code_map.md` — 本檔。

## 測試
- `tests/web/test_bus.py` — EventBus 行為（publish 無 loop 只存、_broadcast 廣播 + 剔除斷線）。
- `tests/web/test_display.py` — display→dict 映射（total 計算、thankyou 帶 paid、未知商品不 raise）。
