# myProgram/ — code_map（本層索引）

> 顆粒：中。

## 子目錄
- `sales/` — 銷售對話業務邏輯（**核心**）：主控狀態機、NLU、商品 / 數量解析、購物車、L0–L5 各層狀態與跨層流程（取消 / 服務確認 / 數量追問）、各層文案與常數。
- `vendor/` — 廠商 Hiwonder TonyPi SDK（🔒 `ActionGroupControl.py` / `Board.py` 禁改、只能 `import`；含 Pi-only 依賴）。
- `tts_cache/` — 內容定址語音快取（預熱資產 tracked＋執行期自我增長；perf_w5）。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `main.py` — 進入點：`TerminalSim` callback 類別（bound methods 餵 `logic.run`）、`_tick_countdown` 倒數 helper、各 worker 啟動與關閉（OOP 重構 W6）。
- `queue_worker.py` — `QueueWorker(ABC)` FIFO daemon 消費者骨架 + `drain_queue` helper（TtsWorker / ActionWorker 繼承；OOP 重構 W6）。
- `tts.py` — 語音合成 worker（edge-tts；繼承 `QueueWorker`；內容定址快取 → prefetch → 合成三層管線＋常駐 event loop，perf_w2/w5；計時倒數 / UX 過場）。
- `tts_prewarm.py` — TTS 預熱腳本（固定文案一次合成進 tts_cache；Pi 端 `python3.11 -m myProgram.tts_prewarm`）。
- `action.py` — 機器人動作組 worker（呼叫 vendor SDK 播動作；繼承 `QueueWorker`）。
- `input_reader.py` — 非阻塞鍵盤輸入 worker（producer，不繼承 QueueWorker；`inject` 供 STT 注入共用單 queue）。
- `stt.py` — 語音辨識 worker（Deepgram Nova-3 串流，websockets 同步 client；producer 形狀無常駐 thread，`arm`/`disarm` session 生命週期；arecord 音源；speech_final 文字注入 input queue；stt_p1）。
- `__init__.py` — 套件標記。
- `__main__.py` — `python -m myProgram` 進入點。
- `CLAUDE.md` — 本層導引。
