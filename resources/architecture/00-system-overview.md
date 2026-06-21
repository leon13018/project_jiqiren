# 00 · 系統鳥瞰

> 以 `myProgram/` 實際程式碼為準（2026-06-21）。本檔給全局視角；各子系統細節見 `10` / `20` / `30`。

---

## 1. 這是什麼

Raspberry Pi 4 上的**互動式銷售輔助機器人**：人形機器人（Hiwonder TonyPi）站在攤位前，以**規則匹配**（非 LLM）跟顧客對話完成點餐 / 收款模擬。兩個商品（冰紅茶、刮刮樂）。對話走 L1（叫賣 / 待機）→ L2/L3（點餐）→ L4（結帳掃碼）→ L5（致謝）的多層狀態機，搭配語音合成（TTS）、語音辨識（STT）、機器人動作、以及一個鏡像到瀏覽器的玻璃風點餐畫面。

設計鐵則：**業務邏輯（`sales/`）嚴格不碰硬體 / 廠商 SDK / I/O**，全靠 callback 注入 → 整套對話邏輯可在 Windows 跑 pytest（584+ 測試）。硬體與 I/O 只在 `main.py` 入口層與各 worker wire 起來。

---

## 2. 進入點與啟動模式

| 進入點 | 用途 |
|---|---|
| `python -m myProgram`（`__main__.py` → `main.main()`）| 正式跑法 |
| `python myProgram/main.py` | 同上（`main.py` 有 `if __name__ == "__main__"`）|
| `python3.11 -m myProgram.tts_prewarm` | 一次性預熱 TTS 快取（非 daemon，bootstrap 用）|
| `python3.11 myProgram/webui/serve.py [port]` | 純前端預覽伺服器（無 API / WS；配 `?demo=1`）|

**啟動旗標 / env**（`main._run_wiring`）：

| 旗標 / env | 效果 |
|---|---|
| `--hawk` | 直接進叫賣模式（跳主選單），複用 `enter_hawk_immediately` |
| `--web` | 背景啟 FastAPI 顯示鏡像伺服器（:8137）；無此旗標則 `display` 為 no-op、完全不 import web |
| `SALES_KEYBOARD=1` | 開鍵盤輸入（預設 0 = 關，demo 走 web / 語音驅動）|

**啟動防呆**：若既無 `--hawk` 又無鍵盤（`SALES_KEYBOARD=0`），等於沒有任何可用控制方式 → 印明確繁中訊息後 early return（不啟 web、不跑對話），交回 cleanup。合法組合：① `--hawk`（鍵盤開關皆可）；② 無 mode flag 但 `SALES_KEYBOARD=1`。典型 demo 啟動：`python -m myProgram --hawk --web`。

---

## 3. Process / Thread 模型（最關鍵的一張圖）

整個程式是**單一 process**，內含一條主線程 + 數條背景 daemon thread。主線程跑純單線程對話狀態機；所有「會阻塞 / 要並行」的事都丟背景 thread，透過 **queue** 與 **EventBus** 解耦。

```
主線程 (main)
  └─ logic.run → SalesMachine.run()  純單線程 L0–L5 對話迴圈
         │  對外動作全部經 callback 注入（不直接碰硬體）
         ▼
  ┌──────────────┬──────────────┬───────────────┬─────────────────┐
  │ speak        │ do_action    │ read_*        │ display(phase…) │
  ▼              ▼              ▼               ▼
[TtsWorker]   [ActionWorker]  [InputReader]   [EventBus]
 daemon        daemon          daemon(producer) (同步→async 橋)
 FIFO queue    FIFO queue      stdin→queue        │
 → mpg123      → vendor SDK      ▲                ▼
                                 │            [webui-server]
                            [stt 每輪]         uvicorn daemon
                          sender/receiver       async loop
                          thread + arecord      → WS 推前端
                                 │                    │
                                 └── speech_final ────┘ 觸控命令
                                     inject 回 queue   經 commands→inject
```

背景 thread 一覽：

