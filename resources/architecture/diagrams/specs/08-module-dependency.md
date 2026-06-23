# ⑧ 模組依賴地圖 · spec（內容事實 + 版面）

> 風格無關（淺色蠟筆風由 report-design-system 權威）。本檔＝**核對過的碼事實** + 版面決策，供未來重畫複用。
> 2026-06-23 由 orchestrator 自己從零重畫（初版過於擁擠「慘」、已刪重做）。鐵則1 核對來源：各模組 `import` 結構（top-level + lazy）。

## thesis（主角）

**Hexagonal / Ports-and-Adapters 注入邊界**：`sales/` 純邏輯核心**零向外依賴**（不 import 任何硬體 / vendor SDK / web / edge_tts / websockets / fastapi）；`main.py` 組合根是**唯一同時認得核心與 adapter 的模組**，把 adapter 的 bound method 當 **callback 注入** `logic.run(**callbacks)`——核心透過注入的函式指標 runtime 呼叫外部，但**原始碼層級對 adapter 零依賴**（依賴反轉）。

**signature ＝ 注入邊界 seam**：`main.py ══▶ sales/` 一條珊瑚粗箭頭「callbacks 注入 · 10 鍵 dict」，視覺主角。

## 核對過的碼事實（逐項回讀 .py）

### CORE — `sales/` 純邏輯核心（零硬體）
所有檔 top-level 只 import **stdlib + intra-sales**，無一觸硬體 / 外部服務：
- `logic.py` → `sales.cart`, `sales.states.machine.SalesMachine`（對話編排入口 `logic.run`）
- `states/machine.py` → `abc`, `dataclasses` + `sales.states`, `sales.cart`（SalesMachine + State(ABC) + Transition）
- `states/{l1,l2_l3_dialog,l4,l5,_*}.py` → `time`/`abc` + intra-sales（State pattern 各層）
- `nlu.py` → `re`, `typing` + `sales.constants`（純函式 NLU）
- `product_parser.py` → `sales.{nlu,phonetic,constants}`
- `cart.py` → `typing` + `sales.constants`（`Cart=dict[str,int]` 純資料）
- `dialog_io.py` → `dataclasses`, `typing`（純 stdlib，IO callback 束）
- `constants/*` → intra-sales（葉層資料：PRODUCTS / timing / 文案）
- **唯一外部觸點**：`phonetic.py` 的 **pypinyin** — ⛔ 頂層禁 import（Windows 未裝），只在 `_default_to_pinyin` **lazy import** + 注入 seam（`to_pinyin` DI）+ **缺則 graceful no-op**（回 None）。→ 畫成核心底下一個小 chip + 短虛線「lazy · 缺則 no-op」。

### 組合根 — `main.py`
- top-level 只 import `math/os/sys/threading/time`（stdlib）+ `sales.logic` + `sales.nlu.normalize_input`（**核心**）。**頂層零 worker / 零 web / 零硬體**。
- `TerminalSim.callbacks()` → **10 鍵 dict**（print_terminal / read_terminal_key / speak / speak_and_wait / do_action / read_customer_input / sleep / tts_is_idle / exit_program / show_hawk_help）→ `logic.run(**callbacks, display=, start_hawk=)`＝**注入邊界**。
- worker **lazy import 在 method 內**：`speak/speak_and_wait/sleep/tts_is_idle` ⤏ `tts`；`do_action` ⤏ `action`；`read_terminal_key/read_customer_input` ⤏ `input_reader`；`read_customer_input` 另 ⤏ `stt`。
- `_run_wiring`：`--hawk`/`--web`/`SALES_KEYBOARD` 旗標；`--web` 時 lazy ⤏ `web.bus`/`web.display`/（背景 thread）`web.server`，`server.start(bus, input_reader.inject, port=8137)`。
- `__main__.py` → `main.main`（進入點）。

