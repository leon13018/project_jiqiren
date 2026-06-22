# 圖⑤ 部署 / 網路拓樸 — 畫圖 spec + 畫圖計畫

> 來源：`00-system-overview.md §2/§7`、`30-web-mirror-and-frontend.md §6/§8`、實讀核對（2026-06-22）：
> `main.py`（`_run_wiring`：`--hawk`/`--web`/`SALES_KEYBOARD`、背景 `webui-boot` 啟 server）、
> `web/server.py`（`start(... host="0.0.0.0", port=8137)` uvicorn daemon thread `webui-server`）、
> `web/app.py`（`/api/state` `/ws/state` `/`(StaticFiles webui/)）、
> `webui/serve.py`（純 stdlib no-cache 靜態 server，預設 8137、`0.0.0.0`）、
> `resources/requirements/raspberry_pi_setup.md`（Pi 已裝清單）。

> ✅ **已交付（2026-06-22 Wave B）**：`05-deployment-topology.{html,png,svg}` 三式同名（stage 1960×1020）。最終版面隨使用者 QA 微調定版（填四區死空白·四區撐到畫布邊 / 金鏈端點落渲染端 group 左框邊 x1466 不穿卡 / `/ws/state` 標籤避金弧 / **frame-label 改浮框內側使虛線框完整**[共用 theme `.frame-label` translate(22,7)，①連帶重出] / 硬體三卡間距 34 / serve.py 預覽鏈方向修正），**以交付 html 為準**。自檢由 3-opus QA panel 執行。
>
> ✅ **淺色換膚交付（2026-06-23）**：copy `_legacy-dark/05` → 外科改 head/濾鏡 + 兩處 inline OKLCH 換淺，**body 座標逐字保留**；6-opus QA panel 0 內容錯誤。使用者視覺精修：Pi 4 裝置框 + frame-label 加 Rough 蠟筆 hachure 填；frame-label 移除外框、translate 改 `(22,12)` 在框頂↔卡片間上下置中。**以 `diagrams/05-deployment-topology.html` 淺色版為準**（深色版在 `_legacy-dark/`）。

## 主題一句話
**Pi 是 server、但自己渲染不了前端**：Pi 4 跑 `python -m myProgram --hawk --web` 當對話程式 + FastAPI 顯示鏡像
（`0.0.0.0:8137`），同 wifi 的**筆電 / 手機瀏覽器**連 `raspberrypi.local:8137` 負責渲染玻璃 UI（Pi 4 GPU +
Chromium<111 不支援 OKLCH → 自身瀏覽器跑不動前端）；STT/TTS 兩朵雲（Deepgram / edge-tts）走網際網路；
本地硬體（ReSpeaker USB 麥 / 喇叭 / TonyPi 伺服）掛在 Pi 上。

## 核對過的碼事實（權威）

### Pi 主機（server 角色）
- 啟動：`python -m myProgram --hawk --web`（`--hawk`=直接叫賣；`--web`=背景啟顯示鏡像 server）。`_run_wiring` 防呆：無 mode flag 又 `SALES_KEYBOARD=0` → early return。
- **單一 process**：主線程（SalesMachine）+ daemon（TtsWorker / ActionWorker / InputReader / 每輪 STT / `webui-server`）（細節見圖①，本圖只標「single process + workers」一張卡，別重畫並行模型）。
- **FastAPI / uvicorn server**：`web/server.start(bus, input_reader.inject, host="0.0.0.0", port=8137)`，daemon thread `webui-server`；路由 `/api/state`（GET 快照）、`/ws/state`（WS 推送 + 上行命令）、`/`（`_NoCacheStaticFiles` 出 `webui/` 靜態檔）。
- 背景 `webui-boot` thread 做笨重 import（fastapi/uvicorn/pydantic）+ `server.start`，不擋對話 menu；啟動失敗 graceful（印繁中錯誤、機器人照常）。

### 本地硬體（掛 Pi，gray）
- **ReSpeaker Mic Array V2**（USB，4 麥 + XVF-3000）→ `arecord -c6 抽 ch0`（細節屬圖⑥，本圖只標 USB 麥 → STT）。
- **喇叭**（ALSA ← `mpg123` 播放，TTS 輸出）。
- **TonyPi 伺服馬達**（vendor SDK `Act.runAction` 播 `/home/pi/TonyPi/ActionGroups/<name>.d6a`）。

### 雲端（網際網路，外部）
- **Deepgram Nova-3**：STT 串流 WSS（`model=nova-3&language=zh-TW...endpointing=300`），需 `DEEPGRAM_API_KEY`（寫入 `~/.bashrc`）；缺金鑰 / 401 → STT 停用、鍵盤照常。
- **edge-tts**（Microsoft）：TTS 合成（HTTPS）；命中內容定址快取則零網路（斷網可播已快取句，細節屬圖⑦）。

### 渲染端（client，同 wifi LAN，cyan）— ★ 主角
- **筆電 / 手機瀏覽器**連 `http://raspberrypi.local:8137/`（**不加** `?demo=1`）→ live：`/api/state` 取快照 + `/ws/state` WS 鏡像下行 + 觸控命令上行。**前端在這裡渲染**（Glaze 玻璃 UI）。
- **Pi 4 自身瀏覽器跑不動前端**（GPU + Chromium<111 無 OKLCH，`colors.css` 大量 OKLCH）→ demo 由 client 渲染、Pi 只當 server。

### 獨立預覽（次要拓樸，secondary）
- `python3.11 myProgram/webui/serve.py 8137` → `localhost:8137/?demo=1`：純 stdlib no-cache 靜態 server（**無 API / WS**），本機假資料 + 切換器，**不需 Pi、不需對話程式**。純看 UI。