| thread name | 來源 | 形狀 | 生命週期 |
|---|---|---|---|
| `TtsWorker` | `tts.py` singleton | consumer（`QueueWorker`）| 常駐，import 時起 |
| `ActionWorker` | `action.py` singleton | consumer（`QueueWorker`）| 常駐，import 時起 |
| `InputReader` | `input_reader.py` singleton | producer（stdin→queue）| 常駐（`SALES_KEYBOARD=1` 才起 reader 迴圈）|
| `SttSender` / `SttReceiver` | `stt.py` | 每輪收音動態起 / 收 | 一輪（<12s）一生，disarm 收線 |
| `worker-prewarm` | `main._prewarm_workers` | 一次性 import 暖機 | 跑完即終 |
| `webui-boot` | `main._run_wiring`（`--web`）| 一次性：笨重 import + 啟 server | 跑完即終 |
| `webui-server` | `web/server.py`（`--web`）| uvicorn async loop | 常駐至 `server.stop` |

全部 `daemon=True` → 程式退出時用 `os._exit(0)` 強退即可隨 process die（見 `10` 的 cleanup 段）。

---

## 4. 模組地圖

```
myProgram/
├── main.py            入口層 wire-up：TerminalSim callbacks + 啟動分流 + cleanup（→ 10）
├── __main__.py        python -m myProgram 進入點
├── queue_worker.py    QueueWorker(ABC) FIFO 消費者骨架 + drain_queue（→ 10）
├── tts.py             TTS worker：edge-tts + 內容定址快取 + prefetch + 常駐 loop（→ 10）
├── stt.py             STT worker：Deepgram Nova-3，每輪 websocket + arecord（→ 10）
├── action.py          動作 worker：呼叫 vendor SDK 播動作組（→ 10）
├── input_reader.py    非阻塞 stdin reader（producer）+ STT/web 命令注入 sink（→ 10）
├── tts_prewarm.py     一次性 TTS 快取預熱腳本（→ 10）
├── tts_cache/         內容定址語音快取（預熱資產 tracked + 執行期自增長）
├── vendor/            Hiwonder TonyPi SDK（🔒 禁改，只 import）
├── sales/             ★核心業務邏輯：L0–L5 對話狀態機（→ 20）
│   ├── logic.py           facade：組 callbacks + 建 SalesMachine
│   ├── cart.py            購物車資料模型（純資料）
│   ├── nlu.py             意圖分類 + 數量解析（純函式）
│   ├── product_parser.py  多商品 + 數量 token parser
│   ├── phonetic.py        拼音近音糾錯（pypinyin lazy）
│   ├── dialog_io.py        IO callback 束 dataclass
│   ├── constants/         L0–L5 常數 subpackage（純資料）
│   └── states/            L1 / dialog(L2L3) / L4 / L5 + 跨層流程 + SalesMachine
├── web/               FastAPI 顯示鏡像 transport（→ 30）
│   ├── bus.py             EventBus：同步機器人線程 → async loop 廣播橋
│   ├── display.py         display callback web 版（phase+cart→dict）
│   ├── models.py          Pydantic DTO（前後端契約）
│   ├── app.py             FastAPI 路由 /api/state + /ws/state + StaticFiles
│   ├── server.py          uvicorn 背景執行緒生命週期
│   └── commands.py        觸控上行命令 → 對話既有 token
└── webui/             buildless 靜態前端（→ 30）
    ├── index.html / app.js / app.css
    ├── serve.py           純 stdlib no-cache 靜態伺服器
    └── tokens/            Glaze Liquid Glass 設計語彙（CSS 變數）
```

★ = 系統核心。`→ NN` 指向本資料夾對應細節文件。「檔在哪」一律先查巢狀 `.claude/code_map.md`。

---

## 5. 端到端資料流（一輪互動）

以「顧客觸控開始點餐 → 點一瓶冰紅茶 → 結帳 → 致謝」為例：

