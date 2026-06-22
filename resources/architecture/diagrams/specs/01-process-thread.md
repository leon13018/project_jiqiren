# 圖① Process / Thread 並行模型 — 畫圖 spec

> 來源:`00-system-overview.md §3` + 實讀 `main.py / queue_worker.py / tts.py / action.py / input_reader.py / stt.py / web/server.py / web/bus.py`(2026-06-21 逐檔核對)。

> ✅ **已交付（2026-06-22 Wave A）**：`01-process-thread.{html,png,svg}` 三式同名。最終版面隨使用者 mockup 定版（左脊 MAIN→queue→daemon→chip + 右欄 STT 置頂→input queue→InputReader + 3→1 金扇入主角 + 緊湊下方），**以交付 html 為準**；下方「畫圖計畫」為原始設計、與最終 html 略有出入。

## 主題一句話
單一 process 內:1 條**主線程**跑純單線程 L0–L5 對話狀態機;所有「會阻塞 / 要並行」的事丟**背景 daemon thread**,以 **queue + EventBus** 解耦。全部 `daemon=True`,退出用 `os._exit(0)` 強退隨 process die。

## 核對過的 thread 清單(權威)

| thread name | 來源 | 形狀 | 生命週期 | 通訊 / 外部 |
|---|---|---|---|---|
| **主線程 main** | `logic.run`→`SalesMachine.run()` | 單線程對話迴圈 | 全程 | 呼叫 10 個 callback;讀 input queue |
| `TtsWorker` | `tts.py` 模組 singleton(import 起) | consumer(QueueWorker)+常駐 asyncio loop | 常駐 | FIFO queue ← speak;→ `mpg123` 子程序 |
| `ActionWorker` | `action.py` 模組 singleton(import 起) | consumer(QueueWorker) | 常駐 | FIFO queue ← do_action;→ vendor SDK `Act.runAction` |
| `InputReader` | `input_reader.py` singleton | producer(stdin→queue) | 常駐(`SALES_KEYBOARD=1` 才起 reader thread) | `stdin.readline`→ input queue |
| `webui-server` | `web/server.py` uvicorn | async loop | 常駐(`--web`,至 `server.stop`) | EventBus→WS 推前端;觸控命令→inject |
| `SttSender` | `stt.py` `arm()` | producer(arecord→ws.send) | **每輪一生**(arm→disarm,<12s) | `arecord` 子程序 read → Deepgram WS send |
| `SttReceiver` | `stt.py` `_ensure_connected()` | consumer(ws.recv→sink) | **每輪一生**(連線→disarm/死) | Deepgram WS recv → `_capturing` 閘 → `input_reader.inject` |
| `SttPrearm` | `stt.py` `prearm()` | 一次性(背景預連線) | **跑完即終** | 藏首輪握手 540ms |
| `worker-prewarm` | `main._prewarm_workers` | 一次性(import 暖機) | **跑完即終** | import tts/action/stt |
| `webui-boot` | `main._run_wiring`(`--web`) | 一次性(笨重 import+啟 server) | **跑完即終** | import fastapi/uvicorn + `server.start` |

## 三條通訊主幹(畫成邊)
1. **FIFO queue(紫)**:主線程 `speak`→TtsWorker queue、`do_action`→ActionWorker queue(各自單 queue 單消費者)。
2. **單一 input queue 扇入(★重點)**:3 producer → 1 consumer。
   - 鍵盤(`InputReader._loop` stdin)
   - STT(`SttReceiver`→`input_reader.inject`)
   - web 觸控(`webui-server`→`commands.to_token`→`input_reader.inject`)
   → 全部進**同一個** queue,主線程 `read_*` 單一消費。「producer 端零分流」是設計鐵則。
3. **EventBus(紫)**:主線程 `display` callback → `bus.publish` → `asyncio.run_coroutine_threadsafe` → webui-server async loop → WS 廣播前端。

