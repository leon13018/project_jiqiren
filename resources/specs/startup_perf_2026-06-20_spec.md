# 啟動 lag 修復：web server 背景啟動 + worker 預熱 — SDD spec

**日期：** 2026-06-20
**類型：** 效能修復（startup lag）+ wire-up / threading 變更
**範圍：** 中（主要 `main.py` _run_wiring + 2 helper + 連動 test）

---

## §1 背景與動機（systematic-debugging 根因）

**症狀**：`python3.11 -m myProgram --web` 剛開啟、banner 後按 '1' 進入時**卡好幾秒**（Pi 實機）。

**根因（已確認，非猜測）**：
- `_run_wiring` 的 `--web` 分支裡 `from myProgram.web import server as web_server` 觸發**笨重 import**——server.py 頂層 `import uvicorn` + app.py `import fastapi` + models.py `import pydantic`，在 Pi 上要好幾秒，且**同步跑在主執行緒、擋在 `logic.run`（menu）之前**。
- 證據：`server.start()` 本身已非阻塞（spawn daemon thread 跑 uvicorn 立即返回，server.py:12）；笨重的是 import。使用者 log 中 `[webui] FastAPI 已啟動` 印在 '1' 之後、menu 之前 → import 確實擋在 menu 前。
- bus.py / display.py 是**純 stdlib**（輕量），重量全在 server/app/models。
- **次要 lag**：按 '1' 進 hawk 時，首次 `speak`/`do_action` 才 lazy-import `tts`（含笨重 `edge_tts` + TtsWorker singleton）/`action`；首次 `read_customer_input` 才 lazy-import `stt`。這些重 import 在首次互動時同步發生。

**使用者裁決**：修主因（web 背景啟動）**＋** 連 tts/action/stt 一起背景預熱（整體 startup 順暢）。

---

## §2 設計核心 + 行為規約

**原則**：把所有笨重 import 移出主執行緒的互動關鍵路徑（menu / 首次互動），改在 startup 背景 daemon thread 預熱。menu 立即可互動；按 '1' 時 worker 已暖。

### A. Web server 背景啟動（`_run_wiring` --web 分支）
- **留主執行緒（輕量 stdlib，瞬間）**：`from myProgram.web.bus import EventBus`、`from myProgram.web.display import make_web_display`、`from myProgram import input_reader`、`bus = EventBus()`、`display_cb = make_web_display(bus)`。
- **移背景 daemon thread（笨重）**：`from myProgram.web import server`（觸發 fastapi/uvicorn/pydantic import）+ `server.start(bus, input_reader.inject, port=8137)` + 成功印 `[webui] FastAPI 已啟動 …`；uvicorn Server 實例存入 `srv_holder`（dict）供 finally stop。
- **錯誤處理在 thread 內**：`try/except Exception` → 印 `[webui] web 啟動失敗（{exc}）→ …機器人照常運作…`（graceful；display_cb 已是 bus-backed，無 server 也只是 publish 到無 client 的 bus，無害——不必 fallback no-op）。
- `logic.run(**callbacks, display=display_cb)` 立即執行（menu 即現）。早期 display emit（menu=standby phase）走 `bus.publish` → 無 loop 時只存 last_state（bus 設計），browser 連上經 `/api/state` 取 last snapshot → **不丟失**。
- **finally**：`srv = srv_holder.get("srv")`；非 None → `from myProgram.web import server; server.stop(srv)`。

### B. Worker 背景預熱（startup）
- helper `_prewarm_workers()`：背景 import `tts` / `action` / `stt`（暖 edge_tts / vendor-lazy / websockets 重 import + worker singleton），讓首次 speak/do_action/read 零 import lag。
  ```python
  def _prewarm_workers():
      import importlib
      for name in ("tts", "action", "stt"):
          try:
              importlib.import_module(f"myProgram.{name}")
          except Exception:
              pass   # best-effort：預熱失敗不影響——lazy import path 屆時自然 fail-fast
  ```
- 在 `main()` banner 之後、`_run_wiring()` 之前 spawn：`threading.Thread(target=_prewarm_workers, name="worker-prewarm", daemon=True).start()`。