1. **喚醒**：瀏覽器觸控「開始點餐」→ WS 送 `{type:"wake"}` → `commands.to_token` 翻成 `"t"` → `input_reader.inject` → 主線程 `read_terminal_key` 取得 `t` → L1 hawk 轉 dialog。
2. **進 dialog**：`SalesMachine` emit `display("ordering", …)` → EventBus → 前端切點餐主畫面；機器人 `speak` 招呼（TtsWorker 背景合成 + mpg123 播放）、`do_action` 揮手（ActionWorker 背景播動作組）。
3. **點餐**：顧客語音「我要一瓶冰紅茶」→ arecord 收音 → STT websocket → `speech_final` → `inject` → 主線程 `read_customer_input` 取得文字 → `nlu` / `product_parser` 解析 → `cart.add_item` → dialog 每輪 emit `display("ordering", cart)` → 前端購物車逐項長出。
4. **結帳**：顧客說「結帳」→ dialog 進 `checkout_confirm`（emit phase → 前端跳確認卡片）→ 確認 → 轉 L4 → emit `display("checkout", …)` → 前端顯示 QR；掃碼模擬（觸控 `{type:"pay"}`→`"s"`）→ 轉 L5。
5. **致謝**：L5 emit `display("thankyou", cart, paid=total)` → 前端全屏謝謝惠顧；`do_action` 揮手、`sleep(3)` 禮貌間隔 → 清 cart → 回 L1。

關鍵：**前端所有畫面切換都由後端 emit 的 phase 驅動**（phase-driven），觸控只「請求」、不本地樂觀改畫面——因為觸發也可能來自語音或自動結帳（非 UI 操作）。

---

## 6. env 旋鈕家族

各模組**各自讀**同名 env（不新增跨模組 import；production 同一啟動 env 值一致）。預設值一律「不改行為 / demo 友善」。

| env | 預設 | 作用 | 讀取處 |
|---|---|---|---|
| `SALES_KEYBOARD` | 0 | 開鍵盤輸入迴圈 | `input_reader` / `main._run_wiring` |
| `SALES_VOICE` | 0 | 顯示終端 echo（`[語音]`/`[動作]`）+ 導航列印（選單 / L4 明細）| `main` / `tts` / `action` |
| `SALES_SHOW_COUNTDOWN` | 0 | 印每秒倒數行（`timeout = N` / `wait = N`），純視覺 | `main._tick_countdown` |
| `STT_TTS_TIMING` | 0 | 印 TTS / STT 計時 debug | `tts` / `stt` |
| `STT_ENDPOINTING_MS` | 300 | Deepgram endpointing（450 會害 timeout，回歸 300）| `stt` |
| `STT_PREROLL_MS` | 0 | 收音前 pre-roll 靜音暖串流 | `stt` |
| `STT_CAPTURE_CHANNELS` | 6 | arecord 聲道數（ReSpeaker 原生 6）| `stt` |
| `STT_ASR_CHANNEL` | 0 | 抽第幾聲道（ch0 = 處理過 ASR 聲道）| `stt` |
| `STT_ARECORD_DEVICE` | — | 指定 arecord 收音裝置 | `stt` |
| `STT_MIC_OPEN_DELAY_MS` | 0 | 開麥前延遲（讓喇叭尾音排空）| `main` |
| `STT_EARLY_MIC` | 0 | 提示音播放期間就開麥串流暖機（不注入）| `main` |
| `DEEPGRAM_API_KEY` | — | STT 金鑰（缺則 STT 停用、鍵盤照常）| `stt` |

---

## 7. 兩個展示拓樸場景

- **筆電預覽**（純看 UI）：`python3.11 myProgram/webui/serve.py 8137` → 瀏覽器 `localhost:8137/?demo=1`，本機假資料 + 切換器，**不需要 Pi、不需要對話程式**。
- **真機 live**（demo 主場）：Pi 跑 `python -m myProgram --hawk --web`，同 wifi 裝置連 `http://raspberrypi.local:8137/`（**不加** `?demo=1`）→ WS 鏡像真實對話狀態。**Pi 4 自身瀏覽器跑不動前端**（GPU + Chromium < 111 不支援 OKLCH）→ 畫面由 client 筆電 / 手機渲染，Pi 只當 server（見 `30`）。

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-06-21 | 初版：取代封存的 2026-05-24 願景文件，以實作現況重寫全系統鳥瞰。|