### ADAPTERS — workers + web transport（driven/secondary）
- `queue_worker.py` → `queue/threading/abc`（純 stdlib）＝ `QueueWorker(ABC)` + `drain_queue`，**tts/action 繼承、input_reader 用 drain_queue** 的共用基座。
- `tts.py` → **top-level `import edge_tts`**（fail-fast）+ stdlib；`subprocess` 跑 **mpg123**（ALSA 播放）。外部：edge-tts + mpg123/ALSA。
- `action.py` → top-level 零 vendor；**lazy `from myProgram.vendor import ActionGroupControl`**（在 `on_thread_start`/`shutdown`）。外部：**Hiwonder TonyPi SDK（lazy）**。
- `stt.py` → top-level stdlib（`array/json/os/subprocess/threading/time/urllib`）；**lazy `from websockets.sync.client import connect`**（Windows 紅線）；`subprocess` 跑 **arecord**（ALSA 收音 `-c6` 抽 ch0）；連 **Deepgram Nova-3 WSS**（`wss://api.deepgram.com`）。
- `input_reader.py` → `os/queue/sys/threading/typing`（純 stdlib）+ `queue_worker.drain_queue`；producer，`inject` 供 STT/web 共用單 queue。**無外部依賴**。
- `web/` transport（鏡像 sales 狀態到瀏覽器，**與 sales 解耦**）：
  - 純 stdlib（Windows pytest）：`bus.py`（asyncio EventBus）、`display.py`、`commands.py`（皆讀 `sales.constants.PRODUCTS` ＝**向核心的向內依賴**）。
  - Pi-only（pydantic/fastapi/uvicorn）：`models.py`（DTO）、`app.py`（路由 + StaticFiles）、`server.py`（uvicorn 背景 thread）。
  - `app.py` `app.mount("/", _NoCacheStaticFiles(directory=webui/))` → **服務 `webui/` 靜態檔**。
- `webui/` → `os/sys/http.server`（純 stdlib），**獨立 process** 前端（buildless 靜態，亦可 `serve.py` 自服）。

### 依賴邊（要畫的箭頭，全部核對過）
- **注入（hero 珊瑚粗）**：`main.py ══▶ logic.run(**callbacks)` 10 鍵；附註「＋top-level import sales.logic ＝ main 對核心的唯一原始碼依賴」。
- **import（中性實線）**：`__main__→main`；`tts→edge-tts`/`tts→ALSA(mpg123)`；`action⤏Hiwonder(lazy)`；`stt→Deepgram WSS`/`stt→ALSA(arecord)`（websockets lazy 折進 Deepgram chip）；`web.{models,app,server}→fastapi·uvicorn·pydantic`；`web.app→webui/`；`web.{display,commands,app}→sales.constants`（向內）；`phonetic⤏pypinyin(lazy)`。
- **lazy import（虛線中性）**：`main⤏{tts,action,stt,input_reader,web}`。
- **不畫**：runtime data flow（inject queue / display callback 回呼）——本圖＝**原始碼 import 依賴**，不畫 runtime 資料流（避免混淆；依賴反轉在 note 文字交代）。

## 版面（Hexagonal 中置核心；adapter↔external 短樁不交叉）

- 畫布 1960×1200。title y32 / subtitle y80。
- **左欄 explainer** x60–500：legend（色彩語意 + 依賴角色）上、`依賴三鐵則 / 依賴方向` note 下。
- **組合根 main.py**（coral hero）頂中 x540–1080 y150–300。
- **注入 seam** 垂直珊瑚粗箭頭 y300→y340（短、最顯眼）。
- **CORE sales/**（核心 region，coral-tint 底 + 內部 rows，**不拆多卡**降擁擠）x540–1080 y340–880：header + 5 子模組 row + badge bar；底掛 `pypinyin` 小 chip。
- **ADAPTERS** 右欄 x1140–1500 直立堆：tts / action / stt / input_reader / queue_worker(小) / web/(拆 stdlib·Pi-only) / webui/。
- **EXTERNAL** 最右 x1560–1900：edge-tts / Hiwonder(lazy) / Deepgram WSS / ALSA / fastapi·uvicorn·pydantic，各**緊貼**對應 adapter 右側（箭頭 60px 短樁、零交叉）。
- **note 底帶**（所以呢·依賴三鐵則）x540–1900 底部 or 左欄。
- 色語意：coral=main 組合根 hero / green=sales 核心 / blue=worker(tts·action·stt·input_reader) / gray=stdlib 基座(queue_worker) / purple=web transport / cyan=webui 前端 / 中性 chip=外部依賴。

## 清潔度教訓（初版「慘」對症）

- 初版擁擠 → 本版：核心收成**單一 region 內部 rows**（非 8 張卡）、external chip **緊貼** adapter（短樁零交叉）、左欄吸納 legend/note 留白、注入 seam 為唯一 hero 邊。