### 行為不變式（保留）
1. 終端模式（無 `--web`）：完全不 import web、display 為 no-op lambda（Windows pytest 不觸發 fastapi/uvicorn）—— 不變。
2. `--web` 缺依賴 / port 衝突 graceful：背景 thread catch + 印錯誤、機器人照常（不再因 web 殼開不了機）。
3. dialog 邏輯 / cart / 各層 / 觸控 / 't' 觸發 全不動。
4. 退出 cleanup（finally worker shutdown + `os._exit(0)`）語意不變；新增 srv_holder stop（取代原 web_srv）。
5. 預熱純加速、無新行為——import 本來就會發生（lazy），只是提前到背景。

---

## §3 改檔範圍

### Prod
- **`myProgram/main.py`**：
  - 頂層 `import threading`。
  - `_run_wiring`：--web 分支重構——輕量 bus/display 留主執行緒、`_start_web` inner fn 移笨重 import+start 到 daemon thread（srv_holder）、display_cb 恆 bus-backed；finally 改用 srv_holder。
  - `main()`：banner 後、`_run_wiring()` 前 spawn `_prewarm_workers` daemon thread。
  - 新增 module-level（或 _run_wiring 內 local）helper：`_prewarm_workers()`。

### Tests
- **`tests/stt/test_main_wireup.py`** / **`tests/sales/test_main_read_callbacks.py`**（sales-coder 擇合適檔）：
  - `_prewarm_workers` best-effort：import 失敗被吞、不 raise（monkeypatch 一個 import 拋錯 → 不 propagate）。
  - `_run_wiring` --web：display_cb 為 bus-backed（非 no-op）；`logic.run` 被呼叫；web server start 在背景 thread（非主執行緒阻塞 logic.run 前）——可 patch `threading.Thread` 捕 target / patch server.start 記錄，驗 logic.run 不等 server start 完成（非阻塞契約）。
  - 終端模式（無 --web）：不 import web、display 為 no-op（既有行為回歸）。

---

## §4 Out of scope
- 不改 dialog / cart / 各層狀態機 / 觸控 / 't' / 's' 邏輯。
- 不改 web transport（bus/display/server/app/models）內部——只改 main.py 的調用時機（背景化）。
- 不改 worker（tts/action/stt）內部——只改 import 時機（預熱）。
- 不動 webui app.js / 前端。
- 不改 SALES_QUIET / SALES_SHOW_COUNTDOWN 等既有旗標。

---

## §5 規範與參考
- **派 `sales-coder`**（opus）；wire-up + **threading** 變更 → 涉 thread sync，dispatch.md「涉 race / thread sync 一律派」。
- pytest `py -3.14 -m pytest`（PATH python 無 pytest）。baseline `tests/` = 701 passed（touch_trigger 後）。
- reuse：`server.start` 已非阻塞（不動）；`bus.publish` 無 loop 只存 last_state（既有 graceful，不動）。
- 繁中、Linux 路徑、不改 vendor、不用 `git add -A`。

---

## §6 測試指令 + 預期
- `py -3.14 -m pytest tests/ -q` → 全綠。baseline 701 → 預期 701 + 新測試（≈704-705）。
- **主 agent 驗收（Iron Law）**：全綠 + 新測試含「--web 下 logic.run 不被 server start 阻塞」契約 + 「_prewarm best-effort 吞錯」+ 終端模式回歸。
- **Pi 實測（使用者）**：`python3.11 -m myProgram --web` → banner 後 menu **立即**出現可按 '1'（不再卡）；`[webui] FastAPI 已啟動` 稍後在背景印出；按 '1' 進 hawk 首句叫賣無明顯 import 頓。

---

## §7 Commit
- `perf(main): start web server + prewarm workers in background to remove startup lag`
- git add 明列：`myProgram/main.py` + 改的 test 檔。
- 結尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

## §8 流程鳥瞰
```
[現況] banner → _run_wiring: [主執行緒同步 import fastapi/uvicorn/pydantic ~數秒] → server.start
        → print → logic.run(menu)            ❌ menu 被擋數秒；'1' 被 buffer
        首次 speak/do_action/read → lazy import tts/action/stt（又一頓）

[修後] banner → spawn[worker-prewarm thread: import tts/action/stt]
        → _run_wiring: 主執行緒建輕量 bus+display → spawn[webui-boot thread: import server + start]
        → logic.run(menu)                     ✅ menu 立即；'1' 即時進 hawk（worker 已暖）
        web server / worker import 全在背景並行
```