## 視覺色彩語意(共用 theme)
藍=主線程 / 綠=常駐 daemon / 青=每輪一生 / 橘=一次性 / 紫=queue·EventBus 通訊 / 灰=子程序·外部(mpg123 / vendor SDK / arecord / Deepgram / 瀏覽器)。

## 版面(緊湊擺位)
- 標題列頂置中。整張包一個半透明圓角「單一 Process」外框(暗示 one process)。
- 主線程:上方置中大卡(藍)＝hub。
- 一次性 3 卡(橘):右上角收一束(bootstrap,不搶中心)。
- 常駐 daemon 4 卡(綠)橫排;各自把外部子程序(灰)收成底部小掛件(相關物件聚攏)。
- 每輪一生 STT(青):子框「STT session(arm→disarm,一輪<12s)」內含 Sender/Receiver + arecord/Deepgram(灰)。
- 通訊:queue/EventBus/input-queue 扇入用箭頭+紫標籤;input-queue 3→1 扇入做視覺強調。
- legend 收左下角空位。SVG overlay 畫箭頭(精確座標),毛玻璃卡用絕對定位。

---

## 畫圖計畫（SDD plan, 2026-06-22 重畫；棄 Mermaid 後 HTML/CSS 版）

> step 3–4 設計定案。座標為**起手近似值 + lane 規則**,實際像素由實作者在 render→截圖自檢迴圈微調(先卡片層→修版面→再 SVG 箭頭層)。骨架 = `architecture-diagram/assets/skeleton.html`(淺色自足);**視覺風格＝ `report-design-system` skill**(淺色蠟筆;原深色 `theme/` 已移入 `_legacy-dark/`、不再用)。淺色定版見 report-design-system `assets/benchmarks/01-process-thread.*`。

### thesis / 主角（boldness 集中一處）
**單一 input queue 的 3→1 扇入**(鍵盤 / STT / web 觸控 → 同一 queue → 主線程單一消費,「producer 端零分流」鐵則)。比照圖② enter_hawk:用**暖金 `.hawk` 線 + `ah-hawk` 箭頭頭**把 3 條 producer 匯入線 + 1 條 consume 線做成視覺焦點;其餘邊一律安靜的 `.flow`(白/紫標籤)。

### 畫布 / 外框
- `.stage` **1960 × 1400**(複雜度高,畫大優先不相碰;實作量座標驗證)。
- `.frame`(單一 Process):約 `left:40 top:112 width:1880 height:1252`;`.frame-label`=「單一 PROCESS · 全 thread daemon=True → 退出 os._exit(0) 隨 process die」。

### 色彩 legend（左下角 `.legend`，6 列）
藍=主線程 / 綠=常駐 daemon / 青=每輪一生(STT session) / 橘=一次性(bootstrap) / 紫=queue · EventBus / 灰=子程序 · 外部。

### 節點清單（卡片層;eyebrow→name(mono)→meta(mono)→desc(cjk)）
**主線程(blue,大卡,頂置中 hub)**
- eyebrow `MAIN · 主線程`;name `logic.run → SalesMachine.run()`;meta `單線程 L0–L5 對話迴圈`;desc `呼叫 10 個 callback;讀 input queue 單一消費`。

**常駐 daemon ×4(green,橫排,各帶底部灰 chip)**
- `TtsWorker` — meta `consumer + 常駐 asyncio loop`;desc `FIFO queue ← speak;synth+播放`;chips:`mpg123`(子程序,播放)、`edge-tts`(雲端 synth)。〔eyebrow 皆 `DAEMON · 常駐`〕
- `ActionWorker` — meta `consumer (QueueWorker)`;desc `FIFO queue ← do_action`;chip:`vendor SDK Act.runAction`。
- `InputReader` — meta `producer (stdin→queue)`;desc `SALES_KEYBOARD=1 才起 reader thread`;chip:`stdin`。
- `webui-server` — meta `uvicorn async loop`;desc `--web 才起,至 server.stop`;chip:`browser (WS)`(雙向)。