### Pi 已裝關鍵依賴（`raspberry_pi_setup.md`，Python 3.11）
edge-tts · websockets · fastapi · uvicorn（**純 uvicorn 非 `[standard]`** — 避 uvloop/httptools C 擴充 Pi wheel 風險）· pypinyin · RPi.GPIO · pyserial · pigpio；apt：mpg123。Python 3.11.9 source build（edge-tts 依賴）。

## thesis / 主角（boldness 集中一處）
**render-offload 金鏈** —— Pi `:8137` server → client 瀏覽器（筆電/手機）那條 WS 鏈做成暖金主角弧（`.hawk`+`ah-hawk`），
旁標「Pi 自身瀏覽器跑不動前端（GPU + Chromium<111 無 OKLCH）→ client 渲染、Pi 只當 server」。其餘鏈路安靜：
本地硬體 = 短實線（USB/ALSA/serial）；雲端 = 虛線 `.async`（WSS/HTTPS over internet）。一處金、餘皆靜。

## 視覺色彩語意（共用 theme + legend，6 列）
藍=Pi 主機（host + single process）/ 綠=Pi 上網路服務（FastAPI server `:8137` 端點）/ 青=渲染端 client（筆電/手機瀏覽器）/
橘=雲端服務（Deepgram / edge-tts，需網際網路）/ 灰=本地硬體周邊（ReSpeaker / 喇叭 / TonyPi 伺服）/ 紫=網路鏈路（wifi LAN · WS · internet，邊標籤用）。
金 = 主角 render-offload 鏈（非分類色）。

## 版面（拓樸圖；非時序）
- `.stage` 約 **1960 × 1280**；DPR 每次實測。標題列頂置中（`FIG.05`）。
- **上帶 · 雲端**（橘）：Deepgram Nova-3（WSS）+ edge-tts（HTTPS）兩朵雲卡，虛線 `.async` 往下連 Pi，標 `STT 串流 / 需 DEEPGRAM_API_KEY`、`TTS 合成 / 命中快取則免網`。
- **中央 · Pi 4 裝置框**（藍 `.frame` 帶 frame-label「Raspberry Pi 4 · python -m myProgram --hawk --web · 單一 process」）：內含「對話程式（主線程 + workers，→ 圖①）」卡 + 「FastAPI server `0.0.0.0:8137`：/api/state · /ws/state · /(webui 靜態)」綠卡。
- **左側 · 本地硬體**（灰 chip / 小卡）：ReSpeaker Mic Array V2（USB）→ 短線標 `USB → arecord ch0`；喇叭 ← 標 `ALSA ← mpg123`；TonyPi 伺服 ← 標 `vendor SDK serial`。聚攏靠 Pi 左緣。
- **右側 · 同 wifi LAN 渲染端**（青）：筆電 + 手機兩張 client 卡（瀏覽器 `raspberrypi.local:8137`，渲染玻璃 UI），用**金 WS 鏈**接 Pi server（雙向：WS 下行鏡像 / 觸控上行）。此區即主角。
- **下角 · 獨立預覽**（次要，compact 小卡 / note，別做空蕩大卡）：`serve.py 8137 → localhost/?demo=1`，標「無 API/WS · 本機假資料 · 不需 Pi」。
- legend 收一空角、note 收另一角；≥30px 不碰任何卡 / 框。

## 邊清單（先卡片層截圖修版面，再加 SVG 箭頭層）
- 雲 ↔ Pi：虛線 `.async`（Deepgram→Pi STT；edge-tts→Pi TTS），標 WSS / HTTPS。
- 本地硬體 ↔ Pi：短實線 `.flow`（USB 麥→Pi；Pi→喇叭；Pi→伺服），標 USB / ALSA / serial。
- **Pi server ↔ client：金 `.hawk` 雙向**（`http://raspberrypi.local:8137/`，WS 雙向：下行 phase 鏡像 / 上行觸控命令）—— 主角。
- 獨立預覽：自成一條 client→serve.py 短鏈（與 Pi 區分開、別連到 Pi）。
> 路由鐵則：金鏈走清空 gutter 不擦雲 / 硬體卡；虛線雲鏈與金鏈分屬不同 lane；邊標籤落線中段清空處 + 深色 halo。

## note（角落，填「所以呢」3 點）
- **Pi serves, client renders**：Pi 4 自身瀏覽器跑不動玻璃 UI（GPU + Chromium<111 無 OKLCH）→ 畫面由同 wifi 的筆電 / 手機渲染，Pi 只當 server。
- **兩朵雲需網際網路**：Deepgram（STT，需 API key）/ edge-tts（TTS 合成，命中快取則免網）；斷網時 STT 停用走鍵盤、TTS 走已快取句。
- **兩條出菜路徑**：真機 live = `--web` FastAPI（含 API/WS）；純看 UI = `serve.py ?demo=1`（純靜態、不需 Pi）。

## 自檢必裁區（render-pipeline §5；先全圖再局部）
① 全圖：四區（雲 / Pi / 本地硬體 / 渲染端）分明、無大片死空白、無卡片相碰。② 金 render-offload 鏈箭頭頭真觸 client 卡與 Pi server 卡、頭色＝金（GetPixel 比色）、雙向都有頭。③ 雲端虛線與硬體實線可辨、標籤（WSS/HTTPS/USB/ALSA/serial/:8137）不溢不壓線。④ Pi 框內兩卡（process / server）內容垂直置中、不溢框。⑤ 獨立預覽小卡不空蕩、不與 Pi 區相碰。⑥ 四角無黑邊（2× 匯出 GetPixel）。
