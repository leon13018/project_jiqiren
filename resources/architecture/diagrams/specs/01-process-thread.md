# 圖① Process / Thread 並行模型 — 畫圖 spec

> 來源:`00-system-overview.md §3` + 實讀 `main.py / queue_worker.py / tts.py / action.py / input_reader.py / stt.py / web/server.py / web/bus.py`(2026-06-21 逐檔核對)。

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

## 版面(緊湊擺位,1600×1040 畫布)
- 標題列頂置中。整張包一個半透明圓角「單一 Process」外框(暗示 one process)。
- 主線程:上方置中大卡(藍)。
- 一次性 3 卡(橘):右上角收一束(bootstrap,不搶中心)。
- 常駐 daemon 4 卡(綠)橫排;各自把外部子程序(灰)收成底部小掛件(相關物件聚攏)。
- 每輪一生 STT(青):子框「STT session(arm→disarm,一輪<12s)」內含 Sender/Receiver + arecord/Deepgram(灰)。
- 通訊:queue/EventBus/input-queue 扇入用箭頭+紫標籤;input-queue 3→1 扇入做視覺強調。
- legend 收左下角空位。SVG overlay 畫箭頭(精確座標),毛玻璃卡用絕對定位。