**每輪一生 STT ×2(cyan,在 STT session 子框內)**
- `SttSender` — eyebrow `PER-ROUND · 每輪一生`;meta `producer (arecord→ws.send)`;desc `arm→disarm 一生(<12s)`。
- `SttReceiver` — eyebrow `PER-ROUND · 每輪一生`;meta `consumer (ws.recv→sink)`;desc `_capturing 閘 → inject`。

**一次性 ×3(orange,右上角 bootstrap 束,短卡)**
- `worker-prewarm` — desc `背景 import tts/action/stt 暖機`。
- `webui-boot` — desc `import fastapi/uvicorn + server.start`。
- `SttPrearm` — desc `背景預連線,藏首輪 540ms 握手`。〔eyebrow 皆 `ONE-SHOT · 一次性`〕

**通道節點(purple,pill/小框,非卡片)**
- `TTS queue`(FIFO,單消費)、`Action queue`(FIFO,單消費)、`input queue`(★HERO,較大,金邊;附註「InputReader 所有;inject() 共用」)、`EventBus`(`run_coroutine_threadsafe → async loop → WS 廣播`)。

**外部 chip(gray)**:mpg123 / edge-tts / vendor SDK / stdin / browser / arecord / Deepgram(共 7,分掛各 thread)。

### 邊清單（先卡片層截圖修版面,再加此 SVG 層）
輸出(main 往下發,`.flow` 白線):
- main → TTS queue(標 `speak`)→ TtsWorker;TtsWorker → mpg123 / → edge-tts。
- main → Action queue(標 `do_action`)→ ActionWorker → vendor SDK。
- main → EventBus(標 `display`)→ webui-server → browser(標 `WS 廣播`)。
輸入(往上匯入 main,**金線 `.hawk` + `ah-hawk`,主角**):
- InputReader → input queue(標 `鍵盤 stdin`);webui-server → input queue(標 `web 觸控 inject`);SttReceiver → input queue(標 `STT inject · _capturing 閘`)。**3 線匯聚** → input queue → main(標 `read 單一消費`)。
STT 內部 pipeline(`.flow`):arecord → SttSender(標 `音框`)→ Deepgram(標 `ws.send`)→ SttReceiver(標 `ws.recv`)。
外部讀入:stdin → InputReader(`.flow`);browser ↔ webui-server 雙向。
> 路由鐵則:金匯聚線走 InputReader / webui-server 之間清空 gutter,不擦過卡;SttReceiver→queue 走垂直 gutter 再轉入,別斜穿 daemon 列。標籤壓線中段(深色 halo)。

### note（右下角 `.note`，3 點，填「所以呢」）
- 全部 `daemon=True` → 主程式 `os._exit(0)` 強退,daemon 隨 process die,不 join。
- 阻塞 / 並行的事全推背景 worker;主線程只跑純單線程對話邏輯。
- **producer 端零分流**:鍵盤 / 語音 / 觸控 → 同一 input queue,主線程單一消費(無旗號分流 race)。

### 自檢必裁區（render-pipeline §5;先全圖再局部）
① input queue 金扇入匯聚區(3→1 線不交纏、不穿卡、有金箭頭頭)。② daemon 列每卡最長 desc + chip 不溢出。③ STT 子框內 pipeline 4 段不壓線、Deepgram/arecord chip 字完整。④ bootstrap 3 短卡不互疊。⑤ 跨 band y 不重疊(channel pill 列 / daemon 列 / STT 子框)。⑥ 四角無黑邊(2× 匯出 GetPixel)。

### 偏離舊 spec 的一處（待使用者驗收確認）
TtsWorker 外部由舊 spec 的「僅 mpg123」**補上 `edge-tts`(雲端 synth)**——`tts._synthesize` 實呼 `edge_tts.Communicate(...).save()`,是真實外部依賴,畫上更完整。(內容定址快取屬圖⑦ TTS 管線,本圖不畫。)
